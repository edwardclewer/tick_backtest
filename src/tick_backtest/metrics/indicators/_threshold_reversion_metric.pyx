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
from libc.math cimport fabs

from tick_backtest.metrics.primitives._base_metric cimport BaseMetric
from tick_backtest.metrics.primitives._tick_types cimport TickStruct
from tick_backtest.metrics.primitives._tick_conversion cimport fill_tick_struct


cdef double NAN = float("nan")


cdef class _MonotonicQueue:
    cdef object times_arr
    cdef object prices_arr
    cdef double[::1] times_view
    cdef double[::1] prices_view
    cdef int capacity
    cdef int size
    cdef int head
    cdef bint is_max

    def __cinit__(self, int initial_capacity, bint is_max):
        self.capacity = 0
        self.size = 0
        self.head = 0
        self.is_max = is_max
        self._ensure_capacity(initial_capacity if initial_capacity > 0 else 16)

    cdef void _ensure_capacity(self, int min_capacity):
        if self.capacity >= min_capacity:
            return

        cdef int new_capacity = self.capacity * 2 if self.capacity > 0 else 16
        if new_capacity < min_capacity:
            new_capacity = min_capacity

        cdef object new_times = np.empty(new_capacity, dtype=np.float64)
        cdef object new_prices = np.empty(new_capacity, dtype=np.float64)
        cdef double[::1] new_times_view = new_times
        cdef double[::1] new_prices_view = new_prices

        cdef int i
        cdef int idx
        if self.capacity > 0:
            for i in range(self.size):
                idx = (self.head + i) % self.capacity
                new_times_view[i] = self.times_view[idx]
                new_prices_view[i] = self.prices_view[idx]

        self.times_arr = new_times
        self.prices_arr = new_prices
        self.times_view = new_times_view
        self.prices_view = new_prices_view
        self.capacity = new_capacity
        self.head = 0

    cdef void append(self, double timestamp, double price):
        cdef int idx

        while self.size > 0:
            idx = (self.head + self.size - 1) % self.capacity
            if self.is_max:
                if self.prices_view[idx] <= price:
                    self.size -= 1
                    continue
            else:
                if self.prices_view[idx] >= price:
                    self.size -= 1
                    continue
            break

        if self.size == self.capacity:
            self._ensure_capacity(self.capacity + 1)

        idx = (self.head + self.size) % self.capacity
        self.prices_view[idx] = price
        self.times_view[idx] = timestamp
        self.size += 1

    cdef void trim(self, double cutoff):
        while self.size > 0:
            if self.times_view[self.head] < cutoff:
                self.head = (self.head + 1) % self.capacity
                self.size -= 1
            else:
                break
        if self.size == 0:
            self.head = 0

    cdef bint find_candidate(
        self,
        double current_price,
        double threshold,
        bint is_low,
        double current_timestamp,
        double min_age,
        double* ts_out,
        double* price_out,
    ):
        if self.size < 2:
            return False

        cdef int idx = (self.head + self.size - 1) % self.capacity
        idx = (idx - 1 + self.capacity) % self.capacity

        cdef int remaining = self.size - 1
        cdef double price
        cdef double diff

        while remaining > 0:
            price = self.prices_view[idx]
            if is_low:
                diff = current_price - price
                if diff >= threshold:
                    if current_timestamp - self.times_view[idx] >= min_age:
                        ts_out[0] = self.times_view[idx]
                        price_out[0] = price
                        return True
            else:
                diff = price - current_price
                if diff >= threshold:
                    if current_timestamp - self.times_view[idx] >= min_age:
                        ts_out[0] = self.times_view[idx]
                        price_out[0] = price
                        return True

            idx = (idx - 1 + self.capacity) % self.capacity
            remaining -= 1

        return False


