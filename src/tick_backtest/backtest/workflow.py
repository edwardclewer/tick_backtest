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

import cProfile
import hashlib
import io
import json
import logging
import pstats
import shutil
import subprocess
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from tick_backtest.backtest.backtest_coordinator import BacktestCoordinator
from tick_backtest.config_parsers.backtest.config_parser import BacktestConfigParser
from tick_backtest.config_parsers.metrics.config_parser import MetricsConfigParser
from tick_backtest.data_feed.data_feed import get_data_months
from tick_backtest.exceptions import ConfigError
from tick_backtest.logging_utils import configure_logging, generate_run_id, get_git_hash

logger = logging.getLogger(__name__)

__all__ = [
    "run_backtest",
    "load_config",
]


def load_config(config_path: Path | str):
    """Parse a backtest configuration file."""
    parser = BacktestConfigParser()
    return parser.parse_config(Path(config_path))


def setup_logging(run_id: str, log_dir: Path | None, level: str | int):
    configure_logging(run_id=run_id, log_dir=log_dir, level=level)
    return logging.getLogger(__name__)


def _snapshot_config(source: Path, dest_dir: Path) -> Dict[str, object]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    dest_path = dest_dir / source.name
    shutil.copy2(source, dest_path)
    schema_version: Optional[str] = None
    try:
        parsed = yaml.safe_load(text)
        if isinstance(parsed, dict):
            raw_version = parsed.get("schema_version")
            if raw_version is not None:
                schema_version = str(raw_version)
    except yaml.YAMLError:
        schema_version = None
    return {
        "source_path": str(source.resolve()),
        "copied_path": str(dest_path.resolve()),
        "sha256": digest,
        "yaml": text,
        "schema_version": schema_version,
    }


def _summarize_metrics_config(metrics_config_path: Path) -> List[Dict[str, object]]:
    try:
        parser = MetricsConfigParser(metrics_config_path)
        data = parser.load_metrics_config()
    except Exception:
        return []

    summary: List[Dict[str, object]] = []
    for cfg in data.metrics:
        summary.append(
            {
                "name": cfg.name,
                "metric_type": cfg.metric_type,
                "enabled": getattr(cfg, "enabled", True),
                "params": cfg.to_kwargs(),
            }
        )
    return summary


def _count_parquet_rows(path: Path) -> Optional[int]:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        return None

    try:
        parquet_file = pq.ParquetFile(path)
        metadata = parquet_file.metadata
        return metadata.num_rows if metadata is not None else None
    except Exception:
        return None


def _collect_trade_outputs(output_root: Path) -> List[Dict[str, object]]:
    outputs: List[Dict[str, object]] = []
    if not output_root.exists():
        return outputs

    for child in sorted(output_root.iterdir()):
        if not child.is_dir() or child.name == "logs":
            continue
        trades_path = child / "trades.parquet"
        if not trades_path.exists():
            continue
        outputs.append(
            {
                "pair": child.name,
                "path": str(trades_path.resolve()),
                "rows": _count_parquet_rows(trades_path),
            }
        )
    return outputs


def _write_environment_snapshot(run_root: Path) -> Path:
    env_path = run_root / "environment.txt"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error_output = result.stderr.strip() if result.stderr else f"exit code {result.returncode}"
        raise RuntimeError(f"pip freeze failed: {error_output}")
    env_path.write_text(result.stdout or "", encoding="utf-8")
    return env_path


def _write_manifest(run_root: Path, manifest: Dict[str, object]) -> Path:
    manifest_path = run_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> Optional[str]:
    hasher = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
    except Exception:
        return None
    return hasher.hexdigest()


def _collect_input_shards(config) -> List[Dict[str, object]]:
    shards: List[Dict[str, object]] = []
    months = get_data_months(
        config.year_start,
        config.year_end,
        config.month_start,
        config.month_end,
    )

    try:
        import pyarrow.parquet as pq  # type: ignore
    except Exception:
        pq = None  # type: ignore

    for pair in config.pairs:
        for year, month in months:
            file_path = config.data_base_path / pair / f"{pair}_{year}-{month:02d}.parquet"
            info: Dict[str, object] = {
                "pair": pair,
                "year_month": f"{year}-{month:02d}",
                "path": str(file_path.resolve()),
            }

            errors: List[str] = []
            row_count: Optional[int] = None

            if file_path.exists() and pq is not None:
                try:
                    parquet_file = pq.ParquetFile(file_path)
                    metadata = parquet_file.metadata
                    if metadata is not None:
                        row_count = metadata.num_rows
                except Exception as exc:
                    errors.append(f"metadata_error: {exc}")
            else:
                if not file_path.exists():
                    errors.append("missing_file")
                elif pq is None:
                    errors.append("pyarrow_unavailable")

            info["rows"] = row_count

            if file_path.exists():
                file_hash = _hash_file(file_path)
                if file_hash is None:
                    errors.append("hash_error")
                info["sha256"] = file_hash
            else:
                info["sha256"] = None

            if errors:
                info["errors"] = errors

            shards.append(info)

    return shards


