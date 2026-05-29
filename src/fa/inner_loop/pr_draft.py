"""Per-session PR-draft store shared by ``pr.prepare`` and ``IntentGuard``.

The initial M-7 implementation treated ``~/.fa/state/runs/<run_id>/pr_draft.md``
as the entire trust boundary: if the file existed, :class:`IntentGuard`
trusted it. That left three gaps:

1. the first mutating tool call still passed when no draft had been
   prepared yet (``allow-on-no-draft``);
2. ``fs.run_bash`` could fabricate the file directly, bypassing the
   ``pr.prepare`` tool's schema + renderer validation; and
3. a stale file from a previous session using the same ``run_id`` could
   poison a later run.

This store closes those gaps by tracking *current-session provenance* in
memory while still persisting the human-readable draft on disk:

- :meth:`write_text` performs an atomic write and records the digest of
  the exact bytes that ``pr.prepare`` produced in this process;
- :meth:`read_current_text` returns text only when the on-disk file both
  exists and still matches the current-session digest; and
- :meth:`clear` resets the in-memory trust marker and optionally removes
  any stale on-disk draft before a new session starts.

Result: the draft remains inspectable at the stable path, but only
``pr.prepare`` writes from *this* session are trusted by the guard.
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
    """Current-session trust wrapper around ``pr_draft.md``.

    ``path`` is the stable filesystem location used for human inspection.
    ``_current_digest`` is the in-memory proof that the current process
    wrote the draft via ``pr.prepare`` and that the file has not been
    modified since.
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
        """Atomically persist ``text`` and trust it for this session."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_text_atomic(text)
        self._current_digest = _digest_text(text)

    def read_current_text(self) -> str | None:
        """Return the trusted current-session draft, else ``None``.

        ``None`` covers all untrusted states: never prepared in this
        session, stale file from a previous run, external tampering after
        ``pr.prepare``, or an unreadable/missing file.
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
        except Exception:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
            raise
