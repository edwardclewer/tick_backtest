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

from tick_backtest.config_validation.schema_registry import validate_schema_version
from tick_backtest.exceptions import ConfigError


def validate_metrics_config(raw: dict) -> dict:
    """Validate metrics YAML payload and return normalized mapping."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid metrics configuration: root must be a mapping")

    try:
        schema_spec = validate_schema_version("metrics", raw.get("schema_version"))
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc

    working = dict(raw)
    if schema_spec.migration is not None:
        migrated = schema_spec.migration(working)
        working = dict(migrated)

    working["schema_version"] = schema_spec.canonical

    allowed_root = {"schema_version", "metrics"}
    extra_root = sorted(set(working.keys()) - allowed_root)
    if extra_root:
        raise ValueError(f"Invalid metrics configuration: unexpected keys {extra_root}")

    metrics = working.get("metrics", [])
    if metrics is None:
        metrics = []
    if not isinstance(metrics, list):
        raise ValueError("Invalid metrics configuration: 'metrics' must be a list")

    normalized = []
    for idx, entry in enumerate(metrics, start=1):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Invalid metrics configuration: entry #{idx} must be a mapping"
            )

        allowed_entry = {"name", "type", "enabled", "params"}
        extra_entry = sorted(set(entry.keys()) - allowed_entry)
        if extra_entry:
            raise ValueError(
                f"Invalid metrics configuration: entry #{idx} has unexpected keys {extra_entry}"
            )

        missing = {"name", "type"} - set(entry.keys())
        if missing:
            raise ValueError(
                f"Invalid metrics configuration: entry #{idx} missing keys {sorted(missing)}"
            )

        name = entry["name"]
        metric_type = entry["type"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Invalid metrics configuration: entry #{idx} 'name' must be a non-empty string"
            )
        if not isinstance(metric_type, str) or not metric_type.strip():
            raise ValueError(
                f"Invalid metrics configuration: entry #{idx} 'type' must be a non-empty string"
            )
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(
                f"Invalid metrics configuration: entry #{idx} 'enabled' must be a boolean"
            )
        params = entry.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError(
                f"Invalid metrics configuration: entry #{idx} 'params' must be a mapping"
            )

        normalized.append(
            {
                "name": name.strip(),
                "type": metric_type.strip(),
                "enabled": enabled,
                "params": dict(params),
            }
        )

    schema_version = working.get("schema_version")
    if not isinstance(schema_version, str):
        raise ValueError("Invalid metrics configuration: 'schema_version' must be a string")

    return {
        "schema_version": schema_version,
        "metrics": normalized,
    }
