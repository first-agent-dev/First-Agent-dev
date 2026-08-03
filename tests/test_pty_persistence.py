"""
Tests for ADR-13: StatefulPtyManager persistence, ANSI stripping, Ctrl+C, defensive worktree checks.
"""

from pathlib import Path

from tests._capabilities import requires_pty_backend

# These tests require fa-runtime-server running or pexpect fallback
# For unit tests without tmux, PtyPool falls back to pexpect


@requires_pty_backend
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


@requires_pty_backend
def test_pty_env_persistence() -> None:
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_env")
    session.run("export FOO=bar")
    result = session.run("echo $FOO")
    assert "bar" in result.stdout, f"Expected bar in {result.stdout}"
    pool.kill("test_env")


@requires_pty_backend
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


@requires_pty_backend
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


@requires_pty_backend
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


@requires_pty_backend
def test_sequential_commands_do_not_bleed_into_each_other() -> None:
    """C1 regression: PtySession._run_tmux must not return a PRIOR command's
    output for the current invocation.

    kill-check: before this fix, _run_tmux matched on the SESSION-lifetime
    self._exit_token/self._end_token, reused across every run() call. tmux
    capture-pane always returns the pane's full persistent scrollback, so
    once a token had appeared once, `str.split(token)[0]` on a later call
    matched the FIRST (oldest / already-echoed) occurrence, silently
    returning the wrong command's output. Reverting to a session-lifetime
    token set (removing the per-invocation FA_START_<call_id> marker and
    positional-match extraction) reproduces this failure.
    """
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_no_bleed")
    try:
        results = [session.run(f"echo cmd{i}") for i in range(5)]
        for i, result in enumerate(results):
            assert result.stdout == f"cmd{i}", (
                f"call {i} returned {result.stdout!r} — cross-command output bleed "
                "(session-lifetime sentinel reuse regression)"
            )
    finally:
        pool.kill("test_no_bleed")


@requires_pty_backend
def test_slow_command_does_not_return_stale_prior_result() -> None:
    """C1 regression: a slow command must not complete-early with a PRIOR
    command's (already-satisfied) end-of-command marker.

    kill-check: with session-lifetime tokens, running `sleep 2 && echo X`
    right after a fast command matched the fast command's already-present
    end_token in the pane's persistent scrollback and returned immediately
    (observed: <0.05s) with the PRIOR command's stdout — before the sleep
    even started. This is not just a display bug: the caller (fs.run_bash)
    would report a not-yet-executed command as complete. Per-invocation
    unique markers make stale matches impossible; assert elapsed time
    proves the harness actually waited for the real command to finish.
    """
    import time

    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_no_stale_race")
    try:
        session.run("echo warm_up")

        start = time.time()
        result = session.run("sleep 1.5 && echo SLOW_DONE", timeout=10)
        elapsed = time.time() - start

        assert result.stdout == "SLOW_DONE"
        assert elapsed >= 1.3, (
            f"returned after {elapsed:.2f}s — command likely matched a STALE "
            "end-of-command marker from the prior run() call instead of "
            "waiting for its own completion (session-lifetime sentinel "
            "reuse regression)"
        )
    finally:
        pool.kill("test_no_stale_race")


@requires_pty_backend
def test_heredoc_command_completes_via_active_backend() -> None:
    """C1 regression: a command containing a heredoc (`<<'WORD' ... WORD`)
    must complete, not hang until the caller's timeout — on WHICHEVER
    backend PtyPool resolves to (tmux if the binary is present, pexpect
    fallback otherwise).

    Root cause: both PtySession._run_tmux and PtySession._run_fallback
    wrapped every non-stateful command as a single string
    `(command); echo <exit_token>:$? <end_token>`. POSIX requires a
    heredoc's closing delimiter to appear ALONE on its own line;
    appending `); echo ...` (or even a bare `)`) immediately after the
    delimiter breaks that, and the shell waits forever for a delimiter
    line that never arrives — reproduced directly against bash outside
    of tmux/pexpect, independent of pty backend.

    History: the first fix for this only patched `_run_tmux`, leaving
    `_run_fallback` with the identical hang. It went undetected because
    the original regression test ran on a machine WITH the tmux binary
    installed, so it only ever exercised `_run_tmux`. `PtyPool` silently
    falls back to pexpect when `tmux` is not on PATH (see
    `test_heredoc_command_completes_via_pexpect_fallback` below for a
    backend-FORCED kill-check that cannot silently skip either path).

    kill-check: routing this command through the single-line "(command);
    echo ..." wrapper (reverting the temp-script-file routing) makes this
    test fail via timeout (PtyResult.timed_out=True), not merely produce
    wrong output — the difference between "hung" and "fast" is the
    signal that proves the fix is live, not just cosmetically applied.
    """
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_heredoc")
    try:
        result = session.run("python3 - <<'PY'\nprint('heredoc-marker-9001')\nPY", timeout=10)
        assert not result.timed_out, "heredoc command hung until timeout instead of completing"
        assert result.exit_code == 0
        assert "heredoc-marker-9001" in result.stdout
    finally:
        pool.kill("test_heredoc")


@requires_pty_backend
def test_heredoc_command_completes_via_pexpect_fallback() -> None:
    """C1 regression, pexpect-path SPECIFIC: same claim as
    test_heredoc_command_completes_via_active_backend, but calls
    PtySession._run_fallback directly so the assertion holds
    regardless of whether tmux is installed on the machine running
    the suite (dev laptops without tmux, CI runners with it — both
    must be covered, not whichever one the ambient environment picks).

    kill-check: reverting _run_fallback's command construction to embed
    the heredoc inline (without routing through _resolve_heredoc_command)
    makes this test fail via timeout, identically to the tmux-path test.
    """
    from fa.runtime.pty_pool import PtySession

    session = PtySession("test_heredoc_pexpect", Path("/tmp"), server=None)
    assert session._is_fallback, "expected pexpect fallback path for this test"
    result = session._run_fallback("python3 - <<'PY'\nprint('heredoc-marker-9001')\nPY", timeout=10)
    assert not result.timed_out, "heredoc command hung until timeout instead of completing"
    assert result.exit_code == 0
    assert "heredoc-marker-9001" in result.stdout


@requires_pty_backend
def test_timed_out_field_distinguishes_timeout_from_other_failures() -> None:
    """C1 regression: PtyResult.timed_out must be True only for an actual
    timeout, not for every -1 exit_code failure mode.

    Root cause: fa.inner_loop.tools.run_bash previously detected a PtyPool
    timeout by checking `"Timeout" in stdout` — a heuristic that only ever
    matched the pexpect fallback path's message shape. PtySession._run_tmux
    never populated a matching substring on its own timeout path, so the
    tmux-backed timeout fallback-to-subprocess retry silently never fired.

    kill-check: asserting `PtyResult.timed_out` directly (not string-
    matching `"Timeout" in result.stdout`) fails if the field is removed
    or hardcoded to False — proving the signal is real, not vacuous.
    """
    from fa.runtime.pty_pool import PtyPool

    pool = PtyPool(max_size=1, base_cwd=Path("/tmp"))
    session = pool.acquire("test_timed_out_field")
    try:
        timeout_result = session.run("sleep 5", timeout=1)
        assert timeout_result.timed_out is True
        assert timeout_result.exit_code == -1

        ok_result = session.run("echo fine", timeout=5)
        assert ok_result.timed_out is False
        assert ok_result.exit_code == 0
    finally:
        pool.kill("test_timed_out_field")
