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

__all__ = ["Tick"]


try:
    from tick_backtest.data_feed._data_feed import TickRecord as Tick  # type: ignore
except ImportError:  # pragma: no cover - fallback when C extensions unavailable

    class Tick:
        """Lightweight Python tick with UTC timestamp tracked at nanosecond precision."""

        __slots__ = ("timestamp", "timestamp_ns", "bid", "ask", "mid", "hour", "minute")

        def __init__(self, timestamp: float, bid: float, ask: float, mid: float, *, timestamp_ns: int | None = None):
            if timestamp_ns is None:
                timestamp_ns = int(float(timestamp) * 1_000_000_000)
            self.timestamp_ns = int(timestamp_ns)
            self.timestamp = float(self.timestamp_ns) / 1_000_000_000.0
            self.bid = float(bid)
            self.ask = float(ask)
            self.mid = float(mid)

            seconds = self.timestamp_ns // 1_000_000_000
            seconds_in_day = seconds % 86400
            self.hour = seconds_in_day // 3600
            self.minute = (seconds_in_day % 3600) // 60
