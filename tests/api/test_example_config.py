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

import logging
from pathlib import Path
from typing import cast

import pytest

from tick_backtest.api import example_config
from tick_backtest.backtest.workflow import run_backtest


def test_example_config_prints_backtest_template(capsys: pytest.CaptureFixture[str]) -> None:
    example_config()
    captured = capsys.readouterr()
    assert 'schema_version: "1.0"' in captured.out
    assert 'metrics_config_path: "./metrics.yaml"' in captured.out
    assert 'strategy_config_path: "./strategy.yaml"' in captured.out


def test_example_config_writes_template_set(tmp_path: Path) -> None:
    example_config(tmp_path)
    assert (tmp_path / "backtest.yaml").is_file()
    assert (tmp_path / "metrics.yaml").is_file()
    assert (tmp_path / "strategy.yaml").is_file()
    metrics_text = (tmp_path / "metrics.yaml").read_text(encoding="utf-8")
    assert "name: z30m" in metrics_text
    assert "name: tick_rate_30s" in metrics_text
    assert "window_seconds: 30" in metrics_text
    strategy_text = (tmp_path / "strategy.yaml").read_text(encoding="utf-8")
    assert "name: threshold_reversion_strategy" in strategy_text
    assert "name: threshold_reversion_entry" in strategy_text
    assert "lookback_seconds: 1800" in strategy_text
    assert "metric: tick_rate_30s.tick_rate_per_min" in strategy_text


def test_example_config_writes_demo_project_with_demo_data(tmp_path: Path) -> None:
    example_config(tmp_path, include_demo_data=True)
    backtest_text = (tmp_path / "backtest.yaml").read_text(encoding="utf-8")
    assert 'data_base_path: "./demo_data"' in backtest_text
    assert 'output_base_path: "./output"' in backtest_text
    assert (tmp_path / "metrics.yaml").is_file()
    assert (tmp_path / "strategy.yaml").is_file()
    assert (tmp_path / "demo_data" / "EURUSD" / "EURUSD_2000-01.parquet").is_file()
    assert (tmp_path / "demo_data" / "GBPUSD" / "GBPUSD_2000-02.parquet").is_file()


def test_example_config_demo_project_runs_end_to_end(tmp_path: Path) -> None:
    example_config(tmp_path, include_demo_data=True)

    result = run_backtest(tmp_path / "backtest.yaml", log_level=logging.WARNING)

    run_root = Path(cast(str, result["run_root"]))
    manifest_path = Path(cast(str, result["manifest_path"]))
    assert run_root.is_dir()
    assert manifest_path.is_file()
    assert (run_root / "output" / "EURUSD" / "trades.parquet").is_file()
    assert (run_root / "output" / "GBPUSD" / "trades.parquet").is_file()


def test_example_config_requires_dest_when_demo_data_is_requested() -> None:
    with pytest.raises(ValueError, match="dest is required"):
        example_config(include_demo_data=True)


def test_example_config_rejects_unknown_template() -> None:
    with pytest.raises(ValueError, match="unknown config template"):
        example_config(template="missing")
