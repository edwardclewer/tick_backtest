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
from importlib.resources.abc import Traversable
from pathlib import Path
import shutil

__all__ = ["analyze", "example_config", "report", "run"]


def _template_dir(template: str) -> Traversable:
    resource = files("tick_backtest").joinpath("config", "templates", template)
    if not resource.is_dir():
        raise ValueError(f"unknown config template: {template}")
    return resource


def _yaml_templates(template_dir: Traversable) -> list[Traversable]:
    return sorted(
        child for child in template_dir.iterdir() if child.is_file() and child.name.endswith(".yaml")
    )


def _copy_resource_tree(resource_dir: Traversable, dest_dir: Path) -> None:
    with ExitStack() as stack:
        def copy_resource_children(current_resource: Traversable, current_dest: Path) -> None:
            current_dest.mkdir(parents=True, exist_ok=True)
            for child in current_resource.iterdir():
                target_path = current_dest / child.name
                if child.is_dir():
                    copy_resource_children(child, target_path)
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)
                resource_path = Path(stack.enter_context(as_file(child)))
                shutil.copy2(resource_path, target_path)

        copy_resource_children(resource_dir, dest_dir)


def example_config(
    dest: str | Path | None = None,
    *,
    template: str = "minimal",
    include_demo_data: bool = False,
) -> None:
    """
    Print or write a packaged starter config template set.

    When dest is omitted, prints the main backtest template to stdout.
    When dest is provided, writes the full template set into that directory.
    """
    effective_template = "demo" if include_demo_data and template == "minimal" else template
    template_dir = _template_dir(effective_template)
    template_files = _yaml_templates(template_dir)
    if not template_files:
        raise ValueError(f"template '{effective_template}' contains no yaml files")

    if include_demo_data and dest is None:
        raise ValueError("dest is required when include_demo_data=True")

    if dest is None:
        backtest_template = next((item for item in template_files if item.name == "backtest.yaml"), None)
        if backtest_template is None:
            raise ValueError(f"template '{effective_template}' is missing backtest.yaml")
        print(backtest_template.read_text(encoding="utf-8"), end="")
        return

    dest_dir = Path(dest).expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack:
        for src in template_files:
            src_path = Path(stack.enter_context(as_file(src)))
            (dest_dir / src.name).write_text(src_path.read_text(encoding="utf-8"), encoding="utf-8")

    if include_demo_data:
        demo_data_dir = files("tick_backtest").joinpath("demo_data")
        _copy_resource_tree(demo_data_dir, dest_dir / "demo_data")


def run(config_path: str | Path, *, output_root: str | Path | None = None) -> None:
    """Execute the backtest engine and write run artefacts only."""
    from tick_backtest.backtest.workflow import run_backtest

    run_backtest(config_path=config_path, output_root=output_root)


def report(trades_path: str | Path) -> None:
    """Generate report artefacts alongside the trades parquet."""
    from tick_backtest.analysis.metric_stratification import derive_backtest_identifier, run_metric_stratification
    from tick_backtest.analysis.trade_analysis import run_trade_analysis

    resolved_trades_path = Path(trades_path).expanduser()
    output_root = resolved_trades_path.parent
    run_trade_analysis(resolved_trades_path, output_dir=output_root, configure_logs=False)

    stratification_root = output_root / "metric_stratification"
    if stratification_root.exists():
        shutil.rmtree(stratification_root)
    stratification_root.mkdir(parents=True, exist_ok=True)

    run_metric_stratification(
        trade_file=resolved_trades_path,
        output_root=stratification_root,
        output_subdir="",
        configure_logs=False,
    )

    reports_dir = stratification_root / "reports"
    if not reports_dir.exists():
        expected = stratification_root / derive_backtest_identifier(resolved_trades_path)
        raise RuntimeError(
            f"metric stratification output was not created under {stratification_root} "
            f"(legacy staged path would have been {expected})"
        )


def analyze(trades_path: str | Path) -> None:
    """Generate regression-style multivariate analysis artefacts beside the trades parquet."""
    from tick_backtest.analysis import run_trade_regression_analysis

    resolved_trades_path = Path(trades_path).expanduser()
    run_trade_regression_analysis(resolved_trades_path, output_dir=resolved_trades_path.parent / "multivariate_analysis")
