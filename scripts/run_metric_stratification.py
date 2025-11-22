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
from pathlib import Path
from collections.abc import Mapping, Sequence

from tick_backtest.analysis.metric_stratification import (
    MetricStratificationOutputs,
    run_metric_stratification,
)
from tick_backtest.analysis.metric_stratification.workflow import DEFAULT_BINNING_MODES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the metric stratification workflow for a trades parquet file.",
    )
    parser.add_argument(
        "trade_file",
        type=Path,
        help="Path to the trades parquet file to analyse.",
    )
    parser.add_argument(
        "output_root",
        type=Path,
        help="Directory where analysis artefacts should be written.",
    )
    parser.add_argument(
        "--metrics",
        nargs="*",
        default=None,
        help="Optional subset of metrics to stratify. Defaults to the full configured list.",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Disable PNG generation (useful for headless environments).",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip writing CSV/PNG/Markdown outputs; still returns DataFrames.",
    )
    parser.add_argument(
        "--binning-modes",
        nargs="*",
        default=None,
        help="Binning modes to render (default: fixed fd scott sigma nbins).",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Disable generation of per-mode Markdown reports.",
    )
    parser.add_argument(
        "--report-name-template",
        type=str,
        default=None,
        help="Filename template for reports (e.g. 'metric_report_{mode}.md').",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Optional directory for compiled reports (defaults to <output>/reports).",
    )
    parser.add_argument(
        "--report-title",
        action="append",
        default=None,
        help="Override report title per mode using MODE=Title. Can be repeated.",
    )
    return parser.parse_args()


def _parse_mode_mapping(pairs: Sequence[str] | None) -> dict[str, str]:
    if not pairs:
        return {}

    mapping: dict[str, str] = {}
    for entry in pairs:
        if "=" not in entry:
            raise ValueError(f"Expected MODE=TITLE formatting for --report-title, got '{entry}'")
        mode, title = entry.split("=", 1)
        mapping[mode.strip()] = title.strip()
    return mapping


def run(
    trade_file: Path,
    output_root: Path,
    *,
    metrics: Sequence[str] | None = None,
    plot: bool = True,
    save_outputs: bool = True,
    binning_modes: Sequence[str] | None = None,
    generate_reports: bool = True,
    report_titles: Mapping[str, str] | None = None,
    report_filename_template: str | None = None,
    report_dir: Path | None = None,
) -> MetricStratificationOutputs:
    return run_metric_stratification(
        trade_file=trade_file,
        output_root=output_root,
        metrics=metrics,
        plot=plot,
        save_outputs=save_outputs,
        binning_modes=binning_modes,
        generate_reports=generate_reports,
        report_titles=report_titles,
        report_filename_template=report_filename_template,
        report_dir=report_dir,
    )


def main() -> None:
    args = parse_args()
    run(
        trade_file=args.trade_file,
        output_root=args.output_root,
        metrics=args.metrics,
        plot=not args.no_plot,
        save_outputs=not args.no_save,
        binning_modes=args.binning_modes or DEFAULT_BINNING_MODES,
        generate_reports=not args.no_report,
        report_titles=_parse_mode_mapping(args.report_title),
        report_filename_template=args.report_name_template,
        report_dir=args.report_dir,
    )


if __name__ == "__main__":
    main()
