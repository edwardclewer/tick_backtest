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

"""Metric stratification tooling for post-trade analysis."""

from .compile_report import (
    build_metric_section,
    compile_report_for_mode,
    compile_reports_for_modes,
    discover_metrics_for_mode,
)
from .workflow import (
    DEFAULT_METRICS,
    DEFAULT_PREVIEW_COLUMNS,
    DEFAULT_BINNING_MODES,
    MetricStratificationOutputs,
    derive_backtest_identifier,
    load_trades,
    run_metric_stratification,
)

__all__ = [
    "DEFAULT_METRICS",
    "DEFAULT_PREVIEW_COLUMNS",
    "DEFAULT_BINNING_MODES",
    "build_metric_section",
    "MetricStratificationOutputs",
    "compile_report_for_mode",
    "compile_reports_for_modes",
    "derive_backtest_identifier",
    "discover_metrics_for_mode",
    "load_trades",
    "run_metric_stratification",
]
