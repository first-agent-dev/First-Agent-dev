"""ContextVar for current SessionState — tool handlers DI via contextvar.

Phase 0.5 integration: fs_write_file handler can declare read_set/write_set
and call detect_conflict() without changing ToolSpec signature.
Uses Python contextvars so thread-safe and works with ThreadPool in Phase 2.
"""

from __future__ import annotations

import contextvars
import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from fa.inner_loop.state import SessionState

_current_session: contextvars.ContextVar[SessionState | None] = contextvars.ContextVar(
    "fa_current_session", default=None
)


def set_current_session(
    state: SessionState | None,
) -> contextvars.Token[SessionState | None]:
    return _current_session.set(state)


def get_current_session() -> SessionState | None:
    try:
        return _current_session.get()
    except LookupError:
        return None


def reset_current_session(token: contextvars.Token[SessionState | None]) -> None:
    try:
        _current_session.reset(token)
    except Exception as exc:  # noqa: BLE001 - reset best-effort, log warning
        logger.warning(f"reset_current_session failed: {exc}")


__all__ = ["get_current_session", "reset_current_session", "set_current_session"]
