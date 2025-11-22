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

"""Analysis utilities for tick-backtest outputs."""

from .backtest_analysis import (
    BacktestAnalysisSummary,
    MetricStratificationSummary,
    run_backtest_analysis,
    run_metric_stratification_analysis,
)
from .trade_analysis import TradeAnalysisResult, run_trade_analysis

__all__ = [
    "BacktestAnalysisSummary",
    "run_backtest_analysis",
    "MetricStratificationSummary",
    "run_metric_stratification_analysis",
    "TradeAnalysisResult",
    "run_trade_analysis",
]
