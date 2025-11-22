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

"""Tests for the time-weighted rolling window primitive."""

from __future__ import annotations

import math

import numpy as np
import pytest
from tick_backtest.metrics.primitives._time_rolling_window_py import PyTimeRollingWindow

try:
    from tick_backtest.metrics.primitives._time_rolling_window import TimeRollingWindow as CTimeRollingWindow
except ImportError:  # pragma: no cover - compiled extension optional
    CTimeRollingWindow = None


IMPLEMENTATIONS = [
    pytest.param(PyTimeRollingWindow, id="python"),
]

if CTimeRollingWindow is not None:
    IMPLEMENTATIONS.append(pytest.param(CTimeRollingWindow, id="cython"))


def _assert_len(window, expected: int) -> None:
    if hasattr(window, "__len__"):
        assert len(window) == expected  # type: ignore[arg-type]


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_append_accumulates_weight(impl):
    """Window should accumulate weighted sums as ticks arrive."""

    window = impl(lookback_seconds=10)
    window.append(ts=0.0, value=1.0, dt=1.0)
    window.append(ts=1.0, value=3.0, dt=1.0)

    mean, stdev = window.stats()
    assert mean == pytest.approx(2.0)
    assert stdev == pytest.approx(1.0)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_trim_drops_expired_samples(impl):
    """Samples older than the lookback horizon should be removed."""

    window = impl(lookback_seconds=5)
    window.append(ts=0.0, value=1.0, dt=1.0)
    window.append(ts=10.0, value=5.0, dt=1.0)

    mean, _ = window.stats()
    assert mean == pytest.approx(5.0)
    _assert_len(window, 1)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_partial_overlap_is_weighted(impl):
    """Intervals partially outside the horizon should be trimmed proportionally."""

    window = impl(lookback_seconds=5)
    window.append(ts=0.0, value=10.0, dt=4.0)
    window.append(ts=4.0, value=2.0, dt=1.0)
    window.append(ts=6.0, value=4.0, dt=1.0)

    mean, stdev = window.stats()
    assert mean == pytest.approx(7.2)
    assert stdev == pytest.approx(3.4871191548)
    _assert_len(window, 3)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_zero_or_negative_dt_is_normalised(impl):
    """Non-positive durations should fall back to an infinitesimal weight."""

    window = impl(lookback_seconds=5)
    window.append(ts=1.0, value=2.0, dt=0.0)

    mean, stdev = window.stats()
    assert mean == pytest.approx(2.0)
    assert stdev == pytest.approx(0.0)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_nan_inputs_are_ignored(impl):
    """Non-finite samples must be skipped before affecting state."""

    window = impl(lookback_seconds=5)
    window.append(ts=float("nan"), value=1.0, dt=1.0)
    window.append(ts=1.0, value=3.0, dt=1.0)

    mean, stdev = window.stats()
    assert mean == pytest.approx(3.0)
    assert stdev == pytest.approx(0.0)
    _assert_len(window, 1)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_large_gap_resets_window(impl):
    """Long gaps should evict stale samples entirely."""

    window = impl(lookback_seconds=3.0)
    window.append(ts=0.0, value=1.0, dt=1.0)
    window.append(ts=1.0, value=2.0, dt=1.0)
    window.append(ts=10.0, value=5.0, dt=1.0)

    mean, stdev = window.stats()
    assert mean == pytest.approx(5.0)
    assert stdev == pytest.approx(0.0)
    _assert_len(window, 1)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_stats_matches_python_reference(impl):
    """Cython and Python implementations should agree on irregular sequences."""

    rng = np.random.default_rng(7)
    lookback = 6.0

    times = np.cumsum(rng.uniform(0.05, 1.0, size=40))
    values = rng.normal(loc=0.0, scale=1.5, size=40)
    durations = rng.uniform(0.02, 0.9, size=40)

    window = impl(lookback_seconds=lookback)
    reference = PyTimeRollingWindow(lookback_seconds=lookback)

    for ts, value, dt in zip(times, values, durations):
        window.append(ts=float(ts), value=float(value), dt=float(dt))
        reference.append(ts=float(ts), value=float(value), dt=float(dt))

    mean, stdev = window.stats()
    ref_mean, ref_stdev = reference.stats()

    if math.isnan(ref_mean):
        assert math.isnan(mean)
    else:
        assert mean == pytest.approx(ref_mean, rel=1e-9, abs=1e-9)

    if math.isnan(ref_stdev):
        assert math.isnan(stdev)
    else:
        assert stdev == pytest.approx(ref_stdev, rel=1e-9, abs=1e-9)


def test_python_reference_consistent_with_internal_sums():
    """Validate stats() aligns with the weighted sums stored on the Python fallback."""

    window = PyTimeRollingWindow(lookback_seconds=4.0)
    samples = [
        (0.0, 1.0, 0.5),
        (1.0, 2.0, 1.0),
        (2.5, 4.0, 0.5),
        (3.5, 1.5, 0.75),
    ]

    for ts, value, dt in samples:
        window.append(ts=ts, value=value, dt=dt)

    mean, stdev = window.stats()
    if window.sum_w <= 1e-12:
        assert math.isnan(mean) and math.isnan(stdev)
        return

    expected_mean = window.sum_x / window.sum_w
    expected_var = max(window.sum_x2 / window.sum_w - expected_mean * expected_mean, 0.0)

    assert mean == pytest.approx(expected_mean, rel=1e-9, abs=1e-9)
    assert stdev == pytest.approx(math.sqrt(expected_var), rel=1e-9, abs=1e-9)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_stats_returns_nan_when_empty(impl):
    """When no weight is present, stats() should return NaNs."""

    window = impl(lookback_seconds=5)
    mean, stdev = window.stats()
    assert math.isnan(mean)
    assert math.isnan(stdev)
