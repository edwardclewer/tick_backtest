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

"""Tests for the strategy config parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from tick_backtest.config_parsers.strategy.config_parser import StrategyConfigParser
from tick_backtest.exceptions import ConfigError


SCHEMA_HEADER = 'schema_version: "1.0"'


def _write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "strategy.yaml"
    path.write_text(text)
    return path


MIN_STRATEGY_YAML = "\n".join(
    [
        SCHEMA_HEADER,
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


def test_strategy_parser_loads_minimal_config(tmp_path: Path):
    path = _write_config(tmp_path, MIN_STRATEGY_YAML)
    parser = StrategyConfigParser(path)
    data = parser.load()
    assert data.name == "stub_strategy"
    assert data.entry.engine == "stub"
    assert data.exit.name == "exit"
    assert data.schema_version == "1.0"


def test_strategy_parser_requires_schema_version(tmp_path: Path):
    path = _write_config(
        tmp_path,
        "\n".join(
            [
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
        ),
    )
    parser = StrategyConfigParser(path)
    with pytest.raises(ConfigError) as excinfo:
        parser.load()
    assert "schema_version" in str(excinfo.value)


def test_strategy_parser_rejects_unknown_top_level_key(tmp_path: Path):
    path = _write_config(
        tmp_path,
        "\n".join(
            [
                SCHEMA_HEADER,
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
                "unexpected: true",
                "",
            ]
        ),
    )
    parser = StrategyConfigParser(path)
    with pytest.raises(ConfigError) as excinfo:
        parser.load()
    assert "invalid strategy configuration" in str(excinfo.value).lower()


def test_strategy_parser_rejects_unknown_predicate_field(tmp_path: Path):
    path = _write_config(
        tmp_path,
        "\n".join(
            [
                SCHEMA_HEADER,
                "strategy:",
                "  name: stub_strategy",
                "  entry:",
                "    name: entry",
                "    engine: stub",
                "    params: {}",
                "    predicates:",
                "      - metric: foo",
                "        operator: '>'",
                "        value: 1",
                "        extra: true",
                "  exit:",
                "    name: exit",
                "    predicates: []",
                "",
            ]
        ),
    )
    parser = StrategyConfigParser(path)
    with pytest.raises(ConfigError) as excinfo:
        parser.load()
    assert "invalid strategy configuration" in str(excinfo.value).lower()


def test_strategy_parser_rejects_duplicate_predicates(tmp_path: Path):
    path = _write_config(
        tmp_path,
        "\n".join(
            [
                SCHEMA_HEADER,
                "strategy:",
                "  name: stub_strategy",
                "  entry:",
                "    name: entry",
                "    engine: stub",
                "    params: {}",
                "    predicates:",
                "      - metric: foo",
                "        operator: '>'",
                "        value: 1",
                "      - metric: foo",
                "        operator: '>'",
                "        value: 1",
                "  exit:",
                "    name: exit",
                "    predicates: []",
                "",
            ]
        ),
    )
    parser = StrategyConfigParser(path)
    with pytest.raises(ConfigError) as excinfo:
        parser.load()
    assert "duplicate predicate" in str(excinfo.value).lower()
