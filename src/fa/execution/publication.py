"""Immutable sealed export of one stopped view (CT105); no publication authority.

Seal answers exactly one question: *which bytes did the barrier freeze, and are
they legal to publish?* It never writes canonical bytes, never creates or moves
`current.json`, never materializes a revision (publish does that under the id
seal returns), and never trusts a caller- or model-supplied manifest.

The three irreversible operations of spec §5 are deliberately separate:

* **seal** (this module) recomputes the view's tree after the terminal barrier,
  validates it and durably records the manifest plus the `SEALED` state;
* **publish** (`E268`) materializes the immutable revision under the id this
  module derives, then commits the current pointer and projects it;
* **recovery** (`E269`) inspects intent/current after a crash.

Nothing here is a live/host verdict, and no receipt from this module authorizes
project execution.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import fastjsonschema  # type: ignore[import-untyped]  # Existing schema library has no typing metadata.

from fa.execution.primitives import ExecutionContractError
from fa.execution.protocol import _check
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import NamespaceRef, ViewRef
from fa.execution.workspace import WorkspaceAuthority, _budget, _canonical, _read_json, _SealInputs
from fa.inner_loop.workflow_artifacts import _replace_private_bytes

MANIFEST_NAME = "sealed.json"
MAX_MANIFEST_BYTES = 64 * 1024**2
MAX_DEPTH = 64
# The walker already drops these; a manifest that still names one was forged.
EXCLUDED_COMPONENTS = frozenset({".git", ".fa", ".venv", ".env"})
_PRIVILEGE_BITS = 0o7000

_SHA = {"type": "string", "pattern": "^[0-9a-f]{64}\\Z"}
_PATH = {"type": "string", "pattern": "^[^/\\x00]+(?:/[^/\\x00]+)*\\Z", "maxLength": 4096}
_ENTRY = {
    "type": "object",
    "properties": {
        "path": _PATH,
        "type": {"enum": ["file", "directory", "symlink"]},
        "mode": {"type": "integer", "minimum": 0, "maximum": 0o7777},
        "size": {"type": "integer", "minimum": 0},
        "sha256": {"anyOf": [_SHA, {"type": "null"}]},
        "deleted": {"type": "boolean"},
        "link_target": {"anyOf": [{"type": "string", "maxLength": 4096}, {"type": "null"}]},
    },
    "required": ["path", "type", "mode", "size", "sha256", "deleted", "link_target"],
    "additionalProperties": False,
}
# Spec §5 freezes this header exactly; it is NOT the revision `_TREE` shape
# (that one carries `revision_id` and forbids tombstones).
_SEALED_MANIFEST = fastjsonschema.compile(
    {
        "type": "object",
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "workspace_id": {"type": "string", "pattern": "^ws-[0-9a-f]{32}\\Z"},
            "generation": {"type": "integer", "minimum": 1},
            "base_revision": {"type": "string", "pattern": "^rev-[0-9a-f]{32}\\Z"},
            "view_id": {"type": "string", "pattern": "^view-[0-9a-f]{32}\\Z"},
            "tree_sha256": _SHA,
            "entries": {"type": "array", "items": _ENTRY},
        },
        "required": [
            "schema_version",
            "workspace_id",
            "generation",
            "base_revision",
            "view_id",
            "tree_sha256",
            "entries",
        ],
        "additionalProperties": False,
    }
)


@dataclass(frozen=True)
class SealResult:
    """The seal reply (`protocol.py:162`): an id, a derived revision, a digest."""

    sealed_manifest_id: str
    revision_id: str
    tree_sha256: str

    def to_wire(self) -> dict[str, str]:
        return {
            "sealed_manifest_id": self.sealed_manifest_id,
            "revision_id": self.revision_id,
            "tree_sha256": self.tree_sha256,
        }


def derive_revision_id(manifest: Mapping[str, Any]) -> str:
    """Content-address the revision publish must materialize (E267 D2).

    The id is a function of the sealed bytes, so publish recomputes it from the
    stored manifest instead of accepting one from a caller, and a swapped or
    edited manifest changes the id it claims.
    """
    return "rev-" + hashlib.sha256(_canonical(dict(manifest))).hexdigest()[:32]


def seal_view(
    authority: WorkspaceAuthority,
    peer: PeerIdentity,
    namespace: NamespaceRef,
    *,
    view_ref: ViewRef,
    capability: str,
    deadline: float,
) -> SealResult:
    """Freeze one stopped view's bytes into a validated manifest and seal it.

    Every precondition (closed gate, `STOPPING`, terminal receipt, live writer
    generation, base revision, source hash) is proved by the authority, which
    also recomputes the tree after the barrier. This function owns only the
    manifest rules and the durability order: manifest first, `SEALED` second.
    """
    if not isinstance(authority, WorkspaceAuthority):
        raise SupervisorError("UNAUTHORIZED")
    inputs = authority.prepare_seal(peer, namespace, view_ref=view_ref, capability=capability, deadline=deadline)
    if inputs.record["state"] == "SEALED":
        return _replay_seal(inputs.directory, str(inputs.record["sealed_manifest_id"]), inputs)
    manifest = _build_manifest(inputs)
    _validate_sealed_tree(manifest, plan_path=inputs.plan_path, base_entries=inputs.base_entries)
    sealed_manifest_id = "seal-" + uuid4().hex
    _write_manifest(inputs.directory, manifest, deadline)
    _budget(deadline)
    authority.mark_sealed(
        peer,
        namespace,
        view_ref=view_ref,
        capability=capability,
        sealed_manifest_id=sealed_manifest_id,
        deadline=deadline,
    )
    return SealResult(sealed_manifest_id, derive_revision_id(manifest), str(manifest["tree_sha256"]))


def _replay_seal(directory: int, sealed_manifest_id: str, inputs: _SealInputs) -> SealResult:
    """A retried seal answers from durable bytes, or refuses loudly (R8)."""
    stored = _read_json(directory, MANIFEST_NAME, _SEALED_MANIFEST, MAX_MANIFEST_BYTES)
    _validate_sealed_tree(stored, plan_path=inputs.plan_path, base_entries=inputs.base_entries)
    # The bytes are frozen after the barrier, so a reseal must observe the same
    # digest; anything else means the view or its manifest moved underneath us.
    if stored["tree_sha256"] != inputs.tree_sha256:
        raise SupervisorError("CORRUPT_STATE")
    if stored["view_id"] != inputs.view_ref.view_id or stored["workspace_id"] != inputs.view_ref.workspace_id:
        raise SupervisorError("CORRUPT_STATE")
    return SealResult(sealed_manifest_id, derive_revision_id(stored), str(stored["tree_sha256"]))


def _build_manifest(inputs: _SealInputs) -> dict[str, Any]:
    entries = _entries_with_tombstones(inputs.entries, inputs.base_entries)
    return {
        "schema_version": 1,
        "workspace_id": inputs.view_ref.workspace_id,
        "generation": inputs.generation,
        "base_revision": inputs.base_revision,
        "view_id": inputs.view_ref.view_id,
        "tree_sha256": _tree_hash(entries),
        "entries": entries,
    }


def _entries_with_tombstones(
    sealed: Sequence[Mapping[str, Any]], base: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """Sealed entries plus a faithful tombstone for every base path now gone.

    A tombstone is *not* a deletion order for the canonical projection; it is the
    record of what disappeared, carrying the base entry's own facts so a reader
    can tell "deleted this file" from "deleted something else at this path".
    """
    kept = {entry["path"] for entry in sealed}
    entries = [dict(entry) for entry in sealed]
    entries.extend({**dict(entry), "deleted": True} for entry in base if entry["path"] not in kept)
    entries.sort(key=lambda entry: entry["path"])
    return entries


def _tree_hash(entries: Sequence[Mapping[str, Any]]) -> str:
    """Spec §5: hash the canonical JSON of the *non-deleted* entries only."""
    live = [dict(entry) for entry in entries if not entry["deleted"]]
    return hashlib.sha256(_canonical(live)).hexdigest()


def _validate_sealed_tree(
    manifest: Mapping[str, Any],
    *,
    plan_path: str | None,
    base_entries: Sequence[Mapping[str, Any]],
) -> None:
    """The one seal validator; every rule a later publisher may rely on.

    Order matters for useful diagnostics: shape, then path domain, then
    per-entry facts, then the base comparison, then the protected plan boundary,
    and only then the digest — so a forged manifest is rejected for what it is,
    never because its self-declared hash happened to disagree first.
    """
    try:
        _check(_SEALED_MANIFEST, manifest)
    except ExecutionContractError:
        raise SupervisorError("INPUT_POLICY") from None
    entries = manifest["entries"]
    _validate_paths(entries)
    for entry in entries:
        _validate_entry_facts(entry)
    base = {entry["path"]: entry for entry in base_entries}
    for entry in entries:
        _validate_against_base(entry, base.get(entry["path"]))
    _validate_plan_boundary(entries, base, plan_path)
    if _tree_hash(entries) != manifest["tree_sha256"]:
        raise SupervisorError("CORRUPT_STATE")


def _validate_paths(entries: Sequence[Mapping[str, Any]]) -> None:
    previous = ""
    for entry in entries:
        path = entry["path"]
        parts = path.split("/")
        if path <= previous:
            raise SupervisorError("INPUT_POLICY")  # Sorted and unique, or the digest is meaningless.
        previous = path
        if len(parts) > MAX_DEPTH or any(part in {"", ".", ".."} for part in parts):
            raise SupervisorError("INPUT_POLICY")
        if parts[0] in EXCLUDED_COMPONENTS:
            raise SupervisorError("INPUT_POLICY")


def _validate_entry_facts(entry: Mapping[str, Any]) -> None:
    """Type/size/hash/link coherence, and no privilege bits anywhere."""
    if entry["mode"] & _PRIVILEGE_BITS:
        raise SupervisorError("INPUT_POLICY")
    kind = entry["type"]
    if kind == "directory":
        if entry["sha256"] is not None or entry["link_target"] is not None or entry["size"] != 0:
            raise SupervisorError("INPUT_POLICY")
        return
    if kind == "file":
        if entry["sha256"] is None or entry["link_target"] is not None:
            raise SupervisorError("INPUT_POLICY")
        return
    target = entry["link_target"]
    if target is None or entry["sha256"] is None:
        raise SupervisorError("INPUT_POLICY")
    raw = target.encode("utf-8")
    if len(raw) != entry["size"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise SupervisorError("INPUT_POLICY")


def _validate_against_base(entry: Mapping[str, Any], base: Mapping[str, Any] | None) -> None:
    """Tombstones may only repeat base facts; links may only stay unchanged."""
    if entry["deleted"]:
        if base is None or any(entry[key] != base[key] for key in ("type", "mode", "size", "sha256", "link_target")):
            raise SupervisorError("INPUT_POLICY")
        return
    if entry["type"] == "symlink":
        if base is None or base["type"] != "symlink" or base["link_target"] != entry["link_target"]:
            raise SupervisorError("INPUT_POLICY")
    target = entry["link_target"]
    if target is not None and (target.startswith("/") or _escapes(entry["path"], target)):
        raise SupervisorError("INPUT_POLICY")


def _escapes(path: str, target: str) -> bool:
    resolved = path.split("/")[:-1]
    for part in target.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not resolved:
                return True
            resolved.pop()
            continue
        resolved.append(part)
    return False


def _validate_plan_boundary(
    entries: Sequence[Mapping[str, Any]], base: Mapping[str, Mapping[str, Any]], plan_path: str | None
) -> None:
    """No run may rewrite its own plan through an ordinary revision seal.

    The plan's canonical path, everything above it and everything below it are
    frozen: a lowercased path here would let a coder edit the document that
    judges it. Unchanged bytes are legitimate and stay in the manifest.
    """
    if plan_path is None:
        return
    for entry in entries:
        path = entry["path"]
        related = path == plan_path or plan_path.startswith(path + "/") or path.startswith(plan_path + "/")
        if not related:
            continue
        if _changes_plan_bytes(entry, base.get(path), plan_path):
            raise SupervisorError("INPUT_POLICY")


def _changes_plan_bytes(entry: Mapping[str, Any], base: Mapping[str, Any] | None, plan_path: str) -> bool:
    """True when this entry would move the bytes a plan-based verdict rests on."""
    if entry["deleted"] or base is None:
        return True
    if entry["path"] == plan_path:
        return any(entry[key] != base[key] for key in ("type", "sha256", "size"))
    # An ancestor of the plan may not change type or vanish; its own metadata is fine.
    return plan_path.startswith(entry["path"] + "/") and entry["type"] != base["type"]


def _write_manifest(directory: int, manifest: Mapping[str, Any], deadline: float) -> None:
    """Manifest first, and prove it; the `SEALED` flip happens after this."""
    try:
        _replace_private_bytes(directory, MANIFEST_NAME, _canonical(dict(manifest)))
        if _read_json(directory, MANIFEST_NAME, _SEALED_MANIFEST, MAX_MANIFEST_BYTES) != manifest:
            raise SupervisorError("DURABILITY_UNKNOWN")
        _budget(deadline)
    except SupervisorError:
        raise
    except OSError:
        raise SupervisorError("DURABILITY_UNKNOWN") from None


__all__ = ["MANIFEST_NAME", "SealResult", "derive_revision_id", "seal_view"]
