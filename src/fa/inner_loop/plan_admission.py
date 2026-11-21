"""Explicit-plan snapshots for retained I02; not an execution-isolation boundary.

Only the selected workspace is authoritative. A snapshot owns the bytes that
were read, not a promise that arbitrary shell/host writers cannot change them.
"""

from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from fa.inner_loop.plan_ids import PlanIds, extract_plan_ids
from fa.inner_loop.plan_v2 import (
    DISPOSITION_OWNERS,
    DISPOSITION_REASONS,
    MAX_DISPOSITION_AGE_DAYS,
    MAX_DISPOSITIONS,
    Invariant,
    PlanGraph,
    PlanV2Error,
    parse_plan,
)

MAX_PLAN_BYTES = 1024 * 1024

#: The grammar an admitted snapshot was read with. This is the *route's*
#: decision, never the document's: nothing here sniffs a marker to pick a
#: parser, because a plan that could choose its own grammar could choose a
#: weaker one (INV-01). ``PLAN-V1`` is the frozen legacy grammar; ``PLAN-V2``
#: is the ``AI-NATIVE-PLAN-V2`` contract in ``plan_v2``.
PLAN_V1 = "PLAN-V1"
PLAN_V2 = "PLAN-V2"
ADMISSION_FORMATS = frozenset({PLAN_V1, PLAN_V2})


class PlanRefError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid plan reference: {rule}")


@dataclass(frozen=True, slots=True)
class PlanRef:
    workspace_relative_path: str
    source_kind: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PlanSnapshot:
    """One captured plan buffer plus the grammar it was admitted under.

    ``ids`` is the legacy V1 extraction and is deliberately empty for a
    ``PLAN-V2`` snapshot: running the V1 extractor over V2 bytes would produce
    a mixed artifact that the V1 rules then judge (the defect INV-01 names).
    ``graph`` is the parsed V2 answer, ``format_error`` its closed refusal
    rule, so a caller can report a refusal without catching an exception.
    """

    ref: PlanRef
    utf8_bytes: bytes
    text: str
    ids: PlanIds
    format: str = PLAN_V1
    graph: PlanGraph | None = None
    format_error: str | None = None


