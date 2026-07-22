"""C2 tests for the deferred optional FastAPI runtime boundary."""

from __future__ import annotations

import fa.runtime
import fa.runtime.server as server


def test_deferred_runtime_import_is_graceful_without_fastapi() -> None:
    """Core runtime remains importable when the deferred server extra is absent."""
    if not server.HAS_FASTAPI:
        assert server.app is None
        assert fa.runtime.app is None
    else:
        # If an environment explicitly installs the deferred extra, the app
        # must be constructed rather than silently pretending it is absent.
        assert server.app is not None
        assert fa.runtime.app is not None


def test_deferred_runtime_exports_pty_pool_independently() -> None:
    """The PTY runtime remains usable without the optional HTTP server."""
    assert fa.runtime.PtyPool is not None
    assert fa.runtime.PtySession is not None
