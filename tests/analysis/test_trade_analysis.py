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

"""Tests for `analysis.trade_analysis`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tick_backtest.analysis.trade_analysis import (
    compute_performance_metrics,
    load_trades,
    run_trade_analysis,
    write_report,
)


def test_load_trades_validates_required_columns(tmp_path: Path):
    """Expect loader to raise when parquet file lacks mandatory columns."""

    path = tmp_path / "trades.parquet"
    df = pd.DataFrame(
        {
            "entry_time": [pd.Timestamp("2020-01-01T00:00:00Z")],
            "pnl_pips": [5.0],
        }
    )
    df.to_parquet(path, index=False)

    with pytest.raises(ValueError) as excinfo:
        load_trades(path)

    assert "missing required columns" in str(excinfo.value)


def test_compute_performance_metrics_aggregates_results():
    """Document the aggregation of PnL, Sharpe, and drawdown metrics."""

    df = pd.DataFrame(
        {
            "entry_time": pd.to_datetime(
                ["2020-01-01T00:00:00Z", "2020-01-01T00:05:00Z", "2020-01-01T00:10:00Z"]
            ),
            "exit_time": pd.to_datetime(
                ["2020-01-01T00:02:00Z", "2020-01-01T00:07:00Z", "2020-01-01T00:12:00Z"]
            ),
            "pnl_pips": [10.0, -5.0, 0.0],
        }
    )

    metrics = compute_performance_metrics(df)

    assert metrics["total_trades"] == 3
    assert metrics["winning_trades"] == 1
    assert metrics["losing_trades"] == 1
    assert metrics["breakeven_trades"] == 1
    assert metrics["net_pnl_pips"] == pytest.approx(5.0)
    assert metrics["win_rate"] == pytest.approx(1 / 3)
    assert metrics["max_drawdown_pips"] <= 0.0
    assert metrics["avg_holding_minutes"] == pytest.approx(2.0)


def test_write_report_formats_markdown(tmp_path: Path):
    """Ensure the Markdown report includes key metrics and optional plots."""

    report_path = tmp_path / "report.md"
    metrics = {
        "total_trades": 2,
        "winning_trades": 1,
        "losing_trades": 1,
        "breakeven_trades": 0,
        "win_rate": 0.5,
        "net_pnl_pips": 5.0,
        "gross_profit_pips": 10.0,
        "gross_loss_pips": -5.0,
        "profit_factor": 2.0,
        "expectancy_pips": 2.5,
        "avg_trade_pips": 2.5,
        "avg_win_pips": 10.0,
        "avg_loss_pips": -5.0,
        "median_trade_pips": 2.5,
        "best_trade_pips": 10.0,
        "worst_trade_pips": -5.0,
        "avg_holding_minutes": 3.0,
        "per_trade_sharpe": 1.0,
        "daily_sharpe": 1.5,
        "daily_return_mean": 0.2,
        "daily_return_std": 0.1,
        "sampled_days": 1,
        "max_drawdown_pips": -2.0,
        "max_drawdown_duration": pd.Timedelta(minutes=5),
    }

    write_report(
        report_path=report_path,
        trades_path=tmp_path / "trades.parquet",
        metrics=metrics,
        plot_path=None,
    )

    text = report_path.read_text()
    assert "# Trade Performance Report" in text
    assert "**Total trades:** 2" in text
    assert "**Win rate:** 50.00%" in text


def test_run_trade_analysis_creates_artifacts(tmp_path: Path):
    """Smoke-test the high-level helper and its return container."""

    df = pd.DataFrame(
        {
            "entry_time": pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-01T00:05:00Z"]),
            "exit_time": pd.to_datetime(["2024-01-01T00:01:00Z", "2024-01-01T00:06:00Z"]),
            "pnl_pips": [10.0, -3.0],
            "direction": [1, -1],
            "entry_price": [1.1, 1.2],
            "exit_price": [1.11, 1.19],
        }
    )

    trades_path = tmp_path / "EURUSD" / "trades.parquet"
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(trades_path, index=False)

    result = run_trade_analysis(
        trades_path,
        output_dir=tmp_path / "analysis" / "EURUSD",
        generate_plot=False,
    )

    assert result.trades_path == trades_path
    assert result.metrics["total_trades"] == 2
    assert result.report_path is not None
    assert result.report_path.exists()
    assert result.plot_path is None
