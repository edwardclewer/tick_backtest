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

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tick_backtest.logging_utils import configure_logging, generate_run_id

from .compile_report import compile_report_for_mode, discover_metrics_for_mode
from .nice_graphs import stratify_metric

logger = logging.getLogger(__name__)

DEFAULT_METRICS: list[str] = [
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
    "reversion_30m.reference_price",
    "reversion_30m.distance_from_reference",
    "reversion_30m.reference_age_seconds",
    "ewma_mid_5m.ewma",
    "ewma_mid_5m_slope.ewma",
    "ewma_mid_5m_slope.slope",
    "spread_60s.spread",
    "spread_60s.spread_pips",
    "spread_60s.spread_percentile",
    "tick_rate_30s.tick_count",
    "tick_rate_30s.tick_rate_per_sec",
    "tick_rate_30s.tick_rate_per_min",
]

DEFAULT_PREVIEW_COLUMNS: tuple[str, ...] = (
    "pnl_pips",
    "is_win",
    "holding_seconds",
    "reversion_30m.threshold",
)

DEFAULT_BINNING_MODES: tuple[str, ...] = ("fixed", "fd", "scott", "sigma", "nbins")


@dataclass(frozen=True)
class MetricStratificationOutputs:
    """Structured result returned by :func:`run_metric_stratification`."""

    output_base: Path
    binning_modes: tuple[str, ...]
    summaries: Mapping[str, pd.DataFrame] = field(default_factory=dict)
    reports_by_mode: Mapping[str, Path] = field(default_factory=dict)


def derive_backtest_identifier(trade_file: Path | str) -> str:
    """Derive a sensible identifier for a trades file based on its path."""
    trade_path = Path(trade_file).expanduser()
    identifier_parts: list[str] = []
    try:
        idx = trade_path.parts.index("backtests")
        identifier_parts = [part for part in trade_path.parts[idx + 1 : -1] if part]
    except ValueError:
        pass

    if not identifier_parts:
        parent_name = trade_path.parent.name
        if parent_name:
            identifier_parts.append(parent_name)

    if not identifier_parts:
        identifier_parts.append(trade_path.stem)

    return "_".join(identifier_parts)


def load_trades(trade_file: Path | str) -> pd.DataFrame:
    """Load a parquet trade file into a DataFrame."""
    trade_path = Path(trade_file).expanduser()
    if not trade_path.exists():
        raise FileNotFoundError(f"Trade file not found: {trade_path}")
    return pd.read_parquet(trade_path)


