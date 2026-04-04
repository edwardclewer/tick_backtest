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

# Tick Backtest

*Deterministic tick-level FX backtesting for reproducible research.*

Tick Backtest is a configuration-first Python 3.12 package for FX strategy research. You provide Parquet tick shards and YAML configs; the package validates the configuration, runs deterministic backtests, and writes manifests, logs, reports, and analysis artefacts to disk.

### Highlights
- **Performance:** ~130k ticks/second/core on AMD 5950X (Parquet -> metrics -> signals -> trades)
- **Deterministic runs:** config snapshots, git hash, dependency snapshot, and shard hashes are captured per run
- **Resilient pipelines:** per-pair failure isolation, tick validation, and structured telemetry
- **Declarative research:** swap YAML configs instead of editing strategy code
- **Report ready:** trade tables, Markdown summaries, metric stratification CSV/PNG artefacts
- **CLI + API parity:** every supported command is exposed both as `tick-backtest ...` and `tick_backtest.api.*(...)`

Documentation is hosted here: [Documentation Site](https://edwardclewer.github.io/tick_backtest/).
Release process details live in [docs/releasing.md](docs/releasing.md).

---

## Install

Installed-package usage is the primary workflow.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install tick-backtest
```

The package uses compiled extensions for core runtime components. Normal installed usage assumes those extensions are available through the package build/install process.

---

## Quickstart

1. Generate a runnable demo project with bundled fixture data:
   ```bash
   tick-backtest example-config --output ./demo --include-demo-data
   ```
2. Run the demo backtest:
   ```bash
   tick-backtest run ./demo/backtest.yaml
   ```
3. Generate report artefacts for one pair:
   ```bash
   tick-backtest report ./demo/output/<RUN_ID>/output/EURUSD/trades.parquet
   ```
4. Run multivariate trade analysis:
   ```bash
   tick-backtest analyze ./demo/output/<RUN_ID>/output/EURUSD/trades.parquet
   ```

The same surface is available from Python:

```python
from tick_backtest import api

api.example_config("./demo", include_demo_data=True)
api.run("./demo/backtest.yaml")
api.report("./demo/output/<RUN_ID>/output/EURUSD/trades.parquet")
api.analyze("./demo/output/<RUN_ID>/output/EURUSD/trades.parquet")
```

The generated demo project contains:
- `backtest.yaml`, `metrics.yaml`, and `strategy.yaml`
- `demo_data/` with bundled EURUSD and GBPUSD Parquet shards
- `output/` as the configured run destination

---

## Your Own Data

To start from generic packaged templates instead of the demo project:

```bash
tick-backtest example-config --output ./tick-backtest-config
```

Edit the generated `backtest.yaml`:

```yaml
schema_version: "1.0"
pairs: [EURUSD]
start: 2024-01
end: 2024-01
pip_size: 0.0001
warmup_seconds: 1800
data_base_path: "/abs/path/to/tick_data/"
output_base_path: "/abs/path/to/backtest_outputs/"
metrics_config_path: "./metrics.yaml"
strategy_config_path: "./strategy.yaml"
```

Expected data layout:

- Tick shards are organised as `{data_root}/{PAIR}/{PAIR}_YYYY-MM.parquet`
- Required Parquet columns are `timestamp`, `bid`, and `ask`
- `start` and `end` are inclusive year-month boundaries
- `data_base_path`, `output_base_path`, `metrics_config_path`, and `strategy_config_path` are resolved relative to the directory containing `backtest.yaml`

Tick Backtest does not download market data itself. If you need a source-to-parquet workflow, [`dukascopy-python`](https://github.com/fx-trader/dukascopy-python) is a suitable external option.

Tick Backtest does not impose a portfolio- or experiment-level directory scheme beyond writing each run to `output_base_path/<RUN_ID>/`. For repeatable research, it is often useful to group related runs under an experiment directory and point `output_base_path` at an experiment-specific `runs/` folder, for example:

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

This keeps the package flexible while still giving you a clean place to organise sweeps, comparisons, and follow-up analysis.

---

## Outputs

After `tick-backtest run`, inspect outputs under the resolved `output_base_path/<RUN_ID>/`:

| Path | Purpose |
| --- | --- |
| `manifest.json` | Immutable run snapshot containing configs, git hash, shard hashes, status, and output metadata |
| `environment.txt` | Dependency snapshot from `pip freeze` |
| `output/logs/<RUN_ID>.log` | Structured NDJSON log with validation summaries and runtime errors |
| `output/<PAIR>/trades.parquet` | Trade-level dataset including entry metadata, metrics, and PnL |
| `configs/*.yaml` | Copies of backtest, metrics, and strategy configs with SHA256 digests |

After `tick-backtest report <trades.parquet>`, additional artefacts are written beside the trade file:

| Path | Purpose |
| --- | --- |
| `trades_report.md` | Markdown performance summary for the selected trade file |
| `trades_equity_curve.png` | Equity curve plot referenced by the report |
| `metric_stratification/` | Stratification CSV, graph, and Markdown report bundles |

After `tick-backtest analyze <trades.parquet>`, multivariate artefacts are written beside the trade file under `multivariate_analysis/`.
This bundle includes `summary.md`, `coefficients.csv`, `correlations.csv`, and `dropped_predictors.csv`.

---

## Public Commands

| Command | Input | Output location |
| --- | --- | --- |
| `tick-backtest run <backtest.yaml>` | Backtest config | Writes a run directory under the configured `output_base_path/<RUN_ID>/` |
| `tick-backtest report <trades.parquet>` | Trade database | Writes trade report artefacts and metric stratification beside the parquet file |
| `tick-backtest analyze <trades.parquet>` | Trade database | Writes `multivariate_analysis/` beside the parquet file |
| `tick-backtest example-config [--output DIR] [--include-demo-data]` | Optional destination dir | Prints starter YAML or writes a template set or runnable demo project |

---

## Python API

| Function | Purpose |
| --- | --- |
| `tick_backtest.api.run(config_path, *, output_root=None)` | Run the backtest engine and write run artefacts only |
| `tick_backtest.api.report(trades_path)` | Generate trade report artefacts and metric stratification outputs |
| `tick_backtest.api.analyze(trades_path)` | Generate multivariate regression-style analysis outputs |
| `tick_backtest.api.example_config(dest=None, *, template="minimal", include_demo_data=False)` | Print or write starter YAML templates, optionally with bundled demo data |

The API is intentionally filesystem-oriented. It writes artefacts to disk and does not aim to return in-memory result objects.

---

## Architecture Snapshot

- Packaged YAML templates and bundled demo data are exposed through `tick-backtest example-config`
- Backtest configs are parsed into validated dataclasses before runtime
- Tick data is streamed from Parquet month by month and wrapped in a validator that skips invalid ticks
- Per-pair execution remains sequential to avoid lookahead bias
- Metrics, signals, and position handling run inside the backtest loop and completed trades persist to Parquet
- Reporting and regression-style analysis are post-run workflows invoked separately from the backtest itself

**Data flow**
1. Parse and validate backtest, metrics, and strategy YAML.
2. Stream Parquet ticks through the validating feed.
3. Update metrics, evaluate signals, and manage positions one tick at a time.
4. Persist trades, logs, config snapshots, manifest, and dependency snapshot to disk.
5. Run `report` or `analyze` later against a chosen `trades.parquet`.

Dive deeper in the [Developer Notes](https://edwardclewer.github.io/tick_backtest/dev/internals/).

---

## Contributor Setup

If you are working from a repository checkout rather than an installed package:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

This editable install step is required for a clean local test run because the package builds compiled extensions used by the runtime and test suite.

If you also want to build the docs locally:

```bash
pip install -r requirements-docs.txt
```

If you want to build distribution artefacts locally:

```bash
python -m build
```

Installed usage should go through `tick-backtest` or `tick_backtest.api`. Repository helper scripts under `scripts/` are secondary development and CI utilities.

---

## Troubleshooting Essentials

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `ConfigError: unknown field ...` | Extra keys in YAML | Remove or rename; see the [Configuration Guide](https://edwardclewer.github.io/tick_backtest/configs/) |
| `pyarrow` import error | Wheel missing | Install the package dependencies and rerun |
| `ModuleNotFoundError` for compiled `tick_backtest` modules in a repo checkout | Editable install/build step missing | Run `pip install -e .` inside the active virtualenv |
| Run finishes but no trades | Warmup consumed data or predicates blocked | Check `output/logs/<RUN_ID>.log` and entry predicates |
| Manifest shows `missing_file` | `data_base_path` does not match the expected shard layout | Adjust the path or supply the expected Parquet shards |
| Percentile metrics return `NaN` | Histogram warming up | Feed more ticks; this is expected during the early part of a run |

---

## Compatibility & Dependencies

- Python 3.12
- `numpy >= 1.26, < 3.0`
- `pandas >= 1.5, < 2.3`
- `pyarrow >= 10.0, < 16.0`
- `matplotlib >= 3.7, < 3.9`
- `pyyaml >= 6.0, < 6.1`

Running offline? Pre-install these wheels in your environment. Backtests require `pip freeze` to succeed so the dependency snapshot can be captured in `environment.txt`.

---

## Testing & CI

For a clean local test run from a checkout:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

Coverage highlights:
- `tests/config_parsers` - YAML schema governance and regression checks
- `tests/data_feed` - tick validation and resilience
- `tests/metrics` - primitives plus indicator mathematics with reference helpers
- `tests/integration/test_backtest_run.py` - end-to-end pipeline regression

GitHub Actions builds wheels, runs tests, validates distribution metadata, and publishes docs via `.github/workflows/`.

---

## Next Steps

1. Generate a starter config with `tick-backtest example-config`.
2. Point it at your own Parquet tick data.
3. Run `tick-backtest run` and inspect the generated manifest and pair-level artefacts.
4. Explore the [documentation](https://edwardclewer.github.io/tick_backtest/) for advanced configuration and internals.

---

**Author**: Edward Clewer  
**License**: Apache License 2.0  
**Docs**: [Docs](https://edwardclewer.github.io/tick_backtest/)
