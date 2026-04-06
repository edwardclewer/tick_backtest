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

"""Facade exposing the compiled EWMAVolMetric implementation."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Protocol, cast

from tick_backtest.data_feed.tick import Tick

__all__ = ["EWMAVolMetric"]


class EWMAVolMetricProtocol(Protocol):
    name: str

    def __init__(
        self,
        *,
        name: str,
        tau_seconds: float,
        percentile_horizon_seconds: float,
        bins: int,
        base_vol: float,
        stddev_cap: float = 5.0,
    ) -> None: ...
    def update(self, tick: Tick) -> None: ...
    def value(self) -> dict[str, float]: ...


def _load_impl() -> type[EWMAVolMetricProtocol]:
    module = import_module("tick_backtest.metrics.indicators._ewma_vol_metric")
    return cast(type[EWMAVolMetricProtocol], module.EWMAVolMetric)


if TYPE_CHECKING:
    class EWMAVolMetric:
        name: str

        def __init__(
            self,
            *,
            name: str,
            tau_seconds: float,
            percentile_horizon_seconds: float,
            bins: int = 256,
            base_vol: float = 1e-4,
            stddev_cap: float = 5.0,
        ) -> None: ...
        def update(self, tick: Tick) -> None: ...
        def value(self) -> dict[str, float]: ...
else:
    EWMAVolMetric = _load_impl()
