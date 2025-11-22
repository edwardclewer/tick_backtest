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

from ..config_dataclass import MetricConfigBase


@dataclass(kw_only=True)
class SpreadConfig(MetricConfigBase):
    """Configuration for spread and percentile metric."""

    enabled: bool
    pip_size: float
    window_seconds: float

    def __post_init__(self) -> None:
        # --- enabled ---
        if not isinstance(self.enabled, bool):
            raise TypeError(f"'enabled' must be a bool, got {type(self.enabled).__name__}")

        # --- pip_size ---
        if isinstance(self.pip_size, bool):
            raise TypeError("'pip_size' must be numeric, not bool")
        if not isinstance(self.pip_size, (int, float)):
            raise TypeError(f"'pip_size' must be numeric, got {type(self.pip_size).__name__}")
        if not math.isfinite(self.pip_size) or self.pip_size <= 0:
            raise ValueError(f"'pip_size' must be positive and finite, got {self.pip_size}")
        self.pip_size = float(self.pip_size)

        # --- window_seconds ---
        if isinstance(self.window_seconds, bool):
            raise TypeError("'window_seconds' must be numeric, not bool")
        if not isinstance(self.window_seconds, (int, float)):
            raise TypeError(f"'window_seconds' must be numeric, got {type(self.window_seconds).__name__}")
        if not math.isfinite(self.window_seconds) or self.window_seconds <= 0:
            raise ValueError(f"'window_seconds' must be positive and finite, got {self.window_seconds}")
        self.window_seconds = float(self.window_seconds)
