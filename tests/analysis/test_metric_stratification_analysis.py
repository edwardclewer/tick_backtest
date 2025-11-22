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

"""Tests for backtest-level metric stratification orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tick_backtest.analysis.backtest_analysis import run_metric_stratification_analysis


def _write_manifest(run_root: Path, metrics_cfg: Path) -> None:
    manifest = {
        "configs": {
            "metrics": {
                "copied_path": str(metrics_cfg),
            }
        }
    }
    (run_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _write_metrics_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "metrics:",
                "  - name: z5m",
                "    type: zscore",
                "    enabled: true",
                "    params:",
                "      lookback_seconds: 300",
            ]
        ),
        encoding="utf-8",
    )


def _write_trades(path: Path, with_metrics: bool = True) -> None:
    periods = 200
    data = {
        "entry_time": pd.date_range("2024-01-01", periods=periods, freq="min", tz="UTC"),
        "exit_time": pd.date_range("2024-01-01", periods=periods, freq="min", tz="UTC") + pd.Timedelta(minutes=5),
        "pnl_pips": pd.Series(range(periods), dtype=float) - (periods / 2),
    }
    if with_metrics:
        data["z5m.z_score"] = pd.Series(range(periods), dtype=float) / 10.0
        data["z5m.rolling_residual"] = pd.Series(range(periods), dtype=float) / 20.0
    df = pd.DataFrame(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def test_metric_stratification_outputs(tmp_path: Path):
    run_root = tmp_path / "run"
    output_dir = run_root / "output"
    trades_path = output_dir / "EURUSD" / "trades.parquet"
    _write_trades(trades_path)

    metrics_cfg = run_root / "configs" / "metrics.yaml"
    _write_metrics_config(metrics_cfg)
    _write_manifest(run_root, metrics_cfg)

    summary = run_metric_stratification_analysis(
        output_dir,
        run_id="test-run",
    )

    assert summary.analysis_root == output_dir
    pair_dir = output_dir / "EURUSD" / "analysis" / "metric_stratification"
    csv_root = pair_dir / "csv"
    graph_root = pair_dir / "graphs"
    reports_root = pair_dir / "reports"

    assert csv_root.exists()
    assert graph_root.exists()
    assert reports_root.exists()

    expected_modes = {"fixed", "fd", "scott", "sigma", "nbins"}
    for mode in expected_modes:
        assert (csv_root / mode).exists()
        assert any((csv_root / mode).glob("*.csv"))
        assert (graph_root / mode).exists()
        assert any((graph_root / mode).glob("*.png"))

    for report in reports_root.glob("metric_report_*.md"):
        mode = report.stem.split("_")[-1]
        assert mode in expected_modes
        text = report.read_text(encoding="utf-8")
        assert "|" not in text
        assert "_No CSV" not in text
        assert "../graphs/" in text
        break
    else:
        pytest.fail("No compiled metric report generated")
    assert not (pair_dir / "md").exists()
    assert summary.failures == {}


def test_metric_stratification_outputs_without_tabulate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Fallback markdown generation should activate when tabulate is absent."""

    run_root = tmp_path / "run"
    output_dir = run_root / "output"
    trades_path = output_dir / "EURUSD" / "trades.parquet"
    _write_trades(trades_path)

    metrics_cfg = run_root / "configs" / "metrics.yaml"
    _write_metrics_config(metrics_cfg)
    _write_manifest(run_root, metrics_cfg)

    import pandas as pd

    monkeypatch.setattr(
        pd.DataFrame,
        "to_markdown",
        lambda *args, **kwargs: (_ for _ in ()).throw(ImportError("missing tabulate")),
    )

    summary = run_metric_stratification_analysis(
        output_dir,
        run_id="test-run",
    )

    pair_dir = output_dir / "EURUSD" / "analysis" / "metric_stratification"
    assert (pair_dir / "reports").exists()
    assert not (pair_dir / "md").exists()
    assert summary.failures == {}


def test_metric_stratification_records_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_root = tmp_path / "run"
    output_dir = run_root / "output"
    trades_path = output_dir / "EURUSD" / "trades.parquet"
    _write_trades(trades_path)

    metrics_cfg = run_root / "configs" / "metrics.yaml"
    _write_metrics_config(metrics_cfg)
    _write_manifest(run_root, metrics_cfg)

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    import tick_backtest.analysis.backtest_analysis as backtest_analysis

    monkeypatch.setattr(backtest_analysis, "run_metric_stratification", boom)

    summary = run_metric_stratification_analysis(output_dir, run_id="test-run")

    assert "EURUSD" in summary.failures
    assert "EURUSD" not in summary.per_pair
