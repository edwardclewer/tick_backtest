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
    assert (output_dir / "dropped_predictors.csv").is_file()

    summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
    assert "Multivariate Trade Analysis" in summary_text
    assert "R-squared" in summary_text
    assert "Collinearity Handling" in summary_text

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

    with pytest.raises(ValueError, match="No eligible entry-time numeric feature columns"):
        run_trade_regression_analysis(trades_path)


def test_run_trade_regression_analysis_excludes_post_trade_and_price_fields(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    pd.DataFrame(
        {
            "pnl_pips": [1.0, 2.0, 1.5, 3.5],
            "direction": [1, -1, 1, -1],
            "entry_price": [1.10, 1.11, 1.12, 1.13],
            "exit_price": [1.11, 1.10, 1.14, 1.15],
            "signal_price": [1.10, 1.11, 1.12, 1.13],
            "holding_seconds": [30, 45, 60, 75],
            "timestamp_entry": [1, 2, 3, 4],
            "timestamp_exit": [2, 3, 4, 5],
            "ewma_mid_5m.ewma": [1.0, 1.1, 1.2, 1.3],
            "spread_60s.spread_pips": [0.1, 0.2, 0.15, 0.3],
        }
    ).to_parquet(trades_path)

    output_dir = run_trade_regression_analysis(trades_path)

    coefficients = pd.read_csv(output_dir / "coefficients.csv")
    assert set(coefficients["feature"]) == {
        "intercept",
        "direction",
        "ewma_mid_5m.ewma",
        "spread_60s.spread_pips",
    }

    summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
    assert "entry-time numeric predictors only" in summary_text
    assert "post-trade or identity-linked columns are excluded" in summary_text


def test_run_trade_regression_analysis_drops_collinear_predictors(tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    pd.DataFrame(
        {
            "pnl_pips": [1.0, 2.0, 3.0, 4.0],
            "direction": [1, -1, 1, -1],
            "ewma_mid_5m.ewma": [10.0, 20.0, 30.0, 40.0],
            "ewma_mid_30m.ewma": [10.0, 20.0, 30.0, 40.0],
            "spread_60s.spread_pips": [0.1, 0.4, 0.2, 0.3],
        }
    ).to_parquet(trades_path)

    output_dir = run_trade_regression_analysis(trades_path)

    coefficients = pd.read_csv(output_dir / "coefficients.csv")
    assert "ewma_mid_5m.ewma" in set(coefficients["feature"])
    assert "ewma_mid_30m.ewma" not in set(coefficients["feature"])

    dropped = pd.read_csv(output_dir / "dropped_predictors.csv")
    collinear = dropped[dropped["reason"] == "collinear"]
    assert len(collinear) == 1
    assert collinear.iloc[0]["feature"] == "ewma_mid_30m.ewma"
    assert collinear.iloc[0]["kept_feature"] == "ewma_mid_5m.ewma"

    summary_text = (output_dir / "summary.md").read_text(encoding="utf-8")
    assert "**Dropped predictors:** 1" in summary_text
