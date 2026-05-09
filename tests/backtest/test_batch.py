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

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
import yaml

from tests.helpers.parquet import write_tick_parquet
from tick_backtest.backtest.batch import BatchConfigError, UnionMetricsManager
from tick_backtest.backtest.workflow import run_backtest_batch
from tick_backtest.config_parsers.backtest.config_parser import BacktestConfigParser
from tick_backtest.signals.signal_generator import SignalGenerator


def _write_ticks(data_root: Path) -> None:
    pair_dir = data_root / "EURUSD"
    pair_dir.mkdir(parents=True, exist_ok=True)
    base = datetime(2015, 1, 1, tzinfo=UTC)
    rows = []
    mids = [1.1000, 1.1008, 1.1014, 1.1007, 1.0998, 1.1003]
    for idx, mid in enumerate(mids):
        rows.append(
            {
                "timestamp": base + timedelta(seconds=idx),
                "bid": mid - 0.0001,
                "ask": mid + 0.0001,
            }
        )
    write_tick_parquet(pair_dir / "EURUSD_2015-01.parquet", rows)


def _write_config(
    tmp_path: Path,
    *,
    name: str,
    metrics: list[dict[str, object]],
    strategy: dict[str, object],
    data_root: Path | None = None,
    start: str = "2015-01",
    end: str = "2015-01",
) -> Path:
    if data_root is None:
        data_root = tmp_path / "data"
        _write_ticks(data_root)
    config_dir = tmp_path / name
    config_dir.mkdir()
    metrics_path = config_dir / "metrics.yaml"
    strategy_path = config_dir / "strategy.yaml"
    backtest_path = config_dir / "backtest.yaml"
    metrics_path.write_text(
        yaml.safe_dump({"schema_version": "1.0", "metrics": metrics}),
        encoding="utf-8",
    )
    strategy_path.write_text(
        yaml.safe_dump({"schema_version": "1.0", "strategy": strategy}),
        encoding="utf-8",
    )
    backtest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "pairs": ["EURUSD"],
                "start": start,
                "end": end,
                "pip_size": 0.0001,
                "warmup_seconds": 0,
                "validate_ticks": False,
                "trade_output_mode": "summary",
                "data_base_path": str(data_root),
                "output_base_path": str(tmp_path / "output"),
                "metrics_config_path": str(metrics_path),
                "strategy_config_path": str(strategy_path),
            }
        ),
        encoding="utf-8",
    )
    return backtest_path


def _stub_strategy() -> dict[str, object]:
    return {
        "name": "stub_strategy",
        "entry": {"name": "entry", "engine": "stub", "params": {}, "predicates": []},
        "exit": {"name": "exit", "predicates": []},
    }


def _threshold_strategy() -> dict[str, object]:
    return {
        "name": "threshold_strategy",
        "entry": {
            "name": "threshold_entry",
            "engine": "threshold_reversion",
            "params": {
                "lookback_seconds": 4,
                "threshold_pips": 5,
                "tp_pips": 5,
                "sl_pips": 8,
                "min_recency_seconds": 0,
                "trade_timeout_seconds": 5,
            },
            "predicates": [],
        },
        "exit": {"name": "exit", "predicates": []},
    }


def _ewma_crossover_strategy(
    *,
    name: str,
    spread_metric: str,
    fast: int,
    slow: int,
) -> dict[str, object]:
    return {
        "name": name,
        "entry": {
            "name": "cross",
            "engine": "ewma_crossover",
            "params": {
                "fast_metric": f"ewma_{fast}.ewma",
                "slow_metric": f"ewma_{slow}.ewma",
                "long_on_cross": True,
                "short_on_cross": True,
                "tp_pips": 1,
                "sl_pips": 1,
                "trade_timeout_seconds": 5,
            },
            "predicates": [
                {
                    "metric": f"{spread_metric}.spread_pips",
                    "operator": "<",
                    "value": 2.0,
                }
            ],
        },
        "exit": {"name": "exit", "predicates": []},
    }


def _ewma_metrics(*, spread_metric: str, fast: int, slow: int) -> list[dict[str, object]]:
    return [
        {
            "name": spread_metric,
            "type": "spread",
            "params": {"pip_size": 0.0001, "window_seconds": 60},
        },
        {
            "name": f"ewma_{fast}",
            "type": "ewma",
            "params": {"tau_seconds": fast, "price_field": "mid"},
        },
        {
            "name": f"ewma_{slow}",
            "type": "ewma",
            "params": {"tau_seconds": slow, "price_field": "mid"},
        },
    ]


def test_union_metrics_deduplicates_equivalent_metric_definitions(tmp_path: Path, tick_factory) -> None:
    metrics_a = [{"name": "spread_a", "type": "spread", "params": {"pip_size": 0.0001, "window_seconds": 60}}]
    metrics_b = [{"name": "spread_b", "type": "spread", "params": {"pip_size": 0.0001, "window_seconds": 60}}]
    parser = BacktestConfigParser()
    cfg_a = parser.parse_config(_write_config(tmp_path, name="a", metrics=metrics_a, strategy=_stub_strategy()))
    cfg_b = parser.parse_config(_write_config(tmp_path, name="b", metrics=metrics_b, strategy=_stub_strategy()))

    manager = UnionMetricsManager([cfg_a, cfg_b])
    snapshot = manager.update(tick_factory(bid=1.0, ask=1.0002))

    assert len(manager._bindings) == 1
    assert snapshot["spread_a.spread_pips"] == pytest.approx(2.0)
    assert snapshot["spread_b.spread_pips"] == pytest.approx(2.0)


