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
from collections.abc import Callable
from dataclasses import dataclass

from tick_backtest.config_parsers.strategy.config_dataclass import (
    EntryConfig,
    ExitConfig,
    PredicateConfig,
    StrategyConfigData,
)
from tick_backtest.config_parsers.strategy.entry_configs import ThresholdReversionEntryParams
from tick_backtest.data_feed.tick import Tick
from tick_backtest.signals.entries import ENTRY_ENGINE_REGISTRY, EntryResult
from tick_backtest.signals.entries.base import EntryEngine
from tick_backtest.signals.signal_data import SignalData


def _to_float(value: object, default: float = math.nan) -> float:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float, str)):
        return float(value)
    return default


@dataclass(frozen=True)
class _CompiledPredicate:
    metric: str
    operator: Callable[[float, float], bool]
    value: float | None
    other_metric: str | None
    use_abs: bool

    def evaluate(self, metrics: dict[str, float]) -> bool:
        left = _to_float(metrics.get(self.metric))
        if not math.isfinite(left):
            return False
        if self.use_abs:
            left = abs(left)
        if self.value is not None:
            right = self.value
        elif self.other_metric is not None:
            right = _to_float(metrics.get(self.other_metric))
            if not math.isfinite(right):
                return False
        else:
            return False
        return bool(self.operator(left, right))


_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class SignalGenerator:
    """Orchestrates entry and exit engines defined by the strategy configuration."""

    def __init__(
        self,
        *,
        strategy_config: StrategyConfigData | None = None,
        pip_size: float = 0.0001,
    ) -> None:
        if strategy_config is None:
            strategy_config = self._default_strategy()

        self.strategy_config = strategy_config
        self.pip_size = float(pip_size)

        self.entry_engine = self._build_entry_engine(strategy_config.entry)
        self.exit_config = strategy_config.exit
        self.entry_predicates = _compile_predicates(strategy_config.entry.predicates)
        self.exit_predicates = _compile_predicates(strategy_config.exit.predicates)
        self.tp_multiple = getattr(self.entry_engine, "tp_multiple", 1.0)
        self.sl_multiple = getattr(self.entry_engine, "sl_multiple", 1.0)
        self.last_signal = SignalData()

    def _build_entry_engine(self, entry_config: EntryConfig) -> EntryEngine:
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

    def update(
        self,
        metrics: dict[str, float],
        tick: Tick,
        *,
        is_warmup: bool = False,
    ) -> SignalData:
        """Compute the latest trading intent from metrics and tick."""
        signal = SignalData(reason=self.strategy_config.entry.name)

        entry_predicates_ok = _evaluate_all(self.entry_predicates, metrics)
        exit_predicates_ok = _evaluate_all(self.exit_predicates, metrics)

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


def _compile_predicates(predicates: list[PredicateConfig]) -> tuple[_CompiledPredicate, ...]:
    compiled = []
    for predicate in predicates:
        compiled.append(
            _CompiledPredicate(
                metric=predicate.metric,
                operator=_OPERATORS[predicate.operator],
                value=predicate.value,
                other_metric=predicate.other_metric,
                use_abs=predicate.use_abs,
            )
        )
    return tuple(compiled)


def _evaluate_all(predicates: tuple[_CompiledPredicate, ...], metrics: dict[str, float]) -> bool:
    for predicate in predicates:
        if not predicate.evaluate(metrics):
            return False
    return True
