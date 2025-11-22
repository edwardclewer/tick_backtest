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

# src/tick_backtest/_build.py
from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
from setuptools import Extension
from setuptools.command.build_ext import build_ext as _build_ext

# Optional Cython
try:
    from Cython.Build import cythonize  # type: ignore
    HAVE_CYTHON = True
except Exception:  # pragma: no cover
    cythonize = None  # type: ignore
    HAVE_CYTHON = False

CYTHON_DIRECTIVES = {
    "language_level": 3,
    "boundscheck": False,
    "wraparound": False,
    "cdivision": True,
}

# Paths:
#   this file -> src/tick_backtest/_build.py
SRC_DIR = Path(__file__).resolve().parents[1]   # .../src
PROJECT_ROOT = SRC_DIR.parent                    # repo root (where setup.py lives)

MODULES: List[str] = [
    # primitives
    "tick_backtest.metrics.primitives._time_rolling_window",
    "tick_backtest.metrics.primitives._base_metric",
    "tick_backtest.metrics.primitives._time_weighted_histogram",
    "tick_backtest.metrics.primitives._ewma",
    "tick_backtest.metrics.primitives._tick_conversion",

    # manager
    "tick_backtest.metrics.manager._metrics_manager",

    # indicators
    "tick_backtest.metrics.indicators._zscore_metric",
    "tick_backtest.metrics.indicators._drift_sign_metric",
    "tick_backtest.metrics.indicators._session_metric",
    "tick_backtest.metrics.indicators._ewma_vol_metric",
    "tick_backtest.metrics.indicators._ewma_metric",
    "tick_backtest.metrics.indicators._ewma_slope_metric",
    "tick_backtest.metrics.indicators._spread_metric",
    "tick_backtest.metrics.indicators._tick_rate_metric",
    "tick_backtest.metrics.indicators._threshold_reversion_metric",

    # data feed
    "tick_backtest.data_feed._data_feed",
]


def _choose_source(modname: str) -> tuple[Path, str | None]:
    """
    Return (relative_source_path, language) for the module.
    Prefers .pyx when Cython is present, otherwise .cpp/.c.
    """
    base_abs = SRC_DIR / modname.replace(".", "/")
    order = (".pyx", ".cpp", ".c") if HAVE_CYTHON else (".cpp", ".c", ".pyx")

    for ext in order:
        p = base_abs.with_suffix(ext)
        if p.exists():
            lang = "c++" if ext == ".cpp" else None
            # setuptools requires sources to be *relative* to setup.py dir
            return p.resolve().relative_to(PROJECT_ROOT), lang

    # Last-chance scan in fixed order
    for ext in (".cpp", ".c", ".pyx"):
        p = base_abs.with_suffix(ext)
        if p.exists():
            lang = "c++" if ext == ".cpp" else None
            return p.resolve().relative_to(PROJECT_ROOT), lang

    raise FileNotFoundError(
        f"No source file for {modname} under {base_abs}.(pyx|c|cpp)"
    )


def _make_extension(modname: str) -> Extension:
    src_rel, lang = _choose_source(modname)
    kwargs = {"language": lang} if lang else {}
    return Extension(
        modname,
        sources=[src_rel.as_posix()],          # <= RELATIVE POSIX PATH
        include_dirs=[np.get_include()],
        **kwargs,
    )


def get_extensions() -> list[Extension]:
    return [_make_extension(m) for m in MODULES]


class BuildExt(_build_ext):
    """Cython-aware build_ext that applies shared compiler directives."""

    def build_extensions(self) -> None:  # noqa: D401
        if not self.extensions:
            self.extensions = get_extensions()

        np_inc = np.get_include()
        any_pyx = any(any(str(s).endswith(".pyx") for s in ext.sources) for ext in self.extensions)

        if any_pyx and not HAVE_CYTHON:
            missing = [
                ext.name for ext in self.extensions
                if any(str(s).endswith(".pyx") for s in ext.sources)
            ]
            raise RuntimeError(
                "Cython is required to build these extensions from .pyx sources:\n"
                + "\n".join(f"  - {m}" for m in missing)
                + "\nEither install Cython or include pre-generated .c/.cpp in the sdist."
            )

        if any_pyx and HAVE_CYTHON:
            self.extensions = cythonize(  # type: ignore[misc]
                self.extensions,
                compiler_directives=CYTHON_DIRECTIVES,
                include_path=[np_inc, SRC_DIR.as_posix()],
                language_level=3,
            )

        for ext in self.extensions:
            if np_inc not in getattr(ext, "include_dirs", []):
                ext.include_dirs.append(np_inc)
            # Avoid stub generation; these are pure extension modules
            setattr(ext, "_needs_stub", False)

        super().build_extensions()
