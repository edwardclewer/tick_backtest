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

import math
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from tick_backtest.data_feed.data_feed import DataFeed, NoMoreTicks
from tick_backtest.metrics.manager.metrics_manager import MetricsManager
from tick_backtest.position.position import Position
from tick_backtest.signals.signal_generator import SignalGenerator


class Backtest:
    """Single-run backtest driver coordinating feed, metrics, and signal."""

    def __init__(
        self,
        data_feed: DataFeed,
        signal_generator: SignalGenerator,
        metrics_manager: MetricsManager,
        output_base_path: Path,
        pip_size: float
    ) -> None:
        self.data_feed = data_feed
        self.signal_generator = signal_generator
        self.metrics_manager = metrics_manager
        self.output_base_path = output_base_path

        self.trades = []
        self.is_trade_open = False
        self.trade_opened_last_tick = False
        self.trade = Position()
        self.pip_size = pip_size
        self.logger = logging.getLogger(__name__)
        self.last_tick = None

    def run(self) -> None:
        processed = 0
        try:
            while True:
                tick = self.data_feed.tick()
                self._handle_tick(tick)
                processed += 1
        except NoMoreTicks:
            pass

        self._finish()

    def warmup(self, initial_tick, warmup_seconds) -> None:
        """Prime rolling metrics with historical data before trading."""
        # Initialise with first tick
        start_ts = self._to_datetime(initial_tick.timestamp)
        last_ts = start_ts
        metrics = self.metrics_manager.update(initial_tick)
        self.signal_generator.update(metrics, initial_tick, is_warmup=True)

        if warmup_seconds <= 0:
            return

        # Iterate through the backtest ticks
        try:
            while (last_ts - start_ts).total_seconds() < warmup_seconds:
                tick = self.data_feed.tick()
                last_ts = self._to_datetime(tick.timestamp)
                metrics = self.metrics_manager.update(tick)
                self.signal_generator.update(metrics, tick, is_warmup=True)
        except NoMoreTicks:
            self.logger.warning("data feed exhausted during warmup phase")

    def _handle_tick(self, tick) -> None:
        self.last_tick = tick
        just_filled = False
        if self.trade_opened_last_tick:
            just_filled = self._update_outstanding(tick)

        metrics = self.metrics_manager.update(tick)
        signal = self.signal_generator.update(metrics, tick)

        if not just_filled:
            self._close_position(tick, signal)

        if signal.should_open:
            self._open_position(tick, signal, metrics)

    def _update_outstanding(self, tick) -> bool:
        """Fill entry price/time for a trade opened on the prior tick."""
        fill_time = self._to_datetime(tick.timestamp)
        entry_price = float(tick.mid)
        self.trade.set_entry_fill(entry_price, fill_time)

        # Recompute TP/SL based on filled entry price to ensure they are anchored to the trade fill.
        entry_meta = self.trade.meta.get("entry_metadata") or {}
        if not isinstance(entry_meta, dict):
            entry_meta = {}

        raw_threshold = entry_meta.get("threshold", float("nan"))
        if isinstance(raw_threshold, (int, float)):
            threshold = float(raw_threshold)
        else:
            threshold = float("nan")

        signal_price = entry_meta.get("signal_price", entry_price)
        if not isinstance(signal_price, (int, float)) or not math.isfinite(float(signal_price)):
            signal_price = entry_price
        signal_price = float(signal_price)

        if math.isfinite(threshold) and threshold > 0.0:
            tp_mult = getattr(self.signal_generator, "tp_multiple", 1.0) or 1.0
            sl_mult = getattr(self.signal_generator, "sl_multiple", 1.0) or 1.0
            tp_mult = float(tp_mult)
            sl_mult = float(sl_mult)
            tp_offset = threshold * tp_mult
            sl_offset = threshold * sl_mult

            if self.trade.direction == 1:
                self.trade.tp = signal_price + tp_offset
                self.trade.sl = signal_price - sl_offset
            elif self.trade.direction == -1:
                self.trade.tp = signal_price - tp_offset
                self.trade.sl = signal_price + sl_offset

            entry_meta["threshold"] = threshold
            entry_meta["tp_price"] = self.trade.tp
            entry_meta["sl_price"] = self.trade.sl

        entry_meta["signal_price"] = signal_price
        self.trade.meta["entry_metadata"] = entry_meta

        self.trade_opened_last_tick = False
        return True

    def _open_position(self, tick, signal, metrics) -> None:
        """Open a new position based on the generated signal."""
        if not signal.should_open:
            return

        if self.is_trade_open:
            self.logger.debug(
                "ignored open signal while position active",
                extra={
                    "reason": getattr(signal, "reason", None),
                    "direction": getattr(signal, "direction", None),
                },
            )
            return

        entry_metrics = dict(metrics)
        meta = {
            "reason": getattr(signal, "reason", "threshold_reversion"),
            "entry_metrics": entry_metrics,
        }
        meta.update(entry_metrics)
        if signal.timeout_seconds is not None:
            meta["timeout_seconds"] = signal.timeout_seconds
        meta["signal_timestamp"] = self._to_datetime(tick.timestamp)
        meta["signal_price"] = float(tick.mid)
        if signal.entry_metadata:
            meta["entry_metadata"] = dict(signal.entry_metadata)

        tp = signal.tp
        if tp is not None:
            try:
                tp = float(tp)
            except (TypeError, ValueError):
                tp = None
            else:
                if not math.isfinite(tp):
                    tp = None

        sl = signal.sl
        if sl is not None:
            try:
                sl = float(sl)
            except (TypeError, ValueError):
                sl = None
            else:
                if not math.isfinite(sl):
                    sl = None

        self.trade = Position(
            tp=tp,
            sl=sl,
            direction=signal.direction,
            timeout_seconds=signal.timeout_seconds,
            meta=meta
        )

        self.is_trade_open = True
        self.trade_opened_last_tick = True

    def _finalize_trade(self, exit_price: float, exit_time: datetime, exit_reason: str) -> None:
        """Close trade, compute PnL, and log the completed record."""
        self.trade.close(exit_price, exit_time, self.pip_size, exit_reason)

        holding_seconds = None
        if self.trade.entry_time and self.trade.exit_time:
            holding_seconds = (self.trade.exit_time - self.trade.entry_time).total_seconds()

        record = {
            "pair": getattr(self.data_feed, "pair", ""),
            "entry_time": self.trade.entry_time,
            "exit_time": self.trade.exit_time,
            "timestamp_entry": self.trade.entry_time,
            "timestamp_exit": self.trade.exit_time,
            "direction": self.trade.direction,
            "entry_price": self.trade.entry_price,
            "exit_price": self.trade.exit_price,
            "pnl_pips": self.trade.pnl_pips,
            "holding_seconds": holding_seconds,
            "outcome_label": self.trade.outcome_label,
        }
        record.update(self.trade.meta)
        self.trades.append(record)
        self.is_trade_open = False

    def _close_position(self, tick, signal=None) -> None:
        """Close an open position if TP/SL breached."""
        if not self.is_trade_open:
            return

        price = float(tick.mid)
        current_time = self._to_datetime(tick.timestamp)
        timeout_hit = False
        hit_tp = hit_sl = False

        if signal is not None and getattr(signal, "should_close", False):
            exit_reason = signal.close_reason or "EXIT_SIGNAL"
            self._finalize_trade(float(price), current_time, exit_reason)
            return

        tp = self.trade.tp if isinstance(self.trade.tp, (int, float)) else None
        sl = self.trade.sl if isinstance(self.trade.sl, (int, float)) else None
        if tp is not None and not math.isfinite(float(tp)):
            tp = None
        if sl is not None and not math.isfinite(float(sl)):
            sl = None

        if self.trade.direction == 1:
            if tp is not None:
                hit_tp = price >= tp
            if sl is not None:
                hit_sl = price <= sl
        elif self.trade.direction == -1:
            if tp is not None:
                hit_tp = price <= tp
            if sl is not None:
                hit_sl = price >= sl
        else:
            raise ValueError(f"Invalid direction: {self.trade.direction}")

        if not (hit_tp or hit_sl):
            if (
                self.trade.timeout_seconds
                and self.trade.timeout_seconds > 0
                and self.trade.entry_time is not None
            ):
                elapsed = (current_time - self.trade.entry_time).total_seconds()
                if elapsed >= self.trade.timeout_seconds:
                    timeout_hit = True

        if not (hit_tp or hit_sl or timeout_hit):
            return

        if not timeout_hit and hit_tp and hit_sl:
            hit_sl = True
            hit_tp = False

        if timeout_hit:
            exit_price = price
            exit_reason = "TIMEOUT"
        else:
            exit_reason = "SL" if hit_sl else "TP"
            exit_price = tp if hit_tp else sl
            if exit_price is None:
                self.logger.error(
                    "stop triggered but no exit price derived; defaulting to mid",
                    extra={
                        "direction": self.trade.direction,
                        "hit_tp": hit_tp,
                        "hit_sl": hit_sl,
                        "tp": tp,
                        "sl": sl,
                    },
                )
                exit_price = price

        self._finalize_trade(float(exit_price), current_time, exit_reason)

    def _finish(self) -> None:
        """Persist captured trades to Parquet."""
        if not self.output_base_path:
            raise ValueError("Backtest has no output_base_path set")

        if self.is_trade_open and self.last_tick is not None:
            if self.trade_opened_last_tick:
                self._update_outstanding(self.last_tick)

            exit_time = self._to_datetime(self.last_tick.timestamp)
            exit_price = float(self.last_tick.mid)
            self._finalize_trade(exit_price, exit_time, "DATA_END")

        if not self.trades:
            pair = getattr(self.data_feed, "pair", "")
            suffix = pair if pair else "this data feed"
            self.logger.info("no trades executed; nothing to save", extra={"pair": suffix or None})
            return

        df = pd.DataFrame(self.trades)
        df.to_parquet(self.output_base_path, index=False)
        self.logger.info(
            "saved trades",
            extra={"trade_count": len(df), "output_path": str(self.output_base_path)},
        )

    @staticmethod
    def _to_datetime(ts) -> datetime:
        if isinstance(ts, datetime):
            return ts
        if hasattr(ts, "to_pydatetime"):
            return ts.to_pydatetime()
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
