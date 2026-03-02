# Filebeat AKAMAI Input — Single Run Report

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Input type | akamai |
| Interval | 1m |
| Initial interval | 1h |
| Event limit | 50000 |
| Duration | 30m |

## Throughput (from /inputs/ endpoint)

| Metric | Value |
|--------|-------|
| Total events published | 27100000 |
| Total events received | 27100000 |
| Total batches published | 542 |
| Total HTTP requests | 543 |
| HTTP 2xx responses | 543 |
| HTTP success rate | 100.00% |

## Throughput (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total events published (log) | 27150000 |
| Avg EPS | 16161.24 |

## Input Timing (from /inputs/ endpoint, all in ms)

| Metric | mean | p75 | p95 | p99 | max |
|--------|------|-----|-----|-----|-----|
| HTTP Round Trip Time | 463.65 ms | 471.48 ms | 501.91 ms | 597.71 ms | 829.79 ms |
| Batch Processing Time | 2625.34 ms | 2618.86 ms | 2724.24 ms | 3676.50 ms | 4907.21 ms |
| API Response Latency | 463.83 ms | 471.66 ms | 502.06 ms | 597.87 ms | 829.94 ms |
| Request Processing Time | 0.00 ms | 0.00 ms | 0.00 ms | 0.00 ms | 0.00 ms |

## Akamai-Specific Metrics

| Metric | Value |
|--------|-------|
| Akamai requests total | 543 |
| Successful requests | 543 |
| Failed requests | 0 |
| Worker utilization | 0.81% |

### Reliability Indicators

| Indicator | Count | Meaning |
|-----------|-------|---------|
| offset_expired | 0 | API returned 416 (offset stale) |
| offset_ttl_drops | 1 | Proactive drops before TTL expires |
| hmac_refresh | 0 | HMAC clock-skew retries |
| cursor_drops | 0 | Offset cleared, window replayed |
| from_clamped | 0 | Lookback clamped to 12h max |
| api_400_fatal | 0 | Non-recoverable 400 errors |

## System Resources (from monitoring logs)

| Metric | Value |
|--------|-------|
| Avg CPU total ms/min | 65379.03 |
| Avg memory alloc | 21.86 MB |
| Max memory alloc | 30.01 MB |
| Avg RSS | 121.19 MB |
| Max RSS | 123.23 MB |
| Avg goroutines | 42.45 |
| Max goroutines | 43.00 |
| Avg normalized load (1m) | 0.26 |

## Output Health (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total acked | 28050000 |
| Total failed | 0 |
| Total dropped | 0 |
| Avg output latency mean | 0.00 µs |
| Avg output latency p99 | 0.00 µs |

## pprof Analysis

## pprof Analysis — AKAMAI input

### CPU Profile (midpoint, 30s)

GC overhead: 0.1% (flat)
JSON decode: 0.0% (flat)

Top 10 functions by flat%:
Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime.pthread_cond_signal                                   59.0%  59.0%
syscall.syscall                                               19.3%  19.3%
runtime.pthread_cond_wait                                      9.3%   9.4%
runtime.usleep                                                 4.3%   4.3%
runtime.pthread_kill                                           1.3%   1.3%
runtime.pcvalue                                                1.0%   1.5%
runtime.kevent                                                 0.8%   0.8%
runtime.madvise                                                0.7%   0.7%
runtime.(*unwinder).resolveInternal                            0.2%   1.0%
runtime.scanobject                                             0.1%   0.8%

### Heap Growth (baseline → final)

Top memory growth paths:
Function                                                      flat%   cum%
--------------------------------------------------------------------------
github.com/elastic/beats/v7/libbeat/asset.GetFields           24.2%  23.2%
go.elastic.co/apm/v2.newBreakdownMetricsMap (inline)           5.3%   5.3%
github.com/elastic/beats/v7/libbeat/publisher/queue/memqueue.newQueue   5.1%   5.1%
runtime.malg                                                   3.4%   3.4%
github.com/elastic/beats/v7/x-pack/filebeat/input/akamai.createBeatEvent (inline)   3.0%   3.0%
github.com/elastic/beats/v7/x-pack/filebeat/input/akamai.StreamEvents   2.5%   4.4%
github.com/rcrowley/go-metrics.NewUniformSample (inline)       2.4%   2.4%
github.com/elastic/beats/v7/x-pack/filebeat/input/akamai.(*siemPoller).processPage.func1   2.3%   7.7%
go.uber.org/zap/internal/bufferpool.init.NewPool.func1         1.9%   1.9%
go.elastic.co/apm/v2.newTracer                                 1.6%   7.0%

### Block Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime.selectgo                                              92.7%  92.7%
runtime.chanrecv1                                              6.7%   6.7%
runtime.chanrecv2                                              0.6%   0.6%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*InputManager).Init.func1   0.0%   9.0%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*cleaner).run   0.0%   9.0%
github.com/elastic/beats/v7/filebeat/input/v2/compat.(*runner).Start.func1   0.0%   2.7%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*InputManager).Init.func1   0.0%  27.1%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*cleaner).run   0.0%  27.1%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.(*Reporter).snapshotLoop   0.0%   3.5%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.MakeReporter.func1   0.0%   3.5%

### Mutex Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime._LostContendedRuntimeLock                            100.0% 100.0%

## Issues Detected

- ⚠️  growing_pipeline_active: possible backpressure
