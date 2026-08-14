#!/usr/bin/env python3
"""Phase 5G-A: cold-start wall-clock benchmark, per deployment mode.

Measures the real wall-clock cost of `import backend.api.router` in a
fresh interpreter, for each deployment mode (dev/admin/public/worker).
Each run is a short-lived subprocess -- nothing binds a port, nothing
is left running.

Usage:
    venv/bin/python deploy/benchmarks/cold_start_benchmark.py [--runs N]

Writes deploy/benchmarks/reports/cold_start_benchmark.json and prints a
human-readable table to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
MODES = ["dev", "admin", "public", "worker"]


def run_once(mode: str) -> float:
    env = os.environ.copy()
    if mode == "dev":
        env.pop("BRUD_DEPLOYMENT_MODE", None)
    else:
        env["BRUD_DEPLOYMENT_MODE"] = mode

    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-c", "import backend.api.router"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise RuntimeError(
            f"cold-start subprocess failed for mode={mode}:\n{result.stderr}"
        )
    return elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3, help="runs per mode (default 3)")
    args = parser.parse_args()

    results: dict[str, list[float]] = {}
    for mode in MODES:
        timings = [run_once(mode) for _ in range(args.runs)]
        results[mode] = timings

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        mode: {
            "runs": timings,
            "min": min(timings),
            "avg": sum(timings) / len(timings),
            "max": max(timings),
        }
        for mode, timings in results.items()
    }
    out_path = REPORTS_DIR / "cold_start_benchmark.json"
    out_path.write_text(json.dumps(summary, indent=2))

    print(f"{'Mode':<10} {'Min (s)':>10} {'Avg (s)':>10} {'Max (s)':>10}")
    for mode, stats in summary.items():
        print(f"{mode:<10} {stats['min']:>10.3f} {stats['avg']:>10.3f} {stats['max']:>10.3f}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
