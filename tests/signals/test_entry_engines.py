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

"""Unit tests for concrete entry engine implementations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pytest

from tick_backtest.config_parsers.strategy.config_dataclass import EntryConfig
from tick_backtest.config_parsers.strategy.entry_configs import (
    EWMACrossoverEntryParams,
    ThresholdReversionEntryParams,
)
from tick_backtest.signals.entries.base import EntryResult
from tick_backtest.signals.entries.ewma_crossover import EWMACrossoverEntryEngine
from tick_backtest.signals.entries.threshold_reversion import ThresholdReversionEntryEngine


@dataclass
class StubTick:
    mid: float = 1.2000
    timestamp: float = 0.0


class FakeThresholdMetric:
    """Test double that returns a deterministic series of snapshots."""

    def __init__(self, snapshots: List[Dict[str, float]]):
        self.snapshots = snapshots
        self.index = 0

    def update(self, _tick):
        return None

    def value_dict(self):
        if self.index >= len(self.snapshots):
            return self.snapshots[-1]
        snapshot = self.snapshots[self.index]
        self.index += 1
        return snapshot


def test_threshold_reversion_entry_engine_emits_once_per_position(monkeypatch):
    snapshots = [
        {
            "position": 0.0,
            "tp_price": float("nan"),
            "sl_price": float("nan"),
            "threshold": 0.0010,
            "reference_price": 1.1990,
            "reference_age_seconds": 120.0,
            "trade_timeout_seconds": 600.0,
        },
        {
            "position": 1.0,
            "tp_price": 1.2010,
            "sl_price": 1.1980,
            "threshold": 0.0010,
            "reference_price": 1.1990,
            "reference_age_seconds": 180.0,
            "trade_timeout_seconds": 600.0,
        },
        {
            "position": 1.0,
            "tp_price": 1.2010,
            "sl_price": 1.1980,
            "threshold": 0.0010,
            "reference_price": 1.1990,
            "reference_age_seconds": 200.0,
            "trade_timeout_seconds": 600.0,
        },
        {
            "position": 0.0,
            "tp_price": float("nan"),
            "sl_price": float("nan"),
            "threshold": 0.0010,
            "reference_price": 1.1990,
            "reference_age_seconds": 0.0,
            "trade_timeout_seconds": 600.0,
        },
        {
            "position": -1.0,
            "tp_price": 1.1980,
            "sl_price": 1.2010,
            "threshold": 0.0010,
            "reference_price": 1.2010,
            "reference_age_seconds": 200.0,
            "trade_timeout_seconds": 600.0,
        },
    ]

    fake_metric = FakeThresholdMetric(snapshots)
    monkeypatch.setattr(
        "tick_backtest.signals.entries.threshold_reversion.ThresholdReversionMetric",
        lambda *args, **kwargs: fake_metric,
    )

    entry_config = EntryConfig(
        name="thr_entry",
        engine="threshold_reversion",
        params=ThresholdReversionEntryParams(
            lookback_seconds=1800,
            threshold_pips=10,
            tp_pips=10,
            sl_pips=20,
            min_recency_seconds=60,
            trade_timeout_seconds=600,
        ),
        predicates=[],
    )
    engine = ThresholdReversionEntryEngine(entry_config, pip_size=0.0001)

    # First call should not open (position 0)
    result = engine.update(StubTick(), {})
    assert result.should_open is False

    # Second call emits long
    result = engine.update(StubTick(mid=1.2000), {})
    assert result.should_open is True
    assert result.direction == 1
    assert result.tp == pytest.approx(1.2010)
    assert result.sl == pytest.approx(1.1980)
    assert result.metadata["threshold_pips"] == 10

    # Third call retains same position -> suppressed
    result = engine.update(StubTick(mid=1.2002), {})
    assert result.should_open is False

    # Fourth call resets position to 0
    engine.update(StubTick(mid=1.1995), {})

    # Fifth call emits short
    result = engine.update(StubTick(mid=1.1990), {})
    assert result.should_open is True
    assert result.direction == -1
    assert result.tp == pytest.approx(1.1980)
    assert result.sl == pytest.approx(1.2010)


def test_ewma_crossover_entry_engine_generates_long_and_short():
    entry_config = EntryConfig(
        name="crossover",
        engine="ewma_crossover",
        params=EWMACrossoverEntryParams(
            fast_metric="fast",
            slow_metric="slow",
            tp_pips=5,
            sl_pips=5,
            long_on_cross=True,
            short_on_cross=True,
            trade_timeout_seconds=120,
        ),
        predicates=[],
    )
    engine = EWMACrossoverEntryEngine(entry_config, pip_size=0.0001)
    tick = StubTick(mid=1.2000)

    # Initialise with fast below slow
    result = engine.update(tick, {"fast": 1.0000, "slow": 1.0010})
    assert result.should_open is False

    # Fast crosses above slow -> long entry
    result = engine.update(tick, {"fast": 1.0020, "slow": 1.0010})
    assert result.should_open is True
    assert result.direction == 1
    assert result.tp == pytest.approx(1.2005)
    assert result.sl == pytest.approx(1.1995)
    assert result.timeout_seconds == pytest.approx(120)

    # Cross back below -> short
    engine.update(tick, {"fast": 1.0020, "slow": 1.0015})  # settle diff positive
    result = engine.update(tick, {"fast": 0.9990, "slow": 1.0010})
    assert result.should_open is True
    assert result.direction == -1
    assert result.tp == pytest.approx(1.1995)
    assert result.sl == pytest.approx(1.2005)
