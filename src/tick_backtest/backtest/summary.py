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

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
MIN_BIN_COUNT = 100
STREAMING_BIN_COUNT = 40

PAIR_METRIC_COLUMNS = [
    "pair",
    "total_trades",
    "net_pnl_pips",
    "adjusted_pnl_pips",
    "expectancy_pips",
    "adjusted_expectancy_pips",
    "win_rate",
    "profit_factor",
    "daily_sharpe",
    "max_drawdown_pips",
    "avg_holding_minutes",
]

METRIC_BIN_COLUMNS = [
    "pair",
    "metric",
    "bin",
    "bin_left",
    "bin_right",
    "count",
    "avg_pnl",
    "std_pnl",
    "median_pnl",
    "win_rate",
    "ev_lo",
    "ev_hi",
]


def write_compact_summary(
    trades: pd.DataFrame,
    *,
    pair: str,
    output_dir: Path,
    extra_cost_pips_per_trade: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write compact pair metrics and metric-bin summaries without retaining trades."""
    output_dir.mkdir(parents=True, exist_ok=True)
    pair_df = pd.DataFrame(
        [_pair_metrics_record(trades, pair=pair, extra_cost=extra_cost_pips_per_trade)],
        columns=PAIR_METRIC_COLUMNS,
    )
    bins_df = pd.DataFrame(_metric_bin_records(trades, pair=pair), columns=METRIC_BIN_COLUMNS)
    _write_parquet_atomic(pair_df, output_dir / "pair_metrics.parquet")
    _write_parquet_atomic(bins_df, output_dir / "metric_bins.parquet")
    return pair_df, bins_df


class CompactSummaryAccumulator:
    """Online compact summary writer for sweep runs that should not retain trades."""

    def __init__(
        self,
        *,
        pair: str,
        output_dir: Path,
        extra_cost_pips_per_trade: float = 0.0,
        bin_count: int = STREAMING_BIN_COUNT,
    ) -> None:
        self.pair = pair
        self.output_dir = output_dir
        self.extra_cost_pips_per_trade = float(extra_cost_pips_per_trade)
        self.bin_count = max(4, int(bin_count))
        self.total_trades = 0
        self.net_pnl = 0.0
        self.gross_profit = 0.0
        self.gross_loss = 0.0
        self.win_count = 0
        self.holding_seconds_sum = 0.0
        self.holding_count = 0
        self.equity = 0.0
        self.peak_equity = 0.0
        self.max_drawdown = 0.0
        self.daily_pnl: dict[datetime, float] = {}
        self.metric_bins: dict[str, _OnlineMetricBins] = {}

    def add_trade(self, record: dict[str, Any]) -> None:
        raw_pnl = record.get("pnl_pips")
        if not isinstance(raw_pnl, (int, float)) or not math.isfinite(float(raw_pnl)):
            return
        pnl = float(raw_pnl)
        self.total_trades += 1
        self.net_pnl += pnl
        if pnl > 0.0:
            self.gross_profit += pnl
            self.win_count += 1
        elif pnl < 0.0:
            self.gross_loss += pnl

        self.equity += pnl
        self.peak_equity = max(self.peak_equity, self.equity)
        self.max_drawdown = min(self.max_drawdown, self.equity - self.peak_equity)

        holding = record.get("holding_seconds")
        if isinstance(holding, (int, float)) and math.isfinite(float(holding)):
            self.holding_seconds_sum += float(holding)
            self.holding_count += 1

        exit_time = _to_utc_datetime(record.get("exit_time"))
        if exit_time is not None:
            day = exit_time.replace(hour=0, minute=0, second=0, microsecond=0)
            self.daily_pnl[day] = self.daily_pnl.get(day, 0.0) + pnl

        for metric in _record_metric_columns(record):
            raw_value = record.get(metric)
            if not isinstance(raw_value, (int, float)):
                continue
            value = float(raw_value)
            if not math.isfinite(value):
                continue
            bins = self.metric_bins.get(metric)
            if bins is None:
                bins = _OnlineMetricBins(metric=metric, bin_count=self.bin_count)
                self.metric_bins[metric] = bins
            bins.add(value, pnl)

    def write(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        pair_df = pd.DataFrame([self._pair_metrics_record()], columns=PAIR_METRIC_COLUMNS)
        bin_records: list[dict[str, object]] = []
        for metric, bins in sorted(self.metric_bins.items()):
            bin_records.extend(bins.records(pair=self.pair, metric=metric))
        bins_df = pd.DataFrame(bin_records, columns=METRIC_BIN_COLUMNS)
        _write_parquet_atomic(pair_df, self.output_dir / "pair_metrics.parquet")
        _write_parquet_atomic(bins_df, self.output_dir / "metric_bins.parquet")
        return pair_df, bins_df

    def _pair_metrics_record(self) -> dict[str, object]:
        adjusted_pnl = self.net_pnl - self.extra_cost_pips_per_trade * self.total_trades
        avg_holding = (
            self.holding_seconds_sum / self.holding_count / 60.0
            if self.holding_count
            else math.nan
        )
        return {
            "pair": self.pair,
            "total_trades": self.total_trades,
            "net_pnl_pips": self.net_pnl,
            "adjusted_pnl_pips": adjusted_pnl,
            "expectancy_pips": self.net_pnl / self.total_trades if self.total_trades else math.nan,
            "adjusted_expectancy_pips": (
                adjusted_pnl / self.total_trades if self.total_trades else math.nan
            ),
            "win_rate": self.win_count / self.total_trades if self.total_trades else math.nan,
            "profit_factor": self._profit_factor(),
            "daily_sharpe": self._daily_sharpe(),
            "max_drawdown_pips": self.max_drawdown,
            "avg_holding_minutes": avg_holding,
        }

    def _profit_factor(self) -> float:
        if self.gross_loss < 0.0:
            return self.gross_profit / abs(self.gross_loss)
        if self.gross_profit > 0.0:
            return math.inf
        return math.nan

    def _daily_sharpe(self) -> float:
        if len(self.daily_pnl) < 2:
            return math.nan
        values = np.array([self.daily_pnl[key] for key in sorted(self.daily_pnl)], dtype=np.float64)
        std = float(values.std(ddof=1))
        if std == 0.0 or math.isnan(std):
            return math.nan
        return float(values.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR))


@dataclass
class _BinStats:
    count: int = 0
    sum_pnl: float = 0.0
    sumsq_pnl: float = 0.0
    wins: int = 0

    def add(self, pnl: float) -> None:
        self.count += 1
        self.sum_pnl += pnl
        self.sumsq_pnl += pnl * pnl
        if pnl > 0.0:
            self.wins += 1


class _OnlineMetricBins:
    def __init__(self, *, metric: str, bin_count: int) -> None:
        self.metric = metric
        self.bin_count = bin_count
        self.lo: float | None = None
        self.hi: float | None = None
        self.bins = [_BinStats() for _ in range(bin_count)]

    def add(self, value: float, pnl: float) -> None:
        if self.lo is None or self.hi is None:
            delta = max(abs(value) * 0.01, 1e-9)
            self.lo = value - delta
            self.hi = value + delta
        while value < self.lo or value > self.hi:
            self._expand(value)
        self.bins[self._index(value)].add(pnl)

    def _expand(self, value: float) -> None:
        assert self.lo is not None
        assert self.hi is not None
        center = 0.5 * (self.lo + self.hi)
        half_width = max(self.hi - self.lo, 1e-9)
        while value < center - half_width or value > center + half_width:
            half_width *= 2.0
        old_lo = self.lo
        old_hi = self.hi
        old_bins = self.bins
        self.lo = center - half_width
        self.hi = center + half_width
        self.bins = [_BinStats() for _ in range(self.bin_count)]
        old_width = (old_hi - old_lo) / self.bin_count
        for index, stats in enumerate(old_bins):
            if stats.count == 0:
                continue
            old_center = old_lo + (index + 0.5) * old_width
            target = self._index(old_center)
            merged = self.bins[target]
            merged.count += stats.count
            merged.sum_pnl += stats.sum_pnl
            merged.sumsq_pnl += stats.sumsq_pnl
            merged.wins += stats.wins

    def _index(self, value: float) -> int:
        assert self.lo is not None
        assert self.hi is not None
        if self.hi <= self.lo:
            return 0
        idx = int((value - self.lo) / (self.hi - self.lo) * self.bin_count)
        return min(self.bin_count - 1, max(0, idx))

    def records(self, *, pair: str, metric: str) -> list[dict[str, object]]:
        if self.lo is None or self.hi is None:
            return []
        width = (self.hi - self.lo) / self.bin_count
        records: list[dict[str, object]] = []
        for index, stats in enumerate(self.bins):
            if stats.count < MIN_BIN_COUNT:
                continue
            left = self.lo + index * width
            right = left + width
            avg = stats.sum_pnl / stats.count
            variance = (
                (stats.sumsq_pnl - stats.sum_pnl * stats.sum_pnl / stats.count) / (stats.count - 1)
                if stats.count > 1
                else math.nan
            )
            std = math.sqrt(max(0.0, variance)) if math.isfinite(variance) else math.nan
            se = std / math.sqrt(stats.count) if math.isfinite(std) else math.nan
            ev_lo = avg - 1.96 * se if math.isfinite(se) else math.nan
            ev_hi = avg + 1.96 * se if math.isfinite(se) else math.nan
            records.append(
                {
                    "pair": pair,
                    "metric": metric,
                    "bin": f"({left:.12g}, {right:.12g}]",
                    "bin_left": left,
                    "bin_right": right,
                    "count": stats.count,
                    "avg_pnl": avg,
                    "std_pnl": std,
                    "median_pnl": math.nan,
                    "win_rate": stats.wins / stats.count,
                    "ev_lo": ev_lo,
                    "ev_hi": ev_hi,
                }
            )
        return records


def _pair_metrics_record(trades: pd.DataFrame, *, pair: str, extra_cost: float) -> dict[str, object]:
    base: dict[str, object] = {
        "pair": pair,
        "total_trades": 0,
        "net_pnl_pips": 0.0,
        "adjusted_pnl_pips": 0.0,
        "expectancy_pips": math.nan,
        "adjusted_expectancy_pips": math.nan,
        "win_rate": math.nan,
        "profit_factor": math.nan,
        "daily_sharpe": math.nan,
        "max_drawdown_pips": 0.0,
        "avg_holding_minutes": math.nan,
    }
    if trades.empty or "pnl_pips" not in trades.columns:
        return base

    pnl = trades["pnl_pips"].astype(float)
    total_trades = int(len(trades))
    net_pnl = float(pnl.sum())
    adjusted_pnl = net_pnl - float(extra_cost) * total_trades
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(losses.sum())
    if gross_loss < 0:
        profit_factor = gross_profit / abs(gross_loss)
    elif gross_profit > 0:
        profit_factor = math.inf
    else:
        profit_factor = math.nan

    avg_holding = math.nan
    if "entry_time" in trades.columns and "exit_time" in trades.columns:
        entry = pd.to_datetime(trades["entry_time"], utc=True, errors="coerce")
        exit_ = pd.to_datetime(trades["exit_time"], utc=True, errors="coerce")
        holding = (exit_ - entry).dt.total_seconds()
        avg_holding = float(holding.mean() / 60.0)

    base.update(
        {
            "total_trades": total_trades,
            "net_pnl_pips": net_pnl,
            "adjusted_pnl_pips": adjusted_pnl,
            "expectancy_pips": float(net_pnl / total_trades),
            "adjusted_expectancy_pips": float(adjusted_pnl / total_trades),
            "win_rate": float((pnl > 0).mean()),
            "profit_factor": profit_factor,
            "daily_sharpe": _daily_sharpe(trades),
            "max_drawdown_pips": _max_drawdown(pnl),
            "avg_holding_minutes": avg_holding,
        }
    )
    return base


def _metric_bin_records(trades: pd.DataFrame, *, pair: str) -> list[dict[str, object]]:
    if trades.empty or "pnl_pips" not in trades.columns:
        return []

    records: list[dict[str, object]] = []
    for metric in _metric_columns(trades):
        try:
            summary = _stratify_metric(trades, metric=metric)
        except ValueError:
            continue
        for row in summary.to_dict(orient="records"):
            records.append(
                {
                    "pair": pair,
                    "metric": metric,
                    "bin": row.get("bin", ""),
                    "bin_left": row.get("bin_left", np.nan),
                    "bin_right": row.get("bin_right", np.nan),
                    "count": row.get("count", 0),
                    "avg_pnl": row.get("avg_pnl", np.nan),
                    "std_pnl": row.get("std_pnl", np.nan),
                    "median_pnl": row.get("median_pnl", np.nan),
                    "win_rate": row.get("win_rate", np.nan),
                    "ev_lo": row.get("ev_lo", np.nan),
                    "ev_hi": row.get("ev_hi", np.nan),
                }
            )
    return records


def _metric_columns(df: pd.DataFrame) -> list[str]:
    excluded = {
        "pnl_pips",
        "entry_price",
        "exit_price",
        "signal_price",
        "direction",
        "holding_seconds",
    }
    return [
        col
        for col in df.select_dtypes(include=[float, int]).columns
        if col not in excluded and not col.endswith("_timestamp")
    ]


def _record_metric_columns(record: dict[str, Any]) -> list[str]:
    excluded = {
        "pnl_pips",
        "entry_price",
        "exit_price",
        "signal_price",
        "direction",
        "holding_seconds",
    }
    return [
        key
        for key, value in record.items()
        if key not in excluded
        and not key.endswith("_timestamp")
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    ]


def _stratify_metric(df: pd.DataFrame, *, metric: str) -> pd.DataFrame:
    from tick_backtest.analysis.metric_stratification.nice_graphs import stratify_metric

    summary = stratify_metric(
        df,
        metric=metric,
        value_col="pnl_pips",
        mode="fixed",
        plot=False,
        min_count=MIN_BIN_COUNT,
        merge_to_min_count=True,
    )
    if summary.empty:
        return summary
    return summary[summary["count"].fillna(0) >= MIN_BIN_COUNT].copy()


def _daily_sharpe(df: pd.DataFrame) -> float:
    if "exit_time" not in df.columns or "pnl_pips" not in df.columns or df.empty:
        return math.nan
    exit_time = pd.to_datetime(df["exit_time"], utc=True, errors="coerce")
    working = pd.DataFrame({"exit_time": exit_time, "pnl_pips": df["pnl_pips"].astype(float)})
    working = working.dropna(subset=["exit_time"]).sort_values("exit_time")
    if working.empty:
        return math.nan
    daily = working.set_index("exit_time")["pnl_pips"].resample("1D").sum()
    if len(daily) < 2:
        return math.nan
    std = float(daily.std(ddof=1))
    if std == 0 or math.isnan(std):
        return math.nan
    return float(daily.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR))


def _max_drawdown(pnl: pd.Series) -> float:
    cumulative = pnl.cumsum()
    drawdown = cumulative - cumulative.cummax()
    return float(drawdown.min()) if not drawdown.empty else 0.0


def _to_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif hasattr(value, "to_pydatetime"):
        dt = value.to_pydatetime()
    else:
        try:
            dt = pd.to_datetime(value, utc=True).to_pydatetime()
        except Exception:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _write_parquet_atomic(df: pd.DataFrame, path: Path) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    df.to_parquet(tmp_path, index=False)
    tmp_path.replace(path)
