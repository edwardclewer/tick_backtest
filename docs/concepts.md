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

# Concepts Glossary

This page defines the key abstractions used throughout the Tick Backtest Research Stack. Each term links to the page where it is most frequently applied.

## Backtest run
One invocation of `run_backtest` (or the CLI wrapper) using a specific backtest, metrics, and strategy configuration. Each run writes a unique directory under `output/backtests/<RUN_ID>/`.

## Manifest
`manifest.json` inside each run directory capturing metadata: run ID, git hash, input shard hashes, config snapshots, validation stats, outputs, and status. See [Analysis & Reporting](analysis.md#manifest-highlights).

## Metrics registry
Mapping from YAML `type` strings to metric dataclasses. Defined in `tick_backtest/config_parsers/metrics/config_registry.py`. Metrics are instantiated by `MetricsManager` and their outputs appear as `<name>.<field>` dictionaries. Reference: [Metrics Reference](configs/metrics.md).

## Metric snapshot
The dictionary returned by `MetricsManager.update()` or `.current()`, containing the latest values for all enabled metrics. Strategies read these snapshots when evaluating predicates or entry engines.

## Predicate
Declarative condition in strategy YAML comparing a metric against a literal or another metric. All predicates must evaluate to `true` for an entry/exit block to trigger. Valid operators: `<`, `<=`, `>`, `>=`, `==`, `!=`. Details in [Strategy Reference](configs/strategy.md#entry-blocks).

## Entry engine
Runtime class implementing strategy-specific entry logic (e.g., threshold reversion, EWMA crossover). Receives ticks + metric snapshots and returns `EntryResult` objects. Configured via `entry.engine` and `entry.params`. See [Strategy Reference](configs/strategy.md).

## Exit predicates
Predicates defined under `strategy.exit`. When all evaluate to `true`, the signal generator requests position closure. If no exit predicates are supplied, trades only close via TP/SL/timeout. See [Strategy Reference](configs/strategy.md#exit-blocks).

## Tick validator
Wrapper around the data feed ensuring ticks are monotonic and free of NaNs/negative spreads. Invalid ticks are skipped, and counts appear in the manifest/logs. Implementation: `tick_backtest.data_feed.validation.ValidatingDataFeed`. Discussed in [Architecture](architecture.md#resilience--reproducibility).

## Trade record
Row written to `trades.parquet` per completed position. Includes entry/exit timestamps, PnL, holding time, outcome label, entry metadata (metrics at signal time), and any engine-specific fields. Reviewed in [Analysis & Reporting](analysis.md#trade-dataset-tradesparquet).

## Threshold reversion metric
Compiled indicator (`ThresholdReversionMetric`) and corresponding entry engine used by the sample strategy. Tracks a reference price and emits signals when price deviates by `threshold_pips`. Explained in [Strategy Reference](configs/strategy.md#threshold_reversion).

Use this glossary as a quick reference while navigating the documentation or describing the system during interviews.
