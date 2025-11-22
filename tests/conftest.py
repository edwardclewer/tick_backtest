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

"""Shared pytest fixtures and utilities for the forthcoming test suite."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import importlib.util
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
signal_init = PROJECT_ROOT / "signal" / "__init__.py"
if signal_init.exists():
    spec = importlib.util.spec_from_file_location(
        "signal",
        signal_init,
        submodule_search_locations=[str(signal_init.parent)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["signal"] = module
    spec.loader.exec_module(module)

import pandas as pd
import pytest

from tick_backtest.data_feed.tick import Tick


@pytest.fixture
def tick_factory() -> Callable[[float, float, float, datetime | None], Tick]:
    """Return a factory that builds `Tick` objects with sensible defaults."""

    def _factory(
        bid: float = 1.0000,
        ask: float = 1.0001,
        mid: float | None = None,
        timestamp: datetime | None = None,
    ) -> Tick:
        ts = timestamp or datetime(2015, 1, 1, tzinfo=timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ts_seconds = ts.timestamp()
        actual_mid = mid if mid is not None else (bid + ask) * 0.5
        return Tick(ts_seconds, bid, ask, actual_mid)

    return _factory


@pytest.fixture
def tick_series_factory(tick_factory: Callable[..., Tick]) -> Callable[[Iterable[tuple[float, float]]], list[Tick]]:
    """Return a helper that creates a list of ticks from bid/ask pairs."""

    def _series(pairs: Iterable[tuple[float, float]]):
        base_time = datetime(2015, 1, 1, tzinfo=timezone.utc)
        ticks: list[Tick] = []
        for idx, (bid, ask) in enumerate(pairs):
            ticks.append(
                tick_factory(
                    bid=bid,
                    ask=ask,
                    timestamp=base_time + pd.Timedelta(seconds=idx),
                )
            )
        return ticks

    return _series


@pytest.fixture
def metrics_snapshot() -> dict[str, Any]:
    """Sample metrics payload mirroring `MetricsManager.current()` output."""

    return {
        "z30m.z_score": 0.0,
        "z30m.rolling_residual": 0.0,
        "ewma_vol_30m.vol_ewma": 1e-6,
        "ewma_vol_30m.vol_percentile": 0.5,
        "drift_sign.drift": 0.0,
        "drift_sign.drift_sign": 0,
        "session.session_label": "London",
        "ewma_mid_5m.ewma": 1.2345,
        "ewma_mid_30m.ewma": 1.2335,
        "ewma_mid_5m_slope.ewma": 1.2345,
        "ewma_mid_5m_slope.slope": 0.00001,
        "spread_60s.spread": 0.0001,
        "spread_60s.spread_pips": 1.0,
        "spread_60s.spread_percentile": 0.4,
        "tick_rate_30s.tick_count": 10.0,
        "tick_rate_30s.tick_rate_per_sec": 0.5,
        "tick_rate_30s.tick_rate_per_min": 30.0,
    }


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Return a temporary path to hold generated YAML configs in tests."""

    config_file = tmp_path / "config.yaml"
    config_file.write_text("# populated during tests\n")
    return config_file
