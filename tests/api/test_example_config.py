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

from tick_backtest.api import example_config


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


def test_example_config_rejects_unknown_template() -> None:
    with pytest.raises(ValueError, match="unknown config template"):
        example_config(template="missing")
