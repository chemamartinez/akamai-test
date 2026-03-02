#!/usr/bin/env bash
# collect_input_metrics.sh — Polls the Filebeat /inputs/ HTTP endpoint every 60 seconds
# and saves each response as a timestamped JSON file.
#
# Designed to be launched as a background process by run_tests.sh.
# It runs until the specified duration has elapsed, then exits on its own.
#
# Files are named t<ELAPSED_SECS:04d>.json (e.g. t0060.json, t0120.json) so that
# lexicographic order equals chronological order.
#
# The /inputs/ endpoint returns CUMULATIVE counters. The analysis script computes
# deltas by subtracting consecutive snapshots.

set -euo pipefail

ENDPOINT="http://localhost:5066/inputs/"
POLL_INTERVAL=60
OUTPUT_DIR=""
DURATION_SECS=""

usage() {
    cat <<EOF
Usage: $(basename "$0") --output-dir DIR --duration-secs N

  --output-dir DIR    Directory to write t<elapsed>.json files into
  --duration-secs N   Total run duration in seconds; script exits after this
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)     OUTPUT_DIR="$2";     shift 2 ;;
        --duration-secs)  DURATION_SECS="$2";  shift 2 ;;
        --help|-h)        usage ;;
        *)  echo "Unknown option: $1" >&2; usage ;;
    esac
done

[[ -z "${OUTPUT_DIR}" ]]    && { echo "ERROR: --output-dir is required" >&2; exit 1; }
[[ -z "${DURATION_SECS}" ]] && { echo "ERROR: --duration-secs is required" >&2; exit 1; }

mkdir -p "${OUTPUT_DIR}"

log() {
    echo "[$(date -u '+%H:%M:%S')] [input-metrics] $*"
}

log "Starting input metrics collection"
log "  Endpoint:    ${ENDPOINT}"
log "  Output dir:  ${OUTPUT_DIR}"
log "  Duration:    ${DURATION_SECS}s"
log "  Poll every:  ${POLL_INTERVAL}s"

ELAPSED=0

while [[ ${ELAPSED} -lt ${DURATION_SECS} ]]; do
    sleep "${POLL_INTERVAL}"
    ELAPSED=$(( ELAPSED + POLL_INTERVAL ))

    FILENAME="$(printf 't%04d.json' ${ELAPSED})"
    OUTFILE="${OUTPUT_DIR}/${FILENAME}"

    if curl -sf --max-time 10 "${ENDPOINT}" -o "${OUTFILE}"; then
        # Validate it is non-empty JSON before keeping it
        if python3 -c "import json,sys; json.load(open('${OUTFILE}'))" 2>/dev/null; then
            log "Saved ${FILENAME}"
        else
            log "WARNING: Response at ${ELAPSED}s was not valid JSON — removing ${FILENAME}"
            rm -f "${OUTFILE}"
        fi
    else
        log "WARNING: curl failed at elapsed=${ELAPSED}s (filebeat may not be ready yet)"
        rm -f "${OUTFILE}" 2>/dev/null || true
    fi
done

log "Input metrics collection finished (${ELAPSED}s elapsed)"
