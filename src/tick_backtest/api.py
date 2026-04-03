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

from contextlib import ExitStack
from importlib.resources import as_file, files
from pathlib import Path
import shutil
from typing import Iterable

__all__ = ["analyze", "example_config", "report", "run"]


def _template_dir(template: str):
    resource = files("tick_backtest").joinpath("config", "templates", template)
    if not resource.is_dir():
        raise ValueError(f"unknown config template: {template}")
    return resource


def _yaml_templates(template_dir) -> Iterable:
    return sorted(
        child for child in template_dir.iterdir() if child.is_file() and child.name.endswith(".yaml")
    )


def example_config(dest: str | Path | None = None, *, template: str = "minimal") -> None:
    """
    Print or write a packaged starter config template set.

    When dest is omitted, prints the main backtest template to stdout.
    When dest is provided, writes the full template set into that directory.
    """
    template_dir = _template_dir(template)
    template_files = _yaml_templates(template_dir)
    if not template_files:
        raise ValueError(f"template '{template}' contains no yaml files")

    if dest is None:
        backtest_template = next((item for item in template_files if item.name == "backtest.yaml"), None)
        if backtest_template is None:
            raise ValueError(f"template '{template}' is missing backtest.yaml")
        print(backtest_template.read_text(encoding="utf-8"), end="")
        return

    dest_dir = Path(dest).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for src in template_files:
            src_path = Path(stack.enter_context(as_file(src)))
            (dest_dir / src.name).write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")


def run(config_path: str | Path, *, output_root: str | Path | None = None) -> None:
    """Execute the full repo workflow for a backtest config."""
    from tick_backtest.analysis import run_backtest_analysis, run_metric_stratification_analysis
    from tick_backtest.backtest.workflow import run_backtest

    result = run_backtest(config_path=config_path, output_root=output_root)
    output_dir = result.get("output_dir") if isinstance(result, dict) else None
    if output_dir is None:
        raise RuntimeError("run_backtest returned no output directory")

    run_id = result.get("run_id") if isinstance(result, dict) else None
    manifest = result.get("manifest") if isinstance(result, dict) else None
    metrics_cfg_copy = None
    if isinstance(manifest, dict):
        metrics_cfg_copy = manifest.get("configs", {}).get("metrics", {}).get("copied_path")

    run_backtest_analysis(output_dir, run_id=run_id)
    run_metric_stratification_analysis(output_dir, metrics_config_path=metrics_cfg_copy, run_id=run_id)


def report(trades_path: str | Path) -> None:
    """Generate single-trade-file report artefacts alongside the trades parquet."""
    from tick_backtest.analysis.trade_analysis import run_trade_analysis

    run_trade_analysis(trades_path, output_dir=Path(trades_path).expanduser().parent, configure_logs=False)


def analyze(trades_path: str | Path) -> None:
    """Generate metric stratification artefacts beside the trades parquet."""
    from tick_backtest.analysis.metric_stratification import derive_backtest_identifier, run_metric_stratification

    resolved_trades_path = Path(trades_path).expanduser()
    working_root = resolved_trades_path.parent
    output_root = working_root / "metric_stratification"
    identifier = derive_backtest_identifier(resolved_trades_path)
    staged_output = output_root / identifier

    if staged_output.exists():
        shutil.rmtree(staged_output)
    if output_root.exists():
        for child in output_root.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        output_root.mkdir(parents=True, exist_ok=True)

    run_metric_stratification(
        trade_file=resolved_trades_path,
        output_root=output_root,
        configure_logs=False,
    )

    if not staged_output.exists():
        raise RuntimeError(f"metric stratification output was not created: {staged_output}")

    for child in list(output_root.iterdir()):
        if child == staged_output:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    for child in staged_output.iterdir():
        target = output_root / child.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(child), str(target))
    shutil.rmtree(staged_output, ignore_errors=True)
