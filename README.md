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

# Tick Backtest Research Stack

*Deterministic tick-level FX backtesting for reproducible research.*

Tick Backtest is a configuration-first Python 3.12 toolkit for running reproducible FX strategy research. You provide Parquet ticks and YAML configs; the stack validates every setting, executes deterministic backtests, and writes manifests, logs, and analysis reports you can trust.

### Highlights
- **Performance:** ~8 million ticks/minute/core on AMD 5950X (Parquet → metrics → signals → trades)
- **Deterministic runs:** Deterministic runs: config, git hash, dependency snapshot, and shard hashes captured per run
- **Resilient pipelines:** Resilient pipelines: per-pair failure isolation, tick validation, and structured telemetry
- **Declarative research:** Declarative research: swap YAML configs instead of editing code
- **Report ready:** Report ready: trade tables, Markdown summaries, metric stratification CSV/PNG artefacts

👉 Looking for configuration docs or developer notes? Visit the [Documentation Site](docs/index.md).

---

## Quickstart (5 minutes)

1. **Install prerequisites**
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Point the sample config at your data**
   ```yaml
   # config/backtest/default_backtest.yaml
   schema_version: "1.0"
   pairs: [EURUSD]
   start: 2012-02
   end: 2013-02
   data_base_path: "/abs/path/to/dukascopy_data/"
   output_base_path: "/abs/path/to/tick_backtest/output/backtests/"
   ```

3. **Run the backtest**
   ```bash
   PYTHONPATH=src python scripts/run_backtest.py \
     --config config/backtest/default_backtest.yaml
   ```
   or from Python:
   ```python
   from tick_backtest.backtest.workflow import run_backtest
   result = run_backtest("config/backtest/default_backtest.yaml")
   print(result["output_dir"])
   ```

4. **Inspect outputs** at `output/backtests/<RUN_ID>/`

   | Path | Purpose |
   | --- | --- |
   | `manifest.json` | Immutable run snapshot (configs, git hash, shard hashes, status). |
   | `output/logs/<RUN_ID>.log` | Structured NDJSON log with validation summaries and errors. |
   | `output/<PAIR>/trades.parquet` | Trade-level dataset including metrics and PnL. |
   | `output/<PAIR>/analysis/report.md` | Markdown analysis summary with equity plots. |
   | `configs/*.yaml` | Copies of backtest/metrics/strategy configs with SHA256 digests. |

---

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

🔗 Need full schemas or extension guidance? See the [Configuration Guide](docs/configs.md).

---

## Script, CLI & Analysis Helpers

| Task | Command / Call | Notes |
| --- | --- | --- |
| Run backtest (CLI) | `PYTHONPATH=src python scripts/run_backtest.py --config config/backtest/default_backtest.yaml` | `--output-root`, `--log-level`, `--profile` available (`--help` for full list). |
| Run backtest (Python) | `run_backtest("config/backtest/default_backtest.yaml", output_root="...")` | Returns a metadata dict including manifest path and output dir. |
| Backtest analysis | `tick_backtest.analysis.run_backtest_analysis(output_dir, run_id=...)` | Produces Markdown reports + equity curves per pair. |
| Metric stratification | `tick_backtest.analysis.run_metric_stratification_analysis(output_dir, run_id=...)` | Expectancy by metric bins (CSV/PNG/Markdown). |
| Single trade analysis | `tick_backtest.analysis.run_trade_analysis(".../trades.parquet", output_dir=...)` | Quick inspection for a single pair. |

Helpers log warnings rather than failing runs; review `output/logs/<RUN_ID>.log` to diagnose skipped artefacts.

---

## Architecture Snapshot
- `config/` – versioned YAML templates validated before runtime.
- `src/tick_backtest/config_parsers/` – schema validation → immutable dataclasses.
- `src/tick_backtest/data_feed/` – compiled tick loader with Python fallback; wrapped by `TickValidator`.
- `src/tick_backtest/backtest/` – `BacktestCoordinator` orchestrates per-pair runs; `Backtest` executes signals and positions.
- `src/tick_backtest/metrics/` – registries and indicator implementations (compiled with Python fallbacks).
- `src/tick_backtest/signals/` – predicate-aware entry/exit engines.
- `src/tick_backtest/analysis/` – reporting, stratification, and plotting utilities.
- `tests/` – unit, integration, and regression coverage across parsers, primitives, and pipeline stages.

**Data & validation flow**
1. Configs are parsed with forbid-by-default schemas (`config_validation/*`).
2. Tick feeds stream from Parquet; invalid ticks are skipped but logged.
3. Per-pair runs are isolated; errors are captured without aborting the batch.
4. Outputs, manifests, and environment snapshots land under `output/backtests/<RUN_ID>/`.

⚙️ **Performance**: ~8 million ticks/minute/core on AMD 5950X (vectorised Parquet loading, sequential signal loop for causal correctness).  
💡 **Design Choice**: sequential execution avoids lookahead; scale comes from multi-pair orchestration and sweep automation.  
🔗 Dive deeper in the [Developer Notes](docs/dev/internals.md).

---

## Troubleshooting Essentials

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `ConfigError: unknown field ...` | Extra keys in YAML | Remove or rename; see [Configuration Guide](docs/configs.md). |
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
PYTHONPATH=src pytest
```

Coverage highlights:
- `tests/config_parsers` – YAML schema governance & regression checks.
- `tests/data_feed` – tick validation and resilience.
- `tests/metrics` – primitives plus indicator mathematics with reference helpers.
- `tests/integration/test_backtest_run.py` – end-to-end pipeline regression.

GitHub Actions builds wheels, runs tests, executes optional golden backtests, and publishes docs via `.github/workflows/mkdocs.yml`.

---

## Extending the Stack
- **Add a metric** – create a dataclass under `metrics/dataclasses`, register it in `metrics/config_registry.py`, implement runtime logic. Validation blocks duplicates.
- **Add a signal engine** – add a class in `signals/entries`, register it in `ENTRY_ENGINE_REGISTRY`, and expose parameters in strategy YAML.
- **Support new data layouts** – extend `tick_backtest.data_feed` for alternative Parquet conventions; the validator enforces monotonic timestamps and finite spreads.

🔗 See the [Developer Notes](docs/dev/internals.md) for dependency maps, testing expectations, and release checklists.

---

## Next Steps
1. Run the sample backtest and inspect the generated manifest/logs.
2. Tailor metrics and strategy configs to your research question.
3. Explore the [documentation](docs/index.md) for advanced configuration, analysis tooling, and developer internals.

## Sample Data & Reports
- Synthetic fixtures under `tests/test_data/` are generated from seeded Brownian-motion processes. They exist solely to exercise the pipeline deterministically without bundling proprietary market data.
- Sample equity curves and report snippets referenced throughout the docs were produced from those synthetic runs; regenerate them locally via `scripts/run_backtest.py` + `scripts/run_metric_stratification.py` before updating screenshots.

### Local overrides
Copy the `.example` configs under `config/**/local_default_*.yaml.example` to files without the `.example` suffix (e.g., `config/backtest/local_default_backtest.yaml`) and update them with your private paths or strategy tweaks. These files are gitignored so you can point `run_backtest` at them without leaking private settings.

---

**Author**: Edward Clewer  
**License**: Apache License 2.0  
**Docs**: [Docs](https://caffeinebean.github.io/tick_backtest/)  
