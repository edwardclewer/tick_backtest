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

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tick_backtest.data_feed.data_feed import NoMoreTicks
from tick_backtest.data_feed.validation import TickValidator, ValidatingDataFeed


class DummyFeed:
    """Simple feed that yields a predetermined sequence of ticks."""

    def __init__(self, ticks):
        self._ticks = iter(ticks)
        self.pair = "DUMMY"

    def tick(self):
        try:
            return next(self._ticks)
        except StopIteration:
            raise NoMoreTicks


def _tick(timestamp, bid, ask):
    return SimpleNamespace(timestamp=timestamp, bid=bid, ask=ask, mid=0.5 * (bid + ask))


def test_tick_validator_accepts_valid_sequence():
    validator = TickValidator(pair="TEST")

    feed = DummyFeed([_tick(1.0, 1.0, 2.0), _tick(2.0, 1.5, 2.5)])
    validating_feed = ValidatingDataFeed(feed, validator)

    t1 = validating_feed.tick()
    t2 = validating_feed.tick()

    assert t1.timestamp == 1.0
    assert t2.timestamp == 2.0
    stats = validator.stats.as_dict()
    assert stats["total_ticks"] == 2
    assert stats["accepted_ticks"] == 2
    assert stats["skipped_ticks"] == 0


def test_tick_validator_skips_invalid_ticks():
    validator = TickValidator(pair="TEST")
    ticks = [
        SimpleNamespace(timestamp=1.0, bid=1.0, ask=0.5, mid=0.75),  # negative spread
        _tick(2.0, 1.0, 2.0),
    ]
    feed = DummyFeed(ticks)
    validating_feed = ValidatingDataFeed(feed, validator)

    tick = validating_feed.tick()

    assert tick.timestamp == 2.0
    stats = validator.stats.as_dict()
    assert stats["total_ticks"] == 2
    assert stats["accepted_ticks"] == 1
    assert stats["skipped_ticks"] == 1
    assert stats["issues"]["negative_spread"] == 1


def test_tick_validator_detects_timestamp_regression():
    validator = TickValidator(pair="TEST")
    ticks = [
        _tick(2.0, 1.0, 2.0),
        _tick(1.0, 1.1, 2.1),
        _tick(3.0, 1.2, 2.2),
    ]
    feed = DummyFeed(ticks)
    validating_feed = ValidatingDataFeed(feed, validator)

    first = validating_feed.tick()
    assert first.timestamp == 2.0
    second = validating_feed.tick()
    assert second.timestamp == 3.0

    stats = validator.stats.as_dict()
    assert stats["total_ticks"] == 3
    assert stats["accepted_ticks"] == 2
    assert stats["issues"]["timestamp_regression"] == 1
