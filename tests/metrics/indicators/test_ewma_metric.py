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

import math
import numpy as np

import pytest

from tick_backtest.metrics.indicators.ewma_metric import EWMAMetric
from tests.helpers.metrics_reference import ewma_metric_expected


def test_ewma_seeds_to_first_price(tick_factory):
    metric = EWMAMetric(name="ewma_mid", tau_seconds=60.0)
    tick = tick_factory(mid=1.2345, timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc))

    metric.update(tick)
    result = metric.value()

    assert result == {"ewma": pytest.approx(1.2345)}


def test_ewma_exponential_response(tick_factory):
    tau = 60.0
    metric = EWMAMetric(name="ewma_mid", tau_seconds=tau)

    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    tick1 = tick_factory(mid=1.0, timestamp=base)
    tick2 = tick_factory(mid=2.0, timestamp=base + timedelta(seconds=30))

    metric.update(tick1)
    metric.update(tick2)

    alpha = 1.0 - math.exp(-30.0 / tau)
    expected = (1.0 - alpha) * 1.0 + alpha * 2.0

    assert metric.value()["ewma"] == pytest.approx(expected)


def test_ewma_custom_price_field(tick_factory):
    metric = EWMAMetric(name="ewma_bid", tau_seconds=10.0, price_field="bid")
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)

    metric.update(tick_factory(bid=1.0, ask=1.1, timestamp=ts))
    metric.update(tick_factory(bid=1.2, ask=1.3, timestamp=ts + timedelta(seconds=5)))

    assert metric.value()["ewma"] > 1.0
    assert metric.value()["ewma"] < 1.2


def test_ewma_metric_handles_identical_timestamps(tick_factory):
    """Metric should respect MIN_DT when successive ticks share a timestamp."""

    tau = 15.0
    metric = EWMAMetric(name="ewma_mid", tau_seconds=tau)
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)

    metric.update(tick_factory(mid=1.0, timestamp=ts))
    metric.update(tick_factory(mid=3.0, timestamp=ts))

    alpha = 1.0 - math.exp(-1e-6 / tau)
    expected = (1.0 - alpha) * 1.0 + alpha * 3.0
    assert metric.value()["ewma"] == pytest.approx(expected, rel=1e-9)


def test_ewma_metric_converges_after_large_gap(tick_factory):
    tau = 5.0
    metric = EWMAMetric(name="ewma_mid", tau_seconds=tau)
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)

    metric.update(tick_factory(mid=0.0, timestamp=ts))
    metric.update(tick_factory(mid=5.0, timestamp=ts + timedelta(seconds=60)))

    assert metric.value()["ewma"] == pytest.approx(5.0, abs=5e-3)


def test_ewma_metric_random_sequence_matches_reference(tick_factory):
    """Ensure EWMA metric tracks the analytical update rule over random data."""

    rng = np.random.default_rng(321)
    tau = 25.0
    metric = EWMAMetric(name="ewma_mid", tau_seconds=tau)

    base = datetime(2021, 1, 1, tzinfo=timezone.utc)
    offsets = np.cumsum(rng.uniform(0.2, 1.0, size=50))
    mids = rng.normal(loc=1.2000, scale=0.0006, size=50)

    expected_values = ewma_metric_expected(offsets.tolist(), mids.tolist(), tau)

    for offset, mid, expected in zip(offsets, mids, expected_values):
        tick = tick_factory(mid=float(mid), timestamp=base + timedelta(seconds=float(offset)))
        metric.update(tick)
        assert metric.value()["ewma"] == pytest.approx(expected, rel=1e-9, abs=1e-9)
