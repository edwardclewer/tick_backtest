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
import sys
from pathlib import Path

from tick_backtest.analysis import run_backtest_analysis, run_metric_stratification_analysis
from tick_backtest.backtest.workflow import run_backtest

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the tick backtest workflow.")
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the backtest YAML configuration file.",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Enable cProfile for the run.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level for the run (default: INFO).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run identifier; generated when omitted.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional override for the output root directory.",
    )
    return parser.parse_args(argv)


def _setup_logging(level: str) -> None:
    resolved = getattr(logging, level.upper(), None)
    if not isinstance(resolved, int):
        logger.warning("invalid log level supplied; defaulting to INFO", extra={"log_level": level})
        resolved = logging.INFO
    logging.basicConfig(level=resolved, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _setup_logging(args.log_level)

    try:
        result = run_backtest(
            config_path=args.config,
            profile=args.profile,
            log_level=args.log_level,
            run_id=args.run_id,
            output_root=args.output_root,
        )
    except Exception:  # pragma: no cover - defensive CLI wrapping
        logger.exception("backtest execution failed", extra={"config": str(args.config)})
        return 1

    run_id = result.get("run_id") if isinstance(result, dict) else None
    output_dir = result["output_dir"] if isinstance(result, dict) else None
    manifest = result.get("manifest") if isinstance(result, dict) else None
    metrics_cfg_copy = None
    if isinstance(manifest, dict):
        metrics_cfg_copy = (
            manifest.get("configs", {})
            .get("metrics", {})
            .get("copied_path")
        )

    if output_dir is None:
        logger.error("run_backtest returned no output directory; skipping post-run analysis")
        return 1

    try:
        analysis_summary = run_backtest_analysis(
            output_dir,
            run_id=run_id,
        )
    except Exception as exc:
        logger.exception("automated trade analysis failed")
        return 1

    if analysis_summary.failures:
        logger.warning(
            "trade analysis completed with failures",
            extra={"failures": dict(analysis_summary.failures)},
        )
    else:
        logger.info(
            "trade analysis completed",
            extra={
                "analysis_root": str(analysis_summary.analysis_root),
                "pairs": sorted(analysis_summary.per_pair.keys()),
            },
        )

    try:
        strat_summary = run_metric_stratification_analysis(
            output_dir,
            metrics_config_path=metrics_cfg_copy,
            run_id=run_id,
        )
    except Exception as exc:
        logger.exception("metric stratification failed")
        return 1

    if strat_summary.failures:
        logger.warning(
            "metric stratification completed with failures",
            extra={"failures": dict(strat_summary.failures)},
        )
    else:
        logger.info(
            "metric stratification completed",
            extra={
                "analysis_root": str(strat_summary.analysis_root),
                "pairs": sorted(strat_summary.per_pair.keys()),
            },
        )

    logger.info(
        "run complete",
        extra={
            "run_id": run_id,
            "output_dir": str(output_dir),
            "analysis_root": str(strat_summary.analysis_root),
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
