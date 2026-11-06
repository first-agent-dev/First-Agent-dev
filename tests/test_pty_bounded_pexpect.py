"""C0/C1/C3: opt-in pexpect streaming; not a worker or Docker acceptance test."""

from __future__ import annotations

import shlex
import tracemalloc
from collections.abc import Iterator
from pathlib import Path

import pytest

from fa.runtime.pty_pool import PtySession


@pytest.fixture
def session(tmp_path: Path) -> Iterator[PtySession]:
    value = PtySession("bounded", tmp_path, server=None)
    if value._fallback is None:
        pytest.fail("real pexpect shell unavailable")
    try:
        yield value
    finally:
        value.close()


def _python(script: str) -> str:
    return "python3 -c " + shlex.quote(script)


@pytest.mark.parametrize("count,truncated", [(4096, False), (4097, True), (1000000, True)])
def test_capture_exact_limit_and_tail(session: PtySession, count: int, truncated: bool) -> None:
    result = session.run(_python(f'import sys; sys.stdout.write("x" * {count})'), timeout=8, capture_chars=4096)
    assert result.exit_code == 0 and not result.timed_out and result.truncated is truncated
    if not truncated:
        assert result.stdout == "x" * count
    else:
        assert result.stdout.endswith("x" * 4096) and len(result.stdout) <= 4096 + 80


def test_one_byte_reads_preserve_every_near_marker_and_utf8(session: PtySession) -> None:
    session._fallback.maxread = 1
    token = session._end_token
    # Every proper prefix, followed by a non-matching character, and Unicode.
    text = "".join(token[:i] + "X" for i in range(1, len(token))) + "ё😀"
    result = session.run(_python(f"import sys; sys.stdout.write({text!r})"), timeout=8, capture_chars=4096)
    assert result.exit_code == 0 and not result.truncated and result.stdout == text
    assert session.run("printf recovered", timeout=3).stdout == "recovered"


def test_long_near_marker_stream_is_neither_lost_nor_false_success(session: PtySession) -> None:
    near = session._end_token[:-1] + "X"
    text = near * 10000
    result = session.run(_python(f"import sys; sys.stdout.write({near!r} * 10000)"), timeout=8, capture_chars=200000)
    assert result.exit_code == 0 and not result.timed_out and not result.truncated
    assert result.stdout == text


def test_timeout_preserves_explicit_failure_and_reclaims_shell(session: PtySession) -> None:
    command = _python('import sys\nwhile True:\n sys.stdout.write("x" * 4096); sys.stdout.flush()')
    result = session.run(command, timeout=0.25, capture_chars=4096)
    assert result.timed_out is True and result.exit_code == -1 and result.truncated is True
    assert len(result.stdout) <= 4096 + 200
    recovered = session.run("printf recovered", timeout=5, capture_chars=4096)
    assert recovered.exit_code == 0 and recovered.stdout == "recovered" and not recovered.truncated
    assert session.run("cd /", timeout=5, capture_chars=4096).exit_code == 0
    assert session.run("pwd", timeout=5, capture_chars=4096).stdout == "/"


def test_opt_in_stream_has_bounded_python_peak_memory(session: PtySession) -> None:
    # The producer emits six MiB; the consumer retains 4 KiB. Tracing this
    # process catches a regression to pexpect's unbounded `before` buffer.
    command = _python('import sys; sys.stdout.write("x" * (6 * 1024 * 1024))')
    tracemalloc.start()
    try:
        result = session.run(command, timeout=15, capture_chars=4096)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.exit_code == 0 and result.truncated and result.stdout.endswith("x" * 4096)
    assert peak < 2 * 1024 * 1024, f"capture allocation grew with output: peak={peak}"


def test_nonzero_exit_is_not_synthesised_as_success(session: PtySession) -> None:
    result = session.run("printf failure; exit 7", timeout=4, capture_chars=4096)
    assert result.exit_code == 7 and result.stdout == "failure" and not result.timed_out


def test_dead_shell_eof_is_not_timeout_or_success(session: PtySession) -> None:
    result = session.run("kill -KILL $$", timeout=4, capture_chars=4096)
    assert result.exit_code == -1 and result.timed_out is False and result.truncated is True


def test_discarded_raw_output_cannot_become_untruncated_after_cr_normalization(session: PtySession) -> None:
    command = _python('import sys; sys.stdout.write("x" * 100000 + "\\rZ")')
    result = session.run(command, timeout=5, capture_chars=4096)
    assert result.exit_code == 0 and not result.timed_out
    assert result.stdout == "Z" and result.truncated is True


def test_near_marker_stream_has_bounded_python_peak_memory(session: PtySession) -> None:
    near = session._end_token[:-1] + "X"
    command = _python(f"import sys; sys.stdout.write({near!r} * 150000)")
    tracemalloc.start()
    try:
        result = session.run(command, timeout=15, capture_chars=4096)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.exit_code == 0 and result.truncated and result.stdout.endswith((near * 400)[-4096:])
    assert peak < 2 * 1024 * 1024, f"near-marker capture allocation grew: peak={peak}"


def test_failed_interrupt_reclaim_closes_session_before_another_command(
    session: PtySession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A command that does not react to the interrupt must never share its shell
    # with a subsequent request. No production streaming algorithm is mocked.
    def ignore_interrupt(_key: str) -> None:
        return None

    child = session._fallback
    monkeypatch.setattr(child, "sendcontrol", ignore_interrupt)
    try:
        first = session.run("sleep 4", timeout=0.1, capture_chars=4096)
        assert first.exit_code == -1 and first.timed_out and first.truncated
        assert session._fallback is None and not child.isalive()
        marker = tmp_path / "must-not-exist"
        next_result = session.run("touch " + shlex.quote(str(marker)), timeout=2, capture_chars=4096)
        assert next_result.exit_code == -1 and not marker.exists()
    finally:
        if child.isalive():
            child.close(force=True)


def test_decode_failure_does_not_reuse_unknown_shell(session: PtySession, tmp_path: Path) -> None:
    result = session.run(_python("import os; os.write(1, bytes([255]))"), timeout=5, capture_chars=4096)
    assert result.exit_code == -1 and not result.timed_out and result.truncated
    marker = tmp_path / "must-not-exist-after-decode"
    subsequent = session.run("touch " + shlex.quote(str(marker)), timeout=2, capture_chars=4096)
    assert subsequent.exit_code == -1 and not marker.exists()
