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

"""Tests for `backtest.backtest_coordinator.BacktestCoordinator`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, List

import pandas as pd
import pytest

from tick_backtest.backtest.backtest_coordinator import BacktestCoordinator
from tick_backtest.config_parsers.backtest.config_dataclass import BacktestConfigData
from tick_backtest.config_parsers.strategy.config_parser import StrategyConfigParser
from tick_backtest.data_feed.data_feed import NoMoreTicks
from tick_backtest.exceptions import DataFeedError
from tick_backtest.data_feed.validation import ValidatingDataFeed
from tick_backtest.data_feed.tick import Tick
from tick_backtest.signals.signal_data import SignalData


def _make_config(tmp_path: Path, pairs: List[str]) -> BacktestConfigData:
    data_base = tmp_path / "data"
    output_base = tmp_path / "output"
    metrics_cfg = tmp_path / "metrics.yaml"
    strategy_cfg = tmp_path / "strategy.yaml"
    data_base.mkdir(parents=True, exist_ok=True)
    output_base.mkdir(parents=True, exist_ok=True)
    metrics_cfg.write_text('schema_version: "1.0"\nmetrics: []\n')
    strategy_cfg.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "strategy:",
                "  name: test_strategy",
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

    return BacktestConfigData(
        schema_version="1.0",
        pairs=pairs,
        year_start=2015,
        year_end=2015,
        month_start=1,
        month_end=1,
        pip_size=0.0001,
        warmup_seconds=120,
        data_base_path=data_base,
        output_base_path=output_base,
        metrics_config_path=metrics_cfg,
        strategy_config_path=strategy_cfg,
        strategy_config=strategy_config,
    )


def test_run_backtests_iterates_over_pairs(monkeypatch, tmp_path, caplog):
    """Coordinator should invoke `_run_backtest` once per configured pair."""

    pairs = ["EURUSD", "GBPUSD"]
    config = _make_config(tmp_path, pairs)
    coordinator = BacktestCoordinator(config, run_id="test-run")

    invoked: list[str] = []

    def fake_run_backtest(self, pair: str) -> None:
        invoked.append(pair)

    monkeypatch.setattr(BacktestCoordinator, "_run_backtest", fake_run_backtest, raising=False)

    caplog.set_level(logging.INFO)
    coordinator.run_backtests()

    assert invoked == pairs
    messages = [record.message for record in caplog.records]
    assert any("starting pair backtest" in message for message in messages)
    assert any("all backtests complete" in message for message in messages)


def test_run_backtest_skips_when_no_ticks_available(monkeypatch, tmp_path, caplog):
    """Expect a friendly message when the data feed is empty."""

    class EmptyFeed:
        def __init__(self, *args, **kwargs):
            self.pair = kwargs.get("pair", "UNKNOWN")

        def tick(self):
            raise NoMoreTicks

    class StubMetricsManager:
        def __init__(self, *_args, **_kwargs):
            pass

    class StubSignalGenerator:
        def __init__(self, *args, **kwargs):
            pass

    def fail_backtest_ctor(*_args, **_kwargs):
        raise AssertionError("Backtest should not be instantiated when feed is empty")

    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.DataFeed", EmptyFeed
    )
    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.MetricsManager", StubMetricsManager
    )
    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.SignalGenerator", StubSignalGenerator
    )
    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.Backtest", fail_backtest_ctor
    )

    config = _make_config(tmp_path, ["EURUSD"])
    coordinator = BacktestCoordinator(config, run_id="test-run")

    caplog.set_level(logging.WARNING)
    coordinator._run_backtest("EURUSD")

    assert any("no data available" in record.message for record in caplog.records)
    assert (config.output_base_path / "EURUSD").is_dir()


def test_run_backtest_wires_dependencies_and_runs(monkeypatch, tmp_path):
    """Ensure `Backtest` receives instantiated dependencies and executes."""

    class SequenceFeed:
        def __init__(self, *args, **kwargs):
            self.calls = 0
            self.pair = kwargs["pair"]
            self.config = kwargs
            ts = pd.Timestamp(datetime(2015, 1, 1, tzinfo=timezone.utc))
            ts_seconds = ts.timestamp()
            self._ticks: Iterator[Tick] = iter(
                [
                    Tick(timestamp=ts_seconds, bid=1.1000, ask=1.1002, mid=1.1001),
                ]
            )

        def tick(self) -> Tick:
            self.calls += 1
            try:
                return next(self._ticks)
            except StopIteration as exc:
                raise NoMoreTicks from exc

    class RecordingMetricsManager:
        def __init__(self, path: Path):
            self.path = path

    class RecordingSignalGenerator:
        def __init__(self, *, pip_size: float, strategy_config=None):
            self.pip_size = pip_size
            self.strategy_config = strategy_config
            self.tp_multiple = 1.0
            self.sl_multiple = 1.0

        def update(self, _metrics, _tick, *, is_warmup=False):
            return SignalData()

    class RecordingBacktest:
        instances: list["RecordingBacktest"] = []

        def __init__(self, *, data_feed, signal_generator, metrics_manager, output_base_path, pip_size):
            self.data_feed = data_feed
            self.signal_generator = signal_generator
            self.metrics_manager = metrics_manager
            self.output_base_path = output_base_path
            self.pip_size = pip_size
            self.warmup_called_with: tuple[Any, Any] | None = None
            self.run_called = False
            RecordingBacktest.instances.append(self)

        def warmup(self, *, initial_tick, warmup_seconds):
            self.warmup_called_with = (initial_tick, warmup_seconds)

        def run(self):
            self.run_called = True

    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.DataFeed", SequenceFeed
    )
    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.MetricsManager", RecordingMetricsManager
    )
    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.SignalGenerator", RecordingSignalGenerator
    )
    monkeypatch.setattr(
        "tick_backtest.backtest.backtest_coordinator.Backtest", RecordingBacktest
    )

    config = _make_config(tmp_path, ["EURUSD"])
    coordinator = BacktestCoordinator(config, run_id="test-run")

    coordinator._run_backtest("EURUSD")

    instance = RecordingBacktest.instances.pop()
    assert instance.warmup_called_with is not None
    initial_tick, warmup_seconds = instance.warmup_called_with
    assert isinstance(initial_tick, Tick)
    assert warmup_seconds == config.warmup_seconds
    assert instance.run_called is True
    assert instance.metrics_manager.path == config.metrics_config_path
    assert instance.signal_generator.pip_size == config.pip_size
    assert instance.output_base_path == config.output_base_path / "EURUSD" / "trades.parquet"
    assert (config.output_base_path / "EURUSD").is_dir()
    assert isinstance(instance.data_feed, ValidatingDataFeed)
    assert "EURUSD" in coordinator.tick_validation_stats


def test_run_backtests_skips_bad_pair(monkeypatch, tmp_path):
    class WorkingFeed:
        def __init__(self, *args, **kwargs):
            self.pair = kwargs["pair"]
            self._emitted = False

        def tick(self):
            if self._emitted:
                raise NoMoreTicks
            self._emitted = True
            return Tick(timestamp=1.0, bid=1.0, ask=2.0, mid=1.5)

    def feed_factory(*args, **kwargs):
        if kwargs.get("pair") == "BAD":
            raise DataFeedError("missing data file")
        return WorkingFeed(*args, **kwargs)

    class DummyMetrics:
        def __init__(self, *_args, **_kwargs):
            pass

    class DummySignal:
        def __init__(self, *args, **kwargs):
            pass

        def update(self, *_args, **_kwargs):
            return SignalData()

    class DummyBacktest:
        def __init__(self, *, data_feed, **_kwargs):
            self.data_feed = data_feed

        def warmup(self, *, initial_tick, warmup_seconds):
            pass

        def run(self):
            pass

    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.DataFeed", feed_factory)
    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.MetricsManager", DummyMetrics)
    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.SignalGenerator", DummySignal)
    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.Backtest", DummyBacktest)

    config = _make_config(tmp_path, ["GOOD", "BAD"])
    coordinator = BacktestCoordinator(config, run_id="test-run")

    coordinator.run_backtests()

    assert "BAD" in coordinator.pair_failures
    assert "GOOD" in coordinator.tick_validation_stats
    assert coordinator.tick_validation_stats["GOOD"].stats.accepted_ticks >= 0


def test_run_backtest_records_runtime_failure(monkeypatch, tmp_path):
    """Runtime failures within Backtest should be captured per pair without aborting."""

    class SingleTickFeed:
        def __init__(self, *args, **kwargs):
            self.pair = kwargs["pair"]
            self._consumed = False

        def tick(self):
            if self._consumed:
                raise NoMoreTicks
            self._consumed = True
            return Tick(timestamp=1.0, bid=1.0, ask=2.0, mid=1.5)

    class StubMetrics:
        def __init__(self, *_args, **_kwargs):
            pass

    class StubSignal:
        def __init__(self, *args, **kwargs):
            pass

        def update(self, *_args, **_kwargs):
            return SignalData()

    class FailingBacktest:
        def __init__(self, *, data_feed, **_kwargs):
            self.data_feed = data_feed

        def warmup(self, *, initial_tick, warmup_seconds):
            assert initial_tick is not None
            assert warmup_seconds >= 0

        def run(self):
            raise RuntimeError("backtest failure")

    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.DataFeed", SingleTickFeed)
    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.MetricsManager", StubMetrics)
    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.SignalGenerator", StubSignal)
    monkeypatch.setattr("tick_backtest.backtest.backtest_coordinator.Backtest", FailingBacktest)

    config = _make_config(tmp_path, ["EURUSD"])
    coordinator = BacktestCoordinator(config, run_id="test-run")

    coordinator._run_backtest("EURUSD")

    assert "EURUSD" in coordinator.pair_failures
    assert "backtest failure" in coordinator.pair_failures["EURUSD"]
    assert "EURUSD" in coordinator.tick_validation_stats
