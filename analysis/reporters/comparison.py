"""
comparison.py — Generates a CEL vs Akamai side-by-side comparison report.

Reads summary.json from each sub-run's analysis/ directory and produces:
  - comparison_report.md
  - comparison_data.json
  - plots/ directory (throughput, latency, resource, input timing PNGs)
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt(value: Any, suffix: str = "", precision: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{precision}f}{suffix}"
    return f"{value}{suffix}"


def _winner(cel_val: Optional[float], akamai_val: Optional[float],
            lower_is_better: bool = True) -> str:
    if cel_val is None or akamai_val is None:
        return "N/A"
    if abs(cel_val - akamai_val) < 0.01 * max(abs(cel_val), abs(akamai_val), 1):
        return "Tie"
    if lower_is_better:
        return "CEL" if cel_val < akamai_val else "Akamai"
    return "CEL" if cel_val > akamai_val else "Akamai"


def _pct_diff(cel_val: Optional[float], akamai_val: Optional[float]) -> str:
    """Show Akamai relative to CEL: positive = Akamai is higher."""
    if cel_val is None or akamai_val is None or cel_val == 0:
        return "N/A"
    diff = (akamai_val - cel_val) / abs(cel_val) * 100
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.1f}%"


def _hist_comparison_rows(
    cel_hist: Optional[Dict],
    akamai_hist: Optional[Dict],
    metric_name: str,
) -> list:
    """Generate markdown table rows comparing two histograms."""
    rows = []
    for pct in ("mean", "p75", "p95", "p99", "max"):
        c = cel_hist.get(pct) if cel_hist else None
        a = akamai_hist.get(pct) if akamai_hist else None
        rows.append(
            f"| {metric_name} {pct} "
            f"| {_fmt(c)} ms "
            f"| {_fmt(a)} ms "
            f"| {_pct_diff(c, a)} "
            f"| {_winner(c, a, lower_is_better=True)} |"
        )
    return rows


# ── Main comparison function ───────────────────────────────────────────────────

def run_comparison(
    run_dir: Path,
    run_config: Dict[str, Any],
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Generate comparison report from two completed single-run analyses.

    Args:
        run_dir:    Path to runs/my-run/ (containing cel/ and akamai/ subdirs)
        run_config: Parsed run_config.json
        output_dir: Where to write outputs (default: run_dir/comparison/)
    """
    if output_dir is None:
        output_dir = run_dir / "comparison"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "plots").mkdir(exist_ok=True)

    # Load both summaries
    cel_summary = _load_summary(run_dir / "cel" / "analysis" / "summary.json")
    akamai_summary = _load_summary(run_dir / "akamai" / "analysis" / "summary.json")

    if not cel_summary and not akamai_summary:
        raise FileNotFoundError(
            "Neither cel nor akamai analysis/summary.json found. "
            "Run 'analyze.py single' for each run first."
        )

    params = run_config.get("parameters", {})
    comparison_data = _build_comparison_data(cel_summary, akamai_summary)

    # Write comparison_data.json
    (output_dir / "comparison_data.json").write_text(
        json.dumps(comparison_data, indent=2, default=str)
    )

    # Generate plots
    if HAS_MATPLOTLIB:
        _plot_comparisons(cel_summary, akamai_summary, output_dir / "plots")

    # Write comparison_report.md
    report = _build_report_md(comparison_data, cel_summary, akamai_summary, params, output_dir)
    (output_dir / "comparison_report.md").write_text(report)

    return comparison_data


