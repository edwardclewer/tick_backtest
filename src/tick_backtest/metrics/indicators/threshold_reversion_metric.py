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

"""Facade exposing the compiled ThresholdReversionMetric implementation."""

from __future__ import annotations

from importlib import import_module
from typing import Protocol, cast

__all__ = ["ThresholdReversionMetric"]


class ThresholdReversionMetricProtocol(Protocol):
    def update(self, tick: object) -> None:
        """Update the metric with a new tick."""

    def value_dict(self) -> dict[str, object]:
        """Return the current metric snapshot."""


class ThresholdReversionMetricFactory(Protocol):
    def __call__(
        self,
        *,
        name: str,
        lookback_seconds: int,
        threshold_pips: float,
        pip_size: float,
        tp_pips: float | None = None,
        sl_pips: float | None = None,
        min_recency_seconds: float = 0.0,
        trade_timeout_seconds: float | None = None,
    ) -> ThresholdReversionMetricProtocol:
        """Construct a threshold reversion metric."""


def _load_impl() -> ThresholdReversionMetricFactory:
    module = import_module("tick_backtest.metrics.indicators._threshold_reversion_metric")
    return cast(ThresholdReversionMetricFactory, module.ThresholdReversionMetric)


ThresholdReversionMetric = _load_impl()
