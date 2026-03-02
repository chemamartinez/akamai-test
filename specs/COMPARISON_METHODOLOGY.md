# Comparison Methodology

How the CEL vs Akamai comparison is structured, what is directly comparable, and how to interpret differences.

---

## Test Design

Both runs use **identical Filebeat parameters**:

| Parameter | Source |
|-----------|--------|
| `--interval` | CLI argument |
| `--initial-interval` | CLI argument |
| `--event-limit` | CLI argument |
| `--duration` | CLI argument |
| Auth credentials | CLI arguments |

The runs are **sequential** (CEL first, then Akamai). This means:
- Minor differences in API server state may exist between runs.
- Network conditions may fluctuate.
- The second run (Akamai) starts from a fresh offset (initial_interval lookback), same as CEL.

For rigorous comparison, run multiple tests and average results.

---

## Hardcoded API Server Constants

These parameters reflect the Akamai SIEM test server environment and are not configurable per test. They are documented here for reproducibility.

| Constant | Value | Description |
|----------|-------|-------------|
| `offset_ttl` | 120s | How long the API server keeps an offset valid. If Filebeat does not use the offset within 120 seconds, the server expires it and returns 416. The Akamai input handles this via `offset_ttl: 120s`. The CEL input handles it via recovery mode in the CEL program. |
| HMAC validity | 120s | Auth signature timestamp validity window (server-side). The API rejects requests whose timestamp deviates from server time by more than 120s. The Akamai input auto-retries on clock-skew errors (`invalid_timestamp_retry.max_attempts: 2`) and tracks retries via `hmac_refresh_total`. |
| API EPS target | Varies | Rate at which the test server delivers events. Not directly configurable from the client side. |

---

## Directly Comparable Metrics

These metrics have **identical semantics** in both input types and can be directly compared:

| Metric | Source | Notes |
|--------|--------|-------|
| `http_round_trip_time` | `/inputs/` | Purely the HTTP call duration (network + API server). Same request/response pattern. |
| `batch_processing_time` | `/inputs/` | Time from batch receipt to pipeline ACK. Both inputs publish to the same pipeline. A higher value means publishing to the pipeline is taking longer (or the pipeline is congested). |
| All monitoring log metrics | log files | CPU, memory, RSS, goroutines, queue fill, pipeline events — all measured identically regardless of input type. |
| pprof profiles | HTTP endpoint | Same collection methodology, same analysis tooling. |

---

## Input-Type-Specific Metrics and Interpretation

### CEL: `cel_processing_time`

Measures: HTTP RTT + response body parsing + CEL expression evaluation + cursor state update.

This is the **total cycle time** for one CEL execution. It includes:
1. HTTP request → response (= `http_round_trip_time`)
2. Response body read and JSON parse
3. CEL program evaluation (HMAC signing, state management, event extraction)
4. Cursor update

**Not directly comparable to any single Akamai metric.** The closest comparison is:
- `cel_processing_time` vs `(response_latency + request_processing_time)` in Akamai

### Akamai: `response_latency`

Measures: HTTP response latency only (purely network + API server time). This is equivalent to `http_round_trip_time` in the CEL input, measured slightly differently.

### Akamai: `request_processing_time`

Measures: Total time to process a request including response handling, but not CEL evaluation (native Go code instead).

### Akamai: `events_per_batch`

Measures: How many events the API returns per batch. The Akamai input fetches up to `event_limit` events per call. The histogram shows the actual distribution — if consistently at `event_limit`, the API has more events available than we're fetching per cycle.

### Akamai: Reliability indicators

These have no CEL equivalent because the native input tracks error recovery more explicitly:

| Indicator | Interpretation |
|-----------|----------------|
| `offset_expired_total` | API returned 416 (offset stale). Expected behavior when Filebeat is slower than the offset TTL. The input handles this automatically. |
| `offset_ttl_drops_total` | Proactive offset drops. Input noticed the offset would expire soon and dropped it proactively. |
| `hmac_refresh_total` | Number of HMAC auth signature refreshes. Non-zero values suggest clock skew between Filebeat host and API server. |
| `cursor_drops_total` | Offset was cleared and the chain window was replayed from scratch. Each drop means re-fetching a window of events. |
| `from_clamped_total` | `chain_from` was clamped to the 12h max lookback. Happens during recovery if the gap is very large. |
| `api_400_fatal_total` | Non-recoverable 400 errors. **Non-zero means data loss.** |

---

## Throughput Fairness

To ensure fair comparison:

1. **Same duration**: Both runs use `--duration` (e.g., `60m`). Each Filebeat process runs for exactly this long.
2. **Same event_limit**: Both fetch the same max events per API call.
3. **Same interval**: Both poll at the same frequency.
4. **Same initial_interval**: Both start with the same lookback window, so initial event volumes are similar.

If the API delivers events at a steady EPS, both runs should have similar theoretical throughput. Differences in actual throughput reflect input processing overhead.

---

## "Winner" Definition

For each metric category:

| Category | Lower is better | Higher is better |
|----------|----------------|-----------------|
| Throughput (EPS) | — | ✓ |
| HTTP RTT | ✓ | — |
| Batch processing time | ✓ | — |
| GC overhead | ✓ | — |
| Memory (alloc, RSS) | ✓ | — |
| Goroutines | ✓ | — |

A "Tie" is declared when the difference is < 1% of the larger value.

---

## Limitations

1. **Sequential runs**: Not concurrent. API server state and network conditions may differ between runs.
2. **Single comparison**: One run per input type. Results may vary due to API rate variation. For robust conclusions, run 3+ times and average.
3. **Local file output**: This test uses `output.file` (no Elasticsearch). Output backpressure is minimal. In production (with Elasticsearch), batch processing times would be longer for both inputs.
4. **pprof overhead**: Profiling adds minor overhead. Block and mutex profiling with `rate=1` captures every event, which may slightly impact performance.
5. **Initial burst**: The first few minutes may show different behavior as Filebeat catches up on the initial_interval lookback. For steady-state comparison, the midpoint CPU profile is most representative.