def run_metric_stratification(
    trade_file: Path | str,
    output_root: Path | str,
    *,
    metrics: Sequence[str] | None = None,
    value_column: str = "pnl_pips",
    preview_columns: Sequence[str] = DEFAULT_PREVIEW_COLUMNS,
    log_dir: Path | str | None = None,
    configure_logs: bool = True,
    plot: bool = True,
    save_outputs: bool = True,
    binning_modes: Sequence[str] | None = None,
    mode_kwargs: Mapping[str, Mapping[str, Any]] | None = None,
    generate_reports: bool = True,
    report_titles: Mapping[str, str] | None = None,
    report_filename_template: str | None = None,
    report_dir: Path | str | None = None,
    report_metadata: Mapping[str, str] | None = None,
    stratify_kwargs: Mapping[str, Mapping[str, Any]] | None = None,
    common_stratify_kwargs: Mapping[str, Any] | None = None,
) -> MetricStratificationOutputs:
    """
    Run the metric stratification workflow for a single trade file.

    Returns:
        MetricStratificationOutputs
    """
    trade_path = Path(trade_file).expanduser()
    output_root_path = Path(output_root).expanduser()
    output_root_path.mkdir(parents=True, exist_ok=True)

    backtest_id = derive_backtest_identifier(trade_path)
    output_base = output_root_path / backtest_id
    output_base.mkdir(parents=True, exist_ok=True)

    run_logger = logger
    if configure_logs:
        resolved_log_dir = Path(log_dir).expanduser() if log_dir else output_base / "logs"
        resolved_log_dir.mkdir(parents=True, exist_ok=True)
        configure_logging(run_id=generate_run_id(), log_dir=resolved_log_dir)
        run_logger = logging.getLogger(__name__)

    run_logger.info("loading trade file", extra={"trade_file": str(trade_path)})
    trades = load_trades(trade_path)

    run_logger.info("loaded trades", extra={"count": len(trades)})
    run_logger.info("trade columns", extra={"columns": trades.columns.tolist()})

    numeric_cols = trades.select_dtypes(include=[float, int]).columns
    missing_numeric = trades[numeric_cols].isna().sum()
    run_logger.info(
        "missing numeric values",
        extra={"missing": missing_numeric[missing_numeric > 0].to_dict()},
    )

    expectancy = trades[value_column].mean()
    win_rate = (trades[value_column] > 0).mean()
    run_logger.info("overall expectancy", extra={"expectancy_pips": expectancy})
    run_logger.info("overall win rate", extra={"win_rate_pct": win_rate * 100})

    working_trades = trades.copy()
    working_trades["is_win"] = (working_trades[value_column] > 0).astype(int)
    preview_cols = [col for col in preview_columns if col in working_trades.columns]
    if preview_cols:
        preview_records = working_trades[preview_cols].head().to_dict(orient="records")
        run_logger.info("preview rows", extra={"rows": preview_records})

    metrics_to_run = list(metrics) if metrics else list(DEFAULT_METRICS)
    modes: tuple[str, ...] = tuple(binning_modes) if binning_modes else DEFAULT_BINNING_MODES
    results: dict[str, pd.DataFrame] = {}
    per_metric_kwargs = stratify_kwargs or {}
    shared_kwargs: dict[str, Any] = dict(common_stratify_kwargs or {})
    shared_kwargs.setdefault("plot", plot)
    mode_specific_kwargs = mode_kwargs or {}

    for metric in metrics_to_run:
        if metric not in working_trades.columns:
            run_logger.info("skip metric absent", extra={"metric": metric})
            continue

        metric_kwargs = dict(shared_kwargs)
        metric_kwargs.update(per_metric_kwargs.get(metric, {}))

        for mode in modes:
            call_kwargs = dict(metric_kwargs)
            call_kwargs.update(mode_specific_kwargs.get(mode, {}))
            call_kwargs["mode"] = mode
            call_kwargs["style"] = "bars"

            graph_path = csv_path = None
            if save_outputs:
                graph_path = output_base / "graphs" / mode / f"{metric}.png"
                csv_path = output_base / "csv" / mode / f"{metric}.csv"

            try:
                summary = stratify_metric(
                    working_trades,
                    metric=metric,
                    value_col=value_column,
                    save_graph_path=graph_path,
                    save_csv_path=csv_path,
                    **call_kwargs,
                )
            except ValueError as exc:
                    run_logger.warning(
                        "metric stratification failed",
                        extra={"metric": metric, "mode": mode, "error": str(exc)},
                    )
                    continue

            if metric not in results:
                results[metric] = summary

    reports: dict[str, Path] = {}
    if save_outputs and generate_reports and modes:
        filename_template = report_filename_template or "metric_report_{mode}.md"
        report_root = Path(report_dir).expanduser() if report_dir else output_base / "reports"
        metadata = {"backtest_id": backtest_id, "value_column": value_column}
        if report_metadata:
            metadata.update(report_metadata)

        for mode in modes:
            metrics_for_mode = discover_metrics_for_mode(output_base, mode)
            if not metrics_for_mode:
                run_logger.info(
                    "skip report generation for mode with no metrics",
                    extra={"mode": mode},
                )
                continue

            resolved_title = report_titles.get(mode) if report_titles else None
            if not resolved_title:
                resolved_title = f"Metric Stratification Report – {backtest_id} ({mode})"

            report_filename = filename_template.format(mode=mode, backtest_id=backtest_id)
            report_path = compile_report_for_mode(
                output_base,
                mode,
                metrics=metrics_for_mode,
                title=resolved_title,
                report_filename=report_filename,
                report_dir=report_root,
                metadata=metadata,
            )
            reports[mode] = report_path

    return MetricStratificationOutputs(
        output_base=output_base,
        binning_modes=modes,
        summaries=results,
        reports_by_mode=reports,
    )
