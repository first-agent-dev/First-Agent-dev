"""Filesystem-canon learning loop primitives (R-8).

Wave-0 implementation per
[`research/borrow-roadmap-2026-05.md` §R-8](../../../knowledge/research/borrow-roadmap-2026-05.md).
Ported from Aperant
``apps/desktop/src/main/ai/tools/auto-claude/record-gotcha.ts`` (78
LOC) + ``record-discovery.ts`` (90 LOC).

The atomic-rename idiom (``.tmp`` + ``os.replace``) used internally
protects each individual call against torn writes (the target file
never contains a half-written body — either the old content or the
fully-written new content is visible). It does **not** make the
functions safe to call concurrently from multiple processes: both
:func:`record_discovery` and :func:`record_gotcha` do a
read-modify-write cycle without locking, so two parallel callers
will race and the later writer overwrites the earlier writer's
update.

This is acceptable for First-Agent's UC1+UC3 single-user CLI scope
([`knowledge/project-overview.md` §1.1](../../../knowledge/project-overview.md)).
Callers MUST serialise access externally (a single inner-loop
HookRegistry post-tool middleware is the planned consumer). File-
locking (``fcntl.flock`` on POSIX / lockfile shim on Windows) is
deferred to BACKLOG M-1 when the HookRegistry runtime lands and
multi-process FA invocation becomes a possibility worth proving.

(Agent Review finding 2026-05-20 on PR #18 — original docstring
claimed parallel-process safety; corrected here.)

Public surface (stable for Wave 0; `LearningObserver` wires these
writers into the inner-loop `AFTER_TOOL_EXEC` hook):

- :func:`record_gotcha` — append a timestamped section to
  ``knowledge/trace/gotchas.md``.
- :func:`record_discovery` — atomic upsert one key in
  ``knowledge/trace/codebase_map.json``.
"""

from __future__ import annotations

from fa.tools.record_discovery import (
    DEFAULT_CODEBASE_MAP_PATH,
    DiscoveryEntry,
    record_discovery,
)
from fa.tools.record_gotcha import (
    DEFAULT_GOTCHAS_PATH,
    record_gotcha,
)

__all__ = [
    "DEFAULT_CODEBASE_MAP_PATH",
    "DEFAULT_GOTCHAS_PATH",
    "DiscoveryEntry",
    "record_discovery",
    "record_gotcha",
]
