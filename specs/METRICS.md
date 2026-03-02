# Metrics Reference

Complete field catalog for all three metric types collected during each test run.

---

## 1. Monitoring Log Metrics

**Source**: Filebeat log files in `<run>/logs/`
**Collection**: Filebeat writes one JSON line per `logging.metrics.period` (1 minute)
**Logger name**: `log.logger: "monitoring"`
**Final summary**: Lines containing `"Total metrics"` in the message

### Counter vs Gauge semantics

> **CRITICAL**: Counter metrics in the monitoring log already represent the **change since the last snapshot** (they are deltas, not cumulative totals). To compute run totals, **SUM** them across all snapshots. The `"Total metrics"` entry at shutdown does contain cumulative totals and is used to cross-validate.
>
> Gauge metrics (e.g. `pipeline_events_active`, `queue_filled_pct`) are point-in-time values — do not sum them.

### Beat metrics (`monitoring.metrics.beat.*`)

| Field path | Type | Description |
|------------|------|-------------|
| `beat.cpu.total.time.ms` | counter | CPU time (user + system) in ms since last snapshot |
| `beat.cpu.user.time.ms` | counter | CPU time in user space in ms |
| `beat.cpu.system.time.ms` | counter | CPU time in kernel space in ms |
| `beat.memstats.memory_alloc` | gauge | Currently allocated heap memory (bytes) |
| `beat.memstats.memory_total` | counter | Total allocated memory since start (bytes) |
| `beat.memstats.rss` | gauge | Resident Set Size — OS-level physical memory (bytes) |
| `beat.memstats.gc_next` | gauge | Next GC target heap size (bytes) |
| `beat.runtime.goroutines` | gauge | Current number of goroutines |
| `beat.info.uptime.ms` | gauge | Beat uptime in milliseconds (in final summary only) |
| `beat.info.version` | string | Filebeat version string |

**Troubleshooting hints**:
- Growing `memory_alloc` → potential memory leak
- Growing `goroutines` (>50% growth) → potential goroutine leak
- `cpu.total.time.ms` high → process is CPU-bound

### Libbeat pipeline metrics (`monitoring.metrics.libbeat.pipeline.*`)

| Field path | Type | Description |
|------------|------|-------------|
| `pipeline.events.active` | gauge | Events currently in the pipeline (in-flight) |
| `pipeline.events.published` | counter | Events published since last snapshot |
| `pipeline.events.total` | counter | Events processed since last snapshot |
| `pipeline.queue.filled.events` | gauge | Events currently in queue |
| `pipeline.queue.filled.bytes` | gauge | Bytes currently in queue |
| `pipeline.queue.filled.pct` | gauge | Queue fill % (0–100) |
| `pipeline.queue.max_events` | gauge | Queue capacity in events |
| `pipeline.queue.added.events` | counter | Events added to queue since last snapshot |
| `pipeline.queue.consumed.events` | counter | Events consumed from queue since last snapshot |
| `pipeline.queue.removed.events` | counter | Events removed (ACKed) since last snapshot |

**Troubleshooting hints**:
- `queue.filled.pct > 90%` → output bottleneck
- `queue.filled.pct` low + low throughput → input bottleneck
- Growing `pipeline.events.active` → backpressure building

### Libbeat output metrics (`monitoring.metrics.libbeat.output.*`)

| Field path | Type | Description |
|------------|------|-------------|
| `output.events.total` | counter | Events sent to output since last snapshot |
| `output.events.acked` | counter | Events acknowledged by output |
| `output.events.active` | gauge | Events currently pending ACK |
| `output.events.failed` | counter | Events that failed delivery |
| `output.events.dropped` | counter | Events dropped (unrecoverable) |
| `output.events.batches` | counter | Batches sent to output |
| `output.write.bytes` | counter | Bytes written to output |
| `output.write.latency.histogram.mean` | gauge | Mean write latency (µs) |
| `output.write.latency.histogram.p95` | gauge | p95 write latency (µs) |
| `output.write.latency.histogram.p99` | gauge | p99 write latency (µs) |
| `output.write.latency.histogram.max` | gauge | Max write latency (µs) |

### Filebeat metrics (`monitoring.metrics.filebeat.*`)

| Field path | Type | Description |
|------------|------|-------------|
| `filebeat.events.active` | gauge | Events in active harvesting |
| `filebeat.events.added` | counter | Events added by harvesters |
| `filebeat.events.done` | counter | Events processed by harvesters |

### System metrics (`monitoring.metrics.system.*`)

| Field path | Type | Description |
|------------|------|-------------|
| `system.load.1` | gauge | 1-minute system load average |
| `system.load.5` | gauge | 5-minute system load average |
| `system.load.15` | gauge | 15-minute system load average |
| `system.load.norm.1` | gauge | Normalized 1-min load (divided by CPU count) |
| `system.load.norm.5` | gauge | Normalized 5-min load |
| `system.load.norm.15` | gauge | Normalized 15-min load |

**Troubleshooting hints**:
- `load.norm.1 > 1.0` → system overloaded

---

## 2. Input Metrics (`/inputs/` HTTP endpoint)

