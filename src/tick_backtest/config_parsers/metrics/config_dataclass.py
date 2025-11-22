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

from dataclasses import dataclass, field, asdict
from typing import List

@dataclass(kw_only=True)
class MetricConfigBase:
    name: str
    metric_type: str
    enabled: bool = True  # moved to base for universal toggle support

    def to_kwargs(self) -> dict:
        """
        Convert config dataclass to kwargs for metric instantiation.
        Strips out config-only fields not accepted by metric constructors.
        """
        d = asdict(self)
        for field in ("name", "metric_type", "enabled"):
            d.pop(field, None)
        return d

@dataclass(kw_only=True)
class MetricsConfigData:
    """
    Container for all validated metric configuration objects.
    Created by MetricsConfigParser and passed downstream for instantiation.
    """
    schema_version: str
    metrics: List[MetricConfigBase] = field(default_factory=list)
