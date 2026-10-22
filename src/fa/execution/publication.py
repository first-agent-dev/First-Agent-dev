"""Immutable sealed export of one stopped view (CT105); no publication authority.

Seal answers exactly one question: *which bytes did the barrier freeze, and are
they legal to publish?* It never writes canonical bytes, never creates or moves
`current.json`, never materializes a revision (publish does that under the id
seal returns), and never trusts a caller- or model-supplied manifest.

The three irreversible operations of spec §5 are deliberately separate:

* **seal** (this module) recomputes the view's tree after the terminal barrier,
  validates it and durably records the manifest plus the `SEALED` state;
* **publish** (this module, E269/CT106) materializes the immutable revision under
  the id this module derives, CAS-commits `current.json`, then projects it and
  proves the projection before answering;
* **recovery** (E270/STEP4) inspects intent/current after a crash.

Nothing here is a live/host verdict, and no receipt from this module authorizes
project execution.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import fastjsonschema  # type: ignore[import-untyped]  # Existing schema library has no typing metadata.
from markdown_it import MarkdownIt

from fa.execution.primitives import ExecutionContractError
from fa.execution.protocol import CONFIG_ID, _check
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import NamespaceRef, ViewRef
from fa.execution.workspace import (
    WorkspaceAuthority,
    _budget,
    _canonical,
    _derive_revision_id,
    _PublishInputs,
    _read_json,
    _SealInputs,
)
from fa.inner_loop.workflow_artifacts import _replace_private_bytes

MANIFEST_NAME = "sealed.json"
_MARKDOWN = MarkdownIt("commonmark")
_CONFIG_ID = re.compile(str(CONFIG_ID["pattern"]))
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_MANIFEST_BYTES = 64 * 1024**2
_MAX_DEPTH = 64
# The walker already drops these; a manifest that still names one was forged.
_EXCLUDED_COMPONENTS = frozenset({".git", ".fa", ".venv", ".env"})
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
    edited manifest changes the id it claims. The formula lives in
    `workspace` (it names a directory under `revisions/`) and is re-exported
    here so there is exactly one implementation.
    """
    return _derive_revision_id(manifest)


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
    stored = _read_json(directory, MANIFEST_NAME, _SEALED_MANIFEST, _MAX_MANIFEST_BYTES)
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
        if len(parts) > _MAX_DEPTH or any(part in {"", ".", ".."} for part in parts):
            raise SupervisorError("INPUT_POLICY")
        if parts[0] in _EXCLUDED_COMPONENTS:
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
        if _read_json(directory, MANIFEST_NAME, _SEALED_MANIFEST, _MAX_MANIFEST_BYTES) != manifest:
            raise SupervisorError("DURABILITY_UNKNOWN")
        _budget(deadline)
    except SupervisorError:
        raise
    except OSError:
        raise SupervisorError("DURABILITY_UNKNOWN") from None


@dataclass(frozen=True)
class PublishResult:
    """The publish reply (`protocol.py:138` `_COMMITTED`), plus the caller's op id.

    `revision_id` is derived from the sealed bytes, `tree_sha256` comes from the
    manifest, `workspace_id` is the workspace's identity, and `operation_id` is
    **the caller's own** (`"op-" + request_id`). Nothing here is stored: an exact
    replay is served from the operation journal one layer up, and a fresh request
    observing `PUBLISHED` re-derives the rest (E269 R9).
    """

    workspace_id: str
    revision_id: str
    tree_sha256: str
    operation_id: str
    projection_complete: bool = True

    def to_wire(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "revision_id": self.revision_id,
            "tree_sha256": self.tree_sha256,
            "operation_id": self.operation_id,
            "projection_complete": self.projection_complete,
        }


