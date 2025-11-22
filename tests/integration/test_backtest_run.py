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

"""Integration tests for backtest orchestration and analysis outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from tick_backtest.analysis.trade_analysis import analyse_trades, load_trades
from tick_backtest.backtest.backtest_coordinator import BacktestCoordinator
from tick_backtest.config_parsers.backtest.config_dataclass import BacktestConfigData
from tick_backtest.config_parsers.strategy.config_parser import StrategyConfigParser
from tick_backtest.backtest.workflow import run_backtest
from tick_backtest.signals.signal_data import SignalData
from tests.helpers.parquet import write_tick_parquet
from tick_backtest.data_feed.validation import TickValidator


class CoordinatorMetricsStub:
    """Collect ticks and emit deterministic metric snapshots."""

    instances: list["CoordinatorMetricsStub"] = []

    def __init__(self, *_args, **_kwargs) -> None:
        self.ticks = []
        self.snapshots = []
        CoordinatorMetricsStub.instances.append(self)

    def update(self, tick):
        self.ticks.append(tick)
        snapshot = {"stub.metric": float(len(self.ticks))}
        self.snapshots.append(snapshot)
        return snapshot

    def current(self):
        return self.snapshots[-1] if self.snapshots else {}


class CoordinatorSignalStub:
    """Open a single long trade on the first tick."""

    instances: list["CoordinatorSignalStub"] = []

    def __init__(self, *, pip_size: float, **_kwargs) -> None:
        self.pip_size = pip_size
        self.triggered = False
        CoordinatorSignalStub.instances.append(self)

    def update(self, _metrics, tick, *, is_warmup=False):
        if is_warmup:
            return SignalData()
        if not self.triggered:
            self.triggered = True
            distance = 5 * self.pip_size
            return SignalData(
                should_open=True,
                direction=1,
                tp=tick.mid + distance,
                sl=tick.mid - distance,
                reason="stub_signal",
            )
        return SignalData()


@pytest.fixture(autouse=True)
def patch_coordinator_dependencies(monkeypatch):
    """Patch BacktestCoordinator dependencies with deterministic stubs."""

    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.MetricsManager",
        CoordinatorMetricsStub,
    )
    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.SignalGenerator",
        CoordinatorSignalStub,
    )
    CoordinatorMetricsStub.instances.clear()
    CoordinatorSignalStub.instances.clear()


def _prepare_tick_dataset(base_path: Path) -> None:
    pair_dir = base_path / "EURUSD"
    pair_dir.mkdir(parents=True, exist_ok=True)
    write_tick_parquet(
        pair_dir / "EURUSD_2015-01.parquet",
        [
            {
                "timestamp": datetime(2015, 1, 1, 0, 0, tzinfo=timezone.utc),
                "bid": 1.1000,
                "ask": 1.1002,
            },
            {
                "timestamp": datetime(2015, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
                "bid": 1.1010,
                "ask": 1.1012,
            },
            {
                "timestamp": datetime(2015, 1, 1, 0, 0, 2, tzinfo=timezone.utc),
                "bid": 1.0995,
                "ask": 1.0997,
            },
            {
                "timestamp": datetime(2015, 1, 1, 0, 0, 3, tzinfo=timezone.utc),
                "bid": 1.0994,
                "ask": 1.0996,
            },
        ],
    )


def _make_config(tmp_path: Path) -> BacktestConfigData:
    data_base = tmp_path / "data"
    output_base = tmp_path / "output"
    metrics_cfg = tmp_path / "metrics.yaml"
    strategy_cfg = tmp_path / "strategy.yaml"
    metrics_cfg.write_text('schema_version: "1.0"\nmetrics: []\n')
    strategy_cfg.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "strategy:",
                "  name: stub_strategy",
                "  entry:",
                "    name: entry",
                "    engine: stub",
                "    params: {}",
                "    predicates: []",
                "  exit:",
                "    name: exit",
                "    predicates: []",
                "",
            ]
        )
    )
    strategy_config = StrategyConfigParser(strategy_cfg).load()

    _prepare_tick_dataset(data_base)

    return BacktestConfigData(
        schema_version="1.0",
        pairs=["EURUSD"],
        year_start=2015,
        year_end=2015,
        month_start=1,
        month_end=1,
        pip_size=0.0001,
        warmup_seconds=0,
        data_base_path=data_base,
        output_base_path=output_base,
        metrics_config_path=metrics_cfg,
        strategy_config_path=strategy_cfg,
        strategy_config=strategy_config,
    )


def test_backtest_pipeline_executes_with_mock_data(tmp_path):
    """Simulate running the full pipeline using synthetic parquet inputs."""

    config = _make_config(tmp_path)
    coordinator = BacktestCoordinator(config, run_id="test-run")

    coordinator.run_backtests()

    trades_path = config.output_base_path / "EURUSD" / "trades.parquet"
    assert trades_path.exists()
    trades = pd.read_parquet(trades_path)
    assert len(trades) == 1
    assert trades.iloc[0]["outcome_label"] in {"TP", "SL"}
    assert CoordinatorSignalStub.instances[0].triggered is True
    assert CoordinatorMetricsStub.instances[0].ticks
    stats = coordinator.tick_validation_stats["EURUSD"].stats.as_dict()
    assert stats["accepted_ticks"] >= 1


def test_analysis_report_generated_after_backtest(tmp_path):
    """Ensure analytics step consumes backtest output and produces reports."""

    config = _make_config(tmp_path)
    coordinator = BacktestCoordinator(config, run_id="test-run")
    coordinator.run_backtests()

    trades_path = config.output_base_path / "EURUSD" / "trades.parquet"
    df = load_trades(trades_path)

    plot_path = tmp_path / "plot.png"
    report_path = tmp_path / "report.md"
    metrics = analyse_trades(
        df,
        trades_path=trades_path,
        plot_path=plot_path,
        report_path=report_path,
    )

    assert metrics["total_trades"] == 1
    assert report_path.exists()
    report_text = report_path.read_text()
    assert "**Trades file:**" in report_text
    if plot_path.exists():
        assert plot_path.stat().st_size > 0


def test_run_backtests_emits_manifest_and_run_directory(monkeypatch, tmp_path):
    """Full entrypoint should snapshot configs and emit immutable outputs."""

    output_base = tmp_path / "run_outputs"
    data_dir = tmp_path / "data"
    metrics_cfg = tmp_path / "metrics.yaml"
    strategy_cfg = tmp_path / "strategy.yaml"
    backtest_cfg = tmp_path / "backtest.yaml"

    data_dir.mkdir(parents=True, exist_ok=True)
    output_base.mkdir(parents=True, exist_ok=True)
    (data_dir / "EURUSD").mkdir(parents=True, exist_ok=True)

    metrics_cfg.write_text('schema_version: "1.0"\nmetrics: []\n', encoding="utf-8")
    strategy_cfg.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "strategy:",
                "  name: stub_strategy",
                "  entry:",
                "    name: entry",
                "    engine: stub",
                "    params: {}",
                "    predicates: []",
                "  exit:",
                "    name: exit",
                "    predicates: []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    backtest_cfg.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "pairs: [EURUSD]",
                f"start: 2015-01",
                f"end: 2015-01",
                "pip_size: 0.0001",
                "warmup_seconds: 0",
                f"data_base_path: \"{data_dir}\"",
                f"output_base_path: \"{output_base}\"",
                f"metrics_config_path: \"{metrics_cfg}\"",
                f"strategy_config_path: \"{strategy_cfg}\"",
                "",
            ]
        ),
        encoding="utf-8",
    )

    class StubCoordinator:
        def __init__(self, config, run_id):
            self.config = config
            self.run_id = run_id
            validator = TickValidator(pair="EURUSD")
            validator.stats.total_ticks = 1
            validator.stats.accepted_ticks = 1
            self.tick_validation_stats = {"EURUSD": validator}
            self.pair_failures = {}

        def run_backtests(self):
            pair_dir = self.config.output_base_path / "EURUSD"
            pair_dir.mkdir(parents=True, exist_ok=True)
            trades_path = pair_dir / "trades.parquet"
            df = pd.DataFrame([{"pair": "EURUSD", "pnl_pips": 1.0}])
            df.to_parquet(trades_path, index=False)

    monkeypatch.setattr("tick_backtest.backtest.workflow.BacktestCoordinator", StubCoordinator)
    monkeypatch.setattr("tick_backtest.backtest.workflow.generate_run_id", lambda: "test-run")

    run_backtest(backtest_cfg, profile=False, log_level="INFO")

    run_root = output_base / "test-run"
    output_dir = run_root / "output"

    trades_path = output_dir / "EURUSD" / "trades.parquet"
    assert trades_path.exists()

    manifest_path = run_root / "manifest.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "test-run"
    assert manifest["status"] == "completed"
    assert manifest["cli"]["config"] == str(backtest_cfg)
    assert manifest["outputs"][0]["rows"] == 1
    assert manifest["input_shards"]
    shard = manifest["input_shards"][0]
    assert shard["pair"] == "EURUSD"
    assert shard["sha256"] is None
    assert shard["rows"] is None
    assert "missing_file" in shard.get("errors", [])
    assert manifest["pair_failures"] == {}
    assert manifest["tick_validation"]["EURUSD"]["accepted_ticks"] == 1
    assert manifest["schema_versions"]["backtest"] == "1.0"
    assert manifest["schema_versions"]["metrics"] == "1.0"
    assert manifest["schema_versions"]["strategy"] == "1.0"

    log_path = run_root / "output" / "logs" / "test-run.log"
    assert log_path.exists()

    configs_dir = run_root / "configs"
    assert (configs_dir / backtest_cfg.name).exists()
    assert (configs_dir / metrics_cfg.name).exists()
    assert (configs_dir / strategy_cfg.name).exists()

    env_path = run_root / "environment.txt"
    assert env_path.exists()
