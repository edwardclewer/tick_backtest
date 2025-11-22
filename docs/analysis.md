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

# Analysis & Reporting

See also: [Quickstart](quickstart.md) · [Metrics Reference](configs/metrics.md) · [Concepts](concepts.md)

Every backtest produces a reproducible bundle under `output/backtests/<RUN_ID>/`. This guide explains the structure and how to interpret the artefacts. Screenshots and snippets in this page originate from seeded Brownian-motion fixtures so you can reproduce them locally.

## Directory Layout

```
output/backtests/<RUN_ID>/
├── configs/                  # Snapshots of the YAML files and SHA256 digests
├── environment.txt           # pip freeze output captured at runtime
├── manifest.json             # High-level run metadata
└── output/
    ├── logs/<RUN_ID>.log     # NDJSON structured log
    └── <PAIR>/
        ├── trades.parquet    # Trade-level dataset
        └── analysis/
            ├── report.md     # Markdown report with metrics summary
            ├── equity_curve.png
            └── metric_stratification/
```

| Artefact | Location | Purpose |
| --- | --- | --- |
| Config snapshots | `configs/*.yaml` | Literal copies of the YAML inputs with SHA256 hashes. |
| Dependency freeze | `environment.txt` | `pip freeze` output captured at runtime for reproducibility. |
| Manifest | `manifest.json` | Run metadata, shard hashes, tick validation summary, and outputs. |
| Structured log | `output/logs/<RUN_ID>.log` | NDJSON event stream covering lifecycle, warnings, and errors. |
| Trades | `output/<PAIR>/trades.parquet` | Row-per-trade dataset (metrics, metadata, PnL). |
| Analysis bundle | `output/<PAIR>/analysis/` | Markdown report, equity curve, and metric stratification artefacts. |

## Manifest Highlights

`manifest.json` provides an auditable snapshot:

- `run_id`, `timestamp_utc`, `code_ref` – Identify the exact run and git commit hash.
- `configs` – Original and copied config paths with SHA256 hashes and embedded YAML text.
- `input_shards` – Each referenced Parquet file with row counts, hashes, and error annotations.
- `outputs` – Per-pair trade files with row counts.
- `pair_failures` – Map of pairs that failed validation or execution.
- `tick_validation` – Counters for skipped ticks grouped by issue type.

Use the manifest to confirm data coverage, identify missing shards, and verify that configs were not altered post-run.

```json
{
  "run_id": "20251101215953-dbb12e3d",
  "code_ref": "56e94c0ebc9a9f269e3fe14bfe35fdfbc98fd06d",
  "configs": {
    "backtest": {
      "sha256": "ac87e12dec2d6c547693b60f355779d86e195665ff063e76a1cb8ffc73cbe852",
      "schema_version": "1.0"
    }
  },
  "outputs": [
    {"pair": "EURUSD", "rows": 46773, "path": ".../output/EURUSD/trades.parquet"}
  ],
  "tick_validation": {
    "EURUSD": {
      "total_ticks": 14748428,
      "accepted_ticks": 14748428,
      "skipped_ticks": 0,
      "issues": {}
    }
  }
}
```

## Structured Logs

`output/logs/<RUN_ID>.log` uses NDJSON entries. Useful log types:

- `run metadata snapshot` – Emitted at start; lists active config paths.
- `starting pair backtest` / `completed pair backtest` – Brackets each symbol run.
- `tick validation summary` – Final tallies of accepted/skipped ticks.
- Error entries – Include stack traces and pair names to aid debugging.

Load the log into tools like `jq`, your preferred observability stack, or attach snippets to GitHub issues for richer analysis.

## Trade Dataset (`trades.parquet`)

Columns include:

- `pair`, `direction`, `entry_time`, `exit_time`, `holding_seconds`
- `entry_price`, `exit_price`, `pnl_pips`, `outcome_label`
- Embedded metric snapshots (`metric_name.value`) at entry time
- Signal metadata (`entry_metadata`, `reason`, `timeout_seconds`)

You can create pandas notebooks to recompute KPIs or feed trades into downstream analytics.

## Markdown Report

`analysis/report.md` summarises headline metrics:

- Trade counts (win/loss/breakeven)
- Net/Gross PnL in pips, expectancy, profit factor
- Sharpe ratios (per-trade and daily)
- Max drawdown and duration
- Link/inline image to `equity_curve.png`

Use this as a lightweight performance overview before diving into raw trades.

![Equity curve example](./_static/equity_curve.png)

## Metric Stratification

The analysis package generates stratification artefacts under `analysis/metric_stratification/`:

- `csv/<mode>/` – Expectancy tables grouped by metric bins.
- `graphs/<mode>/` – PNG visualisations for quick inspection.
- `reports/metric_report_<mode>.md` – Narrative explanation of metric impact.

The binning modes are derived from the metrics configuration. Disable or extend metrics to tailor these outputs.

## Troubleshooting

- **Empty `trades.parquet`** – Check `Warmup` duration and entry predicates; run logs for “no data available” warnings.
- **Missing Analysis Files** – Ensure `tick_backtest.analysis.run_backtest_analysis` executed; errors are logged but do not fail the run.
- **Validation Failures** – Inspect `tick_validation` in the manifest to confirm whether bad ticks were skipped or data shards were missing.

See [Quickstart](quickstart.md) for rerunning the pipeline and [Developer Internals](dev/internals.md) for debugging compiled components.
