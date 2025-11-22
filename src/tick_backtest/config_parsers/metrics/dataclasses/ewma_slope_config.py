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
class EWMASlopeConfig(MetricConfigBase):
    """Configuration for EWMA slope metric."""

    enabled: bool
    tau_seconds: float
    window_seconds: float
    initial_value: float | None = None
    price_field: str = "mid"

    def __post_init__(self) -> None:
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

        # --- window_seconds ---
        if isinstance(self.window_seconds, bool):
            raise TypeError("'window_seconds' must be numeric, not bool")
        if not isinstance(self.window_seconds, (int, float)):
            raise TypeError(f"'window_seconds' must be numeric, got {type(self.window_seconds).__name__}")
        if not math.isfinite(self.window_seconds) or self.window_seconds <= 0:
            raise ValueError(f"'window_seconds' must be positive and finite, got {self.window_seconds}")
        self.window_seconds = float(self.window_seconds)

        # --- initial_value ---
        if self.initial_value is not None:
            if isinstance(self.initial_value, bool):
                raise TypeError("'initial_value' must be numeric, not bool")
            if not isinstance(self.initial_value, (int, float)):
                raise TypeError(f"'initial_value' must be numeric, got {type(self.initial_value).__name__}")
            if not math.isfinite(self.initial_value):
                raise ValueError(f"'initial_value' must be finite, got {self.initial_value}")
            self.initial_value = float(self.initial_value)

        # --- price_field ---
        if not isinstance(self.price_field, str):
            raise TypeError(f"'price_field' must be a string, got {type(self.price_field).__name__}")
        if not self.price_field:
            raise ValueError("'price_field' must be a non-empty string")
