#!/usr/bin/env bash
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

# Golden run: build confidence that two runs with the same config produce identical outputs.
# Assumes you've already activated your venv (package importable as `tick_backtest`).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---- config ----
CONFIG_PATH=${1:-config/backtest/test_backtest.yaml}
RUNS_ROOT="output/backtests"

# ---- preflight ----
if ! python -c "import tick_backtest" >/dev/null 2>&1; then
  echo "ERROR: 'tick_backtest' is not importable. Activate your venv or install the wheel." >&2
  exit 1
fi
[ -f "$CONFIG_PATH" ] || { echo "ERROR: config not found: $CONFIG_PATH" >&2; exit 1; }
mkdir -p "$RUNS_ROOT"

# ---- run twice using the library API ----
run_once() {
  python - <<'PY' "$CONFIG_PATH"
from tick_backtest.backtest.workflow import run_backtest
import sys
result = run_backtest(sys.argv[1])
run_root = result.get("run_root")
if not run_root:
    raise SystemExit("ERROR: run_backtest did not return run_root metadata")
print(run_root)
PY
}

RUN1="$(run_once)"
RUN2="$(run_once)"

for run_dir in "$RUN1" "$RUN2"; do
  if [ ! -d "$run_dir" ]; then
    echo "ERROR: run directory missing: $run_dir" >&2
    exit 1
  fi
done

echo "Comparing:"
echo "  RUN1: $RUN1"
echo "  RUN2: $RUN2"

# ---- compare artefacts in Python (cleaner hashing & checks) ----
python - <<'PY' "$RUN1" "$RUN2"
import sys, os, glob, json, hashlib
r1, r2 = sys.argv[1], sys.argv[2]

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

def sorted_trades(run_dir):
    # trades live at <run>/output/<PAIR>/trades.parquet
    paths = sorted(glob.glob(os.path.join(run_dir, "output", "*", "trades.parquet")))
    return paths

def combined_digest(paths):
    h = hashlib.sha256()
    for p in paths:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1<<20), b""):
                h.update(chunk)
    return h.hexdigest()

def pairs_from_fs(run_dir):
    return sorted({os.path.basename(os.path.dirname(p)) for p in sorted_trades(run_dir)})

def load_manifest(run_dir):
    with open(os.path.join(run_dir, "manifest.json"), "r", encoding="utf-8") as f:
        return json.load(f)

# Ensure manifests exist
for rd in (r1, r2):
    mf = os.path.join(rd, "manifest.json")
    if not os.path.isfile(mf):
        raise SystemExit(f"ERROR: missing manifest: {mf}")

t1, t2 = sorted_trades(r1), sorted_trades(r2)
if not t1 and not t2:
    print("NOTE: no trades in either run (stable no-trade outcome).")
else:
    if not t1 or not t2:
        raise SystemExit("GOLDEN FAIL: one run has trades.parquet while the other does not.")
    print("TRADES (counts):", len(t1), "vs", len(t2))
    if len(t1) != len(t2):
        raise SystemExit("GOLDEN FAIL: different number of per-pair trades files.")
    # Compare pair sets (FS-derived — avoids manifest schema drift)
    pset1, pset2 = pairs_from_fs(r1), pairs_from_fs(r2)
    print("PAIRS:", pset1, "vs", pset2)
    if pset1 != pset2:
        raise SystemExit("GOLDEN FAIL: pair sets differ between runs.")
    # Combined digest over all trades files (sorted for stability)
    d1, d2 = combined_digest(t1), combined_digest(t2)
    print("TRADES DIGEST:", d1)
    print("TRADES DIGEST:", d2)
    if d1 != d2:
        raise SystemExit("GOLDEN FAIL: trades.parquet bytes differ.")

# Optional: compare tick_validation exactly; warn only if it differs
m1, m2 = load_manifest(r1), load_manifest(r2)
tv1, tv2 = m1.get("tick_validation"), m2.get("tick_validation")
if isinstance(tv1, dict) and isinstance(tv2, dict) and tv1 != tv2:
    import pprint; print("WARN: tick_validation differs:\n", pprint.pformat({"run1": tv1, "run2": tv2}), file=sys.stderr)

print("GOLDEN: PASS")
PY
