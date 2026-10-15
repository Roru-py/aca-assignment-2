#!/usr/bin/env bash
set -Eeuo pipefail

# Run baseline (LRU L2) and Task 2A (I-RRIP) on all three traces.
# Run from the ChampSim repository root inside the Docker container.

BASELINE_BIN="bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline"
IRRIP_BIN="bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-irrip-lru-lru-lru-lru-1core-2a_final"

WARMUP=25000000
SIMULATION=25000000
RESULT_DIR="results_2a_comparison"

TRACES=("Trace1.gz" "Trace2.gz" "Trace3.gz")

for binary in "$BASELINE_BIN" "$IRRIP_BIN"; do
  if [[ ! -x "$binary" ]]; then
    echo "ERROR: Binary not found or not executable: $binary" >&2
    echo "Check the exact filename with: ls -1 bin/" >&2
    exit 1
  fi
done

mkdir -p "$RESULT_DIR"

for trace in "${TRACES[@]}"; do
  [[ -f "$trace" ]] || {
    echo "ERROR: Trace not found: $trace (expected in current directory)" >&2
    exit 1
  }
done

run_one() {
  local label="$1"
  local binary="$2"
  local trace="$3"
  local trace_name="${trace%.gz}"
  local output="${RESULT_DIR}/${label}_${trace_name}.txt"

  echo
  echo "============================================================"
  echo "Configuration: $label | Trace: $trace"
  echo "Output: $output"
  echo "============================================================"

  "$binary" \
    -warmup_instructions "$WARMUP" \
    -simulation_instructions "$SIMULATION" \
    -traces "./$trace" 2>&1 | tee "$output"

  echo "Saved: $output"
}

for trace in "${TRACES[@]}"; do
  run_one "baseline_LRU" "$BASELINE_BIN" "$trace"
done

for trace in "${TRACES[@]}"; do
  run_one "task2A_IRRIP" "$IRRIP_BIN" "$trace"
done

echo
echo "All six runs completed. Logs: $RESULT_DIR/"
