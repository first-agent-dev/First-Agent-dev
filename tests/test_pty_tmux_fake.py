from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, override

from fa.runtime.pty_pool import PoolExhaustedError, PtyPool, PtySession


class _Pane:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.ready = ""
        self.response = ""

    def send_keys(self, command: str, **_: object) -> None:
        self.sent.append(command)
        ready = re.search(r"FA_READY_[^' ]+", command)
        if ready:
            self.ready = ready.group(0)
        # Fake simulates the real PtySession._run_tmux wire protocol: a
        # per-invocation start marker echoed first (`echo FA_START_<id>`),
        # then the command's real output, then the exit/end marker line.
        # This mirrors what real tmux capture-pane returns: the shell
        # echoes back what was typed before executing it, so the start
        # marker line precedes the actual command output in the pane.
        start = re.search(r"FA_START_[^' ;]+", command)
        end = re.search(r"(FA_EXIT_[^: ]+):\$\? (FA_END_[^ ]+)", command)
        if start and end:
            self.response = f"{start.group(0)}\noutput\n{end.group(1)}:7 {end.group(2)}"
        elif end:
            self.response = f"output\n{end.group(1)}:7 {end.group(2)}"

    def cmd(self, *_: str) -> SimpleNamespace:
        return SimpleNamespace(stdout=[self.ready if not self.response else self.response])


class _TmuxSession:
    def __init__(self, pane: _Pane) -> None:
        self.active_window = SimpleNamespace(active_pane=pane)
        self.killed = False

    def kill(self) -> None:
        self.killed = True


class _Server:
    socket_name = "fa_test"

    def __init__(self) -> None:
        self.pane = _Pane()
        self.session = _TmuxSession(self.pane)
        self.commands: list[tuple[str, ...]] = []

    def new_session(self, **_: object) -> _TmuxSession:
        return self.session

    def find_where(self, _: dict[str, str]) -> _TmuxSession:
        return self.session

    def cmd(self, *args: str) -> SimpleNamespace:
        self.commands.append(args)
        return SimpleNamespace(stdout=[])


def test_tmux_session_live_run_and_send_ctrl_c(tmp_path: Path) -> None:
    server = _Server()
    session = PtySession("tmux", tmp_path, server=cast(Any, server))

    result = session.run("echo output", timeout=1)
    assert result.stdout == "output"
    assert result.exit_code == 7
    assert result.session_id == "tmux"

    # Exercise the pane interrupt path and no-pane fail-closed path.
    cast(Any, session)._wait_for_sentinel = lambda timeout=5: None
    assert session.send_ctrl_c() == "Ctrl+C ready"
    session.pane = None
    assert session.send_ctrl_c() == "No pane"
    session.close()
    assert server.session.killed is True


def test_tmux_send_failure_is_structured(tmp_path: Path) -> None:
    server = _Server()
    session = PtySession("tmux-fail", tmp_path, server=cast(Any, server))

    def fail(_: str, **__: object) -> None:
        raise RuntimeError("send failed")

    cast(Any, session.pane).send_keys = fail
    result = session.run("echo", timeout=1)
    assert result.exit_code == -1
    assert "send command" in result.stdout


def test_pool_pins_main_when_no_sub_slot(tmp_path: Path) -> None:
    pool = PtyPool(max_size=1, base_cwd=tmp_path, server=_Server())
    pool.acquire("main")
    try:
        pool.acquire("sub")
    except PoolExhaustedError as exc:
        assert "cannot acquire sub" in str(exc)
    else:
        raise AssertionError("pool should not evict pinned main")
    pool._cleanup_all()


# ── S12.3 (CT3): timeout hygiene — partial output + pane reclaim ─────────────
# Live defect 2026-08-31 (RID cae-l2-1788164790-782783): one 30s bash timeout
# left the orphaned command holding the pane, and the next SEVEN commands —
# including `which uv || which pip` — all returned "Timeout 30s: no output
# captured". Two producers are pinned below: the partial-output accumulation
# (kill-check: without it the timeout path reports "no output captured") and
# the C-c pane reclaim (kill-check: without it the next command times out).


class _TimeoutThenRecoverPane:
    """First command never completes; C-c reclaims; later commands work.

    Wire-faithful: echoes the REAL per-invocation start token in the busy
    scrollback (the poll loop anchors on it via rfind) and uses the same
    end-marker regex as the original _Pane harness above.
    """

    def __init__(self) -> None:
        self.sent: list[str] = []
        self.ready = ""
        self.interrupted = False
        self.pending: tuple[str, str, str] | None = None
        self.response = ""

    def send_keys(self, command: str, **_: object) -> None:
        self.sent.append(command)
        ready = re.search(r"FA_READY_[^' ]+", command)
        if ready:
            self.ready = ready.group(0)
        if command == "C-c":
            self.interrupted = True
            self.pending = None
            self.response = ""
            return
        start = re.search(r"FA_START_[^' ;]+", command)
        end = re.search(r"(FA_EXIT_[^: ]+):\$\? (FA_END_[^ ]+)", command)
        if start and end:
            if self.interrupted:
                self.response = f"{start.group(0)}\nrecovered\n{end.group(1)}:0 {end.group(2)}"
            else:
                self.pending = (start.group(0), end.group(1), end.group(2))

    def cmd(self, *_: str) -> SimpleNamespace:
        if self.pending is not None:
            # Busy pane: this call's start marker + partial output, NO end token.
            return SimpleNamespace(stdout=[f"{self.pending[0]}\npartial-line-1\npartial-line-2"])
        return SimpleNamespace(stdout=[self.ready if not self.response else self.response])


