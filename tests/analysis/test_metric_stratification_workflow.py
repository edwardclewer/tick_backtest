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

"""Tests for the metric stratification workflow helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tick_backtest.analysis.metric_stratification.workflow import (
    derive_backtest_identifier,
    load_trades,
    run_metric_stratification,
)


def test_derive_backtest_identifier_handles_generic_path(tmp_path):
    trade_path = tmp_path / "EURUSD" / "trades.parquet"
    trade_path.parent.mkdir(parents=True, exist_ok=True)
    trade_path.write_text("", encoding="utf-8")

    identifier = derive_backtest_identifier(trade_path)
    assert identifier == "EURUSD"


def test_run_metric_stratification_returns_summary(tmp_path):
    trade_path = tmp_path / "trades.parquet"
    df = pd.DataFrame(
        {
            "pnl_pips": [1.0, -0.5, 0.25, 0.75],
            "drift_sign.drift": [0.1, -0.2, 0.05, 0.3],
        }
    )
    df.to_parquet(trade_path, index=False)

    output_root = tmp_path / "analysis_outputs"
    result = run_metric_stratification(
        trade_file=trade_path,
        output_root=output_root,
        metrics=["drift_sign.drift"],
        plot=False,
        save_outputs=False,
        configure_logs=False,
        generate_reports=False,
        binning_modes=("scott",),
    )

    assert "drift_sign.drift" in result.summaries
    summary = result.summaries["drift_sign.drift"]
    assert not summary.empty
    assert {"avg_pnl", "count"}.issubset(summary.columns)
    assert result.reports_by_mode == {}
    assert result.binning_modes == ("scott",)


def test_load_trades_roundtrip(tmp_path):
    trade_path = tmp_path / "sample.parquet"
    df = pd.DataFrame({"pnl_pips": [0.5], "metric": [1.0]})
    df.to_parquet(trade_path, index=False)

    loaded = load_trades(trade_path)
    assert list(loaded.columns) == ["pnl_pips", "metric"]
