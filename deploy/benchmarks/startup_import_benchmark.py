#!/usr/bin/env python3
"""Phase 5G-A: import-time breakdown benchmark, per deployment mode.

Runs `python -X importtime -c "import backend.api.router"` for each
deployment mode, parses the trace, and reports the top slowest modules
plus whether torch is present anywhere in the import graph.

Usage:
    venv/bin/python deploy/benchmarks/startup_import_benchmark.py [--top N]

Writes deploy/benchmarks/reports/startup_import_benchmark.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
MODES = ["dev", "admin", "public", "worker"]

LINE_RE = re.compile(r"import time:\s*(\d+)\s*\|\s*(\d+)\s*\|(\s*)(\S.*)")


def capture_trace(mode: str) -> str:
    env = os.environ.copy()
    if mode == "dev":
        env.pop("BRUD_DEPLOYMENT_MODE", None)
    else:
        env["BRUD_DEPLOYMENT_MODE"] = mode

    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-c", "import backend.api.router"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"importtime subprocess failed for mode={mode}:\n{result.stderr}")
    return result.stderr


def parse_trace(trace_text: str) -> list[tuple[int, str, int, int]]:
    """Return list of (depth, name, self_us, cumulative_us)."""

    parsed = []
    for line in trace_text.splitlines():
        m = LINE_RE.match(line)
        if not m:
            continue
        self_us, cum_us, indent, name = m.groups()
        parsed.append((len(indent), name.strip(), int(self_us), int(cum_us)))
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=10, help="top N modules to report (default 10)")
    args = parser.parse_args()

    summary: dict[str, dict] = {}
    for mode in MODES:
        trace_text = capture_trace(mode)
        parsed = parse_trace(trace_text)
        torch_entries = [p for p in parsed if p[1] == "torch"]
        torch_present = len(torch_entries) > 0
        torch_cumulative_us = torch_entries[0][3] if torch_entries else 0

        # De-duplicate by name, keep the entry with the largest cumulative time
        # (a module can legitimately appear once; this guards against any
        # accidental re-import noise in the raw trace).
        by_name: dict[str, tuple[int, int]] = {}
        for _, name, self_us, cum_us in parsed:
            if name not in by_name or cum_us > by_name[name][1]:
                by_name[name] = (self_us, cum_us)

        top_modules = sorted(by_name.items(), key=lambda kv: kv[1][1], reverse=True)[: args.top]

        summary[mode] = {
            "torch_present": torch_present,
            "torch_cumulative_us": torch_cumulative_us,
            "total_self_us": sum(v[0] for v in by_name.values()),
            "top_modules": [
                {"name": name, "self_us": self_us, "cumulative_us": cum_us}
                for name, (self_us, cum_us) in top_modules
            ],
        }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "startup_import_benchmark.json"
    out_path.write_text(json.dumps(summary, indent=2))

    for mode, data in summary.items():
        print(f"=== {mode} ===")
        print(f"  torch present: {data['torch_present']}")
        if data["torch_present"]:
            print(f"  torch cumulative: {data['torch_cumulative_us'] / 1000:.1f} ms")
        print(f"  top {args.top} modules by cumulative time:")
        for m in data["top_modules"]:
            print(f"    {m['cumulative_us'] / 1000:8.1f} ms  {m['name']}")
        print()

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
