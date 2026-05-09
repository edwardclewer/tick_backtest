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
from pathlib import Path

from tick_backtest.config_parsers.strategy.config_dataclass import StrategyConfigData


@dataclass
class BacktestConfigData:
    schema_version: str
    pairs: list[str]
    year_start: int
    year_end: int
    month_start: int
    month_end: int
    pip_size: float
    warmup_seconds: int
    data_base_path: Path
    output_base_path: Path
    metrics_config_path: Path
    strategy_config_path: Path
    validate_ticks: bool = True
    trade_output_mode: str = "trades"
    strategy_config: StrategyConfigData | None = None
