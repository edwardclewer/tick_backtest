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
from typing import TypedDict

from tick_backtest.config_validation.schema_registry import validate_schema_version
from tick_backtest.exceptions import ConfigError


class ValidatedBacktestConfig(TypedDict):
    schema_version: str
    pairs: list[str]
    start: str
    end: str
    pip_size: float
    warmup_seconds: int
    validate_ticks: bool
    trade_output_mode: str
    data_base_path: Path
    output_base_path: Path
    metrics_config_path: Path
    strategy_config_path: Path


def validate_backtest_config(raw: dict[str, object]) -> ValidatedBacktestConfig:
    """Validate a raw backtest configuration mapping."""
    if not isinstance(raw, dict):
        raise ValueError("Invalid backtest configuration: root must be a mapping")

    schema_version_raw = raw.get("schema_version")
    if schema_version_raw is not None and not isinstance(schema_version_raw, str):
        raise ValueError("Invalid backtest configuration: 'schema_version' must be a string")
    try:
        schema_spec = validate_schema_version("backtest", schema_version_raw)
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
        "validate_ticks",
        "trade_output_mode",
        "data_base_path",
        "output_base_path",
        "metrics_config_path",
        "strategy_config_path",
    }
    required_keys = allowed_keys - {"schema_version", "validate_ticks", "trade_output_mode"}

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
    normalized_pairs: list[str] = []
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

    pip_size_raw = working["pip_size"]
    if isinstance(pip_size_raw, bool) or not isinstance(pip_size_raw, (int, float, str)):
        raise ValueError("Invalid backtest configuration: 'pip_size' must be numeric")
    try:
        pip_size = float(pip_size_raw)
    except ValueError as exc:
        raise ValueError("Invalid backtest configuration: 'pip_size' must be numeric") from exc
    if pip_size <= 0:
        raise ValueError("Invalid backtest configuration: 'pip_size' must be positive")

    warmup_raw = working["warmup_seconds"]
    if isinstance(warmup_raw, bool) or not isinstance(warmup_raw, (int, float, str)):
        raise ValueError("Invalid backtest configuration: 'warmup_seconds' must be an integer")
    try:
        warmup_seconds = int(warmup_raw)
    except ValueError as exc:
        raise ValueError("Invalid backtest configuration: 'warmup_seconds' must be an integer") from exc
    if warmup_seconds < 0:
        raise ValueError("Invalid backtest configuration: 'warmup_seconds' must be non-negative")

    validate_ticks_raw = working.get("validate_ticks", True)
    if not isinstance(validate_ticks_raw, bool):
        raise ValueError("Invalid backtest configuration: 'validate_ticks' must be a boolean")

    trade_output_mode_raw = working.get("trade_output_mode", "trades")
    if not isinstance(trade_output_mode_raw, str):
        raise ValueError("Invalid backtest configuration: 'trade_output_mode' must be a string")
    trade_output_mode = trade_output_mode_raw.strip()
    if trade_output_mode not in {"trades", "summary"}:
        raise ValueError("Invalid backtest configuration: 'trade_output_mode' must be one of: trades, summary")

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
        "validate_ticks": validate_ticks_raw,
        "trade_output_mode": trade_output_mode,
        "data_base_path": data_base_path,
        "output_base_path": output_base_path,
        "metrics_config_path": metrics_config_path,
        "strategy_config_path": strategy_config_path,
    }
