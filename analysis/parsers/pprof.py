"""
pprof.py — Runs `go tool pprof` CLI against collected pprof profiles and parses
the text output for automated analysis and comparison.

Profiles are collected by bin/collect_pprof.sh during each Filebeat run:
  - heap_baseline.pprof  (at ~30s into the run)
  - cpu_midpoint.pprof   (30s CPU profile centered around the run midpoint)
  - heap_final.pprof     (15s before run end)
  - block_final.pprof    (15s before run end)
  - mutex_final.pprof    (15s before run end)

Analysis focuses on the indicators from specs/PPROF_ANALYSIS.md:
  - GC overhead in CPU profile (>20% is high)
  - JSON decode vs CEL boundary cost
  - Heap growth baseline -> final
  - Lock contention in block/mutex profiles
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


# Functions that contribute to GC overhead
GC_FUNCTIONS = {
    "runtime.mallocgc",
    "runtime.gcBgMarkWorker",
    "runtime.gcAssistAlloc",
    "runtime.gcDrain",
    "runtime.gcMarkDone",
}

# Patterns identifying JSON decode cost
JSON_DECODE_PATTERNS = [
    re.compile(r"^encoding/json\."),
]

# Patterns identifying CEL evaluation overhead (CEL input only)
CEL_BOUNDARY_PATTERNS = [
    re.compile(r"cel-go"),
    re.compile(r"ConvertToNative"),
    re.compile(r"AsMap"),
    re.compile(r"github\.com/google/cel-go"),
    re.compile(r"cel\.Program"),
]

# Package path patterns for input-type attribution
CEL_INPUT_PATTERNS = [re.compile(r"input/cel")]
AKAMAI_INPUT_PATTERNS = [re.compile(r"input/akamai")]


def _run_pprof(args: List[str], timeout: int = 90) -> Optional[str]:
    """Run `go tool pprof` with given args. Returns stdout or None on failure."""
    cmd = ["go", "tool", "pprof"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            print(f"Warning: go tool pprof failed: {result.stderr[:500]}", file=sys.stderr)
            return None
        return result.stdout
    except FileNotFoundError:
        print("Warning: 'go' not found in PATH — pprof analysis skipped", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"Warning: go tool pprof timed out after {timeout}s", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: go tool pprof error: {e}", file=sys.stderr)
        return None


def parse_pprof_text(output: str) -> List[Dict[str, Any]]:
    """
    Parse `go tool pprof -text` output into a list of function entries.

    Each entry: {function, flat_pct, cum_pct, flat_value, cum_value, flat_unit}

    Example input line:
        1.20s 23.08% 23.08%      1.80s 34.62%  runtime.mallocgc
    """
    entries = []
    in_table = False

    for line in output.splitlines():
        line = line.strip()

        # Header line marks start of the data table
        if re.match(r'\s*flat\s+flat%\s+sum%', line):
            in_table = True
            continue

        if not in_table:
            continue

        if not line:
            continue

        # Match: <value><unit> <flat%>% <sum%>% <value><unit> <cum%>% <function>
        m = re.match(
            r'^(\S+)\s+([\d.]+)%\s+([\d.]+)%\s+(\S+)\s+([\d.]+)%\s+(.+)$',
            line
        )
        if m:
            flat_val_str, flat_pct_str, sum_pct_str, cum_val_str, cum_pct_str, func_name = m.groups()
            # Parse flat value and unit (e.g. "1.20s" or "512B")
            flat_unit_m = re.match(r'^([\d.]+)(.*)$', flat_val_str)
            entries.append({
                "function": func_name.strip(),
                "flat_pct": float(flat_pct_str),
                "cum_pct": float(cum_pct_str),
                "flat_value": float(flat_unit_m.group(1)) if flat_unit_m else 0.0,
                "flat_unit": flat_unit_m.group(2) if flat_unit_m else "",
            })

    return entries


def _classify_functions(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute category breakdowns from a parsed pprof entry list."""
    gc_flat_pct = sum(e["flat_pct"] for e in entries if e["function"] in GC_FUNCTIONS)
    gc_cum_pct = sum(e["cum_pct"] for e in entries if e["function"] in GC_FUNCTIONS)

    json_flat_pct = sum(
        e["flat_pct"] for e in entries
        if any(p.search(e["function"]) for p in JSON_DECODE_PATTERNS)
    )

    cel_boundary_flat_pct = sum(
        e["flat_pct"] for e in entries
        if any(p.search(e["function"]) for p in CEL_BOUNDARY_PATTERNS)
    )

    cel_input_flat_pct = sum(
        e["flat_pct"] for e in entries
        if any(p.search(e["function"]) for p in CEL_INPUT_PATTERNS)
    )

    akamai_input_flat_pct = sum(
        e["flat_pct"] for e in entries
        if any(p.search(e["function"]) for p in AKAMAI_INPUT_PATTERNS)
    )

    return {
        "gc_flat_pct": round(gc_flat_pct, 2),
        "gc_cum_pct": round(gc_cum_pct, 2),
        "gc_high": gc_flat_pct > 20.0,
        "json_decode_flat_pct": round(json_flat_pct, 2),
        "cel_boundary_flat_pct": round(cel_boundary_flat_pct, 2),
        "cel_input_flat_pct": round(cel_input_flat_pct, 2),
        "akamai_input_flat_pct": round(akamai_input_flat_pct, 2),
    }


