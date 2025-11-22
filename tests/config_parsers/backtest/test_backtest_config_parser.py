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

"""Tests for the backtest config parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from tick_backtest.config_parsers.backtest.config_parser import BacktestConfigParser
from tick_backtest.exceptions import ConfigError


MIN_STRATEGY_YAML = "\n".join(
    [
        'schema_version: "1.0"',
        "strategy:",
        "  name: stub_strategy",
        "  entry:",
        "    name: entry",
        "    engine: stub",
        "    params: {}",
        "    predicates: []",
        "  exit:",
        "    name: exit",
        "    predicates: []",
        "",
    ]
)

MIN_METRICS_YAML = 'schema_version: "1.0"\nmetrics: []\n'


def _write_config(tmp_path: Path, yaml_text: str) -> Path:
    """Helper to write a temporary YAML file."""
    path = tmp_path / "config.yaml"
    path.write_text(yaml_text)
    return path


def test_parse_config_loads_yaml(tmp_path: Path):
    """Parser should read YAML and return a populated dataclass."""

    # create real directories so path validation passes
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)

    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        tmp_path,
        f"""
schema_version: "1.0"
pairs: [EURUSD]
start: 2015-01
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: {data_dir}
output_base_path: {output_dir}
metrics_config_path: {metrics_path}
strategy_config_path: {strategy_path}
        """,
    )

    parser = BacktestConfigParser()
    cfg = parser.parse_config(config_path)

    assert cfg.pairs == ["EURUSD"]
    assert cfg.data_base_path == data_dir
    assert cfg.output_base_path == output_dir
    assert (cfg.year_start, cfg.month_start) == (2015, 1)
    assert (cfg.year_end, cfg.month_end) == (2015, 2)
    assert cfg.pip_size == pytest.approx(0.0001)
    assert cfg.warmup_seconds == 600
    assert cfg.schema_version == "1.0"


def test_parse_config_requires_schema_version(tmp_path: Path):
    """Backtest configs without schema_version should fail fast."""

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)

    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        tmp_path,
        f"""
pairs: [EURUSD]
start: 2015-01
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: {data_dir}
output_base_path: {output_dir}
metrics_config_path: {metrics_path}
strategy_config_path: {strategy_path}
        """,
    )

    parser = BacktestConfigParser()
    with pytest.raises(ConfigError) as excinfo:
        parser.parse_config(config_path)

    assert "schema_version" in str(excinfo.value)


def test_parse_config_validates_required_keys(tmp_path: Path):
    """Ensure missing required keys surface as a ConfigError."""

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        tmp_path,
        f"""
schema_version: "1.0"
pairs: [EURUSD]
start: 2015-01
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: {data_dir}
metrics_config_path: {metrics_path}
strategy_config_path: {strategy_path}
        """,
    )

    parser = BacktestConfigParser()
    with pytest.raises(ConfigError) as excinfo:
        parser.parse_config(config_path)

    assert "invalid backtest configuration" in str(excinfo.value).lower()


def test_parse_config_rejects_start_after_end(tmp_path: Path):
    """Start date must not exceed end date."""

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        tmp_path,
        f"""
schema_version: "1.0"
pairs: [EURUSD]
start: 2015-04
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: {data_dir}
output_base_path: {output_dir}
metrics_config_path: {metrics_path}
strategy_config_path: {strategy_path}
        """,
    )

    parser = BacktestConfigParser()
    with pytest.raises(ConfigError) as excinfo:
        parser.parse_config(config_path)

    assert "start date must be on or before end date" in str(excinfo.value)


def test_parse_config_rejects_invalid_date_format(tmp_path: Path):
    """Detect malformed start/end date strings and report a ConfigError."""

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        tmp_path,
        f"""
schema_version: "1.0"
pairs: [EURUSD]
start: 201501
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: {data_dir}
output_base_path: {output_dir}
metrics_config_path: {metrics_path}
strategy_config_path: {strategy_path}
        """,
    )

    parser = BacktestConfigParser()
    with pytest.raises(ConfigError) as excinfo:
        parser.parse_config(config_path)

    assert "invalid backtest configuration" in str(excinfo.value).lower()
    assert "'start' must be a string" in str(excinfo.value)


def test_parse_config_requires_pairs_list(tmp_path: Path):
    """Non-list `pairs` should trigger a ConfigError."""

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        tmp_path,
        f"""
schema_version: "1.0"
pairs: EURUSD
start: 2015-01
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: {data_dir}
output_base_path: {output_dir}
metrics_config_path: {metrics_path}
strategy_config_path: {strategy_path}
        """,
    )

    parser = BacktestConfigParser()
    with pytest.raises(ConfigError) as excinfo:
        parser.parse_config(config_path)

    assert "invalid backtest configuration" in str(excinfo.value).lower()
    assert "'pairs' must be a non-empty list" in str(excinfo.value)


def test_parse_config_rejects_unknown_keys(tmp_path: Path):
    """Unexpected keys should be rejected by schema validation."""

    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)
    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        tmp_path,
        f"""
schema_version: "1.0"
pairs: [EURUSD]
start: 2015-01
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: {data_dir}
output_base_path: {output_dir}
metrics_config_path: {metrics_path}
strategy_config_path: {strategy_path}
unexpected_key: true
        """,
    )

    parser = BacktestConfigParser()
    with pytest.raises(ConfigError) as excinfo:
        parser.parse_config(config_path)

    assert "invalid backtest configuration" in str(excinfo.value).lower()
