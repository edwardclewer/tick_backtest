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

This repository is prepared to publish Python packages via GitHub Actions using trusted publishing.

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

## TestPyPI publishing flow

TestPyPI publishing is handled by `.github/workflows/testpypi-release.yml`.

1. Bump `pyproject.toml` to a version that has not already been uploaded to TestPyPI.
2. Create and push a tag such as `testpypi-v0.1.0`.
3. The workflow builds the sdist and wheel, then runs `twine check`.
4. The workflow publishes the artifacts to TestPyPI using GitHub OIDC trusted publishing and the `testpypi` environment.

The trigger is intentionally separate from future production tags so TestPyPI rehearsals do not imply a real PyPI release.
The TestPyPI workflow currently disables package attestations because TestPyPI attestation verification can reject otherwise valid trusted-publishing uploads. Revisit this when TestPyPI attestation support is stable enough for this project.

## Trusted publishing setup

Because the TestPyPI project does not exist yet, the first setup step is a pending Trusted Publisher on TestPyPI.

Create a pending Trusted Publisher with:

- Index: TestPyPI
- Project name: `tick-backtest`
- Owner: `edwardclewer`
- Repository: `tick_backtest`
- Workflow file: `testpypi-release.yml`
- Environment name: `testpypi`

This matches the workflow exactly:

- workflow filename: `.github/workflows/testpypi-release.yml`
- GitHub environment: `testpypi`
- publish job: `publish_testpypi`

The first successful trusted-publishing run will create the TestPyPI project automatically.

No API token, username, or password is used in the workflow.

You may optionally add GitHub environment protection rules to `testpypi`, but they are not required for the initial dry run.

## Future production PyPI

Real PyPI publishing is intentionally not implemented yet. Add that only after the TestPyPI flow has succeeded and the release posture is settled.

## After publishing

1. Verify installation from TestPyPI in a clean environment.
2. Confirm the installed first-run path works:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ tick-backtest
   tick-backtest example-config --output ./demo --include-demo-data
   tick-backtest run ./demo/backtest.yaml
   ```
3. Record any issues found before implementing the separate production PyPI workflow.
