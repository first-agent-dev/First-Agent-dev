"""Controller-minted acceptance seal (STEP9A / Q-V2-ACC-1 item 1).

The seal is the only thing that may say "these bytes, under this
configuration, are the oracle for this plan revision". It binds four
identities that a coder could otherwise move independently:

* the plan bytes the acceptance rows came from (``plan_sha256``);
* the immutable workspace revision the seal was minted against (``revision_id``);
* the complete acceptance closure — every sealed file, its digest, the
  aggregate closure digest and the sealed ``pytest.ini``;
* the ``TEST-ID`` -> selector -> resolved nodeid table, whose nodeids must
  live inside the sealed closure.

The record is canonical JSON. Its digest covers every field except itself, so
a tampered field is detectable without re-reading the tree, and the record is
written *outside* the acceptance tree so the tree stays exactly the closure
inventory (no self-referential manifest inside the sealed bytes).

Visibility mode A (coder may read the closure, never write it) is the only
implemented mode. Mode B (hidden test bodies) is not implemented: asking for it
fails closed here instead of silently behaving like A.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .acceptance_closure import (
    AcceptanceClosure,
    AcceptanceClosureError,
    ClosureFile,
    collect_acceptance_closure,
    read_closure_payload,
)
from .plan_v2 import Acceptance, PlanGraph, resolve_selectors

__all__ = [
    "MAX_SEAL_BYTES",
    "SCHEMA_VERSION",
    "SEAL_FILENAME",
    "VISIBILITY_MODES",
    "AcceptanceBundle",
    "AcceptanceBundleError",
    "PinnedIdentity",
    "SealedSelector",
    "load_seal",
    "mint_seal",
    "seal_bytes",
    "seal_payload",
    "verify_plan",
    "verify_revision",
    "verify_sealed_root",
    "write_seal",
]

#: The seal record schema the loader accepts. Unknown versions are refused.
SCHEMA_VERSION = 1
#: Seal file name; it sits beside ``acceptance/``, never inside it.
SEAL_FILENAME = "acceptance.seal.json"
#: Same read cap the authority already applies to its own bundle manifests.
MAX_SEAL_BYTES = 1024**2
#: One seal cannot describe more selectors than the closure can hold tests.
#: Implemented visibility modes; ``B`` is named only to refuse it explicitly.
VISIBILITY_MODES = frozenset({"A"})
_UNSUPPORTED_MODES = frozenset({"B"})

_REVISION_RE = re.compile(r"\Arev-[0-9a-f]{32}\Z")
_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_LABEL_RE = re.compile(r"\A[a-z][a-z0-9._-]{0,63}\Z")
_SEALED_ROOT_RE = re.compile(r"\Aworklogs/[a-z0-9][a-z0-9._-]*/acceptance\Z")

_MANIFEST_KIND = "ACCEPTANCE-BUNDLE"


class AcceptanceBundleError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid acceptance seal: {rule}")


@dataclass(frozen=True, slots=True)
class SealedSelector:
    """One ``TEST-ID`` bound to the exact nodeid collected from sealed bytes."""

    test_id: str
    ct_id: str
    selector: str
    nodeid: str


@dataclass(frozen=True, slots=True)
class PinnedIdentity:
    """A trusted image-side input recorded by identity (label + digest)."""

    name: str
    sha256: str


@dataclass(frozen=True, slots=True)
class AcceptanceBundle:
    """The seal: plan, revision, closure and nodeid table, digest-bound."""

    plan_sha256: str
    revision_id: str
    sealed_root: str
    closure: AcceptanceClosure
    selectors: tuple[SealedSelector, ...]
    mode: str
    identity: tuple[PinnedIdentity, ...]
    supersedes_sha256: str | None
    seal_sha256: str

    def nodeids(self) -> dict[str, str]:
        """``TEST-ID`` -> nodeid, the mapping the verifier executes against."""
        return {selector.test_id: selector.nodeid for selector in self.selectors}


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _require_sha256(value: object, rule: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        raise AcceptanceBundleError(rule)
    return value


def _require_text(value: object, rule: str, *, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value:
        raise AcceptanceBundleError(rule)
    return value


def _require_mode(mode: object) -> str:
    if not isinstance(mode, str) or not mode:
        raise AcceptanceBundleError("visibility-mode-invalid")
    if mode in _UNSUPPORTED_MODES:
        raise AcceptanceBundleError("visibility-mode-unsupported")
    if mode not in VISIBILITY_MODES:
        raise AcceptanceBundleError("visibility-mode-invalid")
    return mode


def _require_revision(revision_id: object) -> str:
    if not isinstance(revision_id, str) or not _REVISION_RE.match(revision_id):
        raise AcceptanceBundleError("revision-invalid")
    return revision_id


def _plan_digest(plan_bytes: object) -> str:
    if not isinstance(plan_bytes, bytes) or not plan_bytes:
        raise AcceptanceBundleError("plan-invalid")
    return _sha256(plan_bytes)


def _require_sealed_root(sealed_root: object) -> str:
    if not isinstance(sealed_root, str) or not _SEALED_ROOT_RE.match(sealed_root):
        raise AcceptanceBundleError("sealed-root-invalid")
    return sealed_root


def _closure_paths(closure: AcceptanceClosure) -> dict[str, str]:
    return {entry.path: entry.sha256 for entry in closure.files}


def _relative_to(path: str, sealed_root: str, rule: str) -> str:
    prefix = f"{sealed_root}/"
    if not path.startswith(prefix):
        raise AcceptanceBundleError(rule)
    return path[len(prefix) :]


def _sealed_selector(
    entry: Acceptance,
    nodeid: str,
    closure_paths: Mapping[str, str],
    sealed_root: str,
) -> SealedSelector:
    """Bind one acceptance row, refusing any selector outside the sealed bytes.

    Resolution itself is ``plan_v2.resolve_selectors``' job (one nodeid, no
    ambiguity); what the seal adds is that the resolved selector actually names
    a file inside this closure.
    """
    path = entry.selector.partition("::")[0]
    if _relative_to(path, sealed_root, "selector-outside-closure") not in closure_paths:
        raise AcceptanceBundleError("selector-outside-closure")
    return SealedSelector(test_id=entry.test_id, ct_id=entry.ct, selector=entry.selector, nodeid=nodeid)


def _bind_selectors(
    graph: PlanGraph,
    resolved: Mapping[str, str],
    closure_paths: Mapping[str, str],
    sealed_root: str,
) -> tuple[SealedSelector, ...]:
    # ``resolved`` comes from ``resolve_selectors`` over this very graph, so it
    # is complete and non-foreign by construction; re-checking would be dead.
    entries = graph.acceptance()
    if not entries:
        # A seal that selects nothing cannot be serialized (`load_seal` refuses an
        # empty table) and asserts nothing, so it is refused where it is minted.
        raise AcceptanceBundleError("no-sealed-selectors")
    return tuple(
        _sealed_selector(entry, resolved[entry.test_id], closure_paths, sealed_root)
        for entry in sorted(entries.values(), key=lambda item: item.test_id)
    )


def _bind_identity(identity: Iterable[PinnedIdentity]) -> tuple[PinnedIdentity, ...]:
    pinned = tuple(sorted(identity, key=lambda item: item.name))
    if not pinned:
        return ()
    for item in pinned:
        if not isinstance(item, PinnedIdentity) or not _LABEL_RE.match(item.name):
            raise AcceptanceBundleError("identity-label-invalid")
        _require_sha256(item.sha256, "identity-digest-invalid")
    if len({item.name for item in pinned}) != len(pinned):
        raise AcceptanceBundleError("identity-duplicate")
    return pinned


def _collect(root: Path) -> AcceptanceClosure:
    try:
        return collect_acceptance_closure(root)
    except AcceptanceClosureError as error:
        raise AcceptanceBundleError(f"closure-{error.rule}") from None


def _record(bundle: AcceptanceBundle) -> dict[str, Any]:
    """The canonical record: every field except the digest over the record."""
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": _MANIFEST_KIND,
        "plan_sha256": bundle.plan_sha256,
        "revision_id": bundle.revision_id,
        "sealed_root": bundle.sealed_root,
        "mode": bundle.mode,
        "closure_sha256": bundle.closure.digest,
        "files": [
            {"path": entry.path, "sha256": entry.sha256, "size": entry.size, "mode": entry.mode}
            for entry in sorted(bundle.closure.files, key=lambda item: item.path)
        ],
        "selectors": [
            {"test_id": item.test_id, "ct_id": item.ct_id, "selector": item.selector, "nodeid": item.nodeid}
            for item in sorted(bundle.selectors, key=lambda item: item.test_id)
        ],
        "identity": [{"name": item.name, "sha256": item.sha256} for item in bundle.identity],
        "supersedes_sha256": bundle.supersedes_sha256,
    }


def seal_bytes(bundle: AcceptanceBundle) -> bytes:
    """Serialize the seal; ``seal_sha256`` is derived, never transcribed."""
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceBundleError("seal-invalid")
    record = _record(bundle)
    record["seal_sha256"] = _sha256(_canonical(record))
    return _canonical(record)


def mint_seal(
    *,
    graph: PlanGraph,
    plan_bytes: bytes,
    revision_id: str,
    sealed_root: str,
    acceptance_root: Path,
    collected: Mapping[str, Iterable[str]],
    mode: str = "A",
    identity: Sequence[PinnedIdentity] = (),
    supersedes_sha256: str | None = None,
) -> AcceptanceBundle:
    """Mint the seal for one plan revision and one sealed acceptance tree.

    ``collected`` is the nodeid report of a collection run made *against the
    sealed bytes*; the plan's own acceptance rows decide which selectors must
    appear, so a missing or foreign resolution is refused rather than ignored.
    """
    if not isinstance(graph, PlanGraph):
        raise AcceptanceBundleError("plan-invalid")
    plan_sha256 = _plan_digest(plan_bytes)
    revision = _require_revision(revision_id)
    visibility = _require_mode(mode)
    root = _require_sealed_root(sealed_root)
    if not isinstance(acceptance_root, Path) or acceptance_root.name != "acceptance":
        raise AcceptanceBundleError("sealed-root-invalid")
    if supersedes_sha256 is not None:
        _require_sha256(supersedes_sha256, "supersedes-invalid")
    closure = _collect(acceptance_root)
    resolved = resolve_selectors(graph, collected)
    selectors = _bind_selectors(graph, resolved, _closure_paths(closure), root)
    bundle = AcceptanceBundle(
        plan_sha256=plan_sha256,
        revision_id=revision,
        sealed_root=root,
        closure=closure,
        selectors=selectors,
        mode=visibility,
        identity=_bind_identity(identity),
        supersedes_sha256=supersedes_sha256,
        seal_sha256="",
    )
    return AcceptanceBundle(
        plan_sha256=bundle.plan_sha256,
        revision_id=bundle.revision_id,
        sealed_root=bundle.sealed_root,
        closure=bundle.closure,
        selectors=bundle.selectors,
        mode=bundle.mode,
        identity=bundle.identity,
        supersedes_sha256=bundle.supersedes_sha256,
        seal_sha256=_sha256(_canonical(_record(bundle))),
    )


def _load_files(raw: object) -> tuple[ClosureFile, ...]:
    if not isinstance(raw, list) or not raw:
        raise AcceptanceBundleError("seal-malformed")
    files: list[ClosureFile] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size", "mode"}:
            raise AcceptanceBundleError("seal-malformed")
        path = _require_text(item["path"], "seal-malformed")
        digest = _require_sha256(item["sha256"], "seal-malformed")
        size = item["size"]
        file_mode = item["mode"]
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise AcceptanceBundleError("seal-malformed")
        if isinstance(file_mode, bool) or not isinstance(file_mode, int) or not 0 <= file_mode <= 511:
            raise AcceptanceBundleError("seal-malformed")
        files.append(ClosureFile(path=path, sha256=digest, size=size, mode=file_mode))
    if len({entry.path for entry in files}) != len(files):
        raise AcceptanceBundleError("seal-malformed")
    return tuple(files)


def _load_selectors(raw: object) -> tuple[SealedSelector, ...]:
    if not isinstance(raw, list) or not raw:
        raise AcceptanceBundleError("seal-malformed")
    selectors: list[SealedSelector] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"test_id", "ct_id", "selector", "nodeid"}:
            raise AcceptanceBundleError("seal-malformed")
        selectors.append(
            SealedSelector(
                test_id=_require_text(item["test_id"], "seal-malformed", limit=128),
                ct_id=_require_text(item["ct_id"], "seal-malformed", limit=128),
                selector=_require_text(item["selector"], "seal-malformed"),
                nodeid=_require_text(item["nodeid"], "seal-malformed"),
            )
        )
    if len({item.test_id for item in selectors}) != len(selectors):
        raise AcceptanceBundleError("seal-malformed")
    return tuple(selectors)


def _load_identity(raw: object) -> tuple[PinnedIdentity, ...]:
    if not isinstance(raw, list):
        raise AcceptanceBundleError("seal-malformed")
    identity: list[PinnedIdentity] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"name", "sha256"}:
            raise AcceptanceBundleError("seal-malformed")
        name = _require_text(item["name"], "seal-malformed", limit=64)
        if not _LABEL_RE.match(name):
            raise AcceptanceBundleError("seal-malformed")
        identity.append(PinnedIdentity(name=name, sha256=_require_sha256(item["sha256"], "seal-malformed")))
    return tuple(identity)


def load_seal(raw: bytes) -> AcceptanceBundle:
    """Parse and verify one seal record, or refuse with a closed rule."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_SEAL_BYTES:
        raise AcceptanceBundleError("seal-malformed")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise AcceptanceBundleError("seal-malformed") from None
    if not isinstance(payload, dict):
        raise AcceptanceBundleError("seal-malformed")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != _MANIFEST_KIND:
        raise AcceptanceBundleError("seal-schema-unknown")
    recorded = _require_sha256(payload.get("seal_sha256"), "seal-malformed")
    body = {key: value for key, value in payload.items() if key != "seal_sha256"}
    if _sha256(_canonical(body)) != recorded:
        raise AcceptanceBundleError("seal-digest-mismatch")
    closure_files = _load_files(body.get("files"))
    closure = AcceptanceClosure(
        files=closure_files,
        total_bytes=sum(entry.size for entry in closure_files),
        digest=_require_sha256(body.get("closure_sha256"), "seal-malformed"),
    )
    supersedes = body.get("supersedes_sha256")
    return AcceptanceBundle(
        plan_sha256=_require_sha256(body.get("plan_sha256"), "seal-malformed"),
        revision_id=_require_revision(body.get("revision_id")),
        sealed_root=_require_sealed_root(body.get("sealed_root")),
        closure=closure,
        selectors=_load_selectors(body.get("selectors")),
        mode=_require_mode(body.get("mode")),
        identity=_load_identity(body.get("identity")),
        supersedes_sha256=None if supersedes is None else _require_sha256(supersedes, "supersedes-invalid"),
        seal_sha256=recorded,
    )


