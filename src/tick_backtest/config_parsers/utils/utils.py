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
import math
import os
from pathlib import Path
from typing import Any

from tick_backtest.exceptions import ConfigError

logger = logging.getLogger(__name__)


def validate_path(
    path: Path | str,
    must_exist: bool,
    expect_dir: bool,
    create_if_missing: bool = False,
    label: str = "",
    base_dir: Path | None = None,
) -> Path:
    """Validate and normalize a filesystem path."""
    raw_path = Path(path).expanduser()
    if base_dir is not None and not raw_path.is_absolute():
        raw_path = base_dir / raw_path
    p = raw_path.resolve(strict=False)
    label = label or str(p)

    if must_exist and not p.exists():
        raise ConfigError(f"required path '{label}' does not exist: {p}")

    if create_if_missing and not p.exists():
        try:
            p.mkdir(parents=True, exist_ok=True)
            logger.info("created missing output directory", extra={"path": p})
        except OSError as e:
            raise ConfigError(f"failed to create output directory '{p}': {e}") from e

    if p.exists():
        if expect_dir and not p.is_dir():
            raise ConfigError(f"expected '{label}' to be a directory, but got a file: {p}")
        if not expect_dir and not p.is_file():
            raise ConfigError(f"expected '{label}' to be a file, but got a directory: {p}")

    if expect_dir:
        if not os.access(p, os.R_OK | os.X_OK):
            raise ConfigError(f"directory '{p}' is not readable/executable")
    else:
        if not os.access(p, os.R_OK):
            raise ConfigError(f"file '{p}' is not readable")

    return p


def parse_year_month(value: str) -> tuple[int, int]:
    try:
        year_str, month_str = value.split("-")
        year, month = int(year_str), int(month_str)
        if not (1 <= month <= 12):
            raise ValueError
        return year, month
    except Exception:
        raise ConfigError(f"invalid date format for '{value}', expected YYYY-MM")


def validate_pairs(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError("'pairs' must be a list")
    pairs = [str(p).strip().upper() for p in value if str(p).strip()]
    if not pairs:
        raise ConfigError("'pairs' cannot be empty")
    return pairs


def validate_positive_float(value: Any, name: str) -> float:
    try:
        parsed_value = float(value)
    except Exception:
        raise ConfigError(f"'{name}' must be numeric")
    if not math.isfinite(parsed_value) or parsed_value <= 0:
        raise ConfigError(f"'{name}' must be finite and positive")
    return parsed_value


def validate_nonnegative_int(value: Any, name: str) -> int:
    try:
        parsed_value = int(value)
    except Exception:
        raise ConfigError(f"'{name}' must be an integer")
    if parsed_value < 0:
        raise ConfigError(f"'{name}' must be nonnegative")
    return parsed_value
