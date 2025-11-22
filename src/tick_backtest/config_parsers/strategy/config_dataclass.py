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

from dataclasses import dataclass, field
from typing import List, Optional

from tick_backtest.config_parsers.strategy.entry_configs import EntryParamsBase


VALID_OPERATORS = {"<", "<=", ">", ">=", "==", "!="}


@dataclass(kw_only=True)
class PredicateConfig:
    """Declarative rule comparing a metric against a constant or another metric."""

    metric: str
    operator: str
    value: Optional[float] = None
    other_metric: Optional[str] = None
    use_abs: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.metric, str) or not self.metric:
            raise ValueError("Predicate 'metric' must be a non-empty string")

        if not isinstance(self.operator, str) or self.operator not in VALID_OPERATORS:
            raise ValueError(
                f"Predicate 'operator' must be one of {sorted(VALID_OPERATORS)}, got {self.operator!r}"
            )

        if self.value is None and self.other_metric is None:
            raise ValueError("Predicate must define either 'value' or 'other_metric'")

        if self.value is not None and self.other_metric is not None:
            raise ValueError("Predicate cannot define both 'value' and 'other_metric'")

        if self.value is not None:
            if isinstance(self.value, bool):
                raise TypeError("Predicate 'value' must be numeric, not bool")
            try:
                self.value = float(self.value)
            except Exception as exc:
                raise TypeError("Predicate 'value' must be numeric") from exc

        if self.other_metric is not None:
            if not isinstance(self.other_metric, str) or not self.other_metric:
                raise ValueError("Predicate 'other_metric' must be a non-empty string")

        if not isinstance(self.use_abs, bool):
            raise TypeError("Predicate 'use_abs' must be a boolean")


@dataclass(kw_only=True)
class EntryConfig:
    """Single entry definition for the strategy."""

    name: str
    engine: str
    params: EntryParamsBase
    predicates: List[PredicateConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Entry 'name' must be a non-empty string")
        if not isinstance(self.engine, str) or not self.engine:
            raise ValueError("Entry 'engine' must be a non-empty string")
        if not isinstance(self.params, EntryParamsBase):
            raise TypeError("Entry 'params' must be an EntryParamsBase instance")
        if not isinstance(self.predicates, list):
            raise TypeError("Entry 'predicates' must be a list")


@dataclass(kw_only=True)
class ExitConfig:
    """Single exit definition governed by predicates."""

    name: str
    predicates: List[PredicateConfig] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Exit 'name' must be a non-empty string")
        if not isinstance(self.predicates, list):
            raise TypeError("Exit 'predicates' must be a list")


@dataclass(kw_only=True)
class StrategyConfigData:
    """Top-level strategy definition containing entry/exit rules."""

    schema_version: str
    name: str
    entry: EntryConfig
    exit: ExitConfig

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str) or not self.schema_version:
            raise ValueError("Strategy 'schema_version' must be a non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Strategy 'name' must be a non-empty string")
