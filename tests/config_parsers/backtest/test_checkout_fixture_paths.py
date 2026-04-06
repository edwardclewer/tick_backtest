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

from __future__ import annotations

from pathlib import Path

import pytest

from tick_backtest.config_parsers.backtest.config_parser import BacktestConfigParser


@pytest.mark.checkout_only
def test_checkout_backtest_fixture_resolves_repo_paths() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "src" / "tick_backtest" / "config" / "backtest" / "test_backtest.yaml"
    if not fixture_path.exists():
        pytest.skip("checkout-only fixture is not present in installed-package test environments")

    cfg = BacktestConfigParser().parse_config(fixture_path)

    assert cfg.data_base_path == (repo_root / "tests" / "test_data").resolve()
    assert cfg.metrics_config_path == (
        repo_root / "src" / "tick_backtest" / "config" / "metrics" / "test_metrics.yaml"
    ).resolve()
    assert cfg.strategy_config_path == (
        repo_root / "src" / "tick_backtest" / "config" / "strategy" / "test_strategy.yaml"
    ).resolve()
