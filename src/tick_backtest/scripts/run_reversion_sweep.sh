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

# Run backtests in parallel with matching metrics configs.
# Pairs:
#   config/backtest/sweeps/min0_tp6_sl6_timeout60.yaml
#   config/metrics/sweeps/reversion_30m_min0_tp6_sl6_timeout60.yaml
#
# Tunables (override via env):
#   MAX_JOBS                  # number of concurrent runs (auto-detected if unset)
#   BACKTEST_DIR=config/backtest/sweeps
#   METRICS_DIR=config/metrics/sweeps
#   METRICS_PREFIX=reversion_30m_
#   PYTHON=python3
#   MAIN=main.py
#   OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1  # clamp BLAS threads
#   METRICS_ARG=--metrics-config  # (optional) only if your main.py supports it; leave unset otherwise

set -euo pipefail
shopt -s nullglob

# ---------- Config ----------
BACKTEST_DIR="${BACKTEST_DIR:-config/backtest/sweeps}"
METRICS_DIR="${METRICS_DIR:-config/metrics/sweeps}"
METRICS_PREFIX="${METRICS_PREFIX:-reversion_30m_}"
PYTHON="${PYTHON:-python3}"
MAIN="${MAIN:-main.py}"

# Auto-detect MAX_JOBS if not set
if [[ -z "${MAX_JOBS:-}" ]]; then
  if command -v nproc >/dev/null 2>&1; then
    MAX_JOBS="$(nproc)"
  elif command -v sysctl >/dev/null 2>&1; then
    MAX_JOBS="$(sysctl -n hw.ncpu 2>/dev/null || echo 8)"
  else
    MAX_JOBS=8
  fi
fi
# Clamp to at least 1
if (( MAX_JOBS < 1 )); then MAX_JOBS=1; fi

# Clamp common threaded libs unless the user overrides.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

LOG_ROOT="logs/sweeps"
mkdir -p "$LOG_ROOT"

STATUS_FILE="$(mktemp -t sweep_status.XXXXXX)"

# ---------- Cleanup ----------
# On normal EXIT, only remove temp file. On SIGINT/SIGTERM, also kill the process group.
cleanup_exit() { rm -f "$STATUS_FILE"; }
cleanup_signal() { kill 0 2>/dev/null || true; rm -f "$STATUS_FILE"; exit 130; }
trap cleanup_exit EXIT
trap cleanup_signal INT TERM

# ---------- Status logging with optional flock ----------
append_status() {
  local line="$1"
  if command -v flock >/dev/null 2>&1; then
    { flock -x 9
      printf '%s\n' "$line" >&9
    } 9>>"$STATUS_FILE"
  else
    printf '%s\n' "$line" >>"$STATUS_FILE"
  fi
}

# ---------- One job ----------
run_one() {
  local bt="$1"
  local base label metrics log_dir start_ts end_ts rc dur

  base="$(basename "$bt")"
  label="${base%.yaml}"
  metrics="${METRICS_DIR}/${METRICS_PREFIX}${label}.yaml"

  if [[ ! -f "$metrics" ]]; then
    echo "[skip] $label — missing metrics: $metrics" >&2
    append_status "$(printf 'SKIP\t%s' "$label")"
    return 3
  fi

  log_dir="${LOG_ROOT}/${label}"
  mkdir -p "$log_dir"

  # Determine what to run:
  #  - If all outputs exist: skip
  #  - If some exist: run a filtered temp YAML containing only missing pairs
  #  - If none exist / can't parse: run original YAML
  local bt_to_run="$bt" tmp_cfg=""
  local py_out="" py_rc=0

  if py_out="$("$PYTHON" - "$bt" <<'PY' 2>/dev/null)"; then
    # Exit 0: all present -> skip (stdout unused)
    echo "[skip] $label — outputs present" >&2
    append_status "$(printf 'SKIP\t%s' "$label")"
    return 0
  else
    py_rc=$?
    if (( py_rc == 2 )); then
      # Partial: use filtered config path printed on stdout
      bt_to_run="$py_out"
      tmp_cfg="$py_out"
      echo "[partial] $label — running only missing pairs ($(basename "$bt_to_run"))"
    else
      # rc 1 or anything else: run original config
      bt_to_run="$bt"
    fi
  fi
  # ----- end decision -----

  echo "[start] $label"
  start_ts="$(date +%s)"

  # Build command
  local cmd=( "$PYTHON" "$MAIN" --config "$bt_to_run" )
  if [[ -n "${METRICS_ARG:-}" ]]; then
    cmd+=( "$METRICS_ARG" "$metrics" )
  fi

  # Run and log
  if "${cmd[@]}" >"$log_dir/stdout.log" 2>"$log_dir/stderr.log"; then
    rc=0
  else
    rc=$?
  fi

  # Clean up temp filtered config, if any
  if [[ -n "$tmp_cfg" && -f "$tmp_cfg" ]]; then
    rm -f -- "$tmp_cfg" || true
  fi

  end_ts="$(date +%s)"
  dur=$(( end_ts - start_ts ))

  if (( rc == 0 )); then
    echo "[ok]   $label (${dur}s)"
    append_status "$(printf 'OK\t%s\t%d' "$label" "$dur")"
  else
    echo "[fail] $label (exit $rc, ${dur}s) — tail stderr:" >&2
    tail -n 50 "$log_dir/stderr.log" >&2 || true
    append_status "$(printf 'FAIL\t%s\t%d\t%d' "$label" "$dur" "$rc")"
  fi

  return "$rc"
}

export -f run_one append_status
export STATUS_FILE LOG_ROOT PYTHON MAIN METRICS_DIR METRICS_PREFIX METRICS_ARG

# ---------- Discover & run ----------
# Keep NUL-delimited stream intact. If `sort -z` is unavailable (BSD/macOS), skip sorting.
if sort -z </dev/null >/dev/null 2>&1; then
  SORT_CMD=(sort -z)
else
  SORT_CMD=(cat)  # preserve -print0 stream
fi

set +e
find "$BACKTEST_DIR" -maxdepth 1 -type f -name '*.yaml' -print0 \
  | "${SORT_CMD[@]}" \
  | xargs -0 -n1 -P "$MAX_JOBS" bash -c 'run_one "$@"' _
xargs_rc=$?
set -e

# ---------- Summary ----------
echo
echo "Summary:"
awk -F'\t' '
  BEGIN{ ok=0; fail=0; skip=0; sumdur=0 }
  $1=="OK"   { ok++; sumdur+=$3 }
  $1=="FAIL" { fail++; sumdur+=$3; printf("  FAIL %s (rc=%s)\n", $2, $4) }
  $1=="SKIP" { skip++ }
  END{
    printf("  OK:   %d\n  FAIL: %d\n  SKIP: %d\n", ok, fail, skip);
  }
' "$STATUS_FILE" || true

# Exit non-zero if any task failed (so CI can catch it), but only after printing summary.
exit "$xargs_rc"
