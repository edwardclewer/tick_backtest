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

from tick_backtest.metrics.indicators.ewma_slope_metric import EWMASlopeMetric
from tests.helpers.metrics_reference import ewma_slope_expected


def test_ewma_slope_nan_until_history_available(tick_factory):
    metric = EWMASlopeMetric(
        name="ewma_slope_mid",
        tau_seconds=60.0,
        window_seconds=30.0,
    )

    tick = tick_factory(mid=1.0, timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc))
    metric.update(tick)

    assert math.isnan(metric.value()["slope"])


def test_ewma_slope_matches_linear_change(tick_factory):
    tau = 60.0
    metric = EWMASlopeMetric(
        name="ewma_slope_mid",
        tau_seconds=tau,
        window_seconds=30.0,
    )

    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    tick1 = tick_factory(mid=1.0, timestamp=base)
    tick2 = tick_factory(mid=2.0, timestamp=base + timedelta(seconds=15))

    metric.update(tick1)
    metric.update(tick2)

    alpha = 1.0 - math.exp(-15.0 / tau)
    ewma_now = (1.0 - alpha) * 1.0 + alpha * 2.0
    expected_slope = (ewma_now - 1.0) / 15.0

    result = metric.value()
    assert result["ewma"] == pytest.approx(ewma_now)
    assert result["slope"] == pytest.approx(expected_slope)


def test_ewma_slope_trims_history(tick_factory):
    metric = EWMASlopeMetric(
        name="ewma_slope_mid",
        tau_seconds=60.0,
        window_seconds=20.0,
    )

    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    ticks = [
        tick_factory(mid=1.0, timestamp=base),
        tick_factory(mid=1.5, timestamp=base + timedelta(seconds=10)),
        tick_factory(mid=2.0, timestamp=base + timedelta(seconds=25)),
    ]

    for tick in ticks:
        metric.update(tick)

    # After third update, the first point (t=0) should be trimmed (window=20s)
    # slope should use last two points (10s and 25s)
    assert metric.value()["slope"] > 0.0


def test_ewma_slope_random_sequence_matches_reference(tick_factory):
    """EWMA slope metric should align with reference implementation on random data."""

    rng = np.random.default_rng(2024)
    tau = 18.0
    window = 12.0
    metric = EWMASlopeMetric(
        name="ewma_slope_mid",
        tau_seconds=tau,
        window_seconds=window,
    )

    base = datetime(2022, 6, 1, tzinfo=timezone.utc)
    offsets = np.cumsum(rng.uniform(0.2, 1.5, size=40))
    mids = rng.normal(loc=1.1000, scale=0.0007, size=40)

    reference = ewma_slope_expected(offsets.tolist(), mids.tolist(), tau, window)

    for offset, mid, (expected_ewma, expected_slope) in zip(offsets, mids, reference):
        tick = tick_factory(mid=float(mid), timestamp=base + timedelta(seconds=float(offset)))
        metric.update(tick)
        values = metric.value()

        assert values["ewma"] == pytest.approx(expected_ewma, abs=1e-9, rel=1e-9)

        if math.isnan(expected_slope):
            assert math.isnan(values["slope"])
        else:
            assert values["slope"] == pytest.approx(expected_slope, rel=1e-6, abs=1e-9)
