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

from typing import Any, Dict, List

from tick_backtest.config_validation.schema_registry import validate_schema_version
from tick_backtest.exceptions import ConfigError

def _validate_predicates(items: Any, context: str) -> List[Dict[str, Any]]:
    if items is None:
        return []
    if not isinstance(items, list):
        raise ValueError(
            f"Invalid strategy configuration: {context} 'predicates' must be a list"
        )

    normalized: List[Dict[str, Any]] = []
    allowed_keys = {"metric", "operator", "value", "other_metric", "use_abs"}

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"Invalid strategy configuration: {context} predicate #{idx} must be a mapping"
            )

        extra = sorted(set(item.keys()) - allowed_keys)
        if extra:
            raise ValueError(
                f"Invalid strategy configuration: {context} predicate #{idx} has unexpected keys {extra}"
            )

        normalized.append(
            {
                "metric": item.get("metric"),
                "operator": item.get("operator"),
                "value": item.get("value"),
                "other_metric": item.get("other_metric"),
                "use_abs": bool(item.get("use_abs", False)),
            }
        )

    return normalized


def _require_mapping(value: Any, *, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Invalid strategy configuration: {label} must be a mapping")
    return value


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Invalid strategy configuration: '{label}' must be a non-empty string"
        )
    return value.strip()


def validate_strategy_config(raw: dict) -> dict:
    """Validate strategy YAML payload and return normalized mapping."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid strategy configuration: root must be a mapping")

    try:
        schema_spec = validate_schema_version("strategy", raw.get("schema_version"))
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc

    working = dict(raw)
    if schema_spec.migration is not None:
        migrated = schema_spec.migration(working)
        working = dict(migrated)

    working["schema_version"] = schema_spec.canonical

    allowed_root = {"schema_version", "strategy"}
    extra_root = sorted(set(working.keys()) - allowed_root)
    if extra_root:
        raise ValueError(
            f"Invalid strategy configuration: unexpected top-level keys {extra_root}"
        )

    if "strategy" not in working:
        raise ValueError("Invalid strategy configuration: missing 'strategy'")

    strategy_raw = _require_mapping(working["strategy"], label="strategy")

    allowed_strategy = {"name", "entry", "exit"}
    extra_strategy = sorted(set(strategy_raw.keys()) - allowed_strategy)
    if extra_strategy:
        raise ValueError(
            f"Invalid strategy configuration: unexpected keys {extra_strategy} in 'strategy'"
        )

    for key in ("name", "entry", "exit"):
        if key not in strategy_raw:
            raise ValueError(
                f"Invalid strategy configuration: 'strategy' missing '{key}'"
            )

    name = _require_string(strategy_raw["name"], label="strategy.name")

    entry_raw = _require_mapping(strategy_raw["entry"], label="strategy.entry")
    allowed_entry = {"name", "engine", "params", "predicates"}
    extra_entry = sorted(set(entry_raw.keys()) - allowed_entry)
    if extra_entry:
        raise ValueError(
            f"Invalid strategy configuration: 'entry' has unexpected keys {extra_entry}"
        )
    for key in ("name", "engine"):
        if key not in entry_raw:
            raise ValueError(
                f"Invalid strategy configuration: 'entry' missing '{key}'"
            )
    entry_name = _require_string(entry_raw["name"], label="entry.name")
    entry_engine = _require_string(entry_raw["engine"], label="entry.engine")
    params = entry_raw.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError(
            "Invalid strategy configuration: 'entry.params' must be a mapping"
        )
    predicates_entry = _validate_predicates(entry_raw.get("predicates"), "entry")

    exit_raw = _require_mapping(strategy_raw["exit"], label="strategy.exit")
    allowed_exit = {"name", "predicates"}
    extra_exit = sorted(set(exit_raw.keys()) - allowed_exit)
    if extra_exit:
        raise ValueError(
            f"Invalid strategy configuration: 'exit' has unexpected keys {extra_exit}"
        )
    if "name" not in exit_raw:
        raise ValueError("Invalid strategy configuration: 'exit' missing 'name'")
    exit_name = _require_string(exit_raw["name"], label="exit.name")
    predicates_exit = _validate_predicates(exit_raw.get("predicates"), "exit")

    schema_version = working.get("schema_version")
    if not isinstance(schema_version, str):
        raise ValueError("Invalid strategy configuration: 'schema_version' must be a string")

    return {
        "schema_version": schema_version,
        "strategy": {
            "name": name,
            "entry": {
                "name": entry_name,
                "engine": entry_engine,
                "params": dict(params),
                "predicates": predicates_entry,
            },
            "exit": {
                "name": exit_name,
                "predicates": predicates_exit,
            },
        },
    }
