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

"""Smoke coverage for cython-backed primitives to ensure platform parity."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pytest

from tick_backtest.metrics.primitives.ewma import EWMA
from tick_backtest.metrics.primitives.time_rolling_window import TimeRollingWindow
from tick_backtest.metrics.primitives.time_weighted_histogram import TimeWeightedHistogram


def test_ewma_smoke_matches_reference():
    tau = 5.0
    ewma = EWMA(tau, power=1)

    timestamps = [0.0, 1.0, 2.5, 4.0, 7.0]
    values = [10.0, 12.0, 11.0, 13.0, 15.0]

    outputs = []
    for t, x in zip(timestamps, values):
        outputs.append(ewma.update(t, x))

    assert outputs[0] == pytest.approx(0.0)
    assert outputs[-1] == pytest.approx(ewma.y)
    assert outputs[-1] > outputs[-2]
    assert math.isfinite(outputs[-1])


def test_time_rolling_window_stats_smoke():
    window = TimeRollingWindow(lookback_seconds=3.0)
    points = [
        (0.0, 1.0, 1.0),
        (1.0, 2.0, 1.0),
        (2.0, 3.0, 1.0),
        (5.0, 4.0, 1.0),
    ]

    for ts, value, dt in points:
        window.append(ts, value, dt)

    mean, stddev = window.stats()

    assert window.__len__() == 3
    assert math.isfinite(mean)
    assert mean == pytest.approx(3.0, rel=1e-5)
    assert stddev == pytest.approx(math.sqrt(2.0 / 3.0), rel=1e-5)


def test_time_weighted_histogram_percentile_smoke():
    edges = np.array([0.0, 1.0, 2.0, 3.0])
    hist = TimeWeightedHistogram(edges=edges, horizon_seconds=10.0)

    hist.add(0.0, 1.0, 0.5)
    hist.add(1.0, 3.0, 1.5)
    hist.trim(5.0)

    percentile = hist.percentile_rank(1.5)
    assert 0.0 <= percentile <= 1.0
    assert math.isfinite(percentile)