class _TimeoutSession(_TmuxSession):
    def __init__(self, pane: _TimeoutThenRecoverPane) -> None:
        self.active_window = SimpleNamespace(active_pane=pane)
        self.killed = False

    @override
    def kill(self) -> None:
        self.killed = True


class _TimeoutServer:
    socket_name = "fa_s123_test"

    def __init__(self) -> None:
        self.pane = _TimeoutThenRecoverPane()
        self.session = _TimeoutSession(self.pane)

    def new_session(self, **_: object) -> _TimeoutSession:
        return self.session

    def find_where(self, _: dict[str, str]) -> _TimeoutSession:
        return self.session

    def cmd(self, *args: str) -> SimpleNamespace:
        return SimpleNamespace(stdout=[])


def test_timeout_returns_partial_output(tmp_path: Path) -> None:
    """T3a kill-check: the "Timeout Ns partial:" branch was dead code before
    S12.3 — `output` was only assigned on success. Removing the per-poll
    accumulation makes this fall back to "no output captured"."""
    server = _TimeoutServer()
    session = PtySession("s123-partial", tmp_path, server=cast(Any, server))
    result = session.run("sleep 99", timeout=1)
    assert result.timed_out is True
    assert "partial-line-1" in result.stdout, f"partial output lost: {result.stdout!r}"
    assert "Timeout 1s partial" in result.stdout
    session.close()


def test_timeout_sends_ctrl_c_and_next_command_recovers(tmp_path: Path) -> None:
    """T3b kill-check: without the C-c reclaim the pane stays busy and the
    NEXT command also times out — the exact 7-command tax from the live run."""
    server = _TimeoutServer()
    session = PtySession("s123-reclaim", tmp_path, server=cast(Any, server))
    first = session.run("sleep 99", timeout=1)
    assert first.timed_out is True
    assert "C-c" in server.pane.sent, "timeout path never interrupted the pane"
    second = session.run("echo recovered", timeout=1)
    assert second.timed_out is False, f"pane not reclaimed: {second.stdout!r}"
    assert second.stdout == "recovered"
    assert second.exit_code == 0
    session.close()


def test_timeout_survives_sigint_resistant_command(tmp_path: Path) -> None:
    """T3c (P5): _wait_for_sentinel RAISES TimeoutError on expiry
    (pty_pool.py). The reclaim must swallow it — a clean timed_out result,
    never an exception escaping into the tool layer."""
    server = _TimeoutServer()
    session = PtySession("s123-sigint", tmp_path, server=cast(Any, server))

    def raise_timeout(timeout: int = 5) -> None:
        raise TimeoutError("sentinel not found")

    cast(Any, session)._wait_for_sentinel = raise_timeout
    result = session.run("sleep 99", timeout=1)
    assert result.timed_out is True
    assert result.exit_code == -1
    session.close()


def test_timeout_cleans_heredoc_script(tmp_path: Path) -> None:
    """T3d (P6): the heredoc temp script must be removed on the timeout path
    too — _cleanup_script runs before the reclaim block."""
    server = _TimeoutServer()
    session = PtySession("s123-heredoc", tmp_path, server=cast(Any, server))
    result = session.run("cat <<EOF\nhello\nEOF", timeout=1)
    assert result.timed_out is True
    leftovers = list(tmp_path.glob(".fa-bash-*.sh"))
    assert leftovers == [], f"heredoc script leaked on timeout: {leftovers}"
    session.close()


def test_pexpect_timeout_sends_interrupt(tmp_path: Path, monkeypatch: Any) -> None:
    """CT3 pexpect parity: the fallback backend must reclaim its shell too."""
    import pexpect  # type: ignore[import-untyped]  # same waiver as pty_pool.py

    controls: list[str] = []

    class _FakeSpawn:
        encoding = "utf-8"

        def __init__(self) -> None:
            self._expects = 0
            self.before = "partial-output"

        def expect(self, *_a: object, **_k: object) -> int:
            self._expects += 1
            if self._expects == 1:
                return 0  # init sentinel handshake
            raise pexpect.TIMEOUT("command overran")

        def sendcontrol(self, char: str) -> None:
            controls.append(char)

        def sendline(self, *_a: object) -> None:
            pass

    fake = _FakeSpawn()
    monkeypatch.setattr(pexpect, "spawn", lambda *_a, **_k: fake)
    session = PtySession("s123-pexpect", tmp_path, server=None)
    result = session.run("sleep 99", timeout=1)
    assert result.timed_out is True
    assert "partial-output" in result.stdout
    assert controls == ["c"], "pexpect timeout path never interrupted the shell"
