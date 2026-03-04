#!/usr/bin/env bash
# run_tests.sh — Main orchestrator for the CEL vs Akamai Filebeat performance test suite.
#
# Runs Filebeat with CEL input, then Akamai input (or just one), collects all three
# metric types during each run, and invokes the Python comparison analysis.
#
# Usage: ./bin/run_tests.sh [OPTIONS]
# See README.md or run with --help for full option list.

set -euo pipefail

# ── Resolve script directory (works even when called from another directory) ──
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Defaults ──────────────────────────────────────────────────────────────────
DURATION="60m"
INTERVAL="5m"
INITIAL_INTERVAL="1h"
EVENT_LIMIT="10000"
AKAMAI_WORKERS="1"
AKAMAI_BATCH_SIZE="1000"
INPUT_TYPE="both"
RUN_NAME=""
API_EPS=""
FILEBEAT_BINARY="${SUITE_DIR}/../beats-akamai/x-pack/filebeat/filebeat"
AKAMAI_URL=""
CLIENT_TOKEN=""
CLIENT_SECRET=""
ACCESS_TOKEN=""

# ── Hardcoded API server constants (not Filebeat config) ──────────────────────
# These reflect characteristics of the Akamai SIEM test server environment.
# They are documented here for reproducibility, but not passed to Filebeat.
# All time values are in seconds (integer).
readonly API_OFFSET_TTL_S=120          # Offset token validity on API server (seconds)
readonly API_HMAC_VALIDITY_S=120       # HMAC auth signature timestamp validity window (seconds)

# ── Usage ─────────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Required:
  --akamai-url URL          Akamai API base URL (e.g. https://host.akamai.com)
  --client-token TOKEN      EdgeGrid client token
  --client-secret SECRET    EdgeGrid client secret
  --access-token TOKEN      EdgeGrid access token

Run control:
  --duration DURATION       How long each Filebeat run lasts. Default: ${DURATION}
                            Format: <N>m (minutes) or <N>s (seconds)
  --interval INTERVAL       Filebeat polling interval. Default: ${INTERVAL}
  --initial-interval INIT   Lookback window for first run. Default: ${INITIAL_INTERVAL}
  --event-limit LIMIT       Max events per API call. Default: ${EVENT_LIMIT}
  --akamai-workers N        Number of Akamai worker goroutines. Default: ${AKAMAI_WORKERS}
                            (Akamai input only)
  --akamai-batch-size N     Events per internal batch. Default: ${AKAMAI_BATCH_SIZE}
                            (Akamai input only)
  --input-type TYPE         Which inputs to test: cel | akamai | both. Default: ${INPUT_TYPE}
  --run-name NAME           Name for this test run. Default: ISO8601 timestamp
  --api-eps N               Expected API events per second (for result context). Optional.

Paths:
  --filebeat-binary PATH    Path to filebeat binary. Default: ${FILEBEAT_BINARY}

  --help                    Show this help message
EOF
    exit 0
}

# ── Parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --akamai-url)       AKAMAI_URL="$2";         shift 2 ;;
        --client-token)     CLIENT_TOKEN="$2";        shift 2 ;;
        --client-secret)    CLIENT_SECRET="$2";       shift 2 ;;
        --access-token)     ACCESS_TOKEN="$2";        shift 2 ;;
        --duration)         DURATION="$2";            shift 2 ;;
        --interval)         INTERVAL="$2";            shift 2 ;;
        --initial-interval) INITIAL_INTERVAL="$2";   shift 2 ;;
        --event-limit)      EVENT_LIMIT="$2";         shift 2 ;;
        --akamai-workers)   AKAMAI_WORKERS="$2";      shift 2 ;;
        --akamai-batch-size) AKAMAI_BATCH_SIZE="$2";  shift 2 ;;
        --input-type)       INPUT_TYPE="$2";          shift 2 ;;
        --run-name)         RUN_NAME="$2";            shift 2 ;;
        --api-eps)          API_EPS="$2";             shift 2 ;;
        --filebeat-binary)  FILEBEAT_BINARY="$2";     shift 2 ;;
        --help|-h)          usage ;;
        *)                  echo "Unknown option: $1" >&2; usage ;;
    esac
done

# ── Logging helpers ───────────────────────────────────────────────────────────
LOG_FILE=""  # Set after run dir is created

log() {
    local ts
    ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "[${ts}] $*"
    if [[ -n "${LOG_FILE}" ]]; then
        echo "[${ts}] $*" >> "${LOG_FILE}"
    fi
}

log_err() { log "ERROR: $*" >&2; }

