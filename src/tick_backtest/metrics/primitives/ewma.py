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
from typing import TYPE_CHECKING, Protocol, cast

__all__ = ["EWMA"]


class EWMAProtocol(Protocol):
    y: float

    def __init__(self, tau_seconds: float, power: int = 1) -> None: ...
    def reset(self) -> None: ...
    def update(self, t: float, x: float) -> float: ...


def _load_impl() -> type[EWMAProtocol]:
    module = import_module("tick_backtest.metrics.primitives._ewma")
    return cast(type[EWMAProtocol], module.EWMA)


if TYPE_CHECKING:
    from ._ewma_py import PyEWMA as EWMA
else:
    try:
        EWMA = _load_impl()
    except ImportError:  # pragma: no cover - fallback when extension unavailable
        from ._ewma_py import PyEWMA as EWMA
