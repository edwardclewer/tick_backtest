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

from typing import Dict, Type, Any, List
from pathlib import Path
import yaml

from tick_backtest.config_parsers.metrics.config_dataclass import MetricsConfigData, MetricConfigBase
from tick_backtest.config_parsers.metrics.config_registry import CONFIG_REGISTRY
from tick_backtest.config_validation import validate_metrics_config
from tick_backtest.exceptions import ConfigError


class MetricsConfigParser:
    """
    Parses and validates the metrics YAML configuration file.

    Produces validated MetricConfigBase-derived dataclasses
    which describe how runtime metric objects should be
    instantiated.
    """

    def __init__(
        self,
        metrics_config_path: Path,
        registry: Dict[str, Type[MetricConfigBase]] = CONFIG_REGISTRY,
    ):
        self.registry = registry
        self.metrics_config_path = metrics_config_path

        if not self.metrics_config_path.exists():
            raise FileNotFoundError(f"Metrics config not found: {metrics_config_path}")

    # ------------------------------------------------------------------
    def load_metrics_config(self) -> MetricsConfigData:
        """Load and validate the metrics YAML into config dataclasses."""

        # --- Parse YAML ---
        try:
            with self.metrics_config_path.open("r", encoding="utf-8") as f:
                raw: Dict[str, Any] = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Error parsing YAML at {self.metrics_config_path}: {e}") from e

        if not isinstance(raw, dict):
            raise ConfigError("Invalid metrics config: root must be a mapping (YAML dict)")

        try:
            validated = validate_metrics_config(raw)
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

        metrics_raw = validated.get("metrics", [])

        configs: List[MetricConfigBase] = []
        seen_names: set[str] = set()

        # --- Build config dataclasses ---
        for i, entry in enumerate(metrics_raw, start=1):
            if not isinstance(entry, dict):
                raise ConfigError(f"Entry #{i} in 'metrics' list must be a mapping, got {type(entry).__name__}")

            name = entry.get("name")
            metric_type = entry.get("type")
            enabled = entry.get("enabled", True)
            params = entry.get("params", {})

            if not (name and metric_type):
                raise ConfigError(f"Metric entry missing 'name' or 'type': {entry}")

            config_class = self.registry.get(metric_type)
            if config_class is None:
                raise ConfigError(f"Unrecognized metric type '{metric_type}' in entry #{i}")

            if not isinstance(params, dict):
                raise ConfigError(f"'params' for metric '{name}' must be a mapping (YAML dict)")

            try:
                metric_kwargs = dict(params)
                config_obj = config_class(
                    name=name,
                    metric_type=metric_type,
                    enabled=enabled,
                    **metric_kwargs,
                )
            except Exception as e:
                raise ConfigError(
                    f"Failed to instantiate config for metric '{name}' of type '{metric_type}': {e}"
                ) from e

            if name in seen_names:
                raise ConfigError(f"Duplicate metric name detected: '{name}'")
            seen_names.add(name)
            configs.append(config_obj)

        schema_version = validated.get("schema_version", "1.0")
        return MetricsConfigData(schema_version=schema_version, metrics=configs)
