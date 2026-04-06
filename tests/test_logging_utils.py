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

# mypy: disable-error-code="no-untyped-def"
from __future__ import annotations

import io
import logging

from tick_backtest.logging_utils import configure_logging


def test_configure_logging_preserves_host_handlers_by_default(tmp_path) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    host_stream = io.StringIO()
    host_handler = logging.StreamHandler(host_stream)

    try:
        root.handlers = [host_handler]
        configure_logging(run_id="run-1", log_dir=tmp_path / "logs")

        assert host_handler in root.handlers
        assert any(getattr(handler, "_tick_backtest_owned_handler", False) for handler in root.handlers)
    finally:
        for handler in list(root.handlers):
            if handler not in original_handlers:
                root.removeHandler(handler)
                handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_configure_logging_can_replace_existing_handlers(tmp_path) -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    host_stream = io.StringIO()
    host_handler = logging.StreamHandler(host_stream)

    try:
        root.handlers = [host_handler]
        configure_logging(run_id="run-2", log_dir=tmp_path / "logs", replace_handlers=True)

        assert host_handler not in root.handlers
        assert root.handlers
        assert all(getattr(handler, "_tick_backtest_owned_handler", False) for handler in root.handlers)
    finally:
        for handler in list(root.handlers):
            if handler not in original_handlers:
                root.removeHandler(handler)
                handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)
