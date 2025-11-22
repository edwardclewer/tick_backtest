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

import json
import logging
import subprocess
import sys
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional


_CONTEXT: ContextVar[Dict[str, Any]] = ContextVar(
    "tick_backtest_logging_context",
    default={"run_id": None, "pair": None},
)


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _serialize_dataclass(value)
    if isinstance(value, set):
        return sorted(_json_default(v) for v in value)
    return value


def _serialize_dataclass(obj: Any) -> Any:
    return _serialize(asdict(obj))


def _serialize(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if is_dataclass(obj):
        return _serialize_dataclass(obj)
    return obj


class StructuredFormatter(logging.Formatter):
    """JSON formatter that injects run context into each record."""

    RESERVED = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
    }

    def format(self, record: logging.LogRecord) -> str:
        context = dict(_CONTEXT.get())
        run_id = getattr(record, "run_id", context.get("run_id"))
        pair = getattr(record, "pair", context.get("pair"))

        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": run_id,
            "pair": pair,
        }

        extra: Dict[str, Any] = {}
        for key, value in record.__dict__.items():
            if key in self.RESERVED or key in ("run_id", "pair"):
                continue
            extra[key] = _serialize(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if extra:
            payload["extra"] = extra

        return json.dumps(payload, default=_json_default)


def configure_logging(
    *,
    run_id: str,
    log_dir: Optional[Path] = None,
    level: int | str = logging.INFO,
) -> None:
    """Set up root logging with structured JSON output."""

    root = logging.getLogger()
    root.setLevel(level if isinstance(level, int) else logging.getLevelName(level))

    # Avoid duplicate handlers when re-configuring
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    formatter = StructuredFormatter()

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(root.level)
    root.addHandler(stream_handler)

    if log_dir is not None:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / f"{run_id}.log")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(root.level)
        root.addHandler(file_handler)

    set_run_context(run_id=run_id)


def generate_run_id() -> str:
    """Return a short unique identifier for the current run."""
    return datetime.utcnow().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]


def set_run_context(**updates: Any) -> ContextVarToken:
    """Merge updates into the current logging context."""
    ctx = dict(_CONTEXT.get())
    ctx.update(updates)
    return ContextVarToken(token=_CONTEXT.set(ctx))


def reset_run_context(token: "ContextVarToken") -> None:
    """Restore the logging context using a previously captured token."""
    _CONTEXT.reset(token.value)


class ContextVarToken:
    """Wrapper to avoid exposing contextvars.Token outside this module."""

    __slots__ = ("value",)

    def __init__(self, token):
        self.value = token


@contextmanager
def run_context(**updates: Any):
    """Context manager that temporarily overrides logging context."""
    token = set_run_context(**updates)
    try:
        yield
    finally:
        reset_run_context(token)


def get_git_hash() -> Optional[str]:
    """Return the current git commit hash if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except (OSError, ValueError):
        return None


def log_run_metadata(
    logger: logging.Logger,
    *,
    backtest_config: Any,
    metrics_config_path: Path,
    strategy_config_path: Path,
    git_hash: Optional[str],
) -> None:
    """Emit configuration and environment metadata for reproducibility."""
    metadata: Dict[str, Any] = {
        "git_hash": git_hash,
        "backtest_config": _serialize(backtest_config),
        "metrics_config_path": str(metrics_config_path),
        "strategy_config_path": str(strategy_config_path),
    }

    try:
        metadata["metrics_config_yaml"] = metrics_config_path.read_text(encoding="utf-8")
    except OSError:
        metadata["metrics_config_yaml"] = None

    try:
        metadata["strategy_config_yaml"] = strategy_config_path.read_text(encoding="utf-8")
    except OSError:
        metadata["strategy_config_yaml"] = None

    logger.info("run metadata snapshot", extra=metadata)
