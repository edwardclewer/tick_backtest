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
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence

logger = logging.getLogger(__name__)


def discover_metrics_for_mode(output_dir: Path | str, mode: str) -> list[str]:
    """
    Return the metric identifiers that have CSV artefacts for a given binning mode.
    """
    output_path = Path(output_dir).expanduser()
    csv_dir = output_path / "csv" / mode
    if not csv_dir.exists():
        return []
    return sorted(p.stem for p in csv_dir.glob("*.csv"))


def build_metric_section(
    output_dir: Path | str,
    mode: str,
    metric: str,
    *,
    report_root: Path | str | None = None,
) -> str:
    """
    Assemble the Markdown block for a single metric/mode combination.
    """
    root = Path(output_dir).expanduser()
    report_base = Path(report_root).expanduser() if report_root else root
    lines: list[str] = [f"## `{metric}` ({mode})", ""]

    graph_rel = Path("graphs") / mode / f"{metric}.png"
    graph_path = root / graph_rel
    if graph_path.exists():
        rel_path = Path(os.path.relpath(graph_path, report_base))
        lines.append(f"![{metric} – {mode}]({rel_path.as_posix()})")
        lines.append("")
    else:
        lines.append("_Graph not available for this metric/mode combination._")
        lines.append("")

    return "\n".join(lines)


def compile_report_for_mode(
    output_dir: Path | str,
    mode: str,
    *,
    metrics: Iterable[str] | None = None,
    title: str | None = None,
    report_filename: str | None = None,
    report_dir: Path | str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> Path:
    """
    Build a Markdown report that collates every metric for a specific binning mode.
    """
    root = Path(output_dir).expanduser()
    selected_metrics = list(metrics) if metrics is not None else discover_metrics_for_mode(root, mode)
    if not selected_metrics:
        raise ValueError(f"No metrics discovered under {root} for mode '{mode}'.")

    report_root = Path(report_dir).expanduser() if report_dir else root / "reports"
    report_root.mkdir(parents=True, exist_ok=True)

    filename = report_filename or f"metric_report_{mode}.md"
    report_path = report_root / filename

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    resolved_title = title or f"Metric Stratification Report – {mode}"

    header = [
        f"# {resolved_title}",
        "",
        f"_Generated {timestamp}_",
        "",
        f"- Output directory: `{root}`",
        f"- Binning mode: `{mode}`",
        f"- Metrics included: {len(selected_metrics)}",
    ]

    meta = dict(metadata or {})
    for key, value in sorted(meta.items()):
        header.append(f"- {key}: {value}")
    header.append("")

    sections = [
        build_metric_section(root, mode, metric, report_root=report_root)
        for metric in selected_metrics
    ]
    report_path.write_text("\n".join(header + sections), encoding="utf-8")
    logger.info(
        "compiled metric stratification report",
        extra={"mode": mode, "report_path": str(report_path)},
    )
    return report_path


def compile_reports_for_modes(
    output_dir: Path | str,
    modes: Sequence[str],
    *,
    metrics_by_mode: Mapping[str, Sequence[str]] | None = None,
    titles: Mapping[str, str] | None = None,
    report_dir: Path | str | None = None,
) -> dict[str, Path]:
    """
    Generate Markdown reports for every requested binning mode and return their paths.
    """
    reports: dict[str, Path] = {}
    for mode in modes:
        metrics = (metrics_by_mode or {}).get(mode)
        title = (titles or {}).get(mode)
        reports[mode] = compile_report_for_mode(
            output_dir,
            mode,
            metrics=metrics,
            title=title,
            report_dir=report_dir,
        )
    return reports
