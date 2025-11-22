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

from collections import deque
import math
import numpy as np


class PyTimeRollingWindow:
    """Reference Python implementation kept for fallback and testing parity."""

    def __init__(self, lookback_seconds: float):
        self.lookback = float(lookback_seconds)
        self.samples = deque()
        self.sum_w = 0.0
        self.sum_x = 0.0
        self.sum_x2 = 0.0

    def __len__(self) -> int:
        return len(self.samples)

    def __iter__(self):
        return iter(self.samples)

    def append(self, ts: float, value: float, dt: float):
        if not (math.isfinite(ts) and math.isfinite(value) and math.isfinite(dt)):
            return
        if dt <= 0.0:
            dt = 1e-9

        self.samples.append((float(ts), float(value), float(dt)))
        self.sum_w += dt
        self.sum_x += dt * value
        self.sum_x2 += dt * value * value

        self._trim(ts)

    def _trim(self, ts: float):
        cutoff = float(ts) - self.lookback
        eps = 1e-12

        while self.samples:
            old_ts, old_val, old_dt = self.samples[0]
            end = old_ts + old_dt

            if end <= cutoff - eps:
                self.samples.popleft()
                self.sum_w -= old_dt
                self.sum_x -= old_dt * old_val
                self.sum_x2 -= old_dt * old_val * old_val
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

                self.samples[0] = (cutoff, old_val, keep_dt)
                break

            break

        if abs(self.sum_w) < eps:
            self.sum_w = 0.0
            self.sum_x = 0.0
            self.sum_x2 = 0.0
        else:
            if self.sum_w < 0.0 and self.sum_w > -eps:
                self.sum_w = 0.0

    def stats(self):
        if not math.isfinite(self.sum_w) or self.sum_w <= 1e-12:
            return (np.nan, np.nan)

        if not (math.isfinite(self.sum_x) and math.isfinite(self.sum_x2)):
            return (np.nan, np.nan)

        mean = self.sum_x / self.sum_w
        raw = self.sum_x2 / self.sum_w - mean * mean

        if not math.isfinite(raw):
            return (mean, np.nan)

        var = raw if raw > 0.0 else 0.0
        return (mean, float(math.sqrt(var)))
