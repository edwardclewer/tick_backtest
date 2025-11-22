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
from typing import Any, Dict, List

import yaml

from tick_backtest.config_parsers.strategy.config_dataclass import (
    EntryConfig,
    ExitConfig,
    PredicateConfig,
    StrategyConfigData,
)
from tick_backtest.config_parsers.strategy.config_registry import ENTRY_PARAMS_REGISTRY
from tick_backtest.config_parsers.strategy.entry_configs import EntryParamsBase
from tick_backtest.config_validation import validate_strategy_config
from tick_backtest.exceptions import ConfigError


class StrategyConfigParser:
    """Parse and validate the single-strategy YAML configuration."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Strategy config not found: {self.config_path}")

    def load(self) -> StrategyConfigData:
        try:
            raw = self._load_yaml()
            validated = validate_strategy_config(raw)
            strategy_raw = self._extract_strategy(validated)
            entry_cfg = self._build_entry(strategy_raw.get("entry"))
            exit_cfg = self._build_exit(strategy_raw.get("exit"))
            name = strategy_raw.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("Strategy config must define a non-empty 'name'")
            schema_version = validated.get("schema_version", "1.0")
            return StrategyConfigData(schema_version=schema_version, name=name, entry=entry_cfg, exit=exit_cfg)
        except (ValueError, TypeError) as exc:
            raise ConfigError(str(exc)) from exc

    # ------------------------------------------------------------------
    def _load_yaml(self) -> Dict[str, Any]:
        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML at {self.config_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Strategy config root must be a mapping (YAML dict)")
        return data

    def _extract_strategy(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        if "strategy" not in raw:
            raise ValueError("Strategy config must contain top-level key 'strategy'")
        strategy = raw["strategy"]
        if not isinstance(strategy, dict):
            raise ValueError("Top-level 'strategy' entry must be a mapping")
        unexpected = [key for key in raw.keys() if key not in ("strategy", "schema_version")]
        if unexpected:
            raise ValueError(f"Unexpected top-level keys in strategy config: {unexpected}")
        return strategy

    def _build_entry(self, entry_raw: Any) -> EntryConfig:
        if not isinstance(entry_raw, dict):
            raise ValueError("Strategy 'entry' must be a mapping")
        name = entry_raw.get("name")
        engine = entry_raw.get("engine")
        params = self._build_entry_params(engine, entry_raw.get("params", {}))
        predicates_raw = entry_raw.get("predicates", [])
        predicates = self._build_predicates(predicates_raw, context="entry")
        return EntryConfig(name=name, engine=engine, params=params, predicates=predicates)

    def _build_exit(self, exit_raw: Any) -> ExitConfig:
        if not isinstance(exit_raw, dict):
            raise ValueError("Strategy 'exit' must be a mapping")
        name = exit_raw.get("name")
        predicates_raw = exit_raw.get("predicates", [])
        predicates = self._build_predicates(predicates_raw, context="exit")
        return ExitConfig(name=name, predicates=predicates)

    def _build_entry_params(self, engine: str, params_raw: Any) -> EntryParamsBase:
        params_cls = ENTRY_PARAMS_REGISTRY.get(engine)
        if params_cls is None:
            raise ValueError(f"Unrecognised entry engine '{engine}' in strategy config")
        if params_raw is None:
            params_raw = {}
        if not isinstance(params_raw, dict):
            raise ValueError(f"'params' for entry engine '{engine}' must be a mapping")
        try:
            return params_cls(**params_raw)
        except Exception as exc:
            raise ValueError(
                f"Failed to instantiate params for entry engine '{engine}': {exc}"
            ) from exc

    def _build_predicates(self, raw_list: Any, *, context: str) -> List[PredicateConfig]:
        if raw_list is None:
            return []
        if not isinstance(raw_list, list):
            raise ValueError(f"{context.capitalize()} 'predicates' must be a list")

        predicates: List[PredicateConfig] = []
        seen: set[tuple[Any, ...]] = set()
        for idx, item in enumerate(raw_list, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"{context.capitalize()} predicate #{idx} must be a mapping")
            predicate = PredicateConfig(
                metric=item.get("metric"),
                operator=item.get("operator"),
                value=item.get("value"),
                other_metric=item.get("other_metric"),
                use_abs=item.get("use_abs", False),
            )
            key = (
                predicate.metric,
                predicate.operator,
                predicate.value,
                predicate.other_metric,
                predicate.use_abs,
            )
            if key in seen:
                raise ValueError(
                    f"Invalid strategy configuration: duplicate predicate in {context} at index {idx}"
                )
            seen.add(key)
            predicates.append(predicate)
        return predicates
