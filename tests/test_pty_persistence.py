"""
Tests for ADR-13: StatefulPtyManager persistence, ANSI stripping, Ctrl+C, defensive worktree checks.
"""

from pathlib import Path

# These tests require fa-runtime-server running or pexpect fallback
# For unit tests without tmux, PtyPool falls back to pexpect


def test_pty_persistence_cd() -> None:
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_cd")
    # First command cd /tmp
    result1 = session.run("cd /tmp && pwd")
    assert "/tmp" in result1.stdout, f"Expected /tmp in {result1.stdout}"
    # Second command should stay in /tmp if stateful
    result2 = session.run("pwd")
    assert "/tmp" in result2.stdout, f"Expected /tmp persistence, got {result2.stdout}"
    pool.kill("test_cd")


def test_pty_env_persistence() -> None:
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_env")
    session.run("export FOO=bar")
    result = session.run("echo $FOO")
    assert "bar" in result.stdout, f"Expected bar in {result.stdout}"
    pool.kill("test_env")


def test_ansi_strip() -> None:
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_ansi")
    # ls --color=always emits ANSI, should be stripped
    result = session.run("ls --color=always /tmp | head -n 1")
    assert "\x1b[" not in result.stdout, f"ANSI not stripped: {result.stdout!r}"
    pool.kill("test_ansi")


def test_resolve_cr_basic() -> None:
    from fa.runtime.pty_pool import resolve_cr

    assert resolve_cr("foo\rbar\n") == "bar"
    assert resolve_cr("12%\r34%\r56%") == "56%"


def test_carriage_returns_cleaned_in_session_output() -> None:
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_cr")
    result = session.run("printf 'foo\\rbar\\n'")
    assert "\r" not in result.stdout
    assert result.stdout.endswith("bar")
    pool.kill("test_cr")


def test_helper_fallback_without_child_returns_structured_failure(tmp_path: Path) -> None:
    """C2: PTY fallback helper fails closed when the child is unavailable."""
    from fa.runtime.pty_pool import PtySession

    session = PtySession("helper-fallback", tmp_path, server=None)
    session._fallback = None
    session._is_fallback = True
    result = session._run_fallback("pwd", timeout=1)
    assert result.exit_code == -1
    assert result.stdout == "No fallback available"


def test_helper_tmux_without_pane_returns_structured_failure(tmp_path: Path) -> None:
    """C2: tmux helper fails closed when no pane is available."""
    from fa.runtime.pty_pool import PtySession

    session = PtySession("helper-tmux", tmp_path, server=None)
    session._is_fallback = False
    session.pane = None
    result = session._run_tmux("pwd", timeout=1)
    assert result.exit_code == -1
    assert result.stdout == "No pane available"


def test_ctrl_c() -> None:
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_ctrlc")
    # Start sleep in background? Actually send sleep 10 then Ctrl+C
    import threading

    def run_sleep() -> None:
        session.run("sleep 10", timeout=2)  # should timeout

    thread = threading.Thread(target=run_sleep)
    thread.start()
    import time

    time.sleep(0.5)
    msg = session.send_ctrl_c()
    assert "Ctrl+C" in msg or "ready" in msg.lower()
    thread.join(timeout=2)
    assert not thread.is_alive(), "PtySession.run thread did not stop after Ctrl+C"
    pool.kill("test_ctrlc")
