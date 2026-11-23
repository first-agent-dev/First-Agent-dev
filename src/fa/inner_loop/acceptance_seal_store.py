"""Where a minted acceptance seal lives, and the rules that keep custody honest (D-V2-5).

The seal is the artifact that says which bytes the oracle is. Three properties make the
storage as load-bearing as the mint:

* **Revisions never walk it.** D-V2-5's C1 is not tidiness: a seal written as a plain file in
  the tracked tree makes "the project at revision R" and "the bytes on disk" stop meaning the
  same thing at exactly the artifact that is supposed to prove custody. The store therefore
  lives under ``.fa/``, which every canonical walk excludes at any depth
  (``workspace.py:_PROTECTED_COMPONENTS``) and which no file tool may address
  (``view_io.py:_BLOCKED_COMPONENTS``).
* **Every seal ever minted stays readable.** Option A-1 appends an immutable per-seal file named by
  the digest it carries and swings one pointer, so ``supersedes_sha256`` stays a walkable
  chain instead of an overwritten claim.
* **A torn or missing record is a hard error, never a re-mint.** Re-minting over a corrupt
  record would launder the corruption into evidence; the rules below refuse instead.

The store is deliberately a plain filesystem object: the run already holds the workspace's
single writer grant, which is the lock D-V2-5 §2 asks for, so no second locking scheme is
introduced for two small writes.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .acceptance_bundle import AcceptanceBundle, AcceptanceBundleError, load_seal, seal_bytes, write_seal

__all__ = [
    "SEAL_POINTER",
    "SEAL_STORE_ROOT",
    "SealStore",
]

#: Immutable per-seal records, named by the digest each record carries.
SEAL_STORE_ROOT: Final = ".fa/seals"

#: The one authority over "which seal is in force".
SEAL_POINTER: Final = ".fa/seal-current.json"

_POINTER_SCHEMA: Final = 1


@dataclass(frozen=True, slots=True)
class SealStore:
    """The seal custody for one workspace root."""

    root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise AcceptanceBundleError("seal-path-invalid")

    @property
    def directory(self) -> Path:
        return self.root / SEAL_STORE_ROOT

    @property
    def pointer_path(self) -> Path:
        return self.root / SEAL_POINTER

    def store(self, bundle: AcceptanceBundle) -> AcceptanceBundle:
        """Persist ``bundle`` as the seal in force, or prove it already is.

        Idempotent on purpose (E3/E9): a run that restarts after the seal was written mints
        the same bytes from the same inputs, and storing them again must succeed rather than
        fail on ``O_EXCL``. Supersession is the *only* way the pointer moves, and it has to be
        declared by the caller's ``supersedes_sha256`` -- otherwise a second mint silently
        replaces the record a reviewer is reading.
        """
        if not isinstance(bundle, AcceptanceBundle):
            raise AcceptanceBundleError("seal-invalid")
        raw = seal_bytes(bundle)
        record = self._record_path(bundle.seal_sha256)
        # Validate the pointer move *before* writing the record: a refused supersede that had
        # already appended a record would leave an orphan seal nobody's pointer names, and the
        # audit chain would show a rung that was never in force.
        previous = self._pointer()
        if previous == bundle.seal_sha256:
            self._write_once(record, raw, bundle)
            return bundle
        if previous is not None and bundle.supersedes_sha256 != previous:
            raise AcceptanceBundleError("seal-supersede-required")
        self._write_once(record, raw, bundle)
        self._swing(bundle.seal_sha256)
        return bundle

    def current(self) -> AcceptanceBundle:
        """The seal in force, or the closed rule that says why there is none."""
        digest = self._pointer()
        if digest is None:
            raise AcceptanceBundleError("seal-pointer-missing")
        path = self._record_path(digest)
        try:
            raw = path.read_bytes()
        except OSError:
            # A pointer naming a record that is not there is corruption, not absence: the
            # alternative -- treating it as "no seal yet" -- would let a lost record read as
            # a workspace that was never sealed (D-V2-5 §4).
            raise AcceptanceBundleError("seal-record-missing") from None
        try:
            return load_seal(raw)
        except AcceptanceBundleError as error:
            raise AcceptanceBundleError(error.rule) from None

    def supersede(self, bundle: AcceptanceBundle, *, supersedes_sha256: str) -> AcceptanceBundle:
        """Store a replacement whose chain names its predecessor.

        Separate from :meth:`store` so the *intent* is declared rather than inferred: the
        defect route supersedes a reported seal, and the create route never does (D-V2-9).
        """
        if bundle.supersedes_sha256 != supersedes_sha256:
            raise AcceptanceBundleError("seal-supersede-invalid")
        if self._pointer() != supersedes_sha256:
            raise AcceptanceBundleError("seal-supersede-stale")
        return self.store(bundle)

    def _record_path(self, seal_sha256: str) -> Path:
        if not isinstance(seal_sha256, str) or len(seal_sha256) != 64:
            raise AcceptanceBundleError("seal-invalid")
        return self.directory / f"{seal_sha256}.json"

    def _write_once(self, path: Path, raw: bytes, bundle: AcceptanceBundle, *, retries: int = 1) -> None:
        """Write one immutable record, or prove the existing bytes are the same ones."""
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise AcceptanceBundleError("seal-store-unwritable") from None
        try:
            existing = path.read_bytes()
        except FileNotFoundError:
            existing = None
        except OSError:
            raise AcceptanceBundleError("seal-store-unreadable") from None
        if existing is not None:
            if existing != raw:
                # Same digest, different bytes: the record is not the seal it claims to be.
                raise AcceptanceBundleError("seal-record-mismatch")
            return
        try:
            write_seal(bundle, path)
        except AcceptanceBundleError as error:
            if error.rule != "seal-exists":
                raise
            # Lost the race with a concurrent writer of the *same* record: the winner's bytes
            # must be ours, or the digest was reused for two different seals. One more pass is
            # enough -- the winner has already written, so the read below either matches or
            # proves a mismatch. A bounded retry keeps a pathological racer a refusal, not a loop.
            if retries == 0:
                raise AcceptanceBundleError("seal-store-unwritable") from None
            self._write_once(path, raw, bundle, retries=retries - 1)

    def _pointer(self) -> str | None:
        try:
            raw = self.pointer_path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError:
            raise AcceptanceBundleError("seal-pointer-unreadable") from None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise AcceptanceBundleError("seal-pointer-invalid") from None
        digest = payload.get("seal_sha256") if isinstance(payload, dict) else None
        if not isinstance(digest, str) or len(digest) != 64:
            raise AcceptanceBundleError("seal-pointer-invalid")
        if payload.get("schema_version") != _POINTER_SCHEMA:
            raise AcceptanceBundleError("seal-pointer-invalid")
        return digest

    def _swing(self, seal_sha256: str) -> None:
        """Replace the pointer atomically: one rename, never a partial file."""
        payload = json.dumps({"schema_version": _POINTER_SCHEMA, "seal_sha256": seal_sha256}, sort_keys=True)
        try:
            self.pointer_path.parent.mkdir(parents=True, exist_ok=True)
            handle = tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.pointer_path.parent, prefix=".seal-current-", delete=False
            )
            try:
                with handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(handle.name, self.pointer_path)
            finally:
                if os.path.exists(handle.name):  # pragma: no cover - only on a failed replace
                    os.unlink(handle.name)
            descriptor = os.open(self.pointer_path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        except OSError:
            raise AcceptanceBundleError("seal-store-unwritable") from None
