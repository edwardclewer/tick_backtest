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

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(kw_only=True)
class MetricConfigBase:
    name: str
    metric_type: str
    enabled: bool = True

    def to_kwargs(self) -> dict[str, object]:
        """Convert config dataclass to kwargs for metric instantiation."""
        d = asdict(self)
        for field_name in ("name", "metric_type", "enabled"):
            d.pop(field_name, None)
        return d


@dataclass(kw_only=True)
class MetricsConfigData:
    """Container for all validated metric configuration objects."""

    schema_version: str
    metrics: list[MetricConfigBase] = field(default_factory=list)
