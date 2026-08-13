"""MB-25: Timeout Runner -- the one explicit execution wrapper the
task spec's own Step 5 names as an exception to "deterministic and
side-effect free": this module is what actually calls a plugin's own
`run(context, arguments)` function, bounded by a real wall-clock
timeout via a single-worker `ThreadPoolExecutor` -- never subprocess,
never a shell, never `eval`/`exec`.

Honest limitation: Python cannot forcibly terminate a running thread.
A plugin that ignores its timeout and keeps computing will continue
running in the background after this function returns a `'timeout'`
status to the caller -- there is no process or container isolation in
this phase to kill it outright. This is disclosed explicitly in every
timeout result and in the final execution report.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Callable

DEFAULT_TIMEOUT_SECONDS = 5.0
MAX_TIMEOUT_SECONDS = 30.0


def run_with_timeout(
    fn: Callable[..., Any], *, args: tuple[Any, ...] = (), kwargs: dict[str, Any] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    bounded_timeout = min(max(timeout_seconds, 0.1), MAX_TIMEOUT_SECONDS)
    kwargs = kwargs or {}
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn, *args, **kwargs)
        try:
            result = future.result(timeout=bounded_timeout)
            return {
                "status": "completed", "result": result, "error": None,
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        except FutureTimeoutError:
            return {
                "status": "timeout", "result": None,
                "error": f"execution exceeded its {bounded_timeout}s timeout",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "disclosure": (
                    "Python cannot forcibly terminate a running thread -- the plugin call may continue "
                    "executing in the background after this timeout is reported; no process or container "
                    "isolation exists in this phase to kill it outright"
                ),
            }
        except Exception as exc:  # noqa: BLE001 -- a plugin's own run() may raise anything
            return {
                "status": "failed", "result": None, "error": str(exc),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            }
