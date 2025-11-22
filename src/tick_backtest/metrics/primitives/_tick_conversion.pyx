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

# cython: language_level=3

from tick_backtest.metrics.primitives._tick_types cimport TickStruct


cdef void fill_tick_struct(object tick, TickStruct* out):
    cdef object ts = getattr(tick, "timestamp")
    cdef object bid = getattr(tick, "bid")
    cdef object ask = getattr(tick, "ask")
    cdef object mid = getattr(tick, "mid")
    cdef object hour_attr
    cdef object minute_attr

    if hasattr(ts, "timestamp"):
        out.timestamp = float(ts.timestamp())
        hour_attr = getattr(ts, "hour", None)
        minute_attr = getattr(ts, "minute", None)
    else:
        out.timestamp = float(ts)
        hour_attr = getattr(tick, "hour", None)
        minute_attr = getattr(tick, "minute", None)

    cdef long long seconds
    cdef long long days
    cdef long long seconds_in_day

    if hour_attr is None or minute_attr is None:
        seconds = <long long> out.timestamp
        days = seconds // 86400
        seconds_in_day = seconds - days * 86400
        if seconds_in_day < 0:
            seconds_in_day += 86400
        hour_attr = seconds_in_day // 3600
        minute_attr = (seconds_in_day % 3600) // 60

    out.bid = float(bid)
    out.ask = float(ask)
    out.mid = float(mid)
    out.hour = int(hour_attr)
    out.minute = int(minute_attr)
