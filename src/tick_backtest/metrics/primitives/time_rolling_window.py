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

"""Public facade for the TimeRollingWindow primitive.

Prefers the Cython implementation when available, falling back to the
pure Python reference kept for parity and testing.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Protocol, cast

__all__ = ["TimeRollingWindow"]


class TimeRollingWindowProtocol(Protocol):
    sum_w: float
    sum_x: float
    sum_x2: float

    def __init__(self, lookback_seconds: float) -> None: ...
    def __len__(self) -> int: ...
    def append(self, ts: float, value: float, dt: float) -> None: ...
    def stats(self) -> tuple[float, float]: ...


def _load_impl() -> type[TimeRollingWindowProtocol]:
    module = import_module("tick_backtest.metrics.primitives._time_rolling_window")
    return cast(type[TimeRollingWindowProtocol], module.TimeRollingWindow)


if TYPE_CHECKING:
    from ._time_rolling_window_py import PyTimeRollingWindow as TimeRollingWindow
else:
    try:
        TimeRollingWindow = _load_impl()
    except ImportError:  # pragma: no cover - fallback when extension unavailable
        from ._time_rolling_window_py import PyTimeRollingWindow as TimeRollingWindow
