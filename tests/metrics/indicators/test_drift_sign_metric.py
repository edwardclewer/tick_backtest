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

"""Tests for the drift sign metric."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from tick_backtest.metrics.indicators.drift_sign_metric import DriftSignMetric
from tests.helpers.metrics_reference import drift_expected


def test_drift_sign_returns_zero_without_history(tick_series_factory):
    """Initial updates should default to neutral sign when history is sparse."""

    metric = DriftSignMetric(name="drift_sign", lookback_seconds=60)
    tick = tick_series_factory([(1.0000, 1.0002)])[0]

    metric.update(tick)

    values = metric.value()
    assert values["drift_sign"] == 0
    assert values["drift"] == pytest.approx(0.0, abs=1e-9)


def test_drift_sign_follows_mid_price_deviation(tick_series_factory, tick_factory):
    """Expect sign to flip based on rolling mean versus current mid."""

    metric = DriftSignMetric(name="drift_sign", lookback_seconds=120)

    ticks = tick_series_factory(
        [
            (1.0000, 1.0002),
            (1.0010, 1.0012),
            (1.0020, 1.0022),
        ]
    )
    for tick in ticks:
        metric.update(tick)

    assert metric.value()["drift_sign"] == 1

    last_timestamp = datetime.fromtimestamp(ticks[-1].timestamp, tz=timezone.utc) + timedelta(seconds=1)
    reversal = tick_factory(bid=0.9990, ask=0.9992, timestamp=last_timestamp)
    metric.update(reversal)

    assert metric.value()["drift_sign"] == -1


def test_drift_sign_random_sequence_matches_reference(tick_factory):
    """Drift magnitude and sign should match reference implementation."""

    rng = np.random.default_rng(17)
    lookback = 30.0
    metric = DriftSignMetric(name="drift_sign", lookback_seconds=lookback)

    base = datetime(2023, 6, 1, tzinfo=timezone.utc)
    offsets = np.cumsum(rng.uniform(0.2, 1.5, size=50))
    mids = rng.normal(loc=1.0500, scale=0.0005, size=50)

    reference = drift_expected(offsets.tolist(), mids.tolist(), lookback)

    for offset, mid, (expected_drift, expected_sign) in zip(offsets, mids, reference):
        tick = tick_factory(
            bid=float(mid) - 0.00005,
            ask=float(mid) + 0.00005,
            timestamp=base + timedelta(seconds=float(offset)),
            mid=float(mid),
        )
        metric.update(tick)
        values = metric.value()

        if not math.isfinite(expected_drift):
            assert math.isnan(values["drift"])
            assert values["drift_sign"] == 0
        else:
            assert values["drift"] == pytest.approx(expected_drift, rel=1e-6, abs=1e-9)
            assert values["drift_sign"] == pytest.approx(float(expected_sign))
