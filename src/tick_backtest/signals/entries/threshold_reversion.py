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
from tick_backtest.config_parsers.strategy.entry_configs import ThresholdReversionEntryParams
from tick_backtest.data_feed.tick import Tick
from tick_backtest.metrics.indicators.threshold_reversion_metric import ThresholdReversionMetric
from tick_backtest.signals.entries.base import BaseEntryEngine, EntryResult


def _to_float(value, default=math.nan) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except Exception:
        return default


class ThresholdReversionEntryEngine(BaseEntryEngine):
    """Threshold reversion entry logic maintained within the strategy layer."""

    def __init__(self, entry_config: EntryConfig, pip_size: float) -> None:
        super().__init__(entry_config, pip_size)
        if not isinstance(entry_config.params, ThresholdReversionEntryParams):
            raise TypeError("ThresholdReversionEntryEngine expects ThresholdReversionEntryParams")
        self.params = entry_config.params

        self.metric = ThresholdReversionMetric(
            name=entry_config.name,
            lookback_seconds=self.params.lookback_seconds,
            threshold_pips=self.params.threshold_pips,
            pip_size=self.pip_size,
            tp_pips=self.params.tp_pips,
            sl_pips=self.params.sl_pips,
            min_recency_seconds=self.params.min_recency_seconds,
            trade_timeout_seconds=self.params.trade_timeout_seconds,
        )

        self.tp_multiple = self.params.tp_pips / self.params.threshold_pips
        self.sl_multiple = self.params.sl_pips / self.params.threshold_pips
        self._last_position = 0

    def update(self, tick: Tick, metrics: Dict[str, float]) -> EntryResult:
        self.metric.update(tick)
        snapshot = self.metric.value_dict()
        metadata = {
            "reference_price": _to_float(snapshot.get("reference_price")),
            "threshold": _to_float(snapshot.get("threshold")),
            "threshold_pips": self.params.threshold_pips,
            "tp_price": _to_float(snapshot.get("tp_price")),
            "sl_price": _to_float(snapshot.get("sl_price")),
            "reference_age_seconds": _to_float(snapshot.get("reference_age_seconds")),
            "position_open_age_seconds": _to_float(snapshot.get("position_open_age_seconds")),
            "trade_timeout_seconds": _to_float(snapshot.get("trade_timeout_seconds")),
        }

        position = int(_to_float(snapshot.get("position"), 0.0))
        if position == 0:
            self._last_position = 0
            return EntryResult(reason=self.entry_config.name, metadata=metadata)

        if self._last_position == position:
            return EntryResult(reason=self.entry_config.name, metadata=metadata)

        self._last_position = position

        price = float(tick.mid)
        tp = _to_float(snapshot.get("tp_price"))
        sl = _to_float(snapshot.get("sl_price"))
        if not math.isfinite(tp) or not math.isfinite(sl):
            tp_offset = self.params.tp_pips * self.pip_size
            sl_offset = self.params.sl_pips * self.pip_size
            if position == 1:
                tp = price + tp_offset
                sl = price - sl_offset
            else:
                tp = price - tp_offset
                sl = price + sl_offset

        timeout = self.params.trade_timeout_seconds
        timeout_seconds = float(timeout) if timeout is not None and timeout > 0 else None

        metadata.update(
            {
                "direction": position,
                "signal_price": price,
            }
        )
        metadata["trade_timeout_seconds"] = timeout_seconds

        return EntryResult(
            should_open=True,
            direction=position,
            tp=tp,
            sl=sl,
            timeout_seconds=timeout_seconds,
            reason=self.entry_config.name,
            metadata=metadata,
        )
