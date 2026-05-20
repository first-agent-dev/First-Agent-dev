"""Pause-file sentinel pattern for First-Agent orchestration.

Wave-1 R-25 (borrow-roadmap-2026-05.md §R-25). Filesystem-based
pause / resume primitive — the orchestrator writes a sentinel
file when it must stop (rate-limit hit, auth failure), the
human-in-the-loop (or a frontend, or a re-auth script) writes a
``RESUME`` sentinel to clear the pause, and the orchestrator
polls the directory at a fixed interval until either the resume
arrives or a hard timeout fires.

The shape is filesystem- and process-agnostic on purpose: it
survives orchestrator restarts (sentinel state lives in the
file system, not in process memory) and works across machines
that share a state directory (NFS-style mounts, future UC5
sub-agent surfaces).

Two pause kinds:

- ``RATE_LIMIT_PAUSE`` — provider returned 429 / 503; resume
  when a human (or a clock-based agent) clears the file.
  Default budget: 2 hours total wait, 30-second poll.
- ``AUTH_PAUSE``       — provider returned 401 / token-expired;
  resume after the human re-runs the auth flow and the
  daemon-side post-login hook clears the file. Default
  budget: 24 hours total wait, 10-second poll.

Constants match Kronos's pause defaults verbatim. The two
budgets are intentionally asymmetric: rate-limit waits are
short and expensive to keep polling; auth waits are long
(human has to context-switch, re-MFA, and come back) and
cheap to keep polling.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

DEFAULT_STATE_DIR: Path = Path.home() / ".fa" / "state" / "pause"

RATE_LIMIT_PAUSE_FILE: str = "RATE_LIMIT_PAUSE"
AUTH_PAUSE_FILE: str = "AUTH_PAUSE"
RESUME_FILE: str = "RESUME"

# Kronos defaults, milliseconds.
MAX_RATE_LIMIT_WAIT_MS: int = 7_200_000  # 2 hours
RATE_LIMIT_CHECK_INTERVAL_MS: int = 30_000  # 30 seconds
AUTH_RESUME_MAX_WAIT_MS: int = 86_400_000  # 24 hours
AUTH_RESUME_CHECK_INTERVAL_MS: int = 10_000  # 10 seconds


class PauseKind(StrEnum):
    """The two pause flavours."""

    RATE_LIMIT = "rate_limit"
    AUTH = "auth"


class ResumeOutcome(StrEnum):
    """Result of waiting for a resume signal."""

    RESUMED = "resumed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class PauseBudget:
    """Polling budget for a pause kind.

    Both fields are millisecond integers for parity with the
    constants above and with Kronos's source. Convert to
    seconds at the polling site.
    """

    max_wait_ms: int
    check_interval_ms: int


_BUDGETS: dict[PauseKind, PauseBudget] = {
    PauseKind.RATE_LIMIT: PauseBudget(
        max_wait_ms=MAX_RATE_LIMIT_WAIT_MS,
        check_interval_ms=RATE_LIMIT_CHECK_INTERVAL_MS,
    ),
    PauseKind.AUTH: PauseBudget(
        max_wait_ms=AUTH_RESUME_MAX_WAIT_MS,
        check_interval_ms=AUTH_RESUME_CHECK_INTERVAL_MS,
    ),
}

_PAUSE_FILENAMES: dict[PauseKind, str] = {
    PauseKind.RATE_LIMIT: RATE_LIMIT_PAUSE_FILE,
    PauseKind.AUTH: AUTH_PAUSE_FILE,
}


def _pause_path(kind: PauseKind, state_dir: Path) -> Path:
    return state_dir / _PAUSE_FILENAMES[kind]


def _resume_path(state_dir: Path) -> Path:
    return state_dir / RESUME_FILE


def write_pause(
    kind: PauseKind,
    *,
    reason: str = "",
    state_dir: Path = DEFAULT_STATE_DIR,
    now: Callable[[], float] = time.time,
) -> Path:
    """Write a pause sentinel for ``kind``.

    Creates ``state_dir`` if absent. The sentinel body is one
    line ``<unix-timestamp> <reason>``; the timestamp is so a
    later debugger can correlate the pause with provider logs,
    the reason is free-text (typically the provider error
    code). Returns the sentinel path.

    Implemented as atomic-rename (``.tmp`` + ``os.replace``) so
    a crash mid-write never leaves a half-written sentinel that
    the orchestrator might read as a malformed signal.
    """

    state_dir.mkdir(parents=True, exist_ok=True)
    target = _pause_path(kind, state_dir)
    tmp = target.with_suffix(target.suffix + ".tmp")
    body = f"{int(now())} {reason}\n"
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(target)
    return target


def write_resume(
    *,
    state_dir: Path = DEFAULT_STATE_DIR,
    now: Callable[[], float] = time.time,
) -> Path:
    """Write the ``RESUME`` sentinel.

    Called by the human-side resume path (frontend button,
    re-auth script's post-login hook, or manual ``touch`` from
    a shell). Resume clears *all* pause kinds — there is one
    ``RESUME`` file, not one per pause kind, because the
    operator who clears a rate-limit pause and an auth pause is
    the same human in the same session ~99% of the time.
    """

    state_dir.mkdir(parents=True, exist_ok=True)
    target = _resume_path(state_dir)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(f"{int(now())}\n", encoding="utf-8")
    tmp.replace(target)
    return target


def is_paused(
    kind: PauseKind,
    *,
    state_dir: Path = DEFAULT_STATE_DIR,
) -> bool:
    """Return ``True`` iff the pause sentinel for ``kind`` exists."""

    return _pause_path(kind, state_dir).exists()


def wait_for_resume(
    kind: PauseKind,
    *,
    state_dir: Path = DEFAULT_STATE_DIR,
    budget: PauseBudget | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.time,
) -> ResumeOutcome:
    """Block until ``RESUME`` is observed or the budget expires.

    Default ``budget`` is the canonical one for ``kind`` (see
    module-level constants). When the resume signal arrives,
    both the pause sentinel and the resume sentinel are
    deleted before return — the next pause cycle starts from a
    clean state dir.

    The ``sleeper`` and ``now`` callables are injected so tests
    can drive the loop without real time passing.
    """

    chosen_budget = budget or _BUDGETS[kind]

    start = now()
    deadline_s = start + chosen_budget.max_wait_ms / 1000.0
    interval_s = chosen_budget.check_interval_ms / 1000.0

    resume_path = _resume_path(state_dir)
    pause_path = _pause_path(kind, state_dir)

    while True:
        if resume_path.exists():
            # Clean both sentinels so the next cycle restarts
            # from an empty directory. Missing-OK on the pause
            # path — caller may have already removed it.
            resume_path.unlink(missing_ok=True)
            pause_path.unlink(missing_ok=True)
            return ResumeOutcome.RESUMED

        if now() >= deadline_s:
            return ResumeOutcome.TIMED_OUT

        sleeper(interval_s)


__all__ = [
    "AUTH_PAUSE_FILE",
    "AUTH_RESUME_CHECK_INTERVAL_MS",
    "AUTH_RESUME_MAX_WAIT_MS",
    "DEFAULT_STATE_DIR",
    "MAX_RATE_LIMIT_WAIT_MS",
    "RATE_LIMIT_CHECK_INTERVAL_MS",
    "RATE_LIMIT_PAUSE_FILE",
    "RESUME_FILE",
    "PauseBudget",
    "PauseKind",
    "ResumeOutcome",
    "is_paused",
    "wait_for_resume",
    "write_pause",
    "write_resume",
]
