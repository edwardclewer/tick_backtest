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

# Test Suite Scaffolding

This directory holds the pytest-based test harness. The current files are placeholders that outline the intended coverage areas without implementing assertions yet. Each module-level skip marker documents the scenarios we plan to exercise once the synthetic fixtures and assertions are ready.

## Conventions
- Use `pytest` as the runner (`pytest.ini` configures strict markers and default paths).
- Organise tests by top-level package (`tests/backtest`, `tests/metrics`, etc.) to keep responsibilities clear.
- Prefer small, fixture-driven unit tests first; promote heavier cross-module flows into `tests/integration/`.
- Helper utilities shared between tests live under `tests/helpers/`.

When adding real tests, remove the `pytestmark = pytest.mark.skip(...)` lines and fill in the skeleton functions with assertions.

## Cython Primitive Smoke Tests

A dedicated suite under `tests/metrics/test_cython_primitives.py` exercises each cython-backed primitive on a small synthetic dataset. The goal is to ensure the compiled extensions behave identically to their Python fallbacks across platforms, so that regressions surface quickly in CI.

## Sample Data Provenance

All fixtures under `tests/test_data` are generated from seeded Brownian-motion simulations rather than live-market recordings. They exist solely to exercise the pipeline deterministically and can be regenerated locally without relying on licensed or proprietary feeds. Update this section if you refresh the generator so downstream users understand exactly what the parquet shards contain.
