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

import hashlib
import json
import logging
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tick_backtest.backtest.backtest import Backtest
from tick_backtest.config_parsers.backtest.config_dataclass import BacktestConfigData
from tick_backtest.config_parsers.backtest.config_parser import BacktestConfigParser
from tick_backtest.config_parsers.metrics.config_dataclass import MetricConfigBase
from tick_backtest.config_parsers.metrics.config_parser import MetricsConfigParser
from tick_backtest.config_parsers.strategy.entry_configs import ThresholdReversionEntryParams
from tick_backtest.data_feed.data_feed import DataFeed, NoMoreTicks
from tick_backtest.data_feed.validation import TickValidator, ValidatingDataFeed
from tick_backtest.logging_utils import configure_logging, get_git_hash
from tick_backtest.metrics.indicators.threshold_reversion_metric import ThresholdReversionMetric
from tick_backtest.metrics.manager.metric_registry import METRIC_CLASS_REGISTRY
from tick_backtest.signals.signal_generator import SignalGenerator

logger = logging.getLogger(__name__)


@dataclass
class _MetricBinding:
    metric: Any
    aliases: list[str]
    fields: tuple[str, ...]


@dataclass
class _BatchItem:
    config_path: Path
    run_id: str
    config: BacktestConfigData
    run_root: Path
    output_dir: Path
    log_dir: Path
    backtest: Backtest


class BatchConfigError(ValueError):
    """Raised when config files cannot be safely run as one shared batch."""


class UnionMetricsManager:
    """Shared metric updater that publishes values under each config's aliases."""

    def __init__(self, configs: list[BacktestConfigData]) -> None:
        self._bindings: list[_MetricBinding] = []
        self._identity_to_binding: dict[str, _MetricBinding] = {}
        self._alias_to_identity: dict[str, str] = {}
        self._record_keys_by_index: dict[int, tuple[str, ...]] = {}
        self._threshold_prefix_by_index: dict[int, str] = {}

        for index, config in enumerate(configs):
            self._add_config_metrics(index, config)
        for index, config in enumerate(configs):
            self._add_strategy_synthetic_metrics(index, config)

    def update(self, tick: object) -> dict[str, float]:
        snapshot: dict[str, float] = {}
        for binding in self._bindings:
            binding.metric.update(tick)
            values = binding.metric.value()
            if not isinstance(values, dict):
                continue
            fields = tuple(str(key) for key in values)
            if fields != binding.fields:
                binding.fields = fields
            for alias in binding.aliases:
                for field in fields:
                    snapshot[f"{alias}.{field}"] = values.get(field)
        return snapshot

    def record_keys_for_config(self, index: int) -> tuple[str, ...]:
        return self._record_keys_by_index.get(index, ())

    def threshold_prefix_for_config(self, index: int) -> str | None:
        return self._threshold_prefix_by_index.get(index)

    def _add_config_metrics(self, index: int, config: BacktestConfigData) -> None:
        parser = MetricsConfigParser(config.metrics_config_path)
        metrics_config = parser.load_metrics_config()
        record_keys: list[str] = []
        for metric_cfg in metrics_config.metrics:
            if not getattr(metric_cfg, "enabled", True):
                continue
            binding = self._add_metric_config(metric_cfg)
            for field in binding.fields:
                record_keys.append(f"{metric_cfg.name}.{field}")
        self._record_keys_by_index[index] = tuple(record_keys)

    def _add_metric_config(self, metric_cfg: MetricConfigBase) -> _MetricBinding:
        identity = _metric_identity(metric_cfg.metric_type, metric_cfg.to_kwargs())
        existing = self._alias_to_identity.get(metric_cfg.name)
        if existing is not None and existing != identity:
            raise BatchConfigError(
                f"metric alias {metric_cfg.name!r} has conflicting definitions in batch"
            )
        self._alias_to_identity[metric_cfg.name] = identity

        binding = self._identity_to_binding.get(identity)
        if binding is not None:
            if metric_cfg.name not in binding.aliases:
                binding.aliases.append(metric_cfg.name)
            return binding

        metric_cls = METRIC_CLASS_REGISTRY.get(metric_cfg.metric_type)
        if metric_cls is None:
            raise BatchConfigError(f"unrecognized metric type {metric_cfg.metric_type!r}")
        metric = metric_cls(name=metric_cfg.name, **metric_cfg.to_kwargs())
        fields = tuple(str(key) for key in metric.value())
        binding = _MetricBinding(metric=metric, aliases=[metric_cfg.name], fields=fields)
        self._bindings.append(binding)
        self._identity_to_binding[identity] = binding
        return binding

    def _add_strategy_synthetic_metrics(self, index: int, config: BacktestConfigData) -> None:
        strategy = config.strategy_config
        if strategy is None or strategy.entry.engine != "threshold_reversion":
            return
        params = strategy.entry.params
        if not isinstance(params, ThresholdReversionEntryParams):
            raise BatchConfigError("threshold_reversion entry has unexpected parameter type")
        kwargs = {
            "lookback_seconds": params.lookback_seconds,
            "threshold_pips": params.threshold_pips,
            "pip_size": config.pip_size,
            "tp_pips": params.tp_pips,
            "sl_pips": params.sl_pips,
            "min_recency_seconds": params.min_recency_seconds,
            "trade_timeout_seconds": params.trade_timeout_seconds,
        }
        identity = _metric_identity("threshold_reversion", kwargs)
        alias = f"__entry_threshold_{hashlib.sha1(identity.encode('utf-8')).hexdigest()[:12]}"
        binding = self._identity_to_binding.get(identity)
        if binding is None:
            metric = ThresholdReversionMetric(name=alias, **kwargs)
            fields = tuple(str(key) for key in metric.value())
            binding = _MetricBinding(metric=metric, aliases=[alias], fields=fields)
            self._bindings.append(binding)
            self._identity_to_binding[identity] = binding
        elif alias not in binding.aliases:
            binding.aliases.append(alias)
        self._threshold_prefix_by_index[index] = alias


