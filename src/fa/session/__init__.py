"""Persistent session lifecycle and run identity boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fa.session.manager import RunContext, SessionContext, SessionManager, SessionManagerError

__all__ = ["RunContext", "SessionContext", "SessionManager", "SessionManagerError"]


def __getattr__(name: str) -> object:
    if name in __all__:
        from fa.session import manager

        return getattr(manager, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
