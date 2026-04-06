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
from collections.abc import Sequence
from pathlib import Path

from tick_backtest import api


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tick-backtest", description="Tick backtest command line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the backtest engine from a config file.")
    run_parser.add_argument("config_path", type=Path, help="Path to the backtest YAML configuration file.")
    run_parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Optional override for the backtest output root.",
    )
    run_parser.set_defaults(handler=_run_command)

    report_parser = subparsers.add_parser("report", help="Generate report artefacts for a trades parquet file.")
    report_parser.add_argument("trades_path", type=Path, help="Path to the trades parquet file.")
    report_parser.set_defaults(handler=_report_command)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run multivariate regression-style analysis for a trades parquet file.",
    )
    analyze_parser.add_argument("trades_path", type=Path, help="Path to the trades parquet file.")
    analyze_parser.set_defaults(handler=_analyze_command)

    example_parser = subparsers.add_parser(
        "example-config",
        help="Print or write starter configs, optionally with bundled demo data.",
    )
    example_parser.add_argument(
        "--dest",
        "--output",
        type=Path,
        default=None,
        help="Optional directory where the template set should be written.",
    )
    example_parser.add_argument(
        "--template",
        default="minimal",
        help="Template name to use (default: minimal).",
    )
    example_parser.add_argument(
        "--include-demo-data",
        action="store_true",
        help="Write a runnable demo project with bundled parquet fixture data.",
    )
    example_parser.set_defaults(handler=_example_config_command)

    return parser


def _run_command(args: argparse.Namespace) -> int:
    api.run(args.config_path, output_root=args.output_root)
    return 0


def _report_command(args: argparse.Namespace) -> int:
    api.report(args.trades_path)
    return 0


def _analyze_command(args: argparse.Namespace) -> int:
    api.analyze(args.trades_path)
    return 0


def _example_config_command(args: argparse.Namespace) -> int:
    api.example_config(dest=args.dest, template=args.template, include_demo_data=args.include_demo_data)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
