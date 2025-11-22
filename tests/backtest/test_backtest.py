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

"""Unit tests for `backtest.backtest.Backtest`."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math

import pandas as pd
import pytest

from tick_backtest.backtest.backtest import Backtest
from tick_backtest.data_feed.data_feed import NoMoreTicks
from tick_backtest.position.position import Position
from tick_backtest.signals.signal_data import SignalData


class StubDataFeed:
    """Deterministic data feed that iterates through supplied ticks."""

    def __init__(self, ticks):
        self._ticks = iter(ticks)

    def tick(self):
        try:
            return next(self._ticks)
        except StopIteration as exc:
            raise NoMoreTicks from exc


@dataclass
class StubMetricsManager:
    """Metrics manager stub that returns a pre-seeded series of snapshots."""

    snapshots: list[dict]

    def __post_init__(self):
        self.updates = []

    def update(self, tick):
        self.updates.append(tick)
        if self.snapshots:
            return self.snapshots.pop(0)
        return {}


class StubSignalGenerator:
    """Signal generator stub yielding predetermined SignalData objects."""

    def __init__(self, signals):
        self._signals = iter(signals)

    def update(self, metrics, tick, *, is_warmup=False):
        try:
            return next(self._signals)
        except StopIteration:
            return SignalData()


def make_backtest(tmp_path, metrics_snapshots=None, signals=None, data_feed=None):
    snapshots = list(metrics_snapshots or [{}])
    manager = StubMetricsManager(snapshots)
    signal_generator = StubSignalGenerator(signals or [SignalData()])
    feed = data_feed or StubDataFeed([])
    return Backtest(
        data_feed=feed,
        signal_generator=signal_generator,
        metrics_manager=manager,
        output_base_path=tmp_path / "trades.parquet",
        pip_size=0.0001,
    ), manager


def test_backtest_warmup_handles_insufficient_data(tick_factory, caplog, tmp_path):
    """Expect warmup to warn and continue when feed exhausts early."""

    initial_tick = tick_factory()
    backtest, manager = make_backtest(
        tmp_path,
        metrics_snapshots=[{"metric.alpha": 1.0}],
        data_feed=StubDataFeed([]),
    )

    caplog.set_level(logging.WARNING)
    backtest.warmup(initial_tick=initial_tick, warmup_seconds=60)

    assert any("data feed exhausted during warmup phase" in rec.message for rec in caplog.records)
    assert manager.updates == [initial_tick]


def test_warmup_feeds_signal_generator(tick_factory, tmp_path):
    """Warmup should seed signal engines without emitting live entries."""

    start_dt = datetime(2015, 1, 1, tzinfo=timezone.utc)
    initial_tick = tick_factory(timestamp=start_dt)
    warmup_tick_1 = tick_factory(timestamp=start_dt + timedelta(seconds=20))
    warmup_tick_2 = tick_factory(timestamp=start_dt + timedelta(seconds=40))

    class RecordingSignalGenerator:
        def __init__(self):
            self.calls: list[bool] = []
            self.tp_multiple = 1.0
            self.sl_multiple = 1.0
            self._responses = iter([])

        def update(self, _metrics, _tick, *, is_warmup=False):
            self.calls.append(is_warmup)
            try:
                return next(self._responses)
            except StopIteration:
                return SignalData()

        def set_responses(self, responses):
            self._responses = iter(responses)

    metrics_snapshots = [{}, {}, {}]
    manager = StubMetricsManager(metrics_snapshots)
    signal_generator = RecordingSignalGenerator()
    feed = StubDataFeed([warmup_tick_1, warmup_tick_2])
    backtest = Backtest(
        data_feed=feed,
        signal_generator=signal_generator,
        metrics_manager=manager,
        output_base_path=tmp_path / "trades.parquet",
        pip_size=0.0001,
    )

    backtest.warmup(initial_tick=initial_tick, warmup_seconds=40)

    # Expect three warmup invocations (initial tick + two warmup ticks)
    assert signal_generator.calls == [True, True, True]

    # Next live tick should be processed with is_warmup=False
    live_tick = tick_factory(mid=1.2005, timestamp=start_dt + timedelta(seconds=60))
    signal_generator.set_responses(
        [
            SignalData(
                should_open=True,
                direction=1,
                tp=live_tick.mid + 0.0002,
                sl=live_tick.mid - 0.0002,
                reason="live_entry",
            )
        ]
    )
    manager.snapshots.append({})

    backtest._handle_tick(live_tick)

    assert signal_generator.calls[-1] is False
    assert backtest.is_trade_open


def test_open_position_records_metric_metadata(tick_factory, metrics_snapshot, tmp_path):
    """Validate trade metadata includes metric snapshot on entry."""

    tick = tick_factory()
    signal = SignalData(should_open=True, direction=1, tp=tick.mid + 0.0002, sl=tick.mid - 0.0002, reason="test")
    backtest, manager = make_backtest(
        tmp_path,
        metrics_snapshots=[metrics_snapshot],
        signals=[signal],
    )

    backtest._handle_tick(tick)

    assert backtest.is_trade_open
    assert backtest.trade.meta["reason"] == "test"
    for key, value in metrics_snapshot.items():
        stored = backtest.trade.meta[key]
        if all(isinstance(v, float) for v in (stored, value)) and math.isnan(stored) and math.isnan(value):
            continue
        assert stored == value
    # Entry fill deferred until next tick
    assert backtest.trade.entry_time is None
    assert backtest.trade.entry_price == 0.0
    assert "signal_timestamp" in backtest.trade.meta


def test_open_position_sanitizes_non_finite_stops(tick_factory, tmp_path):
    """NaN/inf TP-SL inputs from strategies should be treated as absent."""

    tick = tick_factory()
    signal = SignalData(
        should_open=True,
        direction=1,
        tp=float("nan"),
        sl=float("inf"),
        reason="bad-stops",
    )
    backtest, _ = make_backtest(
        tmp_path,
        signals=[signal],
    )

    backtest._handle_tick(tick)

    assert backtest.is_trade_open
    assert backtest.trade.tp is None
    assert backtest.trade.sl is None


def test_metrics_snapshot_persisted_into_trade_log(tick_factory, metrics_snapshot, tmp_path):
    """Ensure entry metrics are present on the saved trade record for post-hoc analysis."""

    entry_tick = tick_factory(mid=1.2000)
    fill_tick = tick_factory(mid=1.2005)
    exit_tick = tick_factory(mid=1.2020)
    signal = SignalData(
        should_open=True,
        direction=1,
        tp=exit_tick.mid,
        sl=entry_tick.mid - 0.0002,
        reason="metric-log",
    )

    backtest, manager = make_backtest(
        tmp_path,
        metrics_snapshots=[metrics_snapshot, metrics_snapshot.copy()],
        signals=[signal, SignalData()],
        data_feed=StubDataFeed([entry_tick, fill_tick, exit_tick]),
    )

    # First tick opens the trade with metrics snapshot
    backtest._handle_tick(entry_tick)
    assert backtest.is_trade_open
    assert backtest.trade.entry_time is None
    # Second tick fills entry
    backtest._handle_tick(fill_tick)
    assert backtest.is_trade_open
    # Third tick hits TP
    backtest._handle_tick(exit_tick)
    assert not backtest.is_trade_open

    assert len(backtest.trades) == 1
    trade = backtest.trades[0]
    assert trade["entry_time"] == Backtest._to_datetime(exit_tick.timestamp)
    for key in metrics_snapshot.keys():
        assert key in trade, f"missing metric {key} in trade record"


def test_open_position_applies_timeout(tick_factory, metrics_snapshot, tmp_path):
    tick = tick_factory()
    signal = SignalData(
        should_open=True,
        direction=1,
        tp=tick.mid + 0.0002,
        sl=tick.mid - 0.0002,
        reason="timeout-test",
        timeout_seconds=90.0,
    )
    backtest, _ = make_backtest(
        tmp_path,
        metrics_snapshots=[metrics_snapshot],
        signals=[signal],
    )

    backtest._handle_tick(tick)

    assert backtest.trade.timeout_seconds == pytest.approx(90.0)
    assert backtest.trade.meta["timeout_seconds"] == pytest.approx(90.0)


def test_open_signal_ignored_when_trade_active(tick_factory, tmp_path, caplog):
    """Second open intent while a trade is live should be rejected and logged."""

    start = datetime(2015, 1, 1, tzinfo=timezone.utc)
    first_tick = tick_factory(mid=1.2000, timestamp=start)
    second_tick = tick_factory(mid=1.2005, timestamp=start + timedelta(seconds=1))

    first_signal = SignalData(
        should_open=True,
        direction=1,
        tp=first_tick.mid + 0.0002,
        sl=first_tick.mid - 0.0002,
        reason="first",
    )
    second_signal = SignalData(
        should_open=True,
        direction=-1,
        tp=second_tick.mid - 0.0003,
        sl=second_tick.mid + 0.0003,
        reason="second",
    )

    backtest, _ = make_backtest(
        tmp_path,
        signals=[first_signal, second_signal],
    )

    caplog.set_level(logging.DEBUG, logger="tick_backtest.backtest.backtest")

    backtest._handle_tick(first_tick)
    assert backtest.is_trade_open
    existing_trade = backtest.trade

    backtest._handle_tick(second_tick)

    assert backtest.is_trade_open
    assert backtest.trade is existing_trade
    assert "ignored open signal while position active" in caplog.text


def test_close_position_handles_tp_sl_collisions(tick_factory, tmp_path):
    """Ensure TP/SL collision logic favours stop-loss path."""

    tick = tick_factory(bid=1.2345, ask=1.2345)
    backtest, _ = make_backtest(tmp_path)
    backtest.is_trade_open = True
    backtest.trade = Position(
        entry_time=datetime(2015, 1, 1, tzinfo=timezone.utc),
        entry_price=1.2335,
        tp=1.2345,
        sl=1.2345,
        direction=1,
    )
    backtest.trade.meta = {}

    backtest._close_position(tick)

    assert not backtest.is_trade_open
    assert backtest.trades[0]["exit_price"] == pytest.approx(1.2345)
    assert backtest.trades[0]["outcome_label"] == "SL"


def test_close_position_tolerates_missing_stops(tick_factory, tmp_path):
    """Strategies may omit stops; ensure backtest loop keeps trade alive until another exit trigger."""

    backtest, _ = make_backtest(tmp_path)
    backtest.is_trade_open = True
    entry_time = datetime(2015, 1, 1, tzinfo=timezone.utc)
    backtest.trade = Position(
        entry_time=entry_time,
        entry_price=1.2000,
        direction=1,
        meta={},
    )

    tick = tick_factory(mid=1.2010, timestamp=entry_time + timedelta(seconds=5))
    backtest._close_position(tick)

    assert backtest.is_trade_open
    assert backtest.trades == []


def test_close_position_honours_exit_signal(tick_factory, tmp_path):
    """Dynamic exit signals should close the trade at market price."""

    backtest, _ = make_backtest(tmp_path)
    backtest.is_trade_open = True
    entry_time = datetime(2015, 1, 1, tzinfo=timezone.utc)
    backtest.trade = Position(
        entry_time=entry_time,
        entry_price=1.2000,
        tp=1.2050,
        sl=1.1950,
        direction=1,
        meta={},
    )

    exit_signal = SignalData(should_close=True, close_reason="EXIT_RULE")
    exit_tick = tick_factory(mid=1.2025, timestamp=entry_time + timedelta(minutes=5))

    backtest._close_position(exit_tick, exit_signal)

    assert not backtest.is_trade_open
    assert len(backtest.trades) == 1
    trade = backtest.trades[0]
    assert trade["exit_price"] == pytest.approx(exit_tick.mid)
    assert trade["outcome_label"] == "EXIT_RULE"


def test_close_position_times_out(tick_factory, tmp_path):
    """Verify positions close when timeout elapses without TP/SL."""

    entry_time = datetime(2015, 1, 1, tzinfo=timezone.utc)
    backtest, _ = make_backtest(tmp_path)
    backtest.is_trade_open = True
    backtest.trade = Position(
        entry_time=entry_time,
        entry_price=1.2000,
        tp=None,
        sl=None,
        direction=1,
        timeout_seconds=30.0,
    )
    backtest.trade.meta = {"timeout_seconds": 30.0}

    exit_tick = tick_factory(
        mid=1.2005,
        timestamp=entry_time + timedelta(seconds=45),
    )

    backtest._close_position(exit_tick)

    assert not backtest.is_trade_open
    trade = backtest.trades[0]
    assert trade["exit_price"] == pytest.approx(1.2005)
    assert trade["outcome_label"] == "TIMEOUT"
    assert trade["holding_seconds"] == pytest.approx(45.0)


def test_finish_closes_open_trade_with_last_tick(tick_factory, tmp_path):
    """Open trades at end-of-data should be closed at the final observed price."""

    entry_tick = tick_factory(mid=1.2100)
    signal = SignalData(
        should_open=True,
        direction=1,
        tp=entry_tick.mid + 0.0005,
        sl=entry_tick.mid - 0.0005,
        reason="end-of-data",
    )
    backtest, _ = make_backtest(
        tmp_path,
        metrics_snapshots=[{"alpha": 1.0}],
        signals=[signal],
    )

    backtest._handle_tick(entry_tick)
    assert backtest.is_trade_open

    backtest._finish()

    trades_path = backtest.output_base_path
    assert trades_path.exists()
    df = pd.read_parquet(trades_path)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["outcome_label"] == "DATA_END"
    assert row["exit_price"] == pytest.approx(entry_tick.mid)
    assert row["entry_price"] == pytest.approx(entry_tick.mid)


def test_finish_persists_trades_to_parquet(tmp_path):
    """Check that completed trades are flushed to parquet output."""

    backtest, _ = make_backtest(tmp_path)
    backtest.trades = [
        {
            "entry_time": datetime(2015, 1, 1, tzinfo=timezone.utc),
            "exit_time": datetime(2015, 1, 1, 0, 5, tzinfo=timezone.utc),
            "direction": 1,
            "entry_price": 1.1000,
            "exit_price": 1.1010,
            "pnl_pips": 10.0,
            "outcome_label": "TP",
        }
    ]

    backtest._finish()

    trades_path = backtest.output_base_path
    assert trades_path.exists()
    df = pd.read_parquet(trades_path)
    assert set(["entry_time", "exit_time", "direction", "entry_price", "exit_price", "pnl_pips", "outcome_label"]).issubset(df.columns)
    assert len(df) == 1
