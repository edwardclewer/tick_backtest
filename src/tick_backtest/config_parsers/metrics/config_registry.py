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

# metrics/config_registry.py
from typing import Dict, Type
from tick_backtest.config_parsers.metrics.dataclasses.drift_sign_config import DriftSignConfig
from tick_backtest.config_parsers.metrics.dataclasses.ewma_vol_config import EWMAVolConfig
from tick_backtest.config_parsers.metrics.dataclasses.session_config import SessionConfig
from tick_backtest.config_parsers.metrics.dataclasses.zscore_config import ZScoreConfig
from tick_backtest.config_parsers.metrics.dataclasses.ewma_config import EWMAConfig
from tick_backtest.config_parsers.metrics.dataclasses.ewma_slope_config import EWMASlopeConfig
from tick_backtest.config_parsers.metrics.dataclasses.spread_config import SpreadConfig
from tick_backtest.config_parsers.metrics.dataclasses.tick_rate_config import TickRateConfig

CONFIG_REGISTRY: Dict[str, Type] = {
    "drift_sign": DriftSignConfig,
    "ewma_vol": EWMAVolConfig,
    "session": SessionConfig,
    "zscore": ZScoreConfig,
    "ewma": EWMAConfig,
    "ewma_slope": EWMASlopeConfig,
    "spread": SpreadConfig,
    "tick_rate": TickRateConfig,
}
