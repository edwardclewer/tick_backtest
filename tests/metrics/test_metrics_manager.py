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

"""Tests for the MetricsManager runtime behaviour (aligned to current source)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable
import textwrap

import pytest

from tick_backtest.metrics.manager.metrics_manager import MetricsManager


@dataclass
class DummyMetric:
    """Simple metric stub used to verify MetricsManager behaviour."""

    name: str
    payloads: list[dict[str, Any]]

    def __post_init__(self) -> None:
        self.updates: list[Any] = []
        self._index = 0

    def update(self, tick: Any) -> None:
        """Record the tick for validation."""
        self.updates.append(tick)

    def value(self) -> Dict[str, Any]:
        """Return deterministic metric values."""
        if not self.payloads:
            return {}
        idx = min(self._index, len(self.payloads) - 1)
        self._index += 1
        return self.payloads[idx]


# ---------------------------------------------------------------------------


@pytest.fixture
def manager_factory(monkeypatch):
    """Patch MetricsConfigParser + registry so MetricsManager builds DummyMetrics."""

    def _factory(metrics: Iterable[DummyMetric]) -> MetricsManager:
        # Build fake config dataclass objects to simulate parser output
        class DummyConfig:
            def __init__(self, name: str, metric_type: str, metric: DummyMetric):
                self.name = name
                self.metric_type = metric_type
                self._metric = metric

            def to_kwargs(self):
                # pass through DummyMetric's payloads so constructor gets them
                return {"payloads": self._metric.payloads}

        fake_configs = [
            DummyConfig(m.name, f"type_{i}", m) for i, m in enumerate(metrics)
        ]

        class StubParser:
            def __init__(self, *_args, **_kwargs):
                self._config = type(
                    "StubMetricsConfigData",
                    (),
                    {
                        "metrics": fake_configs,
                        "schema_version": "1.0",
                    },
                )()

            def load_metrics_config(self):
                return self._config

        # Patch both parser + registry used by MetricsManager
        monkeypatch.setattr(
            "tick_backtest.metrics.manager.metrics_manager.MetricsConfigParser", StubParser
        )
        monkeypatch.setattr(
            "tick_backtest.metrics.manager.metrics_manager.METRIC_CLASS_REGISTRY",
            {f"type_{i}": DummyMetric for i, _ in enumerate(metrics)},
        )

        return MetricsManager(Path("dummy.yaml"))

    return _factory


# ---------------------------------------------------------------------------


def test_update_invokes_metrics_and_returns_prefixed_snapshot(manager_factory, tick_factory):
    """Ensure .update() calls each metric and produces prefixed snapshot."""
    metric_a = DummyMetric(name="alpha", payloads=[{"z": 1}, {"z": 2}])
    metric_b = DummyMetric(name="beta", payloads=[{"vol": 0.5}])
    manager = manager_factory([metric_a, metric_b])

    tick = tick_factory()
    snapshot = manager.update(tick)

    # Get internal metric instances actually used by manager
    internal_a, internal_b = manager.metrics

    assert internal_a.updates == [tick]
    assert internal_b.updates == [tick]
    assert snapshot == {"alpha.z": 1, "beta.vol": 0.5}



def test_update_overwrites_previous_values(manager_factory, tick_factory):
    """Second update replaces previous snapshot values."""
    metric = DummyMetric(name="alpha", payloads=[{"z": 1}, {"z": 3}])
    manager = manager_factory([metric])

    first = manager.update(tick_factory())
    second = manager.update(tick_factory(bid=1.0002, ask=1.0003))

    assert first == {"alpha.z": 1}
    assert second == {"alpha.z": 3}


def test_current_returns_copy(manager_factory, tick_factory):
    """Ensure .current() returns a copy, not the same internal dict."""
    metric = DummyMetric(name="alpha", payloads=[{"z": 5}])
    manager = manager_factory([metric])
    manager.update(tick_factory())

    snapshot = manager.current()
    snapshot["alpha.z"] = 99

    fresh = manager.current()
    assert fresh["alpha.z"] == 5


def test_metrics_manager_with_real_config(tmp_path, tick_series_factory):
    """Instantiate MetricsManager with the actual parser and registry."""

    config_path = tmp_path / "metrics.yaml"
    config_path.write_text(
        textwrap.dedent(
            """
            schema_version: "1.0"
            metrics:
              - name: test_z
                type: zscore
                enabled: true
                params:
                  lookback_seconds: 60
              - name: tick_rate
                type: tick_rate
                enabled: true
                params:
                  window_seconds: 30
              - name: skip_me
                type: ewma
                enabled: false
                params:
                  tau_seconds: 10
                  price_field: mid
            """
        ).strip()
    )

    manager = MetricsManager(config_path)

    ticks = tick_series_factory(
        [
            (1.0000, 1.0002),
            (1.0005, 1.0007),
            (1.0010, 1.0012),
            (1.0012, 1.0014),
            (1.0013, 1.0015),
        ]
    )

    snapshot: Dict[str, Any] = {}
    for tick in ticks:
        snapshot = manager.update(tick)

    assert "test_z.z_score" in snapshot
    assert "test_z.rolling_residual" in snapshot
    assert "tick_rate.tick_rate_per_sec" in snapshot
    assert "tick_rate.tick_rate_per_min" in snapshot

    metric_names = {metric.name for metric in manager.metrics}
    assert "skip_me" not in metric_names
    assert metric_names == {"test_z", "tick_rate"}
