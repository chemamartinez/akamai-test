# `/inputs/` Endpoint JSON Schema Reference

The HTTP endpoint `GET http://localhost:5066/inputs/` returns a JSON array of input metric objects, one per configured input. In this test setup, a single input is active at a time, so the array always has one element.

---

## CEL Input Sample Response

```json
[{
  "batch_processing_time": {
    "histogram": {
      "count": 18, "max": 644283583, "mean": 627206238.28, "median": 630032895.5,
      "min": 594735833, "p75": 635611604.5, "p95": 644283583, "p99": 644283583,
      "p999": 644283583, "stddev": 12479499.87
    }
  },
  "batches_published_total": 18,
  "batches_received_total": 18,
  "cel_executions": 19,
  "cel_processing_time": {
    "histogram": {
      "count": 18, "max": 2541287000, "mean": 2322709055.56, "median": 2306084500,
      "min": 2226291000, "p75": 2347596500, "p95": 2541287000, "p99": 2541287000,
      "p999": 2541287000, "stddev": 84317375.27
    }
  },
  "events_pipeline_filtered_total": 0,
  "events_pipeline_published_total": 180018,
  "events_pipeline_total": 180018,
  "events_published_total": 180018,
  "events_received_total": 180018,
  "http_request_body_bytes": { "histogram": { "count": 19, "max": 0, "mean": 0, "min": 0 } },
  "http_request_body_bytes_total": 0,
  "http_request_delete_total": 0,
  "http_request_errors_total": 0,
  "http_request_get_total": 19,
  "http_request_head_total": 0,
  "http_request_options_total": 0,
  "http_request_patch_total": 0,
  "http_request_post_total": 0,
  "http_request_put_total": 0,
  "http_request_total": 19,
  "http_response_1xx_total": 0,
  "http_response_2xx_total": 19,
  "http_response_3xx_total": 0,
  "http_response_4xx_total": 0,
  "http_response_5xx_total": 0,
  "http_response_body_bytes": { "histogram": { "count": 0, "max": 0, "mean": 0, "min": 0 } },
  "http_response_body_bytes_total": 0,
  "http_response_errors_total": 0,
  "http_response_total": 19,
  "http_round_trip_time": {
    "histogram": {
      "count": 19, "max": 494124416, "mean": 456261131.53, "median": 457030000,
      "min": 416102375, "p75": 469296167, "p95": 494124416, "p99": 494124416,
      "p999": 494124416, "stddev": 18054874.83
    }
  },
  "id": "796C8844D7CE98FE::https://example.akamai.com/siem/v1/configs/1",
  "input": "cel",
  "resource": "https://example.akamai.com/siem/v1/configs/1"
}]
```

### Key observations
- All histogram values are in **nanoseconds** — divide by 1,000,000 for milliseconds.
- `cel_executions: 19` vs `batches_received_total: 18` — one extra execution with zero events (initial check or `want_more` false).
- `http_request_total == cel_executions` — one HTTP call per CEL execution.
- `events_published_total == events_received_total` — no filtering or drops.

---

## Akamai Input Sample Response

```json
[{
  "akamai_requests_errors_total": 0,
  "akamai_requests_success_total": 57,
  "akamai_requests_total": 57,
  "api_400_fatal_total": 0,
  "batch_processing_time": {
    "histogram": {
      "count": 56, "max": 4346922917, "mean": 1014826327.45, "median": 894414270.5,
      "min": 841554292, "p75": 916422646.25, "p95": 1902619358.15, "p99": 4346922917,
      "p999": 4346922917, "stddev": 559789760.39
    }
  },
  "batches_published_total": 56,
  "batches_received_total": 56,
  "cursor_drops_total": 0,
  "errors_total": 0,
  "events_per_batch": {
    "histogram": {
      "count": 56, "max": 10000, "mean": 10000, "median": 10000,
      "min": 10000, "p75": 10000, "p95": 10000, "p99": 10000, "stddev": 0
    }
  },
  "events_pipeline_filtered_total": 0,
  "events_pipeline_published_total": 560453,
  "events_pipeline_total": 560454,
  "events_publish_failed_total": 0,
  "events_published_total": 560000,
  "events_received_total": 560000,
  "failed_events_per_page": { "histogram": { "count": 0, "max": 0, "mean": 0, "min": 0 } },
  "from_clamped_total": 0,
  "hmac_refresh_total": 0,
  "http_request_body_bytes": { "histogram": { "count": 57, "max": 0, "mean": 0, "min": 0 } },
  "http_request_body_bytes_total": 0,
  "http_request_delete_total": 0,
  "http_request_errors_total": 0,
  "http_request_get_total": 57,
  "http_request_head_total": 0,
  "http_request_options_total": 0,
  "http_request_patch_total": 0,
  "http_request_post_total": 0,
  "http_request_put_total": 0,
  "http_request_total": 57,
  "http_response_1xx_total": 0,
  "http_response_2xx_total": 57,
  "http_response_3xx_total": 0,
  "http_response_4xx_total": 0,
  "http_response_5xx_total": 0,
  "http_response_body_bytes": { "histogram": { "count": 0, "max": 0, "mean": 0, "min": 0 } },
  "http_response_body_bytes_total": 0,
  "http_response_errors_total": 0,
  "http_response_total": 57,
  "http_round_trip_time": {
    "histogram": {
      "count": 57, "max": 544886250, "mean": 457341853.23, "median": 455809125,
      "min": 422339250, "p75": 465425604, "p95": 512339262.5, "p99": 544886250,
      "p999": 544886250, "stddev": 21024545.09
    }
  },
  "id": "1A64BEC679FC34D5",
  "input": "akamai",
  "offset_expired_total": 0,
  "offset_ttl_drops_total": 0,
  "request_processing_time": {
    "histogram": { "count": 0, "max": 0, "mean": 0, "min": 0 }
  },
  "resource": "https://example.akamai.com/siem/v1/configs/1",
  "response_latency": {
    "histogram": {
      "count": 57, "max": 545061292, "mean": 457519189.32, "median": 455966417,
      "min": 422501250, "p75": 465584396, "p95": 512530629.4, "p99": 545061292,
      "p999": 545061292, "stddev": 21044808.12
    }
  },
  "worker_utilization": 0.69,
  "workers_active_gauge": 1
}]
```

### Key observations
- `akamai_requests_total: 57` includes one extra request for a trailing empty page (stream end detection).
- `batches_received_total: 56` = actual non-empty batches processed.
- `events_per_batch` histogram shows `mean: 10000` = every batch was at event_limit capacity, indicating the API has more events than we fetched per cycle (backlog present).
- `worker_utilization: 0.69` = workers were busy 69% of the time.
- `response_latency` ≈ `http_round_trip_time` — they measure the same underlying HTTP call, slightly different measurement points.

---

## Polling and Storage

Collection script: `bin/collect_input_metrics.sh`

```bash
# Starts 60 seconds into the run, then every 60 seconds
curl -sf --max-time 10 "http://localhost:5066/inputs/" -o "t0060.json"
curl -sf --max-time 10 "http://localhost:5066/inputs/" -o "t0120.json"
# ...
```

File naming: `t<elapsed_secs:04d>.json` where elapsed is the number of seconds since the run started. Lexicographic sort = chronological sort.

Since counters are cumulative, per-interval throughput is computed by subtracting consecutive snapshots:
```
events_in_interval_[60,120] = t0120.events_published_total - t0060.events_published_total
```
