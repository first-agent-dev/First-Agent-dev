from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

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
        end = re.search(r"(FA_EXIT_[^: ]+):\$\? (FA_END_[^ ]+)", command)
        if end:
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
