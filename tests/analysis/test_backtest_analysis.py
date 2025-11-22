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

"""Tests for the batch backtest analysis helper."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tick_backtest.analysis.backtest_analysis import run_backtest_analysis


def _write_trades(path: Path, *, include_exit: bool = True) -> None:
    data = {
        "entry_time": pd.to_datetime(["2024-01-01T00:00:00Z"]),
        "pnl_pips": [5.0],
    }
    if include_exit:
        data["exit_time"] = pd.to_datetime(["2024-01-01T00:01:00Z"])

    df = pd.DataFrame(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_run_backtest_analysis_creates_per_pair_reports(tmp_path: Path):
    """Expect analysis artefacts to land under output/<run>/analysis/<pair>/."""

    run_output_dir = tmp_path / "run" / "output"
    trades_path = run_output_dir / "EURUSD" / "trades.parquet"
    _write_trades(trades_path)

    summary = run_backtest_analysis(
        run_output_dir,
        generate_plot=False,
        run_id="test-run",
    )

    expected_dir = run_output_dir / "EURUSD" / "analysis"
    assert summary.analysis_root == run_output_dir
    assert "EURUSD" in summary.per_pair
    artefacts = summary.per_pair["EURUSD"]
    assert artefacts.report_path is not None
    assert artefacts.report_path.exists()
    assert artefacts.plot_path is None
    assert artefacts.report_path.parent == expected_dir
    assert summary.failures == {}


def test_run_backtest_analysis_records_failures(tmp_path: Path):
    """Pairs with invalid trade files should be captured as warnings only."""

    run_output_dir = tmp_path / "run" / "output"
    good_trades = run_output_dir / "EURUSD" / "trades.parquet"
    bad_trades = run_output_dir / "GBPUSD" / "trades.parquet"
    _write_trades(good_trades)
    _write_trades(bad_trades, include_exit=False)  # missing column triggers validation error

    summary = run_backtest_analysis(run_output_dir, generate_plot=False, run_id="test-run")

    assert "EURUSD" in summary.per_pair
    assert "GBPUSD" in summary.failures
    assert summary.per_pair["EURUSD"].report_path is not None
