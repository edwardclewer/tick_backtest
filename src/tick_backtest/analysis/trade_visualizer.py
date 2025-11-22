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

import argparse
import logging
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
import pyarrow.parquet as pq


"""
USAGE

python analysis/trade_visualizer.py \
  --trades output/backtests/EURUSD/trades.parquet \
  --ticks-root /path/to/dukascopy_data/EURUSD \
  [--trade-index 123] \
  [--seed 42] \
  [--output plots/example.png] \
  [--padding-seconds 300] \
  [--log-file run.log]
"""


@dataclass
class TradeRecord:
    index: int                      # NEW: the row index used
    pair: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: int
    entry_price: float
    exit_price: float
    tp: Optional[float]
    sl: Optional[float]
    reference_price: Optional[float]
    threshold: Optional[float]
    reference_age: Optional[float]
    pnl_pips: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Visualise a random trade with surrounding tick data."
    )
    parser.add_argument(
        "--trades",
        type=Path,
        required=True,
        help="Path to trades.parquet for a single pair.",
    )
    parser.add_argument(
        "--ticks-root",
        type=Path,
        required=True,
        help="Root directory containing tick parquet files organised by pair/year.",
    )
    parser.add_argument(
        "--trade-index",
        type=int,
        default=None,
        help="Specific trade index to plot. Leave blank to sample randomly.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed when sampling trades.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to save the generated plot. Defaults to showing interactively.",
    )
    parser.add_argument(
        "--padding-seconds",
        type=int,
        default=None,
        help="Override time padding before/after trade. Defaults to trade duration.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help=(
            "Path to write a run log (seed, chosen trade, trade metrics, "
            "padding/window, tick counts). Defaults to OUTPUT with .log extension "
            "if --output is provided, else <trades_dir>/trade_visualizer.log."
        ),
    )
    return parser.parse_args()


