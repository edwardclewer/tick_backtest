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

import math
from typing import Dict, Iterable

from tick_backtest.config_parsers.strategy.config_dataclass import PredicateConfig


def _to_float(value, default=math.nan) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        return float(value)
    except Exception:
        return default


class PredicateEvaluator:
    """Evaluate configured predicates against the current metric snapshot."""

    _OPS = {
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }

    @classmethod
    def evaluate(cls, predicate: PredicateConfig, metrics: Dict[str, float]) -> bool:
        left = _to_float(metrics.get(predicate.metric))
        if not math.isfinite(left):
            return False
        if predicate.use_abs:
            left = abs(left)

        if predicate.value is not None:
            right = float(predicate.value)
        else:
            right = _to_float(metrics.get(predicate.other_metric))
            if not math.isfinite(right):
                return False

        op = cls._OPS[predicate.operator]
        return bool(op(left, right))

    @classmethod
    def evaluate_all(cls, predicates: Iterable[PredicateConfig], metrics: Dict[str, float]) -> bool:
        return all(cls.evaluate(pred, metrics) for pred in predicates)

