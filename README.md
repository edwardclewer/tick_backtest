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

Tick Backtest is a configuration-first Python 3.12 toolkit for reproducible FX strategy research. You provide Parquet ticks and YAML configs; the stack validates every setting, executes deterministic backtests, and writes manifests, logs, reports, and analysis artefacts to disk.

### Highlights
- **Performance:** ~8 million ticks/minute/core on AMD 5950X (Parquet -> metrics -> signals -> trades)
- **Deterministic runs:** Deterministic runs: config, git hash, dependency snapshot, and shard hashes captured per run
- **Resilient pipelines:** Resilient pipelines: per-pair failure isolation, tick validation, and structured telemetry
- **Declarative research:** Declarative research: swap YAML configs instead of editing code
- **Report ready:** Report ready: trade tables, Markdown summaries, metric stratification CSV/PNG artefacts
- **CLI + API parity:** Every supported command is exposed both as `tick-backtest ...` and `tick_backtest.api.*(...)`

Documentation is hosted here: [Documentation Site](https://edwardclewer.github.io/tick_backtest/).
Release process details are documented in [docs/releasing.md](docs/releasing.md).

---

## Quickstart

1. **Install prerequisites**
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install tick-backtest
   ```

2. **Write a starter config**
   ```bash
   tick-backtest example-config --output ./demo --include-demo-data
   ```

3. **Run the bundled demo project**
   ```bash
   tick-backtest run ./demo/backtest.yaml
   ```

4. **Generate report artefacts for a single trade file**
   ```bash
   tick-backtest report ./demo/output/<RUN_ID>/output/EURUSD/trades.parquet
   ```

5. **Run multivariate trade analysis**
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

The generated demo project includes:
- `backtest.yaml`, `metrics.yaml`, and `strategy.yaml`
- `demo_data/` with bundled EURUSD and GBPUSD parquet shards
- `output/` as the run destination declared in the emitted config

Config surfaces are intentionally split:
- `src/tick_backtest/config/templates/` and `src/tick_backtest/demo_data/` are the public packaged assets used by installed users.
- `config/` at the repository root is for checkout-only development, smoke tests, and CI golden runs.

For your own data instead of the bundled demo, emit the generic starter templates:
```bash
tick-backtest example-config --output ./tick-backtest-config
```
Then edit the generated YAML files:
```yaml
# tick-backtest-config/backtest.yaml
data_base_path: "/abs/path/to/your/parquet/shards"
output_base_path: "/abs/path/to/backtest/output"
metrics_config_path: "./metrics.yaml"
strategy_config_path: "./strategy.yaml"
```

`data_base_path` should contain monthly shards organised as `{data_root}/{PAIR}/{PAIR}_YYYY-MM.parquet` with `timestamp`, `bid`, and `ask` columns. Tick Backtest does not download market data itself; if you need a source-to-parquet workflow, [`dukascopy-python`](https://github.com/fx-trader/dukascopy-python) is a suitable external option.

Path handling is config-relative. In the backtest parser, `data_base_path`, `output_base_path`, `metrics_config_path`, and `strategy_config_path` are resolved against the directory containing `backtest.yaml`, so `./metrics.yaml` means "next to this backtest config", not "relative to the shell's current working directory".

After `tick-backtest run`, inspect outputs under the resolved `output_base_path/<RUN_ID>/`:

   | Path | Purpose |
   | --- | --- |
   | `manifest.json` | Immutable run snapshot (configs, git hash, shard hashes, status). |
   | `output/logs/<RUN_ID>.log` | Structured NDJSON log with validation summaries and errors. |
   | `output/<PAIR>/trades.parquet` | Trade-level dataset including metrics and PnL. |
   | `configs/*.yaml` | Copies of backtest/metrics/strategy configs with SHA256 digests. |

After `tick-backtest report output/<PAIR>/trades.parquet`, additional artefacts are written beside the trade file:

   | Path | Purpose |
   | --- | --- |
   | `output/<PAIR>/trades_report.md` | Markdown performance summary for the selected trade file. |
   | `output/<PAIR>/trades_equity_curve.png` | Equity curve plot referenced by the report. |
   | `output/<PAIR>/metric_stratification/` | Stratification CSV, graph, and Markdown report bundles. |

After `tick-backtest analyze output/<PAIR>/trades.parquet`, multivariate artefacts are written beside the trade file under `output/<PAIR>/multivariate_analysis/`.
This bundle includes `summary.md`, `coefficients.csv`, `correlations.csv`, and `dropped_predictors.csv` for predictors removed during explicit collinearity pruning.

---

## Public Commands

| Command | Input | Output location |
| --- | --- | --- |
| `tick-backtest run <backtest.yaml>` | Backtest config | Writes a run directory under `output_base_path/<RUN_ID>/` |
| `tick-backtest report <trades.parquet>` | Trade database | Writes trade report artefacts and metric stratification beside the parquet file |
| `tick-backtest analyze <trades.parquet>` | Trade database | Writes `multivariate_analysis/` beside the parquet file |
| `tick-backtest example-config [--output DIR] [--include-demo-data]` | Optional destination dir | Prints starter YAML or writes a template set or runnable demo project |

## Configuration Cheat Sheet

Tick Backtest is driven by three YAML files that are validated against strict schemas (unknown keys and duplicates are rejected).

<details>
<summary><strong>Backtest YAML</strong></summary>

```yaml
schema_version: "1.0"
pairs: [EURUSD, GBPUSD]
start: 2012-02
end: 2013-02
pip_size: 0.0001
warmup_seconds: 1800
data_base_path: "/data/dukascopy/"
output_base_path: "/results/backtests/"
metrics_config_path: "config/metrics/default_metrics.yaml"
strategy_config_path: "config/strategy/default_strategy.yaml"
```
Key fields: pair list, inclusive year-month span, data/output roots, warmup length, and the metric/strategy config locations.

</details>

<details>
<summary><strong>Metrics YAML</strong></summary>

```yaml
metrics:
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
Entries wire directly into registries; unknown types or duplicate names raise immediately.

</details>

<details>
<summary><strong>Strategy YAML</strong></summary>

```yaml
strategy:
  name: threshold_reversion_strategy
  entry:
    engine: threshold_reversion
    params:
      threshold_pips: 10
      tp_pips: 10
      sl_pips: 20
      trade_timeout_seconds: 7200
    predicates:
      - metric: tick_rate_30s.tick_rate_per_min
        operator: "<"
        value: 200
  exit:
    name: default_exit
    predicates: []
```
Entry engines and predicates gate trade opens; exit predicates can force closures.

</details>

Need full schemas or extension guidance? See the [Configuration Guide](https://edwardclewer.github.io/tick_backtest/configs/).

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

## Repository Development

If you are working from a checkout rather than an installed package:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

Legacy repo scripts under `scripts/` still exist for internal development and CI coverage, but installed usage should go through `tick-backtest` or `tick_backtest.api`.

## Release Posture

The project is versioned for public releases starting at `0.1.0`. Tagged releases publish via GitHub Actions using staged TestPyPI then PyPI trusted publishing. See [docs/releasing.md](docs/releasing.md) and [CHANGELOG.md](CHANGELOG.md).

---

## Architecture Snapshot
- `config/` - versioned YAML templates validated before runtime.
- `src/tick_backtest/config_parsers/` - schema validation -> immutable dataclasses.
- `src/tick_backtest/data_feed/` - compiled tick loader with Python fallback; wrapped by `TickValidator`.
- `src/tick_backtest/backtest/` - `BacktestCoordinator` orchestrates per-pair runs; `Backtest` executes signals and positions.
- `src/tick_backtest/metrics/` - registries and indicator implementations (compiled with Python fallbacks).
- `src/tick_backtest/signals/` - predicate-aware entry/exit engines.
- `src/tick_backtest/analysis/` - reporting, stratification, and plotting utilities.
- `tests/` - unit, integration, and regression coverage across parsers, primitives, and pipeline stages.

**Data & validation flow**
1. Configs are parsed with forbid-by-default schemas (`config_validation/*`).
2. Tick feeds stream from Parquet; invalid ticks are skipped but logged.
3. Per-pair runs are isolated; errors are captured without aborting the batch.
4. Outputs, manifests, and environment snapshots land under `output/backtests/<RUN_ID>/`.

**Design Choice**: sequential execution avoids lookahead; scale comes from multi-pair orchestration and sweep automation.  
Dive deeper in the [Developer Notes](https://edwardclewer.github.io/tick_backtest/dev/internals/).

---

## Troubleshooting Essentials

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `ConfigError: unknown field ...` | Extra keys in YAML | Remove or rename; see [Configuration Guide](https://edwardclewer.github.io/tick_backtest/configs/). |
| `pyarrow` import error | Wheel missing | Install pinned version from `requirements.txt` and rerun. |
| Run finishes but no trades | Warmup consumed data or predicates blocked | Check `output/logs/<RUN_ID>.log` and entry predicates. |
| Manifest shows `missing_file` | `data_base_path` doesn’t match shard layout | Adjust path or supply expected Parquet shards. |
| Percentile metrics return `NaN` | Histogram warming up | Feed more ticks; expected during first few minutes. |

---

## Compatibility & Dependencies
- Python 3.12
- `numpy >= 1.26, < 3.0`
- `pandas >= 1.5, < 2.3`
- `pyarrow >= 10.0, < 16.0`
- `matplotlib >= 3.7, < 3.9`
- `pyyaml >= 6.0, < 6.1`

Running offline? Pre-install these wheels in your environment. Backtests abort if `pip freeze` fails (dependency snapshot is required).

---

## Testing & CI

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest
```

Coverage highlights:
- `tests/config_parsers` - YAML schema governance and regression checks.
- `tests/data_feed` - tick validation and resilience.
- `tests/metrics` - primitives plus indicator mathematics with reference helpers.
- `tests/integration/test_backtest_run.py` - end-to-end pipeline regression.

GitHub Actions builds wheels, runs tests, validates distribution metadata, and publishes docs via `.github/workflows/mkdocs.yml`.

---

## Extending the Stack
- **Add a metric** - create a dataclass under `metrics/dataclasses`, register it in `metrics/config_registry.py`, implement runtime logic. Validation blocks duplicates.
- **Add a signal engine** - add a class in `signals/entries`, register it in `ENTRY_ENGINE_REGISTRY`, and expose parameters in strategy YAML.
- **Support new data layouts** - extend `tick_backtest.data_feed` for alternative Parquet conventions; the validator enforces monotonic timestamps and finite spreads.

See the [Developer Notes](https://edwardclewer.github.io/tick_backtest/dev/internals/) for dependency maps, testing expectations, and release checklists.

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
