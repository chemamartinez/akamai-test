# pprof Collection and Analysis Guide

The pprof (profiling) data tells us **why** certain operations are slow or memory-intensive. It complements the metrics data (which tells us **what** is slow).

Configuration required in `filebeat.yml` (already set in the config templates):

```yaml
http.host: 127.0.0.1
http.port: 5066
http.pprof.enabled: true
http.pprof.block_profile_rate: 1
http.pprof.mem_profile_rate: 1
http.pprof.mutex_profile_rate: 1
```

---

## Available Endpoints

| Profile | URL | Description |
|---------|-----|-------------|
| Index | `http://localhost:5066/debug/pprof/` | All available profiles |
| CPU | `http://localhost:5066/debug/pprof/profile?seconds=N` | CPU sampling for N seconds (blocking) |
| Heap | `http://localhost:5066/debug/pprof/heap` | Heap allocations (in-use and alloc) |
| Goroutines | `http://localhost:5066/debug/pprof/goroutine` | Goroutine stack traces |
| Allocations | `http://localhost:5066/debug/pprof/allocs` | All past allocations (not just live) |
| Block | `http://localhost:5066/debug/pprof/block` | Goroutine blocking events |
| Mutex | `http://localhost:5066/debug/pprof/mutex` | Mutex contention |
| Trace | `http://localhost:5066/debug/pprof/trace?seconds=N` | Execution trace (high overhead) |

---

## Collection Strategy

Profiles are collected automatically by `bin/collect_pprof.sh`. The timing is computed relative to the total run duration.

### Timing formula

Given run duration D seconds:

| Checkpoint | Time | Profile(s) |
|------------|------|-----------|
| Baseline | t = 30s | `heap_baseline.pprof` |
| CPU start | t = D/2 - 30s | (30s blocking collection begins) |
| CPU end = Midpoint | t = D/2 | `cpu_midpoint.pprof` |
| Final | t = D - 15s | `heap_final.pprof`, `block_final.pprof`, `mutex_final.pprof` |

**Example for a 60-minute (3600s) run:**

```
t=30s    → curl -sf http://localhost:5066/debug/pprof/heap -o heap_baseline.pprof
t=1770s  → curl begins 30s CPU collection
t=1800s  → cpu_midpoint.pprof saved (blocking curl returns)
t=3585s  → heap_final.pprof, block_final.pprof, mutex_final.pprof collected
```

**Example for a 10-minute (600s) run:**

```
t=30s  → heap_baseline.pprof
t=270s → CPU collection begins
t=300s → cpu_midpoint.pprof saved
t=585s → heap_final, block_final, mutex_final collected
```

### Manual collection

```bash
# Baseline heap (at start)
curl -sf http://localhost:5066/debug/pprof/heap -o heap_baseline.pprof

# CPU profile (blocks for 30 seconds)
curl -sf "http://localhost:5066/debug/pprof/profile?seconds=30" -o cpu_midpoint.pprof

# Final profiles (near run end)
curl -sf http://localhost:5066/debug/pprof/heap  -o heap_final.pprof
curl -sf http://localhost:5066/debug/pprof/block -o block_final.pprof
curl -sf http://localhost:5066/debug/pprof/mutex -o mutex_final.pprof
```

---

## Analysis Pipeline

Each profile collected by `bin/collect_pprof.sh` is analysed by `analysis/parsers/pprof.py` using `go tool pprof -text`. The table below maps each file to what it captures and the analysis performed on it.

### Files collected per run

| File | When | What it captures |
|------|------|-----------------|
| `heap_baseline.pprof` | t = 30s | Point-in-time snapshot of live heap allocations at run start |
| `cpu_midpoint.pprof` | t = D/2 − 30s … D/2 | 30-second CPU sample window centred at the run midpoint |
| `heap_final.pprof` | t = D − 15s | Point-in-time snapshot of live heap allocations near run end |
| `block_final.pprof` | t = D − 15s | Goroutine blocking events accumulated since run start |
| `mutex_final.pprof` | t = D − 15s | Mutex contention events accumulated since run start |

### Analysis performed on each file

```
heap_baseline ──┐
                ├─ pprof -text -inuse_space -base baseline final  →  heap_growth: which functions grew
heap_final   ───┘

heap_final ────── pprof -text -inuse_space final                  →  heap_final: absolute in-use memory at run end

cpu_midpoint ──── pprof -text cpu_midpoint                        →  cpu: function breakdown for the 30s window

block_final ───── pprof -text block_final                         →  block: goroutine blocking by function
mutex_final ───── pprof -text mutex_final                         →  mutex: mutex contention by function
```

### Comparison axis per profile type

CPU and heap have different comparison axes, which is important for interpreting results:

| Profile | Within-run comparison | Cross-run (CEL vs Akamai) |
|---------|----------------------|--------------------------|
| `heap_baseline` → `heap_final` | Yes — `heap_growth` diff shows memory growth over the run | Yes — compare growth paths between CEL and Akamai |
| `heap_final` (absolute) | No | Yes — compare in-use memory at equivalent point in each run |
| `cpu_midpoint` | No — see below | Yes — primary comparison axis |
| `block_final`, `mutex_final` | No | Yes — compare contention between CEL and Akamai |

---

## Analysis Commands (CLI only, no web UI)

### CPU profile

```bash
# Top 30 functions by CPU flat%
go tool pprof -text -nodecount=30 cpu_midpoint.pprof

# Full interactive session
go tool pprof cpu_midpoint.pprof
# Then: top, list <function>, tree
```

