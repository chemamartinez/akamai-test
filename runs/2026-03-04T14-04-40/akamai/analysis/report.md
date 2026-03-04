# Filebeat AKAMAI Input — Single Run Report

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Input type | akamai |
| Interval | 1m |
| Initial interval | 1h |
| Event limit | 60000 |
| Duration | 60m |

## Throughput (from /inputs/ endpoint)

| Metric | Value |
|--------|-------|
| Total events published | 57420001 |
| Total events received | 57420001 |
| Total batches published | 958 |
| Total HTTP requests | 959 |
| HTTP 2xx responses | 959 |
| HTTP success rate | 100.00% |

## Throughput (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total events published (log) | 57476690 |
| Avg EPS | 16516.29 |

## Input Timing (from /inputs/ endpoint, all in ms)

| Metric | mean | p75 | p95 | p99 | max |
|--------|------|-----|-----|-----|-----|
| HTTP Round Trip Time | 514.64 ms | 540.38 ms | 644.36 ms | 779.02 ms | 887.53 ms |
| Batch Processing Time | 3051.56 ms | 3039.64 ms | 3427.59 ms | 4450.29 ms | 5515.85 ms |
| API Response Latency | 514.81 ms | 540.54 ms | 644.50 ms | 779.19 ms | 887.68 ms |
| Request Processing Time | 527.34 ms | 527.34 ms | 527.34 ms | 527.34 ms | 527.34 ms |

## Akamai-Specific Metrics

| Metric | Value |
|--------|-------|
| Akamai requests total | 959 |
| Successful requests | 959 |
| Failed requests | 0 |
| Worker utilization | 0.90% |

### Reliability Indicators

| Indicator | Count | Meaning |
|-----------|-------|---------|
| offset_expired | 0 | API returned 416 (offset stale) |
| offset_ttl_drops | 1 | Proactive drops before TTL expires |
| hmac_refresh | 0 | HMAC clock-skew retries |
| cursor_drops | 0 | Offset cleared, window replayed |
| from_clamped | 1 | Lookback clamped to 12h max |
| api_400_fatal | 0 | Non-recoverable 400 errors |

## System Resources (from monitoring logs)

| Metric | Value |
|--------|-------|
| Avg CPU total ms/min | 63617.78 |
| Avg memory alloc | 20.93 MB |
| Max memory alloc | 30.45 MB |
| Avg RSS | 123.14 MB |
| Max RSS | 125.55 MB |
| Avg goroutines | 37.61 |
| Max goroutines | 38.00 |
| Avg normalized load (1m) | 0.24 |

## Output Health (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total acked | 58391001 |
| Total failed | 0 |
| Total dropped | 0 |
| Avg output latency mean | 0.02 µs |
| Avg output latency p99 | 0.02 µs |

## pprof Analysis

## pprof Analysis — AKAMAI input

### CPU Profile (midpoint, 30s)

GC overhead: 0.2% (flat)
JSON decode: 0.0% (flat)

Top 10 functions by flat%:
Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime.pthread_cond_signal                                   59.6%  59.6%
syscall.syscall                                               18.8%  18.8%
runtime.pthread_cond_wait                                     10.2%  10.2%
runtime.usleep                                                 4.3%   4.3%
runtime.pthread_kill                                           1.5%   1.5%
runtime.madvise                                                0.8%   0.8%
runtime.pcvalue                                                0.5%   0.9%
runtime.scanobject                                             0.2%   0.7%
runtime.gcDrain                                                0.2%   2.7%
runtime.unlock2                                                0.1%   1.6%

### Heap Growth (baseline → final)

Top memory growth paths:
Function                                                      flat%   cum%
--------------------------------------------------------------------------
github.com/elastic/beats/v7/x-pack/filebeat/input/akamai.createBeatEvent (inline)  35.7%  35.7%
github.com/elastic/elastic-agent-libs/mapstr.cloneMap         32.8%  32.8%
github.com/elastic/beats/v7/libbeat/asset.GetFields            6.9%   5.4%
go.elastic.co/apm/v2.newBreakdownMetricsMap (inline)           1.5%   1.5%
github.com/elastic/beats/v7/libbeat/publisher/queue/memqueue.newQueue   1.4%   1.4%
github.com/elastic/beats/v7/libbeat/publisher/pipeline.newBatch   1.4%   1.4%
runtime.malg                                                   1.3%   1.3%
bytes.growSlice                                                0.8%   0.8%
github.com/elastic/beats/v7/x-pack/filebeat/input/akamai.StreamEvents   0.7%   1.5%
github.com/rcrowley/go-metrics.NewUniformSample (inline)       0.7%   0.7%

### Block Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime.selectgo                                              92.3%  92.3%
runtime.chanrecv1                                              6.9%   6.9%
runtime.chanrecv2                                              0.7%   0.7%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*InputManager).Init.func1   0.0%  10.5%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*cleaner).run   0.0%  10.5%
github.com/elastic/beats/v7/filebeat/input/v2/compat.(*runner).Start.func1   0.0%   2.7%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*InputManager).Init.func1   0.0%  31.4%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*cleaner).run   0.0%  31.4%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.(*Reporter).snapshotLoop   0.0%   3.8%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.MakeReporter.func1   0.0%   3.8%

### Mutex Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime._LostContendedRuntimeLock                            100.0% 100.0%

## Issues Detected

- ⚠️  growing_pipeline_active: possible backpressure
