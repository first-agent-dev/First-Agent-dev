# pylint: disable=duplicate-code  # Atomic-write cleanup mirrors workflow_artifacts intentionally.
"""Per-session optional PR/work-note store for ``pr_prepare``.

The stable ``~/.fa/session-log/<run_id>/pr_draft.md`` artifact remains
inspectable and resumable. Atomic replacement plus an in-memory digest detect
accidental changes to bytes written by the current process; this provenance is
artifact-integrity metadata only, never mutation authorization. Production
``fa run`` paths do not register IntentGuard, and no caller may treat this
store's presence or digest as a write permit.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["PrDraftStore"]


def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class PrDraftStore:
    """Optional note store with a current-process artifact-integrity digest.

    ``path`` is the stable filesystem location used for human inspection.
    ``_current_digest`` detects whether bytes still match the current process'
    last write; it is not a write authorization signal.
    """

    path: Path
    _current_digest: str | None = field(default=None, init=False, repr=False)

    def clear(self, *, remove_file: bool = False) -> None:
        """Reset current-session trust and optionally delete the on-disk draft."""

        self._current_digest = None
        if not remove_file:
            return
        try:
            self.path.unlink()
        except FileNotFoundError:
            return

    def write_text(self, text: str) -> None:
        """Atomically persist ``text`` and remember its digest for integrity checks."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(text)
        self._current_digest = _digest_text(text)

    def read_current_text(self) -> str | None:
        """Return note text if it still matches this process' last write.

        ``None`` covers never-written, stale, modified, unreadable, or missing
        note states. It conveys artifact integrity only, never permission to
        perform a workspace mutation.
        """

        if self._current_digest is None:
            return None
        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, PermissionError):
            return None
        if _digest_text(text) != self._current_digest:
            return None
        return text

    def has_current_text(self) -> bool:
        return self.read_current_text() is not None

    def _write_text_atomic(self, text: str) -> None:
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
                temp_path = Path(handle.name)
            os.replace(temp_path, self.path)
        except Exception:  # graceful degradation per Phase 0.5, failure-observable WARNING
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            raise
