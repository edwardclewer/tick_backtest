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


cdef class BaseMetric:
    def __cinit__(self):
        self.name = None

    def __init__(self, name):
        self.name = name

    cpdef dict value(self):
        raise NotImplementedError()

    cpdef tuple field_names(self):
        return tuple(self.value().keys())

    cpdef void write_values_to_slots(self, double[::1] values, unsigned char[::1] valid, tuple slots):
        cdef dict snapshot = self.value()
        cdef tuple fields = tuple(snapshot.keys())
        cdef Py_ssize_t i
        cdef Py_ssize_t limit = min(len(fields), len(slots))
        cdef object raw
        cdef Py_ssize_t slot
        for i in range(limit):
            slot = <Py_ssize_t>slots[i]
            raw = snapshot.get(fields[i])
            if raw is None:
                values[slot] = 0.0
                valid[slot] = 0
            else:
                try:
                    values[slot] = float(raw)
                    valid[slot] = 1
                except (TypeError, ValueError):
                    values[slot] = 0.0
                    valid[slot] = 0

    cdef void update_from_struct(self, TickStruct* tick):
        raise NotImplementedError()

    def update(self, tick):  # pragma: no cover - abstract placeholder
        raise NotImplementedError()
