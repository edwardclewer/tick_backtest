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
Generate threshold reversion sweep metric configs and manifest.

Usage:
    python scripts/build_reversion_sweep.py \
        --base-metrics config/metrics/default_metrics.yaml \
        --output-dir config/metrics/sweeps
"""

from __future__ import annotations

import argparse
import csv
import itertools
from copy import deepcopy
from pathlib import Path
from typing import Iterable

import yaml

import logging
from tick_backtest.logging_utils import configure_logging, generate_run_id

logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build threshold reversion sweep configs.")
    parser.add_argument(
        "--base-metrics",
        type=Path,
        default=Path("config/metrics/default_metrics.yaml"),
        help="Path to the baseline metrics YAML to clone.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("config/metrics/sweeps"),
        help="Directory to write generated metric configs.",
    )
    parser.add_argument(
        "--metric-name",
        default="reversion_30m",
        help="Metric `name` to update in the generated configs.",
    )
    return parser.parse_args()


def load_metrics_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "metrics" not in data:
        raise ValueError(f"Metrics config {path} missing 'metrics' list")
    return data


def update_reversion_metric(
    config: dict,
    metric_name: str,
    *,
    min_recency_seconds: float,
    tp_pips: float,
    sl_pips: float,
    trade_timeout_seconds: float,
) -> None:
    for metric in config.get("metrics", []):
        if metric.get("name") != metric_name:
            continue
        params = metric.setdefault("params", {})
        params["min_recency_seconds"] = int(min_recency_seconds)
        params["tp_pips"] = int(tp_pips)
        params["sl_pips"] = int(sl_pips)
        params["trade_timeout_seconds"] = int(trade_timeout_seconds)
        return

    raise ValueError(f"Metric named '{metric_name}' not found in config.")


def iter_combinations() -> Iterable[dict]:
    min_recency_values = [0, 30, 60, 90, 120]
    tp_sl_pairs = [(10, 10), (8, 8), (6, 6), (12, 12)]
    timeout_values = [60, 120, 180, 300]

    for min_recency, (tp, sl), timeout in itertools.product(
        min_recency_values, tp_sl_pairs, timeout_values
    ):
        yield {
            "min_recency_seconds": min_recency,
            "tp_pips": tp,
            "sl_pips": sl,
            "trade_timeout_seconds": timeout,
        }


def make_filename(params: dict) -> str:
    return (
        f"reversion_30m_min{int(params['min_recency_seconds'])}"
        f"_tp{int(params['tp_pips'])}"
        f"_sl{int(params['sl_pips'])}"
        f"_timeout{int(params['trade_timeout_seconds'])}.yaml"
    )


def make_label(params: dict) -> str:
    return (
        f"min{int(params['min_recency_seconds'])}"
        f"_tp{int(params['tp_pips'])}"
        f"_sl{int(params['sl_pips'])}"
        f"_timeout{int(params['trade_timeout_seconds'])}"
    )


def main() -> None:
    args = parse_args()
    configure_logging(run_id=generate_run_id(), log_dir=args.output_dir / "logs")
    base_config = load_metrics_config(args.base_metrics)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "manifest.csv"

    with manifest_path.open("w", newline="", encoding="utf-8") as manifest_file:
        writer = csv.DictWriter(
            manifest_file,
            fieldnames=[
                "label",
                "metrics_config_path",
                "min_recency_seconds",
                "tp_pips",
                "sl_pips",
                "trade_timeout_seconds",
            ],
        )
        writer.writeheader()

        for params in iter_combinations():
            config_copy = deepcopy(base_config)
            update_reversion_metric(
                config_copy,
                args.metric_name,
                **params,
            )

            filename = make_filename(params)
            config_path = output_dir / filename
            with config_path.open("w", encoding="utf-8") as out_file:
                yaml.safe_dump(config_copy, out_file, sort_keys=False)

            writer.writerow(
                {
                    "label": make_label(params),
                    "metrics_config_path": str(config_path),
                    **params,
                }
            )

    logger.info(
        "wrote sweep configs",
        extra={"output_dir": str(output_dir), "manifest": str(manifest_path)},
    )


if __name__ == "__main__":
    main()