def publish_view(
    authority: WorkspaceAuthority,
    peer: PeerIdentity,
    namespace: NamespaceRef,
    *,
    view_ref: ViewRef,
    capability: str,
    sealed_manifest_id: str,
    expected_base_revision: str,
    operation_id: str,
    deadline: float,
) -> PublishResult:
    """Commit one SEALED view's bytes to the canonical tree, or prove it is done.

    Four durable boundaries, one transaction each (E269 D3), mirroring seal's
    `prepare_seal`/`mark_sealed` split rather than inventing a longer critical
    section: validate (no writes) → materialize revision + intent → CAS the
    pointer → project, prove, publish. A determinate failure before the pointer
    discards only this attempt's revision; anything at or after the pointer is
    `DURABILITY_UNKNOWN` and belongs to recovery, never to a silent retry.
    """
    if not isinstance(authority, WorkspaceAuthority):
        raise SupervisorError("UNAUTHORIZED")
    inputs = authority.prepare_publish(
        peer,
        namespace,
        view_ref=view_ref,
        capability=capability,
        sealed_manifest_id=sealed_manifest_id,
        expected_base_revision=expected_base_revision,
        operation_id=operation_id,
        manifest_reader=_read_sealed_manifest,
        deadline=deadline,
    )
    if inputs.record["state"] == "PUBLISHED":
        return _result(
            authority.verify_publication(peer, namespace, capability=capability, inputs=inputs, deadline=deadline)
        )
    try:
        authority.materialize_publication(peer, namespace, capability=capability, inputs=inputs, deadline=deadline)
        _commit_current(authority, peer, namespace, capability=capability, inputs=inputs, deadline=deadline)
    except SupervisorError as error:
        if error.code in {"STALE_REVISION", "STALE_GENERATION"}:
            authority.abandon_publication(peer, namespace, capability=capability, inputs=inputs, deadline=deadline)
        raise
    return _result(
        authority.project_publication(peer, namespace, capability=capability, inputs=inputs, deadline=deadline)
    )


def _commit_current(
    authority: WorkspaceAuthority,
    peer: PeerIdentity,
    namespace: NamespaceRef,
    *,
    capability: str,
    inputs: _PublishInputs,
    deadline: float,
) -> None:
    """The pointer commit, isolated so CT106's kill target is one call (E269 D1).

    Removing this call leaves `current.json` at the base revision: no functional
    publish case can pass, and no revision is ever reachable by a reader.
    """
    authority.commit_revision_current(peer, namespace, capability=capability, inputs=inputs, deadline=deadline)


def _result(receipt: Mapping[str, Any]) -> PublishResult:
    return PublishResult(
        workspace_id=str(receipt["workspace_id"]),
        revision_id=str(receipt["revision_id"]),
        tree_sha256=str(receipt["tree_sha256"]),
        operation_id=str(receipt["operation_id"]),
        projection_complete=bool(receipt["projection_complete"]),
    )


