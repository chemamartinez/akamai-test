# Filebeat CEL Input — Single Run Report

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Input type | cel |
| Interval | 1m |
| Initial interval | 1h |
| Event limit | 60000 |
| Duration | 60m |

## Throughput (from /inputs/ endpoint)

| Metric | Value |
|--------|-------|
| Total events published | 15120252 |
| Total events received | 15120252 |
| Total batches published | 252 |
| Total HTTP requests | 253 |
| HTTP 2xx responses | 253 |
| HTTP success rate | 100.00% |

## Throughput (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total events published (log) | 15120252 |
| Avg EPS | 4344.89 |

## Input Timing (from /inputs/ endpoint, all in ms)

| Metric | mean | p75 | p95 | p99 | max |
|--------|------|-----|-----|-----|-----|
| HTTP Round Trip Time | 544.22 ms | 565.10 ms | 722.87 ms | 1149.43 ms | 1377.52 ms |
| Batch Processing Time | 3539.15 ms | 3546.08 ms | 3561.60 ms | 3575.58 ms | 3586.31 ms |
| CEL Processing Time | 10476.41 ms | 10505.18 ms | 10879.18 ms | 11938.18 ms | 14162.15 ms |

## CEL-Specific Metrics

| Metric | Value |
|--------|-------|
| CEL executions | 253 |

## System Resources (from monitoring logs)

| Metric | Value |
|--------|-------|
| Avg CPU total ms/min | 54464.54 |
| Avg memory alloc | 209.97 MB |
| Max memory alloc | 314.96 MB |
| Avg RSS | 728.10 MB |
| Max RSS | 779.09 MB |
| Avg goroutines | 33.00 |
| Max goroutines | 36.00 |
| Avg normalized load (1m) | 0.24 |

## Output Health (from monitoring logs)

| Metric | Value |
|--------|-------|
| Total acked | 15360256 |
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
runtime.pthread_cond_signal                                   29.6%  29.6%
runtime.pcvalue                                               13.8%  29.0%
runtime.(*mspan).specialFindSplicePoint (inline)               9.5%   9.5%
runtime.step                                                   6.7%   8.3%
syscall.syscall                                                6.2%   6.2%
runtime.(*moduledata).textAddr                                 3.4%   3.4%
runtime.tracebackPCs                                           2.5%  40.1%
runtime.usleep                                                 2.5%   2.5%
runtime.findfunc                                               2.3%   2.9%
runtime.(*unwinder).resolveInternal                            2.1%  14.7%

### Heap Growth (baseline → final)

Top memory growth paths:
Function                                                      flat%   cum%
--------------------------------------------------------------------------
bytes.growSlice                                               41.9%  41.9%
bytes.(*Buffer).ReadFrom                                       0.0%  41.9%
bytes.(*Buffer).grow                                           0.0%  41.9%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*managedInput).Run.func1   0.0%  41.9%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*managedInput).runSource   0.0%  41.9%
github.com/elastic/beats/v7/x-pack/filebeat/input/cel.evalWith   0.0%  41.9%
github.com/elastic/beats/v7/x-pack/filebeat/input/cel.input.Run   0.0%  41.9%
github.com/elastic/beats/v7/x-pack/filebeat/input/cel.input.run   0.0%  41.9%
github.com/elastic/beats/v7/x-pack/filebeat/input/cel.input.run.func1   0.0%  41.9%
github.com/elastic/beats/v7/x-pack/filebeat/input/cel.periodically   0.0%  41.9%

### Block Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime.selectgo                                              90.7%  90.7%
runtime.chanrecv1                                              9.3%   9.3%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*InputManager).Init.func1   0.0%  13.2%
github.com/elastic/beats/v7/filebeat/input/filestream/internal/input-logfile.(*cleaner).run   0.0%  13.2%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*InputManager).Init.func1   0.0%  39.5%
github.com/elastic/beats/v7/filebeat/input/v2/input-cursor.(*cleaner).run   0.0%  39.5%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.(*Reporter).snapshotLoop   0.0%   4.7%
github.com/elastic/beats/v7/libbeat/monitoring/report/log.MakeReporter.func1   0.0%   4.7%
github.com/elastic/beats/v7/libbeat/processors/add_kubernetes_metadata.(*cache).cleanup   0.0%   4.8%
github.com/elastic/beats/v7/libbeat/processors/add_kubernetes_metadata.newCache.gowrap1   0.0%   4.8%

### Mutex Contention

Function                                                      flat%   cum%
--------------------------------------------------------------------------
runtime._LostContendedRuntimeLock                            100.0% 100.0%

## Issues Detected

_No issues detected._