# ── Validation ────────────────────────────────────────────────────────────────
errors=0
[[ -z "${AKAMAI_URL}" ]]     && { log_err "--akamai-url is required";     errors=$((errors + 1)); }
[[ -z "${CLIENT_TOKEN}" ]]   && { log_err "--client-token is required";   errors=$((errors + 1)); }
[[ -z "${CLIENT_SECRET}" ]]  && { log_err "--client-secret is required";  errors=$((errors + 1)); }
[[ -z "${ACCESS_TOKEN}" ]]   && { log_err "--access-token is required";   errors=$((errors + 1)); }
[[ "${INPUT_TYPE}" != "cel" && "${INPUT_TYPE}" != "akamai" && "${INPUT_TYPE}" != "both" ]] && \
    { log_err "--input-type must be cel, akamai, or both"; errors=$((errors + 1)); }

if [[ ! -f "${FILEBEAT_BINARY}" || ! -x "${FILEBEAT_BINARY}" ]]; then
    log_err "Filebeat binary not found or not executable: ${FILEBEAT_BINARY}"
    errors=$((errors + 1))
fi

if ! command -v go &>/dev/null; then
    log_err "'go' not found in PATH — required for pprof analysis"
    errors=$((errors + 1))
fi

if ! command -v python3 &>/dev/null; then
    log_err "'python3' not found in PATH — required for analysis"
    errors=$((errors + 1))
fi

[[ ${errors} -gt 0 ]] && exit 1

# ── Duration parsing ──────────────────────────────────────────────────────────
# Converts Xm or Xs strings to seconds for timing calculations.
parse_duration_secs() {
    local d="$1"
    if [[ "${d}" =~ ^([0-9]+)m$ ]]; then
        echo $(( BASH_REMATCH[1] * 60 ))
    elif [[ "${d}" =~ ^([0-9]+)s$ ]]; then
        echo "${BASH_REMATCH[1]}"
    elif [[ "${d}" =~ ^([0-9]+)h$ ]]; then
        echo $(( BASH_REMATCH[1] * 3600 ))
    else
        log_err "Cannot parse duration '${d}'. Use formats like 60m, 3600s, or 1h."
        exit 1
    fi
}

DURATION_SECS=$(parse_duration_secs "${DURATION}")

# ── Run directory setup ───────────────────────────────────────────────────────
if [[ -z "${RUN_NAME}" ]]; then
    RUN_NAME="$(date -u '+%Y-%m-%dT%H-%M-%S')"
fi

RUN_DIR="${SUITE_DIR}/runs/${RUN_NAME}"

for subdir in cel/logs cel/filebeat_output cel/input_metrics cel/pprof cel/analysis \
              akamai/logs akamai/filebeat_output akamai/input_metrics akamai/pprof akamai/analysis \
              comparison/plots; do
    mkdir -p "${RUN_DIR}/${subdir}"
done

LOG_FILE="${RUN_DIR}/run.log"
log "Test suite started"
log "Run directory: ${RUN_DIR}"

# ── Write run_config.json ─────────────────────────────────────────────────────
python3 - <<PYEOF
import json, os
config = {
    "run_name": "${RUN_NAME}",
    "started_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "parameters": {
        "duration": "${DURATION}",
        "duration_secs": ${DURATION_SECS},
        "interval": "${INTERVAL}",
        "initial_interval": "${INITIAL_INTERVAL}",
        "event_limit": "${EVENT_LIMIT}",
        "akamai_workers": "${AKAMAI_WORKERS}",
        "akamai_batch_size": "${AKAMAI_BATCH_SIZE}",
        "input_type": "${INPUT_TYPE}",
    },
    "api_constants": {
        "offset_ttl_s": ${API_OFFSET_TTL_S},
        "hmac_validity_s": ${API_HMAC_VALIDITY_S},
        "api_eps": ${API_EPS:-null},
    }
}
with open("${RUN_DIR}/run_config.json", "w") as f:
    json.dump(config, f, indent=2)
PYEOF

log "Wrote run_config.json"

# ── Compute pprof timing checkpoints ─────────────────────────────────────────
# See specs/PPROF_ANALYSIS.md for rationale.
PPROF_BASELINE_SECS=30
PPROF_CPU_DURATION_SECS=30
PPROF_CPU_END_SECS=$(( DURATION_SECS / 2 ))
PPROF_CPU_START_SECS=$(( PPROF_CPU_END_SECS - PPROF_CPU_DURATION_SECS ))
PPROF_FINAL_SECS=$(( DURATION_SECS - 15 ))

