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

from typing import Dict, Optional

from tick_backtest.config_parsers.strategy.config_dataclass import EntryConfig, ExitConfig, StrategyConfigData
from tick_backtest.config_parsers.strategy.entry_configs import ThresholdReversionEntryParams
from tick_backtest.data_feed.tick import Tick
from tick_backtest.signals.entries import ENTRY_ENGINE_REGISTRY, EntryResult
from tick_backtest.signals.predicates import PredicateEvaluator
from tick_backtest.signals.signal_data import SignalData


class SignalGenerator:
    """Orchestrates entry and exit engines defined by the strategy configuration."""

    def __init__(
        self,
        *,
        strategy_config: Optional[StrategyConfigData] = None,
        pip_size: float = 0.0001,
    ) -> None:
        if strategy_config is None:
            strategy_config = self._default_strategy()

        self.strategy_config = strategy_config
        self.pip_size = float(pip_size)
        self.predicate_evaluator = PredicateEvaluator()

        self.entry_engine = self._build_entry_engine(strategy_config.entry)
        self.exit_config = strategy_config.exit
        self.tp_multiple = getattr(self.entry_engine, "tp_multiple", 1.0)
        self.sl_multiple = getattr(self.entry_engine, "sl_multiple", 1.0)
        self.last_signal = SignalData()

    def _build_entry_engine(self, entry_config: EntryConfig):
        engine_cls = ENTRY_ENGINE_REGISTRY.get(entry_config.engine)
        if engine_cls is None:
            raise ValueError(f"Unrecognised strategy entry engine '{entry_config.engine}'")
        return engine_cls(entry_config, self.pip_size)

    def _default_strategy(self) -> StrategyConfigData:
        entry = EntryConfig(
            name="threshold_reversion_entry",
            engine="threshold_reversion",
            params=ThresholdReversionEntryParams(
                lookback_seconds=1800,
                threshold_pips=10,
                tp_pips=10,
                sl_pips=20,
                min_recency_seconds=60,
                trade_timeout_seconds=7200,
            ),
            predicates=[],
        )
        exit_cfg = ExitConfig(name="default_exit", predicates=[])
        return StrategyConfigData(
            schema_version="1.0",
            name="default_strategy",
            entry=entry,
            exit=exit_cfg,
        )

    def update(self, metrics: Dict[str, float], tick: Tick, *, is_warmup: bool = False) -> SignalData:
        """Compute the latest trading intent from metrics and tick."""
        signal = SignalData(reason=self.strategy_config.entry.name)

        entry_predicates_ok = self.predicate_evaluator.evaluate_all(
            self.strategy_config.entry.predicates, metrics
        )
        exit_predicates_ok = self.predicate_evaluator.evaluate_all(
            self.exit_config.predicates, metrics
        )

        entry_result: EntryResult = self.entry_engine.update(tick, metrics)

        if entry_result.metadata:
            signal.entry_metadata = dict(entry_result.metadata)

        if entry_result.should_open and entry_predicates_ok and not is_warmup:
            signal.should_open = True
            signal.direction = entry_result.direction
            signal.tp = entry_result.tp
            signal.sl = entry_result.sl
            signal.timeout_seconds = entry_result.timeout_seconds
            signal.reason = entry_result.reason
        elif entry_result.should_open and not entry_predicates_ok:
            signal.reason = "entry_predicate_blocked"
        else:
            signal.reason = entry_result.reason

        if exit_predicates_ok and not is_warmup:
            signal.should_close = True
            signal.close_reason = self.exit_config.name

        self.last_signal = signal
        return signal
