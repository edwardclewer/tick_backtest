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

from libc.math cimport isfinite

from tick_backtest.metrics.primitives._base_metric cimport BaseMetric
from tick_backtest.metrics.primitives.time_rolling_window import TimeRollingWindow
from tick_backtest.metrics.primitives._tick_types cimport TickStruct
from tick_backtest.metrics.primitives._tick_conversion cimport fill_tick_struct

cdef double NAN = float("nan")


cdef class ZScoreMetric(BaseMetric):
    cdef object window
    cdef double _z
    cdef double _resid
    cdef double _last_ts
    cdef bint _has_last

    def __init__(self, name, lookback_seconds):
        BaseMetric.__init__(self, name)
        if not isinstance(lookback_seconds, (float, int)):
            raise TypeError("lookback_seconds must be numeric")
        if lookback_seconds <= 0:
            raise ValueError("lookback_seconds must be positive")

        self.window = TimeRollingWindow(lookback_seconds)
        self._z = NAN
        self._resid = NAN
        self._last_ts = 0.0
        self._has_last = False

    cdef void update_from_struct(self, TickStruct* tick):
        cdef double t = tick.timestamp
        cdef double mid = tick.mid
        cdef double dt

        if self._has_last:
            dt = t - self._last_ts
            if dt < 1e-6:
                dt = 1e-6
        else:
            dt = 0.0
            self._has_last = True

        self.window.append(t, mid, dt)

        cdef double mean
        cdef double std
        cdef object mean_std = self.window.stats()
        mean = mean_std[0]
        std = mean_std[1]

        if not isfinite(mean):
            self._resid = NAN
        else:
            self._resid = mid - mean

        if (not isfinite(std)) or std <= 1e-12:
            self._z = 0.0
        else:
            self._z = (mid - mean) / std

        self._last_ts = t

    cpdef dict value_dict(self):
        cdef dict out = {}
        out["z_score"] = self._z
        out["rolling_residual"] = self._resid
        return out

    cpdef dict value(self):
        return self.value_dict()

    def update(self, tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)
        self.update_from_struct(&c_tick)
