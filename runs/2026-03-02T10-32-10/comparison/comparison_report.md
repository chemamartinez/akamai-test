# CEL vs Akamai — Performance Comparison Report

## Test Parameters

| Parameter | Value |
|-----------|-------|
| Duration | 30m |
| Interval | 1m |
| Initial interval | 1h |
| Event limit | 50000 |

> **Note**: Runs are sequential (CEL first, then Akamai) using the same parameters.
> Minor differences in API server state or network conditions may affect results.

---

## Executive Summary

| Metric | CEL | Akamai | Δ (Akamai vs CEL) | Better |
|--------|-----|--------|-------------------|--------|
| Total events published | 7100143 | 27100000 | +281.7% | Akamai |
| Avg EPS (monitoring log) | 4243.08 | 16161.24 | +280.9% | Akamai |
| HTTP RTT mean | 469.19 ms | 463.65 ms | -1.2% | Akamai |
| Batch processing mean | 3199.24 ms | 2625.34 ms | -17.9% | Akamai |
| GC overhead (CPU%) | 0% | 0.09% | N/A | CEL |
| Avg memory alloc | 191.53 MB | 21.86 MB | -88.6% | Akamai |
| Max RSS | 642.30 MB | 123.23 MB | -80.8% | Akamai |
| Avg goroutines | 37.41 | 42.45 | +13.5% | CEL |

---

## Throughput Comparison

| Metric | CEL | Akamai | Δ |
|--------|-----|--------|---|
| Total events published (/inputs/) | 7100143 | 27100000 | +281.7% |
| Avg EPS (monitoring log) | 4243.08 | 16161.24 | +280.9% |
| HTTP success rate | 99.31% | 100.00% | — |

---

## Latency Comparison

### HTTP Round Trip Time (shared metric)

| Percentile | CEL | Akamai | Δ | Better |
|------------|-----|--------|---|--------|
| mean | 469.19 ms | 463.65 ms | -1.2% | Akamai |
| p75 | 481.11 ms | 471.48 ms | -2.0% | Akamai |
| p95 | 510.88 ms | 501.91 ms | -1.8% | Akamai |
| p99 | 695.85 ms | 597.71 ms | -14.1% | Akamai |
| max | 710.66 ms | 829.79 ms | +16.8% | CEL |

### Batch Processing Time — receipt to pipeline ACK (shared metric)

| Percentile | CEL | Akamai | Δ | Better |
|------------|-----|--------|---|--------|
| mean | 3199.24 ms | 2625.34 ms | -17.9% | Akamai |
| p75 | 3220.38 ms | 2618.86 ms | -18.7% | Akamai |
| p95 | 3241.54 ms | 2724.24 ms | -16.0% | Akamai |
| p99 | 3254.96 ms | 3676.50 ms | +13.0% | CEL |
| max | 3256.54 ms | 4907.21 ms | +50.7% | CEL |

### Input-Specific Timing

> **CEL Processing Time** = HTTP RTT + response parsing + CEL evaluation.
> **Akamai Response Latency** = purely HTTP response time (no CEL overhead).
> These measure different things — use HTTP Round Trip Time for direct apples-to-apples comparison.

| Metric | Value |
|--------|-------|
| CEL: cel_processing_time mean | 8886.45 ms |
| CEL: cel_processing_time p99  | 10839.37 ms |
| Akamai: response_latency mean | 463.83 ms |
| Akamai: response_latency p99  | 597.87 ms |

---

## Resource Usage Comparison

| Metric | CEL | Akamai | Δ | Better |
|--------|-----|--------|---|--------|
| Avg memory alloc | 191.53 MB | 21.86 MB | -88.6% | Akamai |
| Max memory alloc | 308.24 MB | 30.01 MB | -90.3% | Akamai |
| Avg RSS | 636.37 MB | 121.19 MB | -81.0% | Akamai |
| Max RSS | 642.30 MB | 123.23 MB | -80.8% | Akamai |
| Avg goroutines | 37.41 | 42.45 | +13.5% | CEL |
| Avg normalized load | 0.34 | 0.26 | -24.3% | Akamai |

---

## pprof Deep Dive

### GC Pressure

| Metric | CEL | Akamai | Δ |
|--------|-----|--------|---|
| GC overhead (CPU flat%) | 0% | 0.09% | N/A |
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
| worker_utilization | 0.81% | % of time workers were busy (0–1). |

---

## Issues Summary

**CEL run issues:** None detected

**Akamai run issues:**
- ⚠️  growing_pipeline_active: possible backpressure

---

## Conclusions

1. **Throughput**: Akamai achieved higher average EPS (280.9% difference). CEL: 4243.1 EPS, Akamai: 16161.2 EPS.
2. **HTTP Latency**: Akamai had lower HTTP RTT (Δ mean = 6 ms).
3. **Batch Processing Time** (receipt→ACK): Akamai was faster (Δ mean = 574 ms). A higher value for CEL may indicate CEL evaluation adds publishing latency.
4. **GC Pressure**: CEL GC overhead = 0.0%, Akamai = 0.1%. Higher CEL GC is expected due to CEL expression evaluation and value conversion allocations.
5. **Memory**: Akamai used less RSS at peak (642 MB vs 123 MB).
6. **Recommendation**: Based on the above, review the latency and GC overhead differences to determine whether the Akamai native input provides sufficient improvement to justify migration from the CEL implementation.

## Visualizations

Generated plots in `comparison/plots/`:
- `throughput_comparison.png` — events published over time
- `latency_comparison.png` — HTTP RTT and batch processing percentiles
- `resource_comparison.png` — CPU, memory, RSS, goroutines