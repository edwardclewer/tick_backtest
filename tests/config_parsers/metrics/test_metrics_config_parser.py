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

"""Tests for the metrics config parser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import pytest

from tick_backtest.config_parsers.metrics.config_parser import MetricsConfigParser
from tick_backtest.config_parsers.metrics.config_dataclass import MetricConfigBase
from tick_backtest.exceptions import ConfigError


SCHEMA_HEADER = 'schema_version: "1.0"'


@dataclass(kw_only=True)
class StubMetricConfig(MetricConfigBase):
    """Minimal MetricConfig that records constructor parameters for assertions."""

    window: int
    alpha: float = 1.0

    def to_kwargs(self) -> Dict[str, Any]:
        payload = super().to_kwargs()
        payload.update({"window": self.window, "alpha": self.alpha})
        return payload


def _write_config(tmp_path: Path, yaml_text: str) -> Path:
    path = tmp_path / "metrics.yaml"
    path.write_text(yaml_text)
    return path


def test_load_metrics_config_instantiates_registry_entries(tmp_path: Path):
    """Expect registry-driven instantiation with provided parameters."""

    config_path = _write_config(
        tmp_path,
        f"""
{SCHEMA_HEADER}
metrics:
    - name: alpha
      type: stub
      params:
        window: 5
    - name: beta
      type: stub
      params:
        window: 10
        """,
    )

    parser = MetricsConfigParser(config_path, registry={"stub": StubMetricConfig})
    config = parser.load_metrics_config()

    assert [metric.name for metric in config.metrics] == ["alpha", "beta"]
    assert isinstance(config.metrics[0], StubMetricConfig)
    assert config.metrics[0].window == 5
    assert config.metrics[0].alpha == 1.0
    assert config.metrics[0].to_kwargs() == {"window": 5, "alpha": 1.0}
    assert config.schema_version == "1.0"
    assert isinstance(config.metrics[1], StubMetricConfig)
    assert config.metrics[1].window == 10


def test_load_metrics_config_requires_schema_version(tmp_path: Path):
    """Metrics config must declare a schema version."""

    config_path = _write_config(
        tmp_path,
        """
metrics:
    - name: alpha
      type: stub
      params:
        window: 5
        """,
    )

    parser = MetricsConfigParser(config_path, registry={"stub": StubMetricConfig})
    with pytest.raises(ConfigError) as excinfo:
        parser.load_metrics_config()

    assert "schema_version" in str(excinfo.value)


def test_load_metrics_config_rejects_unknown_metric_type(tmp_path: Path):
    """An unknown `type` value should raise a ValueError."""

    config_path = _write_config(
        tmp_path,
        f"""
{SCHEMA_HEADER}
metrics:
    - name: mystery
      type: missing
      params: {{}}
        """,
    )

    parser = MetricsConfigParser(config_path, registry={})
    with pytest.raises(ConfigError) as excinfo:
        parser.load_metrics_config()

    assert "Unrecognized metric type" in str(excinfo.value)


def test_load_metrics_config_enforces_list_structure(tmp_path: Path):
    """Top-level `metrics` must be a list."""

    config_path = _write_config(
        tmp_path,
        f"""
{SCHEMA_HEADER}
metrics:
    name: not-a-list
    type: stub
        """,
    )

    parser = MetricsConfigParser(config_path, registry={"stub": StubMetricConfig})
    with pytest.raises(ConfigError) as excinfo:
        parser.load_metrics_config()

    assert "invalid metrics configuration" in str(excinfo.value).lower()
    assert "'metrics' must be a list" in str(excinfo.value)


def test_load_metrics_config_rejects_unknown_top_level_key(tmp_path: Path):
    """Extra root keys should be rejected by schema validation."""

    config_path = _write_config(
        tmp_path,
        f"""
{SCHEMA_HEADER}
metrics:
    - name: alpha
      type: stub
      params:
        window: 5
unexpected: true
        """,
    )

    parser = MetricsConfigParser(config_path, registry={"stub": StubMetricConfig})
    with pytest.raises(ConfigError) as excinfo:
        parser.load_metrics_config()

    assert "invalid metrics configuration" in str(excinfo.value).lower()


def test_load_metrics_config_rejects_unknown_metric_field(tmp_path: Path):
    """Unknown keys within a metric definition should fail validation."""

    config_path = _write_config(
        tmp_path,
        f"""
{SCHEMA_HEADER}
metrics:
    - name: alpha
      type: stub
      params:
        window: 5
      extra_field: 123
        """,
    )

    parser = MetricsConfigParser(config_path, registry={"stub": StubMetricConfig})
    with pytest.raises(ConfigError) as excinfo:
        parser.load_metrics_config()

    assert "invalid metrics configuration" in str(excinfo.value).lower()


def test_load_metrics_config_rejects_duplicate_names(tmp_path: Path):
    """Duplicate metric names should not be allowed."""

    config_path = _write_config(
        tmp_path,
        f"""
{SCHEMA_HEADER}
metrics:
    - name: alpha
      type: stub
      params:
        window: 5
    - name: alpha
      type: stub
      params:
        window: 10
        """,
    )

    parser = MetricsConfigParser(config_path, registry={"stub": StubMetricConfig})
    with pytest.raises(ConfigError) as excinfo:
        parser.load_metrics_config()

    assert "duplicate metric name" in str(excinfo.value).lower()
