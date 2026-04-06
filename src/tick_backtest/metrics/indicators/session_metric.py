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

"""Facade exposing the compiled SessionMetric implementation."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Protocol, cast

from tick_backtest.data_feed.tick import Tick

__all__ = ["SessionMetric"]


class SessionMetricProtocol(Protocol):
    name: str

    def __init__(self, *, name: str) -> None: ...
    def update(self, tick: Tick) -> None: ...
    def value(self) -> dict[str, float]: ...


def _load_impl() -> type[SessionMetricProtocol]:
    module = import_module("tick_backtest.metrics.indicators._session_metric")
    return cast(type[SessionMetricProtocol], module.SessionMetric)


if TYPE_CHECKING:
    SessionMetric = SessionMetricProtocol
else:
    SessionMetric = _load_impl()
