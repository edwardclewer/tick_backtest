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

# Contributing to Tick Backtest

Thanks for taking the time to contribute! This document explains how to propose changes, report bugs, and contribute new features.

## Getting Started

1. **Fork and clone** the repository.
2. Create a virtual environment (`python3.12 -m venv .venv && source .venv/bin/activate`).
3. Install dependencies and the package in editable mode:
   ```bash
   pip install -r requirements.txt
   pip install -e .[tests]
   ```
4. Run the test suite before submitting changes:
   ```bash
   PYTHONPATH=src pytest
   ```

## Reporting Issues

- Search existing issues before opening a new one.
- Include reproduction steps, expected vs. actual behavior, and relevant manifests/log snippets.
- For security-sensitive reports, follow the instructions in `SECURITY.md` instead of filing a public issue.

## Making Changes

- Create a topic branch (`git checkout -b feature/my-change`).
- Keep commits focused and descriptive.
- Update documentation when behavior or configuration options change.
- Add or update tests to cover your changes.

## Sample Data & Artefacts

The `tests/test_data` fixtures are generated from seeded Brownian-motion processes so the suite remains deterministic and license-free. Regenerate or extend them using the provided generators rather than copying real-market data.

## Pull Requests

- Ensure `pytest` and linting (if configured) pass locally.
- Fill out the pull request template, referencing any related issues.
- Be responsive to review feedback; we aim for collaborative, respectful discussions.

## Code of Conduct

By participating you agree to abide by the project's [Code of Conduct](CODE_OF_CONDUCT.md). Please report unacceptable behavior to the contact listed in `SECURITY.md`.

We appreciate every contribution—thanks for helping improve Tick Backtest!
