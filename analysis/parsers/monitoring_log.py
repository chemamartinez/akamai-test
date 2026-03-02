"""
monitoring_log.py — Parser for Filebeat periodic monitoring log entries.

Filebeat writes JSON-formatted metrics to its log file every `logging.metrics.period`
(default: 1m). Each log line is a JSON object with `log.logger: "monitoring"`.

IMPORTANT: Counter metrics in these logs already represent the CHANGE since the last
snapshot (they are deltas, not cumulative totals). To get run totals, SUM them.
Gauge metrics (pipeline_events_active, queue_filled_pct, etc.) are point-in-time
values and should NOT be summed.

Adapted from analyze_filebeat.py in the same repository.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

import pandas as pd


# ── Counter metrics ────────────────────────────────────────────────────────────
# These show change since the last snapshot — sum them to get run totals.
COUNTER_METRICS = {
    'pipeline_events_published',
    'pipeline_events_total',
    'queue_added_events',
    'queue_consumed_events',
    'queue_removed_events',
    'output_events_total',
    'output_events_acked',
    'output_events_failed',
    'output_events_dropped',
    'output_events_batches',
    'filebeat_events_added',
    'filebeat_events_done',
    'cpu_total_ms',
    'cpu_user_ms',
    'cpu_system_ms',
}


@dataclass
class MetricSnapshot:
    """A single periodic metrics snapshot from the monitoring log."""
    timestamp: datetime

    # Pipeline
    pipeline_events_active: Optional[int] = None
    pipeline_events_published: Optional[int] = None
    pipeline_events_total: Optional[int] = None

    # Queue
    queue_filled_events: Optional[int] = None
    queue_filled_bytes: Optional[int] = None
    queue_filled_pct: Optional[float] = None
    queue_max_events: Optional[int] = None
    queue_added_events: Optional[int] = None
    queue_consumed_events: Optional[int] = None
    queue_removed_events: Optional[int] = None

    # Output
    output_events_total: Optional[int] = None
    output_events_acked: Optional[int] = None
    output_events_active: Optional[int] = None
    output_events_failed: Optional[int] = None
    output_events_dropped: Optional[int] = None
    output_events_batches: Optional[int] = None

    # Output write latency (microseconds from monitoring log)
    latency_mean: Optional[float] = None
    latency_median: Optional[float] = None
    latency_p95: Optional[float] = None
    latency_p99: Optional[float] = None
    latency_p999: Optional[float] = None
    latency_max: Optional[float] = None

    # Filebeat input
    filebeat_events_active: Optional[int] = None
    filebeat_events_added: Optional[int] = None
    filebeat_events_done: Optional[int] = None

    # Resources
    cpu_total_ms: Optional[int] = None
    cpu_user_ms: Optional[int] = None
    cpu_system_ms: Optional[int] = None
    memory_alloc: Optional[int] = None
    memory_total: Optional[int] = None
    rss: Optional[int] = None
    gc_next: Optional[int] = None
    goroutines: Optional[int] = None

    # System load
    load_1: Optional[float] = None
    load_5: Optional[float] = None
    load_15: Optional[float] = None
    load_norm_1: Optional[float] = None
    load_norm_5: Optional[float] = None
    load_norm_15: Optional[float] = None


@dataclass
class FinalMetrics:
    """Cumulative totals from the 'Total metrics' log entry written at shutdown."""
    timestamp: datetime

    # Beat info
    uptime_ms: Optional[int] = None
    version: Optional[str] = None

    # Pipeline
    pipeline_events_published: Optional[int] = None
    pipeline_events_total: Optional[int] = None

    # Queue
    queue_acked: Optional[int] = None
    queue_added_events: Optional[int] = None
    queue_consumed_events: Optional[int] = None
    queue_removed_events: Optional[int] = None

    # Output
    output_events_total: Optional[int] = None
    output_events_acked: Optional[int] = None
    output_events_failed: Optional[int] = None
    output_events_dropped: Optional[int] = None
    output_events_batches: Optional[int] = None
    output_write_bytes: Optional[int] = None

    # Filebeat
    filebeat_events_added: Optional[int] = None
    filebeat_events_done: Optional[int] = None

    # Resources
    cpu_total_ms: Optional[int] = None
    memory_total: Optional[int] = None


class FilebeatMonitoringLogParser:
    """
    Parses Filebeat monitoring log files.

    Filebeat writes one JSON line per metric period. Lines with `log.logger: "monitoring"`
    and no 'Total metrics' in the message are periodic snapshots. Lines with
    'Total metrics' are the final cumulative summary logged at shutdown.
    """

    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.snapshots: List[MetricSnapshot] = []
        self.final_metrics: Optional[FinalMetrics] = None

    def parse(self) -> List[MetricSnapshot]:
        """Parse all log files in log_dir. Returns list of snapshots sorted by time."""
        log_files = sorted(self.log_dir.glob("filebeat*.ndjson")) + \
                    sorted(self.log_dir.glob("filebeat*.log"))

        if not log_files:
            # Try any .log files
            log_files = sorted(self.log_dir.glob("*.log"))

        for log_file in log_files:
            self._parse_file(log_file)

        self.snapshots.sort(key=lambda s: s.timestamp)
        return self.snapshots

    def _parse_file(self, log_file: Path) -> None:
        try:
            with open(log_file, 'r', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get('log.logger') != 'monitoring':
                            continue
                        if 'Total metrics' in entry.get('message', ''):
                            final = self._extract_final(entry)
                            if final:
                                self.final_metrics = final
                        else:
                            snap = self._extract_snapshot(entry)
                            if snap:
                                self.snapshots.append(snap)
                    except json.JSONDecodeError:
                        continue
        except OSError as e:
            print(f"Warning: Could not read {log_file}: {e}", file=sys.stderr)

    def _ts(self, entry: Dict[str, Any]) -> Optional[datetime]:
        ts = entry.get('@timestamp')
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))

    def _extract_snapshot(self, entry: Dict[str, Any]) -> Optional[MetricSnapshot]:
        try:
            ts = self._ts(entry)
            if not ts:
                return None
            m = entry.get('monitoring', {}).get('metrics', {})
            if not m:
                return None

            beat = m.get('beat', {})
            fb = m.get('filebeat', {})
            lb = m.get('libbeat', {})
            sys_m = m.get('system', {})
            pipeline = lb.get('pipeline', {})
            queue = pipeline.get('queue', {})
            output = lb.get('output', {})
            latency = output.get('write', {}).get('latency', {}).get('histogram', {})

            return MetricSnapshot(
                timestamp=ts,
                pipeline_events_active=pipeline.get('events', {}).get('active'),
                pipeline_events_published=pipeline.get('events', {}).get('published'),
                pipeline_events_total=pipeline.get('events', {}).get('total'),
                queue_filled_events=queue.get('filled', {}).get('events'),
                queue_filled_bytes=queue.get('filled', {}).get('bytes'),
                queue_filled_pct=queue.get('filled', {}).get('pct'),
                queue_max_events=queue.get('max_events'),
                queue_added_events=queue.get('added', {}).get('events'),
                queue_consumed_events=queue.get('consumed', {}).get('events'),
                queue_removed_events=queue.get('removed', {}).get('events'),
                output_events_total=output.get('events', {}).get('total'),
                output_events_acked=output.get('events', {}).get('acked'),
                output_events_active=output.get('events', {}).get('active'),
                output_events_failed=output.get('events', {}).get('failed'),
                output_events_dropped=output.get('events', {}).get('dropped'),
                output_events_batches=output.get('events', {}).get('batches'),
                latency_mean=latency.get('mean'),
                latency_median=latency.get('median'),
                latency_p95=latency.get('p95'),
                latency_p99=latency.get('p99'),
                latency_p999=latency.get('p999'),
                latency_max=latency.get('max'),
                filebeat_events_active=fb.get('events', {}).get('active'),
                filebeat_events_added=fb.get('events', {}).get('added'),
                filebeat_events_done=fb.get('events', {}).get('done'),
                cpu_total_ms=beat.get('cpu', {}).get('total', {}).get('time', {}).get('ms'),
                cpu_user_ms=beat.get('cpu', {}).get('user', {}).get('time', {}).get('ms'),
                cpu_system_ms=beat.get('cpu', {}).get('system', {}).get('time', {}).get('ms'),
                memory_alloc=beat.get('memstats', {}).get('memory_alloc'),
                memory_total=beat.get('memstats', {}).get('memory_total'),
                rss=beat.get('memstats', {}).get('rss'),
                gc_next=beat.get('memstats', {}).get('gc_next'),
                goroutines=beat.get('runtime', {}).get('goroutines'),
                load_1=sys_m.get('load', {}).get('1'),
                load_5=sys_m.get('load', {}).get('5'),
                load_15=sys_m.get('load', {}).get('15'),
                load_norm_1=sys_m.get('load', {}).get('norm', {}).get('1'),
                load_norm_5=sys_m.get('load', {}).get('norm', {}).get('5'),
                load_norm_15=sys_m.get('load', {}).get('norm', {}).get('15'),
            )
        except Exception as e:
            print(f"Warning: snapshot extraction error: {e}", file=sys.stderr)
            return None

    def _extract_final(self, entry: Dict[str, Any]) -> Optional[FinalMetrics]:
        try:
            ts = self._ts(entry)
            if not ts:
                return None
            m = entry.get('monitoring', {}).get('metrics', {})
            if not m:
                return None

            beat = m.get('beat', {})
            fb = m.get('filebeat', {})
            lb = m.get('libbeat', {})
            pipeline = lb.get('pipeline', {})
            queue = pipeline.get('queue', {})
            output = lb.get('output', {})

            return FinalMetrics(
                timestamp=ts,
                uptime_ms=beat.get('info', {}).get('uptime', {}).get('ms'),
                version=beat.get('info', {}).get('version'),
                pipeline_events_published=pipeline.get('events', {}).get('published'),
                pipeline_events_total=pipeline.get('events', {}).get('total'),
                queue_acked=queue.get('acked'),
                queue_added_events=queue.get('added', {}).get('events'),
                queue_consumed_events=queue.get('consumed', {}).get('events'),
                queue_removed_events=queue.get('removed', {}).get('events'),
                output_events_total=output.get('events', {}).get('total'),
                output_events_acked=output.get('events', {}).get('acked'),
                output_events_failed=output.get('events', {}).get('failed'),
                output_events_dropped=output.get('events', {}).get('dropped'),
                output_events_batches=output.get('events', {}).get('batches'),
                output_write_bytes=output.get('write', {}).get('bytes'),
                filebeat_events_added=fb.get('events', {}).get('added'),
                filebeat_events_done=fb.get('events', {}).get('done'),
                cpu_total_ms=beat.get('cpu', {}).get('total', {}).get('time', {}).get('ms'),
                memory_total=beat.get('memstats', {}).get('memory_total'),
            )
        except Exception as e:
            print(f"Warning: final metrics extraction error: {e}", file=sys.stderr)
            return None


class MonitoringMetricsAnalyzer:
    """Computes summary statistics from a list of MetricSnapshot objects."""

    def __init__(self, snapshots: List[MetricSnapshot], final: Optional[FinalMetrics] = None):
        self.snapshots = sorted(snapshots, key=lambda s: s.timestamp)
        self.final = final
        self.df = self._to_dataframe()

    def _to_dataframe(self) -> pd.DataFrame:
        data = [asdict(s) for s in self.snapshots]
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        return df

    def get_summary(self) -> Dict[str, Any]:
        """Return a dict suitable for JSON serialisation."""
        if self.df.empty:
            return {"error": "no_monitoring_snapshots"}

        # Use final metrics for totals when available; fall back to summing snapshots.
        def total(field: str) -> Optional[int]:
            if self.final:
                v = getattr(self.final, field, None)
                if v is not None:
                    return v
            if field in self.df.columns:
                return int(self.df[field].dropna().sum())
            return None

        def _avg(col: str) -> Optional[float]:
            if col not in self.df.columns:
                return None
            s = self.df[col].dropna()
            return float(s.mean()) if len(s) else None

        def _max(col: str) -> Optional[float]:
            if col not in self.df.columns:
                return None
            s = self.df[col].dropna()
            return float(s.max()) if len(s) else None

        # EPS computation: sum of counter deltas / elapsed time in seconds
        elapsed_s = (self.df.index.max() - self.df.index.min()).total_seconds()
        total_published = total('pipeline_events_published') or 0
        avg_eps = (total_published / elapsed_s) if elapsed_s > 0 else 0.0

        issues = []

        # Backpressure: growing pipeline_events_active
        if 'pipeline_events_active' in self.df.columns:
            active = self.df['pipeline_events_active'].dropna()
            if len(active) >= 3 and active.iloc[-1] > active.iloc[0] * 1.5:
                issues.append("growing_pipeline_active: possible backpressure")

        # Queue fill
        if 'queue_filled_pct' in self.df.columns:
            qfill = self.df['queue_filled_pct'].dropna()
            if len(qfill) and qfill.max() > 90:
                issues.append(f"high_queue_fill: max {qfill.max():.1f}% — output bottleneck")

        # Goroutine leak
        if 'goroutines' in self.df.columns:
            g = self.df['goroutines'].dropna()
            if len(g) >= 3 and g.iloc[-1] > g.iloc[0] * 1.5:
                issues.append("growing_goroutines: possible goroutine leak")

        # Memory growth
        if 'memory_alloc' in self.df.columns:
            ma = self.df['memory_alloc'].dropna()
            if len(ma) >= 3 and ma.iloc[-1] > ma.iloc[0] * 2:
                issues.append("growing_memory_alloc: possible memory leak")

        # System load
        if 'load_norm_1' in self.df.columns:
            ln = self.df['load_norm_1'].dropna()
            if len(ln) and ln.max() > 1.0:
                issues.append(f"system_overload: max norm load {ln.max():.2f}")

        # Output failures
        failed = total('output_events_failed') or 0
        dropped = total('output_events_dropped') or 0
        if failed > 0:
            issues.append(f"output_failures: {failed} failed events")
        if dropped > 0:
            issues.append(f"output_drops: {dropped} dropped events")

        return {
            "duration": {
                "start": self.df.index.min().isoformat(),
                "end": self.df.index.max().isoformat(),
                "elapsed_minutes": round(elapsed_s / 60, 2),
                "snapshots": len(self.df),
            },
            "throughput": {
                "total_events_published": total_published,
                "avg_eps": round(avg_eps, 2),
            },
            "pipeline": {
                "avg_active_events": _avg('pipeline_events_active'),
                "max_active_events": _max('pipeline_events_active'),
            },
            "queue": {
                "avg_fill_pct": _avg('queue_filled_pct'),
                "max_fill_pct": _max('queue_filled_pct'),
            },
            "output": {
                "total_acked": total('output_events_acked'),
                "total_failed": total('output_events_failed'),
                "total_dropped": total('output_events_dropped'),
                "avg_latency_mean": _avg('latency_mean'),
                "avg_latency_p95": _avg('latency_p95'),
                "avg_latency_p99": _avg('latency_p99'),
            },
            "resources": {
                "avg_cpu_total_ms": _avg('cpu_total_ms'),
                "avg_memory_alloc_mb": round((_avg('memory_alloc') or 0) / 1024 / 1024, 2),
                "max_memory_alloc_mb": round((_max('memory_alloc') or 0) / 1024 / 1024, 2),
                "avg_rss_mb": round((_avg('rss') or 0) / 1024 / 1024, 2),
                "max_rss_mb": round((_max('rss') or 0) / 1024 / 1024, 2),
                "avg_goroutines": _avg('goroutines'),
                "max_goroutines": _max('goroutines'),
                "avg_load_norm_1": _avg('load_norm_1'),
                "max_load_norm_1": _max('load_norm_1'),
                "first_rss_mb": round((self.df['rss'].dropna().iloc[0] if 'rss' in self.df.columns and len(self.df['rss'].dropna()) else 0) / 1024 / 1024, 2),
                "last_rss_mb": round((self.df['rss'].dropna().iloc[-1] if 'rss' in self.df.columns and len(self.df['rss'].dropna()) else 0) / 1024 / 1024, 2),
            },
            "issues": issues,
        }
