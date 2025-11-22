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

"""Tests for the time-weighted histogram primitive."""

from __future__ import annotations

import numpy as np
import pytest

from tick_backtest.metrics.primitives._time_weighted_histogram_py import PyTimeWeightedHistogram

try:
    from tick_backtest.metrics.primitives._time_weighted_histogram import TimeWeightedHistogram as CTimeWeightedHistogram
except ImportError:  # pragma: no cover - optional extension
    CTimeWeightedHistogram = None


IMPLEMENTATIONS = [
    pytest.param(PyTimeWeightedHistogram, id="python"),
]

if CTimeWeightedHistogram is not None:
    IMPLEMENTATIONS.append(pytest.param(CTimeWeightedHistogram, id="cython"))


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_add_assigns_weights_to_bins(impl):
    """Document bin lookup and weight accumulation behaviour."""

    hist = impl(np.array([0.0, 1.0, 2.0]), horizon_seconds=10.0)
    hist.add(start=0.0, end=5.0, value=0.5)

    assert hist.weights[0] == pytest.approx(5.0)
    assert hist.total == pytest.approx(5.0)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_trim_removes_partial_interval(impl):
    """Ensure trim applies partial expiry when intervals straddle cutoff."""

    hist = impl(np.array([0.0, 1.0, 2.0]), horizon_seconds=5.0)
    hist.add(start=0.0, end=4.0, value=0.5)  # bin 0
    hist.add(start=4.0, end=6.0, value=1.5)  # bin 1

    hist.trim(now=7.0)

    # First event trimmed from [0,4] -> [2,4]
    assert hist.weights[0] == pytest.approx(2.0)
    # Second event fully retained (weight = 2)
    assert hist.weights[1] == pytest.approx(2.0)
    assert hist.total == pytest.approx(4.0)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_percentile_rank_interpolates_within_bin(impl):
    """Validate interpolation within the active histogram bin."""

    hist = impl(np.array([0.0, 1.0, 2.0]), horizon_seconds=10.0)
    hist.add(start=0.0, end=2.0, value=0.2)   # weight 2 in bin 0
    hist.add(start=2.0, end=4.0, value=1.6)   # weight 2 in bin 1

    pct_low = hist.percentile_rank(0.5)
    pct_high = hist.percentile_rank(1.6)

    assert pct_low == pytest.approx(0.25)
    assert pct_high == pytest.approx(0.8)
