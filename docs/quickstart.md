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

This guide helps you install the Tick Backtest Research Stack, configure your environment, and run the default EURUSD backtest end-to-end. The bundled fixtures are generated from seeded Brownian-motion processes so you can experiment without access to proprietary market data.

## Prerequisites

- Python 3.12
- Access to Dukascopy-style Parquet shards organised as `{data_root}/{PAIR}/{PAIR}_YYYY-MM.parquet`
- Sufficient disk space for output manifests and trade artefacts

## Installation

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# optional: editable install with tests
pip install -e .[tests]
```

??? tip "Need docs tooling?"
    To build this documentation locally, also install the doc extras:
    ```bash
    pip install -r requirements-docs.txt
    ```

## Configure the Sample Backtest

The default configuration lives at `config/backtest/default_backtest.yaml`. Update these fields for your data environment or copy the `.example` files (e.g. `config/backtest/local_default_backtest.yaml.example`) to files without the `.example` suffix (gitignored) and customise those versions for private datasets:

- `data_base_path`: absolute path to your Parquet archive
- `output_base_path`: directory for backtest artefacts
- `start` / `end`: inclusive year-month ranges (ISO `YYYY-MM`)
- `pairs`: list of currency pairs (default `["EURUSD"]`)

Metrics and strategy definitions live in:

- `config/metrics/default_metrics.yaml`
- `config/strategy/default_strategy.yaml`

You can accept the defaults for a first run.

## Run the Backtest

### Python API

```python
from tick_backtest.backtest.workflow import run_backtest

result = run_backtest("config/backtest/default_backtest.yaml")
print(result["run_id"], result["output_dir"])
```

### Command Line Helper

```bash
PYTHONPATH=src python scripts/run_backtest.py \
  --config config/backtest/default_backtest.yaml
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
