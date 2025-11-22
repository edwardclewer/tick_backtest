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

"""Tests for the EWMA primitive."""

from __future__ import annotations

import math

import pytest

from tick_backtest.metrics.primitives._ewma_py import PyEWMA

try:
    from tick_backtest.metrics.primitives._ewma import EWMA as CEWMA
except ImportError:  # pragma: no cover
    CEWMA = None


IMPLEMENTATIONS = [
    pytest.param(PyEWMA, id="python"),
]

if CEWMA is not None:
    IMPLEMENTATIONS.append(pytest.param(CEWMA, id="cython"))


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_ewma_warm_start_behaviour(impl):
    """The first update seeds the timestamp and keeps the accumulator at zero."""

    ewma = impl(tau_seconds=10.0)
    initial = ewma.update(t=0.0, x=1.0)
    assert initial == 0.0


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_ewma_respects_time_constant(impl):
    """Subsequent updates should decay according to the configured tau."""

    tau = 2.0
    ewma = impl(tau_seconds=tau)
    ewma.update(t=0.0, x=1.0)  # warm start
    value = ewma.update(t=2.0, x=2.0)

    decay = math.exp(-1.0)  # dt / tau = 2 / 2
    expected = (1.0 - decay) * 2.0
    assert value == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_ewma_handles_zero_dt(impl):
    """Zero elapsed time should fall back to the minimum delta."""

    tau = 5.0
    ewma = impl(tau_seconds=tau)
    ewma.update(t=1.0, x=1.0)
    value = ewma.update(t=1.0, x=3.0)  # identical timestamp

    min_dt = 1e-9
    alpha = 1.0 - math.exp(-min_dt / tau)
    expected = alpha * 3.0  # accumulator previously zero
    assert value == pytest.approx(expected, rel=1e-6, abs=1e-12)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_ewma_converges_on_large_gap(impl):
    """Large gaps should pull the smoother close to the latest observation."""

    tau = 2.0
    ewma = impl(tau_seconds=tau)
    ewma.update(t=0.0, x=0.0)
    value = ewma.update(t=20.0, x=5.0)

    # With dt >> tau, expected value approaches current observation
    assert value == pytest.approx(5.0, abs=5e-3)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_ewma_handles_power_two(impl):
    """When power=2, the smoother should treat inputs as squared."""

    ewma = impl(tau_seconds=1.0, power=2)
    ewma.update(t=0.0, x=2.0)
    value = ewma.update(t=1.0, x=3.0)

    decay = math.exp(-1.0)
    expected = (1.0 - decay) * 9.0  # 3^2
    assert value == pytest.approx(expected, rel=1e-6)
