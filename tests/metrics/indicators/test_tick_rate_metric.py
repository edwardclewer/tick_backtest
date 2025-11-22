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

import numpy as np
import pytest

from tick_backtest.metrics.indicators.tick_rate_metric import TickRateMetric
from tests.helpers.metrics_reference import tick_rate_expected


def test_tick_rate_counts_within_window(tick_factory):
    metric = TickRateMetric(name="tick_rate", window_seconds=10.0)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)

    for i in range(5):
        metric.update(tick_factory(timestamp=base + timedelta(seconds=i)))

    values = metric.value()
    assert values["tick_count"] == pytest.approx(5.0)
    assert values["tick_rate_per_sec"] == pytest.approx(0.5)
    assert values["tick_rate_per_min"] == pytest.approx(30.0)


def test_tick_rate_trims_old_ticks(tick_factory):
    metric = TickRateMetric(name="tick_rate", window_seconds=5.0)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)

    for i in range(6):
        metric.update(tick_factory(timestamp=base + timedelta(seconds=i)))

    values = metric.value()
    # window=5s -> ticks at times 1..5 inclusive remain (5 ticks)
    assert values["tick_count"] == pytest.approx(5.0)


def test_tick_rate_random_sequence_matches_reference(tick_factory):
    """Randomised arrival times should match reference counting logic."""

    rng = np.random.default_rng(202)
    window = 12.0
    metric = TickRateMetric(name="tick_rate", window_seconds=window)

    base = datetime(2022, 3, 1, tzinfo=timezone.utc)
    offsets = np.cumsum(rng.uniform(0.1, 4.0, size=50))
    reference = tick_rate_expected(offsets.tolist(), window)

    for offset, (count, per_sec, per_min) in zip(offsets, reference):
        tick = tick_factory(timestamp=base + timedelta(seconds=float(offset)))
        metric.update(tick)

        values = metric.value()
        assert values["tick_count"] == pytest.approx(float(count))
        assert values["tick_rate_per_sec"] == pytest.approx(per_sec)
        assert values["tick_rate_per_min"] == pytest.approx(per_min)
        assert values["tick_rate_per_min"] == pytest.approx(values["tick_rate_per_sec"] * 60.0)
