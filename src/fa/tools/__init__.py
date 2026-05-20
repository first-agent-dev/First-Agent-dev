"""Filesystem-canon learning loop primitives (R-8).

Wave-0 implementation per
[`research/borrow-roadmap-2026-05.md` §R-8](../../../knowledge/research/borrow-roadmap-2026-05.md).
Ported from Aperant
``apps/desktop/src/main/ai/tools/auto-claude/record-gotcha.ts`` (78
LOC) + ``record-discovery.ts`` (90 LOC). The atomic-rename idiom
(``.tmp`` + ``os.replace``) is preserved because both tools are
expected to be called from multiple processes in parallel — the
TS originals used the same pattern.

Public surface (stable for Wave 0; HookRegistry integration in R-1
adds the `post_tool` adapter that calls these tools):

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
