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

# cython: language_level=3, boundscheck=False, wraparound=False

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

cdef object _LOGGER = None


cdef inline object _get_logger():
    global _LOGGER
    if _LOGGER is None:
        import logging
        _LOGGER = logging.getLogger(__name__)
    return _LOGGER


cdef class NoMoreTicks(Exception):
    pass


cdef class TickRecord:
    cdef public double timestamp
    cdef public double bid
    cdef public double ask
    cdef public double mid
    cdef public int hour
    cdef public int minute

    def __cinit__(self):
        self.timestamp = 0.0
        self.bid = 0.0
        self.ask = 0.0
        self.mid = 0.0
        self.hour = 0
        self.minute = 0

    def __init__(self, double timestamp, double bid, double ask, double mid):
        self.timestamp = timestamp
        self.bid = bid
        self.ask = ask
        self.mid = mid
        self._update_time()

    cdef void _update_time(self):
        cdef long long seconds = <long long> self.timestamp
        cdef long long days = seconds // 86400
        cdef long long seconds_in_day = seconds - days * 86400
        if seconds_in_day < 0:
            seconds_in_day += 86400
        self.hour = <int>(seconds_in_day // 3600)
        self.minute = <int>((seconds_in_day % 3600) // 60)

    cdef void set(self, double timestamp, double bid, double ask, double mid):
        self.timestamp = timestamp
        self.bid = bid
        self.ask = ask
        self.mid = mid
        self._update_time()


cdef class DataFeed:
    cdef object base_path
    cdef object pair
    cdef int year_start
    cdef int year_end
    cdef int month_start
    cdef int month_end
    cdef list _file_paths
    cdef list _month_labels
    cdef Py_ssize_t _file_index
    cdef Py_ssize_t _row_index
    cdef Py_ssize_t _row_count
    cdef object _ts_array
    cdef object _bids_array
    cdef object _asks_array
    cdef object _mids_array
    cdef double[::1] _ts_view
    cdef double[::1] _bids_view
    cdef double[::1] _asks_view
    cdef double[::1] _mids_view

    def __cinit__(
        self,
        base_path,
        pair,
        int year_start,
        int year_end,
        int month_start,
        int month_end,
        int batch_size=10000,
    ):
        self.base_path = Path(base_path)
        self.pair = pair
        self.year_start = year_start
        self.year_end = year_end
        self.month_start = month_start
        self.month_end = month_end
        self._file_paths = self._build_file_sequence()
        self._file_index = -1
        self._row_index = 0
        self._row_count = 0
        self._ts_array = None
        self._bids_array = None
        self._asks_array = None
        self._mids_array = None

    cdef list _build_file_sequence(self):
        cdef list file_paths = []
        cdef list month_labels = []
        cdef int year
        cdef int month
        cdef list months = self._get_month_pairs()
        cdef object path
        for year, month in months:
            path = self.base_path / self.pair / f"{self.pair}_{year:04d}-{month:02d}.parquet"
            if not path.exists():
                raise FileNotFoundError(f"Missing data file: {path}")
            file_paths.append(path)
            month_labels.append(f"{year:04d}-{month:02d}")
        self._month_labels = month_labels
        return file_paths

    cdef list _get_month_pairs(self):
        cdef list result = []
        cdef int year
        cdef int month

        if self.year_start == self.year_end:
            if self.month_start > self.month_end:
                raise ValueError("month_start must be <= month_end when year_start == year_end")
            for month in range(self.month_start, self.month_end + 1):
                result.append([self.year_start, month])
            return result

        for month in range(self.month_start, 13):
            result.append([self.year_start, month])

        for year in range(self.year_start + 1, self.year_end):
            for month in range(1, 13):
                result.append([year, month])

        for month in range(1, self.month_end + 1):
            result.append([self.year_end, month])

        return result

    cdef bint _load_next_file(self):
        self._file_index += 1
        if self._file_index >= len(self._file_paths):
            return False

        path = self._file_paths[self._file_index]
        table = pq.read_table(path, columns=["timestamp", "bid", "ask"])

        bids = np.array(
            table.column("bid").to_numpy(zero_copy_only=False),
            dtype=np.float64,
            copy=True,
        )
        asks = np.array(
            table.column("ask").to_numpy(zero_copy_only=False),
            dtype=np.float64,
            copy=True,
        )

        mids = (bids + asks) * 0.5

        ts_series = table.column("timestamp").to_pandas()
        if ts_series.dt.tz is None:
            ts_series = ts_series.dt.tz_localize("UTC")
        else:
            ts_series = ts_series.dt.tz_convert("UTC")

        ts_int = ts_series.astype("int64").to_numpy(copy=True)
        timestamps = ts_int.astype(np.float64, copy=True)
        timestamps /= 1e9

        self._ts_array = timestamps
        self._bids_array = bids
        self._asks_array = asks
        self._mids_array = mids

        self._ts_view = timestamps
        self._bids_view = bids
        self._asks_view = asks
        self._mids_view = mids
        self._row_count = bids.shape[0]
        self._row_index = 0

        ym = self._month_labels[self._file_index]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        _get_logger().info(
            "processing data file",
            extra={
                "pair": self.pair,
                "year_month": ym,
                "file_index": self._file_index + 1,
                "file_total": len(self._file_paths),
                "timestamp_utc": now,
            },
        )
        return True

    cdef bint _ensure_row(self):
        if self._ts_array is None or self._row_index >= self._row_count:
            return self._load_next_file()
        return True

    def tick(self):
        if not self._ensure_row():
            raise NoMoreTicks("No more ticks available")

        cdef Py_ssize_t i = self._row_index
        cdef double ts = self._ts_view[i]
        cdef double bid = self._bids_view[i]
        cdef double ask = self._asks_view[i]
        cdef double mid = self._mids_view[i]
        self._row_index += 1

        return TickRecord(ts, bid, ask, mid)
