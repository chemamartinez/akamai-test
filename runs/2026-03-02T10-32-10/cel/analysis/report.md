# Filebeat CEL Input — Single Run Report

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Input type | cel |
| Interval | 1m |
| Initial interval | 1h |
| Event limit | 50000 |
| Duration | 30m |

## Throughput (from /inputs/ endpoint)

| Metric | Value |
|--------|-------|
| Total events published | 7100143 |
| Total events received | 7100143 |
| Total batches published | 143 |
| Total HTTP requests | 144 |
| HTTP 2xx responses | 143 |
| HTTP success rate | 99.31% |

## Throughput (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total events published (log) | 7128434 |
| Avg EPS | 4243.08 |

## Input Timing (from /inputs/ endpoint, all in ms)

| Metric | mean | p75 | p95 | p99 | max |
|--------|------|-----|-----|-----|-----|
| HTTP Round Trip Time | 469.19 ms | 481.11 ms | 510.88 ms | 695.85 ms | 710.66 ms |
| Batch Processing Time | 3199.24 ms | 3220.38 ms | 3241.54 ms | 3254.96 ms | 3256.54 ms |
| CEL Processing Time | 8886.45 ms | 8878.52 ms | 10023.92 ms | 10839.37 ms | 11186.68 ms |

## CEL-Specific Metrics

| Metric | Value |
|--------|-------|
| CEL executions | 144 |

## System Resources (from monitoring logs)

| Metric | Value |
|--------|-------|
| Avg CPU total ms/min | 54500.00 |
| Avg memory alloc | 191.53 MB |
| Max memory alloc | 308.24 MB |
| Avg RSS | 636.37 MB |
| Max RSS | 642.30 MB |
| Avg goroutines | 37.41 |
| Max goroutines | 41.00 |
| Avg normalized load (1m) | 0.34 |

## Output Health (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total acked | 7350148 |
| Total failed | 0 |
| Total dropped | 0 |
| Avg output latency mean | 0.00 µs |
| Avg output latency p99 | 0.00 µs |

## pprof Analysis

## pprof Analysis — CEL input

### CPU Profile (midpoint, 30s)

GC overhead: 0.0% (flat)
JSON decode: 0.0% (flat)
CEL eval/boundary: 0.0% (flat)

Top 10 functions by flat%:
Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime.pthread_cond_signal                                   36.6%  36.6%
runtime.pcvalue                                               11.3%  21.6%
syscall.syscall                                                7.2%   7.2%
runtime.(*mspan).specialFindSplicePoint (inline)               5.8%   5.8%
runtime.step                                                   4.4%   5.8%
runtime.madvise                                                4.3%   4.3%
runtime.markrootSpans                                          2.9%   2.9%
runtime.usleep                                                 2.8%   2.8%
runtime.findfunc                                               2.5%   2.9%
runtime.(*moduledata).textAddr                                 2.5%   2.5%

### Heap Growth (baseline → final)

Top memory growth paths:
Function                                                      flat%   cum%
--------------------------------------------------------------------------
bytes.growSlice                                               40.5%  40.5%
github.com/google/cel-go/common/types.Bytes.ConvertToType     39.8%  39.8%
github.com/elastic/elastic-agent-libs/mapstr.cloneMap          0.5%   0.5%
github.com/elastic/beats/v7/libbeat/publisher/pipeline.(*client).publish   0.0%   0.7%
github.com/google/cel-go/interpreter.(*folder).ResolveName     0.0%  80.3%
bytes.(*Buffer).ReadFrom                                       0.0%  40.5%
bytes.(*Buffer).grow                                           0.0%  40.5%
github.com/elastic/beats/v7/filebeat/beater.(*countingClient).Publish   0.0%   0.7%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*cursorPublisher).Publish   0.0%   0.7%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*cursorPublisher).forward   0.0%   0.7%

### Block Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime.selectgo                                              91.2%  91.2%
runtime.chanrecv1                                              8.8%   8.8%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*InputManager).Init.func1   0.0%  11.2%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*cleaner).run   0.0%  11.2%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*InputManager).Init.func1   0.0%  33.5%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*cleaner).run   0.0%  33.5%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.(*Reporter).snapshotLoop   0.0%   4.3%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.MakeReporter.func1   0.0%   4.3%
github.com/elastic/beats/v7/libbeat/processors/add_kubernetes_metadata.(*cache).cleanup   0.0%   4.4%
github.com/elastic/beats/v7/libbeat/processors/add_kubernetes_metadata.newCache.gowrap1   0.0%   4.4%

### Mutex Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime._LostContendedRuntimeLock                             81.2%  81.2%
sync.(*Mutex).Unlock                                          18.8%  18.8%
github.com/elastic/beats/v7/libbeat/processors/add_cloud_metadata.(*addCloudMetadata).init   0.0%  18.8%
github.com/elastic/beats/v7/libbeat/processors/add_cloud_metadata.New.gowrap1   0.0%  18.8%
sync.(*Once).Do (inline)                                       0.0%  18.8%
sync.(*Once).doSlow                                            0.0%  18.8%

## Issues Detected

_No issues detected._
