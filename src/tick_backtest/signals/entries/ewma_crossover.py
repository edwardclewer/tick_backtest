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

import math

from tick_backtest.config_parsers.strategy.config_dataclass import EntryConfig
from tick_backtest.config_parsers.strategy.entry_configs import EWMACrossoverEntryParams
from tick_backtest.data_feed.tick import Tick
from tick_backtest.signals.entries.base import BaseEntryEngine, EntryResult


def _to_float(value: object, default: float = math.nan) -> float:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float, str)):
        return float(value)
    return default


class EWMACrossoverEntryEngine(BaseEntryEngine):
    """Entry engine based on fast/slow EWMA crossover events."""

    def __init__(self, entry_config: EntryConfig, pip_size: float) -> None:
        super().__init__(entry_config, pip_size)
        if not isinstance(entry_config.params, EWMACrossoverEntryParams):
            raise TypeError("EWMACrossoverEntryEngine expects EWMACrossoverEntryParams")
        self.params = entry_config.params
        self._last_diff: float | None = None

    def update(self, tick: Tick, metrics: dict[str, float]) -> EntryResult:
        fast = _to_float(metrics.get(self.params.fast_metric))
        slow = _to_float(metrics.get(self.params.slow_metric))

        if not (math.isfinite(fast) and math.isfinite(slow)):
            self._last_diff = None
            return EntryResult(reason=self.entry_config.name)

        diff = fast - slow

        if self._last_diff is None:
            self._last_diff = diff
            return EntryResult(reason=self.entry_config.name)

        should_open = False
        direction = 0
        if self.params.long_on_cross and diff >= 0 and self._last_diff < 0:
            should_open = True
            direction = 1
        elif self.params.short_on_cross and diff <= 0 and self._last_diff > 0:
            should_open = True
            direction = -1

        self._last_diff = diff
        if not should_open:
            return EntryResult(reason=self.entry_config.name)

        price = float(tick.mid)
        tp = sl = None
        if self.params.tp_pips > 0:
            offset = self.params.tp_pips * self.pip_size
            tp = price + offset if direction == 1 else price - offset
        if self.params.sl_pips > 0:
            offset = self.params.sl_pips * self.pip_size
            sl = price - offset if direction == 1 else price + offset

        timeout = (
            float(self.params.trade_timeout_seconds)
            if self.params.trade_timeout_seconds and self.params.trade_timeout_seconds > 0
            else None
        )
        return EntryResult(
            should_open=True,
            direction=direction,
            tp=tp,
            sl=sl,
            timeout_seconds=timeout,
            reason=self.entry_config.name,
            metadata={"fast": fast, "slow": slow, "diff": diff, "direction": direction, "signal_price": price},
        )
