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

import pandas as pd
import pytest

from tick_backtest.analysis.trade_regression import run_trade_regression_analysis


def test_run_trade_regression_analysis_writes_expected_outputs(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    pd.DataFrame(
        {
            "pnl_pips": [1.0, 2.0, 1.5, 3.5],
            "holding_seconds": [30, 45, 60, 75],
            "spread_60s.spread_pips": [0.1, 0.2, 0.15, 0.3],
            "tick_rate_30s.tick_rate_per_min": [120.0, 140.0, 150.0, 180.0],
        }
    ).to_parquet(trades_path)

    output_dir = run_trade_regression_analysis(trades_path)

    assert output_dir == tmp_path / "multivariate_analysis"
    assert (output_dir / "summary.md").is_file()
    assert (output_dir / "coefficients.csv").is_file()
    assert (output_dir / "correlations.csv").is_file()

    summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
    assert "Multivariate Trade Analysis" in summary_text
    assert "R-squared" in summary_text

    coefficients = pd.read_csv(output_dir / "coefficients.csv")
    assert "feature" in coefficients.columns
    assert "coefficient" in coefficients.columns


def test_run_trade_regression_analysis_requires_numeric_predictors(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    pd.DataFrame(
        {
            "pnl_pips": [1.0, 2.0],
            "direction": ["buy", "sell"],
        }
    ).to_parquet(trades_path)

    with pytest.raises(ValueError, match="No numeric feature columns"):
        run_trade_regression_analysis(trades_path)
