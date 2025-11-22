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


cdef class MetricsManager:
    cdef list _metrics
    cdef list _key_cache
    cdef list _full_key_cache
    cdef dict _snapshot

    def __cinit__(self, list metrics):
        self._metrics = metrics
        self._key_cache = [()] * len(metrics)
        self._full_key_cache = [()] * len(metrics)
        self._snapshot = {}

    cpdef dict update_all(self, object tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)

        cdef int count = len(self._metrics)
        cdef int i
        cdef dict values
        cdef tuple keys
        cdef tuple full_keys
        cdef object metric_name
        cdef set new_full_keys
        cdef set old_full_keys
        cdef list full_key_buffer
        cdef object key

        for i in range(count):
            py_metric = self._metrics[i]

            if isinstance(py_metric, BaseMetric):
                metric_obj = <BaseMetric>py_metric
                metric_obj.update_from_struct(&c_tick)
                values = metric_obj.value()
                metric_name = metric_obj.name
            else:
                getattr(py_metric, "update")(tick)
                values = py_metric.value()
                metric_name = getattr(py_metric, "name")
            keys = self._key_cache[i]
            full_keys = self._full_key_cache[i]

            needs_refresh = False
            if not keys or len(values) != len(keys):
                needs_refresh = True
            else:
                idx = 0
                for key in values:
                    if key != keys[idx]:
                        needs_refresh = True
                        break
                    idx += 1

            if needs_refresh:
                old_full_keys = set(full_keys)
                keys = tuple(values.keys())
                full_key_buffer = []
                for key in keys:
                    full_key_buffer.append(f"{metric_name}.{key}")
                full_keys = tuple(full_key_buffer)
                self._key_cache[i] = keys
                self._full_key_cache[i] = full_keys
                new_full_keys = set(full_keys)
                for obsolete in old_full_keys.difference(new_full_keys):
                    self._snapshot.pop(obsolete, None)

            for key, full_key in zip(keys, full_keys):
                self._snapshot[full_key] = values.get(key)

        return dict(self._snapshot)

    cpdef dict current(self):
        return dict(self._snapshot)
