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

from datetime import datetime, timezone, timedelta

import numpy as np
import pytest

from tick_backtest.metrics.indicators.spread_metric import SpreadMetric
from tests.helpers.metrics_reference import spread_percentile_reference


def test_spread_metric_basic_values(tick_factory):
    metric = SpreadMetric(name="spread", pip_size=0.0001, window_seconds=60.0)
    tick = tick_factory(bid=1.0000, ask=1.0001, timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc))

    metric.update(tick)
    values = metric.value()

    assert values["spread"] == pytest.approx(0.0001)
    assert values["spread_pips"] == pytest.approx(1.0)
    assert values["spread_percentile"] == pytest.approx(1.0)


def test_spread_metric_percentile_rank(tick_factory):
    metric = SpreadMetric(name="spread", pip_size=0.0001, window_seconds=60.0)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)

    ticks = [
        tick_factory(bid=1.0000, ask=1.0001, timestamp=base),  # 1 pip
        tick_factory(bid=1.0000, ask=1.0002, timestamp=base + timedelta(seconds=10)),  # 2 pips
        tick_factory(bid=1.0000, ask=1.00005, timestamp=base + timedelta(seconds=20)),  # 0.5 pip
    ]

    for tick in ticks:
        metric.update(tick)

    values = metric.value()

    assert values["spread_pips"] == pytest.approx(0.5)
    assert values["spread_percentile"] == pytest.approx(1 / 3)


def test_spread_metric_window_trimming(tick_factory):
    metric = SpreadMetric(name="spread", pip_size=0.0001, window_seconds=30.0)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)

    metric.update(tick_factory(bid=1.0, ask=1.0002, timestamp=base))  # older tick
    metric.update(tick_factory(bid=1.0, ask=1.0001, timestamp=base + timedelta(seconds=40)))

    values = metric.value()
    # After trimming, only last tick remains -> percentile should be 1.0 again
    assert values["spread_percentile"] == pytest.approx(1.0)


def test_spread_metric_random_sequence_matches_reference(tick_factory):
    """Validate percentile calculation against an explicit reference."""

    rng = np.random.default_rng(99)
    window = 25.0
    metric = SpreadMetric(name="spread", pip_size=0.0001, window_seconds=window)

    base = datetime(2023, 1, 1, tzinfo=timezone.utc)
    offsets = np.cumsum(rng.uniform(0.5, 3.0, size=30))
    spreads_pips = rng.uniform(0.1, 3.0, size=30)

    history: list[tuple[float, float]] = []

    for offset, spread in zip(offsets, spreads_pips):
        spread_raw = spread * 0.0001
        ts = base + timedelta(seconds=float(offset))
        tick = tick_factory(
            bid=1.2000,
            ask=1.2000 + spread_raw,
            timestamp=ts,
        )
        metric.update(tick)

        history.append((float(offset), spread))
        cutoff = float(offset) - window
        history = [(t, s) for (t, s) in history if t >= cutoff]

        expected_percentile = spread_percentile_reference(history, spread)
        values = metric.value()

        assert values["spread"] == pytest.approx(spread_raw, abs=1e-9)
        assert values["spread_pips"] == pytest.approx(spread, abs=1e-9)
        assert values["spread_percentile"] == pytest.approx(expected_percentile, abs=1e-9)
