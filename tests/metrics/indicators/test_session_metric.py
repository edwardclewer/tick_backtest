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

"""Tests for the session classifier metric."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tick_backtest.metrics.indicators.session_metric import SessionMetric


@pytest.mark.parametrize(
    "hour, expected",
    [
        (6, "Asia"),
        (8, "London"),
        (13, "London_New_York_Overlap"),
        (17, "New_York"),
        (21, "Other"),
        (23, "Asia"),
    ],
)
def test_session_metric_labels_minutes(tick_factory, hour, expected):
    """The session label follows the predefined UTC session table."""

    metric = SessionMetric(name="session")
    ts = datetime(2015, 1, 1, hour=hour, tzinfo=timezone.utc)
    tick = tick_factory(timestamp=ts)

    metric.update(tick)

    assert metric.value()["session_label"] == expected


def test_session_metric_handles_midnight_wrap(tick_factory):
    """Minutes after midnight should continue mapping to the Asia session."""

    metric = SessionMetric(name="session")

    before_midnight = tick_factory(timestamp=datetime(2015, 1, 1, 23, 59, tzinfo=timezone.utc))
    metric.update(before_midnight)
    assert metric.value()["session_label"] == "Asia"

    after_midnight = tick_factory(timestamp=datetime(2015, 1, 2, 0, 1, tzinfo=timezone.utc))
    metric.update(after_midnight)
    assert metric.value()["session_label"] == "Asia"
