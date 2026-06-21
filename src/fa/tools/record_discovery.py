"""``record_discovery`` — per-key upsert into the codebase map.

Stores in ``knowledge/trace/codebase_map.json`` a flat
``{key: DiscoveryEntry}`` dictionary. Each call updates exactly
one key; writes are atomic per call via ``.tmp`` + ``os.replace``
(mirrors Aperant TS ``record-discovery.ts`` idiom) so the target
file never contains a partially-written JSON object.

The per-call atomic-rename does NOT protect the read-modify-write
cycle (load existing map → add one key → dump full map) from
concurrent invocation — two parallel callers can each read the
same initial state and the later writer's ``os.replace`` overwrites
the earlier key. See :mod:`fa.tools` package docstring for the
single-writer contract and BACKLOG M-1 deferral.

The map is intentionally JSON (not Markdown) because it is meant
to be programmatically loaded by future routing layers — see
[`research/borrow-roadmap-2026-05.md` §R-8](../../../knowledge/research/borrow-roadmap-2026-05.md)
"codebase_map.json = pointer index «do not re-read src/fa/chunker/»".
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_CODEBASE_MAP_PATH = Path("knowledge/trace/codebase_map.json")

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.\-/]+$")


@dataclass(frozen=True)
class DiscoveryEntry:
    """One entry in the codebase map.

    - ``summary`` — one-line description of what was discovered.
    - ``pointers`` — file paths / URLs / identifiers a future
      session can use to re-locate the discovery without
      re-deriving it. Order preserved.
    - ``recorded_at`` — ISO-8601 UTC timestamp set by
      :func:`record_discovery` when the entry was last written.
      Existing value preserved across reads.
    """

    summary: str
    pointers: tuple[str, ...] = ()
    recorded_at: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


def _now_iso_z() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_existing(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(
            f"codebase map at {path} is not a JSON object (top-level {type(parsed).__name__})"
        )
    cleaned: dict[str, dict[str, object]] = {}
    for key, value in parsed.items():
        if not isinstance(value, dict):
            raise ValueError(f"codebase map entry for {key!r} is not an object")
        cleaned[key] = value
    return cleaned


def record_discovery(
    key: str,
    entry: DiscoveryEntry,
    *,
    path: Path = DEFAULT_CODEBASE_MAP_PATH,
    now: str | None = None,
) -> Path:
    """Upsert one ``key`` → ``entry`` into the map at ``path``.

    ``key`` MUST match ``[A-Za-z0-9_./-]+`` — a constraint
    intentionally narrower than JSON object keys so that future
    tooling can parse ``key`` as either a slug or a relative
    path without an escaping layer.

    The function:

    1. Reads the existing map (empty dict if file does not exist).
    2. Stamps ``recorded_at`` on the new entry (overriding the
       passed-in value with ``now`` or "now in UTC" — entries
       carry the time they were *written*, not constructed).
    3. Replaces the existing value for ``key`` (no merge — pure
       upsert).
    4. Writes the JSON to a ``.tmp`` sibling and ``os.replace``s
       it over ``path``.
    """

    if not _KEY_PATTERN.fullmatch(key):
        raise ValueError(f"discovery key must match [A-Za-z0-9_./-]+ (got {key!r})")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    timestamp = now if now is not None else _now_iso_z()
    stamped_entry = DiscoveryEntry(
        summary=entry.summary,
        pointers=tuple(entry.pointers),
        recorded_at=timestamp,
        tags=tuple(entry.tags),
    )

    existing = _load_existing(target)
    existing[key] = asdict(stamped_entry)  # pyrefly: ignore[unsupported-operation]

    serialised = json.dumps(
        existing,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(serialised + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return target


__all__ = ["DEFAULT_CODEBASE_MAP_PATH", "DiscoveryEntry", "record_discovery"]
