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

"""Utilities for generating synthetic parquet datasets for tests (skeleton)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

REQUIRED_COLUMNS = ("timestamp", "bid", "ask")


def _normalise_rows(rows: Iterable[dict]) -> Sequence[dict]:
    normalised: list[dict] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError(f"Row {idx} must be a dict, got {type(row).__name__}")
        payload = {key: row.get(key) for key in REQUIRED_COLUMNS}
        missing = [k for k, v in payload.items() if v is None]
        if missing:
            raise ValueError(f"Row {idx} missing required keys: {missing}")
        normalised.append(payload)
    if not normalised:
        raise ValueError("Cannot write empty parquet dataset")
    return normalised


def write_tick_parquet(path: Path, rows: Iterable[dict]) -> None:
    """Persist iterable tick dictionaries to parquet for use in tests."""
    payload = _normalise_rows(rows)
    df = pd.DataFrame(payload)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["bid"] = pd.to_numeric(df["bid"], downcast="float")
    df["ask"] = pd.to_numeric(df["ask"], downcast="float")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)
