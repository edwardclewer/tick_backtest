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

from tick_backtest.config_parsers.backtest.config_dataclass import BacktestConfigData
from tick_backtest.config_parsers.metrics.config_parser import MetricsConfigParser
from tick_backtest.config_parsers.strategy.config_parser import StrategyConfigParser
from tick_backtest.config_parsers.utils.utils import (
    parse_year_month,
    validate_nonnegative_int,
    validate_pairs,
    validate_path,
    validate_positive_float,
)
from tick_backtest.config_validation import validate_backtest_config
from tick_backtest.exceptions import ConfigError
from tick_backtest.metrics.manager.metric_registry import METRIC_CLASS_REGISTRY


class BacktestConfigParser:
    @staticmethod
    def _enabled_metric_references(metrics_config) -> set[str]:
        references: set[str] = set()

        for metric_cfg in metrics_config.metrics:
            if not getattr(metric_cfg, "enabled", True):
                continue

            references.add(metric_cfg.name)

            metric_cls = METRIC_CLASS_REGISTRY.get(metric_cfg.metric_type)
            if metric_cls is None:
                raise ConfigError(f"Unrecognized metric type '{metric_cfg.metric_type}'")

            try:
                metric = metric_cls(name=metric_cfg.name, **metric_cfg.to_kwargs())
            except Exception as exc:
                raise ConfigError(
                    f"Failed to instantiate metric '{metric_cfg.name}' of type "
                    f"'{metric_cfg.metric_type}' for strategy validation: {exc}"
                ) from exc

            value_method = getattr(metric, "value", None)
            if not callable(value_method):
                continue

            snapshot = value_method()
            if not isinstance(snapshot, dict):
                continue

            for field_name in snapshot.keys():
                if isinstance(field_name, str) and field_name:
                    references.add(f"{metric_cfg.name}.{field_name}")

        return references

    def parse_config(self, backtest_config_path: Path) -> BacktestConfigData:
        cfg, config_path = self._validate_yaml(backtest_config_path)
        try:
            cfg = validate_backtest_config(cfg)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        return self._validate_and_build_backtest_config(cfg, config_path.parent)

    def _validate_yaml(self, backtest_config_path: Path) -> tuple[dict[str, object], Path]:
        try:
            path = backtest_config_path.resolve(strict=True)
        except FileNotFoundError:
            raise ConfigError(f"config file not found: {backtest_config_path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"error parsing YAML: {e}") from e

        if not isinstance(cfg, dict):
            raise ConfigError("config root must be a mapping (YAML dict)")

        return cfg, path

    def _validate_and_build_backtest_config(
        self,
        cfg: dict[str, object],
        config_dir: Path,
    ) -> BacktestConfigData:
        required = [
            "pairs",
            "start",
            "end",
            "data_base_path",
            "output_base_path",
            "pip_size",
            "warmup_seconds",
            "metrics_config_path",
            "strategy_config_path",
            ]

        for key in required:
            if key not in cfg:
                raise ConfigError(f"missing required config key: {key}")

        year_start, month_start = parse_year_month(cfg["start"])
        year_end, month_end = parse_year_month(cfg["end"])

        if (year_start, month_start) > (year_end, month_end):
            raise ConfigError("start date must be on or before end date")

        data_base_path = validate_path(
            cfg["data_base_path"],
            must_exist=True,
            expect_dir=True,
            label="data_base_path",
            base_dir=config_dir,
        )

        output_base_path = validate_path(
            cfg["output_base_path"],
            must_exist=False,
            expect_dir=True,
            create_if_missing=True,
            label="output_base_path",
            base_dir=config_dir,
        )

        metrics_config_path = validate_path(
            cfg["metrics_config_path"],
            must_exist=True,
            expect_dir=False,
            label="metrics_config_path",
            base_dir=config_dir,
        )

        strategy_config_path = validate_path(
            cfg["strategy_config_path"],
            must_exist=True,
            expect_dir=False,
            label="strategy_config_path",
            base_dir=config_dir,
        )

        pairs = validate_pairs(cfg["pairs"])
        pip_size = validate_positive_float(cfg["pip_size"], "pip_size")
        warmup_seconds = validate_nonnegative_int(cfg["warmup_seconds"], "warmup_seconds")

        metrics_parser = MetricsConfigParser(metrics_config_path)
        try:
            metrics_config = metrics_parser.load_metrics_config()
        except ConfigError as exc:
            raise ConfigError(f"invalid metrics configuration: {exc}") from exc

        enabled_metric_names = self._enabled_metric_references(metrics_config)

        strategy_parser = StrategyConfigParser(strategy_config_path)
        try:
            strategy_config = strategy_parser.load(enabled_metric_names=enabled_metric_names)
        except ConfigError as exc:
            raise ConfigError(f"invalid strategy configuration: {exc}") from exc

        backtest_config = BacktestConfigData(
            schema_version=cfg["schema_version"],
            pairs=pairs,
            year_start=year_start,
            year_end=year_end,
            month_start=month_start,
            month_end=month_end,
            pip_size=pip_size,
            warmup_seconds=warmup_seconds,
            data_base_path=data_base_path,
            output_base_path=output_base_path,
            metrics_config_path=metrics_config_path,
            strategy_config_path=strategy_config_path,
            strategy_config=strategy_config,
        )

        return backtest_config
