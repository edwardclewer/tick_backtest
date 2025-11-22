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

"""Tests for the configurable signal generator facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import pytest

from tick_backtest.config_parsers.strategy.config_dataclass import (
    EntryConfig,
    ExitConfig,
    PredicateConfig,
    StrategyConfigData,
)
from tick_backtest.config_parsers.strategy.entry_configs import StubEntryParams
from tick_backtest.signals.entries import ENTRY_ENGINE_REGISTRY
from tick_backtest.signals.entries.base import EntryResult
from tick_backtest.signals.signal_generator import SignalGenerator


def _metrics(**overrides) -> Dict[str, float]:
    base = {
        "tick_rate_30s.tick_rate_per_min": 120.0,
        "ewma_mid_5m.ewma": 1.2,
        "ewma_mid_30m.ewma": 1.1,
    }
    base.update(overrides)
    return base


@dataclass
class StubTick:
    mid: float = 1.2000
    timestamp: float = 0.0


class _DeterministicEntryEngine:
    """Test helper that yields a predetermined EntryResult."""

    def __init__(self, entry_config: EntryConfig, pip_size: float) -> None:
        self.entry_config = entry_config
        self.pip_size = pip_size
        self.tp_multiple = 1.0
        self.sl_multiple = 1.0
        self._next_result: EntryResult = EntryResult(reason=entry_config.name)

    def update(self, tick, metrics):
        return self._next_result


@pytest.fixture()
def stub_engine(monkeypatch):
    """Inject the deterministic entry engine into the registry for tests."""

    monkeypatch.setitem(ENTRY_ENGINE_REGISTRY, "deterministic", _DeterministicEntryEngine)
    yield
    ENTRY_ENGINE_REGISTRY.pop("deterministic", None)


def _strategy(entry_result: Optional[EntryResult] = None, predicates=None, exit_predicates=None):
    entry = EntryConfig(
        name="stub_entry",
        engine="deterministic",
        params=StubEntryParams(),
        predicates=predicates or [],
    )
    exit_cfg = ExitConfig(name="stub_exit", predicates=exit_predicates or [])
    strategy = StrategyConfigData(schema_version="1.0", name="unit_test_strategy", entry=entry, exit=exit_cfg)
    return strategy


def test_signal_generator_emits_entry_when_engine_triggers(monkeypatch, stub_engine):
    strategy = _strategy()
    generator = SignalGenerator(strategy_config=strategy, pip_size=0.0001)

    engine: _DeterministicEntryEngine = generator.entry_engine  # type: ignore[assignment]
    engine._next_result = EntryResult(
        should_open=True,
        direction=1,
        tp=1.2010,
        sl=1.1990,
        timeout_seconds=300.0,
        reason="entry_triggered",
        metadata={"threshold": 0.0010},
    )

    signal = generator.update(_metrics(), StubTick(mid=1.2000))

    assert signal.should_open is True
    assert signal.direction == 1
    assert signal.tp == pytest.approx(1.2010)
    assert signal.timeout_seconds == pytest.approx(300.0)
    assert signal.reason == "entry_triggered"
    assert signal.entry_metadata == {"threshold": 0.0010}


def test_signal_generator_blocks_on_predicate(stub_engine):
    predicate = PredicateConfig(metric="tick_rate_30s.tick_rate_per_min", operator="<", value=100.0)
    strategy = _strategy(predicates=[predicate])
    generator = SignalGenerator(strategy_config=strategy, pip_size=0.0001)

    engine: _DeterministicEntryEngine = generator.entry_engine  # type: ignore[assignment]
    engine._next_result = EntryResult(should_open=True, direction=1, reason="entry_triggered")

    signal = generator.update(_metrics(), StubTick(mid=1.2000))

    assert signal.should_open is False
    assert signal.reason == "entry_predicate_blocked"


def test_signal_generator_emits_exit_signal(stub_engine):
    exit_predicate = PredicateConfig(metric="ewma_mid_5m.ewma", operator=">", value=1.0)
    strategy = _strategy(exit_predicates=[exit_predicate])
    generator = SignalGenerator(strategy_config=strategy, pip_size=0.0001)

    signal = generator.update(_metrics(), StubTick(mid=1.2000))

    assert signal.should_close is True
    assert signal.close_reason == "stub_exit"


def test_signal_generator_propagates_last_reason(stub_engine):
    strategy = _strategy()
    generator = SignalGenerator(strategy_config=strategy, pip_size=0.0001)

    engine: _DeterministicEntryEngine = generator.entry_engine  # type: ignore[assignment]
    engine._next_result = EntryResult(should_open=False, reason="no_setup")

    signal = generator.update(_metrics(), StubTick(mid=1.2000))

    assert signal.should_open is False
    assert signal.reason == "no_setup"
