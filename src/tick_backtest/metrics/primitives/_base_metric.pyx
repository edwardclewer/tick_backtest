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

    cdef void update_from_struct(self, TickStruct* tick):
        raise NotImplementedError()

    def update(self, tick):  # pragma: no cover - abstract placeholder
        raise NotImplementedError()
