#!/usr/bin/env python3
"""
analyze.py — Analysis entry point for the Akamai Filebeat performance test suite.

Subcommands:
  single      Analyze a single run (CEL or Akamai input)
  compare     Compare completed CEL and Akamai runs side by side
  ai-analyze  Run AI-driven analysis using the Claude API (requires ANTHROPIC_API_KEY)

Usage:
  python analysis/analyze.py single \\
      --run-dir runs/my-run/cel/ \\
      --input-type cel \\
      --run-config runs/my-run/run_config.json

  python analysis/analyze.py compare \\
      --run-dir runs/my-run/ \\
      --run-config runs/my-run/run_config.json

  python analysis/analyze.py ai-analyze \\
      --run-dir runs/my-run/ \\
      --run-config runs/my-run/run_config.json

Must be run from the akamai-test/ directory (suite root).
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure analysis/ package is importable when run directly
_suite_root = Path(__file__).parent.parent
if str(_suite_root) not in sys.path:
    sys.path.insert(0, str(_suite_root))

from analysis.reporters.single_run import run_single_analysis
from analysis.reporters.comparison import run_comparison
from analysis.ai_analysis import run_ai_analysis


def _load_run_config(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: run_config.json not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid run_config.json: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_single(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    run_config_path = Path(args.run_config).resolve()

    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    run_config = _load_run_config(run_config_path)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "analysis"

    print(f"Analyzing {args.input_type.upper()} run in {run_dir}")
    summary = run_single_analysis(
        run_dir=run_dir,
        input_type=args.input_type,
        run_config=run_config,
        output_dir=output_dir,
    )

    report_path = output_dir / "report.md"
    summary_path = output_dir / "summary.json"
    print(f"  Report:  {report_path}")
    print(f"  Summary: {summary_path}")

    issues = (
        summary.get("monitoring", {}).get("issues", [])
        + summary.get("input_metrics", {}).get("issues", [])
    )
    if issues:
        print(f"\n  Issues detected ({len(issues)}):")
        for i in issues:
            print(f"    ⚠  {i}")

    throughput = summary.get("input_metrics", {}).get("throughput", {})
    events = throughput.get("total_events_published")
    eps = summary.get("monitoring", {}).get("throughput", {}).get("avg_eps")
    if events:
        print(f"\n  Total events published: {events:,}")
    if eps:
        print(f"  Avg EPS: {eps:.1f}")


def cmd_compare(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    run_config_path = Path(args.run_config).resolve()

    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    run_config = _load_run_config(run_config_path)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "comparison"

    print(f"Generating comparison report in {run_dir}")
    try:
        comparison_data = run_comparison(
            run_dir=run_dir,
            run_config=run_config,
            output_dir=output_dir,
        )
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    report_path = output_dir / "comparison_report.md"
    print(f"  Comparison report: {report_path}")

    # Print headline numbers
    t = comparison_data.get("throughput", {})
    print("\n  Headline results:")
    print(f"    CEL   total events: {t.get('cel_events_published', 'N/A'):,}" if isinstance(t.get('cel_events_published'), int) else f"    CEL   total events: N/A")
    print(f"    Akamai total events: {t.get('akamai_events_published', 'N/A'):,}" if isinstance(t.get('akamai_events_published'), int) else f"    Akamai total events: N/A")

    lat = comparison_data.get("latency", {})
    cel_rtt = (lat.get("cel_http_rtt_ms") or {}).get("mean")
    ak_rtt = (lat.get("akamai_http_rtt_ms") or {}).get("mean")
    if cel_rtt:
        print(f"    CEL   HTTP RTT mean: {cel_rtt:.0f} ms")
    if ak_rtt:
        print(f"    Akamai HTTP RTT mean: {ak_rtt:.0f} ms")


def cmd_ai_analyze(args: argparse.Namespace) -> None:
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ERROR: ANTHROPIC_API_KEY environment variable is not set.\n"
            "Export it before running AI analysis:\n"
            "  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)

    run_dir = Path(args.run_dir).resolve()
    run_config_path = Path(args.run_config).resolve()

    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    run_config = _load_run_config(run_config_path)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else run_dir / "comparison"

    print(f"Running AI analysis for run in {run_dir}")
    try:
        output_path = run_ai_analysis(
            run_dir=run_dir,
            run_config=run_config,
            output_dir=output_dir,
        )
    except (EnvironmentError, ImportError, RuntimeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  AI analysis written to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Akamai Filebeat performance test analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── single ────────────────────────────────────────────────────────────────
    p_single = subparsers.add_parser(
        "single",
        help="Analyze a single run (CEL or Akamai)",
    )
    p_single.add_argument(
        "--run-dir", required=True,
        help="Path to the run sub-directory (e.g. runs/my-run/cel/)",
    )
    p_single.add_argument(
        "--input-type", required=True, choices=["cel", "akamai"],
        help="Input type for this run",
    )
    p_single.add_argument(
        "--run-config", required=True,
        help="Path to run_config.json",
    )
    p_single.add_argument(
        "--output-dir",
        help="Output directory (default: <run-dir>/analysis/)",
    )
    p_single.set_defaults(func=cmd_single)

    # ── compare ───────────────────────────────────────────────────────────────
    p_compare = subparsers.add_parser(
        "compare",
        help="Compare completed CEL and Akamai runs",
    )
    p_compare.add_argument(
        "--run-dir", required=True,
        help="Path to the parent run directory (e.g. runs/my-run/)",
    )
    p_compare.add_argument(
        "--run-config", required=True,
        help="Path to run_config.json",
    )
    p_compare.add_argument(
        "--output-dir",
        help="Output directory (default: <run-dir>/comparison/)",
    )
    p_compare.set_defaults(func=cmd_compare)

    # ── ai-analyze ────────────────────────────────────────────────────────────
    p_ai = subparsers.add_parser(
        "ai-analyze",
        help="Run AI-driven analysis using the Claude API (requires ANTHROPIC_API_KEY)",
    )
    p_ai.add_argument(
        "--run-dir", required=True,
        help="Path to the parent run directory (e.g. runs/my-run/)",
    )
    p_ai.add_argument(
        "--run-config", required=True,
        help="Path to run_config.json",
    )
    p_ai.add_argument(
        "--output-dir",
        help="Output directory for final_analysis.md (default: <run-dir>/comparison/)",
    )
    p_ai.set_defaults(func=cmd_ai_analyze)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
