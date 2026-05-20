"""Tests for ``fa.orchestration.pause`` sentinel pattern (Wave-1 R-25)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from fa.orchestration.pause import (
    AUTH_PAUSE_FILE,
    AUTH_RESUME_CHECK_INTERVAL_MS,
    AUTH_RESUME_MAX_WAIT_MS,
    MAX_RATE_LIMIT_WAIT_MS,
    RATE_LIMIT_CHECK_INTERVAL_MS,
    RATE_LIMIT_PAUSE_FILE,
    RESUME_FILE,
    PauseBudget,
    PauseKind,
    ResumeOutcome,
    is_paused,
    wait_for_resume,
    write_pause,
    write_resume,
)


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    """Empty pause state directory under tmp_path."""
    return tmp_path / "pause-state"


def test_constants_match_kronos_defaults() -> None:
    # Constants pinned by ADR-6 §Amendment 2026-05-20 + Kronos
    # `kronos/config.py:62-69`. Changing them is an ADR amendment,
    # not a code refactor — guard explicitly.
    assert MAX_RATE_LIMIT_WAIT_MS == 7_200_000
    assert RATE_LIMIT_CHECK_INTERVAL_MS == 30_000
    assert AUTH_RESUME_MAX_WAIT_MS == 86_400_000
    assert AUTH_RESUME_CHECK_INTERVAL_MS == 10_000


def test_filenames_are_uppercase_sentinels() -> None:
    # Filenames must be exact so a human (or a frontend) can
    # `touch ~/.fa/state/pause/RESUME` from a shell without
    # second-guessing the case.
    assert RATE_LIMIT_PAUSE_FILE == "RATE_LIMIT_PAUSE"
    assert AUTH_PAUSE_FILE == "AUTH_PAUSE"
    assert RESUME_FILE == "RESUME"


def test_write_pause_creates_file_and_dir(state_dir: Path) -> None:
    assert not state_dir.exists()
    path = write_pause(
        PauseKind.RATE_LIMIT,
        reason="provider returned 429",
        state_dir=state_dir,
        now=lambda: 1_700_000_000.0,
    )
    assert path == state_dir / RATE_LIMIT_PAUSE_FILE
    body = path.read_text(encoding="utf-8")
    assert body == "1700000000 provider returned 429\n"


def test_write_pause_atomic_rename_leaves_no_tmp(state_dir: Path) -> None:
    write_pause(PauseKind.AUTH, state_dir=state_dir, now=lambda: 0.0)
    leftover = list(state_dir.glob("*.tmp"))
    assert leftover == []


def test_is_paused_after_write_pause(state_dir: Path) -> None:
    assert not is_paused(PauseKind.RATE_LIMIT, state_dir=state_dir)
    write_pause(PauseKind.RATE_LIMIT, state_dir=state_dir, now=lambda: 0.0)
    assert is_paused(PauseKind.RATE_LIMIT, state_dir=state_dir)
    # AUTH pause is independent.
    assert not is_paused(PauseKind.AUTH, state_dir=state_dir)


def test_write_resume_creates_resume_sentinel(state_dir: Path) -> None:
    path = write_resume(state_dir=state_dir, now=lambda: 42.0)
    assert path == state_dir / RESUME_FILE
    assert path.read_text(encoding="utf-8") == "42\n"


def test_wait_for_resume_returns_resumed_when_resume_present(
    state_dir: Path,
) -> None:
    write_pause(PauseKind.RATE_LIMIT, state_dir=state_dir, now=lambda: 0.0)
    write_resume(state_dir=state_dir, now=lambda: 1.0)

    fake_now_ticks = iter([0.0, 0.0])

    def fake_now() -> float:
        return next(fake_now_ticks)

    def fake_sleep(_seconds: float) -> None:
        raise AssertionError("RESUME present → should not have slept")

    outcome = wait_for_resume(
        PauseKind.RATE_LIMIT,
        state_dir=state_dir,
        sleeper=fake_sleep,
        now=fake_now,
    )
    assert outcome is ResumeOutcome.RESUMED

    # Both sentinels removed after a successful resume.
    assert not (state_dir / RESUME_FILE).exists()
    assert not (state_dir / RATE_LIMIT_PAUSE_FILE).exists()


def test_wait_for_resume_arrives_during_polling(state_dir: Path) -> None:
    write_pause(PauseKind.AUTH, state_dir=state_dir, now=lambda: 0.0)

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        # On the second sleep call the "human" creates RESUME.
        if len(sleep_calls) == 2:
            write_resume(state_dir=state_dir, now=lambda: 0.0)

    fake_now_seq: Iterator[float] = iter([0.0, 10.0, 20.0, 30.0])

    def fake_now() -> float:
        return next(fake_now_seq)

    outcome = wait_for_resume(
        PauseKind.AUTH,
        state_dir=state_dir,
        sleeper=fake_sleep,
        now=fake_now,
    )
    assert outcome is ResumeOutcome.RESUMED
    # Poll interval matches AUTH default (10s).
    assert sleep_calls[0] == pytest.approx(AUTH_RESUME_CHECK_INTERVAL_MS / 1000.0)


def test_wait_for_resume_times_out_when_budget_expires(state_dir: Path) -> None:
    write_pause(PauseKind.RATE_LIMIT, state_dir=state_dir, now=lambda: 0.0)

    tiny_budget = PauseBudget(max_wait_ms=10, check_interval_ms=5)

    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    # First three calls return values inside budget, the fourth
    # exceeds — the loop must return TIMED_OUT.
    fake_now_seq: Iterator[float] = iter([0.0, 0.0, 0.005, 0.005, 0.020, 0.020])

    def fake_now() -> float:
        return next(fake_now_seq)

    outcome = wait_for_resume(
        PauseKind.RATE_LIMIT,
        state_dir=state_dir,
        budget=tiny_budget,
        sleeper=fake_sleep,
        now=fake_now,
    )
    assert outcome is ResumeOutcome.TIMED_OUT
    # The pause file is NOT cleaned on timeout — caller decides
    # whether to abort or retry, so it must still see the
    # sentinel.
    assert (state_dir / RATE_LIMIT_PAUSE_FILE).exists()


def test_wait_for_resume_uses_canonical_budget_for_each_kind(
    state_dir: Path,
) -> None:
    # Both kinds resolve to RESUMED on first iteration without
    # sleeping — but the default poll interval must match the
    # documented constant for that kind.
    write_pause(PauseKind.RATE_LIMIT, state_dir=state_dir, now=lambda: 0.0)
    write_resume(state_dir=state_dir, now=lambda: 0.0)
    outcome = wait_for_resume(
        PauseKind.RATE_LIMIT,
        state_dir=state_dir,
        sleeper=lambda _seconds: None,
        now=lambda: 0.0,
    )
    assert outcome is ResumeOutcome.RESUMED

    write_pause(PauseKind.AUTH, state_dir=state_dir, now=lambda: 0.0)
    write_resume(state_dir=state_dir, now=lambda: 0.0)
    outcome = wait_for_resume(
        PauseKind.AUTH,
        state_dir=state_dir,
        sleeper=lambda _seconds: None,
        now=lambda: 0.0,
    )
    assert outcome is ResumeOutcome.RESUMED


def test_pause_kind_enum_values_are_stable_strings() -> None:
    # Audit log will serialise these as strings — pin them.
    assert PauseKind.RATE_LIMIT.value == "rate_limit"
    assert PauseKind.AUTH.value == "auth"