def run_backtest_batch(
    config_paths: list[Path | str],
    run_ids: list[str],
    *,
    output_root: Path | str,
    batch_id: str,
    log_level: str | int = "WARNING",
    run_roots: list[Path | str] | None = None,
) -> dict[str, object]:
    """Run compatible summary-mode configs over one shared tick stream."""
    if len(config_paths) != len(run_ids):
        raise ValueError("config_paths and run_ids must have the same length")
    if run_roots is not None and len(run_roots) != len(run_ids):
        raise ValueError("run_roots and run_ids must have the same length")
    if not config_paths:
        raise ValueError("config_paths must contain at least one config")

    batch_output_root = Path(output_root).expanduser()
    batch_output_root.mkdir(parents=True, exist_ok=True)
    log_dir = batch_output_root / f"_batch_{batch_id}" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    configure_logging(run_id=batch_id, log_dir=log_dir, level=log_level)

    parser = BacktestConfigParser()
    resolved_paths = [Path(path).expanduser().resolve() for path in config_paths]
    configs = [parser.parse_config(path) for path in resolved_paths]
    _validate_compatible_batch(configs)

    union_metrics = UnionMetricsManager(configs)
    items = _build_batch_items(
        configs=configs,
        config_paths=resolved_paths,
        run_ids=run_ids,
        output_root=batch_output_root,
        union_metrics=union_metrics,
        run_roots=[Path(path).expanduser() for path in run_roots] if run_roots is not None else None,
    )
    first = configs[0]
    pair = first.pairs[0]

    raw_feed = DataFeed(
        base_path=first.data_base_path,
        pair=pair,
        year_start=first.year_start,
        year_end=first.year_end,
        month_start=first.month_start,
        month_end=first.month_end,
    )
    validator = TickValidator(pair=pair)
    data_feed = ValidatingDataFeed(raw_feed, validator) if first.validate_ticks else raw_feed

    try:
        initial_tick = data_feed.tick()
    except NoMoreTicks:
        for item in items:
            item.backtest._finish()
        _write_item_manifests(items, batch_id=batch_id, validator=validator)
        return _batch_result(batch_id, items)

    start_ts = Backtest._to_datetime(initial_tick.timestamp)
    last_ts = start_ts
    metrics = union_metrics.update(initial_tick)
    for item in items:
        item.backtest.handle_warmup_tick(initial_tick, metrics)

    if first.warmup_seconds > 0:
        try:
            while (last_ts - start_ts).total_seconds() < first.warmup_seconds:
                tick = data_feed.tick()
                last_ts = Backtest._to_datetime(tick.timestamp)
                metrics = union_metrics.update(tick)
                for item in items:
                    item.backtest.handle_warmup_tick(tick, metrics)
        except NoMoreTicks:
            logger.warning("data feed exhausted during batch warmup phase")

    try:
        while True:
            tick = data_feed.tick()
            metrics = union_metrics.update(tick)
            for item in items:
                item.backtest.handle_tick_with_metrics(tick, metrics)
    except NoMoreTicks:
        pass

    for item in items:
        item.backtest._finish()

    _write_item_manifests(items, batch_id=batch_id, validator=validator)
    return _batch_result(batch_id, items)


