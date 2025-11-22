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

"""Tests for the z-score metric."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from tick_backtest.metrics.indicators.zscore_metric import ZScoreMetric
from tests.helpers.metrics_reference import RollingWindowReference


def _make_metric(lookback_seconds: float = 1800.0) -> ZScoreMetric:
    return ZScoreMetric(name="z", lookback_seconds=lookback_seconds)


def test_zscore_requires_sufficient_variance(tick_series_factory):
    """With flat prices the z-score should fall back to zero."""

    metric = _make_metric()
    ticks = tick_series_factory([(1.0000, 1.0002)] * 5)

    for tick in ticks:
        metric.update(tick)

    values = metric.value()
    assert values["rolling_residual"] == pytest.approx(0.0, abs=1e-6)
    assert values["z_score"] == pytest.approx(0.0, abs=1e-6)


def test_zscore_computes_residual_from_weighted_mean(tick_series_factory):
    """Rolling residual and z-score should respect the time-weighted statistics."""

    metric = _make_metric()
    ticks = tick_series_factory(
        [
            (1.0000, 1.0002),  # mid ≈ 1.0001
            (2.0000, 2.0002),  # mid ≈ 2.0001
            (3.0000, 3.0002),  # mid ≈ 3.0001
        ]
    )

    for tick in ticks:
        metric.update(tick)

    values = metric.value()
    residual = values["rolling_residual"]
    z_score = values["z_score"]

    assert residual == pytest.approx(0.5, abs=1e-3)
    assert z_score == pytest.approx(1.0, abs=1e-3)


def test_zscore_matches_time_weighted_reference(tick_factory):
    """Verify the metric mirrors the reference rolling window for irregular ticks."""

    lookback = 5.0
    metric = _make_metric(lookback_seconds=lookback)
    reference = RollingWindowReference(lookback_seconds=lookback)

    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    points = [
        (0.0, 1.3300),
        (1.5, 1.3315),
        (3.5, 1.3350),
        (7.2, 1.3290),
        (9.0, 1.3275),
    ]

    for offset, mid in points:
        tick = tick_factory(
            bid=mid - 0.00005,
            ask=mid + 0.00005,
            timestamp=base + timedelta(seconds=offset),
        )
        metric.update(tick)

        mean, stdev = reference.update(offset, tick.mid)
        values = metric.value()

        if math.isnan(mean):
            assert values["rolling_residual"] == pytest.approx(0.0)
            assert values["z_score"] == pytest.approx(0.0)
            continue

        residual = tick.mid - mean
        assert values["rolling_residual"] == pytest.approx(residual, abs=1e-9)

        if math.isnan(stdev) or stdev <= 0.0:
            assert values["z_score"] == pytest.approx(0.0, abs=5e-6)
        else:
            expected_z = residual / stdev
            assert values["z_score"] == pytest.approx(expected_z, abs=1e-8)


def test_zscore_random_sequence_matches_reference(tick_factory):
    """Randomised sequence should mirror rolling window statistics at each tick."""

    rng = np.random.default_rng(123)
    lookback = 45.0
    metric = _make_metric(lookback_seconds=lookback)
    reference = RollingWindowReference(lookback_seconds=lookback)

    base = datetime(2021, 1, 1, tzinfo=timezone.utc)
    offsets = np.cumsum(rng.uniform(0.3, 1.2, size=60))
    mids = rng.normal(loc=1.2500, scale=0.0008, size=60)

    for offset, mid in zip(offsets, mids):
        ts = base + timedelta(seconds=float(offset))
        tick = tick_factory(
            bid=float(mid) - 0.00005,
            ask=float(mid) + 0.00005,
            timestamp=ts,
        )

        metric.update(tick)
        mean, std = reference.update(float(offset), float(tick.mid))
        values = metric.value()

        if not math.isfinite(mean):
            assert values["rolling_residual"] == pytest.approx(0.0, abs=1e-9)
            assert values["z_score"] == pytest.approx(0.0, abs=1e-9)
            continue

        residual = tick.mid - mean
        assert values["rolling_residual"] == pytest.approx(residual, abs=1e-9)

        if not math.isfinite(std) or std <= 0.0:
            assert values["z_score"] == pytest.approx(0.0, abs=5e-6)
        else:
            assert values["z_score"] == pytest.approx(residual / std, abs=1e-6)
