# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog and the project uses semantic versioning for public releases.

## [0.1.0] - 2026-04-03

### Added
- Public `tick-backtest` CLI entry points for `run`, `report`, `analyze`, and `example-config`.
- Packaged demo templates and bundled demo parquet data for a first-run installed workflow.
- Installed-package CI smoke coverage for the public CLI surface.
- GitHub Actions release workflow for staged TestPyPI then PyPI publication.

### Changed
- Standard `python -m build` now succeeds alongside the existing no-isolation compiled-extension CI checks.
- Public packaging metadata now includes project URLs, classifiers, and an explicit `0.1.0` first public release posture.
- Distributed package data is now limited to public templates and demo data; repo-only configs remain checkout-only.
