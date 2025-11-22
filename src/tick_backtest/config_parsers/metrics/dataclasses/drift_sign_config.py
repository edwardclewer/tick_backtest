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
from ..config_dataclass import MetricConfigBase

@dataclass(kw_only=True)
class DriftSignConfig(MetricConfigBase):
    """
    Configuration for the drift sign metric.

    Parameters
    ----------
    enabled : bool
        Whether to compute this metric during backtests.
    lookback_seconds : int
        Lookback window in seconds for computing drift direction.
    """
    enabled: bool
    lookback_seconds: int

    def __post_init__(self):
        # --- enabled ---
        if not isinstance(self.enabled, bool):
            raise TypeError(f"'enabled' must be a bool, got {type(self.enabled).__name__}")

        # --- lookback_seconds ---
        # Allow floats that are whole numbers (e.g., 600.0)
        if isinstance(self.lookback_seconds, float):
            if not self.lookback_seconds.is_integer():
                raise ValueError(f"'lookback_seconds' must be an integer number of seconds, got {self.lookback_seconds}")
            self.lookback_seconds = int(self.lookback_seconds)

        if not isinstance(self.lookback_seconds, int):
            raise TypeError(f"'lookback_seconds' must be an int, got {type(self.lookback_seconds).__name__}")

        if self.lookback_seconds <= 0:
            raise ValueError(f"'lookback_seconds' must be positive, got {self.lookback_seconds}")
