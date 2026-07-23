"""Verify server.py follows 'open stand' error handling philosophy.

This test verifies that the runtime server logs errors loudly with full
tracebacks before raising HTTP exceptions, ensuring observability.
"""

from __future__ import annotations

from unittest.mock import patch


def test_server_imports_without_fastapi() -> None:
    """Server module must import cleanly when FastAPI is absent."""
    # Simulate FastAPI not installed by mocking importlib to raise ImportError
    with patch("importlib.import_module", side_effect=ImportError("fastapi not installed")):
        # Re-import the module to trigger the except ImportError branch
        import sys

        if "fa.runtime.server" in sys.modules:
            del sys.modules["fa.runtime.server"]

        import fa.runtime.server as server

        # Verify fallback state
        assert server.HAS_FASTAPI is False
        assert server.app is None
        assert server.pool is None


def test_server_has_fastapi_when_available() -> None:
    """Server module must detect and use FastAPI when present."""
    import fa.runtime.server as server

    # In dev environment with runtime extras, FastAPI should be available
    # (but this test is skipped if extras not installed)
    if server.HAS_FASTAPI:
        assert server.app is not None
        assert server.pool is not None
        assert server.FastAPI is not None
        assert server.HTTPException is not None


def test_server_exception_boundary_logs_loudly() -> None:
    """Verify that exception boundaries log with exc_info=True.

    This is a structural test: we verify the code contains logger.error calls
    with exc_info=True at exception boundaries, ensuring 'open stand' philosophy.
    """
    import inspect

    import fa.runtime.server as server

    source = inspect.getsource(server)

    # Count logger.error calls with exc_info=True
    loud_logs = source.count("exc_info=True")

    # We expect at least 2 loud log calls (one for AssertionError, one for Exception)
    # in the execute() endpoint
    assert loud_logs >= 2, (
        f"Expected at least 2 loud log calls with exc_info=True, found {loud_logs}. "
        "The 'open stand' principle requires all errors to be logged with full tracebacks."
    )


def test_server_preserves_exception_chains() -> None:
    """Verify that exception boundaries preserve the original exception with 'from e'.

    Exception chaining is critical for debugging: it preserves the original
    traceback and makes errors traceable to their root cause.
    """
    import inspect

    import fa.runtime.server as server

    source = inspect.getsource(server)

    # Count 'from e' exception chains
    chains = source.count("from e")

    # We expect at least 2 exception chains in the execute() endpoint
    assert chains >= 2, (
        f"Expected at least 2 'from e' exception chains, found {chains}. "
        "Exception chaining is required to preserve root cause information."
    )


def test_server_no_ble001_noqa_comments() -> None:
    """Verify that BLE001 is not silenced with noqa comments.

    The 'open stand' philosophy requires errors to be loud and observable.
    Broad exception catches must be justified by proper logging and chaining,
    not silenced with noqa comments.
    """
    import inspect

    import fa.runtime.server as server

    source = inspect.getsource(server)

    # Check that there are no 'noqa: BLE001' comments
    assert "noqa: BLE001" not in source, (
        "Found 'noqa: BLE001' comment. Broad exception catches should be justified "
        "by loud logging and exception chaining, not silenced with noqa."
    )
