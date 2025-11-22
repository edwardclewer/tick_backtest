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
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

import pandas as pd

from tick_backtest.analysis.metric_stratification import (
    derive_backtest_identifier,
    run_metric_stratification,
)
from tick_backtest.config_parsers.metrics.config_parser import MetricsConfigParser

from .trade_analysis import TradeAnalysisResult, run_trade_analysis

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestAnalysisSummary:
    """Summary of per-pair trade analysis artefacts for a completed run."""

    run_output_dir: Path
    analysis_root: Path
    per_pair: Mapping[str, TradeAnalysisResult] = field(default_factory=dict)
    failures: Mapping[str, str] = field(default_factory=dict)


def _iter_trades(output_dir: Path) -> Dict[str, Path]:
    trades: Dict[str, Path] = {}
    for child in sorted(output_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name in {"logs", "analysis"}:
            continue
        trades_path = child / "trades.parquet"
        if trades_path.exists():
            trades[child.name] = trades_path
    return trades


def run_backtest_analysis(
    run_output_dir: Path | str,
    *,
    analysis_root: Path | str | None = None,
    run_id: Optional[str] = None,
    generate_plot: bool = True,
    generate_report: bool = True,
) -> BacktestAnalysisSummary:
    """
    Generate per-pair trade analysis artefacts for a completed backtest run.

    Parameters
    ----------
    run_output_dir:
        Path to the ``output`` directory produced by ``run_backtest``.
    analysis_root:
        Optional override for where analysis artefacts are written. Defaults to
        ``<run_output_dir>/analysis``.
    run_id:
        Optional identifier used for logging context.
    generate_plot / generate_report:
        Toggle plot or report creation when you need faster runs (e.g. tests).
    """
    output_dir = Path(run_output_dir).expanduser()
    if not output_dir.exists():
        raise FileNotFoundError(f"Backtest output directory not found: {output_dir}")

    analysis_dir = Path(analysis_root).expanduser() if analysis_root else output_dir
    analysis_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "starting backtest analysis",
        extra={
            "run_output_dir": str(output_dir),
            "analysis_root": str(analysis_dir),
            "run_id": run_id,
        },
    )

    per_pair_results: Dict[str, TradeAnalysisResult] = {}
    failures: Dict[str, str] = {}
    trades_map = _iter_trades(output_dir)

    for pair, trades_path in trades_map.items():
        pair_output_dir = trades_path.parent
        pair_analysis_dir = pair_output_dir / "analysis"
        pair_analysis_dir.mkdir(parents=True, exist_ok=True)
        try:
            result = run_trade_analysis(
                trades_path,
                output_dir=pair_analysis_dir,
                plot_filename="equity_curve.png",
                report_filename="report.md",
                generate_plot=generate_plot,
                generate_report=generate_report,
                configure_logs=False,
            )
        except Exception as exc:  # pragma: no cover - defensive; captured via tests
            failures[pair] = str(exc)
            logger.warning(
                "trade analysis failed",
                extra={
                    "run_id": run_id,
                    "pair": pair,
                    "trades_path": str(trades_path),
                    "error": str(exc),
                },
            )
            continue

        per_pair_results[pair] = result
        logger.info(
            "trade analysis complete",
            extra={
                "run_id": run_id,
                "pair": pair,
                "report_path": str(result.report_path) if result.report_path else None,
                "plot_path": str(result.plot_path) if result.plot_path else None,
            },
        )

    summary = BacktestAnalysisSummary(
        run_output_dir=output_dir,
        analysis_root=analysis_dir,
        per_pair=per_pair_results,
        failures=failures,
    )
    logger.info(
        "backtest analysis summary",
        extra={
            "run_id": run_id,
            "pairs_analyzed": sorted(per_pair_results.keys()),
            "failures": failures,
        },
    )
    return summary


@dataclass(frozen=True)
class MetricStratificationSummary:
    """Summary of per-pair metric stratification artefacts."""

    run_output_dir: Path
    analysis_root: Path
    per_pair: Mapping[str, Path] = field(default_factory=dict)
    failures: Mapping[str, str] = field(default_factory=dict)


def _resolve_metrics_config(run_root: Path) -> Path:
    manifest_path = run_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics_cfg = (
        manifest.get("configs", {})
        .get("metrics", {})
        .get("copied_path")
    )
    if not metrics_cfg:
        raise ValueError("Metrics config path missing from manifest.")
    return Path(metrics_cfg)


def _enabled_metric_names(parser: MetricsConfigParser) -> List[str]:
    config = parser.load_metrics_config()
    names: List[str] = []
    for metric in config.metrics:
        enabled = getattr(metric, "enabled", True)
        if enabled:
            names.append(metric.name)
    return names


