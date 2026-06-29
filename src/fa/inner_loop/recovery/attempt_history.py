"""Per-run ``attempt_history.json`` writer + reader (Wave-2 R-6).

Aperant ``recovery-manager.ts`` keeps a per-subtask retry history under
``<specDir>/memory/attempt_history.json``. We port the writer side to
``~/.fa/session-log/<run_id>/attempt_history.json`` so the per-session anchor
matches the events.jsonl pattern in ADR-7 §7. Cross-session aggregation
(the «commit `knowledge/trace/attempt_history.json` into the repo» path
in the source spec) is intentionally deferred: it adds PR-noise and the
single-session reader prompt does not need it yet.

The writer is **append-only** + bounded:

- sliding window ``max_age_seconds`` (default 7200 = 2h, Aperant
  anchor) — older entries are dropped on next append.
- hard cap ``max_entries`` (default 50, Aperant anchor) — when the
  cap is hit, the oldest entry is dropped before the new one lands.

Both knobs are loaded from :class:`fa.inner_loop.runtime_limits.RuntimeLimits`
so they obey ADR-7 §Amendment 2026-05-20 rule 1 («caps live in
``~/.fa/config.yaml``, never as constants in hook code»).

The file is a JSON document (NOT JSONL) because the reader prompt
loads the entire history in one read; that is a simpler integration
than JSONL streaming, at the cost of a single full rewrite per append.
50 entries x ~200 bytes ~= 10 KB max, so the rewrite cost is bounded.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Aperant ``recovery-manager.ts`` constants — documented anchors that
# end up here because they double as the documented YAML defaults
# loaded by :class:`fa.inner_loop.runtime_limits.RuntimeLimits`. The
# anchors live in one place so the YAML loader and the writer both
# import from the same source of truth.
DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES = 50
DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS = 7200


@dataclass(frozen=True)
class AttemptHistoryEntry:
    """One row in ``attempt_history.json``.

    Field shapes match the coder-recovery prompt reader so the prompt
    can render the table without a transformation layer in Python.
    """

    ts: float
    tool_name: str
    params_hash: str
    error_code: str
    error_message: str
    recovery_action: str
    recovery_category: str

    def to_json(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "tool_name": self.tool_name,
            "params_hash": self.params_hash,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "recovery_action": self.recovery_action,
            "recovery_category": self.recovery_category,
        }

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> AttemptHistoryEntry:
        return cls(
            ts=float(raw["ts"]),
            tool_name=str(raw["tool_name"]),
            params_hash=str(raw["params_hash"]),
            error_code=str(raw["error_code"]),
            error_message=str(raw["error_message"]),
            recovery_action=str(raw["recovery_action"]),
            recovery_category=str(raw["recovery_category"]),
        )


def canonical_params_hash(tool_name: str, params: Mapping[str, object]) -> str:
    """Deterministic per-attempt signature.

    Aperant uses a JS ``simpleHash`` over the stringified call; we use
    a SHA-1 of ``{tool_name}|{canonical-json-params}`` truncated to 12
    hex chars. That is enough entropy to distinguish attempts within a
    50-entry window and short enough to print in the prompt without
    line-wrap.
    """

    canonical = json.dumps(dict(params), sort_keys=True, ensure_ascii=False)
    blob = f"{tool_name}|{canonical}".encode()
    return hashlib.sha1(blob, usedforsecurity=False).hexdigest()[:12]


@dataclass
class AttemptHistory:
    """JSON-backed sliding window of failed-attempt entries.

    Construct with :meth:`open` to load existing entries from disk;
    construct directly for an in-memory instance (tests). All mutations
    write to disk immediately so a crash mid-session preserves the
    history up to the last successful ``append``.
    """

    path: Path
    max_entries: int = DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES
    max_age_seconds: int = DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS
    entries: list[AttemptHistoryEntry] = field(default_factory=list)

    @classmethod
    def open(
        cls,
        path: Path,
        *,
        max_entries: int = DEFAULT_ATTEMPT_HISTORY_MAX_ENTRIES,
        max_age_seconds: int = DEFAULT_ATTEMPT_HISTORY_MAX_AGE_SECONDS,
    ) -> AttemptHistory:
        """Load entries from ``path`` if it exists; else return empty."""

        history = cls(
            path=path,
            max_entries=max_entries,
            max_age_seconds=max_age_seconds,
        )
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                # Corrupt history file — start fresh rather than crash
                # the loop. The next append rewrites the file cleanly.
                return history
            if isinstance(raw, list):
                for row in raw:
                    if not isinstance(row, dict):
                        continue
                    try:
                        history.entries.append(AttemptHistoryEntry.from_json(row))
                    except (KeyError, ValueError, TypeError):
                        continue
        return history

    def _prune(self, now: float) -> None:
        """Drop entries older than ``max_age_seconds`` and enforce cap."""

        cutoff = now - self.max_age_seconds
        self.entries = [entry for entry in self.entries if entry.ts >= cutoff]
        if len(self.entries) > self.max_entries:
            # Keep the most recent ``max_entries`` rows.
            self.entries = self.entries[-self.max_entries :]

    def _flush(self) -> None:
        """Atomic write: rendered JSON → temp file → rename."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            [entry.to_json() for entry in self.entries],
            indent=2,
            ensure_ascii=False,
        )
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(self.path)

    def append(
        self,
        *,
        tool_name: str,
        params_hash: str,
        error_code: str,
        error_message: str,
        recovery_action: str,
        recovery_category: str,
        ts: float | None = None,
    ) -> AttemptHistoryEntry:
        """Append one entry, prune the window, and rewrite the file."""

        now = time.time() if ts is None else ts
        # Cap entries against the configured limit minus one to leave
        # room for the new row, then run the time-based prune on the
        # combined list. This ordering keeps the «most recent
        # ``max_entries`` rows» invariant after every append.
        if len(self.entries) >= self.max_entries:
            self.entries = self.entries[-(self.max_entries - 1) :]
        entry = AttemptHistoryEntry(
            ts=now,
            tool_name=tool_name,
            params_hash=params_hash,
            error_code=error_code,
            error_message=error_message,
            recovery_action=recovery_action,
            recovery_category=recovery_category,
        )
        self.entries.append(entry)
        self._prune(now)
        self._flush()
        return entry

    def attempt_count(self, *, tool_name: str, params_hash: str) -> int:
        """Number of rows matching this exact ``(tool, params_hash)``.

        The coder-recovery prompt uses this directly: ``>= 1`` triggers
        the WARN banner, ``>= 2`` triggers HIGH RISK + «pick a different
        library / approach».
        """

        return sum(
            1
            for entry in self.entries
            if entry.tool_name == tool_name and entry.params_hash == params_hash
        )
