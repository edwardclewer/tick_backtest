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
import os
from setuptools import setup, Extension, find_packages
from Cython.Build import cythonize
import numpy as np

def ext(name: str, rel_src: str) -> Extension:
    # rel_src is relative to the "src" directory, POSIX style
    return Extension(
        name=name,
        sources=[os.path.join("src", rel_src)],  # RELATIVE paths
        include_dirs=[np.get_include()],
        extra_compile_args=["-O3"],
        extra_link_args=[],
        language="c",  # use "c++" if any .pyx uses c++
    )

# ---- REQUIRED: data feed + ALL indicator exts ----
ext_modules = [
    # data feed
    ext("tick_backtest.data_feed._data_feed",
        "tick_backtest/data_feed/_data_feed.pyx"),

    # indicators (include all you ship)
    ext("tick_backtest.metrics.indicators._ewma_metric",
        "tick_backtest/metrics/indicators/_ewma_metric.pyx"),
    ext("tick_backtest.metrics.indicators._ewma_slope_metric",
        "tick_backtest/metrics/indicators/_ewma_slope_metric.pyx"),
    ext("tick_backtest.metrics.indicators._ewma_vol_metric",
        "tick_backtest/metrics/indicators/_ewma_vol_metric.pyx"),
    ext("tick_backtest.metrics.indicators._zscore_metric",
        "tick_backtest/metrics/indicators/_zscore_metric.pyx"),
    ext("tick_backtest.metrics.indicators._session_metric",
        "tick_backtest/metrics/indicators/_session_metric.pyx"),
    ext("tick_backtest.metrics.indicators._spread_metric",
        "tick_backtest/metrics/indicators/_spread_metric.pyx"),
    ext("tick_backtest.metrics.indicators._threshold_reversion_metric",
        "tick_backtest/metrics/indicators/_threshold_reversion_metric.pyx"),
    ext("tick_backtest.metrics.indicators._tick_rate_metric",
        "tick_backtest/metrics/indicators/_tick_rate_metric.pyx"),
    ext("tick_backtest.metrics.indicators._drift_sign_metric",
        "tick_backtest/metrics/indicators/_drift_sign_metric.pyx"),
]

# ---- OPTIONAL (nice-to-have): core primitives/manager exts ----
# Enable these if your runtime imports them as compiled modules.
ext_modules += [
    ext("tick_backtest.metrics.primitives._base_metric",
        "tick_backtest/metrics/primitives/_base_metric.pyx"),
    ext("tick_backtest.metrics.primitives._ewma",
        "tick_backtest/metrics/primitives/_ewma.pyx"),
    ext("tick_backtest.metrics.primitives._tick_conversion",
        "tick_backtest/metrics/primitives/_tick_conversion.pyx"),
    ext("tick_backtest.metrics.primitives._time_rolling_window",
        "tick_backtest/metrics/primitives/_time_rolling_window.pyx"),
    ext("tick_backtest.metrics.primitives._time_weighted_histogram",
        "tick_backtest/metrics/primitives/_time_weighted_histogram.pyx"),
    ext("tick_backtest.metrics.manager._metrics_manager",
        "tick_backtest/metrics/manager/_metrics_manager.pyx"),
]

packages = find_packages(
    where="src",
    include=["tick_backtest", "tick_backtest.*"],
    exclude=[
        "tick_backtest.__pycache__", "tick_backtest.__pycache__.*",
    ],
)

setup(
    package_dir={"": "src"},
    packages=packages,
    include_package_data=True,
    zip_safe=False,
    ext_modules=cythonize(
        ext_modules,
        language_level=3,
        compiler_directives={"boundscheck": False, "wraparound": False, "cdivision": True},
    ),
)
