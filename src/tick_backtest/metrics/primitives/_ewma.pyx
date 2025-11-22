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

from libc.math cimport exp

cdef double MIN_DT = 1e-9


cdef class EWMA:
    cdef public double tau
    cdef public int power
    cdef public double y
    cdef double _last_t
    cdef bint _has_last

    def __cinit__(self, double tau_seconds, int power=1):
        if tau_seconds <= 0.0:
            raise AssertionError("tau_seconds must be positive")
        if power not in (1, 2):
            raise AssertionError("power must be 1 or 2")
        self.tau = tau_seconds
        self.power = power
        self.y = 0.0
        self._last_t = 0.0
        self._has_last = False

    cpdef void reset(self):
        self.y = 0.0
        self._last_t = 0.0
        self._has_last = False

    cpdef double update(self, double t, double x):
        if not self._has_last:
            self._last_t = t
            self._has_last = True
            return self.y

        cdef double dt = t - self._last_t
        if dt <= MIN_DT:
            dt = MIN_DT

        cdef double decay = exp(-dt / self.tau)
        cdef double value = x
        if self.power == 2:
            value = x * x

        self.y = decay * self.y + (1.0 - decay) * value
        self._last_t = t
        return self.y
