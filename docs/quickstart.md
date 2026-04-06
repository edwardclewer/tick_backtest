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

# Quickstart

See also: [Configuration Overview](configs.md) · [Metrics Reference](configs/metrics.md) · [Strategy Reference](configs/strategy.md)

This guide covers both installed-package usage and repository-checkout usage. Installed users should start with the packaged demo project. Repository-checkout setup appears later as a secondary contributor workflow.

!!! info "No proprietary market data required"
    The package ships with seeded Brownian-motion Parquet fixtures, so you can complete this quickstart immediately and only later point the stack at private shards.

## Prerequisites

- Python 3.12
- Sufficient disk space for output manifests and trade artefacts

If you want to run the bundled demo project, no external market data is required.

For your own data, Tick Backtest expects an existing archive of Parquet shards organised as `{data_root}/{PAIR}/{PAIR}_YYYY-MM.parquet` with `timestamp`, `bid`, and `ask` columns. Tick Backtest does not download market data itself; if you need a fetch pipeline, [`dukascopy-python`](https://github.com/fx-trader/dukascopy-python) is a suitable external option.

If your upstream source is Dukascopy, convert the downloaded data into that Parquet layout before running the package. Tick Backtest does not consume Dukascopy raw exports directly. Preserve pair separation, keep one shard per month, and expose `timestamp`, `bid`, and `ask` in the converted files.

Tick Backtest does not impose an experiment-level directory scheme beyond writing each run to `output_base_path/<RUN_ID>/`. If you are running related strategies or config sweeps, a simple pattern is to group runs under an experiment folder and point `output_base_path` at an experiment-specific `runs/` directory.

## Installed Package Quickstart

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install tick-backtest
```

Generate a runnable public demo project:

```bash
tick-backtest example-config --output ./demo --include-demo-data
tick-backtest run ./demo/backtest.yaml
```

Then inspect the trade artefacts and optional post-processing:

```bash
tick-backtest report ./demo/output/<RUN_ID>/output/EURUSD/trades.parquet
tick-backtest analyze ./demo/output/<RUN_ID>/output/EURUSD/trades.parquet
```

If you want to locate the generated trade files first:

```bash
find ./demo/output -path '*/output/*/trades.parquet' | sort
```

The generated demo project contains:

- `backtest.yaml`, `metrics.yaml`, and `strategy.yaml`
- `demo_data/` with bundled EURUSD and GBPUSD Parquet shards
- `output/` as the configured run destination

For your own data, start from the generic packaged templates:

```bash
tick-backtest example-config --output ./tick-backtest-config
```

Edit `backtest.yaml` to point at your parquet archive and output location, then run `tick-backtest run ./tick-backtest-config/backtest.yaml`.

Path handling is config-relative: `data_base_path`, `output_base_path`, `metrics_config_path`, and `strategy_config_path` are resolved against the directory containing `backtest.yaml`.

Expected archive shape:

```text
tick_data/
  EURUSD/
    EURUSD_2024-01.parquet
    EURUSD_2024-02.parquet
  GBPUSD/
    GBPUSD_2024-01.parquet
```

Packaged starter strategies:

- `minimal` emits `threshold_reversion_strategy`
- `demo` emits `ewma_crossover`

These are starter configurations for validating your data path and runtime setup. For a first pass on new market data, it is usually better to run one of them unchanged before tuning thresholds, predicates, or exits.

Execution model limits:

- no commissions or fees
- no slippage model
- no order book depth, queue position, or market impact model
- no exchange-specific matching or partial-fill simulation

The package is intended for deterministic signal and strategy research, not full execution-cost simulation.

For example, you might use a layout like:

```text
research/
  configs/
  experiments/
    mean_reversion_q2_2026/
      runs/
        <RUN_ID>/
      notes/
      summaries/
```

This keeps the package flexible while still giving you a clean place to organise sweeps and follow-up analysis.

## Repository Checkout Quickstart

If you are working from a checkout rather than an installed package:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

??? tip "Need docs tooling?"
    To build this documentation locally, also install the doc requirements:
    ```bash
    pip install -r requirements-docs.txt
    ```

This editable install step is required for a clean local test run because the package builds compiled extensions used by the runtime and test suite.

Repository helper fixtures live under `src/tick_backtest/config/` and are checkout-only development assets. The bundled test backtest fixture lives at `src/tick_backtest/config/backtest/test_backtest.yaml`. Update these fields for your local data environment before using that fixture outside CI-style checks:

- `data_base_path`: absolute path to your Parquet archive
- `output_base_path`: directory for backtest artefacts
- `start` / `end`: inclusive year-month ranges (ISO `YYYY-MM`)
- `pairs`: list of currency pairs

The paired metrics and strategy fixtures live in:

- `src/tick_backtest/config/metrics/test_metrics.yaml`
- `src/tick_backtest/config/strategy/test_strategy.yaml`

### Python API

```python
from tick_backtest.backtest.workflow import run_backtest

result = run_backtest("src/tick_backtest/config/backtest/test_backtest.yaml")
print(result["run_id"], result["output_dir"])
```

### Command Line Helper

```bash
tick-backtest run src/tick_backtest/config/backtest/test_backtest.yaml
```

Both entry points create a timestamped directory under the configured `output_base_path/<RUN_ID>/`.

## Inspect the Results

After the run completes, explore:

- `manifest.json`: snapshot of configs, input shards, trade outputs, and status
- `output/<PAIR>/trades.parquet`: trade-level dataset
- `output/logs/<RUN_ID>.log`: NDJSON log for auditing

Then generate post-run artefacts from the pair trade file:

```bash
tick-backtest report ./demo/output/<RUN_ID>/output/EURUSD/trades.parquet
tick-backtest analyze ./demo/output/<RUN_ID>/output/EURUSD/trades.parquet
```

These commands write beside `trades.parquet`:

- `trades_report.md`
- `trades_equity_curve.png`
- `metric_stratification/`
- `multivariate_analysis/`

Continue to [Analysis & Reporting](analysis.md) for a detailed walkthrough of these artefacts.

!!! note "Performance & design rationale"
    Tick ingestion is vectorised via PyArrow, but trade execution remains sequential per pair to preserve causal correctness. On an AMD 5950X reference machine the backtest loop processes ~8 million ticks per minute per core while still writing deterministic manifests and logs for every configuration.
