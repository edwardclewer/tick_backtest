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

# Releasing

This repository publishes Python packages via GitHub Actions using trusted publishing.

## Release posture

- Public releases follow semantic versioning.
- The first intentional public release line is `0.1.x`.
- `main` should stay releasable: CI green, `python -m build` green, and installed-wheel smoke tests passing.

## Config surfaces

- `src/tick_backtest/config/templates/` contains the public packaged templates exposed by `tick-backtest example-config`.
- `src/tick_backtest/demo_data/` contains the bundled public demo dataset used for the packaged example project.
- `config/` at repo root contains checkout-only development and CI configs. These are not part of the public installed template surface.

The CI workflow validates both sides:
- installed-package smoke tests exercise the public packaged templates and demo data
- repo smoke/golden scripts exercise the checkout-only configs

## Before tagging

1. Update `pyproject.toml` version.
2. Add a short entry to `CHANGELOG.md`.
3. Ensure local checks pass:
   ```bash
   source .venv/bin/activate
   rm -rf build dist
   python -m build
   python -m twine check dist/*
   pytest -q
   ```
4. Merge to `main`.

## Publishing flow

Publishing is handled by `.github/workflows/release.yml`.

1. Create and push a version tag such as `v0.1.0`.
2. The release workflow builds the sdist and wheel, then runs `twine check`.
3. The workflow publishes the artifacts to TestPyPI using the `testpypi` environment.
4. After TestPyPI succeeds, the `pypi` environment can approve and publish the same artifacts to PyPI.

This staged flow keeps TestPyPI and PyPI publication in one pipeline while still allowing a human approval gate before the production upload.

## Trusted publishing setup

Trusted publishing must be configured once in both indexes:

- PyPI project: `tick-backtest`
- TestPyPI project: `tick-backtest`
- Workflow file: `.github/workflows/release.yml`
- Repository: `edwardclewer/tick_backtest`

The GitHub environments expected by the workflow are:

- `testpypi`
- `pypi`

Set environment protection rules as desired. A common setup is:

- `testpypi`: no manual approval
- `pypi`: required reviewer approval

## After publishing

1. Verify installation from TestPyPI or PyPI in a clean environment.
2. Confirm the installed first-run path works:
   ```bash
   pip install tick-backtest
   tick-backtest example-config --output ./demo --include-demo-data
   tick-backtest run ./demo/backtest.yaml
   ```
3. Create a GitHub Release entry summarising the changelog highlights.