def _build_batch_items(
    *,
    configs: list[BacktestConfigData],
    config_paths: list[Path],
    run_ids: list[str],
    output_root: Path,
    union_metrics: UnionMetricsManager,
    run_roots: list[Path] | None = None,
) -> list[_BatchItem]:
    items: list[_BatchItem] = []
    for index, (config, config_path, run_id) in enumerate(zip(configs, config_paths, run_ids, strict=True)):
        run_root = run_roots[index] if run_roots is not None else output_root / run_id
        output_dir = run_root / "output"
        pair = config.pairs[0]
        pair_output_dir = output_dir / pair
        pair_output_dir.mkdir(parents=True, exist_ok=True)
        log_dir = output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        signal_generator = SignalGenerator(
            strategy_config=config.strategy_config,
            pip_size=config.pip_size,
        )
        threshold_prefix = union_metrics.threshold_prefix_for_config(index)
        if threshold_prefix is not None and hasattr(signal_generator.entry_engine, "use_shared_metric"):
            signal_generator.entry_engine.use_shared_metric(threshold_prefix)

        backtest = Backtest(
            data_feed=_BatchFeedRef(pair),
            signal_generator=signal_generator,
            metrics_manager=_NoMetricsManager(),
            output_base_path=pair_output_dir / "trades.parquet",
            pip_size=config.pip_size,
            trade_output_mode="summary",
            metric_record_keys=union_metrics.record_keys_for_config(index),
        )
        _snapshot_configs(run_root / "configs", config_path, config)
        items.append(
            _BatchItem(
                config_path=config_path,
                run_id=run_id,
                config=config,
                run_root=run_root,
                output_dir=output_dir,
                log_dir=log_dir,
                backtest=backtest,
            )
        )
    return items


class _BatchFeedRef:
    def __init__(self, pair: str) -> None:
        self.pair = pair


class _NoMetricsManager:
    def update(self, tick: object) -> dict[str, float]:
        raise RuntimeError("batch backtests receive metrics from UnionMetricsManager")


def _validate_compatible_batch(configs: list[BacktestConfigData]) -> None:
    first = configs[0]
    if len(first.pairs) != 1:
        raise BatchConfigError("batched configs must contain exactly one pair")
    if first.trade_output_mode != "summary":
        raise BatchConfigError("batched configs must use trade_output_mode: summary")

    keys = (
        "pairs",
        "year_start",
        "year_end",
        "month_start",
        "month_end",
        "pip_size",
        "warmup_seconds",
        "data_base_path",
        "validate_ticks",
        "trade_output_mode",
    )
    for config in configs[1:]:
        if len(config.pairs) != 1:
            raise BatchConfigError("batched configs must contain exactly one pair")
        for key in keys:
            if getattr(config, key) != getattr(first, key):
                raise BatchConfigError(f"batched configs differ on {key}")


def _snapshot_configs(dest_dir: Path, backtest_path: Path, config: BacktestConfigData) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for label, path in (
        ("backtest", backtest_path),
        ("metrics", config.metrics_config_path),
        ("strategy", config.strategy_config_path),
    ):
        target = dest_dir / f"{label}.yaml"
        try:
            shutil.copy2(path, target)
        except Exception:
            logger.warning("failed to snapshot batch config", extra={"path": str(path)})


def _write_item_manifests(
    items: list[_BatchItem],
    *,
    batch_id: str,
    validator: TickValidator,
) -> None:
    code_ref = get_git_hash()
    now = datetime.now(UTC).isoformat()
    for item in items:
        manifest = {
            "run_id": item.run_id,
            "batch_id": batch_id,
            "timestamp_utc": now,
            "code_ref": code_ref,
            "cli": {"config": str(item.config_path.resolve())},
            "output_root": str(item.output_dir.resolve()),
            "log_path": "",
            "status": "completed",
            "outputs": [],
            "summary_outputs": _summary_outputs(item.output_dir),
            "pair_failures": {},
            "tick_validation": {
                item.config.pairs[0]: validator.stats.as_dict(),
            },
            "strategy_registry": asdict(item.config.strategy_config) if item.config.strategy_config else None,
        }
        item.run_root.mkdir(parents=True, exist_ok=True)
        (item.run_root / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _summary_outputs(output_dir: Path) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for child in sorted(output_dir.iterdir()) if output_dir.exists() else []:
        if not child.is_dir() or child.name == "logs":
            continue
        summary_dir = child / "summary"
        pair_metrics = summary_dir / "pair_metrics.parquet"
        metric_bins = summary_dir / "metric_bins.parquet"
        if pair_metrics.exists() or metric_bins.exists():
            outputs.append(
                {
                    "pair": child.name,
                    "pair_metrics_path": str(pair_metrics.resolve()) if pair_metrics.exists() else "",
                    "metric_bins_path": str(metric_bins.resolve()) if metric_bins.exists() else "",
                }
            )
    return outputs


def _batch_result(batch_id: str, items: list[_BatchItem]) -> dict[str, object]:
    return {
        "batch_id": batch_id,
        "runs": [
            {
                "run_id": item.run_id,
                "run_root": item.run_root,
                "output_dir": item.output_dir,
                "manifest_path": item.run_root / "manifest.json",
                "status": "completed",
            }
            for item in items
        ],
    }


def _metric_identity(metric_type: str, params: dict[str, object]) -> str:
    return json.dumps(
        {"type": metric_type, "params": params},
        sort_keys=True,
        default=str,
    )
