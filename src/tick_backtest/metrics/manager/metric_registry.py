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

from tick_backtest.metrics.indicators.ewma_vol_metric import EWMAVolMetric
from tick_backtest.metrics.indicators.drift_sign_metric import DriftSignMetric
from tick_backtest.metrics.indicators.zscore_metric import ZScoreMetric
from tick_backtest.metrics.indicators.session_metric import SessionMetric
from tick_backtest.metrics.indicators.ewma_metric import EWMAMetric
from tick_backtest.metrics.indicators.ewma_slope_metric import EWMASlopeMetric
from tick_backtest.metrics.indicators.spread_metric import SpreadMetric
from tick_backtest.metrics.indicators.tick_rate_metric import TickRateMetric

METRIC_CLASS_REGISTRY = {
    "ewma_vol": EWMAVolMetric,
    "drift_sign": DriftSignMetric,
    "zscore": ZScoreMetric,
    "session": SessionMetric,
    "ewma": EWMAMetric,
    "ewma_slope": EWMASlopeMetric,
    "spread": SpreadMetric,
    "tick_rate": TickRateMetric,
}
