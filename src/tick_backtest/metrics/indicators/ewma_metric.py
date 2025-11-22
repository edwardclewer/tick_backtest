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
import math
from typing import Callable

from tick_backtest.data_feed.tick import Tick

MIN_DT = 1e-6


def _load_impl():
    module = import_module("tick_backtest.metrics.indicators._ewma_metric")
    return getattr(module, "EWMAMetric")


try:  # pragma: no cover - exercised when Cython extension is available
    EWMAMetric = _load_impl()
except (ImportError, AttributeError):  # pragma: no cover - fallback during development

    class EWMAMetric:
        """Python implementation of a basic EWMA over the selected price field."""

        def __init__(
            self,
            *,
            name: str,
            tau_seconds: float,
            initial_value: float | None = None,
            price_field: str = "mid",
        ) -> None:
            if tau_seconds <= 0:
                raise ValueError(f"tau_seconds must be positive, got {tau_seconds}")

            self.name = name
            self.tau = float(tau_seconds)
            self._value = float(initial_value) if initial_value is not None else math.nan
            self._last_ts = math.nan
            self._price_getter: Callable[[Tick], float] = self._resolve_price_field(price_field)

        def update(self, tick: Tick) -> None:
            price = float(self._price_getter(tick))
            t = float(getattr(tick, "timestamp", 0.0))

            if math.isnan(self._value):
                self._value = price
                self._last_ts = t
                return

            dt = max(MIN_DT, t - self._last_ts if not math.isnan(self._last_ts) else MIN_DT)
            alpha = 1.0 - math.exp(-dt / self.tau)
            self._value = (1.0 - alpha) * self._value + alpha * price
            self._last_ts = t

        def value(self) -> dict[str, float]:
            return {"ewma": self._value}

        @property
        def current(self) -> float:
            return self._value

        def _resolve_price_field(self, field: str) -> Callable[[Tick], float]:
            if field not in ("mid", "bid", "ask"):
                raise ValueError(f"Unsupported price_field '{field}'. Expected one of ['mid', 'bid', 'ask'].")

            def _getter(tick: Tick) -> float:
                return float(getattr(tick, field))

            return _getter
