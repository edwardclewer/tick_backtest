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

from tick_backtest import cli


def test_cli_help_includes_public_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "run" in captured.out
    assert "report" in captured.out
    assert "analyze" in captured.out
    assert "example-config" in captured.out


def test_cli_run_dispatches_to_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(config_path, *, output_root=None) -> None:
        captured["config_path"] = config_path
        captured["output_root"] = output_root

    monkeypatch.setattr("tick_backtest.api.run", fake_run)

    exit_code = cli.main(["run", "config/backtest.yaml", "--output-root", "output-root"])

    assert exit_code == 0
    assert captured == {
        "config_path": Path("config/backtest.yaml"),
        "output_root": Path("output-root"),
    }


def test_cli_report_dispatches_to_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_report(trades_path) -> None:
        captured["trades_path"] = trades_path

    monkeypatch.setattr("tick_backtest.api.report", fake_report)

    exit_code = cli.main(["report", "runs/EURUSD/trades.parquet"])

    assert exit_code == 0
    assert captured == {"trades_path": Path("runs/EURUSD/trades.parquet")}


def test_cli_analyze_dispatches_to_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_analyze(trades_path) -> None:
        captured["trades_path"] = trades_path

    monkeypatch.setattr("tick_backtest.api.analyze", fake_analyze)

    exit_code = cli.main(["analyze", "runs/EURUSD/trades.parquet"])

    assert exit_code == 0
    assert captured == {"trades_path": Path("runs/EURUSD/trades.parquet")}


def test_cli_example_config_dispatches_to_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_example_config(*, dest=None, template="minimal") -> None:
        captured["dest"] = dest
        captured["template"] = template

    monkeypatch.setattr("tick_backtest.api.example_config", fake_example_config)

    exit_code = cli.main(["example-config", "--dest", "examples", "--template", "minimal"])

    assert exit_code == 0
    assert captured == {
        "dest": Path("examples"),
        "template": "minimal",
    }
