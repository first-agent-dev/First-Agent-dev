"""fa.runtime — EventStream Runtime for stateful bash

ADR-13: Stateful Bash via EventStream Runtime (FastAPI + PTY Pool)
Graceful degradation: server.app may be None if FastAPI not installed.
"""

import logging

from .pty_pool import PtyPool, PtySession

_logger = logging.getLogger(__name__)

try:
    from .server import app
except ImportError as exc:
    # Graceful degradation per review Gap 1: tests requiring only PtyPool
    # must work without FastAPI. Log WARNING and continue.
    _logger.warning(
        "Failed to import fa.runtime.server: %s — app=None, continuing",
        exc,
    )
    app = None  # type: ignore

__all__ = ["PtyPool", "PtySession", "app"]
