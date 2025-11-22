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
from libc.math cimport fabs, sqrt, isfinite

cnp.import_array()

cdef double EPS = 1e-12
cdef double MIN_DT = 1e-9
cdef double NAN = float("nan")


cdef class TimeRollingWindow:
    cdef double lookback
    cdef int capacity
    cdef int size
    cdef int head
    cdef object ts_arr
    cdef object val_arr
    cdef object dt_arr
    cdef double[::1] ts_view
    cdef double[::1] val_view
    cdef double[::1] dt_view
    cdef double sum_w
    cdef double sum_x
    cdef double sum_x2

    def __cinit__(self, lookback_seconds):
        self.lookback = float(lookback_seconds)
        self.capacity = 0
        self.size = 0
        self.head = 0
        self.sum_w = 0.0
        self.sum_x = 0.0
        self.sum_x2 = 0.0
        self._ensure_capacity(16)

    def __len__(self):
        return self.size

    def __iter__(self):
        cdef int i
        cdef int idx
        for i in range(self.size):
            idx = (self.head + i) % self.capacity
            yield (
                self.ts_view[idx],
                self.val_view[idx],
                self.dt_view[idx],
            )

    cpdef void append(self, double ts, double value, double dt) except *:
        if not (isfinite(ts) and isfinite(value) and isfinite(dt)):
            return
        if dt <= 0.0:
            dt = MIN_DT

        if self.size == self.capacity:
            self._ensure_capacity(self.capacity + 1)

        cdef int tail = (self.head + self.size) % self.capacity
        self.ts_view[tail] = ts
        self.val_view[tail] = value
        self.dt_view[tail] = dt
        self.size += 1

        self.sum_w += dt
        self.sum_x += dt * value
        self.sum_x2 += dt * value * value

        self._trim(ts)

    cdef void _trim(self, double ts):
        cdef double cutoff = ts - self.lookback
        cdef double end
        cdef double old_ts
        cdef double old_val
        cdef double old_dt
        cdef double drop_dt
        cdef double keep_dt

        if self.size == 0:
            return

        while self.size > 0:
            old_ts = self.ts_view[self.head]
            old_val = self.val_view[self.head]
            old_dt = self.dt_view[self.head]
            end = old_ts + old_dt

            if end <= cutoff - EPS:
                self.sum_w -= old_dt
                self.sum_x -= old_dt * old_val
                self.sum_x2 -= old_dt * old_val * old_val
                self.head = (self.head + 1) % self.capacity
                self.size -= 1
                continue

            if old_ts < cutoff < end:
                drop_dt = cutoff - old_ts
                keep_dt = old_dt - drop_dt
                if keep_dt < 0.0:
                    keep_dt = 0.0
                    drop_dt = old_dt

                self.sum_w -= drop_dt
                self.sum_x -= drop_dt * old_val
                self.sum_x2 -= drop_dt * old_val * old_val

                self.ts_view[self.head] = cutoff
                self.dt_view[self.head] = keep_dt
                break

            break

        if fabs(self.sum_w) < EPS:
            self.sum_w = 0.0
            self.sum_x = 0.0
            self.sum_x2 = 0.0
        elif self.sum_w < 0.0 and self.sum_w > -EPS:
            self.sum_w = 0.0

    cpdef tuple stats(self):
        if (not isfinite(self.sum_w)) or self.sum_w <= 1e-12:
            return (NAN, NAN)

        if (not isfinite(self.sum_x)) or (not isfinite(self.sum_x2)):
            return (NAN, NAN)

        cdef double mean = self.sum_x / self.sum_w
        cdef double raw = self.sum_x2 / self.sum_w - mean * mean

        if not isfinite(raw):
            return (mean, NAN)

        cdef double var = raw if raw > 0.0 else 0.0
        return (mean, sqrt(var))

    cdef void _ensure_capacity(self, int min_capacity):
        cdef int new_capacity
        cdef int i
        cdef int idx

        if self.capacity >= min_capacity:
            return

        new_capacity = self.capacity * 2 if self.capacity > 0 else 16
        if new_capacity < min_capacity:
            new_capacity = min_capacity

        cdef cnp.ndarray[cnp.float64_t, ndim=1] new_ts = np.empty(new_capacity, dtype=np.float64)
        cdef cnp.ndarray[cnp.float64_t, ndim=1] new_val = np.empty(new_capacity, dtype=np.float64)
        cdef cnp.ndarray[cnp.float64_t, ndim=1] new_dt = np.empty(new_capacity, dtype=np.float64)

        cdef double[::1] new_ts_view = new_ts
        cdef double[::1] new_val_view = new_val
        cdef double[::1] new_dt_view = new_dt

        if self.capacity > 0:
            for i in range(self.size):
                idx = (self.head + i) % self.capacity
                new_ts_view[i] = self.ts_view[idx]
                new_val_view[i] = self.val_view[idx]
                new_dt_view[i] = self.dt_view[idx]

        self.ts_arr = new_ts
        self.val_arr = new_val
        self.dt_arr = new_dt
        self.ts_view = new_ts_view
        self.val_view = new_val_view
        self.dt_view = new_dt_view
        self.capacity = new_capacity
        self.head = 0
