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
from typing import Dict

from tick_backtest.config_parsers.strategy.config_dataclass import EntryConfig
from tick_backtest.config_parsers.strategy.entry_configs import EWMACrossoverEntryParams
from tick_backtest.data_feed.tick import Tick
from tick_backtest.signals.entries.base import BaseEntryEngine, EntryResult


def _to_float(value, default=math.nan):
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except Exception:
        return default


class EWMACrossoverEntryEngine(BaseEntryEngine):
    """Entry engine based on fast/slow EWMA crossover events."""

    def __init__(self, entry_config: EntryConfig, pip_size: float) -> None:
        super().__init__(entry_config, pip_size)
        if not isinstance(entry_config.params, EWMACrossoverEntryParams):
            raise TypeError("EWMACrossoverEntryEngine expects EWMACrossoverEntryParams")
        self.params = entry_config.params
        self._last_diff: float | None = None

    def update(self, tick: Tick, metrics: Dict[str, float]) -> EntryResult:
        fast = _to_float(metrics.get(self.params.fast_metric))
        slow = _to_float(metrics.get(self.params.slow_metric))
        metadata = {"fast": fast, "slow": slow}

        if not (math.isfinite(fast) and math.isfinite(slow)):
            self._last_diff = None
            return EntryResult(reason=self.entry_config.name, metadata=metadata)

        diff = fast - slow
        metadata["diff"] = diff

        if self._last_diff is None:
            self._last_diff = diff
            return EntryResult(reason=self.entry_config.name, metadata=metadata)

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
            return EntryResult(reason=self.entry_config.name, metadata=metadata)

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
        metadata.update({"direction": direction, "signal_price": price})

        return EntryResult(
            should_open=True,
            direction=direction,
            tp=tp,
            sl=sl,
            timeout_seconds=timeout,
            reason=self.entry_config.name,
            metadata=metadata,
        )