def test_union_metrics_rejects_conflicting_same_alias(tmp_path: Path) -> None:
    metrics_a = [{"name": "spread", "type": "spread", "params": {"pip_size": 0.0001, "window_seconds": 60}}]
    metrics_b = [{"name": "spread", "type": "spread", "params": {"pip_size": 0.0001, "window_seconds": 30}}]
    parser = BacktestConfigParser()
    cfg_a = parser.parse_config(_write_config(tmp_path, name="a", metrics=metrics_a, strategy=_stub_strategy()))
    cfg_b = parser.parse_config(_write_config(tmp_path, name="b", metrics=metrics_b, strategy=_stub_strategy()))

    with pytest.raises(BatchConfigError, match="conflicting definitions"):
        UnionMetricsManager([cfg_a, cfg_b])


def test_threshold_synthetic_metric_matches_private_entry_engine(tmp_path: Path, tick_factory) -> None:
    parser = BacktestConfigParser()
    cfg = parser.parse_config(_write_config(tmp_path, name="threshold", metrics=[], strategy=_threshold_strategy()))
    manager = UnionMetricsManager([cfg])
    shared = SignalGenerator(strategy_config=cfg.strategy_config, pip_size=cfg.pip_size)
    prefix = manager.threshold_prefix_for_config(0)
    assert prefix is not None
    shared.entry_engine.use_shared_metric(prefix)
    private = SignalGenerator(strategy_config=cfg.strategy_config, pip_size=cfg.pip_size)

    base = datetime(2015, 1, 1, tzinfo=UTC)
    ticks = [
        tick_factory(bid=1.0999, ask=1.1001, timestamp=base),
        tick_factory(bid=1.1007, ask=1.1009, timestamp=base + timedelta(seconds=1)),
        tick_factory(bid=1.1013, ask=1.1015, timestamp=base + timedelta(seconds=2)),
        tick_factory(bid=1.1006, ask=1.1008, timestamp=base + timedelta(seconds=3)),
    ]

    for tick in ticks:
        shared_signal = shared.update(manager.update(tick), tick)
        private_signal = private.update({}, tick)
        assert shared_signal.should_open == private_signal.should_open
        assert shared_signal.direction == private_signal.direction
        assert shared_signal.tp == private_signal.tp
        assert shared_signal.sl == private_signal.sl


def test_run_backtest_batch_writes_per_run_summaries_and_manifests(tmp_path: Path) -> None:
    config_a = _write_config(tmp_path, name="a", metrics=[], strategy=_stub_strategy())
    config_b = _write_config(tmp_path, name="b", metrics=[], strategy=_stub_strategy())
    output_root = tmp_path / "runs"
    result = run_backtest_batch(
        [config_a, config_b],
        ["run-a", "run-b"],
        output_root=output_root,
        batch_id="batch-1",
        log_level="ERROR",
    )

    assert result["batch_id"] == "batch-1"
    for run_id in ["run-a", "run-b"]:
        run_root = output_root / run_id
        assert (run_root / "manifest.json").exists()
        summary_dir = run_root / "output" / "EURUSD" / "summary"
        assert (summary_dir / "pair_metrics.parquet").exists()
        assert (summary_dir / "metric_bins.parquet").exists()
        pair_metrics = pd.read_parquet(summary_dir / "pair_metrics.parquet")
        assert int(pair_metrics.iloc[0]["total_trades"]) == 0


def test_batch_on_brownian_fixture_separates_outputs_and_metric_aliases(tmp_path: Path) -> None:
    data_root = Path(__file__).resolve().parents[1] / "test_data"
    config_a = _write_config(
        tmp_path,
        name="brownian-a",
        metrics=_ewma_metrics(spread_metric="spread_a", fast=1, slow=10),
        strategy=_ewma_crossover_strategy(
            name="brownian_a",
            spread_metric="spread_a",
            fast=1,
            slow=10,
        ),
        data_root=data_root,
        start="2000-01",
        end="2000-01",
    )
    config_b = _write_config(
        tmp_path,
        name="brownian-b",
        metrics=_ewma_metrics(spread_metric="spread_b", fast=2, slow=20),
        strategy=_ewma_crossover_strategy(
            name="brownian_b",
            spread_metric="spread_b",
            fast=2,
            slow=20,
        ),
        data_root=data_root,
        start="2000-01",
        end="2000-01",
    )

    run_backtest_batch(
        [config_a, config_b],
        ["brownian-a", "brownian-b"],
        output_root=tmp_path / "runs",
        batch_id="brownian-batch",
        log_level="ERROR",
    )

    summaries: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for run_id in ["brownian-a", "brownian-b"]:
        run_root = tmp_path / "runs" / run_id
        summary_dir = run_root / "output" / "EURUSD" / "summary"
        assert (run_root / "manifest.json").exists()
        assert not (run_root / "output" / "EURUSD" / "trades.parquet").exists()
        pair_metrics = pd.read_parquet(summary_dir / "pair_metrics.parquet")
        metric_bins = pd.read_parquet(summary_dir / "metric_bins.parquet")
        assert int(pair_metrics.iloc[0]["total_trades"]) > 100
        assert not metric_bins.empty
        summaries[run_id] = (pair_metrics, metric_bins)

    metrics_a = set(summaries["brownian-a"][1]["metric"])
    metrics_b = set(summaries["brownian-b"][1]["metric"])
    assert "spread_a.spread_pips" in metrics_a
    assert "spread_b.spread_pips" not in metrics_a
    assert "spread_b.spread_pips" in metrics_b
    assert "spread_a.spread_pips" not in metrics_b
    assert summaries["brownian-a"][0].iloc[0]["total_trades"] != summaries["brownian-b"][0].iloc[0]["total_trades"]
