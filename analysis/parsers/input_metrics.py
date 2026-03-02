"""
input_metrics.py — Parser for /inputs/ HTTP endpoint snapshot files.

During each Filebeat run, collect_input_metrics.sh polls `GET localhost:5066/inputs/`
every 60 seconds and saves the raw JSON array as t<elapsed>.json.

The /inputs/ endpoint returns CUMULATIVE counters (they accumulate from Filebeat
startup). Histograms are also cumulative over the run.

This module:
  - Loads all snapshot files in chronological order.
  - Computes per-interval deltas for counter fields.
  - Extracts histogram statistics (in milliseconds) from the final snapshot.
  - Returns a summary dict suitable for the analysis report.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


# Nanoseconds to milliseconds
NS_TO_MS = 1_000_000

# ── Field definitions ──────────────────────────────────────────────────────────

SHARED_COUNTER_FIELDS = [
    "batches_received_total",
    "batches_published_total",
    "events_received_total",
    "events_published_total",
    "http_request_total",
    "http_request_errors_total",
    "http_response_1xx_total",
    "http_response_2xx_total",
    "http_response_3xx_total",
    "http_response_4xx_total",
    "http_response_5xx_total",
    "http_response_errors_total",
]

SHARED_HISTOGRAM_FIELDS = [
    "batch_processing_time",
    "http_round_trip_time",
]

CEL_COUNTER_FIELDS = ["cel_executions"]
CEL_HISTOGRAM_FIELDS = ["cel_processing_time"]

AKAMAI_COUNTER_FIELDS = [
    "akamai_requests_total",
    "akamai_requests_success_total",
    "akamai_requests_errors_total",
    "offset_expired_total",
    "offset_ttl_drops_total",
    "hmac_refresh_total",
    "cursor_drops_total",
    "from_clamped_total",
    "api_400_fatal_total",
    "errors_total",
]
AKAMAI_GAUGE_FIELDS = ["workers_active_gauge", "worker_utilization"]
AKAMAI_HISTOGRAM_FIELDS = [
    "response_latency",
    "request_processing_time",
    "events_per_batch",
]


@dataclass
class InputMetricSnapshot:
    elapsed_secs: int
    raw: Dict[str, Any]
    input_type: str  # "cel" or "akamai"


def load_snapshots(input_metrics_dir: Path, input_type: str) -> List[InputMetricSnapshot]:
    """Load all t<elapsed>.json files in chronological order."""
    files = sorted(input_metrics_dir.glob("t*.json"))
    if not files:
        return []

    snapshots = []
    for f in files:
        stem = f.stem  # "t0060"
        try:
            elapsed = int(stem[1:])
        except ValueError:
            continue
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: Could not load {f}: {e}", file=sys.stderr)
            continue

        # /inputs/ returns a JSON array; take first element
        entry = data[0] if isinstance(data, list) and data else {}
        snapshots.append(InputMetricSnapshot(
            elapsed_secs=elapsed,
            raw=entry,
            input_type=input_type,
        ))

    return snapshots


def _hist_to_ms(entry: Dict[str, Any], field: str) -> Optional[Dict[str, Any]]:
    """Extract a histogram field and convert nanosecond values to milliseconds."""
    h = entry.get(field, {}).get('histogram')
    if not h:
        return None
    result = {}
    for key in ('count', 'mean', 'median', 'min', 'max', 'p75', 'p95', 'p99', 'p999', 'stddev'):
        v = h.get(key)
        if v is None:
            result[key] = None
        elif key == 'count':
            result[key] = int(v)
        else:
            result[key] = round(v / NS_TO_MS, 3)
    return result


def _hist_raw(entry: Dict[str, Any], field: str) -> Optional[Dict[str, Any]]:
    """Extract a histogram field without unit conversion (for count-based metrics)."""
    h = entry.get(field, {}).get('histogram')
    if not h:
        return None
    result = {}
    for key in ('count', 'mean', 'median', 'min', 'max', 'p75', 'p95', 'p99', 'p999', 'stddev'):
        v = h.get(key)
        if v is None:
            result[key] = None
        elif key == 'count':
            result[key] = int(v)
        else:
            result[key] = round(float(v), 3)
    return result


def compute_deltas(snapshots: List[InputMetricSnapshot], input_type: str) -> List[Dict[str, Any]]:
    """
    Compute per-interval counter deltas between consecutive snapshots.

    Returns a list of dicts, one per interval (starting from the second snapshot).
    Each dict contains the elapsed_secs, interval duration, and delta values.
    """
    if len(snapshots) < 2:
        return []

    counter_fields = (
        SHARED_COUNTER_FIELDS
        + (CEL_COUNTER_FIELDS if input_type == "cel" else [])
        + (AKAMAI_COUNTER_FIELDS if input_type == "akamai" else [])
    )

    deltas = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1].raw
        curr = snapshots[i].raw
        interval_s = snapshots[i].elapsed_secs - snapshots[i - 1].elapsed_secs
        row: Dict[str, Any] = {
            "elapsed_secs": snapshots[i].elapsed_secs,
            "interval_secs": interval_s,
        }
        for f in counter_fields:
            c = curr.get(f)
            p = prev.get(f)
            if c is not None and p is not None:
                row[f"{f}_delta"] = c - p
        deltas.append(row)

    return deltas


def summarize(snapshots: List[InputMetricSnapshot], input_type: str) -> Dict[str, Any]:
    """
    Produce a summary dict from a list of snapshots.

    Uses the FINAL snapshot for cumulative counters and histograms.
    Uses per-interval deltas for throughput calculations.
    """
    if not snapshots:
        return {"error": "no_input_metric_snapshots"}

    final = snapshots[-1].raw
    first = snapshots[0].raw

    # Elapsed time in seconds (from first to last snapshot)
    elapsed_s = snapshots[-1].elapsed_secs - snapshots[0].elapsed_secs if len(snapshots) > 1 else 0

    def counter(field: str) -> Optional[int]:
        v = final.get(field)
        return int(v) if v is not None else None

    def gauge(field: str) -> Optional[float]:
        v = final.get(field)
        return float(v) if v is not None else None

    # Throughput
    total_events = counter("events_published_total") or 0
    total_requests = counter("http_request_total") or 0
    total_2xx = counter("http_response_2xx_total") or 0
    total_req_errors = counter("http_request_errors_total") or 0
    success_rate = (total_2xx / total_requests * 100) if total_requests else None

    result: Dict[str, Any] = {
        "input_type": input_type,
        "snapshots_count": len(snapshots),
        "elapsed_secs": snapshots[-1].elapsed_secs,
        "throughput": {
            "total_events_published": total_events,
            "total_events_received": counter("events_received_total"),
            "total_batches_published": counter("batches_published_total"),
            "total_http_requests": total_requests,
            "http_2xx_total": total_2xx,
            "http_errors_total": total_req_errors,
            "http_success_rate_pct": round(success_rate, 2) if success_rate is not None else None,
        },
        "histograms": {
            "batch_processing_time_ms": _hist_to_ms(final, "batch_processing_time"),
            "http_round_trip_time_ms": _hist_to_ms(final, "http_round_trip_time"),
        },
    }

    # CEL-specific fields
    if input_type == "cel":
        result["cel"] = {
            "cel_executions": counter("cel_executions"),
        }
        result["histograms"]["cel_processing_time_ms"] = _hist_to_ms(final, "cel_processing_time")

    # Akamai-specific fields
    if input_type == "akamai":
        result["akamai"] = {
            "akamai_requests_total": counter("akamai_requests_total"),
            "akamai_requests_success": counter("akamai_requests_success_total"),
            "akamai_requests_errors": counter("akamai_requests_errors_total"),
            "offset_expired_total": counter("offset_expired_total"),
            "offset_ttl_drops_total": counter("offset_ttl_drops_total"),
            "hmac_refresh_total": counter("hmac_refresh_total"),
            "cursor_drops_total": counter("cursor_drops_total"),
            "from_clamped_total": counter("from_clamped_total"),
            "api_400_fatal_total": counter("api_400_fatal_total"),
            "errors_total": counter("errors_total"),
            "workers_active_gauge": gauge("workers_active_gauge"),
            "worker_utilization": gauge("worker_utilization"),
        }
        result["histograms"]["response_latency_ms"] = _hist_to_ms(final, "response_latency")
        result["histograms"]["request_processing_time_ms"] = _hist_to_ms(final, "request_processing_time")
        result["histograms"]["events_per_batch"] = _hist_raw(final, "events_per_batch")

    # Reliability issues
    issues = []
    if total_req_errors > 0:
        issues.append(f"http_request_errors: {total_req_errors}")
    if input_type == "akamai":
        akamai = result.get("akamai", {})
        if akamai.get("offset_expired_total", 0):
            issues.append(f"offset_expired: {akamai['offset_expired_total']} — offset expired (416)")
        if akamai.get("hmac_refresh_total", 0):
            issues.append(f"hmac_refresh: {akamai['hmac_refresh_total']} — HMAC clock-skew retries")
        if akamai.get("cursor_drops_total", 0):
            issues.append(f"cursor_drops: {akamai['cursor_drops_total']} — offset cleared, window replayed")
        if akamai.get("api_400_fatal_total", 0):
            issues.append(f"api_400_fatal: {akamai['api_400_fatal_total']} — non-recoverable 400 errors")

    result["issues"] = issues
    return result
