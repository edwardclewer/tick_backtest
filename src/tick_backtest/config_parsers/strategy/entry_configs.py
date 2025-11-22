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

from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(kw_only=True)
class EntryParamsBase:
    """Base class for entry engine parameter bundles."""

    def to_kwargs(self) -> dict:
        return asdict(self)


@dataclass(kw_only=True)
class StubEntryParams(EntryParamsBase):
    """Placeholder parameters for stub/deterministic engines."""


@dataclass(kw_only=True)
class ThresholdReversionEntryParams(EntryParamsBase):
    lookback_seconds: int
    threshold_pips: float
    tp_pips: Optional[float] = None
    sl_pips: Optional[float] = None
    min_recency_seconds: float = 0.0
    trade_timeout_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        self.lookback_seconds = self._coerce_positive_int(self.lookback_seconds, "lookback_seconds")
        self.threshold_pips = self._coerce_positive_float(self.threshold_pips, "threshold_pips")

        if self.tp_pips is None:
            self.tp_pips = self.threshold_pips
        else:
            self.tp_pips = self._coerce_positive_float(self.tp_pips, "tp_pips")

        if self.sl_pips is None:
            self.sl_pips = self.threshold_pips
        else:
            self.sl_pips = self._coerce_positive_float(self.sl_pips, "sl_pips")

        self.min_recency_seconds = self._coerce_nonnegative_float(
            self.min_recency_seconds, "min_recency_seconds"
        )

        if self.trade_timeout_seconds is not None:
            self.trade_timeout_seconds = self._coerce_positive_float(
                self.trade_timeout_seconds, "trade_timeout_seconds"
            )

    @staticmethod
    def _coerce_positive_int(value, name: str) -> int:
        if isinstance(value, bool):
            raise TypeError(f"'{name}' must be an integer")
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError(f"'{name}' must be an integer number of seconds, got {value}")
            value = int(value)
        if not isinstance(value, int):
            raise TypeError(f"'{name}' must be an integer")
        if value <= 0:
            raise ValueError(f"'{name}' must be positive, got {value}")
        return value

    @staticmethod
    def _coerce_positive_float(value, name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"'{name}' must be numeric")
        try:
            numeric = float(value)
        except Exception as exc:
            raise TypeError(f"'{name}' must be numeric") from exc
        if numeric <= 0 or not numeric == numeric:
            raise ValueError(f"'{name}' must be positive and finite, got {value}")
        return numeric

    @staticmethod
    def _coerce_nonnegative_float(value, name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"'{name}' must be numeric")
        try:
            numeric = float(value)
        except Exception as exc:
            raise TypeError(f"'{name}' must be numeric") from exc
        if numeric < 0 or not numeric == numeric:
            raise ValueError(f"'{name}' must be non-negative and finite, got {value}")
        return numeric


@dataclass(kw_only=True)
class EWMACrossoverEntryParams(EntryParamsBase):
    fast_metric: str
    slow_metric: str
    long_on_cross: bool = True
    short_on_cross: bool = False
    tp_pips: float = 0.0
    sl_pips: float = 0.0
    trade_timeout_seconds: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.fast_metric, str) or not self.fast_metric:
            raise ValueError("'fast_metric' must be a non-empty string")
        if not isinstance(self.slow_metric, str) or not self.slow_metric:
            raise ValueError("'slow_metric' must be a non-empty string")
        if not isinstance(self.long_on_cross, bool):
            raise TypeError("'long_on_cross' must be a boolean")
        if not isinstance(self.short_on_cross, bool):
            raise TypeError("'short_on_cross' must be a boolean")

        self.tp_pips = self._coerce_nonnegative_float(self.tp_pips, "tp_pips")
        self.sl_pips = self._coerce_nonnegative_float(self.sl_pips, "sl_pips")

        if self.trade_timeout_seconds is not None:
            self.trade_timeout_seconds = self._coerce_positive_float(
                self.trade_timeout_seconds, "trade_timeout_seconds"
            )

    @staticmethod
    def _coerce_nonnegative_float(value, name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"'{name}' must be numeric")
        try:
            numeric = float(value)
        except Exception as exc:
            raise TypeError(f"'{name}' must be numeric") from exc
        if numeric < 0 or not numeric == numeric:
            raise ValueError(f"'{name}' must be non-negative and finite, got {value}")
        return numeric

    @staticmethod
    def _coerce_positive_float(value, name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"'{name}' must be numeric")
        try:
            numeric = float(value)
        except Exception as exc:
            raise TypeError(f"'{name}' must be numeric") from exc
        if numeric <= 0 or not numeric == numeric:
            raise ValueError(f"'{name}' must be positive and finite, got {value}")
        return numeric


__all__ = [
    "EntryParamsBase",
    "StubEntryParams",
    "ThresholdReversionEntryParams",
    "EWMACrossoverEntryParams",
]

