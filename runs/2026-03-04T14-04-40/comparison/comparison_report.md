# CEL vs Akamai — Performance Comparison Report

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Duration | 60m |
| Interval | 1m |
| Initial interval | 1h |
| Event limit | 60000 |

> **Note**: Runs are sequential (CEL first, then Akamai) using the same parameters.
> Minor differences in API server state or network conditions may affect results.

---

## Executive Summary

| Metric | CEL | Akamai | Δ (Akamai vs CEL) | Better |
|--------|-----|--------|-------------------|--------|
| Total events published | 15120252 | 57420001 | +279.8% | Akamai |
| Avg EPS (monitoring log) | 4344.89 | 16516.29 | +280.1% | Akamai |
| HTTP RTT mean | 544.22 ms | 514.64 ms | -5.4% | Akamai |
| Batch processing mean | 3539.15 ms | 3051.56 ms | -13.8% | Akamai |
| GC overhead (CPU%) | 0% | 0.18% | N/A | CEL |
| Avg memory alloc | 209.97 MB | 20.93 MB | -90.0% | Akamai |
| Max RSS | 779.09 MB | 125.55 MB | -83.9% | Akamai |
| Avg goroutines | 33.00 | 37.61 | +14.0% | CEL |

---

## Throughput Comparison

| Metric | CEL | Akamai | Δ |
|--------|-----|--------|---|
| Total events published (/inputs/) | 15120252 | 57420001 | +279.8% |
| Avg EPS (monitoring log) | 4344.89 | 16516.29 | +280.1% |
| HTTP success rate | 100.00% | 100.00% | — |

---

## Latency Comparison

### HTTP Round Trip Time (shared metric)

| Percentile | CEL | Akamai | Δ | Better |
|------------|-----|--------|---|--------|
| mean | 544.22 ms | 514.64 ms | -5.4% | Akamai |
| p75 | 565.10 ms | 540.38 ms | -4.4% | Akamai |
| p95 | 722.87 ms | 644.36 ms | -10.9% | Akamai |
| p99 | 1149.43 ms | 779.02 ms | -32.2% | Akamai |
| max | 1377.52 ms | 887.53 ms | -35.6% | Akamai |

### Batch Processing Time — receipt to pipeline ACK (shared metric)

| Percentile | CEL | Akamai | Δ | Better |
|------------|-----|--------|---|--------|
| mean | 3539.15 ms | 3051.56 ms | -13.8% | Akamai |
| p75 | 3546.08 ms | 3039.64 ms | -14.3% | Akamai |
| p95 | 3561.60 ms | 3427.59 ms | -3.8% | Akamai |
| p99 | 3575.58 ms | 4450.29 ms | +24.5% | CEL |
| max | 3586.31 ms | 5515.85 ms | +53.8% | CEL |

### Input-Specific Timing

> **CEL Processing Time** = HTTP RTT + response parsing + CEL evaluation.
> **Akamai Response Latency** = purely HTTP response time (no CEL overhead).
> These measure different things — use HTTP Round Trip Time for direct apples-to-apples comparison.

| Metric | Value |
|--------|-------|
| CEL: cel_processing_time mean | 10476.41 ms |
| CEL: cel_processing_time p99  | 11938.18 ms |
| Akamai: response_latency mean | 514.81 ms |
| Akamai: response_latency p99  | 779.19 ms |

---

## Resource Usage Comparison

| Metric | CEL | Akamai | Δ | Better |
|--------|-----|--------|---|--------|
| Avg memory alloc | 209.97 MB | 20.93 MB | -90.0% | Akamai |
| Max memory alloc | 314.96 MB | 30.45 MB | -90.3% | Akamai |
| Avg RSS | 728.10 MB | 123.14 MB | -83.1% | Akamai |
| Max RSS | 779.09 MB | 125.55 MB | -83.9% | Akamai |
| Avg goroutines | 33.00 | 37.61 | +14.0% | CEL |
| Avg normalized load | 0.24 | 0.24 | +1.2% | Tie |

---

## pprof Deep Dive

### GC Pressure

| Metric | CEL | Akamai | Δ |
|--------|-----|--------|---|
| GC overhead (CPU flat%) | 0% | 0.18% | N/A |
| JSON decode (CPU flat%) | 0% | 0% | N/A |

> GC overhead > 20% indicates allocation-heavy paths (JSON decode, CEL eval, event publish).

### Per-Run pprof Reports

See individual run reports for full top-N function tables:
- `cel/analysis/pprof_report.txt`
- `akamai/analysis/pprof_report.txt`

---

## Akamai Reliability Indicators

| Indicator | Count | Interpretation |
|-----------|-------|----------------|
| offset_expired | 0 | API offset stale (416). Expected if run exceeds offset TTL (120s). |
| hmac_refresh | 0 | Auth clock-skew retries. Non-zero = clock drift between client/server. |
| cursor_drops | 0 | Offset cleared; chain window replayed from scratch. |
| api_400_fatal | 0 | Non-recoverable 400 errors. Non-zero = data loss. |
| worker_utilization | 0.90% | % of time workers were busy (0–1). |

---

## Issues Summary

**CEL run issues:** None detected

**Akamai run issues:**
- ⚠️  growing_pipeline_active: possible backpressure

---

## Conclusions

1. **Throughput**: Akamai achieved higher average EPS (280.1% difference). CEL: 4344.9 EPS, Akamai: 16516.3 EPS.
2. **HTTP Latency**: Akamai had lower HTTP RTT (Δ mean = 30 ms).
3. **Batch Processing Time** (receipt→ACK): Akamai was faster (Δ mean = 488 ms). A higher value for CEL may indicate CEL evaluation adds publishing latency.
4. **GC Pressure**: CEL GC overhead = 0.0%, Akamai = 0.2%. Higher CEL GC is expected due to CEL expression evaluation and value conversion allocations.
5. **Memory**: Akamai used less RSS at peak (779 MB vs 126 MB).
6. **Recommendation**: Based on the above, review the latency and GC overhead differences to determine whether the Akamai native input provides sufficient improvement to justify migration from the CEL implementation.

## Visualizations

Generated plots in `comparison/plots/`:
- `throughput_comparison.png` — events published over time
- `latency_comparison.png` — HTTP RTT and batch processing percentiles
- `resource_comparison.png` — CPU, memory, RSS, goroutines