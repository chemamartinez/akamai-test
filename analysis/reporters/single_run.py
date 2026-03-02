"""
single_run.py — Generates analysis output for a single Filebeat run.

Reads:
  - <run_dir>/logs/        (monitoring log files)
  - <run_dir>/input_metrics/  (t<elapsed>.json snapshot files)
  - <run_dir>/pprof/       (pprof profiles)
  - run_config.json        (test parameters)

Writes to <run_dir>/analysis/:
  - summary.json           (machine-readable combined summary)
  - monitoring_metrics.csv (raw snapshot data)
  - input_metrics.csv      (per-interval deltas)
  - pprof_report.txt       (human-readable pprof analysis)
  - report.md              (human-readable single-run report)
"""

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from analysis.parsers.monitoring_log import FilebeatMonitoringLogParser, MonitoringMetricsAnalyzer
from analysis.parsers.input_metrics import load_snapshots, compute_deltas, summarize
from analysis.parsers.pprof import analyze_pprof_dir, format_pprof_report


def _bytes_to_mb(b: Optional[float]) -> Optional[float]:
    if b is None:
        return None
    return round(b / 1024 / 1024, 2)


def run_single_analysis(
    run_dir: Path,
    input_type: str,
    run_config: Dict[str, Any],
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Analyse a single run directory. Returns the combined summary dict.

    Args:
        run_dir:    Path to e.g. runs/my-run/cel/
        input_type: "cel" or "akamai"
        run_config: Parsed run_config.json
        output_dir: Where to write analysis outputs (default: run_dir/analysis/)
    """
    if output_dir is None:
        output_dir = run_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)

    params = run_config.get("parameters", {})

    # ── 1. Monitoring log ────────────────────────────────────────────────────
    log_dir = run_dir / "logs"
    monitoring_summary: Dict[str, Any] = {}
    monitoring_csv_data = []

    if log_dir.exists():
        parser = FilebeatMonitoringLogParser(log_dir)
        snapshots = parser.parse()
        if snapshots:
            analyzer = MonitoringMetricsAnalyzer(snapshots, parser.final_metrics)
            monitoring_summary = analyzer.get_summary()

            # Write monitoring_metrics.csv
            monitoring_csv_data = [asdict(s) for s in snapshots]
            if monitoring_csv_data:
                csv_path = output_dir / "monitoring_metrics.csv"
                with open(csv_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=monitoring_csv_data[0].keys())
                    writer.writeheader()
                    writer.writerows(monitoring_csv_data)
        else:
            monitoring_summary = {"warning": "no_monitoring_snapshots_found"}
    else:
        monitoring_summary = {"warning": "log_dir_not_found"}

    # ── 2. Input metrics ────────────────────────────────────────────────────
    input_metrics_dir = run_dir / "input_metrics"
    input_summary: Dict[str, Any] = {}
    input_deltas: list = []

    if input_metrics_dir.exists():
        snapshots_im = load_snapshots(input_metrics_dir, input_type)
        if snapshots_im:
            input_summary = summarize(snapshots_im, input_type)
            input_deltas = compute_deltas(snapshots_im, input_type)

            # Write input_metrics.csv (per-interval deltas)
            if input_deltas:
                csv_path = output_dir / "input_metrics.csv"
                with open(csv_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=input_deltas[0].keys())
                    writer.writeheader()
                    writer.writerows(input_deltas)
        else:
            input_summary = {"warning": "no_input_metric_snapshots_found"}
    else:
        input_summary = {"warning": "input_metrics_dir_not_found"}

    # ── 3. pprof analysis ──────────────────────────────────────────────────
    pprof_dir = run_dir / "pprof"
    pprof_results: Dict[str, Any] = {}
    pprof_report_text = ""

    if pprof_dir.exists():
        pprof_results = analyze_pprof_dir(pprof_dir)
        if pprof_results:
            pprof_report_text = format_pprof_report(pprof_results, input_type)
            (output_dir / "pprof_report.txt").write_text(pprof_report_text)
        else:
            pprof_report_text = "No pprof profiles found or go tool pprof not available."

    # ── 4. Combine into summary.json ─────────────────────────────────────
    summary = {
        "input_type": input_type,
        "run_config": run_config,
        "monitoring": monitoring_summary,
        "input_metrics": input_summary,
        "pprof_summary": pprof_results.get("summary", {}),
    }

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    # ── 5. Write report.md ───────────────────────────────────────────────
    report = _build_report_md(summary, input_type, pprof_report_text, params)
    (output_dir / "report.md").write_text(report)

    return summary


def _fmt(value: Any, suffix: str = "", precision: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{precision}f}{suffix}"
    return f"{value}{suffix}"


def _hist_row(hist: Optional[Dict[str, Any]], label: str) -> str:
    if not hist:
        return f"| {label} | N/A | N/A | N/A | N/A | N/A |"
    return (
        f"| {label} "
        f"| {_fmt(hist.get('mean'))} ms "
        f"| {_fmt(hist.get('p75'))} ms "
        f"| {_fmt(hist.get('p95'))} ms "
        f"| {_fmt(hist.get('p99'))} ms "
        f"| {_fmt(hist.get('max'))} ms |"
    )


def _build_report_md(
    summary: Dict[str, Any],
    input_type: str,
    pprof_text: str,
    params: Dict[str, Any],
) -> str:
    mon = summary.get("monitoring", {})
    im = summary.get("input_metrics", {})
    pprof_s = summary.get("pprof_summary", {})
    hist = im.get("histograms", {})
    throughput = im.get("throughput", {})
    mon_throughput = mon.get("throughput", {})
    resources = mon.get("resources", {})
    output = mon.get("output", {})
    issues_mon = mon.get("issues", [])
    issues_im = im.get("issues", [])

    lines = [
        f"# Filebeat {input_type.upper()} Input — Single Run Report\n",
        "## Test Parameters\n",
        f"| Parameter | Value |",
        f"|-----------|-------|",
        f"| Input type | {input_type} |",
        f"| Interval | {params.get('interval', 'N/A')} |",
        f"| Initial interval | {params.get('initial_interval', 'N/A')} |",
        f"| Event limit | {params.get('event_limit', 'N/A')} |",
        f"| Duration | {params.get('duration', 'N/A')} |",
        "",
        "## Throughput (from /inputs/ endpoint)\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total events published | {_fmt(throughput.get('total_events_published'))} |",
        f"| Total events received | {_fmt(throughput.get('total_events_received'))} |",
        f"| Total batches published | {_fmt(throughput.get('total_batches_published'))} |",
        f"| Total HTTP requests | {_fmt(throughput.get('total_http_requests'))} |",
        f"| HTTP 2xx responses | {_fmt(throughput.get('http_2xx_total'))} |",
        f"| HTTP success rate | {_fmt(throughput.get('http_success_rate_pct'), '%')} |",
        "",
        "## Throughput (from monitoring logs)\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total events published (log) | {_fmt(mon_throughput.get('total_events_published'))} |",
        f"| Avg EPS | {_fmt(mon_throughput.get('avg_eps'))} |",
        "",
        "## Input Timing (from /inputs/ endpoint, all in ms)\n",
        f"| Metric | mean | p75 | p95 | p99 | max |",
        f"|--------|------|-----|-----|-----|-----|",
        _hist_row(hist.get("http_round_trip_time_ms"), "HTTP Round Trip Time"),
        _hist_row(hist.get("batch_processing_time_ms"), "Batch Processing Time"),
    ]

    if input_type == "cel":
        lines.append(_hist_row(hist.get("cel_processing_time_ms"), "CEL Processing Time"))
    if input_type == "akamai":
        lines.append(_hist_row(hist.get("response_latency_ms"), "API Response Latency"))
        lines.append(_hist_row(hist.get("request_processing_time_ms"), "Request Processing Time"))

    lines += [""]

    if input_type == "cel":
        cel = im.get("cel", {})
        lines += [
            "## CEL-Specific Metrics\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| CEL executions | {_fmt(cel.get('cel_executions'))} |",
            "",
        ]

    if input_type == "akamai":
        ak = im.get("akamai", {})
        lines += [
            "## Akamai-Specific Metrics\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Akamai requests total | {_fmt(ak.get('akamai_requests_total'))} |",
            f"| Successful requests | {_fmt(ak.get('akamai_requests_success'))} |",
            f"| Failed requests | {_fmt(ak.get('akamai_requests_errors'))} |",
            f"| Worker utilization | {_fmt(ak.get('worker_utilization'), '%')} |",
            "",
            "### Reliability Indicators\n",
            f"| Indicator | Count | Meaning |",
            f"|-----------|-------|---------|",
            f"| offset_expired | {_fmt(ak.get('offset_expired_total'))} | API returned 416 (offset stale) |",
            f"| offset_ttl_drops | {_fmt(ak.get('offset_ttl_drops_total'))} | Proactive drops before TTL expires |",
            f"| hmac_refresh | {_fmt(ak.get('hmac_refresh_total'))} | HMAC clock-skew retries |",
            f"| cursor_drops | {_fmt(ak.get('cursor_drops_total'))} | Offset cleared, window replayed |",
            f"| from_clamped | {_fmt(ak.get('from_clamped_total'))} | Lookback clamped to 12h max |",
            f"| api_400_fatal | {_fmt(ak.get('api_400_fatal_total'))} | Non-recoverable 400 errors |",
            "",
        ]

    lines += [
        "## System Resources (from monitoring logs)\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Avg CPU total ms/min | {_fmt(resources.get('avg_cpu_total_ms'))} |",
        f"| Avg memory alloc | {_fmt(resources.get('avg_memory_alloc_mb'))} MB |",
        f"| Max memory alloc | {_fmt(resources.get('max_memory_alloc_mb'))} MB |",
        f"| Avg RSS | {_fmt(resources.get('avg_rss_mb'))} MB |",
        f"| Max RSS | {_fmt(resources.get('max_rss_mb'))} MB |",
        f"| Avg goroutines | {_fmt(resources.get('avg_goroutines'))} |",
        f"| Max goroutines | {_fmt(resources.get('max_goroutines'))} |",
        f"| Avg normalized load (1m) | {_fmt(resources.get('avg_load_norm_1'))} |",
        "",
        "## Output Health (from monitoring logs)\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total acked | {_fmt(output.get('total_acked'))} |",
        f"| Total failed | {_fmt(output.get('total_failed'))} |",
        f"| Total dropped | {_fmt(output.get('total_dropped'))} |",
        f"| Avg output latency mean | {_fmt(output.get('avg_latency_mean'))} µs |",
        f"| Avg output latency p99 | {_fmt(output.get('avg_latency_p99'))} µs |",
        "",
    ]

    if pprof_text:
        lines += [
            "## pprof Analysis\n",
            pprof_text,
        ]
    else:
        lines += ["## pprof Analysis\n", "_No pprof profiles available._\n"]

    all_issues = issues_mon + issues_im
    if all_issues:
        lines += [
            "## Issues Detected\n",
        ]
        for issue in all_issues:
            lines.append(f"- ⚠️  {issue}")
        lines.append("")
    else:
        lines += ["## Issues Detected\n", "_No issues detected._\n"]

    return "\n".join(lines)
