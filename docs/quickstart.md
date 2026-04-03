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

This guide covers both installed-package usage and repository-checkout usage. Installed users should start with the packaged demo project. Repository-root configs under `config/` are for checkout-only development and CI.

!!! info "No proprietary market data required"
    The package ships with seeded Brownian-motion Parquet fixtures, so you can complete this quickstart immediately and only later point the stack at private shards.

## Prerequisites

- Python 3.12
- Access to Dukascopy-style Parquet shards organised as `{data_root}/{PAIR}/{PAIR}_YYYY-MM.parquet`
- Sufficient disk space for output manifests and trade artefacts

Each shard should contain `timestamp`, `bid`, and `ask` columns. Tick Backtest expects this archive to exist already and does not download market data itself; if you need a fetch pipeline, [`dukascopy-python`](https://github.com/fx-trader/dukascopy-python) is a suitable external option.

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

For your own data, start from the generic packaged templates:

```bash
tick-backtest example-config --output ./tick-backtest-config
```

Edit `backtest.yaml` to point at your parquet archive and output location, then run `tick-backtest run ./tick-backtest-config/backtest.yaml`.

## Repository Checkout Quickstart

If you are working from a checkout rather than an installed package:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .[tests]
```

??? tip "Need docs tooling?"
    To build this documentation locally, also install the doc requirements:
    ```bash
    pip install -r requirements-docs.txt
    ```

Repository-root configs live under `config/` and are checkout-only development assets. The default backtest config lives at `config/backtest/default_backtest.yaml`. Update these fields for your data environment or copy the `.example` files (for example `config/backtest/local_default_backtest.yaml.example`) to files without the `.example` suffix and customise those versions for private datasets:

- `data_base_path`: absolute path to your Parquet archive
- `output_base_path`: directory for backtest artefacts
- `start` / `end`: inclusive year-month ranges (ISO `YYYY-MM`)
- `pairs`: list of currency pairs

Metrics and strategy definitions live in:

- `config/metrics/default_metrics.yaml`
- `config/strategy/default_strategy.yaml`

### Python API

```python
from tick_backtest.backtest.workflow import run_backtest

result = run_backtest("config/backtest/default_backtest.yaml")
print(result["run_id"], result["output_dir"])
```

### Command Line Helper

```bash
tick-backtest run config/backtest/default_backtest.yaml
```

Both entry points create a timestamped directory under `output/backtests/`.

## Inspect the Results

After the run completes, explore:

- `manifest.json`: snapshot of configs, input shards, trade outputs, and status
- `output/<PAIR>/trades.parquet`: trade-level dataset
- `output/<PAIR>/analysis/report.md`: Markdown report with key metrics and equity curve
- `output/logs/<RUN_ID>.log`: NDJSON log for auditing

Continue to [Analysis & Reporting](analysis.md) for a detailed walkthrough of these artefacts.

!!! note "Performance & design rationale"
    Tick ingestion is vectorised via PyArrow, but trade execution remains sequential per pair to preserve causal correctness. On an AMD 5950X reference machine the backtest loop processes ~8 million ticks per minute per core while still writing deterministic manifests and logs for every configuration.
