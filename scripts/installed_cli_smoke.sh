#!/usr/bin/env bash
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

set -euo pipefail

DEMO_ROOT="${TMPDIR:-/tmp}/tick-backtest-installed-wheel-smoke"
rm -rf "$DEMO_ROOT"

tick-backtest --help
tick-backtest example-config --output "$DEMO_ROOT" --include-demo-data

test -f "$DEMO_ROOT/backtest.yaml"
test -f "$DEMO_ROOT/metrics.yaml"
test -f "$DEMO_ROOT/strategy.yaml"
test -f "$DEMO_ROOT/demo_data/EURUSD/EURUSD_2000-01.parquet"
test -f "$DEMO_ROOT/demo_data/GBPUSD/GBPUSD_2000-02.parquet"

tick-backtest run "$DEMO_ROOT/backtest.yaml"

TRADES_PATH="$(find "$DEMO_ROOT/output" -path '*/output/*/trades.parquet' | sort | head -n 1)"
test -n "$TRADES_PATH"

tick-backtest report "$TRADES_PATH"
tick-backtest analyze "$TRADES_PATH"

test -f "$(dirname "$TRADES_PATH")/trades_report.md"
test -f "$(dirname "$TRADES_PATH")/metric_stratification/reports/metric_report_fixed.md"
test -f "$(dirname "$TRADES_PATH")/multivariate_analysis/summary.md"
