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

"""Top-level exports for the tick_backtest package."""

__all__ = [
    "DEFAULT_METRICS",
    "BacktestAnalysisSummary",
    "MetricStratificationSummary",
    "run_backtest",
    "run_backtest_analysis",
    "run_metric_stratification_analysis",
    "run_metric_stratification",
    "run_trade_analysis",
    "TradeAnalysisResult",
]


def __getattr__(name):
    """Lazily import heavy submodules when their symbols are first accessed."""
    if name in ("DEFAULT_METRICS", "run_metric_stratification"):
        from tick_backtest.analysis.metric_stratification import (
            DEFAULT_METRICS,
            run_metric_stratification,
        )
        globals().update(
            DEFAULT_METRICS=DEFAULT_METRICS,
            run_metric_stratification=run_metric_stratification,
        )
        return globals()[name]

    if name == "run_backtest":
        from tick_backtest.backtest.workflow import run_backtest
        globals()["run_backtest"] = run_backtest
        return run_backtest

    if name in {
        "BacktestAnalysisSummary",
        "MetricStratificationSummary",
        "run_backtest_analysis",
        "run_metric_stratification_analysis",
        "run_trade_analysis",
        "TradeAnalysisResult",
    }:
        from tick_backtest.analysis import (
            BacktestAnalysisSummary,
            MetricStratificationSummary,
            run_backtest_analysis,
            run_metric_stratification_analysis,
            run_trade_analysis,
            TradeAnalysisResult,
        )

        globals().update(
            BacktestAnalysisSummary=BacktestAnalysisSummary,
            MetricStratificationSummary=MetricStratificationSummary,
            run_backtest_analysis=run_backtest_analysis,
            run_metric_stratification_analysis=run_metric_stratification_analysis,
            run_trade_analysis=run_trade_analysis,
            TradeAnalysisResult=TradeAnalysisResult,
        )
        return globals()[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
