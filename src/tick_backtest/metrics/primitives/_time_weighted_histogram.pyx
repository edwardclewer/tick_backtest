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
cimport numpy as cnp
from libc.math cimport fabs

cnp.import_array()

cdef double NAN = float("nan")
cdef double TINY_TOTAL = 1e-9


cdef class TimeWeightedHistogram:
    cdef public object edges
    cdef public double horizon
    cdef public Py_ssize_t n_bins
    cdef public object weights
    cdef public double total

    cdef double[::1] _edges_view
    cdef double[::1] _weights_view

    cdef Py_ssize_t _event_capacity
    cdef Py_ssize_t _event_size
    cdef Py_ssize_t _event_head

    cdef object _event_start_arr
    cdef object _event_end_arr
    cdef object _event_bin_arr
    cdef double[::1] _event_start_view
    cdef double[::1] _event_end_view
    cdef long[::1] _event_bin_view

    def __cinit__(self, cnp.ndarray edges, double horizon_seconds):
        cdef cnp.ndarray[cnp.float64_t, ndim=1] edges_arr = np.asarray(edges, dtype=np.float64)
        if edges_arr.ndim != 1 or edges_arr.shape[0] < 2:
            raise AssertionError("edges must be 1-D with at least two points")

        cdef Py_ssize_t i
        cdef Py_ssize_t count = edges_arr.shape[0]
        cdef double[::1] edges_view = edges_arr
        for i in range(count - 1):
            if edges_view[i + 1] - edges_view[i] <= 0.0:
                raise AssertionError("edges must be strictly increasing")

        if horizon_seconds <= 0.0:
            raise AssertionError("horizon_seconds must be positive")

        self.edges = edges_arr
        self._edges_view = edges_view
        self.horizon = horizon_seconds
        self.n_bins = count - 1

        cdef cnp.ndarray[cnp.float64_t, ndim=1] weights_arr = np.zeros(self.n_bins, dtype=np.float64)
        self.weights = weights_arr
        self._weights_view = weights_arr
        self.total = 0.0

        self._event_capacity = 16
        self._event_size = 0
        self._event_head = 0

        self._event_start_arr = np.empty(self._event_capacity, dtype=np.float64)
        self._event_end_arr = np.empty(self._event_capacity, dtype=np.float64)
        self._event_bin_arr = np.empty(self._event_capacity, dtype=np.int64)
        self._event_start_view = self._event_start_arr
        self._event_end_view = self._event_end_arr
        self._event_bin_view = self._event_bin_arr

    cdef inline Py_ssize_t _bin_index(self, double x) noexcept:
        if x <= self._edges_view[0]:
            return 0
        if x >= self._edges_view[self.n_bins]:
            return self.n_bins - 1

        cdef Py_ssize_t lo = 0
        cdef Py_ssize_t hi = self.n_bins
        cdef Py_ssize_t mid

        while lo < hi:
            mid = (lo + hi) >> 1
            if self._edges_view[mid + 1] <= x:
                lo = mid + 1
            elif self._edges_view[mid] > x:
                hi = mid
            else:
                return mid

        if lo >= self.n_bins:
            return self.n_bins - 1
        return lo

    cdef void _ensure_event_capacity(self, Py_ssize_t min_capacity):
        if self._event_capacity >= min_capacity:
            return

        cdef Py_ssize_t new_capacity = self._event_capacity * 2 if self._event_capacity > 0 else 16
        if new_capacity < min_capacity:
            new_capacity = min_capacity

        cdef cnp.ndarray[cnp.float64_t, ndim=1] new_start = np.empty(new_capacity, dtype=np.float64)
        cdef cnp.ndarray[cnp.float64_t, ndim=1] new_end = np.empty(new_capacity, dtype=np.float64)
        cdef cnp.ndarray[cnp.int64_t, ndim=1] new_bin = np.empty(new_capacity, dtype=np.int64)

        cdef double[::1] new_start_view = new_start
        cdef double[::1] new_end_view = new_end
        cdef long[::1] new_bin_view = new_bin

        cdef Py_ssize_t i, idx
        if self._event_capacity > 0:
            for i in range(self._event_size):
                idx = (self._event_head + i) % self._event_capacity
                new_start_view[i] = self._event_start_view[idx]
                new_end_view[i] = self._event_end_view[idx]
                new_bin_view[i] = self._event_bin_view[idx]

        self._event_start_arr = new_start
        self._event_end_arr = new_end
        self._event_bin_arr = new_bin
        self._event_start_view = new_start_view
        self._event_end_view = new_end_view
        self._event_bin_view = new_bin_view
        self._event_capacity = new_capacity
        self._event_head = 0

    cdef void _append_event(self, double start, double end, Py_ssize_t bin_idx):
        if self._event_size == self._event_capacity:
            self._ensure_event_capacity(self._event_capacity + 1)

        cdef Py_ssize_t tail = (self._event_head + self._event_size) % self._event_capacity
        self._event_start_view[tail] = start
        self._event_end_view[tail] = end
        self._event_bin_view[tail] = bin_idx
        self._event_size += 1

    cpdef void add(self, double start, double end, double value) except *:
        if end <= start:
            return

        cdef Py_ssize_t bin_idx = self._bin_index(value)
        cdef double weight = end - start

        self._weights_view[bin_idx] += weight
        self.total += weight
        self._append_event(start, end, bin_idx)

    cpdef void trim(self, double now) except *:
        if self._event_size == 0:
            return

        cdef double cutoff = now - self.horizon
        cdef Py_ssize_t head = self._event_head
        cdef double start
        cdef double end
        cdef long bin_idx
        cdef double drop

        while self._event_size > 0:
            start = self._event_start_view[head]
            end = self._event_end_view[head]
            bin_idx = self._event_bin_view[head]

            if end <= cutoff:
                drop = end - start
                self._weights_view[bin_idx] -= drop
                self.total -= drop
                head = (head + 1) % self._event_capacity
                self._event_head = head
                self._event_size -= 1
                continue

            if start < cutoff < end:
                drop = cutoff - start
                self._weights_view[bin_idx] -= drop
                self.total -= drop
                self._event_start_view[head] = cutoff
                break

            break

        if self.total < 0.0 and fabs(self.total) < TINY_TOTAL:
            self.total = 0.0

    cpdef double percentile_rank(self, double x):
        if self.total <= 0.0:
            return NAN

        cdef Py_ssize_t bin_idx = self._bin_index(x)
        cdef double below = 0.0
        cdef Py_ssize_t i
        for i in range(bin_idx):
            below += self._weights_view[i]

        cdef double left = self._edges_view[bin_idx]
        cdef double right = self._edges_view[bin_idx + 1]
        cdef double frac = 0.0

        if right > left:
            frac = (x - left) / (right - left)
            if frac < 0.0:
                frac = 0.0
            elif frac > 1.0:
                frac = 1.0

        cdef double in_bin = self._weights_view[bin_idx] * frac
        return (below + in_bin) / self.total
