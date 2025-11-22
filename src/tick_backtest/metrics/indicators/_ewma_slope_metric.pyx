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

from tick_backtest.metrics.primitives._base_metric cimport BaseMetric
from tick_backtest.metrics.primitives._tick_types cimport TickStruct
from tick_backtest.metrics.primitives._tick_conversion cimport fill_tick_struct

cdef double MIN_DT = 1e-6
cdef double NAN = float("nan")


cdef inline double _select_price(TickStruct* tick, int field):
    if field == 0:
        return tick.mid
    elif field == 1:
        return tick.bid
    else:
        return tick.ask


cdef class EWMASlopeMetric(BaseMetric):
    cdef double tau
    cdef double window
    cdef int _price_field
    cdef double _value
    cdef double _slope
    cdef double _last_ts
    cdef bint _has_value
    cdef list _history

    def __init__(
        self,
        *,
        name,
        tau_seconds,
        window_seconds,
        initial_value=None,
        price_field="mid",
    ):
        BaseMetric.__init__(self, name)

        if not isinstance(tau_seconds, (float, int)):
            raise TypeError("tau_seconds must be numeric")
        if tau_seconds <= 0:
            raise ValueError("tau_seconds must be positive")
        self.tau = float(tau_seconds)

        if not isinstance(window_seconds, (float, int)):
            raise TypeError("window_seconds must be numeric")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.window = float(window_seconds)

        if not isinstance(price_field, str):
            raise TypeError("price_field must be a string")
        pf = price_field.lower()
        if pf == "mid":
            self._price_field = 0
        elif pf == "bid":
            self._price_field = 1
        elif pf == "ask":
            self._price_field = 2
        else:
            raise ValueError(f"Unsupported price_field '{price_field}'")

        if initial_value is None:
            self._value = NAN
            self._has_value = False
        else:
            if not isinstance(initial_value, (float, int)):
                raise TypeError("initial_value must be numeric")
            self._value = float(initial_value)
            self._has_value = True

        self._slope = NAN
        self._last_ts = 0.0
        self._history = []

    cdef void update_from_struct(self, TickStruct* tick):
        cdef double timestamp = tick.timestamp
        cdef double price = _select_price(tick, self._price_field)

        if not self._has_value:
            self._value = price
            self._last_ts = timestamp
            self._has_value = True
            self._history.append((timestamp, self._value))
            self._slope = NAN
            return

        cdef double dt = timestamp - self._last_ts
        if dt < MIN_DT:
            dt = MIN_DT

        cdef double alpha = 1.0 - exp(-dt / self.tau)
        self._value = (1.0 - alpha) * self._value + alpha * price
        self._last_ts = timestamp

        self._history.append((timestamp, self._value))
        cdef double cutoff = timestamp - self.window
        while len(self._history) > 1:
            if self._history[0][0] < cutoff:
                self._history.pop(0)
            else:
                break

        if len(self._history) < 2:
            self._slope = NAN
            return

        cdef double oldest_t = self._history[0][0]
        cdef double oldest_v = self._history[0][1]
        dt = timestamp - oldest_t
        if dt < MIN_DT:
            dt = MIN_DT
        self._slope = (self._value - oldest_v) / dt

    cpdef dict value_dict(self):
        return {"ewma": self._value, "slope": self._slope}

    cpdef dict value(self):
        return self.value_dict()

    def update(self, tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)
        self.update_from_struct(&c_tick)