def _read_sealed_manifest(
    directory: int, plan_path: str | None, base_entries: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Read and re-validate the stored manifest; never re-derive one from a tree.

    The same `_validate_sealed_tree` that seal used runs again here, so a
    manifest edited on disk is refused for what it is (path/fact/base/plan/digest)
    rather than being trusted because it parses.
    """
    manifest = _read_json(directory, MANIFEST_NAME, _SEALED_MANIFEST, _MAX_MANIFEST_BYTES)
    _validate_sealed_tree(manifest, plan_path=plan_path, base_entries=base_entries)
    return manifest


# --- prepared bundle (E271 / STEP3): the trusted bounded renderer ----------
#
# Spec §7.1 fixes the literal layout and the controller-owned frontmatter; no
# model-supplied file map exists anywhere on this path. The renderer is pure so
# every rule below is a C0 oracle, and `prepare_bundle` only stores its output.

BUNDLE_ROOT = "worklogs"
_LEDGER_BODY = "# Ledger — decision and evidence log\n\nFixed heading only; entries are appended by the run.\n"
_MAX_BUNDLE_BYTES = 4 * 1024**2
_ROADMAP_HEADINGS = ("## Intent", "## Out-of-scope")
_METADATA_LINE = re.compile(r"^\s*(?:Roadmap-ID|Increment-ID|status|slices|shipped|active-increment)\s*:", re.M)
_SLICE_HEADING = re.compile(r"^## SLICE(\d+):", re.M)


@dataclass(frozen=True)
class InstallResult:
    """The `install_project` reply (protocol `_COMMITTED`): one committed revision."""

    workspace_id: str
    revision_id: str
    tree_sha256: str
    operation_id: str
    projection_complete: bool


@dataclass(frozen=True)
class BundleResult:
    """The `prepare_bundle` reply (`protocol.py`): a private id and its digest."""

    validated_bundle_id: str
    bundle_sha256: str

    def to_wire(self) -> dict[str, str]:
        return {"validated_bundle_id": self.validated_bundle_id, "bundle_sha256": self.bundle_sha256}


def bundle_paths(project_slug: str, increment_slug: str) -> tuple[str, str, str]:
    """The three canonical paths, in the order the renderer emits them."""
    root = f"{BUNDLE_ROOT}/{project_slug}"
    return (f"{root}/roadmap.md", f"{root}/ledger.md", f"{root}/increments/increment-01-{increment_slug}.md")


def render_bundle(
    project_slug: str, increment_slug: str, roadmap_text: str, increment_text: str, *, created: str
) -> dict[str, bytes]:
    """Render exactly three files from prose that has been strictly validated.

    The controller owns every piece of metadata: ids, dates, statuses, the slice
    count and the ledger header. The caller supplies prose only, so a model can
    never smuggle a frontmatter field, a second increment or a lifecycle claim
    into a new project.
    """
    _validate_bundle_text(project_slug, increment_slug, roadmap_text, increment_text, created)
    slices = _slice_numbers(increment_text)
    roadmap_path, ledger_path, increment_path = bundle_paths(project_slug, increment_slug)
    roadmap = (
        "---\n"
        f"Roadmap-ID: RM-{project_slug}\n"
        f"slug: {project_slug}\n"
        f"created: {created}\n"
        "status: IN PROGRESS\n"
        "active-increment: I01\n"
        "---\n\n"
        f"# Roadmap — {project_slug}\n\n"
        "## Artifacts\n\n"
        "| Artifact | Path | Status |\n"
        "| --- | --- | --- |\n"
        f"| Roadmap | `{roadmap_path}` | IN PROGRESS |\n"
        f"| Increment | `{increment_path}` | IN PROGRESS |\n"
        f"| Ledger | `{ledger_path}` | — |\n\n"
        "## Increments\n\n"
        "| ID | Slug | Status |\n"
        "| --- | --- | --- |\n"
        f"| I01 | [{increment_slug}]({increment_path}) | IN PROGRESS |\n\n" + roadmap_text.rstrip("\n") + "\n"
    )
    increment = (
        "---\n"
        f"Increment-ID: RM-{project_slug}-I01\n"
        f"Roadmap-ID: RM-{project_slug}\n"
        f"slug: {increment_slug}\n"
        "status: IN PROGRESS\n"
        f"slices: {len(slices)}\n"
        "shipped: —\n"
        "---\n\n" + increment_text.rstrip("\n") + "\n"
    )
    return {
        roadmap_path: roadmap.encode("utf-8"),
        ledger_path: _LEDGER_BODY.encode("utf-8"),
        increment_path: increment.encode("utf-8"),
    }


def _validate_bundle_text(
    project_slug: str, increment_slug: str, roadmap_text: str, increment_text: str, created: str
) -> None:
    """Every refusal here is `INPUT_POLICY`: prose in, metadata out."""
    for slug in (project_slug, increment_slug):
        if len(slug) > 48 or not _CONFIG_ID.fullmatch(slug):
            raise SupervisorError("INPUT_POLICY")
    if not _DATE.fullmatch(created):
        raise SupervisorError("INPUT_POLICY")
    for text in (roadmap_text, increment_text):
        if not isinstance(text, str) or len(text.encode("utf-8")) > _MAX_BUNDLE_BYTES:
            raise SupervisorError("INPUT_POLICY")
        if "\x00" in text:
            raise SupervisorError("INPUT_POLICY")
        if _METADATA_LINE.search(_outside_fences(text)):
            raise SupervisorError("INPUT_POLICY")  # no disguised controller metadata
    if roadmap_text.lstrip("\n").startswith("---"):
        raise SupervisorError("INPUT_POLICY")
    if increment_text.lstrip("\n").startswith("---"):
        raise SupervisorError("INPUT_POLICY")
    headings = [line.strip() for line in _outside_fences(roadmap_text).splitlines() if line.startswith("## ")]
    if headings != list(_ROADMAP_HEADINGS):
        raise SupervisorError("INPUT_POLICY")  # both prose sections, exactly, in order
    slices = _slice_numbers(increment_text)
    if not slices:
        raise SupervisorError("INPUT_POLICY")
    if sorted(slices) != list(range(1, len(slices) + 1)):
        raise SupervisorError("INPUT_POLICY")  # contiguous, unique, starting at one


def _slice_numbers(increment_text: str) -> list[int]:
    return [int(number) for number in _SLICE_HEADING.findall(_outside_fences(increment_text))]


def _outside_fences(text: str) -> str:
    """Blank every code block, keeping line positions intact.

    Spec §7.1 asks for MarkdownIt tokens rather than substring surgery or a
    second parser, so the existing dependency decides what a code block is:
    ```/~~~ fences and 4-space indented blocks behave exactly as CommonMark
    says. A blanked line keeps its newline so line-based rules stay aligned.
    """
    lines = text.splitlines()
    masked = list(lines)
    for token in _MARKDOWN.parse(text):
        if token.type not in {"fence", "code_block"} or token.map is None:
            continue
        start, end = token.map
        for index in range(start, min(end, len(masked))):
            masked[index] = ""
    return "\n".join(masked)


def prepare_bundle(
    authority: WorkspaceAuthority,
    peer: PeerIdentity,
    namespace: NamespaceRef,
    *,
    capability: str,
    project_slug: str,
    increment_slug: str,
    roadmap_text: str,
    increment_text: str,
    expected_base_revision: str,
    operation_id: str,
    created: str,
    deadline: float,
) -> BundleResult:
    """Render, validate and durably store a bundle; mint its id privately.

    OWNER grant, no view, all writers settled, exact base revision: a bundle is
    a *pre-install* object, so it is bound to the generation and base it was
    prepared against and can never be reused against a different one.
    """
    if not isinstance(authority, WorkspaceAuthority):
        raise SupervisorError("UNAUTHORIZED")
    files = render_bundle(project_slug, increment_slug, roadmap_text, increment_text, created=created)
    stored = authority.store_bundle(
        peer,
        namespace,
        capability=capability,
        project_slug=project_slug,
        increment_slug=increment_slug,
        files=files,
        expected_base_revision=expected_base_revision,
        operation_id=operation_id,
        deadline=deadline,
    )
    return BundleResult(
        validated_bundle_id=str(stored["validated_bundle_id"]), bundle_sha256=str(stored["bundle_sha256"])
    )


def install_project(
    authority: WorkspaceAuthority,
    peer: PeerIdentity,
    namespace: NamespaceRef,
    *,
    capability: str,
    validated_bundle_id: str,
    project_slug: str,
    deadline: float,
) -> InstallResult:
    """Install a prepared bundle into this workspace and return the committed receipt.

    One call, one irreversible step: the authority owns the intent, the
    no-clobber rename, the revision and the pointer, so a caller cannot install
    half a project or leave a bundle consumed. The wire's `_COMMITTED` is the
    only reply, and it is returned only after the canonical tree is proved.
    """
    if not isinstance(authority, WorkspaceAuthority):
        raise SupervisorError("UNAUTHORIZED")
    receipt = authority.install_project(
        peer,
        namespace,
        capability=capability,
        validated_bundle_id=validated_bundle_id,
        project_slug=project_slug,
        deadline=deadline,
    )
    return InstallResult(
        workspace_id=str(receipt["workspace_id"]),
        revision_id=str(receipt["revision_id"]),
        tree_sha256=str(receipt["tree_sha256"]),
        operation_id=str(receipt["operation_id"]),
        projection_complete=bool(receipt["projection_complete"]),
    )


__all__ = [
    "BUNDLE_ROOT",
    "MANIFEST_NAME",
    "BundleResult",
    "InstallResult",
    "PublishResult",
    "SealResult",
    "bundle_paths",
    "derive_revision_id",
    "install_project",
    "prepare_bundle",
    "publish_view",
    "render_bundle",
    "seal_view",
]
