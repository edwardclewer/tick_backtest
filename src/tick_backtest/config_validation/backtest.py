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

from pathlib import Path

from tick_backtest.exceptions import ConfigError
from tick_backtest.config_validation.schema_registry import validate_schema_version
def validate_backtest_config(raw: dict) -> dict:
    """Validate a raw backtest configuration mapping."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid backtest configuration: root must be a mapping")

    try:
        schema_spec = validate_schema_version("backtest", raw.get("schema_version"))
    except ConfigError as exc:
        raise ValueError(str(exc)) from exc

    working = dict(raw)
    if schema_spec.migration is not None:
        migrated = schema_spec.migration(working)
        working = dict(migrated)

    working["schema_version"] = schema_spec.canonical

    allowed_keys = {
        "schema_version",
        "pairs",
        "start",
        "end",
        "pip_size",
        "warmup_seconds",
        "data_base_path",
        "output_base_path",
        "metrics_config_path",
        "strategy_config_path",
    }
    required_keys = allowed_keys - {"schema_version"}

    extra = sorted(set(working.keys()) - allowed_keys)
    if extra:
        raise ValueError(f"Invalid backtest configuration: unexpected keys {extra}")

    missing = sorted(required_keys - set(working.keys()))
    if missing:
        raise ValueError(f"Invalid backtest configuration: missing keys {missing}")

    schema_version = working["schema_version"]
    if not isinstance(schema_version, str):
        raise ValueError("Invalid backtest configuration: 'schema_version' must be a string")

    pairs = working["pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Invalid backtest configuration: 'pairs' must be a non-empty list")
    normalized_pairs = []
    for pair in pairs:
        if not isinstance(pair, str) or not pair.strip():
            raise ValueError("Invalid backtest configuration: each pair must be a non-empty string")
        normalized_pairs.append(pair.strip())

    def _require_str(key: str) -> str:
        value = working[key]
        if not isinstance(value, str):
            raise ValueError(f"Invalid backtest configuration: '{key}' must be a string")
        value = value.strip()
        if not value:
            raise ValueError(f"Invalid backtest configuration: '{key}' must be non-empty")
        return value

    start = _require_str("start")
    end = _require_str("end")

    try:
        pip_size = float(working["pip_size"])
    except Exception as exc:
        raise ValueError("Invalid backtest configuration: 'pip_size' must be numeric") from exc
    if pip_size <= 0:
        raise ValueError("Invalid backtest configuration: 'pip_size' must be positive")

    try:
        warmup_seconds = int(working["warmup_seconds"])
    except Exception as exc:
        raise ValueError("Invalid backtest configuration: 'warmup_seconds' must be an integer") from exc
    if warmup_seconds < 0:
        raise ValueError("Invalid backtest configuration: 'warmup_seconds' must be non-negative")

    def _to_path(key: str) -> Path:
        value = working[key]
        if not isinstance(value, (str, Path)):
            raise ValueError(f"Invalid backtest configuration: '{key}' must be a path string")
        return Path(value)

    data_base_path = _to_path("data_base_path")
    output_base_path = _to_path("output_base_path")
    metrics_config_path = _to_path("metrics_config_path")
    strategy_config_path = _to_path("strategy_config_path")

    return {
        "schema_version": schema_version,
        "pairs": normalized_pairs,
        "start": start,
        "end": end,
        "pip_size": pip_size,
        "warmup_seconds": warmup_seconds,
        "data_base_path": data_base_path,
        "output_base_path": output_base_path,
        "metrics_config_path": metrics_config_path,
        "strategy_config_path": strategy_config_path,
    }
