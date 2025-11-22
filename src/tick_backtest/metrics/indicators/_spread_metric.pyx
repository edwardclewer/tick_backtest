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


cdef class SpreadMetric(BaseMetric):
    cdef double pip_size
    cdef double window
    cdef double _spread
    cdef double _spread_pips
    cdef double _percentile
    cdef object _history  # deque of (timestamp, spread_pips)

    def __init__(
        self,
        *,
        name,
        pip_size,
        window_seconds,
    ):
        BaseMetric.__init__(self, name)

        if not isinstance(pip_size, (float, int)):
            raise TypeError("pip_size must be numeric")
        if pip_size <= 0:
            raise ValueError("pip_size must be positive")
        self.pip_size = float(pip_size)

        if not isinstance(window_seconds, (float, int)):
            raise TypeError("window_seconds must be numeric")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.window = float(window_seconds)

        self._spread = NAN
        self._spread_pips = NAN
        self._percentile = NAN
        self._history = deque()

    cdef void update_from_struct(self, TickStruct* tick):
        cdef double bid = tick.bid
        cdef double ask = tick.ask
        cdef double timestamp = tick.timestamp

        cdef double raw = ask - bid
        if raw < 0.0:
            raw = 0.0
        cdef double spread_pips = raw / self.pip_size

        self._spread = raw
        self._spread_pips = spread_pips

        self._history.append((timestamp, spread_pips))
        cdef double cutoff = timestamp - self.window
        while self._history:
            if self._history[0][0] < cutoff:
                self._history.popleft()
            else:
                break

        cdef Py_ssize_t total = len(self._history)
        if total == 0:
            self._percentile = NAN
            return

        cdef Py_ssize_t count = 0
        for entry in self._history:
            if entry[1] <= spread_pips:
                count += 1
        self._percentile = (<double>count) / (<double>total)

    cpdef dict value_dict(self):
        return {
            "spread": self._spread,
            "spread_pips": self._spread_pips,
            "spread_percentile": self._percentile,
        }

    cpdef dict value(self):
        return self.value_dict()

    def update(self, tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)
        self.update_from_struct(&c_tick)
