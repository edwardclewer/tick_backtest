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

# Test Suite

This directory holds the active pytest suite for the project. The tests cover config parsing, data-feed behaviour, backtest orchestration, package/API/CLI surface area, analytics workflows, and cython-backed primitives.

## Conventions
- Use `pytest` as the runner (`pytest.ini` configures strict markers and default paths).
- Organise tests by top-level package (`tests/backtest`, `tests/metrics`, etc.) to keep responsibilities clear.
- Prefer small, fixture-driven unit tests first; promote heavier cross-module flows into `tests/integration/`.
- Helper utilities shared between tests live under `tests/helpers/`.
- Keep repository fixtures deterministic so integration coverage stays stable across local runs and CI.

## Cython Primitive Smoke Tests

A dedicated suite under `tests/metrics/test_cython_primitives.py` exercises each cython-backed primitive on a small synthetic dataset. The goal is to ensure the compiled extensions behave identically to their Python fallbacks on supported build targets, so regressions surface quickly in CI.

## Sample Data Provenance

All fixtures under `tests/test_data` are generated from seeded Brownian-motion simulations rather than live-market recordings. They exist solely to exercise the pipeline deterministically and can be regenerated locally without relying on licensed or proprietary feeds. Update this section if you refresh the generator so downstream users understand exactly what the parquet shards contain.
