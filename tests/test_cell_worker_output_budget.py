"""C0/C1: real local PTY retains the cell protocol budget without changing legacy."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from fa.execution.cell_worker import CellWorker, _cell_pool
from fa.execution.protocol import MAX_TAIL_BYTES
from fa.runtime import pty_pool
from fa.runtime.pty_pool import PtyResult, PtySession
from tests.test_execution_cell_worker import run_message
from tests.test_pty_tmux_fake import _Server


def _pexpect_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_tmux(_name: str) -> None:
        return None

    monkeypatch.setattr(pty_pool, "shutil", SimpleNamespace(which=no_tmux))


def test_cell_real_pty_preserves_envelope_above_legacy_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _pexpect_only(monkeypatch)
    worker = CellWorker(_cell_pool(tmp_path), workspace=tmp_path, max_command_ms=10000)
    try:
        result = worker.handle(run_message("python3 -c 'print(\"x\" * 60000)'", timeout_ms=8000))
        assert result["exit_code"] == 0 and result["timed_out"] is False
        assert result["truncated"] is False and result["stdout"] == "x" * 60000
    finally:
        worker.close()


def test_legacy_pty_still_truncates_at_old_limit(tmp_path: Path) -> None:
    session = PtySession("legacy", tmp_path, server=None)
    try:
        result = session.run("python3 -c 'print(\"x\" * 35000)'", timeout=8)
        assert result.exit_code == 0 and result.truncated is True
        assert "showing last 30000 chars" in result.stdout
    finally:
        session.close()


@pytest.mark.parametrize("count,truncated", [(MAX_TAIL_BYTES, False), (MAX_TAIL_BYTES + 1, True)])
def test_cell_ascii_tail_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int, truncated: bool) -> None:
    _pexpect_only(monkeypatch)
    worker = CellWorker(_cell_pool(tmp_path), workspace=tmp_path, max_command_ms=10000)
    try:
        command = f"python3 -c 'import sys; sys.stdout.write(\"x\" * {count})'"
        result = worker.handle(run_message(command, timeout_ms=8000))
        assert result["exit_code"] == 0
        assert result["truncated"] is truncated
        assert len(result["stdout"].encode()) <= MAX_TAIL_BYTES
        if not truncated:
            assert result["stdout"] == "x" * count
    finally:
        worker.close()


@pytest.mark.parametrize("count,truncated", [(20000, False), (40000, True)])
def test_cell_unicode_byte_limit_is_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int, truncated: bool
) -> None:
    _pexpect_only(monkeypatch)
    worker = CellWorker(_cell_pool(tmp_path), workspace=tmp_path, max_command_ms=10000)
    try:
        result = worker.handle(run_message(f"python3 -c 'print(chr(0x44f) * {count})'", timeout_ms=8000))
        assert result["exit_code"] == 0 and result["truncated"] is truncated
        assert len(result["stdout"].encode("utf-8")) <= MAX_TAIL_BYTES
        if not truncated:
            assert result["stdout"] == "я" * count
    finally:
        worker.close()


def test_tmux_adapter_honours_configured_output_limit(tmp_path: Path) -> None:
    server = _Server()
    session = PtySession("tmux-budget", tmp_path, server=cast(Any, server), output_limit=MAX_TAIL_BYTES)
    original = server.pane.send_keys

    def send(command: str, **kwargs: object) -> None:
        original(command, **kwargs)
        server.pane.response = server.pane.response.replace("output", "x" * 35000)

    server.pane.send_keys = send  # type: ignore[method-assign]
    try:
        result = session.run("echo ignored", timeout=2)
        assert result.exit_code == 7 and not result.truncated and result.stdout == "x" * 35000
    finally:
        session.close()


@pytest.mark.parametrize("bad", [0, -1, True])
def test_invalid_output_limit_is_rejected_before_session_creation(tmp_path: Path, bad: int) -> None:
    with pytest.raises(ValueError, match="output_limit"):
        PtySession("bad", tmp_path, output_limit=bad)
    with pytest.raises(ValueError, match="output_limit"):
        pty_pool.PtyPool(base_cwd=tmp_path, output_limit=bad)


def test_cell_preserves_pty_truncation_even_for_short_tail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _pexpect_only(monkeypatch)

    def truncated(self: PtySession, command: str, timeout: float = 30) -> PtyResult:
        return PtyResult("tail", 0, True, self.session_id)

    monkeypatch.setattr(PtySession, "run", truncated)
    worker = CellWorker(_cell_pool(tmp_path), workspace=tmp_path, max_command_ms=10000)
    try:
        result = worker.handle(run_message("fixture"))
        assert result["stdout"] == "tail" and result["truncated"] is True
    finally:
        worker.close()