# Guard against durations too short for meaningful pprof collection
MIN_VIABLE_SECS=$(( PPROF_BASELINE_SECS + PPROF_CPU_DURATION_SECS + 15 + 10 ))
if [[ ${DURATION_SECS} -lt ${MIN_VIABLE_SECS} ]]; then
    log "WARNING: Duration ${DURATION} (${DURATION_SECS}s) is very short; pprof checkpoints may overlap"
fi

# ── Cleanup trap ──────────────────────────────────────────────────────────────
FILEBEAT_PID=""
METRICS_PID=""
PPROF_PID=""

cleanup() {
    log "Caught signal — cleaning up background processes..."
    [[ -n "${FILEBEAT_PID}" ]] && kill "${FILEBEAT_PID}" 2>/dev/null && log "Killed filebeat (${FILEBEAT_PID})"
    [[ -n "${METRICS_PID}" ]] && kill "${METRICS_PID}" 2>/dev/null && log "Killed metrics collector (${METRICS_PID})"
    [[ -n "${PPROF_PID}" ]]   && kill "${PPROF_PID}"   2>/dev/null && log "Killed pprof collector (${PPROF_PID})"
    exit 1
}
trap cleanup SIGINT SIGTERM

# ── Run a single input type ────────────────────────────────────────────────────
run_input() {
    local input_type="$1"   # "cel" or "akamai"
    local config_file="${SUITE_DIR}/configs/filebeat_${input_type}.yml"

    if [[ ! -f "${config_file}" ]]; then
        log_err "Config file not found: ${config_file}"
        return 1
    fi

    local run_subdir="${RUN_DIR}/${input_type}"
    local log_dir="${run_subdir}/logs"
    local output_dir="${run_subdir}/filebeat_output"
    local metrics_dir="${run_subdir}/input_metrics"
    local pprof_dir="${run_subdir}/pprof"

    log "─────────────────────────────────────────────────────"
    log "Starting $(echo "${input_type}" | tr '[:lower:]' '[:upper:]') input run"
    log "  Config:   ${config_file}"
    log "  Duration: ${DURATION} (${DURATION_SECS}s)"
    log "  Logs:     ${log_dir}"

    # Export Filebeat env vars
    export AKAMAI_URL="${AKAMAI_URL}"
    export AKAMAI_CLIENT_TOKEN="${CLIENT_TOKEN}"
    export AKAMAI_CLIENT_SECRET="${CLIENT_SECRET}"
    export AKAMAI_ACCESS_TOKEN="${ACCESS_TOKEN}"
    export INTERVAL="${INTERVAL}"
    export INITIAL_INTERVAL="${INITIAL_INTERVAL}"
    export EVENT_LIMIT="${EVENT_LIMIT}"
    export AKAMAI_WORKERS="${AKAMAI_WORKERS}"
    export AKAMAI_BATCH_SIZE="${AKAMAI_BATCH_SIZE}"
    export OUTPUT_DIR="${output_dir}"
    export LOG_DIR="${log_dir}"

    # Start input metrics collector
    "${SCRIPT_DIR}/collect_input_metrics.sh" \
        --output-dir "${metrics_dir}" \
        --duration-secs "${DURATION_SECS}" \
        >> "${RUN_DIR}/run.log" 2>&1 &
    METRICS_PID=$!
    log "Started input metrics collector (PID ${METRICS_PID})"

    # Start pprof collector
    "${SCRIPT_DIR}/collect_pprof.sh" \
        --output-dir "${pprof_dir}" \
        --baseline-secs "${PPROF_BASELINE_SECS}" \
        --cpu-start-secs "${PPROF_CPU_START_SECS}" \
        --cpu-duration-secs "${PPROF_CPU_DURATION_SECS}" \
        --final-secs "${PPROF_FINAL_SECS}" \
        >> "${RUN_DIR}/run.log" 2>&1 &
    PPROF_PID=$!
    log "Started pprof collector (PID ${PPROF_PID})"

    # Launch Filebeat with timeout
    log "Launching filebeat: timeout ${DURATION} ${FILEBEAT_BINARY} -c ${config_file}"
    timeout "${DURATION}" "${FILEBEAT_BINARY}" -c "${config_file}" \
        >> "${run_subdir}/logs/filebeat_stdout.log" 2>&1 &
    FILEBEAT_PID=$!
    log "Filebeat started (PID ${FILEBEAT_PID})"

    # Wait for filebeat to finish (timeout will send SIGTERM)
    local fb_exit=0
    wait "${FILEBEAT_PID}" || fb_exit=$?
    FILEBEAT_PID=""

    if [[ ${fb_exit} -eq 124 ]]; then
        log "Filebeat reached duration limit (timeout exit 124) — expected"
    elif [[ ${fb_exit} -eq 0 ]]; then
        log "Filebeat exited cleanly"
    else
        log "WARNING: Filebeat exited with code ${fb_exit}"
    fi

    # Give collectors a moment to flush, then stop them
    sleep 2
    [[ -n "${METRICS_PID}" ]] && { kill "${METRICS_PID}" 2>/dev/null || true; wait "${METRICS_PID}" 2>/dev/null || true; METRICS_PID=""; }
    [[ -n "${PPROF_PID}" ]]   && { kill "${PPROF_PID}"   2>/dev/null || true; wait "${PPROF_PID}"   2>/dev/null || true; PPROF_PID="";   }

    log "Completed $(echo "${input_type}" | tr '[:lower:]' '[:upper:]') input run"
    log "─────────────────────────────────────────────────────"
    return 0
}

