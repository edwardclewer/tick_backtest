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

import math
from typing import Optional


class PyEWMA:
    """Reference Python EWMA retained for fallback and testing parity."""

    def __init__(self, tau_seconds: float, power: int = 1):
        assert tau_seconds > 0.0
        assert power in (1, 2)
        self.tau = float(tau_seconds)
        self.power = int(power)
        self.y = 0.0
        self._last_t: Optional[float] = None

    def reset(self) -> None:
        self.y = 0.0
        self._last_t = None

    def update(self, t: float, x: float) -> float:
        if self._last_t is None:
            self._last_t = float(t)
            return self.y

        dt = max(1e-9, float(t) - self._last_t)
        decay = math.exp(-dt / self.tau)
        if self.power == 2:
            x = x * x
        self.y = decay * self.y + (1.0 - decay) * x
        self._last_t = float(t)
        return self.y