def _columns_for_metrics(df: pd.DataFrame, metric_names: Sequence[str]) -> List[str]:
    columns: Dict[str, None] = {}
    for name in metric_names:
        if name in df.columns and pd.api.types.is_numeric_dtype(df[name]):
            columns[name] = None
        prefix = f"{name}."
        for col in df.columns:
            if col.startswith(prefix) and pd.api.types.is_numeric_dtype(df[col]):
                columns[col] = None
    return list(columns.keys())


def run_metric_stratification_analysis(
    run_output_dir: Path | str,
    *,
    metrics_config_path: Path | str | None = None,
    analysis_root: Path | str | None = None,
    run_id: Optional[str] = None,
    plot: bool = True,
    save_outputs: bool = True,
) -> MetricStratificationSummary:
    """
    Run metric stratification across every pair output within a backtest run.
    """
    output_dir = Path(run_output_dir).expanduser()
    if not output_dir.exists():
        raise FileNotFoundError(f"Backtest output directory not found: {output_dir}")

    run_root = output_dir.parent
    cfg_path = Path(metrics_config_path).expanduser() if metrics_config_path else _resolve_metrics_config(run_root)
    parser = MetricsConfigParser(cfg_path)
    metric_names = _enabled_metric_names(parser)

    analysis_dir = Path(analysis_root).expanduser() if analysis_root else output_dir
    analysis_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "starting metric stratification analysis",
        extra={
            "run_output_dir": str(output_dir),
            "analysis_root": str(analysis_dir),
            "run_id": run_id,
            "metrics_config": str(cfg_path),
            "metric_names": metric_names,
        },
    )

    per_pair_outputs: Dict[str, Path] = {}
    failures: Dict[str, str] = {}

    trades_map = _iter_trades(output_dir)
    for pair, trades_path in trades_map.items():
        pair_dir = trades_path.parent
        pair_analysis_dir = pair_dir / "analysis"
        pair_analysis_dir.mkdir(parents=True, exist_ok=True)
        strat_root = pair_analysis_dir / "metric_stratification"

        try:
            df = pd.read_parquet(trades_path)
        except Exception as exc:  # pragma: no cover - defensive
            failures[pair] = f"load_error: {exc}"
            logger.warning(
                "failed to load trades for stratification",
                extra={"pair": pair, "error": str(exc), "trades_path": str(trades_path)},
            )
            continue

        metric_columns = _columns_for_metrics(df, metric_names)
        if not metric_columns:
            logger.info(
                "no metric columns available for stratification",
                extra={"pair": pair, "metrics": metric_names},
            )
            per_pair_outputs[pair] = strat_root
            continue

        backtest_id = derive_backtest_identifier(trades_path)
        tmp_output_dir = pair_analysis_dir / backtest_id
        if tmp_output_dir.exists():
            shutil.rmtree(tmp_output_dir)
        if strat_root.exists():
            shutil.rmtree(strat_root)

        try:
            run_metric_stratification(
                trade_file=trades_path,
                output_root=pair_analysis_dir,
                metrics=metric_columns,
                plot=plot,
                save_outputs=save_outputs,
            )
        except Exception as exc:  # pragma: no cover - defensive
            failures[pair] = str(exc)
            logger.warning(
                "metric stratification failed",
                extra={"pair": pair, "error": str(exc), "metric_columns": metric_columns},
            )
            if tmp_output_dir.exists():
                shutil.rmtree(tmp_output_dir, ignore_errors=True)
            continue

        if strat_root.exists():
            shutil.rmtree(strat_root)
        strat_root.mkdir(parents=True, exist_ok=True)

        if tmp_output_dir.exists():
            for child in tmp_output_dir.iterdir():
                target = strat_root / child.name
                if child.is_dir():
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.move(str(child), str(target))
                else:
                    if target.exists():
                        target.unlink()
                    shutil.move(str(child), str(target))
            shutil.rmtree(tmp_output_dir, ignore_errors=True)

        per_pair_outputs[pair] = strat_root
        logger.info(
            "metric stratification complete",
            extra={
                "pair": pair,
                "output_dir": str(strat_root),
                "metrics": metric_columns,
            },
        )

    summary = MetricStratificationSummary(
        run_output_dir=output_dir,
        analysis_root=analysis_dir,
        per_pair=per_pair_outputs,
        failures=failures,
    )
    logger.info(
        "metric stratification summary",
        extra={
            "run_id": run_id,
            "pairs": sorted(per_pair_outputs.keys()),
            "failures": failures,
        },
    )
    return summary
