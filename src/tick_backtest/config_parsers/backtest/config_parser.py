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

from pathlib import Path

import yaml

from tick_backtest.config_parsers.backtest.config_dataclass import BacktestConfigData
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

class BacktestConfigParser:
    def __init__(
        self,
        ):
        return

    def parse_config(
        self,
        backtest_config_path: Path
        ):
        cfg = self._validate_yaml(backtest_config_path)
        try:
            cfg = validate_backtest_config(cfg)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc
        backtest_config = self._validate_and_build_backtest_coordinator(cfg)
        return backtest_config

    def _validate_yaml(
        self,
        backtest_config_path: Path
        ):
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

        return cfg


    def _validate_and_build_backtest_coordinator(
        self,
        cfg
        ):
        required = [
            "pairs",
            "start",
            "end",
            "data_base_path",
            "output_base_path",
            "pip_size",
            "warmup_seconds",
            "metrics_config_path",
            "strategy_config_path"
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
            label="data_base_path"
        )

        output_base_path = validate_path(
            cfg["output_base_path"],
            must_exist=False,
            expect_dir=True,
            create_if_missing=True,
            label="output_base_path"
        )

        metrics_config_path = validate_path(
            cfg["metrics_config_path"],
            must_exist=True,
            expect_dir=False,
            label="metrics_config_path"
        )

        strategy_config_path = validate_path(
            cfg["strategy_config_path"],
            must_exist=True,
            expect_dir=False,
            label="strategy_config_path"
        )

        pairs = validate_pairs(cfg["pairs"])
        pip_size = validate_positive_float(cfg["pip_size"], "pip_size")
        warmup_seconds = validate_nonnegative_int(cfg["warmup_seconds"], "warmup_seconds")


        strategy_parser = StrategyConfigParser(strategy_config_path)
        try:
            strategy_config = strategy_parser.load()
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
