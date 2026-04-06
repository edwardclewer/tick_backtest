<!--
Copyright 2025 Edward Clewer

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Developer Internals

This section captures implementation details that are useful when extending or maintaining the Tick Backtest Research Stack. It is aimed at contributors and advanced users; casual readers can stick to the user-facing guides.

## Module Overview

| Area | Key Modules | Notes |
| --- | --- | --- |
| Configuration | `tick_backtest/config_parsers/*` | YAML validation, schema versioning, dataclasses. See [Config Overview](../configs.md). |
| Data Feed | `tick_backtest/data_feed/*` | Cython extension `_data_feed`, Python fallback, validation wrapper. Tied to [Architecture](../architecture.md#high-level-flow). |
| Backtest Execution | `tick_backtest/backtest/*` | Workflow orchestration, coordinator, main loop. Entry points documented in [Quickstart](../quickstart.md#run-the-backtest). |
| Metrics | `tick_backtest/metrics/*` | Registries, primitives, compiled manager. Reference parameters in [Metrics Reference](../configs/metrics.md). |
| Signals | `tick_backtest/signals/*` | Entry engines, predicates, signal data model. Pair with [Strategy Reference](../configs/strategy.md). |
| Analysis | `tick_backtest/analysis/*` | Markdown/plot generation, stratification helpers. Outputs described in [Analysis & Reporting](../analysis.md). |
| Logging | `tick_backtest/logging_utils.py` | Structured logging setup and run context feeding manifests/logs. |

## Execution Path

1. `run_backtest` loads the backtest config and snapshots YAML files.
2. `BacktestCoordinator` iterates pairs, building a `DataFeed`, `TickValidator`, `MetricsManager`, and `SignalGenerator` for each.
3. The `Backtest` loop consumes ticks, updates metrics, and pushes trade lifecycle events.
4. Once the feed is exhausted, trades persist to Parquet. Post-run analysis remains a separate package workflow (`report` / `analyze`) even though the repository helper script `scripts/run_backtest.py` chains extra analysis for internal use.

`threshold_reversion` is the one built-in exception to the normal metric ownership model. Its entry engine maintains a private `ThresholdReversionMetric` instance inside `signals/entries/threshold_reversion.py` rather than registering that indicator through `MetricsManager`. Keep that distinction explicit when adding new engines so config-time metric validation does not treat strategy-private indicator state as a required metrics-config dependency.

## Extension Points

- **Metrics** - Implement new classes under `metrics/dataclasses` and runtime behaviour under `metrics/primitives`. Register in `metrics/config_registry.py`.
- **Signals** - Add entry engines in `signals/entries/` and update `ENTRY_ENGINE_REGISTRY`. Ensure predicate coverage in `signals/predicates.py`.
  `threshold_reversion` is strategy-owned today; use it as the template only when the indicator state is intentionally private to the engine.
- **Data Feed** - Extend `_data_feed.pyx` for alternative storage layouts or override the fallback `DataFeed` to adapt path conventions.
- **Analysis** - New reports can hook into `analysis/workflow.py` or custom scripts under `scripts/`.

## Testing Strategy

- Unit tests live in `tests/` broken down by concern (config parsing, data feed validation, backtest coordinator, integration runs).
- Use a clean editable install before running tests so compiled extensions are available: `pip install -e . && pytest -m "not slow"`.
- When adding new metrics or signals, include regression fixtures to lock expected schema and trade behaviour.

## Build & Release Notes

- Wheels are built via `python -m build`. Ensure the Cython extension is compiled before distribution.
- CI (GitHub Actions) runs unit tests plus smoke/release workflows defined under `.github/workflows/`.
- When bumping schema versions, update config templates, parsers, and this documentation simultaneously.

## Open Questions / TODOs

- Consider documenting the compiled interface for `MetricsManager` if we expose more public APIs.
- Evaluate adding a plugin mechanism for custom analysis outputs in future releases.

Update this file whenever internal architecture changes or new extension points become available.
