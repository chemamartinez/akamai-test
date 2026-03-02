#!/usr/bin/env bash
# collect_pprof.sh — Collects pprof profiles from Filebeat at timed checkpoints.
#
# Collection strategy (see specs/PPROF_ANALYSIS.md for rationale):
#   1. Baseline heap at run start  (~30s in)
#   2. 30-second CPU profile       (centered around run midpoint)
#   3. Final heap, block, mutex    (~15s before run end)
#
# The script is started at the same moment as Filebeat, so elapsed time in this
# script approximates elapsed time in the Filebeat run.
#
# Designed to be launched as a background process by run_tests.sh.

set -euo pipefail

PPROF_BASE_URL="http://localhost:5066/debug/pprof"
OUTPUT_DIR=""
BASELINE_SECS=30
CPU_START_SECS=""
CPU_DURATION_SECS=30
FINAL_SECS=""

usage() {
    cat <<EOF
Usage: $(basename "$0") OPTIONS

  --output-dir DIR          Directory to write .pprof files into
  --baseline-secs N         Seconds after start to capture heap baseline (default: 30)
  --cpu-start-secs N        Seconds after start to begin CPU profile collection
  --cpu-duration-secs N     Duration of CPU profile in seconds (default: 30)
  --final-secs N            Seconds after start to capture final profiles
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)         OUTPUT_DIR="$2";        shift 2 ;;
        --baseline-secs)      BASELINE_SECS="$2";     shift 2 ;;
        --cpu-start-secs)     CPU_START_SECS="$2";    shift 2 ;;
        --cpu-duration-secs)  CPU_DURATION_SECS="$2"; shift 2 ;;
        --final-secs)         FINAL_SECS="$2";        shift 2 ;;
        --help|-h)            usage ;;
        *)  echo "Unknown option: $1" >&2; usage ;;
    esac
done

[[ -z "${OUTPUT_DIR}" ]]      && { echo "ERROR: --output-dir is required" >&2; exit 1; }
[[ -z "${CPU_START_SECS}" ]]  && { echo "ERROR: --cpu-start-secs is required" >&2; exit 1; }
[[ -z "${FINAL_SECS}" ]]      && { echo "ERROR: --final-secs is required" >&2; exit 1; }

mkdir -p "${OUTPUT_DIR}"

COLLECTION_LOG="${OUTPUT_DIR}/pprof_collection.log"

log() {
    local msg="[$(date -u '+%H:%M:%S')] [pprof] $*"
    echo "${msg}"
    echo "${msg}" >> "${COLLECTION_LOG}"
}

fetch_profile() {
    local name="$1"
    local url="$2"
    local outfile="${OUTPUT_DIR}/${name}"
    local max_time="${3:-30}"

    log "Fetching ${name} from ${url}"
    if curl -sf --max-time "${max_time}" "${url}" -o "${outfile}"; then
        local size
        size=$(wc -c < "${outfile}")
        log "Saved ${name} (${size} bytes)"
        return 0
    else
        log "WARNING: Failed to fetch ${name} from ${url}"
        rm -f "${outfile}" 2>/dev/null || true
        return 1
    fi
}

log "Starting pprof collection"
log "  Output dir:      ${OUTPUT_DIR}"
log "  Baseline at:     ${BASELINE_SECS}s"
log "  CPU start at:    ${CPU_START_SECS}s (${CPU_DURATION_SECS}s duration)"
log "  Final at:        ${FINAL_SECS}s"

# ── Phase 1: Baseline heap ────────────────────────────────────────────────────
log "Waiting ${BASELINE_SECS}s for baseline checkpoint..."
sleep "${BASELINE_SECS}"

fetch_profile "heap_baseline.pprof" "${PPROF_BASE_URL}/heap" || true

# ── Phase 2: CPU profile at midpoint ─────────────────────────────────────────
CPU_WAIT=$(( CPU_START_SECS - BASELINE_SECS ))
if [[ ${CPU_WAIT} -gt 0 ]]; then
    log "Waiting ${CPU_WAIT}s until CPU profile start checkpoint..."
    sleep "${CPU_WAIT}"
fi

# curl blocks for CPU_DURATION_SECS while the profile is collected server-side
CPU_CURL_TIMEOUT=$(( CPU_DURATION_SECS + 10 ))
fetch_profile "cpu_midpoint.pprof" \
    "${PPROF_BASE_URL}/profile?seconds=${CPU_DURATION_SECS}" \
    "${CPU_CURL_TIMEOUT}" || true

# ── Phase 3: Final profiles ───────────────────────────────────────────────────
CPU_END_SECS=$(( CPU_START_SECS + CPU_DURATION_SECS ))
FINAL_WAIT=$(( FINAL_SECS - CPU_END_SECS ))
if [[ ${FINAL_WAIT} -gt 0 ]]; then
    log "Waiting ${FINAL_WAIT}s until final checkpoint..."
    sleep "${FINAL_WAIT}"
elif [[ ${FINAL_WAIT} -lt 0 ]]; then
    log "WARNING: Final checkpoint already past — collecting immediately"
fi

fetch_profile "heap_final.pprof"  "${PPROF_BASE_URL}/heap"  || true
fetch_profile "block_final.pprof" "${PPROF_BASE_URL}/block" || true
fetch_profile "mutex_final.pprof" "${PPROF_BASE_URL}/mutex" || true

log "pprof collection finished"
