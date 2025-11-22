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
from collections import deque
import math
from typing import Deque, Tuple

from tick_backtest.data_feed.tick import Tick
from tick_backtest.metrics.indicators.ewma_metric import EWMAMetric

MIN_DT = 1e-6


def _load_impl():
    module = import_module("tick_backtest.metrics.indicators._ewma_slope_metric")
    return getattr(module, "EWMASlopeMetric")


try:  # pragma: no cover - exercised when Cython extension is available
    EWMASlopeMetric = _load_impl()
except (ImportError, AttributeError):  # pragma: no cover - fallback during development

    class EWMASlopeMetric:
        """EWMA slope metric backed by the Python EWMA implementation."""

        def __init__(
            self,
            *,
            name: str,
            tau_seconds: float,
            window_seconds: float,
            initial_value: float | None = None,
            price_field: str = "mid",
        ) -> None:
            if window_seconds <= 0:
                raise ValueError(f"window_seconds must be positive, got {window_seconds}")

            self.name = name
            self.window = float(window_seconds)
            self._ewma = EWMAMetric(
                name=f"{name}_inner",
                tau_seconds=tau_seconds,
                initial_value=initial_value,
                price_field=price_field,
            )
            self._history: Deque[Tuple[float, float]] = deque()
            self._slope = math.nan

        def update(self, tick: Tick) -> None:
            timestamp = float(getattr(tick, "timestamp", 0.0))
            self._ewma.update(tick)
            current_value = self._ewma.current

            self._history.append((timestamp, current_value))
            cutoff = timestamp - self.window
            while len(self._history) > 1 and self._history[0][0] < cutoff:
                self._history.popleft()

            if len(self._history) < 2:
                self._slope = math.nan
                return

            oldest_t, oldest_v = self._history[0]
            dt = max(MIN_DT, timestamp - oldest_t)
            self._slope = (current_value - oldest_v) / dt

        def value(self) -> dict[str, float]:
            return {"ewma": self._ewma.current, "slope": self._slope}
