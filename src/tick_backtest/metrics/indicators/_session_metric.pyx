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

from tick_backtest.metrics.primitives._base_metric cimport BaseMetric
from tick_backtest.metrics.primitives._tick_types cimport TickStruct
from tick_backtest.metrics.primitives._tick_conversion cimport fill_tick_struct


cdef list _build_table():
    table = [None] * 1440
    cdef int minute
    cdef int hour
    for minute in range(1440):
        hour = minute // 60
        if hour >= 22 or hour < 7:
            table[minute] = "Asia"
        elif 7 <= hour < 12:
            table[minute] = "London"
        elif 12 <= hour < 16:
            table[minute] = "London_New_York_Overlap"
        elif 16 <= hour < 21:
            table[minute] = "New_York"
        else:
            table[minute] = "Other"
    return table


SESSION_TABLE = _build_table()


cdef class SessionMetric(BaseMetric):
    cdef object _session

    def __init__(self, name):
        BaseMetric.__init__(self, name)
        self._session = "Other"

    cdef void update_from_struct(self, TickStruct* tick):
        cdef int idx = tick.hour * 60 + tick.minute
        if idx < 0:
            idx = 0
        elif idx >= 1440:
            idx = 1439
        self._session = SESSION_TABLE[idx]

    cpdef dict value_dict(self):
        return {"session_label": self._session}

    cpdef dict value(self):
        return self.value_dict()

    def update(self, tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)
        self.update_from_struct(&c_tick)
