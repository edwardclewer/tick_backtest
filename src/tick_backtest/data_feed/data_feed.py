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

from importlib import import_module
from typing import List

from tick_backtest.exceptions import DataFeedError

__all__ = ["DataFeed", "NoMoreTicks", "Tick", "get_data_months", "DataFeedError"]


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


def get_data_months(year_start: int, year_end: int, month_start: int, month_end: int) -> List[List[int]]:
    """Return [[year, month], ...] pairs from a start to end date (inclusive)."""
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


try:
    _compiled = import_module("tick_backtest.data_feed._data_feed")
    DataFeed = getattr(_compiled, "DataFeed")
    NoMoreTicks = getattr(_compiled, "NoMoreTicks")
    Tick = getattr(_compiled, "TickRecord")
    DataFeedError = getattr(_compiled, "DataFeedError", DataFeedError)
except ImportError:  # pragma: no cover - fallback when extension unavailable
    from ._data_feed_py import DataFeed, NoMoreTicks  # type: ignore
    from .tick import Tick  # noqa: F401
