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

from dataclasses import dataclass
import math
import warnings
import numpy as np
from ..config_dataclass import MetricConfigBase


@dataclass(kw_only=True)
class EWMAVolConfig(MetricConfigBase):
    enabled: bool
    tau_seconds: float
    percentile_horizon_seconds: float
    bins: int
    base_vol: float  # e.g., 1e-4 typical std of returns
    stddev_cap: float = 5.0  # how many σ to cover

    def __post_init__(self):
        # --- enabled ---
        if not isinstance(self.enabled, bool):
            raise TypeError(f"'enabled' must be a bool, got {type(self.enabled).__name__}")

        # --- tau_seconds ---
        if isinstance(self.tau_seconds, bool):
            raise TypeError("'tau_seconds' must be numeric, not bool")
        if not isinstance(self.tau_seconds, (int, float)):
            raise TypeError(f"'tau_seconds' must be numeric, got {type(self.tau_seconds).__name__}")
        if not math.isfinite(self.tau_seconds) or self.tau_seconds <= 0:
            raise ValueError(f"'tau_seconds' must be positive and finite, got {self.tau_seconds}")
        self.tau_seconds = float(self.tau_seconds)

        # --- percentile_horizon_seconds ---
        if isinstance(self.percentile_horizon_seconds, bool):
            raise TypeError("'percentile_horizon_seconds' must be numeric, not bool")
        if not isinstance(self.percentile_horizon_seconds, (int, float)):
            raise TypeError(f"'percentile_horizon_seconds' must be numeric, got {type(self.percentile_horizon_seconds).__name__}")
        if not math.isfinite(self.percentile_horizon_seconds) or self.percentile_horizon_seconds <= 0:
            raise ValueError(f"'percentile_horizon_seconds' must be positive and finite, got {self.percentile_horizon_seconds}")
        self.percentile_horizon_seconds = float(self.percentile_horizon_seconds)

        # --- bins ---
        if isinstance(self.bins, bool):
            raise TypeError("'bins' must be an integer count, not bool")
        if isinstance(self.bins, float):
            if not self.bins.is_integer():
                raise ValueError(f"'bins' must be an integer, got {self.bins}")
            self.bins = int(self.bins)
        if not isinstance(self.bins, int):
            raise TypeError(f"'bins' must be an int, got {type(self.bins).__name__}")
        if not (2 <= self.bins <= 10_000):
            raise ValueError(f"'bins' must be between 2 and 10_000, got {self.bins}")

        # --- base_vol ---
        if isinstance(self.base_vol, bool):
            raise TypeError("'base_vol' must be numeric, not bool")
        if not isinstance(self.base_vol, (int, float)):
            raise TypeError(f"'base_vol' must be numeric, got {type(self.base_vol).__name__}")
        if not math.isfinite(self.base_vol) or self.base_vol <= 0:
            raise ValueError(f"'base_vol' must be positive and finite, got {self.base_vol}")
        self.base_vol = float(self.base_vol)

        # --- stddev_cap ---
        if isinstance(self.stddev_cap, bool):
            raise TypeError("'stddev_cap' must be numeric, not bool")
        if not isinstance(self.stddev_cap, (int, float)):
            raise TypeError(f"'stddev_cap' must be numeric, got {type(self.stddev_cap).__name__}")
        if not math.isfinite(self.stddev_cap) or self.stddev_cap <= 0:
            raise ValueError(f"'stddev_cap' must be positive and finite, got {self.stddev_cap}")
        self.stddev_cap = float(self.stddev_cap)

        # --- derived variance range ---
        self.var_min = 0.0
        self.var_max = (self.stddev_cap * self.base_vol) ** 2

        if self.var_max / (self.base_vol**2) > 1e4:
            warnings.warn(
                f"EWMAVolConfig variance range very wide (var_max={self.var_max:.2e}); "
                "check base_vol/stddev_cap settings."
            )

    @property
    def edges(self) -> np.ndarray:
        """Return variance bin edges as a numpy array."""
        return np.linspace(self.var_min, self.var_max, self.bins + 1)