### Heap profile (in-use space)

```bash
# Top 20 by in-use space
go tool pprof -text -inuse_space -nodecount=20 heap_final.pprof

# Top 20 by allocated objects
go tool pprof -text -alloc_objects -nodecount=20 heap_final.pprof
```

### Heap growth (baseline → final diff)

```bash
# Shows memory growth: what grew between start and end of run
go tool pprof -text -inuse_space -base heap_baseline.pprof heap_final.pprof
```

### Block / Mutex contention

```bash
go tool pprof -text -nodecount=20 block_final.pprof
go tool pprof -text -nodecount=20 mutex_final.pprof
```

---

## Key Indicators and What to Look For

### 1. GC Overhead (CPU profile)

**What to check**: What percentage of CPU is consumed by GC functions?

```
GC functions to look for:
  runtime.mallocgc
  runtime.gcBgMarkWorker
  runtime.gcAssistAlloc
  runtime.gcDrain
```

**Threshold**: > 20% combined flat% is considered high.

**Interpretation**:
- High GC in **CEL run**: Expected. CEL evaluation involves heavy allocation — JSON decode + CEL value construction (`ConvertToNative`, `AsMap`) + event construction per cycle.
- High GC in **Akamai run**: Less expected. Akamai native input avoids CEL evaluation overhead. If GC is still high, look at `encoding/json` cost and event struct construction.
- Difference between CEL and Akamai GC → quantifies the CEL evaluation allocation cost.

### 2. JSON Decode vs CEL Boundary Cost (CPU profile)

**What to check**: Time in `encoding/json.*` vs `cel-go.*` / `ConvertToNative` / `AsMap`.

JSON decode cost exists in **both** inputs (both parse the API response body). The CEL input additionally pays the cost of:
- CEL program evaluation (`cel.Program.Eval`)
- Value boundary crossing (`ConvertToNative`, `cel.refVal.ConvertToNative`, `AsMap`)
- State management and cursor update in CEL

The difference in `encoding/json.*` CPU% between CEL and Akamai runs reflects the actual JSON parsing overhead. Any additional CPU in `cel-go.*` functions is pure CEL overhead.

### 3. Heap Growth (heap diff)

**What to check**: Does memory grow significantly from baseline to run end?

```bash
go tool pprof -text -inuse_space -base heap_baseline.pprof heap_final.pprof
```

**Expected pattern (healthy)**:
- Moderate growth (a few MB) is normal — Go's GC allows heap to grow between collections.
- Growth should be bounded and not correlate with run duration.

**Concerning pattern**:
- Sustained linear growth → memory leak.
- Large batch sizes (e.g. 60k events) can push RSS hard even without a leak due to per-batch allocation amplification.

**Rule of thumb**: A 3-minute run is too short to confirm a slow leak. Runs of 60+ minutes with snapshots every 15 minutes give a reliable leak signal.

### 4. Per-Batch Heap Amplification (heap profile)

**What to check**: Does `inuse_space` in payload-processing functions roughly double when batch size doubles?

Expected behavior: Allocating a batch of 60k events uses approximately twice the memory of 30k events (linear scaling). This is not a bug — it's the expected behavior of processing larger batches. If memory does NOT drop after GC after a large batch, that's concerning.

### 5. Lock Contention (block/mutex profiles)

**What to check**: Are there stalls in the block or mutex profiles?

**Expected in this setup** (local file output):
- Minimal Elasticsearch-style network backpressure stalls (no network output).
- If stalls appear, they are more likely to be internal pipeline/queue contention or CEL execution/publish cycle burstiness.

**Functions to watch**:
- Queue lock contention: `libbeat/publisher/queue.*`
- CEL state lock: `input/cel.*`
- Akamai input lock: `input/akamai.*`

---

## Comparison Methodology

The analysis script (`parsers/pprof.py`) runs `go tool pprof -text` and parses the output into structured entries. Comparisons are made by:

1. **GC overhead**: Sum of `flat%` for `{mallocgc, gcBgMarkWorker, gcAssistAlloc}` per run. CEL vs Akamai difference.
2. **JSON decode**: Sum of `flat%` for `encoding/json.*` functions. Both inputs pay this cost; difference should be minimal.
3. **CEL boundary**: Sum of `flat%` for `cel-go.*` / `ConvertToNative` / `AsMap`. Only present in CEL run. Quantifies CEL overhead.
4. **Heap growth diff**: Compare top growth paths between CEL and Akamai `heap_growth` reports.
5. **Contention**: Compare top-N block/mutex entries between runs.

### Generating text-format comparison manually

```bash
# Extract top functions for both runs
go tool pprof -text -nodecount=30 runs/my-run/cel/pprof/cpu_midpoint.pprof > /tmp/cel_cpu.txt
go tool pprof -text -nodecount=30 runs/my-run/akamai/pprof/cpu_midpoint.pprof > /tmp/akamai_cpu.txt

# Compare side by side
diff /tmp/cel_cpu.txt /tmp/akamai_cpu.txt

# Heap growth for each run
go tool pprof -text -inuse_space \
    -base runs/my-run/cel/pprof/heap_baseline.pprof \
    runs/my-run/cel/pprof/heap_final.pprof \
    > /tmp/cel_heap_growth.txt

go tool pprof -text -inuse_space \
    -base runs/my-run/akamai/pprof/heap_baseline.pprof \
    runs/my-run/akamai/pprof/heap_final.pprof \
    > /tmp/akamai_heap_growth.txt
```
