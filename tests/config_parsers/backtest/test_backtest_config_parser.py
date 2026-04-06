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


def test_parse_config_resolves_relative_paths_from_config_directory(tmp_path: Path) -> None:
    config_dir = tmp_path / "config_bundle"
    config_dir.mkdir()
    data_dir = config_dir / "data"
    data_dir.mkdir()

    metrics_path = config_dir / "metrics.yaml"
    metrics_path.write_text(MIN_METRICS_YAML)

    strategy_path = config_dir / "strategy.yaml"
    strategy_path.write_text(MIN_STRATEGY_YAML)

    config_path = _write_config(
        config_dir,
        """
schema_version: "1.0"
pairs: [EURUSD]
start: 2015-01
end: 2015-02
pip_size: 0.0001
warmup_seconds: 600
data_base_path: ./data
output_base_path: ./outputs
metrics_config_path: ./metrics.yaml
strategy_config_path: ./strategy.yaml
        """,
    )

    parser = BacktestConfigParser()
    cfg = parser.parse_config(config_path)

    assert cfg.data_base_path == data_dir.resolve()
    assert cfg.output_base_path == (config_dir / "outputs").resolve()
    assert cfg.metrics_config_path == metrics_path.resolve()
    assert cfg.strategy_config_path == strategy_path.resolve()


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


def test_parse_config_accepts_strategy_references_to_metric_output_fields(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "metrics:",
                "  - name: ewma_mid_5m",
                "    type: ewma",
                "    enabled: true",
                "    params:",
                "      tau_seconds: 300",
                "      price_field: mid",
                "  - name: ewma_mid_30m",
                "    type: ewma",
                "    enabled: true",
                "    params:",
                "      tau_seconds: 1800",
                "      price_field: mid",
                "",
            ]
        )
    )

    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "strategy:",
                "  name: crossover_strategy",
                "  entry:",
                "    name: entry",
                "    engine: ewma_crossover",
                "    params:",
                "      fast_metric: ewma_mid_5m.ewma",
                "      slow_metric: ewma_mid_30m.ewma",
                "    predicates: []",
                "  exit:",
                "    name: exit",
                "    predicates:",
                "      - metric: ewma_mid_5m.ewma",
                "        operator: '<'",
                "        other_metric: ewma_mid_30m.ewma",
                "",
            ]
        )
    )

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

    assert cfg.strategy_config.entry.params.fast_metric == "ewma_mid_5m.ewma"
    assert cfg.strategy_config.exit.predicates[0].other_metric == "ewma_mid_30m.ewma"


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


def test_parse_config_rejects_strategy_reference_to_unknown_metric(tmp_path: Path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    metrics_path = tmp_path / "metrics.yaml"
    metrics_path.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "metrics:",
                "  - name: known_metric",
                "    type: zscore",
                "    enabled: true",
                "    params:",
                "      lookback_seconds: 300",
                "",
            ]
        )
    )

    strategy_path = tmp_path / "strategy.yaml"
    strategy_path.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                "strategy:",
                "  name: stub_strategy",
                "  entry:",
                "    name: entry",
                "    engine: stub",
                "    params: {}",
                "    predicates:",
                "      - metric: missing_metric",
                "        operator: '>'",
                "        value: 1",
                "  exit:",
                "    name: exit",
                "    predicates: []",
                "",
            ]
        )
    )

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
    with pytest.raises(ConfigError) as excinfo:
        parser.parse_config(config_path)

    assert "invalid strategy configuration" in str(excinfo.value).lower()
    assert "missing_metric" in str(excinfo.value)
