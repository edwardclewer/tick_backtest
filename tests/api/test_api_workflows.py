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

import pytest

import tick_backtest.api as api


def test_run_wraps_backtest_and_post_run_analysis(monkeypatch) -> None:
    calls: list[tuple[str, object, object]] = []

    def fake_run_backtest(*, config_path, output_root=None):
        calls.append(("run_backtest", config_path, output_root))
        return {"run_id": "run-123"}

    monkeypatch.setattr("tick_backtest.backtest.workflow.run_backtest", fake_run_backtest)

    api.run("config/backtest.yaml", output_root="custom-output")

    assert calls == [
        ("run_backtest", "config/backtest.yaml", "custom-output"),
    ]


def test_report_writes_report_and_stratification_beside_trades_file(monkeypatch, tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    captured: dict[str, object] = {}
    staged_output = tmp_path / "metric_stratification" / tmp_path.name

    def fake_run_trade_analysis(path, *, output_dir=None, configure_logs=False):
        captured["path"] = path
        captured["output_dir"] = output_dir
        captured["configure_logs"] = configure_logs

    def fake_run_metric_stratification(*, trade_file, output_root, configure_logs=False):
        captured["trade_file"] = trade_file
        captured["strat_output_root"] = output_root
        captured["strat_configure_logs"] = configure_logs
        staged_output.mkdir(parents=True, exist_ok=True)
        (staged_output / "reports").mkdir()
        (staged_output / "reports" / "summary.md").write_text("ok", encoding="utf-8")

    monkeypatch.setattr("tick_backtest.analysis.trade_analysis.run_trade_analysis", fake_run_trade_analysis)
    monkeypatch.setattr(
        "tick_backtest.analysis.metric_stratification.run_metric_stratification",
        fake_run_metric_stratification,
    )

    api.report(trades_path)

    assert captured == {
        "path": trades_path,
        "output_dir": tmp_path,
        "configure_logs": False,
        "trade_file": trades_path,
        "strat_output_root": tmp_path / "metric_stratification",
        "strat_configure_logs": False,
    }
    assert not staged_output.exists()
    assert (tmp_path / "metric_stratification" / "reports" / "summary.md").is_file()


def test_report_raises_if_metric_stratification_output_is_missing(monkeypatch, tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    monkeypatch.setattr(
        "tick_backtest.analysis.trade_analysis.run_trade_analysis",
        lambda *args, **kwargs: None,
    )

    def fake_run_metric_stratification(*, trade_file, output_root, configure_logs=False):
        output_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "tick_backtest.analysis.metric_stratification.run_metric_stratification",
        fake_run_metric_stratification,
    )

    with pytest.raises(RuntimeError, match="output was not created"):
        api.report(trades_path)


def test_analyze_runs_trade_regression_analysis(monkeypatch, tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    captured: dict[str, object] = {}

    def fake_run_trade_regression_analysis(trades_path_arg, *, output_dir=None, target_column="pnl_pips"):
        captured["trades_path"] = trades_path_arg
        captured["output_dir"] = output_dir
        captured["target_column"] = target_column

    monkeypatch.setattr(
        "tick_backtest.analysis.run_trade_regression_analysis",
        fake_run_trade_regression_analysis,
    )

    api.analyze(trades_path)

    assert captured == {
        "trades_path": trades_path,
        "output_dir": tmp_path / "multivariate_analysis",
        "target_column": "pnl_pips",
    }