#: R1/R6 (E577): the caller's grant. ``doc:`` is the only kind a machine can
#: check, and it is checked against bytes (``<path>@sha256:<64 hex>``); ``issue:``
#: and ``review:`` are typed references this system cannot resolve, so they stay
#: attested-with-reference and are never reported as verified.
_EVIDENCE_DOC_RE = re.compile(r"doc:(?P<path>[A-Za-z0-9_][A-Za-z0-9_./-]*)@sha256:(?P<digest>[0-9a-f]{64})")
_EVIDENCE_ISSUE_RE = re.compile(r"issue:[A-Z][A-Z0-9]+-[0-9]+")
_EVIDENCE_REVIEW_RE = re.compile(r"review:[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
MAX_EVIDENCE_CHARS = 256
_DISPOSITION_FIELDS = frozenset({"reason", "owner", "evidence", "reviewed_at"})


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """One typed evidence reference; ``digest`` exists only for ``doc``."""

    kind: str
    target: str
    digest: str | None = None

    def text(self) -> str:
        """The canonical form, which is what a bound invariant carries."""
        if self.kind == "doc":
            return f"doc:{self.target}@sha256:{self.digest}"
        return f"{self.kind}:{self.target}"


@dataclass(frozen=True, slots=True)
class DispositionDeclaration:
    """What the caller grants: a reason, who owns it, against what, and when."""

    reason: str
    owner: str
    evidence: EvidenceRef
    reviewed_at: date


def _evidence_ref(raw: object) -> EvidenceRef:
    if not isinstance(raw, str) or not raw or len(raw) > MAX_EVIDENCE_CHARS:
        raise PlanRefError("disposition-evidence-invalid")
    doc = _EVIDENCE_DOC_RE.fullmatch(raw)
    if doc is not None:
        return EvidenceRef(kind="doc", target=doc["path"], digest=doc["digest"])
    if _EVIDENCE_ISSUE_RE.fullmatch(raw) is not None:
        return EvidenceRef(kind="issue", target=raw.partition(":")[2])
    if _EVIDENCE_REVIEW_RE.fullmatch(raw) is not None:
        return EvidenceRef(kind="review", target=raw.partition(":")[2])
    raise PlanRefError("disposition-evidence-invalid")


def _review_date(raw: object) -> date:
    if not isinstance(raw, str):
        raise PlanRefError("disposition-reviewed-at-invalid")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise PlanRefError("disposition-reviewed-at-invalid") from None


def parse_dispositions(raw: object) -> tuple[DispositionDeclaration, ...]:
    """Validate the caller's declarations; every refusal is a closed rule.

    Shape and vocabulary only. Age is a fact about *today*, so it is checked by
    :func:`bind_dispositions`, which is told the date.
    """
    if raw is None:
        return ()
    if not isinstance(raw, (list, tuple)):
        raise PlanRefError("disposition-invalid")
    if len(raw) > MAX_DISPOSITIONS:
        raise PlanRefError("disposition-too-many")
    declarations: list[DispositionDeclaration] = []
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != _DISPOSITION_FIELDS:
            raise PlanRefError("disposition-invalid")
        reason = item["reason"]
        if not isinstance(reason, str) or reason not in DISPOSITION_REASONS:
            raise PlanRefError("disposition-reason-unratified")
        owner = item["owner"]
        if not isinstance(owner, str) or owner not in DISPOSITION_OWNERS:
            raise PlanRefError("disposition-owner-invalid")
        declarations.append(
            DispositionDeclaration(
                reason=reason,
                owner=owner,
                evidence=_evidence_ref(item["evidence"]),
                reviewed_at=_review_date(item["reviewed_at"]),
            )
        )
    if len({item.reason for item in declarations}) != len(declarations):
        raise PlanRefError("disposition-duplicate-reason")
    return tuple(declarations)


def bind_dispositions(graph: PlanGraph, declarations: Sequence[DispositionDeclaration], *, today: date) -> PlanGraph:
    """Attach the caller's grant to the plan's requests, or refuse (R1).

    The plan asks by reason and can never name an owner; only a declaration makes
    the request legal, and the declaration is the sole source of owner, evidence
    and review date. A grant older than ``MAX_DISPOSITION_AGE_DAYS`` authorises
    nothing -- including when the plan does not use it, because a stale grant
    says the review that backs it is stale, not that the claim is fine.
    """
    granted: dict[str, DispositionDeclaration] = {}
    for grant in declarations:
        if grant.reviewed_at > today:
            raise PlanRefError("disposition-reviewed-at-invalid")
        if (today - grant.reviewed_at).days > MAX_DISPOSITION_AGE_DAYS:
            raise PlanRefError("disposition-review-stale")
        granted[grant.reason] = grant
    bound: list[Invariant] = []
    for invariant in graph.invariants:
        if invariant.evidence != "NON_EXECUTABLE":
            bound.append(invariant)
            continue
        declaration = granted.get(invariant.reason or "")
        if declaration is None:
            raise PlanRefError("disposition-undeclared")
        bound.append(replace(invariant, owner=declaration.owner, evidence_ref=declaration.evidence.text()))
    return replace(graph, invariants=tuple(bound))


def _require_plan_for_coder(roles: list[str], plan_path: Path | None) -> None:
    """Presence only; callers own read/evidence policy (CT90/95)."""
    if "coder" in roles and plan_path is None:
        raise PlanRefError("missing")


def _relative_plan_path(workspace: Path, plan_path: Path) -> tuple[Path, tuple[str, ...]]:
    try:
        root = workspace.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PlanRefError("unreadable") from exc
    path = plan_path
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError as exc:
            raise PlanRefError("path-escape") from exc
    parts = path.parts
    if any("\x00" in part for part in parts):
        raise PlanRefError("unreadable")
    # Path already normalizes empty/dot components; parent traversal remains.
    if not parts or ".." in parts:
        raise PlanRefError("path-escape")
    return root, parts


def _open_plan_component(parent_fd: int, name: str, *, directory: bool) -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    if directory:
        flags |= os.O_DIRECTORY
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as exc:
        # Classification only: never authorize an open using this second stat.
        try:
            is_link = stat.S_ISLNK(os.stat(name, dir_fd=parent_fd, follow_symlinks=False).st_mode)
        except OSError:
            is_link = False
        if exc.errno == errno.ELOOP or is_link:
            raise PlanRefError("symlink") from exc
        raise PlanRefError("unreadable") from exc


def _read_plan_bytes(root: Path, parts: tuple[str, ...]) -> bytes:
    parent_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    file_fd: int | None = None
    try:
        for part in parts[:-1]:
            previous_fd = parent_fd
            parent_fd = _open_plan_component(parent_fd, part, directory=True)
            os.close(previous_fd)
        file_fd = _open_plan_component(parent_fd, parts[-1], directory=False)
        return _read_open_plan_bytes(file_fd)

    finally:
        try:
            if file_fd is not None:
                os.close(file_fd)
        finally:
            os.close(parent_fd)


def _read_open_plan_bytes(file_fd: int) -> bytes:
    before = os.fstat(file_fd)
    if not stat.S_ISREG(before.st_mode):
        raise PlanRefError("not-regular")
    if before.st_size > MAX_PLAN_BYTES:
        raise PlanRefError("too-large")
    chunks: list[bytes] = []
    remaining = MAX_PLAN_BYTES + 1
    while remaining:
        chunk = os.read(file_fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    raw = b"".join(chunks)
    if len(raw) > MAX_PLAN_BYTES:
        raise PlanRefError("too-large")
    after = os.fstat(file_fd)
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise PlanRefError("source-changed")
    return raw


def read_plan_snapshot(workspace: Path, plan_path: Path) -> PlanSnapshot:
    """Read at most limit+1 bytes via no-follow descriptors, then parse once.

    Absolute public inputs are allowed only lexically inside the selected
    workspace. Stored identity is always normalized relative POSIX. Hard-link
    publication restrictions belong to promotion, not this read-only operation.
    """
    root, parts = _relative_plan_path(workspace, plan_path)
    try:
        raw = _read_plan_bytes(root, parts)
    except OSError as exc:
        raise PlanRefError("unreadable") from exc
    return snapshot_from_bytes(Path(*parts).as_posix(), raw)


def _decode_plan_bytes(raw: bytes) -> str:
    if len(raw) > MAX_PLAN_BYTES:
        raise PlanRefError("too-large")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PlanRefError("invalid-utf8") from exc
    if not text.strip():
        raise PlanRefError("empty")
    return text


def snapshot_from_bytes(
    relative_path: str,
    raw: bytes,
    *,
    source_kind: str = "EXPLICIT",
    format: str = PLAN_V1,
    roadmap: str = "",
) -> PlanSnapshot:
    """Capture/parse one immutable buffer; publication never recopies a mutable draft.

    ``format`` comes from the caller's route, and only the caller's route. A
    ``PLAN-V2`` snapshot requires the roadmap text because the V2 contract is a
    roadmap/increment pair; the pair is parsed once here so admission can
    report a closed rule instead of an exception, and no partial result ever
    escapes (``graph`` is ``None`` whenever ``format_error`` is set).
    """
    if format not in ADMISSION_FORMATS:
        raise PlanRefError("format-unknown")
    text = _decode_plan_bytes(raw)
    ref = PlanRef(relative_path, source_kind, hashlib.sha256(raw).hexdigest())
    if format == PLAN_V1:
        return PlanSnapshot(ref=ref, utf8_bytes=raw, text=text, ids=extract_plan_ids(text))
    graph, rule = _v2_graph(roadmap, text)
    return PlanSnapshot(
        ref=ref,
        utf8_bytes=raw,
        text=text,
        ids=PlanIds(),
        format=PLAN_V2,
        graph=graph,
        format_error=rule,
    )


def _v2_graph(roadmap: object, increment: str) -> tuple[PlanGraph | None, str | None]:
    """Parse the V2 roadmap/increment pair into a closed (graph, rule) pair."""
    if not isinstance(roadmap, str) or not roadmap.strip():
        return None, "roadmap-missing"
    try:
        return parse_plan(roadmap=roadmap, increment=increment), None
    except PlanV2Error as error:
        return None, error.rule
