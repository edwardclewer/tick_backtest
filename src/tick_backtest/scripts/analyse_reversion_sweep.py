#!/usr/bin/env python3
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

"""
Run metric stratification analysis across completed sweep backtests and
summarise expectancy versus configuration parameters.

Example:
    python scripts/analyse_reversion_sweep.py \
        --manifest config/metrics/sweeps/manifest.csv \
        --backtest-config-dir config/backtest/sweeps \
        --analysis-root analysis/metric_stratification/output/sweeps
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd
import yaml
import logging

from tick_backtest.analysis.metric_stratification import nice_graphs
from tick_backtest.logging_utils import configure_logging, generate_run_id

logger = logging.getLogger(__name__)


METRIC_NAME = "reversion_30m"
METRIC_FIELDS = [
    f"{METRIC_NAME}.position",
    f"{METRIC_NAME}.reference_price",
    f"{METRIC_NAME}.distance_from_reference",
    f"{METRIC_NAME}.reference_age_seconds",
]

CONTINUOUS_METRICS = [
    "drift_sign.drift",
    "holding_seconds",
    "z30m.z_score",
    "z30m.rolling_residual",
    "z5m.z_score",
    "z5m.rolling_residual",
    "ewma_vol_5m.vol_ewma",
    "ewma_vol_5m.vol_percentile",
    "ewma_vol_30m.vol_ewma",
    "ewma_vol_30m.vol_percentile",
    f"{METRIC_NAME}.reference_price",
    f"{METRIC_NAME}.distance_from_reference",
    f"{METRIC_NAME}.reference_age_seconds",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stratified analysis for sweep runs.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("config/metrics/sweeps/manifest.csv"),
        help="Sweep manifest CSV (from build_reversion_sweep.py).",
    )
    parser.add_argument(
        "--backtest-config-dir",
        type=Path,
        default=Path("config/backtest/sweeps"),
        help="Directory containing per-run backtest configs (label.yaml).",
    )
    parser.add_argument(
        "--analysis-root",
        type=Path,
        default=Path("analysis/metric_stratification/output/sweeps"),
        help="Root directory for analysis outputs.",
    )
    parser.add_argument(
        "--metrics-name",
        default=METRIC_NAME,
        help="Name of the reversion metric in configs.",
    )
    return parser.parse_args()


def read_manifest(manifest_path: Path) -> List[Dict[str, str]]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if not rows:
        raise ValueError(f"Manifest {manifest_path} is empty.")
    return rows


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def find_metric_params(config: dict, metric_name: str) -> Dict[str, float]:
    for metric in config.get("metrics", []):
        if metric.get("name") == metric_name:
            params = metric.get("params", {})
            return {
                "min_recency_seconds": params.get("min_recency_seconds"),
                "tp_pips": params.get("tp_pips"),
                "sl_pips": params.get("sl_pips"),
                "trade_timeout_seconds": params.get("trade_timeout_seconds"),
            }
    raise ValueError(f"Metric '{metric_name}' not found in metrics config.")


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_trades(trades_path: Path) -> pd.DataFrame:
    trades = pd.read_parquet(trades_path)
    if f"{METRIC_NAME}.distance_from_reference" in trades.columns:
        trades[f"{METRIC_NAME}.distance_from_reference"] = trades[
            f"{METRIC_NAME}.distance_from_reference"
        ].abs()
    trades["is_win"] = (trades["pnl_pips"] > 0).astype(int)
    return trades


def stratify_metric(trades: pd.DataFrame, metric: str, save_prefix: Path) -> None:
    series = trades[metric].dropna()
    if series.empty or math.isclose(series.max(), series.min()):
        return

    min_val, max_val = float(series.min()), float(series.max())
    bin_width = (max_val - min_val) / 300 if max_val > min_val else 1.0
    bins = np.arange(min_val, max_val + bin_width, bin_width)
    labels = [round((a + b) / 2, 10) for a, b in zip(bins[:-1], bins[1:])]
    df = trades[[metric, "pnl_pips", "is_win"]].dropna()
    df = df.assign(bin=pd.cut(df[metric], bins=bins, labels=labels, include_lowest=True))

    summary = (
        df.groupby("bin", observed=True)
        .agg(
            count=("pnl_pips", "size"),
            win_rate=("is_win", "mean"),
            avg_pnl=("pnl_pips", "mean"),
            std_pnl=("pnl_pips", "std"),
        )
        .reset_index()
        .dropna()
    )

    metrics_path = save_prefix.with_suffix(".csv")
    ensure_output_dir(metrics_path.parent)
    summary.to_csv(metrics_path, index=False)

    nice_graphs.stratify_metric(
        trades,
        metric=metric,
        mode="fd",
        min_count=250,
        merge_to_min_count=True,
        save_graph_path=str(save_prefix.parent / "graph" / f"{save_prefix.name}.png"),
)


def run_analysis_for_trade_file(
    trades_path: Path,
    output_dir: Path,
) -> pd.DataFrame:
    trades = load_trades(trades_path)
    ensure_output_dir(output_dir)

    for metric in CONTINUOUS_METRICS:
        if metric not in trades.columns:
            continue
        stratify_metric(trades, metric, output_dir / metric.replace(".", "_"))

    # Focused holding time analysis (mirrors existing script defaults)
    df_focus = trades.query("holding_seconds >= 0 and holding_seconds <= 250").copy()
    if not df_focus.empty:
        focus_prefix = output_dir / "holding_seconds_focus_0_250s"
        nice_graphs.stratify_metric(
            df_focus,
            metric="holding_seconds",
            mode="fixed",
            width=(250 - 0) / 100,
            min_count=20,
            merge_to_min_count=False,
            counts_logscale=False,
            zero_line=True,
            clip_quantiles=(0, 1),
            title="Holding Time – Expectancy (0–250 s, 10 s bins)",
            save_graph_path=str(focus_prefix.parent / "graph" / f"{focus_prefix.name}.png"),
            save_csv_path=str(focus_prefix.parent / "csv" / f"{focus_prefix.name}.csv"),
        )

    return trades


def generate_summary_row(
    label: str,
    pair: str,
    trades: pd.DataFrame,
    params: Dict[str, float],
) -> Dict[str, float | str]:
    avg_pnl = float(trades["pnl_pips"].mean()) if not trades.empty else float("nan")
    trade_count = int(len(trades))
    return {
        "label": label,
        "pair": pair,
        "trade_count": trade_count,
        "avg_pnl_pips": avg_pnl,
        "min_recency_seconds": params.get("min_recency_seconds"),
        "tp_pips": params.get("tp_pips"),
        "sl_pips": params.get("sl_pips"),
        "trade_timeout_seconds": params.get("trade_timeout_seconds"),
    }


def find_trade_files(backtest_config_path: Path) -> Iterable[tuple[str, Path]]:
    config = load_yaml(backtest_config_path)
    output_base = Path(config["output_base_path"]).expanduser().resolve()
    pairs = config.get("pairs", [])
    if isinstance(pairs, str):
        pairs = [pairs]
    for pair in pairs:
        trade_path = output_base / pair / "trades.parquet"
        yield pair, trade_path


def main() -> None:
    args = parse_args()
    configure_logging(run_id=generate_run_id(), log_dir=args.analysis_root / "logs")
    manifest_rows = read_manifest(args.manifest)

    summary_rows: List[Dict[str, float | str]] = []
    for row in manifest_rows:
        label = row["label"]
        backtest_config_path = (args.backtest_config_dir / f"{label}.yaml").resolve()
        metrics_config_path = Path(row["metrics_config_path"]).resolve()

        if not backtest_config_path.exists():
            logger.info(
                "skip missing backtest config",
                extra={"label": label, "config_path": str(backtest_config_path)},
            )
            continue

        if not metrics_config_path.exists():
            logger.info(
                "skip missing metrics config",
                extra={"label": label, "metrics_config_path": str(metrics_config_path)},
            )
            continue

        metrics_config = load_yaml(metrics_config_path)
        params = find_metric_params(metrics_config, args.metrics_name)

        for pair, trade_path in find_trade_files(backtest_config_path):
            if not trade_path.exists():
                logger.info(
                    "skip missing trades",
                    extra={"label": label, "pair": pair, "trade_path": str(trade_path)},
                )
                continue

            output_dir = args.analysis_root / label / pair
            logger.info(
                "running sweep analysis",
                extra={"label": label, "pair": pair, "output_dir": str(output_dir)},
            )

            trades = run_analysis_for_trade_file(trade_path, output_dir)
            summary_rows.append(generate_summary_row(label, pair, trades, params))

    if not summary_rows:
        logger.info("no completed runs found; nothing to summarise")
        return

    summary_df = pd.DataFrame(summary_rows)
    summary_df.sort_values(["min_recency_seconds", "tp_pips", "trade_timeout_seconds", "pair"], inplace=True)

    ensure_output_dir(args.analysis_root)
    summary_path = args.analysis_root / "summary.csv"
    summary_df.to_csv(summary_path, index=False)

    logger.info(
        "summary preview",
        extra={"rows": summary_df.head(10).to_dict(orient="records")},
    )
    logger.info("saved summary", extra={"summary_path": str(summary_path)})


if __name__ == "__main__":
    main()
