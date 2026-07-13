"""fa.runtime — EventStream Runtime for stateful bash

ADR-13: Stateful Bash via EventStream Runtime (FastAPI + PTY Pool)
Graceful degradation: server.app may be None if FastAPI not installed.
"""

from .pty_pool import PtyPool, PtySession

try:
    from .server import app  # noqa: F401 - FastAPI may not be installed
except ImportError as exc:
    # Graceful degradation per review Gap 1: tests requiring only PtyPool
    # must work without FastAPI. Log WARNING and continue.
    print(f"WARNING: Failed to import fa.runtime.server: {exc} — app=None, continuing")
    app = None  # type: ignore

__all__ = ["PtyPool", "PtySession", "app"]
