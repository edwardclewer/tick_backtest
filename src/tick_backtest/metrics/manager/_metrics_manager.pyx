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

import numpy as np

from tick_backtest.metrics.primitives._base_metric cimport BaseMetric
from tick_backtest.metrics.primitives._tick_types cimport TickStruct
from tick_backtest.metrics.primitives._tick_conversion cimport fill_tick_struct


cdef class MetricSnapshotView:
    cdef dict _key_to_slot
    cdef object _values_arr
    cdef object _valid_arr
    cdef double[::1] _values
    cdef unsigned char[::1] _valid

    def __cinit__(self, dict key_to_slot, object values_arr, object valid_arr):
        self._key_to_slot = key_to_slot
        self._values_arr = values_arr
        self._valid_arr = valid_arr
        self._values = values_arr
        self._valid = valid_arr

    cpdef object get(self, object key, object default=None):
        cdef object slot_obj = self._key_to_slot.get(key)
        cdef Py_ssize_t slot
        if slot_obj is None:
            return default
        slot = <Py_ssize_t>slot_obj
        if slot < 0 or slot >= self._valid.shape[0] or self._valid[slot] == 0:
            return default
        return self._values[slot]

    def __getitem__(self, object key):
        cdef object value = self.get(key, None)
        if value is None:
            raise KeyError(key)
        return value

    def __contains__(self, object key):
        cdef object slot_obj = self._key_to_slot.get(key)
        cdef Py_ssize_t slot
        if slot_obj is None:
            return False
        slot = <Py_ssize_t>slot_obj
        return 0 <= slot < self._valid.shape[0] and self._valid[slot] != 0

    def to_dict(self):
        cdef dict out = {}
        cdef object key
        cdef object slot_obj
        cdef Py_ssize_t slot
        for key, slot_obj in self._key_to_slot.items():
            slot = <Py_ssize_t>slot_obj
            if 0 <= slot < self._valid.shape[0] and self._valid[slot] != 0:
                out[key] = self._values[slot]
        return out

    def keys(self):
        return self._key_to_slot.keys()


cdef class MetricsManager:
    cdef list _metrics
    cdef list _key_cache
    cdef list _full_key_cache
    cdef dict _snapshot
    cdef list _slot_cache
    cdef object _slot_values_arr
    cdef object _slot_valid_arr
    cdef double[::1] _slot_values
    cdef unsigned char[::1] _slot_valid
    cdef dict _slot_key_to_index
    cdef object _slot_view
    cdef bint _slots_configured

    def __cinit__(self, list metrics):
        self._metrics = metrics
        self._key_cache = [()] * len(metrics)
        self._full_key_cache = [()] * len(metrics)
        self._snapshot = {}
        self._slot_cache = [()] * len(metrics)
        self._slot_values_arr = None
        self._slot_valid_arr = None
        self._slot_key_to_index = {}
        self._slot_view = None
        self._slots_configured = False

    cdef void _update_snapshot(self, object tick):
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

    cpdef dict update_all(self, object tick):
        self._update_snapshot(tick)
        return dict(self._snapshot)

    cpdef dict update_selected(self, object tick, tuple selected_keys):
        self._update_snapshot(tick)
        cdef dict selected = {}
        cdef object key
        for key in selected_keys:
            selected[key] = self._snapshot.get(key)
        return selected

    cpdef dict current(self):
        return dict(self._snapshot)

    cpdef object configure_slots(self, list metric_slots, dict key_to_slot):
        cdef Py_ssize_t slot_count = 0
        cdef object slot
        cdef tuple slots
        for slots in metric_slots:
            for slot in slots:
                if <Py_ssize_t>slot + 1 > slot_count:
                    slot_count = <Py_ssize_t>slot + 1
        for slot in key_to_slot.values():
            if <Py_ssize_t>slot + 1 > slot_count:
                slot_count = <Py_ssize_t>slot + 1

        self._slot_cache = metric_slots
        self._slot_key_to_index = key_to_slot
        self._slot_values_arr = np.zeros(slot_count, dtype=np.float64)
        self._slot_valid_arr = np.zeros(slot_count, dtype=np.uint8)
        self._slot_values = self._slot_values_arr
        self._slot_valid = self._slot_valid_arr
        self._slot_view = MetricSnapshotView(key_to_slot, self._slot_values_arr, self._slot_valid_arr)
        self._slots_configured = True
        return self._slot_view

    cpdef object update_slots(self, object tick):
        if not self._slots_configured:
            raise RuntimeError("metric slots have not been configured")

        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)

        cdef int count = len(self._metrics)
        cdef int i
        cdef object py_metric
        cdef BaseMetric metric_obj
        cdef tuple slots

        for i in range(count):
            py_metric = self._metrics[i]
            slots = self._slot_cache[i]
            if isinstance(py_metric, BaseMetric):
                metric_obj = <BaseMetric>py_metric
                metric_obj.update_from_struct(&c_tick)
                metric_obj.write_values_to_slots(self._slot_values, self._slot_valid, slots)
            else:
                getattr(py_metric, "update")(tick)
                self._write_python_metric_slots(py_metric, slots)
        return self._slot_view

    cdef void _write_python_metric_slots(self, object metric, tuple slots):
        cdef dict values = metric.value()
        cdef tuple keys = tuple(values.keys())
        cdef Py_ssize_t i
        cdef Py_ssize_t limit = min(len(keys), len(slots))
        cdef object raw
        cdef Py_ssize_t slot
        for i in range(limit):
            slot = <Py_ssize_t>slots[i]
            raw = values.get(keys[i])
            if raw is None:
                self._slot_values[slot] = 0.0
                self._slot_valid[slot] = 0
            else:
                try:
                    self._slot_values[slot] = float(raw)
                    self._slot_valid[slot] = 1
                except (TypeError, ValueError):
                    self._slot_values[slot] = 0.0
                    self._slot_valid[slot] = 0

    cpdef object current_view(self):
        if not self._slots_configured:
            raise RuntimeError("metric slots have not been configured")
        return self._slot_view
