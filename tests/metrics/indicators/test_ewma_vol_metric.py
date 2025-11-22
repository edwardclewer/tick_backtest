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

"""Tests for the EWMA volatility metric."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from tick_backtest.metrics.indicators.ewma_vol_metric import EWMAVolMetric
from tests.helpers.metrics_reference import ewma_vol_expected


def test_ewma_vol_requires_previous_mid(tick_factory):
    """Document warmup behaviour requiring two ticks."""

    metric = EWMAVolMetric(name="vol", tau_seconds=60.0, percentile_horizon_seconds=120.0)
    metric.update(tick_factory())
    values = metric.value()

    assert values["vol_ewma"] == pytest.approx(0.0)
    assert math.isnan(values["vol_percentile"])


def test_ewma_vol_updates_histogram_percentiles(tick_series_factory):
    """Ensure percentile rank reflects the EWMA distribution."""

    metric = EWMAVolMetric(name="vol", tau_seconds=30.0, percentile_horizon_seconds=120.0)
    ticks = tick_series_factory(
        [
            (1.0000, 1.0002),
            (1.0010, 1.0012),
            (1.0050, 1.0052),
            (1.0005, 1.0007),
            (1.0040, 1.0042),
        ]
    )

    for tick in ticks:
        metric.update(tick)

    values = metric.value()
    assert values["vol_ewma"] > 0.0
    assert 0.0 <= values["vol_percentile"] <= 1.0


def test_ewma_vol_percentile_responds_to_shocks(tick_series_factory):
    """Percentile rank should increase on volatility spikes and decay during calm."""

    metric = EWMAVolMetric(
        name="vol",
        tau_seconds=20.0,
        percentile_horizon_seconds=120.0,
        bins=64,
        stddev_cap=5.0,
    )

    calm_ticks = tick_series_factory(
        [
            (1.0000, 1.0002),
            (1.0001, 1.0003),
            (1.0002, 1.0004),
            (1.00015, 1.00035),
            (1.00018, 1.00038),
        ]
    )
    for tick in calm_ticks:
        metric.update(tick)

    baseline = metric.value()["vol_percentile"]
    assert math.isnan(baseline) or 0.0 <= baseline <= 0.5

    shock_ticks = tick_series_factory(
        [
            (1.0020, 1.0022),
            (0.9980, 0.9982),
            (1.0040, 1.0042),
        ]
    )
    for tick in shock_ticks:
        metric.update(tick)

    shocked = metric.value()["vol_percentile"]
    assert shocked > baseline or math.isnan(baseline)

    # Feed quiet data so histogram decays towards lower percentiles
    quiet_ticks = tick_series_factory(
        [
            (1.0010, 1.0012),
            (1.0011, 1.0013),
            (1.0012, 1.0014),
            (1.00115, 1.00135),
        ]
    )
    for tick in quiet_ticks:
        metric.update(tick)

    cooled = metric.value()["vol_percentile"]
    assert cooled <= shocked


def test_ewma_vol_random_sequence_matches_reference(tick_factory):
    """Cross-check EWMA variance and percentile against Python primitives."""

    rng = np.random.default_rng(77)
    params = dict(
        tau_seconds=45.0,
        percentile_horizon_seconds=90.0,
        bins=64,
        base_vol=1e-4,
        stddev_cap=3.0,
    )

    metric = EWMAVolMetric(name="vol", **params)
    base =  datetime(2022, 7, 1, tzinfo=timezone.utc)
    offsets = np.cumsum(rng.uniform(0.1, 0.8, size=50))
    mids = np.exp(rng.normal(loc=0.0, scale=0.0005, size=50))  # ensure positive

    reference = ewma_vol_expected(
        offsets.tolist(),
        mids.tolist(),
        **params,
    )

    for offset, mid, (expected_ewma, expected_pct) in zip(offsets, mids, reference):
        tick = tick_factory(
            bid=float(mid) - 0.00005,
            ask=float(mid) + 0.00005,
            timestamp=base + timedelta(seconds=float(offset)),
            mid=float(mid),
        )

        metric.update(tick)
        values = metric.value()

        assert values["vol_ewma"] == pytest.approx(expected_ewma, rel=1e-6, abs=1e-12)

        if math.isnan(expected_pct):
            assert math.isnan(values["vol_percentile"])
        else:
            assert values["vol_percentile"] == pytest.approx(expected_pct, rel=1e-5, abs=1e-6)
