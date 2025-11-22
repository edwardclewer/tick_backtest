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

Welcome to the user documentation for the Tick Backtest Research Stack. This site explains how to run tick-level FX backtests, configure strategies and metrics, and interpret the generated artefacts.

## What You Can Do

- Run deterministic tick-level FX backtests from YAML configuration files.
- Combine compiled tick feeds, rolling indicators, and predicate-driven entry rules.
- Produce reproducible manifests, NDJSON logs, and trade-level analytics for every run.
- Generate post-run reports, equity curves, and metric stratification studies.

## How to Navigate

- New users should start with the [Quickstart](quickstart.md) to install dependencies and execute the sample run.
- Use [Configuration](configs.md) as a reference when editing backtest, metrics, or strategy YAML.
- [Analysis & Reporting](analysis.md) walks through the outputs stored under `output/backtests/<RUN_ID>/`.
- Developers can explore [Architecture](architecture.md) for a deeper look at the runtime flow and resilience features.
- Advanced implementation notes live under [Developer Notes](dev/internals.md); these are optional for end users.

## Getting Help

If you run into issues, review the troubleshooting sections embedded throughout the documentation or open a GitHub issue with run logs and manifests.
