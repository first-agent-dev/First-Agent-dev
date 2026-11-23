"""Legacy workspace-local seal storage; not authority-private custody.

Records are content-addressed and a pointer names the seal in force. Reads are
bounded and reject linked or non-regular final files, but workspace ancestors are
not an authority boundary. PLAN-V2 coder dispatch remains blocked until storage
and read-only projections are managed by WorkspaceAuthority.
"""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .acceptance_bundle import (
    MAX_SEAL_BYTES,
    AcceptanceBundle,
    AcceptanceBundleError,
    load_seal,
    seal_bytes,
    write_seal,
)

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
_DIGEST = re.compile(r"\A[0-9a-f]{64}\Z")
_MAX_POINTER_BYTES = 4096


def _read_bounded_file(path: Path, limit: int) -> bytes:
    """Read at most limit + 1 bytes from a non-linked regular file, never a FIFO."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise OSError("invalid file")
        chunks: list[bytes] = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate pointer field")
        result[key] = value
    return result


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
        # seal_bytes derives a digest from fields; an in-memory object may still
        # carry a stale digest. Refuse before making a record or swinging a pointer.
        if load_seal(raw) != bundle:
            raise AcceptanceBundleError("seal-record-mismatch")
        record = self._record_path(bundle.seal_sha256)
        # Validate the pointer move *before* writing the record: a refused supersede that had
        # already appended a record would leave an orphan seal nobody's pointer names, and the
        # audit chain would show a rung that was never in force.
        previous = self._pointer()
        if previous == bundle.seal_sha256:
            self.current()  # Do not reconstruct a missing or torn pointed record.
            self._write_once(record, raw, bundle)
            return bundle
        if previous is not None:
            self.current()  # A corrupt predecessor cannot authorize a pointer move.
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
            raw = _read_bounded_file(path, MAX_SEAL_BYTES)
        except OSError:
            # A pointer naming a record that is not there is corruption, not absence: the
            # alternative -- treating it as "no seal yet" -- would let a lost record read as
            # a workspace that was never sealed (D-V2-5 §4).
            raise AcceptanceBundleError("seal-record-missing") from None
        try:
            bundle = load_seal(raw)
        except AcceptanceBundleError as error:
            raise AcceptanceBundleError(error.rule) from None
        if bundle.seal_sha256 != digest:
            raise AcceptanceBundleError("seal-record-mismatch")
        return bundle

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
        if not isinstance(seal_sha256, str) or _DIGEST.fullmatch(seal_sha256) is None:
            raise AcceptanceBundleError("seal-invalid")
        return self.directory / f"{seal_sha256}.json"

    def _write_once(self, path: Path, raw: bytes, bundle: AcceptanceBundle, *, retries: int = 1) -> None:
        """Write one immutable record, or prove the existing bytes are the same ones."""
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            raise AcceptanceBundleError("seal-store-unwritable") from None
        try:
            existing = _read_bounded_file(path, MAX_SEAL_BYTES)
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
            raw = _read_bounded_file(self.pointer_path, _MAX_POINTER_BYTES)
        except FileNotFoundError:
            return None
        except OSError:
            raise AcceptanceBundleError("seal-pointer-unreadable") from None
        if len(raw) > _MAX_POINTER_BYTES:
            raise AcceptanceBundleError("seal-pointer-invalid")
        try:
            payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
        except (UnicodeError, ValueError):
            raise AcceptanceBundleError("seal-pointer-invalid") from None
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "seal_sha256"}:
            raise AcceptanceBundleError("seal-pointer-invalid")
        digest = payload["seal_sha256"]
        version = payload["schema_version"]
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            raise AcceptanceBundleError("seal-pointer-invalid")
        if type(version) is not int or version != _POINTER_SCHEMA:
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
