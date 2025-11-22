# Copyright 2025 Edward Clewer
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Prefer dedicated smoke venv, fall back to project venv
TARGET_VENV="${SMOKE_VENV:-.venv}"

if [ ! -d "$TARGET_VENV" ]; then
  echo "ERROR: virtualenv '$TARGET_VENV' not found. Create it first (e.g. python -m venv $TARGET_VENV && source $TARGET_VENV/bin/activate && pip install -e .[tests])." >&2
  exit 1
fi

source "$TARGET_VENV/bin/activate"

# Ensure package installs cleanly using existing build deps (no network)
if [ "${SKIP_SMOKE_INSTALL:-0}" != "1" ] && [ -d "src" ]; then
  python -m pip install --no-deps --no-build-isolation -e .
else
  echo "Skipping editable install (SKIP_SMOKE_INSTALL=${SKIP_SMOKE_INSTALL:-0}, src present=$([ -d src ] && echo yes || echo no))."
fi

# Import & quick tests
python -c "import tick_backtest; print('import OK')"
pytest -q  # or: pytest -q -k 'not slow'

# Tiny backtest (adjust config path as needed)
python - <<'PY'
from tick_backtest.backtest.workflow import run_backtest
meta = run_backtest("config/backtest/test_backtest.yaml")
print("run OK:", meta.get("run_id"))
PY
