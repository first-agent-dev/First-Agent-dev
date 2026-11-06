"""C0/C1/C3: per-call capture supplier; no worker/host cutover claim."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, override

import pytest

from fa.runtime.pty_pool import PtyResult, PtySession
from tests.test_pty_tmux_fake import _Server


class _HistoryServer(_Server):
    def __init__(self, local: str | None = None, *, fail_set: bool = False, fail_restore: bool = False) -> None:
        super().__init__()
        cast(Any, self.pane).pane_id = "%9"
        self.local = local
        self.fail_set = fail_set
        self.fail_restore = fail_restore
        self.option_calls: list[tuple[str, ...]] = []

    @override
    def cmd(self, *args: str) -> SimpleNamespace:
        self.option_calls.append(args)
        if args[0] == "show-options":
            return SimpleNamespace(
                returncode=0, stdout=[] if self.local is None else [f"history-limit {self.local}"], stderr=[]
            )
        if args[0] == "display-message":
            return SimpleNamespace(returncode=0, stdout=[self.local or "2000"], stderr=[])
        if args[0] == "set-option":
            restoring = args[1] == "-wu" or args[-1] != "10000"
            self.local = None if args[1] == "-wu" else args[-1]
            failed = self.fail_restore if restoring else self.fail_set
            return SimpleNamespace(returncode=1 if failed else 0, stdout=[], stderr=["failed"] if failed else [])
        return SimpleNamespace(returncode=0, stdout=[], stderr=[])


@pytest.mark.parametrize("initial", [None, "3500"])
def test_tmux_capture_is_addressed_and_restores_local_or_inherited(tmp_path: Path, initial: str | None) -> None:
    server = _HistoryServer(initial)
    session = PtySession("large", tmp_path, server=cast(Any, server))
    try:
        result = session.run("echo result", timeout=1, capture_chars=2_500_000, history_lines=10000)
        assert result.exit_code == 7 and result.stdout == "output" and not result.truncated
        assert server.local == initial
        assert server.option_calls[0] == ("show-options", "-w", "-t", "%9", "history-limit")
        assert server.option_calls[1] == ("display-message", "-p", "-t", "%9", "#{history_limit}")
        assert server.option_calls[2] == ("set-option", "-w", "-t", "%9", "history-limit", "10000")
        assert server.option_calls[3] == (
            ("set-option", "-wu", "-t", "%9", "history-limit")
            if initial is None
            else ("set-option", "-w", "-t", "%9", "history-limit", initial)
        )
        assert session._output_limit == 30000
    finally:
        session.close()


def test_setting_failure_restores_and_never_sends_command(tmp_path: Path) -> None:
    server = _HistoryServer(fail_set=True)
    session = PtySession("failure", tmp_path, server=cast(Any, server))
    before = list(server.pane.sent)
    try:
        with pytest.raises(RuntimeError, match="capture_history_unavailable"):
            session.run("echo forbidden", capture_chars=100000, history_lines=10000)
        assert server.pane.sent == before
        assert server.local is None and session._output_limit == 30000
    finally:
        session.close()


def test_restore_failure_never_returns_command_success(tmp_path: Path) -> None:
    server = _HistoryServer(fail_restore=True)
    session = PtySession("restore-failure", tmp_path, server=cast(Any, server))
    try:
        with pytest.raises(RuntimeError, match="capture_history_unavailable"):
            session.run("echo ran", capture_chars=100000, history_lines=10000)
        assert any("echo ran" in sent for sent in server.pane.sent)
        assert session._output_limit == 30000
    finally:
        session.close()


@pytest.mark.parametrize(
    ("capture", "history"),
    [(0, None), (-1, None), (True, None), (8 * 1024 * 1024 + 1, None), (None, 1), (1, 0), (1, True), (1, 32769)],
)
def test_invalid_limits_fail_before_command_or_tmux_options(
    tmp_path: Path, capture: int | None, history: int | None
) -> None:
    server = _HistoryServer()
    session = PtySession("bad", tmp_path, server=cast(Any, server))
    before = list(server.pane.sent)
    try:
        with pytest.raises(ValueError):
            session.run("echo forbidden", capture_chars=capture, history_lines=history)
        assert server.pane.sent == before and server.option_calls == []
    finally:
        session.close()


def test_normal_tmux_run_has_no_history_options(tmp_path: Path) -> None:
    server = _HistoryServer()
    session = PtySession("legacy", tmp_path, server=cast(Any, server))
    try:
        assert session.run("echo legacy").exit_code == 7
        assert server.option_calls == []
    finally:
        session.close()


def test_real_pexpect_capture_is_temporary_and_legacy_is_unchanged(tmp_path: Path) -> None:
    session = PtySession("pexpect", tmp_path, server=None)
    try:
        if session._fallback is None:
            pytest.fail("pexpect must be available for this local test")
        command = "python3 -c 'print(\"x\" * 35000)'"
        expanded = session.run(command, timeout=8, capture_chars=40000, history_lines=10000)
        assert expanded.exit_code == 0 and not expanded.truncated and expanded.stdout == "x" * 35000
        legacy = session.run(command, timeout=8)
        assert legacy.exit_code == 0 and legacy.truncated and "showing last 30000 chars" in legacy.stdout
    finally:
        session.close()


def test_concurrent_calls_cannot_observe_temporary_capture_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = PtySession("serial", tmp_path, server=None)
    entered, release, second_started, second_entered = (threading.Event() for _ in range(4))
    seen: list[tuple[str, int]] = []

    def run_fallback(command: str, timeout: float, *, bounded: bool = False) -> PtyResult:
        seen.append((command, session._output_limit))
        if command == "first":
            entered.set()
            assert release.wait(5)
        else:
            second_entered.set()
        return PtyResult("ok", 0, False, session.session_id)

    monkeypatch.setattr(session, "_run_fallback", run_fallback)
    first = threading.Thread(target=lambda: session.run("first", capture_chars=40000))

    def run_second() -> None:
        second_started.set()
        session.run("second")

    second = threading.Thread(target=run_second)
    try:
        first.start()
        assert entered.wait(5)
        second.start()
        assert second_started.wait(5) and not second_entered.wait(0.05)
    finally:
        release.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
        session.close()
    assert not first.is_alive() and not second.is_alive()
    assert seen == [("first", 40000), ("second", 30000)]


def test_malformed_pane_id_fails_before_command(tmp_path: Path) -> None:
    server = _HistoryServer()
    cast(Any, server.pane).pane_id = "%9; injection"
    session = PtySession("bad-pane", tmp_path, server=cast(Any, server))
    before = list(server.pane.sent)
    try:
        with pytest.raises(RuntimeError, match="capture_history_unavailable"):
            session.run("echo forbidden", capture_chars=100000, history_lines=10000)
        assert server.pane.sent == before and server.option_calls == []
    finally:
        session.close()


def test_timeout_preserves_signal_and_restores_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = _HistoryServer("3500")
    session = PtySession("timeout", tmp_path, server=cast(Any, server))

    def timed_out(_command: str, _timeout: float) -> PtyResult:
        return PtyResult("partial", -1, True, session.session_id, timed_out=True)

    monkeypatch.setattr(session, "_run_tmux", timed_out)
    try:
        result = session.run("sleep 99", capture_chars=100000, history_lines=10000)
        assert result.timed_out is True and result.exit_code == -1 and result.truncated is True
        assert server.local == "3500" and session._output_limit == 30000
    finally:
        session.close()


def test_capture_never_shrinks_an_existing_larger_window_limit(tmp_path: Path) -> None:
    server = _HistoryServer("15000")
    session = PtySession("large-existing", tmp_path, server=cast(Any, server))
    try:
        result = session.run("echo result", capture_chars=100000, history_lines=10000)
        assert result.exit_code == 7 and server.local == "15000"
        assert [call[0] for call in server.option_calls] == ["show-options", "display-message"]
    finally:
        session.close()


def test_capture_refuses_oversized_existing_history_without_changing_it(tmp_path: Path) -> None:
    server = _HistoryServer("40000")
    session = PtySession("too-large", tmp_path, server=cast(Any, server))
    before = list(server.pane.sent)
    try:
        with pytest.raises(RuntimeError, match="capture_history_unavailable"):
            session.run("echo forbidden", capture_chars=100000, history_lines=10000)
        assert server.local == "40000" and server.pane.sent == before
        assert [call[0] for call in server.option_calls] == ["show-options", "display-message"]
    finally:
        session.close()
