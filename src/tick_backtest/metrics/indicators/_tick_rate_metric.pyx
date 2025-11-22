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

# cython: boundscheck=False, wraparound=False, cdivision=True, language_level=3

from collections import deque

from tick_backtest.metrics.primitives._base_metric cimport BaseMetric
from tick_backtest.metrics.primitives._tick_types cimport TickStruct
from tick_backtest.metrics.primitives._tick_conversion cimport fill_tick_struct

cdef double NAN = float("nan")


cdef class TickRateMetric(BaseMetric):
    cdef double window
    cdef object _timestamps  # deque of timestamps
    cdef Py_ssize_t _count

    def __init__(self, *, name, window_seconds):
        BaseMetric.__init__(self, name)

        if not isinstance(window_seconds, (float, int)):
            raise TypeError("window_seconds must be numeric")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.window = float(window_seconds)
        self._timestamps = deque()
        self._count = 0

    cdef void update_from_struct(self, TickStruct* tick):
        cdef double timestamp = tick.timestamp
        self._timestamps.append(timestamp)
        cdef double cutoff = timestamp - self.window

        while self._timestamps:
            if self._timestamps[0] <= cutoff:
                self._timestamps.popleft()
            else:
                break

        self._count = len(self._timestamps)

    cpdef dict value_dict(self):
        if self.window <= 0:
            return {
                "tick_count": float(self._count),
                "tick_rate_per_sec": NAN,
                "tick_rate_per_min": NAN,
            }

        cdef double rate_per_sec = self._count / self.window
        cdef double rate_per_min = rate_per_sec * 60.0
        return {
            "tick_count": float(self._count),
            "tick_rate_per_sec": rate_per_sec,
            "tick_rate_per_min": rate_per_min,
        }

    cpdef dict value(self):
        return self.value_dict()

    def update(self, tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)
        self.update_from_struct(&c_tick)
