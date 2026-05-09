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

import numpy as np
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
    cdef object _history
    cdef object _counts_arr
    cdef long[::1] _counts_view
    cdef object _edges_arr
    cdef double[::1] _edges_view
    cdef Py_ssize_t _n_bins

    def __init__(
        self,
        *,
        name,
        pip_size,
        window_seconds,
        percentile_bins=512,
        max_spread_pips=50.0,
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
        if not isinstance(percentile_bins, int) or percentile_bins < 2:
            raise ValueError("percentile_bins must be an integer >= 2")
        if not isinstance(max_spread_pips, (float, int)) or max_spread_pips <= 0:
            raise ValueError("max_spread_pips must be positive")

        self._spread = NAN
        self._spread_pips = NAN
        self._percentile = NAN
        self._edges_arr = np.linspace(0.0, float(max_spread_pips), percentile_bins + 1, dtype=np.float64)
        self._edges_view = self._edges_arr
        self._n_bins = percentile_bins
        self._counts_arr = np.zeros(percentile_bins, dtype=np.int64)
        self._counts_view = self._counts_arr
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

        cdef Py_ssize_t bin_idx = self._bin_index(spread_pips)
        self._history.append((timestamp, bin_idx))
        self._counts_view[bin_idx] += 1

        cdef double cutoff = timestamp - self.window
        cdef object old
        while self._history:
            old = self._history[0]
            if old[0] < cutoff:
                self._history.popleft()
                self._counts_view[<Py_ssize_t>old[1]] -= 1
            else:
                break

        self._percentile = self._percentile_rank_le(bin_idx)

    cdef Py_ssize_t _bin_index(self, double spread_pips):
        cdef Py_ssize_t lo = 0
        cdef Py_ssize_t hi = self._n_bins
        cdef Py_ssize_t mid
        if spread_pips <= self._edges_view[0]:
            return 0
        if spread_pips >= self._edges_view[self._n_bins]:
            return self._n_bins - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if spread_pips < self._edges_view[mid + 1]:
                hi = mid
            else:
                lo = mid + 1
        return lo

    cdef double _percentile_rank_le(self, Py_ssize_t bin_idx):
        cdef Py_ssize_t total = len(self._history)
        if total <= 0:
            return NAN

        cdef Py_ssize_t i
        cdef Py_ssize_t cumulative = 0
        for i in range(bin_idx + 1):
            cumulative += self._counts_view[i]
        return (<double>cumulative) / (<double>total)

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
