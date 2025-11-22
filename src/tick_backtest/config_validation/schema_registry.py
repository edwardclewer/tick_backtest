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

from dataclasses import dataclass
from typing import Callable, Dict, Mapping, Optional

from tick_backtest.exceptions import ConfigError

Migration = Callable[[Mapping[str, object]], Mapping[str, object]]


@dataclass(frozen=True)
class SchemaSpec:
    """Describes how to handle a declared schema version."""

    canonical: str
    migration: Optional[Migration] = None


SUPPORTED_SCHEMAS: Dict[str, Dict[str, SchemaSpec]] = {
    "backtest": {
        "1.0": SchemaSpec(canonical="1.0"),
    },
    "metrics": {
        "1.0": SchemaSpec(canonical="1.0"),
    },
    "strategy": {
        "1.0": SchemaSpec(canonical="1.0"),
    },
}


def validate_schema_version(config_name: str, version: Optional[str]) -> SchemaSpec:
    """Ensure the supplied schema version is recognised and return its handler."""
    if config_name not in SUPPORTED_SCHEMAS:
        raise ConfigError(f"Unsupported configuration type '{config_name}'")

    if version is None:
        raise ConfigError(
            f"{config_name} configuration must declare 'schema_version' (supported: "
            f"{sorted(SUPPORTED_SCHEMAS[config_name].keys())})"
        )

    spec = SUPPORTED_SCHEMAS[config_name].get(str(version))
    if spec is None:
        known = ", ".join(sorted(SUPPORTED_SCHEMAS[config_name].keys()))
        raise ConfigError(
            f"{config_name} configuration references unsupported schema_version '{version}'. "
            f"Supported versions: [{known}]"
        )

    return spec
