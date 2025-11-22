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


def _load_impl():
    module = import_module("tick_backtest.metrics.indicators._spread_metric")
    return getattr(module, "SpreadMetric")


try:  # pragma: no cover - exercised when Cython extension is available
    SpreadMetric = _load_impl()
except (ImportError, AttributeError):  # pragma: no cover - fallback during development

    class SpreadMetric:
        """Track raw spread, spread in pips, and percentile over a rolling window."""

        def __init__(
            self,
            *,
            name: str,
            pip_size: float,
            window_seconds: float,
        ) -> None:
            if pip_size <= 0:
                raise ValueError(f"pip_size must be positive, got {pip_size}")
            if window_seconds <= 0:
                raise ValueError(f"window_seconds must be positive, got {window_seconds}")

            self.name = name
            self.pip_size = float(pip_size)
            self.window = float(window_seconds)

            self._spread = math.nan
            self._spread_pips = math.nan
            self._percentile = math.nan
            self._history: Deque[Tuple[float, float]] = deque()

        def update(self, tick: Tick) -> None:
            bid = float(getattr(tick, "bid", math.nan))
            ask = float(getattr(tick, "ask", math.nan))
            timestamp = float(getattr(tick, "timestamp", 0.0))

            raw = max(0.0, ask - bid)
            spread_pips = raw / self.pip_size if self.pip_size else math.nan

            self._spread = raw
            self._spread_pips = spread_pips

            self._history.append((timestamp, spread_pips))
            cutoff = timestamp - self.window
            while self._history and self._history[0][0] < cutoff:
                self._history.popleft()

            if not self._history:
                self._percentile = math.nan
                return

            count = sum(1 for _, value in self._history if value <= spread_pips)
            self._percentile = count / len(self._history)

        def value(self) -> dict[str, float]:
            return {
                "spread": self._spread,
                "spread_pips": self._spread_pips,
                "spread_percentile": self._percentile,
            }
