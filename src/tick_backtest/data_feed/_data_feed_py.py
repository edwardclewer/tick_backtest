# Copyright 2025 Edward Clewer
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from tick_backtest.data_feed.tick import Tick
from tick_backtest.exceptions import DataFeedError

__all__ = ["DataFeed", "NoMoreTicks", "Tick", "get_data_months", "DataFeedError"]

logger = logging.getLogger(__name__)

class NoMoreTicks(Exception):
    """Raised when the feed runs out of rows."""


def _validate_year(value: int, label: str) -> int:
    if not isinstance(value, int):
        raise DataFeedError(f"{label} must be an integer year")
    return value


def _validate_month(value: int, label: str) -> int:
    if not isinstance(value, int):
        raise DataFeedError(f"{label} must be an integer month")
    if value < 1 or value > 12:
        raise DataFeedError(f"{label} must be between 1 and 12")
    return value


def get_data_months(year_start: int, year_end: int, month_start: int, month_end: int):
    year_start = _validate_year(year_start, "year_start")
    year_end = _validate_year(year_end, "year_end")
    month_start = _validate_month(month_start, "month_start")
    month_end = _validate_month(month_end, "month_end")

    if (year_start, month_start) > (year_end, month_end):
        raise DataFeedError("start year/month must not be after end year/month")

    if year_start == year_end:
        return [[year_start, m] for m in range(month_start, month_end + 1)]

    first_year = [[year_start, m] for m in range(month_start, 13)]
    middle_years = [[y, m] for y in range(year_start + 1, year_end) for m in range(1, 13)]
    last_year = [[year_end, m] for m in range(1, month_end + 1)]
    return first_year + middle_years + last_year


class DataFeed:
    """Pure Python fallback matching the original behaviour."""

    def __init__(
        self,
        base_path: str,
        pair: str,
        year_start: int,
        year_end: int,
        month_start: int,
        month_end: int,
        batch_size: int = 10_000,
    ) -> None:
        self.base_path = Path(base_path)
        self.pair = pair
        self.year_start = year_start
        self.year_end = year_end
        self.month_start = month_start
        self.month_end = month_end
        self.batch_size = max(1, batch_size)

        self._file_paths = self._build_file_sequence()
        self._file_index = -1
        self._batch_iterator: Optional[Iterator] = None
        self._current_batch = None
        self._batch_row_index = 0

        self._bids: Optional[np.ndarray] = None
        self._asks: Optional[np.ndarray] = None
        self._mids: Optional[np.ndarray] = None
        self._timestamps: Optional[np.ndarray] = None
        self._timestamps_ns: Optional[np.ndarray] = None
        self.logger = logging.getLogger(__name__)

    def _build_file_sequence(self):
        month_pairs = get_data_months(self.year_start, self.year_end, self.month_start, self.month_end)
        file_paths = []
        for year, month in month_pairs:
            path = self.base_path / self.pair / f"{self.pair}_{year}-{month:02d}.parquet"
            if not path.exists():
                raise DataFeedError(f"missing data file: {path}")
            file_paths.append(path)
        return file_paths

    def _prepare_next_file(self) -> bool:
        self._file_index += 1
        if self._file_index >= len(self._file_paths):
            return False

        current_file = self._file_paths[self._file_index]
        try:
            parquet_file = pq.ParquetFile(current_file)
        except Exception as exc:  # pragma: no cover - depends on local filesystem
            raise DataFeedError(f"failed to open data file {current_file}: {exc}") from exc
        self._batch_iterator = parquet_file.iter_batches(batch_size=self.batch_size)

        ym = current_file.stem.split("_")[-1]
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(
            "processing data file",
            extra={
                "pair": self.pair,
                "year_month": ym,
                "file_index": self._file_index + 1,
                "file_total": len(self._file_paths),
            },
        )
        return True

    def _load_next_batch(self) -> bool:
        while True:
            if self._batch_iterator is None:
                if not self._prepare_next_file():
                    return False

            try:
                batch = next(self._batch_iterator)
            except StopIteration:
                self._batch_iterator = None
                self._current_batch = None
                continue
            except Exception as exc:
                self.logger.error(
                    "read_batch_failed",
                    extra={"path": str(self._file_paths[self._file_index]), "error": repr(exc)}
                )
                raise DataFeedError(f"failed reading {self._file_paths[self._file_index]}") from exc
            
            self._current_batch = batch
            self._batch_row_index = 0

            self._bids = batch.column("bid").to_numpy(zero_copy_only=False)
            self._asks = batch.column("ask").to_numpy(zero_copy_only=False)
            self._mids = 0.5 * (self._bids + self._asks)

            ts_series = batch.column("timestamp").to_pandas()
            if ts_series.dt.tz is None:
                ts_series = ts_series.dt.tz_localize("UTC")
            else:
                ts_series = ts_series.dt.tz_convert("UTC")

            # Keep ns precision
            ts_int = ts_series.view("int64").to_numpy(copy=False)  # or .astype("int64")
            self._timestamps_ns = ts_int
            self._timestamps = self._timestamps_ns.astype(np.float64) / 1e9

            return True

    def _ensure_row_loaded(self) -> bool:
        if self._current_batch is None or self._batch_row_index >= len(self._bids):
            return self._load_next_batch()
        return True

    def tick(self) -> Tick:
        if not self._ensure_row_loaded():
            raise NoMoreTicks("No more ticks available")

        i = self._batch_row_index
        ts_ns = int(self._timestamps_ns[i]) if self._timestamps_ns is not None else int(self._timestamps[i] * 1e9)
        ts = float(self._timestamps[i])
        bid = float(self._bids[i])
        ask = float(self._asks[i])
        mid = float(self._mids[i])

        self._batch_row_index += 1
        return Tick(ts, bid, ask, mid, timestamp_ns=ts_ns)
