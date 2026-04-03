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
from typing import Iterable

__all__ = ["example_config"]


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
