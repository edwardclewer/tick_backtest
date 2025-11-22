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

# Configuration Reference

Backtests are driven entirely by YAML files. This guide explains each schema and how validation enforces correctness.

## Backtest Configuration (`config/backtest/*.yaml`)

| Field | Type | Description |
| --- | --- | --- |
| `schema_version` | string | Required version tag (current: `"1.0"`). |
| `pairs` | list[string] | Currency pairs to backtest (e.g., `["EURUSD", "GBPUSD"]`). |
| `start` / `end` | string (`YYYY-MM`) | Inclusive year-month range for data shards. |
| `pip_size` | float | Pip precision used for PnL and TP/SL calculations. |
| `warmup_seconds` | int | Seconds of historical ticks consumed before trading. |
| `data_base_path` | path | Root directory containing `{pair}/{pair}_YYYY-MM.parquet` shards. |
| `output_base_path` | path | Directory where `output/backtests/<RUN_ID>/` will be created. |
| `metrics_config_path` | path | Metrics YAML to load. |
| `strategy_config_path` | path | Strategy YAML to load. |

Validation highlights:

- Start month must be less than or equal to end month.
- Unknown keys raise a configuration error.
- Output paths are created automatically if missing.

## Metrics Configuration (`config/metrics/*.yaml`)

Each metric entry maps to a dataclass in `tick_backtest.config_parsers.metrics`. Validation enforces:

- unique `name` values (used as prefixes in metric snapshots),
- recognised `type` keys from `METRIC_CLASS_REGISTRY`,
- optional `enabled` flag (defaults to `true` when omitted),
- a `params` mapping matching the metric’s schema.

<details>
<summary><strong>Sample metrics YAML</strong></summary>

```
- name: z30m
  type: zscore
  enabled: true
  params:
    lookback_seconds: 1800
- name: ewma_vol_5m
  type: ewma_vol
  params:
    tau_seconds: 300
    percentile_horizon_seconds: 300
    bins: 256
    base_vol: 0.0001
    stddev_cap: 5.0
```

</details>

👉 Need per-metric parameter tables, defaults, output fields, and behavioural notes? See the dedicated [Metrics Reference](configs/metrics.md).

## Strategy Configuration (`config/strategy/*.yaml`)

<details>
<summary><strong>Sample strategy YAML</strong></summary>

```
schema_version: "1.0"
strategy:
  name: threshold_reversion_strategy
  entry:
    name: threshold_reversion_entry
    engine: threshold_reversion
    params:
      lookback_seconds: 1800
      threshold_pips: 10
      tp_pips: 10
      sl_pips: 20
      min_recency_seconds: 60
      trade_timeout_seconds: 7200
    predicates:
      - metric: tick_rate_30s.tick_rate_per_min
        operator: "<"
        value: 200.0
      - metric: ewma_mid_5m_slope.slope
        operator: ">"
        use_abs: true
        value: 5e-7
  exit:
    name: default_exit
    predicates: []
```

</details>

Entry and exit definitions combine:

- **Engine** – `engine` selects an entry implementation from `ENTRY_ENGINE_REGISTRY`.
- **Params** – Engine-specific tuning (thresholds, TP/SL, timeouts).
- **Predicates** – Optional guards that must evaluate `true` before opening or closing trades. Supported operands:
  - `metric` – Dot-referenced metric field (e.g., `ewma_vol_5m.vol_percentile`).
  - `operator` – String comparator (`<`, `>`, `<=`, `>=`, `==`, `!=`).
  - `value` or `other_metric` – Literal value or second metric.
  - `use_abs` – Apply absolute value before comparing.

Validation prevents duplicate predicates and rejects unknown fields.

👉 For detailed documentation of every entry engine, predicate option, metadata field, and runtime behaviour, jump to the [Strategy Reference](configs/strategy.md).

## Extending Configurations

- **New Metrics** – Implement a metric dataclass and runtime class, register in `METRIC_CLASS_REGISTRY`, then reference via `type`.
- **New Entry Engines** – Add implementations under `tick_backtest/signals/entries/`, register in `ENTRY_ENGINE_REGISTRY`, and expose parameters in the strategy config.
- **Alternative Schemas** – Bump `schema_version` when adding new fields, and update config parsers to maintain backward compatibility.

Refer to [Developer Internals](dev/internals.md) for wiring new components into registries and tests.