**Source**: `GET http://localhost:5066/inputs/`
**Collection**: Polled every 60 seconds by `bin/collect_input_metrics.sh`
**Storage**: `<run>/input_metrics/t<elapsed_secs>.json` (e.g. `t0060.json`)
**Format**: JSON array; take `data[0]` for the single configured input

> **CRITICAL**: These counters are **cumulative** from Filebeat startup. The analysis script computes per-interval deltas by subtracting consecutive snapshots. Histograms are cumulative over the full run — use the **final snapshot** for run-level histogram statistics.

### Shared fields (both CEL and Akamai)

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `input` | string | — | Input type identifier (`"cel"` or `"akamai"`) |
| `id` | string | — | Input instance ID |
| `resource` | string | — | API URL |
| `batches_received_total` | counter | batches | Event batches received from API |
| `batches_published_total` | counter | batches | Event batches published to pipeline |
| `events_received_total` | counter | events | Total events received |
| `events_published_total` | counter | events | Total events published |
| `events_pipeline_total` | counter | events | Events sent through pipeline |
| `events_pipeline_published_total` | counter | events | Events published through pipeline |
| `http_request_total` | counter | requests | Total HTTP requests made |
| `http_request_errors_total` | counter | requests | HTTP request errors |
| `http_request_get_total` | counter | requests | GET requests |
| `http_response_total` | counter | responses | Total HTTP responses |
| `http_response_2xx_total` | counter | responses | 2xx success responses |
| `http_response_4xx_total` | counter | responses | 4xx client error responses |
| `http_response_5xx_total` | counter | responses | 5xx server error responses |
| `http_response_errors_total` | counter | responses | Response errors |
| `batch_processing_time` | histogram | nanoseconds | Time from batch receipt to pipeline ACK |
| `http_round_trip_time` | histogram | nanoseconds | HTTP round trip time (network + API) |

### CEL-specific fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `cel_executions` | counter | executions | Number of CEL program evaluations |
| `cel_processing_time` | histogram | nanoseconds | HTTP RTT + response parsing + CEL evaluation |

> **Note on `cel_processing_time` vs `http_round_trip_time`**: `http_round_trip_time` measures purely the HTTP call. `cel_processing_time` adds CEL expression evaluation, response body parsing, and value conversion overhead. The difference represents the pure CEL overhead per cycle.

### Akamai-specific fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `akamai_requests_total` | counter | requests | Total Akamai API requests |
| `akamai_requests_success_total` | counter | requests | Successful API requests |
| `akamai_requests_errors_total` | counter | requests | Failed API requests |
| `offset_expired_total` | counter | occurrences | 416 responses (offset stale on API server) |
| `offset_ttl_drops_total` | counter | occurrences | Proactive offset drops before TTL expires |
| `hmac_refresh_total` | counter | occurrences | HMAC auth signature refreshes (clock-skew retries) |
| `cursor_drops_total` | counter | occurrences | Times offset was cleared and chain window replayed |
| `from_clamped_total` | counter | occurrences | `chain_from` clamped to 12h max lookback |
| `api_400_fatal_total` | counter | occurrences | Non-recoverable 400 responses (data loss indicator) |
| `errors_total` | counter | occurrences | Total errors |
| `workers_active_gauge` | gauge | workers | Currently active event-publishing workers |
| `worker_utilization` | gauge | ratio (0–1) | Worker utilization, updated every 5s |
| `request_processing_time` | histogram | nanoseconds | Request processing time |
| `response_latency` | histogram | nanoseconds | API response latency (purely HTTP) |
| `events_per_batch` | histogram | events | Events per API batch |

### Histogram fields

All histograms expose these sub-fields:

| Sub-field | Description |
|-----------|-------------|
| `histogram.count` | Number of observations |
| `histogram.mean` | Mean value |
| `histogram.median` | Median value |
| `histogram.min` | Minimum value |
| `histogram.max` | Maximum value |
| `histogram.p75` | 75th percentile |
| `histogram.p95` | 95th percentile |
| `histogram.p99` | 99th percentile |
| `histogram.p999` | 99.9th percentile |
| `histogram.stddev` | Standard deviation |

The analysis script converts all nanosecond histogram values to milliseconds by dividing by 1,000,000.

---

## 3. pprof Profiles

**Source**: `GET http://localhost:5066/debug/pprof/*`
**Collection**: `bin/collect_pprof.sh` at timed checkpoints during the run
**Storage**: `<run>/pprof/` directory

For collection commands, timing strategy, and analysis methodology, see [PPROF_ANALYSIS.md](PPROF_ANALYSIS.md).

### Profiles collected

| File | Endpoint | When | Purpose |
|------|----------|------|---------|
| `heap_baseline.pprof` | `/debug/pprof/heap` | ~30s into run | Pre-steady-state heap snapshot for diff |
| `cpu_midpoint.pprof` | `/debug/pprof/profile?seconds=30` | Run midpoint | CPU hotspot identification |
| `heap_final.pprof` | `/debug/pprof/heap` | ~15s before end | Final heap state for growth analysis |
| `block_final.pprof` | `/debug/pprof/block` | ~15s before end | Goroutine blocking events |
| `mutex_final.pprof` | `/debug/pprof/mutex` | ~15s before end | Mutex contention |
