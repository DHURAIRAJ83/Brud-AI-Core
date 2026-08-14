#!/usr/bin/env python3
"""Phase 5G-A: single-user sequential latency benchmark.

Starts a real uvicorn server for one deployment mode (default: public)
on a dedicated test port against an isolated temp database -- never
touches the real data/ directory or any already-running service -- and
fires N sequential (not concurrent) requests at /api/health, measuring
latency. The server is always terminated and the temp directory always
removed, even on error.

Sequential-only by design: concurrent/load testing is Phase 5G-B's
scope (documented, unattended), not this interactive benchmark.

Usage:
    venv/bin/python deploy/benchmarks/latency_benchmark.py [--mode public] [--requests 50] [--port 18099]

Writes deploy/benchmarks/reports/latency_benchmark.json.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(__file__).resolve().parent / "reports"


def port_is_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) != 0


def wait_for_ready(url: str, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_error = exc
        time.sleep(0.3)
    raise TimeoutError(f"server did not become ready at {url}: {last_error}")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="public", choices=["dev", "admin", "public", "worker"])
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--port", type=int, default=18099)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    if not port_is_free(args.port, args.host):
        raise SystemExit(
            f"port {args.port} is already in use -- refusing to start "
            "(this benchmark must never collide with a real running service)"
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="brud-benchmark-"))
    proc: subprocess.Popen | None = None
    try:
        env = os.environ.copy()
        env["BRUD_DEPLOYMENT_MODE"] = args.mode
        env["BRUD_DATABASE_PATH"] = str(tmp_dir / "benchmark.db")
        env["BRUD_DATABASE_BACKUP_DIR"] = str(tmp_dir / "backups")
        env["BRUD_ALLOW_EXTERNAL_STORAGE"] = "true"

        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "backend.main:app",
                "--host", args.host, "--port", str(args.port),
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        health_url = f"http://{args.host}:{args.port}/api/health"
        wait_for_ready(health_url)

        latencies_ms: list[float] = []
        for _ in range(args.requests):
            started = time.perf_counter()
            with urllib.request.urlopen(health_url, timeout=5) as resp:
                resp.read()
                status = resp.status
            latencies_ms.append((time.perf_counter() - started) * 1000)
            if status != 200:
                raise RuntimeError(f"unexpected status {status} from {health_url}")

        summary = {
            "mode": args.mode,
            "endpoint": "/api/health",
            "requests": args.requests,
            "min_ms": min(latencies_ms),
            "avg_ms": sum(latencies_ms) / len(latencies_ms),
            "p50_ms": percentile(latencies_ms, 50),
            "p95_ms": percentile(latencies_ms, 95),
            "max_ms": max(latencies_ms),
        }

        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / "latency_benchmark.json"
        out_path.write_text(json.dumps(summary, indent=2))

        print(f"mode={summary['mode']} endpoint={summary['endpoint']} requests={summary['requests']}")
        print(f"  min={summary['min_ms']:.2f}ms  avg={summary['avg_ms']:.2f}ms  "
              f"p50={summary['p50_ms']:.2f}ms  p95={summary['p95_ms']:.2f}ms  max={summary['max_ms']:.2f}ms")
        print(f"\nWrote {out_path}")
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
