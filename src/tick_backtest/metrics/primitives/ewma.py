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

"""Facade for the EWMA primitive, preferring the Cython implementation."""

from __future__ import annotations

from importlib import import_module
from typing import Type

__all__ = ["EWMA"]


def _load_impl() -> Type[object]:
    module = import_module("tick_backtest.metrics.primitives._ewma")
    return getattr(module, "EWMA")


try:
    EWMA = _load_impl()
except ImportError:
    from ._ewma_py import PyEWMA as EWMA  # noqa: F401