def run_backtest(
    config_path: Path | str,
    *,
    profile: bool = False,
    log_level: str | int = "INFO",
    run_id: str | None = None,
    output_root: Path | str | None = None,
) -> Dict[str, object]:
    """
    Execute a backtest using the provided configuration path.

    Returns metadata about the run, including the manifest contents.
    """
    run_identifier = run_id or generate_run_id()
    initial_logger = setup_logging(run_identifier, None, log_level)

    try:
        config = load_config(config_path)
    except ConfigError:
        initial_logger.exception(
            "failed to load backtest configuration",
            extra={"config_path": str(Path(config_path).resolve())},
        )
        raise

    base_output_root = Path(output_root).expanduser() if output_root else config.output_base_path
    run_root = base_output_root / run_identifier
    run_root.mkdir(parents=True, exist_ok=True)
    run_output_dir = run_root / "output"
    run_output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = run_output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    configs_dir = run_root / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging(run_identifier, log_dir, log_level)
    logger.info(
        "run metadata snapshot",
        extra={
            "git_hash": get_git_hash(),
            "config_paths": {
                "backtest": str(Path(config_path).resolve()),
                "metrics": str(config.metrics_config_path.resolve()),
                "strategy": str(config.strategy_config_path.resolve()),
            },
        },
    )

    manifest: Dict[str, object] = {
        "run_id": run_identifier,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "code_ref": get_git_hash(),
        "cli": {"config": str(Path(config_path).resolve())},
        "output_root": str(run_output_dir.resolve()),
        "log_path": str((log_dir / f"{run_identifier}.log").resolve()),
        "status": "pending",
    }

    config_snapshots: Dict[str, Dict[str, object]] = {}
    for key, path in (
        ("backtest", Path(config_path)),
        ("metrics", config.metrics_config_path),
        ("strategy", config.strategy_config_path),
    ):
        try:
            config_snapshots[key] = _snapshot_config(path, configs_dir)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("failed to snapshot config", extra={"config_key": key, "error": str(exc)})
    manifest["configs"] = config_snapshots
    metrics_schema_version = config_snapshots.get("metrics", {}).get("schema_version")
    strategy_schema_version = (
        config.strategy_config.schema_version
        if config.strategy_config
        else config_snapshots.get("strategy", {}).get("schema_version")
    )
    manifest["schema_versions"] = {
        "backtest": getattr(config, "schema_version", None),
        "metrics": metrics_schema_version,
        "strategy": strategy_schema_version,
    }
    logger.info("config schema versions", extra={"schema_versions": manifest["schema_versions"]})
    manifest["metrics_registry"] = _summarize_metrics_config(config.metrics_config_path)
    manifest["strategy_registry"] = asdict(config.strategy_config) if config.strategy_config else None

    config_for_run = replace(config, output_base_path=run_output_dir)
    coordinator = BacktestCoordinator(config_for_run, run_id=run_identifier)

    input_shards_cache: Optional[List[Dict[str, object]]] = None
    input_shards_logged = False
    pair_failures: Dict[str, str] = {}
    tick_validation_summary: Dict[str, Dict[str, object]] = {}

    def _finalize_run(status: str) -> None:
        nonlocal input_shards_cache, input_shards_logged
        manifest["status"] = status
        manifest["outputs"] = _collect_trade_outputs(run_output_dir)
        if input_shards_cache is None:
            input_shards_cache = _collect_input_shards(config)
        manifest["input_shards"] = input_shards_cache
        manifest["pair_failures"] = pair_failures
        manifest["tick_validation"] = tick_validation_summary
        try:
            _write_manifest(run_root, manifest)
            _write_environment_snapshot(run_root)
        except Exception:
            logger.exception("failed to persist run artefacts")
        if not input_shards_logged and input_shards_cache is not None:
            logger.info("input shard summary", extra={"input_shards": input_shards_cache})
            input_shards_logged = True
        if tick_validation_summary:
            logger.info(
                "tick validation summary",
                extra={"tick_validation": tick_validation_summary, "pair_failures": pair_failures},
            )

    if profile:
        profile_path = run_root / "profile_stats.prof"
        logger.info("profiling enabled", extra={"profile_path": str(profile_path)})
        with cProfile.Profile() as profiler:
            try:
                coordinator.run_backtests()
            except Exception:
                pair_failures = dict(coordinator.pair_failures)
                tick_validation_summary = {
                    pair: validator.stats.as_dict()
                    for pair, validator in coordinator.tick_validation_stats.items()
                }
                _finalize_run("failed")
                raise
        profiler.dump_stats(profile_path)
        stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.strip_dirs().sort_stats("cumulative").print_stats(30)
        logger.info("profiling summary", extra={"profile_report": stream.getvalue()})
        pair_failures = dict(coordinator.pair_failures)
        tick_validation_summary = {
            pair: validator.stats.as_dict()
            for pair, validator in coordinator.tick_validation_stats.items()
        }
        _finalize_run("completed")
    else:
        try:
            coordinator.run_backtests()
        except Exception:
            pair_failures = dict(coordinator.pair_failures)
            tick_validation_summary = {
                pair: validator.stats.as_dict()
                for pair, validator in coordinator.tick_validation_stats.items()
            }
            _finalize_run("failed")
            raise
        pair_failures = dict(coordinator.pair_failures)
        tick_validation_summary = {
            pair: validator.stats.as_dict()
            for pair, validator in coordinator.tick_validation_stats.items()
        }
        _finalize_run("completed")

    logger.info("run complete")
    manifest_path = run_root / "manifest.json"
    result: Dict[str, object] = {
        "run_id": run_identifier,
        "run_root": run_root,
        "output_dir": run_output_dir,
        "log_dir": log_dir,
        "manifest": manifest,
        "manifest_path": manifest_path,
    }
    return result
