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
from typing import Deque

from tick_backtest.data_feed.tick import Tick


def _load_impl():
    module = import_module("tick_backtest.metrics.indicators._tick_rate_metric")
    return getattr(module, "TickRateMetric")


try:  # pragma: no cover - exercised when Cython extension is available
    TickRateMetric = _load_impl()
except (ImportError, AttributeError):  # pragma: no cover - fallback during development

    class TickRateMetric:
        """Count ticks over a rolling window and emit rates per second/minute."""

        def __init__(self, *, name: str, window_seconds: float) -> None:
            if window_seconds <= 0:
                raise ValueError(f"window_seconds must be positive, got {window_seconds}")

            self.name = name
            self.window = float(window_seconds)
            self._timestamps: Deque[float] = deque()
            self._count = 0

        def update(self, tick: Tick) -> None:
            timestamp = float(getattr(tick, "timestamp", 0.0))
            self._timestamps.append(timestamp)
            cutoff = timestamp - self.window

            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            self._count = len(self._timestamps)

        def value(self) -> dict[str, float]:
            rate_per_sec = self._count / self.window if self.window > 0 else math.nan
            rate_per_min = rate_per_sec * 60.0 if self.window > 0 else math.nan
            return {
                "tick_count": float(self._count),
                "tick_rate_per_sec": rate_per_sec,
                "tick_rate_per_min": rate_per_min,
            }
