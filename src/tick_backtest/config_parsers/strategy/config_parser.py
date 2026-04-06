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

import yaml

from tick_backtest.config_parsers.strategy.config_dataclass import (
    EntryConfig,
    ExitConfig,
    PredicateConfig,
    StrategyConfigData,
)
from tick_backtest.config_parsers.strategy.config_registry import ENTRY_PARAMS_REGISTRY
from tick_backtest.config_parsers.strategy.entry_configs import (
    EntryParamsBase,
    EWMACrossoverEntryParams,
)
from tick_backtest.config_validation import validate_strategy_config
from tick_backtest.config_validation.strategy import (
    EntryPayload,
    ExitPayload,
    PredicatePayload,
    StrategyPayload,
    ValidatedStrategyConfig,
)
from tick_backtest.exceptions import ConfigError


class StrategyConfigParser:
    """Parse and validate the single-strategy YAML configuration."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Strategy config not found: {self.config_path}")

    def load(self, *, enabled_metric_names: set[str] | None = None) -> StrategyConfigData:
        try:
            raw = self._load_yaml()
            validated = validate_strategy_config(raw)
            strategy_raw = self._extract_strategy(validated)
            entry_cfg = self._build_entry(strategy_raw["entry"])
            exit_cfg = self._build_exit(strategy_raw["exit"])
            name = strategy_raw["name"]
            self._validate_metric_references(
                entry_cfg=entry_cfg,
                exit_cfg=exit_cfg,
                enabled_metric_names=enabled_metric_names,
            )
            schema_version = validated["schema_version"]
            return StrategyConfigData(schema_version=schema_version, name=name, entry=entry_cfg, exit=exit_cfg)
        except (ValueError, TypeError) as exc:
            raise ConfigError(str(exc)) from exc

    def _load_yaml(self) -> dict[str, object]:
        try:
            with self.config_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ValueError(f"Error parsing YAML at {self.config_path}: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("Strategy config root must be a mapping (YAML dict)")
        return data

    def _extract_strategy(self, raw: ValidatedStrategyConfig) -> StrategyPayload:
        return raw["strategy"]

    def _build_entry(self, entry_raw: EntryPayload) -> EntryConfig:
        name = entry_raw["name"]
        engine = entry_raw["engine"]
        params = self._build_entry_params(engine, entry_raw["params"])
        predicates = self._build_predicates(entry_raw["predicates"], context="entry")
        return EntryConfig(name=name, engine=engine, params=params, predicates=predicates)

    def _build_exit(self, exit_raw: ExitPayload) -> ExitConfig:
        name = exit_raw["name"]
        predicates = self._build_predicates(exit_raw["predicates"], context="exit")
        return ExitConfig(name=name, predicates=predicates)

    def _build_entry_params(self, engine: str, params_raw: dict[str, object]) -> EntryParamsBase:
        params_cls = ENTRY_PARAMS_REGISTRY.get(engine)
        if params_cls is None:
            raise ValueError(f"Unrecognised entry engine '{engine}' in strategy config")
        try:
            return params_cls(**params_raw)
        except Exception as exc:
            raise ValueError(
                f"Failed to instantiate params for entry engine '{engine}': {exc}"
            ) from exc

    def _build_predicates(
        self,
        raw_list: list[PredicatePayload],
        *,
        context: str,
    ) -> list[PredicateConfig]:
        predicates: list[PredicateConfig] = []
        seen: set[tuple[object, ...]] = set()
        for idx, item in enumerate(raw_list, start=1):
            predicate = PredicateConfig(
                metric=item["metric"],
                operator=item["operator"],
                value=item["value"],
                other_metric=item["other_metric"],
                use_abs=item["use_abs"],
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

    def _validate_metric_references(
        self,
        *,
        entry_cfg: EntryConfig,
        exit_cfg: ExitConfig,
        enabled_metric_names: set[str] | None,
    ) -> None:
        if enabled_metric_names is None:
            return

        self._validate_predicate_metric_references(
            entry_cfg.predicates,
            enabled_metric_names,
            context="entry predicate",
        )
        self._validate_predicate_metric_references(
            exit_cfg.predicates,
            enabled_metric_names,
            context="exit predicate",
        )

        if entry_cfg.engine == "ewma_crossover" and isinstance(entry_cfg.params, EWMACrossoverEntryParams):
            missing: list[tuple[str, str]] = []
            if entry_cfg.params.fast_metric not in enabled_metric_names:
                missing.append(("fast_metric", entry_cfg.params.fast_metric))
            if entry_cfg.params.slow_metric not in enabled_metric_names:
                missing.append(("slow_metric", entry_cfg.params.slow_metric))
            if missing:
                details = ", ".join(f"{label}={metric!r}" for label, metric in missing)
                raise ValueError(
                    "Strategy config references unknown metrics for ewma_crossover entry: "
                    f"{details}"
                )

    @staticmethod
    def _validate_predicate_metric_references(
        predicates: list[PredicateConfig],
        enabled_metric_names: set[str],
        *,
        context: str,
    ) -> None:
        for predicate in predicates:
            if predicate.metric not in enabled_metric_names:
                raise ValueError(
                    f"Strategy config references unknown metric {predicate.metric!r} in {context}"
                )
            if predicate.other_metric is not None and predicate.other_metric not in enabled_metric_names:
                raise ValueError(
                    "Strategy config references unknown other_metric "
                    f"{predicate.other_metric!r} in {context}"
                )
