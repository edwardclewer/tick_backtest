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

"""Tests for the threshold reversion metric."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from tick_backtest.metrics.indicators.threshold_reversion_metric import ThresholdReversionMetric


def _make_metric(**overrides) -> ThresholdReversionMetric:
    params = {
        "name": "reversion",
        "lookback_seconds": 120,
        "threshold_pips": 10,
        "pip_size": 0.0001,
        "tp_pips": 10,
        "sl_pips": 12,
        "min_recency_seconds": 0.0,
        "trade_timeout_seconds": None,
    }
    params.update(overrides)
    return ThresholdReversionMetric(**params)


def test_threshold_reversion_goes_short_on_upward_breach(tick_factory):
    metric = _make_metric()
    base_time = datetime(2015, 1, 1, tzinfo=timezone.utc)

    # Seed prices within threshold – no position yet.
    for idx, mid in enumerate((1.2000, 1.2003)):
        metric.update(
            tick_factory(
                mid=mid,
                timestamp=base_time + timedelta(seconds=idx * 5),
            )
        )
        assert metric.value()["position"] == pytest.approx(0.0)

    # Price rallies beyond threshold (>= 10 pips) from earlier 1.2000 price.
    metric.update(
        tick_factory(
            mid=1.2012,
            timestamp=base_time + timedelta(seconds=30),
        )
    )

    values = metric.value()
    assert values["position"] == -1.0  # short toward reference
    assert math.isclose(values["reference_price"], 1.2000, rel_tol=0, abs_tol=1e-9)
    assert values["distance_from_reference"] >= 0.0010
    assert math.isclose(values["tp_price"], 1.2002, rel_tol=0, abs_tol=1e-6)
    assert math.isclose(values["sl_price"], 1.2024, rel_tol=0, abs_tol=1e-6)


def test_threshold_reversion_min_recency_blocks_recent_reference(tick_factory):
    metric = _make_metric(min_recency_seconds=30.0)
    base_time = datetime(2015, 1, 1, tzinfo=timezone.utc)

    metric.update(tick_factory(mid=1.2000, timestamp=base_time))
    metric.update(
        tick_factory(
            mid=1.2012,
            timestamp=base_time + timedelta(seconds=20),
        )
    )

    values = metric.value()
    assert values["position"] == 0.0
    assert math.isnan(values["tp_price"])
    assert math.isnan(values["sl_price"])

    # Once the reference is old enough the position should form.
    metric.update(
        tick_factory(
            mid=1.2013,
            timestamp=base_time + timedelta(seconds=40),
        )
    )
    values = metric.value()
    assert values["position"] == -1.0
    assert values["reference_age_seconds"] >= 30.0


def test_threshold_reversion_flattens_on_return(tick_factory):
    metric = _make_metric()
    base_time = datetime(2015, 1, 1, tzinfo=timezone.utc)

    metric.update(tick_factory(mid=1.2000, timestamp=base_time))
    metric.update(
        tick_factory(
            mid=1.2012,
            timestamp=base_time + timedelta(seconds=30),
        )
    )
    assert metric.value()["position"] == -1.0

    metric.update(
        tick_factory(
            mid=1.20005,
            timestamp=base_time + timedelta(seconds=35),
        )
    )  # revert and overshoot; should flip to long
    assert metric.value()["position"] == 1.0
