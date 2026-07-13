"""
Tests for ADR-13: StatefulPtyManager persistence, ANSI stripping, Ctrl+C, defensive worktree checks
Prior art: OpenHands, OpenCode ShellPool, pi-persistent-term
"""

import pytest
from pathlib import Path

# These tests require fa-runtime-server running or pexpect fallback
# For unit tests without tmux, PtyPool falls back to pexpect

def test_pty_persistence_cd():
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

def test_pty_env_persistence():
    from fa.runtime.pty_pool import PtyPool
    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_env")
    session.run("export FOO=bar")
    result = session.run("echo $FOO")
    assert "bar" in result.stdout, f"Expected bar in {result.stdout}"
    pool.kill("test_env")

def test_ansi_strip():
    from fa.runtime.pty_pool import PtyPool
    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_ansi")
    # ls --color=always emits ANSI, should be stripped
    result = session.run("ls --color=always /tmp | head -n 1")
    # ANSI codes like \x1b[ should not be in output after stripping
    assert "\x1b[" not in result.stdout, f"ANSI not stripped: {result.stdout!r}"
    pool.kill("test_ansi")

def test_ctrl_c():
    from fa.runtime.pty_pool import PtyPool
    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_ctrlc")
    # Start sleep in background? Actually send sleep 10 then Ctrl+C
    import threading

    def run_sleep():
        session.run("sleep 10", timeout=2)  # should timeout

    thread = threading.Thread(target=run_sleep)
    thread.start()
    import time
    time.sleep(0.5)
    msg = session.send_ctrl_c()
    assert "Ctrl+C" in msg or "ready" in msg.lower()
    thread.join(timeout=2)
    pool.kill("test_ctrlc")