def analyze_cpu(pprof_path: Path, top: int = 30) -> Optional[Dict[str, Any]]:
    """Analyze CPU profile."""
    if not pprof_path.exists():
        return None
    output = _run_pprof(["-text", f"-top={top}", str(pprof_path)])
    if not output:
        return None
    entries = parse_pprof_text(output)
    return {
        "profile": "cpu",
        "path": str(pprof_path),
        "top_functions": entries[:top],
        "categories": _classify_functions(entries),
        "raw_text": output,
    }


def analyze_heap(pprof_path: Path, top: int = 20) -> Optional[Dict[str, Any]]:
    """Analyze heap profile (in-use space)."""
    if not pprof_path.exists():
        return None
    output = _run_pprof(["-text", "-inuse_space", f"-top={top}", str(pprof_path)])
    if not output:
        return None
    entries = parse_pprof_text(output)
    return {
        "profile": "heap_inuse",
        "path": str(pprof_path),
        "top_functions": entries[:top],
        "categories": _classify_functions(entries),
        "raw_text": output,
    }


def analyze_heap_growth(baseline_path: Path, final_path: Path, top: int = 20) -> Optional[Dict[str, Any]]:
    """Diff two heap profiles to show memory growth (baseline -> final)."""
    if not baseline_path.exists() or not final_path.exists():
        return None
    output = _run_pprof(["-text", "-inuse_space", "-base", str(baseline_path), str(final_path)])
    if not output:
        return None
    entries = parse_pprof_text(output)
    return {
        "profile": "heap_growth",
        "baseline": str(baseline_path),
        "final": str(final_path),
        "top_functions": entries[:top],
        "categories": _classify_functions(entries),
        "raw_text": output,
    }


def analyze_contention(pprof_path: Path, profile_type: str, top: int = 20) -> Optional[Dict[str, Any]]:
    """Analyze block or mutex contention profile."""
    if not pprof_path.exists():
        return None
    output = _run_pprof(["-text", f"-top={top}", str(pprof_path)])
    if not output:
        return None
    entries = parse_pprof_text(output)
    return {
        "profile": profile_type,
        "path": str(pprof_path),
        "top_functions": entries[:top],
        "categories": _classify_functions(entries),
        "raw_text": output,
    }


