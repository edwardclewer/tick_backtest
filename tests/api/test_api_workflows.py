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
        return {
            "run_id": "run-123",
            "output_dir": Path("/tmp/backtests/run-123/output"),
            "manifest": {"configs": {"metrics": {"copied_path": "/tmp/backtests/run-123/configs/metrics.yaml"}}},
        }

    def fake_run_backtest_analysis(output_dir, *, run_id=None):
        calls.append(("run_backtest_analysis", output_dir, run_id))

    def fake_run_metric_stratification_analysis(output_dir, *, metrics_config_path=None, run_id=None):
        calls.append(("run_metric_stratification_analysis", output_dir, (metrics_config_path, run_id)))

    monkeypatch.setattr("tick_backtest.backtest.workflow.run_backtest", fake_run_backtest)
    monkeypatch.setattr("tick_backtest.analysis.run_backtest_analysis", fake_run_backtest_analysis)
    monkeypatch.setattr(
        "tick_backtest.analysis.run_metric_stratification_analysis",
        fake_run_metric_stratification_analysis,
    )

    api.run("config/backtest.yaml", output_root="custom-output")

    assert calls == [
        ("run_backtest", "config/backtest.yaml", "custom-output"),
        ("run_backtest_analysis", Path("/tmp/backtests/run-123/output"), "run-123"),
        (
            "run_metric_stratification_analysis",
            Path("/tmp/backtests/run-123/output"),
            ("/tmp/backtests/run-123/configs/metrics.yaml", "run-123"),
        ),
    ]


def test_run_raises_when_workflow_returns_no_output_dir(monkeypatch) -> None:
    def fake_run_backtest(*, config_path, output_root=None):
        return {"run_id": "run-123", "manifest": {}}

    monkeypatch.setattr("tick_backtest.backtest.workflow.run_backtest", fake_run_backtest)

    with pytest.raises(RuntimeError, match="no output directory"):
        api.run("config/backtest.yaml")


def test_report_writes_beside_trades_file(monkeypatch, tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    captured: dict[str, object] = {}

    def fake_run_trade_analysis(path, *, output_dir=None, configure_logs=False):
        captured["path"] = path
        captured["output_dir"] = output_dir
        captured["configure_logs"] = configure_logs

    monkeypatch.setattr("tick_backtest.analysis.trade_analysis.run_trade_analysis", fake_run_trade_analysis)

    api.report(trades_path)

    assert captured == {
        "path": trades_path,
        "output_dir": tmp_path,
        "configure_logs": False,
    }


def test_analyze_flattens_metric_stratification_output(monkeypatch, tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"
    output_root = tmp_path / "metric_stratification"
    staged_output = output_root / tmp_path.name

    def fake_run_metric_stratification(*, trade_file, output_root, configure_logs=False):
        assert trade_file == trades_path
        assert output_root == tmp_path / "metric_stratification"
        assert configure_logs is False
        staged_output.mkdir(parents=True, exist_ok=True)
        (staged_output / "reports").mkdir()
        (staged_output / "reports" / "summary.md").write_text("ok", encoding="utf-8")
        (staged_output / "csv").mkdir()
        (staged_output / "csv" / "metric.csv").write_text("value\n1\n", encoding="utf-8")

    monkeypatch.setattr(
        "tick_backtest.analysis.metric_stratification.run_metric_stratification",
        fake_run_metric_stratification,
    )

    api.analyze(trades_path)

    assert not staged_output.exists()
    assert (output_root / "reports" / "summary.md").is_file()
    assert (output_root / "csv" / "metric.csv").is_file()


def test_analyze_raises_if_workflow_creates_no_expected_output(monkeypatch, tmp_path: Path) -> None:
    trades_path = tmp_path / "trades.parquet"

    def fake_run_metric_stratification(*, trade_file, output_root, configure_logs=False):
        output_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "tick_backtest.analysis.metric_stratification.run_metric_stratification",
        fake_run_metric_stratification,
    )

    with pytest.raises(RuntimeError, match="output was not created"):
        api.analyze(trades_path)