def _fsync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_seal(bundle: AcceptanceBundle, path: Path) -> Path:
    """Write the seal once, atomically; an existing seal is never replaced."""
    if not isinstance(path, Path):
        raise AcceptanceBundleError("seal-path-invalid")
    raw = seal_bytes(bundle)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644)
    except FileExistsError:
        raise AcceptanceBundleError("seal-exists") from None
    except OSError:
        raise AcceptanceBundleError("seal-path-invalid") from None
    try:
        try:
            handle = os.fdopen(descriptor, "wb")
        except OSError:
            os.close(descriptor)
            raise AcceptanceBundleError("seal-write-failed") from None
        with handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except OSError:
        raise AcceptanceBundleError("seal-write-failed") from None
    return path


def verify_sealed_root(bundle: AcceptanceBundle, root: Path) -> None:
    """Prove ``root`` still is exactly the sealed closure — no more, no less."""
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceBundleError("seal-invalid")
    found = _collect(root)
    expected = _closure_paths(bundle.closure)
    current = _closure_paths(found)
    if set(expected) - set(current):
        raise AcceptanceBundleError("seal-missing-bytes")
    if set(current) - set(expected):
        raise AcceptanceBundleError("seal-extra-bytes")
    if {path: current[path] for path in expected} != expected:
        raise AcceptanceBundleError("seal-byte-drift")
    if found.digest != bundle.closure.digest:
        raise AcceptanceBundleError("seal-digest-mismatch")


def seal_payload(bundle: AcceptanceBundle, root: Path) -> dict[str, bytes]:
    """The exact bytes to hand the authority, verified against the record."""
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceBundleError("seal-invalid")
    try:
        return read_closure_payload(root, bundle.closure)
    except AcceptanceClosureError as error:
        raise AcceptanceBundleError(f"seal-{error.rule.replace('closure-', '')}") from None


def verify_plan(bundle: AcceptanceBundle, plan_bytes: bytes) -> None:
    """The seal is only valid for the plan bytes it was minted from."""
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceBundleError("seal-invalid")
    if _plan_digest(plan_bytes) != bundle.plan_sha256:
        raise AcceptanceBundleError("plan-digest-mismatch")


def verify_revision(bundle: AcceptanceBundle, revision_id: str) -> None:
    """The seal is only valid against the immutable revision it names."""
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceBundleError("seal-invalid")
    if _require_revision(revision_id) != bundle.revision_id:
        raise AcceptanceBundleError("seal-stale")