# ── Execute runs ──────────────────────────────────────────────────────────────
CEL_OK=false
AKAMAI_OK=false

if [[ "${INPUT_TYPE}" == "cel" || "${INPUT_TYPE}" == "both" ]]; then
    if run_input "cel"; then
        CEL_OK=true
    else
        log "WARNING: CEL run failed — continuing"
    fi
fi

if [[ "${INPUT_TYPE}" == "akamai" || "${INPUT_TYPE}" == "both" ]]; then
    if run_input "akamai"; then
        AKAMAI_OK=true
    else
        log "WARNING: Akamai run failed — continuing"
    fi
fi

# ── Analysis phase ────────────────────────────────────────────────────────────
ANALYSIS_SCRIPT="${SUITE_DIR}/analysis/analyze.py"

if [[ ! -f "${ANALYSIS_SCRIPT}" ]]; then
    log "WARNING: Analysis script not found: ${ANALYSIS_SCRIPT} — skipping analysis"
else
    if ${CEL_OK}; then
        log "Running single-run analysis for CEL..."
        python3 "${ANALYSIS_SCRIPT}" single \
            --run-dir "${RUN_DIR}/cel/" \
            --input-type cel \
            --run-config "${RUN_DIR}/run_config.json" \
            >> "${RUN_DIR}/run.log" 2>&1 && log "CEL analysis complete" \
            || log "WARNING: CEL analysis failed"
    fi

    if ${AKAMAI_OK}; then
        log "Running single-run analysis for Akamai..."
        python3 "${ANALYSIS_SCRIPT}" single \
            --run-dir "${RUN_DIR}/akamai/" \
            --input-type akamai \
            --run-config "${RUN_DIR}/run_config.json" \
            >> "${RUN_DIR}/run.log" 2>&1 && log "Akamai analysis complete" \
            || log "WARNING: Akamai analysis failed"
    fi

    if ${CEL_OK} && ${AKAMAI_OK}; then
        log "Running comparison analysis..."
        python3 "${ANALYSIS_SCRIPT}" compare \
            --run-dir "${RUN_DIR}/" \
            --run-config "${RUN_DIR}/run_config.json" \
            >> "${RUN_DIR}/run.log" 2>&1 && log "Comparison analysis complete" \
            || log "WARNING: Comparison analysis failed"
    fi

    # ── Phase 6: AI analysis (optional) ───────────────────────────────────────
    if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
        if ${CEL_OK} && ${AKAMAI_OK}; then
            log "ANTHROPIC_API_KEY found — running AI-driven analysis..."
            python3 "${ANALYSIS_SCRIPT}" ai-analyze \
                --run-dir "${RUN_DIR}/" \
                --run-config "${RUN_DIR}/run_config.json" \
                >> "${RUN_DIR}/run.log" 2>&1 \
                && log "AI analysis complete: ${RUN_DIR}/comparison/final_analysis.md" \
                || log "WARNING: AI analysis failed (check run.log for details)"
        else
            log "Skipping AI analysis — requires both CEL and Akamai runs to complete"
        fi
    else
        log "Skipping AI analysis (ANTHROPIC_API_KEY not set)"
    fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
log "═══════════════════════════════════════════════════════"
log "Test suite finished"
log "Run directory: ${RUN_DIR}"
REPORT="${RUN_DIR}/comparison/comparison_report.md"
if [[ -f "${REPORT}" ]]; then
    log "Comparison report: ${REPORT}"
fi
AI_REPORT="${RUN_DIR}/comparison/final_analysis.md"
if [[ -f "${AI_REPORT}" ]]; then
    log "AI analysis report: ${AI_REPORT}"
fi
log "═══════════════════════════════════════════════════════"
