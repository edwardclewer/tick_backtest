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
from libc.math cimport log

from tick_backtest.metrics.primitives._base_metric cimport BaseMetric
from tick_backtest.metrics.primitives.ewma import EWMA
from tick_backtest.metrics.primitives.time_weighted_histogram import TimeWeightedHistogram
from tick_backtest.metrics.primitives._tick_types cimport TickStruct
from tick_backtest.metrics.primitives._tick_conversion cimport fill_tick_struct


cdef inline double _safe_logret(double curr, double prev):
    if curr > 0.0 and prev > 0.0:
        return log(curr / prev)
    return 0.0


cdef class EWMAVolMetric(BaseMetric):
    cdef double tau
    cdef double horizon
    cdef object smoother
    cdef object hist
    cdef double _last_t
    cdef double _last_mid
    cdef bint _has_last
    cdef double _ewma
    cdef double _pct

    def __init__(self, name: str, tau_seconds: float = 1800.0, percentile_horizon_seconds: float = 1800.0,
                  bins: int = 256, base_vol: float = 1e-4, stddev_cap: float = 5.0):
        BaseMetric.__init__(self, name)

        if not isinstance(tau_seconds, (int, float)) or tau_seconds <= 0:
            raise ValueError(f"tau_seconds must be positive, got {tau_seconds}")
        if not isinstance(percentile_horizon_seconds, (int, float)) or percentile_horizon_seconds <= 0:
            raise ValueError(f"percentile_horizon_seconds must be positive, got {percentile_horizon_seconds}")
        if not isinstance(bins, int) or bins < 2:
            raise ValueError(f"bins must be an integer >= 2, got {bins}")
        if not isinstance(base_vol, (float, int)) or base_vol <= 0:
            raise ValueError(f"base_vol must be positive, got {base_vol}")
        if not isinstance(stddev_cap, (float, int)) or stddev_cap <= 0:
            raise ValueError(f"stddev_cap must be positive, got {stddev_cap}")

        var_min = 0.0
        var_max = (stddev_cap * base_vol) ** 2
        edges = np.linspace(var_min, var_max, bins + 1, dtype=np.float64)

        self.tau = float(tau_seconds)
        self.horizon = float(percentile_horizon_seconds)
        self.smoother = EWMA(self.tau, power=2)
        self.hist = TimeWeightedHistogram(edges, self.horizon)

        self._last_t = 0.0
        self._last_mid = 0.0
        self._has_last = False
        self._ewma = 0.0
        self._pct = float("nan")

    cdef void update_from_struct(self, TickStruct* tick):
        cdef double t = tick.timestamp
        cdef double mid = tick.mid

        if not self._has_last:
            self._last_t = t
            self._last_mid = mid
            self._has_last = True
            return

        cdef double dt = t - self._last_t
        if dt < 1e-6:
            dt = 1e-6

        cdef double ret = _safe_logret(mid, self._last_mid)
        self._ewma = self.smoother.update(t, ret)

        self.hist.add(t - dt, t, self._ewma)
        self.hist.trim(t)
        self._pct = self.hist.percentile_rank(self._ewma)

        self._last_t = t
        self._last_mid = mid
        self._has_last = True

    cpdef dict value_dict(self):
        return {
            "vol_ewma": self._ewma,
            "vol_percentile": self._pct,
        }

    cpdef dict value(self):
        return self.value_dict()

    def update(self, tick):
        cdef TickStruct c_tick
        fill_tick_struct(tick, &c_tick)
        self.update_from_struct(&c_tick)
