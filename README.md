# Akamai Filebeat Performance Test Suite

Automated test runner to compare the performance of Filebeat's **CEL input** vs the native **Akamai input** when collecting events from the Akamai SIEM API.

## Overview

The runner executes Filebeat sequentially with each input type, collects three kinds of metrics during each run, and generates a side-by-side comparison report.

```
┌──────────────────────────────────────────────────────────────┐
│  run_tests.sh                                                │
│                                                              │
│  ┌─────────────┐        ┌───────────────┐                    │
│  │  CEL Input  │        │ Akamai Input  │                    │
│  │  (N minutes)│        │ (N minutes)   │                    │
│  └─────────────┘        └───────────────┘                    │
│         │                       │                            │
│  ┌──────┴───────────────────────┴──────┐                     │
│  │  3 metric streams (per run):        │                     │
│  │  1. Monitoring logs (log files)     │                     │
│  │  2. Input metrics (/inputs/ API)    │                     │
│  │  3. pprof profiles (at checkpoints) │                     │
│  └─────────────────────────────────────┘                     │
│         │                                                    │
│  ┌──────▼───────────────────┐                                │
│  │  analyze.py compare      │                                │
│  │  → comparison_report.md  │                                │
│  └──────────────────────────┘                                │
│         │                                                    │
│  ┌──────▼──────────────────────────────┐    (optional)       │
│  │  analyze.py ai-analyze              │◄── ANTHROPIC_API_KEY│
│  │  → final_analysis.md                │                     │
│  └─────────────────────────────────────┘                     │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Build Filebeat

```bash
cd ../beats-akamai/x-pack/filebeat
mage build
```

### 3. Run the tests

```bash
cd akamai-test
./bin/run_tests.sh \
    --akamai-url "https://your-host.akamai.com" \
    --client-token "akab-..." \
    --client-secret "your-client-secret" \
    --access-token "akab-..." \
    --duration 60m \
    --interval 5m \
    --initial-interval 1h \
    --event-limit 10000 \
    --akamai-workers 1 \
    --akamai-batch-size 1000
```

Results will be written to `runs/<run-name>/comparison/comparison_report.md`.

If `ANTHROPIC_API_KEY` is set, an additional AI-driven analysis is written to `runs/<run-name>/comparison/final_analysis.md`.

## Entry Point Options

```
Usage: ./bin/run_tests.sh [OPTIONS]

Required:
  --akamai-url URL          Akamai API base URL (e.g. https://host.akamai.com)
  --client-token TOKEN      Akamai client token
  --client-secret SECRET    Akamai client secret
  --access-token TOKEN      Akamai access token

Run control:
  --duration DURATION       How long each Filebeat run lasts. Default: 60m
                            Format: <N>m (minutes) or <N>s (seconds)
  --interval INTERVAL       Filebeat polling interval. Default: 5m
  --initial-interval INIT   Lookback window for first run. Default: 1h
  --event-limit LIMIT       Max events per API call. Default: 10000
  --akamai-workers N        Number of Akamai worker goroutines. Default: 1
                            (Akamai input only)
  --akamai-batch-size N     Events per internal batch. Default: 1000
                            (Akamai input only)
  --input-type TYPE         Which inputs to test: cel | akamai | both. Default: both
  --run-name NAME           Name for this test run. Default: ISO8601 timestamp

Paths:
  --filebeat-binary PATH    Path to filebeat binary.
                            Default: ../beats-akamai/x-pack/filebeat/filebeat
```

## Run Output Layout

```
runs/
└── 2026-03-01T14-30-00/
    ├── run_config.json          # Parameters used
    ├── run.log                  # Orchestration log
    ├── cel/
    │   ├── logs/                # Filebeat log files (JSON metrics every 1m)
    │   ├── filebeat_output/     # Filebeat output.file events
    │   ├── input_metrics/       # t0060.json, t0120.json, ... (from /inputs/ API)
    │   ├── pprof/               # heap_baseline, cpu_midpoint, heap/block/mutex_final
    │   └── analysis/            # summary.json, report.md, CSVs, pprof_report.txt
    ├── akamai/
    │   └── (same structure as cel/)
    └── comparison/
        ├── comparison_report.md
        ├── comparison_data.json
        ├── final_analysis.md    # AI-driven analysis (if ANTHROPIC_API_KEY was set)
        └── plots/               # PNG visualizations
```

## Optional: AI-Driven Analysis

The suite can optionally call the Claude API to produce an expert narrative analysis that goes beyond the algorithmic comparison. It applies domain knowledge from the `specs/` files to reason holistically across all signals: throughput, latency, pprof, GC overhead, and Akamai reliability indicators.

**Output**: `runs/<run-name>/comparison/final_analysis.md`

**Contents**: Executive Verdict, Throughput Analysis, Latency Deep Dive, Memory and CPU Analysis, pprof Interpretation, Akamai Reliability Assessment, Root Cause Hypotheses, Recommendations, Suggested Follow-up Tests.

**Model used**: `claude-opus-4-6`

### Enable AI analysis

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./bin/run_tests.sh ...   # AI analysis runs automatically after comparison
```

The step is silently skipped if `ANTHROPIC_API_KEY` is not set.

### Run AI analysis manually on an existing run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python analysis/analyze.py ai-analyze \
    --run-dir runs/my-run/ \
    --run-config runs/my-run/run_config.json
```

## Manual Analysis

You can also run analysis separately:

```bash
# Analyze a single run
python analysis/analyze.py single \
    --run-dir runs/my-run/cel/ \
    --input-type cel \
    --run-config runs/my-run/run_config.json

# Compare two completed runs
python analysis/analyze.py compare \
    --run-dir runs/my-run/ \
    --run-config runs/my-run/run_config.json
```

## Hardcoded API Server Parameters

The following parameters reflect characteristics of the Akamai SIEM test API server and are not configurable via CLI:

- **Offset TTL**: 120 seconds (offset token validity on the API server side)
- **HMAC validity**: Auth signature lifetime (server-side)
- **API EPS target**: The rate at which the test server delivers events

These are documented in `specs/COMPARISON_METHODOLOGY.md`.

## Documentation

| File | Description |
|------|-------------|
| [specs/METRICS.md](specs/METRICS.md) | Complete field catalog for all 3 metric types |
| [specs/PPROF_ANALYSIS.md](specs/PPROF_ANALYSIS.md) | pprof collection strategy and analysis guide |
| [specs/COMPARISON_METHODOLOGY.md](specs/COMPARISON_METHODOLOGY.md) | How CEL vs Akamai comparison works |
| [specs/INPUT_SCHEMAS.md](specs/INPUT_SCHEMAS.md) | `/inputs/` endpoint JSON schema reference |

## Prerequisites

- `go` in PATH (for `go tool pprof` analysis)
- `curl` in PATH
- Python 3.9+ with `pandas`, `matplotlib`, and `anthropic` (`pip install -r requirements.txt`)
- Filebeat binary built from `beats-akamai`
- `ANTHROPIC_API_KEY` environment variable — **optional**, only needed for AI-driven analysis
