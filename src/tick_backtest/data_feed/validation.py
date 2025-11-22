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

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from tick_backtest.data_feed.data_feed import NoMoreTicks


@dataclass
class TickValidationStats:
    """Accumulates counts for tick validation outcomes."""

    total_ticks: int = 0
    accepted_ticks: int = 0
    skipped_ticks: int = 0
    issues: Counter = field(default_factory=Counter)

    def record_issue(self, issue: str) -> None:
        self.skipped_ticks += 1
        self.issues[issue] += 1

    def as_dict(self) -> Dict[str, Any]:
        return {
            "total_ticks": self.total_ticks,
            "accepted_ticks": self.accepted_ticks,
            "skipped_ticks": self.skipped_ticks,
            "issues": dict(self.issues),
        }


class TickValidator:
    """Validates ticks emitted by a data feed, tracking error tallies."""

    def __init__(self, *, pair: str) -> None:
        self.pair = pair
        self.stats = TickValidationStats()
        self._last_timestamp: Optional[float] = None
        self._last_timestamp_ns: Optional[int] = None

    def _require_field(self, tick: Any, field: str) -> float:
        try:
            value = getattr(tick, field)
        except AttributeError as exc:  # pragma: no cover - defensive
            raise ValueError(f"missing_field:{field}") from exc
        try:
            value = float(value)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"non_numeric_field:{field}") from exc
        if not math.isfinite(value):
            raise ValueError(f"non_finite_field:{field}")
        return value

    def validate(self, tick: Any) -> bool:
        """Return True if the tick is valid, otherwise record an issue and return False."""
        self.stats.total_ticks += 1

        timestamp_ns_raw = getattr(tick, "timestamp_ns", None)
        if timestamp_ns_raw is not None:
            try:
                timestamp_ns = int(timestamp_ns_raw)
            except Exception:
                self.stats.record_issue("non_numeric_field:timestamp")
                return False
            timestamp = float(timestamp_ns) / 1_000_000_000.0
        else:
            timestamp_ns = None
            try:
                timestamp = self._require_field(tick, "timestamp")
            except ValueError as exc:
                issue = str(exc)
                self.stats.record_issue(issue)
                return False

        try:
            bid = self._require_field(tick, "bid")
            ask = self._require_field(tick, "ask")
            mid = self._require_field(tick, "mid")
        except ValueError as exc:
            issue = str(exc)
            self.stats.record_issue(issue)
            return False

        if ask < bid:
            self.stats.record_issue("negative_spread")
            return False

        expected_mid = 0.5 * (bid + ask)
        if not math.isfinite(expected_mid) or abs(expected_mid - mid) > 1e-6 * max(1.0, abs(expected_mid)):
            self.stats.record_issue("invalid_mid")
            return False

        if timestamp_ns is not None and self._last_timestamp_ns is not None:
            if timestamp_ns < self._last_timestamp_ns:
                self.stats.record_issue("timestamp_regression")
                return False
        elif self._last_timestamp is not None and timestamp < self._last_timestamp:
            self.stats.record_issue("timestamp_regression")
            return False

        # Passed all checks
        self._last_timestamp = timestamp
        self._last_timestamp_ns = timestamp_ns
        self.stats.accepted_ticks += 1
        return True


class ValidatingDataFeed:
    """Wraps a data feed, skipping invalid ticks while recording validation stats."""

    def __init__(self, feed: Any, validator: TickValidator):
        self._feed = feed
        self.validator = validator
        self.pair = getattr(feed, "pair", validator.pair)

    def tick(self):
        while True:
            tick = self._feed.tick()
            if self.validator.validate(tick):
                return tick

    def __getattr__(self, item):
        if item == "validator":
            return self.validator
        return getattr(self._feed, item)

    def __iter__(self):  # pragma: no cover - convenience for potential streaming
        try:
            while True:
                yield self.tick()
        except NoMoreTicks:
            return
