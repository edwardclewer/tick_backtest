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

# Documentation & Code Style Guide

Use this guide when contributing to the Tick Backtest Research Stack or updating the documentation site.

## Code Style

- Follow the existing formatting conventions (PEP 8, type hints, descriptive logging).
- Do not remove or override user-provided configurations; prefer additive changes.
- Ensure new modules include focused unit tests; integration tests should remain deterministic.

## Documentation Workflow

1. Draft updates in Markdown under `docs/`.
2. Run `mkdocs serve` locally to preview changes.
3. Place contributor-/maintainer-focused material under `docs/dev/` to keep the main guides user-friendly.
4. Keep user-facing pages concise and task-oriented; link to deeper references when needed.

### Tooling

- Install doc dependencies via:
  ```bash
  pip install -r requirements-docs.txt
  ```
- Lint Markdown with `pre-commit run --all-files` (configure in `.pre-commit-config.yaml` if available).
- Build the static site with:
  ```bash
  mkdocs build --strict
  ```

## Content Guidelines

- Use admonitions (`!!! note`) for important callouts; keep tables for schema references.
- Embed diagrams using Mermaid when possible; store exported assets in `docs/_static/`.
- Cross-link between pages to avoid duplication (e.g., `configs.md` ↔ `analysis.md`).

## Release Checklist

- Update `mkdocs.yml` navigation if new pages are added.
- Regenerate screenshots or sample manifests when output format changes.
- Verify Quickstart instructions against the latest `requirements.txt`.
- Summarise documentation changes in the project changelog or release notes so external users can track updates.

Maintain this guide as your checklist for consistent documentation quality.