def load_trades(trades_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(trades_path)
    if df.empty:
        raise ValueError(f"Trades file {trades_path} contains no rows")
    if {"entry_time", "exit_time"}.difference(df.columns):
        raise ValueError("Trades parquet must include entry_time and exit_time columns")
    df["entry_time"] = pd.to_datetime(df["entry_time"], utc=True)
    df["exit_time"] = pd.to_datetime(df["exit_time"], utc=True)
    return df.reset_index(drop=True)


def choose_trade(
    df: pd.DataFrame,
    trade_index: Optional[int],
    seed: Optional[int],
    trades_path: Optional[Path] = None,
) -> TradeRecord:
    if trade_index is None:
        rng = random.Random(seed)
        idx = rng.randrange(len(df))
    else:
        if not 0 <= trade_index < len(df):
            raise IndexError(f"Trade index {trade_index} out of bounds (0 <= idx < {len(df)})")
        idx = trade_index

    row = df.iloc[idx]
    tp = row.get("reversion_30m.tp_price", row.get("tp_price", row.get("tp")))
    sl = row.get("reversion_30m.sl_price", row.get("sl_price", row.get("sl")))
    reference_price = row.get("reversion_30m.reference_price")
    threshold = row.get("reversion_30m.threshold")
    reference_age = row.get("reversion_30m.reference_age_seconds")
    pair = row.get("pair", "")
    if (not pair or pd.isna(pair)) and trades_path is not None:
        pair = trades_path.parent.name

    return TradeRecord(
        index=int(idx),  # NEW
        pair=pair,
        entry_time=row["entry_time"],
        exit_time=row["exit_time"],
        direction=int(row.get("direction", 0)),
        entry_price=float(row.get("entry_price", float("nan"))),
        exit_price=float(row.get("exit_price", float("nan"))),
        tp=float(tp) if pd.notna(tp) else None,
        sl=float(sl) if pd.notna(sl) else None,
        reference_price=float(reference_price) if pd.notna(reference_price) else None,
        threshold=float(threshold) if pd.notna(threshold) else None,
        reference_age=float(reference_age) if pd.notna(reference_age) else None,
        pnl_pips=float(row.get("pnl_pips", float("nan"))),
    )


def load_tick_slice(ticks_root: Path, trade: TradeRecord, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    pair_dir = ticks_root / trade.pair
    if not pair_dir.exists():
        raise FileNotFoundError(f"Tick directory for pair {trade.pair!r} not found under {ticks_root}")

    months = sorted(pair_dir.glob(f"{trade.pair}_*.parquet"))
    if not months:
        raise FileNotFoundError(f"No parquet files found for pair {trade.pair!r} in {pair_dir}")

    batches = []
    for path in months:
        table = pq.read_table(path, columns=["timestamp", "bid", "ask"])
        df = table.to_pandas()
        if "timestamp" not in df.columns:
            if df.index.name == "timestamp":
                df = df.reset_index()
            else:
                raise KeyError(f"'timestamp' column missing in {path}")

        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
        mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
        if mask.any():
            df = df.loc[mask].copy()
            df["mid"] = (df["bid"] + df["ask"]) * 0.5
            batches.append(df)

    if not batches:
        raise ValueError(f"No tick data found for window {start} → {end}")

    ticks = pd.concat(batches, ignore_index=True).sort_values("timestamp")
    return ticks


def plot_trade(trade: TradeRecord, ticks: pd.DataFrame, output: Optional[Path], seed: Optional[int] = None) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(ticks["timestamp"], ticks["mid"], label="Mid price", linewidth=1.2)

    ax.axvline(trade.entry_time, color="green", linestyle="--", label="Entry")
    ax.axvline(trade.exit_time, color="red", linestyle="--", label="Exit")

    ax.scatter([trade.entry_time], [trade.entry_price], color="green", s=40, zorder=5)
    ax.scatter([trade.exit_time], [trade.exit_price], color="red", s=40, zorder=5)

    if trade.reference_price is not None:
        ax.axhline(trade.reference_price, color="purple", linestyle="--", label="Reference")
    if trade.tp is not None:
        ax.axhline(trade.tp, color="blue", linestyle=":", label="TP")
    if trade.sl is not None:
        ax.axhline(trade.sl, color="orange", linestyle=":", label="SL")

    info_lines = [
        f"Direction: {'Long' if trade.direction == 1 else 'Short' if trade.direction == -1 else 'Flat'}",
        f"PnL: {trade.pnl_pips:.2f} pips",
    ]
    if trade.reference_age is not None:
        info_lines.append(f"Reference age: {trade.reference_age:.1f}s")
    if trade.threshold is not None:
        info_lines.append(f"Threshold: {trade.threshold:.5f}")
    # NEW: include seed and trade index in the annotation
    info_lines.append(f"Seed: {seed if seed is not None else '—'}")
    info_lines.append(f"Trade idx: {trade.index}")

    ax.text(
        0.02,
        0.98,
        "\n".join(info_lines),
        transform=ax.transAxes,
        verticalalignment="top",
        fontsize=10,
        bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"),
    )

    direction = "Long" if trade.direction == 1 else "Short" if trade.direction == -1 else "Flat"
    title = f"{trade.pair or 'Unknown'} | {direction} | PnL: {trade.pnl_pips:.2f} pips | idx={trade.index} | seed={seed if seed is not None else '—'}"
    ax.set_title(title)
    ax.set_xlabel("Timestamp (UTC)")
    ax.set_ylabel("Mid Price")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.autofmt_xdate()

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=160)
        logging.getLogger("trade_visualizer").info("saved plot", extra={"output": str(output), "seed": seed})
    else:
        plt.show()

    plt.close(fig)


# --- NEW: logging helpers -----------------------------------------------------

def _default_log_path(trades_path: Path, output: Optional[Path]) -> Path:
    if output:
        return output.with_suffix(".log")
    return (trades_path.parent / "trade_visualizer.log").resolve()


def _setup_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("trade_visualizer")
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers if re-run in the same interpreter
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path) for h in logger.handlers):
        fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        fh.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def _log_run_context(
    logger: logging.Logger,
    trades_path: Path,
    ticks_root: Path,
    seed: Optional[int],
    requested_index: Optional[int],
    trade: TradeRecord,
    padding_seconds: int,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
    ticks: pd.DataFrame,
    output: Optional[Path],
    log_path: Path,
) -> None:
    logger.info("=== Trade visualizer run ===")
    logger.info(f"Trades file: {trades_path}")
    logger.info(f"Ticks root:  {ticks_root}")
    logger.info(f"Output:      {output if output else '(shown interactively)'}")
    logger.info(f"Log file:    {log_path}")
    logger.info(f"Seed: {seed!r} | Requested trade index: {requested_index!r} | Chosen trade index: {trade.index}")
    logger.info(f"Padding seconds: {padding_seconds}")
    logger.info(f"Window UTC: {window_start.isoformat()} → {window_end.isoformat()}")

    # Log trade metrics (everything relevant to the plot from the record)
    for k, v in asdict(trade).items():
        logger.info(f"TRADE.{k} = {v}")

    # Log tick slice metadata
    if not ticks.empty:
        tmin = ticks["timestamp"].min()
        tmax = ticks["timestamp"].max()
        logger.info(f"Ticks loaded: {len(ticks)} rows | {tmin} → {tmax}")
        if "mid" in ticks:
            logger.info(
                "Ticks mid stats: min=%.8f mean=%.8f max=%.8f",
                float(ticks["mid"].min()),
                float(ticks["mid"].mean()),
                float(ticks["mid"].max()),
            )


# --- main ---------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    trades_path = args.trades.resolve()
    ticks_root = args.ticks_root.resolve()

    # Decide log file path and setup logger
    log_path = (args.log_file.resolve() if args.log_file else _default_log_path(trades_path, args.output))
    logger = _setup_logger(log_path)

    trades_df = load_trades(trades_path)
    trade = choose_trade(trades_df, args.trade_index, args.seed, trades_path)

    duration = (trade.exit_time - trade.entry_time).total_seconds()
    pad = args.padding_seconds if args.padding_seconds is not None else max(duration, 60)
    pad = max(pad, 60)  # ensure at least a minute either side

    window_start = trade.entry_time - pd.Timedelta(seconds=pad)
    window_end = trade.exit_time + pd.Timedelta(seconds=pad)

    ticks = load_tick_slice(ticks_root, trade, window_start, window_end)
    if ticks.empty:
        raise ValueError("No tick data found in the sampled window.")

    # NEW: log everything relevant
    _log_run_context(
        logger=logger,
        trades_path=trades_path,
        ticks_root=ticks_root,
        seed=args.seed,
        requested_index=args.trade_index,
        trade=trade,
        padding_seconds=int(pad),
        window_start=window_start,
        window_end=window_end,
        ticks=ticks,
        output=(args.output.resolve() if args.output else None),
        log_path=log_path,
    )

    plot_trade(trade, ticks, args.output.resolve() if args.output else None, seed=args.seed)


if __name__ == "__main__":
    main()
