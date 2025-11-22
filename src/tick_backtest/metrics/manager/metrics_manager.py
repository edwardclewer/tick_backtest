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

"""Facade for the compiled metrics manager implementation."""

from __future__ import annotations

import logging
from importlib import import_module
from pathlib import Path
from typing import Dict, List

from tick_backtest.config_parsers.metrics.config_dataclass import MetricsConfigData
from tick_backtest.config_parsers.metrics.config_parser import MetricsConfigParser
from tick_backtest.data_feed.tick import Tick
from tick_backtest.metrics.manager.metric_registry import METRIC_CLASS_REGISTRY
from tick_backtest.metrics.primitives.base_metric import BaseMetric


def _load_impl():
    module = import_module("tick_backtest.metrics.manager._metrics_manager")
    return getattr(module, "MetricsManager")


_CompiledManager = _load_impl()


class MetricsManager:
    def __init__(self, metrics_config_path: Path) -> None:
        parser = MetricsConfigParser(metrics_config_path)
        config_data: MetricsConfigData = parser.load_metrics_config()

        metrics: List[BaseMetric] = []
        for cfg in config_data.metrics:
            if hasattr(cfg, "enabled") and not getattr(cfg, "enabled", True):
                logger.info("metric disabled via config", extra={"metric_name": cfg.name})
                continue

            metric_cls = METRIC_CLASS_REGISTRY.get(cfg.metric_type)
            if metric_cls is None:
                raise ValueError(f"Unrecognized metric type '{cfg.metric_type}'")

            try:
                metric = metric_cls(name=cfg.name, **cfg.to_kwargs())
            except Exception as exc:  # pragma: no cover - config errors
                raise ValueError(
                    f"Failed to instantiate metric '{cfg.name}' of type '{cfg.metric_type}': {exc}"
                ) from exc

            metrics.append(metric)

        self.metrics = metrics
        self._impl = _CompiledManager(metrics)

    def update(self, tick: Tick) -> Dict[str, float]:
        return self._impl.update_all(tick)

    def current(self) -> Dict[str, float]:
        return self._impl.current()
logger = logging.getLogger(__name__)