def _load_summary(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _safe_get(summary: Optional[Dict], *keys) -> Any:
    if not summary:
        return None
    d = summary
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _build_comparison_data(
    cel: Optional[Dict[str, Any]],
    akamai: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a machine-readable comparison dict."""

    def c(*keys):
        return _safe_get(cel, *keys)

    def a(*keys):
        return _safe_get(akamai, *keys)

    return {
        "throughput": {
            "cel_events_published": c("input_metrics", "throughput", "total_events_published"),
            "akamai_events_published": a("input_metrics", "throughput", "total_events_published"),
            "cel_avg_eps_log": c("monitoring", "throughput", "avg_eps"),
            "akamai_avg_eps_log": a("monitoring", "throughput", "avg_eps"),
            "cel_http_success_rate_pct": c("input_metrics", "throughput", "http_success_rate_pct"),
            "akamai_http_success_rate_pct": a("input_metrics", "throughput", "http_success_rate_pct"),
        },
        "latency": {
            "cel_http_rtt_ms": c("input_metrics", "histograms", "http_round_trip_time_ms"),
            "akamai_http_rtt_ms": a("input_metrics", "histograms", "http_round_trip_time_ms"),
            "cel_batch_processing_ms": c("input_metrics", "histograms", "batch_processing_time_ms"),
            "akamai_batch_processing_ms": a("input_metrics", "histograms", "batch_processing_time_ms"),
            "cel_cel_processing_ms": c("input_metrics", "histograms", "cel_processing_time_ms"),
            "akamai_response_latency_ms": a("input_metrics", "histograms", "response_latency_ms"),
        },
        "resources": {
            "cel_avg_rss_mb": c("monitoring", "resources", "avg_rss_mb"),
            "akamai_avg_rss_mb": a("monitoring", "resources", "avg_rss_mb"),
            "cel_max_rss_mb": c("monitoring", "resources", "max_rss_mb"),
            "akamai_max_rss_mb": a("monitoring", "resources", "max_rss_mb"),
            "cel_avg_memory_alloc_mb": c("monitoring", "resources", "avg_memory_alloc_mb"),
            "akamai_avg_memory_alloc_mb": a("monitoring", "resources", "avg_memory_alloc_mb"),
            "cel_avg_goroutines": c("monitoring", "resources", "avg_goroutines"),
            "akamai_avg_goroutines": a("monitoring", "resources", "avg_goroutines"),
            "cel_avg_load_norm_1": c("monitoring", "resources", "avg_load_norm_1"),
            "akamai_avg_load_norm_1": a("monitoring", "resources", "avg_load_norm_1"),
        },
        "pprof": {
            "cel_gc_overhead_pct": c("pprof_summary", "cpu_gc_flat_pct"),
            "akamai_gc_overhead_pct": a("pprof_summary", "cpu_gc_flat_pct"),
            "cel_json_decode_pct": c("pprof_summary", "cpu_json_decode_pct"),
            "akamai_json_decode_pct": a("pprof_summary", "cpu_json_decode_pct"),
        },
        "akamai_reliability": {
            "offset_expired": a("input_metrics", "akamai", "offset_expired_total"),
            "hmac_refresh": a("input_metrics", "akamai", "hmac_refresh_total"),
            "cursor_drops": a("input_metrics", "akamai", "cursor_drops_total"),
            "api_400_fatal": a("input_metrics", "akamai", "api_400_fatal_total"),
            "worker_utilization": a("input_metrics", "akamai", "worker_utilization"),
        },
    }


def _build_report_md(
    data: Dict[str, Any],
    cel: Optional[Dict],
    akamai: Optional[Dict],
    params: Dict[str, Any],
    output_dir: Path,
) -> str:
    lines = [
        "# CEL vs Akamai — Performance Comparison Report\n",
        "## Test Parameters\n",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Duration | {params.get('duration', 'N/A')} |",
        f"| Interval | {params.get('interval', 'N/A')} |",
        f"| Initial interval | {params.get('initial_interval', 'N/A')} |",
        f"| Event limit | {params.get('event_limit', 'N/A')} |",
        "",
        "> **Note**: Runs are sequential (CEL first, then Akamai) using the same parameters.",
        "> Minor differences in API server state or network conditions may affect results.",
        "",
        "---",
        "",
        "## Executive Summary\n",
    ]

    t = data["throughput"]
    r = data["resources"]
    p = data["pprof"]

    cel_events = t.get("cel_events_published")
    ak_events = t.get("akamai_events_published")
    cel_rtt_mean = _safe_get(data, "latency", "cel_http_rtt_ms", "mean")
    ak_rtt_mean = _safe_get(data, "latency", "akamai_http_rtt_ms", "mean")
    cel_batch_mean = _safe_get(data, "latency", "cel_batch_processing_ms", "mean")
    ak_batch_mean = _safe_get(data, "latency", "akamai_batch_processing_ms", "mean")

    lines += [
        f"| Metric | CEL | Akamai | Δ (Akamai vs CEL) | Better |",
        f"|--------|-----|--------|-------------------|--------|",
        f"| Total events published | {_fmt(cel_events)} | {_fmt(ak_events)} | {_pct_diff(cel_events, ak_events)} | {_winner(cel_events, ak_events, lower_is_better=False)} |",
        f"| Avg EPS (monitoring log) | {_fmt(t.get('cel_avg_eps_log'))} | {_fmt(t.get('akamai_avg_eps_log'))} | {_pct_diff(t.get('cel_avg_eps_log'), t.get('akamai_avg_eps_log'))} | {_winner(t.get('cel_avg_eps_log'), t.get('akamai_avg_eps_log'), lower_is_better=False)} |",
        f"| HTTP RTT mean | {_fmt(cel_rtt_mean)} ms | {_fmt(ak_rtt_mean)} ms | {_pct_diff(cel_rtt_mean, ak_rtt_mean)} | {_winner(cel_rtt_mean, ak_rtt_mean)} |",
        f"| Batch processing mean | {_fmt(cel_batch_mean)} ms | {_fmt(ak_batch_mean)} ms | {_pct_diff(cel_batch_mean, ak_batch_mean)} | {_winner(cel_batch_mean, ak_batch_mean)} |",
        f"| GC overhead (CPU%) | {_fmt(p.get('cel_gc_overhead_pct'), '%')} | {_fmt(p.get('akamai_gc_overhead_pct'), '%')} | {_pct_diff(p.get('cel_gc_overhead_pct'), p.get('akamai_gc_overhead_pct'))} | {_winner(p.get('cel_gc_overhead_pct'), p.get('akamai_gc_overhead_pct'))} |",
        f"| Avg memory alloc | {_fmt(r.get('cel_avg_memory_alloc_mb'))} MB | {_fmt(r.get('akamai_avg_memory_alloc_mb'))} MB | {_pct_diff(r.get('cel_avg_memory_alloc_mb'), r.get('akamai_avg_memory_alloc_mb'))} | {_winner(r.get('cel_avg_memory_alloc_mb'), r.get('akamai_avg_memory_alloc_mb'))} |",
        f"| Max RSS | {_fmt(r.get('cel_max_rss_mb'))} MB | {_fmt(r.get('akamai_max_rss_mb'))} MB | {_pct_diff(r.get('cel_max_rss_mb'), r.get('akamai_max_rss_mb'))} | {_winner(r.get('cel_max_rss_mb'), r.get('akamai_max_rss_mb'))} |",
        f"| Avg goroutines | {_fmt(r.get('cel_avg_goroutines'))} | {_fmt(r.get('akamai_avg_goroutines'))} | {_pct_diff(r.get('cel_avg_goroutines'), r.get('akamai_avg_goroutines'))} | {_winner(r.get('cel_avg_goroutines'), r.get('akamai_avg_goroutines'))} |",
        "",
        "---",
        "",
        "## Throughput Comparison\n",
        f"| Metric | CEL | Akamai | Δ |",
        f"|--------|-----|--------|---|",
        f"| Total events published (/inputs/) | {_fmt(t.get('cel_events_published'))} | {_fmt(t.get('akamai_events_published'))} | {_pct_diff(t.get('cel_events_published'), t.get('akamai_events_published'))} |",
        f"| Avg EPS (monitoring log) | {_fmt(t.get('cel_avg_eps_log'))} | {_fmt(t.get('akamai_avg_eps_log'))} | {_pct_diff(t.get('cel_avg_eps_log'), t.get('akamai_avg_eps_log'))} |",
        f"| HTTP success rate | {_fmt(t.get('cel_http_success_rate_pct'), '%')} | {_fmt(t.get('akamai_http_success_rate_pct'), '%')} | — |",
        "",
        "---",
        "",
        "## Latency Comparison\n",
        "### HTTP Round Trip Time (shared metric)\n",
        f"| Percentile | CEL | Akamai | Δ | Better |",
        f"|------------|-----|--------|---|--------|",
    ]

    cel_rtt = _safe_get(data, "latency", "cel_http_rtt_ms") or {}
    ak_rtt = _safe_get(data, "latency", "akamai_http_rtt_ms") or {}
    for pct in ("mean", "p75", "p95", "p99", "max"):
        c_v = cel_rtt.get(pct)
        a_v = ak_rtt.get(pct)
        lines.append(
            f"| {pct} | {_fmt(c_v)} ms | {_fmt(a_v)} ms "
            f"| {_pct_diff(c_v, a_v)} | {_winner(c_v, a_v)} |"
        )

    lines += [
        "",
        "### Batch Processing Time — receipt to pipeline ACK (shared metric)\n",
        f"| Percentile | CEL | Akamai | Δ | Better |",
        f"|------------|-----|--------|---|--------|",
    ]

    cel_bp = _safe_get(data, "latency", "cel_batch_processing_ms") or {}
    ak_bp = _safe_get(data, "latency", "akamai_batch_processing_ms") or {}
    for pct in ("mean", "p75", "p95", "p99", "max"):
        c_v = cel_bp.get(pct)
        a_v = ak_bp.get(pct)
        lines.append(
            f"| {pct} | {_fmt(c_v)} ms | {_fmt(a_v)} ms "
            f"| {_pct_diff(c_v, a_v)} | {_winner(c_v, a_v)} |"
        )

    lines += [
        "",
        "### Input-Specific Timing\n",
        "> **CEL Processing Time** = HTTP RTT + response parsing + CEL evaluation.",
        "> **Akamai Response Latency** = purely HTTP response time (no CEL overhead).",
        "> These measure different things — use HTTP Round Trip Time for direct apples-to-apples comparison.",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
    ]

    cel_cel = _safe_get(data, "latency", "cel_cel_processing_ms") or {}
    ak_rl = _safe_get(data, "latency", "akamai_response_latency_ms") or {}
    lines.append(f"| CEL: cel_processing_time mean | {_fmt(cel_cel.get('mean'))} ms |")
    lines.append(f"| CEL: cel_processing_time p99  | {_fmt(cel_cel.get('p99'))} ms |")
    lines.append(f"| Akamai: response_latency mean | {_fmt(ak_rl.get('mean'))} ms |")
    lines.append(f"| Akamai: response_latency p99  | {_fmt(ak_rl.get('p99'))} ms |")

    lines += [
        "",
        "---",
        "",
        "## Resource Usage Comparison\n",
        f"| Metric | CEL | Akamai | Δ | Better |",
        f"|--------|-----|--------|---|--------|",
        f"| Avg memory alloc | {_fmt(r.get('cel_avg_memory_alloc_mb'))} MB | {_fmt(r.get('akamai_avg_memory_alloc_mb'))} MB | {_pct_diff(r.get('cel_avg_memory_alloc_mb'), r.get('akamai_avg_memory_alloc_mb'))} | {_winner(r.get('cel_avg_memory_alloc_mb'), r.get('akamai_avg_memory_alloc_mb'))} |",
        f"| Max memory alloc | — | — | — | — |",
        f"| Avg RSS | {_fmt(r.get('cel_avg_rss_mb'))} MB | {_fmt(r.get('akamai_avg_rss_mb'))} MB | {_pct_diff(r.get('cel_avg_rss_mb'), r.get('akamai_avg_rss_mb'))} | {_winner(r.get('cel_avg_rss_mb'), r.get('akamai_avg_rss_mb'))} |",
        f"| Max RSS | {_fmt(r.get('cel_max_rss_mb'))} MB | {_fmt(r.get('akamai_max_rss_mb'))} MB | {_pct_diff(r.get('cel_max_rss_mb'), r.get('akamai_max_rss_mb'))} | {_winner(r.get('cel_max_rss_mb'), r.get('akamai_max_rss_mb'))} |",
        f"| Avg goroutines | {_fmt(r.get('cel_avg_goroutines'))} | {_fmt(r.get('akamai_avg_goroutines'))} | {_pct_diff(r.get('cel_avg_goroutines'), r.get('akamai_avg_goroutines'))} | {_winner(r.get('cel_avg_goroutines'), r.get('akamai_avg_goroutines'))} |",
        f"| Avg normalized load | {_fmt(r.get('cel_avg_load_norm_1'))} | {_fmt(r.get('akamai_avg_load_norm_1'))} | {_pct_diff(r.get('cel_avg_load_norm_1'), r.get('akamai_avg_load_norm_1'))} | {_winner(r.get('cel_avg_load_norm_1'), r.get('akamai_avg_load_norm_1'))} |",
        "",
        "---",
        "",
        "## pprof Deep Dive\n",
        "### GC Pressure\n",
        f"| Metric | CEL | Akamai | Δ |",
        f"|--------|-----|--------|---|",
        f"| GC overhead (CPU flat%) | {_fmt(p.get('cel_gc_overhead_pct'), '%')} | {_fmt(p.get('akamai_gc_overhead_pct'), '%')} | {_pct_diff(p.get('cel_gc_overhead_pct'), p.get('akamai_gc_overhead_pct'))} |",
        f"| JSON decode (CPU flat%) | {_fmt(p.get('cel_json_decode_pct'), '%')} | {_fmt(p.get('akamai_json_decode_pct'), '%')} | {_pct_diff(p.get('cel_json_decode_pct'), p.get('akamai_json_decode_pct'))} |",
        "",
        "> GC overhead > 20% indicates allocation-heavy paths (JSON decode, CEL eval, event publish).",
        "",
        "### Per-Run pprof Reports\n",
        "See individual run reports for full top-N function tables:",
        "- `cel/analysis/pprof_report.txt`",
        "- `akamai/analysis/pprof_report.txt`",
        "",
        "---",
        "",
        "## Akamai Reliability Indicators\n",
    ]

    rel = data.get("akamai_reliability", {})
    lines += [
        f"| Indicator | Count | Interpretation |",
        f"|-----------|-------|----------------|",
        f"| offset_expired | {_fmt(rel.get('offset_expired'))} | API offset stale (416). Expected if run exceeds offset TTL (120s). |",
        f"| hmac_refresh | {_fmt(rel.get('hmac_refresh'))} | Auth clock-skew retries. Non-zero = clock drift between client/server. |",
        f"| cursor_drops | {_fmt(rel.get('cursor_drops'))} | Offset cleared; chain window replayed from scratch. |",
        f"| api_400_fatal | {_fmt(rel.get('api_400_fatal'))} | Non-recoverable 400 errors. Non-zero = data loss. |",
        f"| worker_utilization | {_fmt(rel.get('worker_utilization'), '%')} | % of time workers were busy (0–1). |",
        "",
        "---",
        "",
        "## Issues Summary\n",
    ]

    cel_issues = _safe_get(cel, "monitoring", "issues") or []
    cel_issues += _safe_get(cel, "input_metrics", "issues") or []
    ak_issues = _safe_get(akamai, "monitoring", "issues") or []
    ak_issues += _safe_get(akamai, "input_metrics", "issues") or []

    if cel_issues:
        lines.append("**CEL run issues:**")
        for i in cel_issues:
            lines.append(f"- ⚠️  {i}")
        lines.append("")
    else:
        lines.append("**CEL run issues:** None detected\n")

    if ak_issues:
        lines.append("**Akamai run issues:**")
        for i in ak_issues:
            lines.append(f"- ⚠️  {i}")
        lines.append("")
    else:
        lines.append("**Akamai run issues:** None detected\n")

    lines += [
        "---",
        "",
        "## Conclusions\n",
        _generate_conclusions(data, params),
    ]

    # Mention plots if generated
    if HAS_MATPLOTLIB:
        lines += [
            "",
            "## Visualizations\n",
            "Generated plots in `comparison/plots/`:",
            "- `throughput_comparison.png` — events published over time",
            "- `latency_comparison.png` — HTTP RTT and batch processing percentiles",
            "- `resource_comparison.png` — CPU, memory, RSS, goroutines",
        ]

    return "\n".join(lines)


def _generate_conclusions(data: Dict[str, Any], params: Dict[str, Any]) -> str:
    lines = []
    t = data["throughput"]
    lat = data["latency"]
    r = data["resources"]
    p = data["pprof"]

    cel_eps = t.get("cel_avg_eps_log")
    ak_eps = t.get("akamai_avg_eps_log")
    if cel_eps and ak_eps:
        w = "Akamai" if ak_eps > cel_eps else "CEL"
        diff = abs(ak_eps - cel_eps) / max(cel_eps, 1) * 100
        lines.append(f"1. **Throughput**: {w} achieved higher average EPS ({diff:.1f}% difference). "
                     f"CEL: {cel_eps:.1f} EPS, Akamai: {ak_eps:.1f} EPS.")
    else:
        lines.append("1. **Throughput**: Insufficient data for comparison.")

    cel_rtt = (lat.get("cel_http_rtt_ms") or {}).get("mean")
    ak_rtt = (lat.get("akamai_http_rtt_ms") or {}).get("mean")
    if cel_rtt and ak_rtt:
        w = "Akamai" if ak_rtt < cel_rtt else "CEL"
        diff = abs(ak_rtt - cel_rtt)
        lines.append(f"2. **HTTP Latency**: {w} had lower HTTP RTT (Δ mean = {diff:.0f} ms).")
    else:
        lines.append("2. **HTTP Latency**: Insufficient data.")

    cel_batch = (lat.get("cel_batch_processing_ms") or {}).get("mean")
    ak_batch = (lat.get("akamai_batch_processing_ms") or {}).get("mean")
    if cel_batch and ak_batch:
        w = "Akamai" if ak_batch < cel_batch else "CEL"
        diff = abs(ak_batch - cel_batch)
        lines.append(f"3. **Batch Processing Time** (receipt→ACK): {w} was faster (Δ mean = {diff:.0f} ms). "
                     "A higher value for CEL may indicate CEL evaluation adds publishing latency.")
    else:
        lines.append("3. **Batch Processing Time**: Insufficient data.")

    cel_gc = p.get("cel_gc_overhead_pct")
    ak_gc = p.get("akamai_gc_overhead_pct")
    if cel_gc is not None and ak_gc is not None:
        gc_note = " (above 20% threshold)" if cel_gc > 20 else ""
        lines.append(f"4. **GC Pressure**: CEL GC overhead = {cel_gc:.1f}%{gc_note}, "
                     f"Akamai = {ak_gc:.1f}%. "
                     "Higher CEL GC is expected due to CEL expression evaluation and value conversion allocations.")
    else:
        lines.append("4. **GC Pressure**: pprof data not available.")

    cel_rss = r.get("cel_max_rss_mb")
    ak_rss = r.get("akamai_max_rss_mb")
    if cel_rss and ak_rss:
        w = "Akamai" if ak_rss < cel_rss else "CEL"
        lines.append(f"5. **Memory**: {w} used less RSS at peak ({cel_rss:.0f} MB vs {ak_rss:.0f} MB).")
    else:
        lines.append("5. **Memory**: Insufficient data.")

    lines.append("6. **Recommendation**: Based on the above, review the latency and GC overhead "
                 "differences to determine whether the Akamai native input provides sufficient "
                 "improvement to justify migration from the CEL implementation.")

    return "\n".join(lines)


# ── Visualization ──────────────────────────────────────────────────────────────

def _plot_comparisons(
    cel: Optional[Dict[str, Any]],
    akamai: Optional[Dict[str, Any]],
    plots_dir: Path,
) -> None:
    """Generate comparison PNG plots."""
    _plot_latency_bars(cel, akamai, plots_dir)
    _plot_resource_bars(cel, akamai, plots_dir)


def _plot_latency_bars(
    cel: Optional[Dict[str, Any]],
    akamai: Optional[Dict[str, Any]],
    plots_dir: Path,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Latency Comparison: CEL vs Akamai", fontsize=13)

    percentiles = ["mean", "p75", "p95", "p99", "max"]
    x = range(len(percentiles))
    width = 0.35

    for ax, (metric_key_cel, metric_key_ak, title) in zip(axes, [
        ("http_round_trip_time_ms", "http_round_trip_time_ms", "HTTP Round Trip Time (ms)"),
        ("batch_processing_time_ms", "batch_processing_time_ms", "Batch Processing Time (ms)"),
    ]):
        cel_hist = _safe_get(cel, "input_metrics", "histograms", metric_key_cel) or {}
        ak_hist = _safe_get(akamai, "input_metrics", "histograms", metric_key_ak) or {}

        cel_vals = [cel_hist.get(p) or 0 for p in percentiles]
        ak_vals = [ak_hist.get(p) or 0 for p in percentiles]

        bars1 = ax.bar([i - width / 2 for i in x], cel_vals, width, label="CEL", color="#4A90D9")
        bars2 = ax.bar([i + width / 2 for i in x], ak_vals, width, label="Akamai", color="#E8784D")

        ax.set_title(title)
        ax.set_xticks(list(x))
        ax.set_xticklabels(percentiles)
        ax.set_ylabel("ms")
        ax.legend()

    plt.tight_layout()
    plt.savefig(plots_dir / "latency_comparison.png", dpi=120)
    plt.close(fig)


def _plot_resource_bars(
    cel: Optional[Dict[str, Any]],
    akamai: Optional[Dict[str, Any]],
    plots_dir: Path,
) -> None:
    metrics = [
        ("avg_rss_mb", "Avg RSS (MB)"),
        ("max_rss_mb", "Max RSS (MB)"),
        ("avg_memory_alloc_mb", "Avg Memory Alloc (MB)"),
        ("avg_goroutines", "Avg Goroutines"),
    ]

    labels = [m[1] for m in metrics]
    cel_vals = [_safe_get(cel, "monitoring", "resources", m[0]) or 0 for m in metrics]
    ak_vals = [_safe_get(akamai, "monitoring", "resources", m[0]) or 0 for m in metrics]

    x = range(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar([i - width / 2 for i in x], cel_vals, width, label="CEL", color="#4A90D9")
    ax.bar([i + width / 2 for i in x], ak_vals, width, label="Akamai", color="#E8784D")
    ax.set_title("Resource Usage Comparison")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.legend()
    plt.tight_layout()
    plt.savefig(plots_dir / "resource_comparison.png", dpi=120)
    plt.close(fig)
