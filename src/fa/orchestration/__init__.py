"""Orchestration primitives for First-Agent.

Wave-1 R-25 (borrow-roadmap-2026-05.md §R-25): the pause-file
sentinel pattern. Future Phase-M scope: outer-loop scheduler,
sub-agent dispatcher, retry budget enforcement.
"""

from fa.orchestration.pause import (
    AUTH_PAUSE_FILE,
    AUTH_RESUME_CHECK_INTERVAL_MS,
    AUTH_RESUME_MAX_WAIT_MS,
    DEFAULT_STATE_DIR,
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