def analyze_pprof_dir(pprof_dir: Path) -> Dict[str, Any]:
    """
    Analyze all pprof files in a run's pprof directory.

    Returns a dict with analysis results for each collected profile type.
    """
    results: Dict[str, Any] = {}

    cpu = analyze_cpu(pprof_dir / "cpu_midpoint.pprof")
    if cpu:
        results["cpu"] = cpu

    heap_final = analyze_heap(pprof_dir / "heap_final.pprof")
    if heap_final:
        results["heap_final"] = heap_final

    heap_growth = analyze_heap_growth(
        pprof_dir / "heap_baseline.pprof",
        pprof_dir / "heap_final.pprof",
    )
    if heap_growth:
        results["heap_growth"] = heap_growth

    block = analyze_contention(pprof_dir / "block_final.pprof", "block")
    if block:
        results["block"] = block

    mutex = analyze_contention(pprof_dir / "mutex_final.pprof", "mutex")
    if mutex:
        results["mutex"] = mutex

    # Summary for easy access
    results["summary"] = {
        "cpu_gc_flat_pct": cpu["categories"]["gc_flat_pct"] if cpu else None,
        "cpu_gc_high": cpu["categories"]["gc_high"] if cpu else None,
        "cpu_json_decode_pct": cpu["categories"]["json_decode_flat_pct"] if cpu else None,
        "cpu_cel_boundary_pct": cpu["categories"]["cel_boundary_flat_pct"] if cpu else None,
        "profiles_collected": list(results.keys()),
    }

    return results


def format_pprof_report(pprof_results: Dict[str, Any], input_type: str) -> str:
    """Format pprof analysis results as human-readable text."""
    lines = [f"## pprof Analysis — {input_type.upper()} input\n"]

    cpu = pprof_results.get("cpu")
    if cpu:
        cats = cpu["categories"]
        gc_flag = " ⚠️  HIGH" if cats["gc_high"] else ""
        lines.append(f"### CPU Profile (midpoint, 30s)\n")
        lines.append(f"GC overhead: {cats['gc_flat_pct']:.1f}% (flat){gc_flag}")
        lines.append(f"JSON decode: {cats['json_decode_flat_pct']:.1f}% (flat)")
        if input_type == "cel":
            lines.append(f"CEL eval/boundary: {cats['cel_boundary_flat_pct']:.1f}% (flat)")
        lines.append(f"\nTop {min(10, len(cpu['top_functions']))} functions by flat%:")
        lines.append(f"{'Function':<60} {'flat%':>6} {'cum%':>6}")
        lines.append("-" * 74)
        for e in cpu["top_functions"][:10]:
            lines.append(f"{e['function']:<60} {e['flat_pct']:>5.1f}% {e['cum_pct']:>5.1f}%")
        lines.append("")

    heap_growth = pprof_results.get("heap_growth")
    if heap_growth:
        lines.append("### Heap Growth (baseline → final)\n")
        lines.append(f"Top memory growth paths:")
        lines.append(f"{'Function':<60} {'flat%':>6} {'cum%':>6}")
        lines.append("-" * 74)
        for e in heap_growth["top_functions"][:10]:
            lines.append(f"{e['function']:<60} {e['flat_pct']:>5.1f}% {e['cum_pct']:>5.1f}%")
        lines.append("")

    block = pprof_results.get("block")
    if block:
        lines.append("### Block Contention\n")
        if block["top_functions"]:
            lines.append(f"{'Function':<60} {'flat%':>6} {'cum%':>6}")
            lines.append("-" * 74)
            for e in block["top_functions"][:10]:
                lines.append(f"{e['function']:<60} {e['flat_pct']:>5.1f}% {e['cum_pct']:>5.1f}%")
        else:
            lines.append("No significant block contention detected.")
        lines.append("")

    mutex = pprof_results.get("mutex")
    if mutex:
        lines.append("### Mutex Contention\n")
        if mutex["top_functions"]:
            lines.append(f"{'Function':<60} {'flat%':>6} {'cum%':>6}")
            lines.append("-" * 74)
            for e in mutex["top_functions"][:10]:
                lines.append(f"{e['function']:<60} {e['flat_pct']:>5.1f}% {e['cum_pct']:>5.1f}%")
        else:
            lines.append("No significant mutex contention detected.")
        lines.append("")

    return "\n".join(lines)
