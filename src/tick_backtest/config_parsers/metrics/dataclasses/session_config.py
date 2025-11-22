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
class SessionConfig(MetricConfigBase):
    enabled: bool

    def __post_init__(self):
        # --- enabled ---
        if not isinstance(self.enabled, bool):
            raise TypeError(f"'enabled' must be a bool, got {type(self.enabled).__name__}")
