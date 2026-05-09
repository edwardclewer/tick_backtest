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
from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
MIN_BIN_COUNT = 100

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


def _write_parquet_atomic(df: pd.DataFrame, path: Path) -> None:
    tmp_path = path.with_name(f".{path.name}.tmp")
    df.to_parquet(tmp_path, index=False)
    tmp_path.replace(path)