cdef class ThresholdReversionMetric(BaseMetric):
    cdef int lookback_seconds
    cdef double threshold
    cdef double pip_size
    cdef double tp_distance
    cdef double sl_distance
    cdef double tp_price
    cdef double sl_price
    cdef double min_recency
    cdef double trade_timeout
    cdef _MonotonicQueue max_q
    cdef _MonotonicQueue min_q
    cdef double p_ref
    cdef double p_ref_time
    cdef double position_open_time
    cdef double last_mid
    cdef double last_timestamp
    cdef bint has_ref
    cdef bint has_last
    cdef int position

    def __init__(
        self,
        name: str,
        lookback_seconds: int,
        threshold_pips: float,
        pip_size: float,
        tp_pips: float,
        sl_pips: float,
        min_recency_seconds: float,
        trade_timeout_seconds=None,
    ):
        BaseMetric.__init__(self, name=name)
        self.lookback_seconds = int(lookback_seconds)
        self.threshold = float(threshold_pips * pip_size)
        self.pip_size = float(pip_size)
        self.tp_distance = float(tp_pips * pip_size)
        self.sl_distance = float(sl_pips * pip_size)
        self.min_recency = float(min_recency_seconds)
        if trade_timeout_seconds is None:
            self.trade_timeout = NAN
        else:
            self.trade_timeout = float(trade_timeout_seconds)

        self.max_q = _MonotonicQueue(64, True)
        self.min_q = _MonotonicQueue(64, False)

        self.p_ref = NAN
        self.p_ref_time = NAN
        self.position_open_time = NAN
        self.tp_price = NAN
        self.sl_price = NAN
        self.last_mid = NAN
        self.last_timestamp = NAN
        self.has_ref = False
        self.has_last = False
        self.position = 0

    cdef void update_from_struct(self, TickStruct* tick):
        cdef double mid = tick.mid
        cdef double timestamp = tick.timestamp

        self._append_tick(timestamp, mid)
        self.last_mid = mid
        self.last_timestamp = timestamp
        self.has_last = True

        cdef double ref_time
        cdef double ref_price
        cdef bint has_ref_candidate = self._find_reference(mid, timestamp, &ref_time, &ref_price)

        if self.position != 0 and self.has_ref:
            if fabs(mid - self.p_ref) <= self.pip_size:
                self._flatten()
                has_ref_candidate = self._find_reference(mid, timestamp, &ref_time, &ref_price)

        if not has_ref_candidate:
            self._flatten()
            return

        if self.has_ref and fabs(ref_price - self.p_ref) > self.pip_size / 10.0:
            self._flatten()

        if self.position == 0:
            self._maybe_open(ref_price, ref_time, mid, timestamp)

    cdef void _append_tick(self, double timestamp, double mid):
        cdef double cutoff = timestamp - self.lookback_seconds
        self.max_q.append(timestamp, mid)
        self.min_q.append(timestamp, mid)
        self.max_q.trim(cutoff)
        self.min_q.trim(cutoff)

    cdef bint _find_reference(self, double current_price, double current_time, double* out_time, double* out_price):
        cdef double low_time
        cdef double low_price
        cdef double high_time
        cdef double high_price
        cdef bint has_low = self.min_q.find_candidate(
            current_price,
            self.threshold,
            True,
            current_time,
            self.min_recency,
            &low_time,
            &low_price,
        )
        cdef bint has_high = self.max_q.find_candidate(
            current_price,
            self.threshold,
            False,
            current_time,
            self.min_recency,
            &high_time,
            &high_price,
        )

        if has_low and has_high:
            if low_time >= high_time:
                out_time[0] = low_time
                out_price[0] = low_price
            else:
                out_time[0] = high_time
                out_price[0] = high_price
            return True
        elif has_low:
            out_time[0] = low_time
            out_price[0] = low_price
            return True
        elif has_high:
            out_time[0] = high_time
            out_price[0] = high_price
            return True
        else:
            return False

    cdef void _maybe_open(self, double ref_price, double ref_time, double current_price, double now):
        cdef double distance = current_price - ref_price
        if distance >= self.threshold:
            self._set_reference(ref_price, ref_time)
            self.position = -1
            self.position_open_time = now
            self._set_trade_levels(current_price, -1)
        elif distance <= -self.threshold:
            self._set_reference(ref_price, ref_time)
            self.position = 1
            self.position_open_time = now
            self._set_trade_levels(current_price, 1)

    cdef void _flatten(self):
        self.position = 0
        self.has_ref = False
        self.p_ref = NAN
        self.p_ref_time = NAN
        self.position_open_time = NAN
        self.tp_price = NAN
        self.sl_price = NAN

    cdef void _set_reference(self, double price, double timestamp):
        self.p_ref = price
        self.p_ref_time = timestamp
        self.has_ref = True

    cdef void _set_trade_levels(self, double current_price, int direction):
        if direction == -1:
            self.tp_price = current_price - self.tp_distance
            self.sl_price = current_price + self.sl_distance
        else:
            self.tp_price = current_price + self.tp_distance
            self.sl_price = current_price - self.sl_distance

    cpdef dict value_dict(self):
        cdef double ref_price = self.p_ref if self.has_ref else NAN
        cdef double ref_age
        if self.has_ref and self.has_last and self.p_ref_time == self.p_ref_time:
            ref_age = self.last_timestamp - self.p_ref_time
        else:
            ref_age = NAN

        cdef double distance
        if self.has_ref and self.has_last:
            distance = self.last_mid - ref_price
        else:
            distance = NAN

        cdef double open_age
        if self.position != 0 and self.has_last and self.position_open_time == self.position_open_time:
            open_age = self.last_timestamp - self.position_open_time
        else:
            open_age = NAN

        return {
            "position": float(self.position),
            "reference_price": ref_price,
            "distance_from_reference": distance,
            "reference_age_seconds": ref_age,
            "threshold": self.threshold,
            "tp_price": self.tp_price,
            "sl_price": self.sl_price,
            "trade_timeout_seconds": self.trade_timeout,
            "position_open_age_seconds": open_age,
            "min_recency_seconds": self.min_recency,
        }

    cpdef dict value(self):
        return self.value_dict()

    def update(self, tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)
        self.update_from_struct(&c_tick)
