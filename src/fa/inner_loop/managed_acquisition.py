"""Strict data boundary for the controller-owned nested acquisition choice.

This module intentionally contains no workflow state machine or filesystem
access. A future controller caller supplies the actual initial planner's
``SessionOutcome.final_text``; only the exact closed JSON variants below cross
that boundary. Stable-ID resolution and rendering remain separate trusted
steps, not model-selected paths or bytes written by the planner.
"""

from __future__ import annotations

import json
import re
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, TypeAlias, TypeGuard

import yaml
from yaml.nodes import MappingNode
from yaml.tokens import AliasToken, AnchorToken

from fa.inner_loop.plan_admission import PlanSnapshot, snapshot_from_bytes

__all__ = [
    "AcquisitionChoice",
    "AcquisitionChoiceError",
    "AcquisitionMetadataError",
    "BootstrapNewProjectChoice",
    "CanonicalIncrementArtifact",
    "IncrementMetadata",
    "NeedsClarificationChoice",
    "ProjectArtifactInventory",
    "ResolvedExistingIncrement",
    "RoadmapMetadata",
    "SelectExistingChoice",
    "parse_acquisition_choice",
    "parse_artifact_metadata",
    "resolve_existing_choice",
]

_MAX_SLUG_LENGTH = 48
_MAX_BOOTSTRAP_BODY_BYTES = 1024 * 1024
_SLUG_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_INCREMENT_ID_RE = re.compile(r"I[0-9]{2,}\Z")
_CANONICAL_INCREMENT_PATH_RE = re.compile(
    r"worklogs/(?P<project_slug>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)/increments/"
    r"increment-(?P<sequence>[0-9]{2,})-(?P<increment_slug>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)\.md\Z"
)
_ROADMAP_PATH_RE = re.compile(r"worklogs/(?P<project_slug>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)/roadmap\.md\Z")


@dataclass(frozen=True, slots=True)
class SelectExistingChoice:
    """Select an existing increment only by its stable project/increment IDs."""

    project_slug: str
    increment_id: str
    kind: Literal["SELECT_EXISTING"] = "SELECT_EXISTING"


@dataclass(frozen=True, slots=True)
class BootstrapNewProjectChoice:
    """Submit prose for a controller-rendered, fixed three-file project bundle."""

    project_slug: str
    increment_slug: str
    roadmap_body: str
    increment_body: str
    kind: Literal["BOOTSTRAP_NEW_PROJECT"] = "BOOTSTRAP_NEW_PROJECT"


@dataclass(frozen=True, slots=True)
class NeedsClarificationChoice:
    """Return one closed clarification reason without authorizing a mutation."""

    reason: Literal["AMBIGUOUS_PROJECT", "MISSING_CONTEXT", "UNKNOWN_INCREMENT"]
    kind: Literal["NEEDS_CLARIFICATION"] = "NEEDS_CLARIFICATION"


@dataclass(frozen=True, slots=True)
class RoadmapMetadata:
    """Validated flat controller metadata from one canonical roadmap."""

    roadmap_id: str
    slug: str
    created: str
    status: Literal["IN PROGRESS", "DONE"]
    active_increment: str
    supersedes: str | None


@dataclass(frozen=True, slots=True)
class IncrementMetadata:
    """Validated flat controller metadata from one canonical increment."""

    increment_id: str
    roadmap_id: str
    status: Literal["OUTLINED", "READY", "IN PROGRESS", "SHIPPED"]
    slices: int
    shipped: str


@dataclass(frozen=True, slots=True)
class CanonicalIncrementArtifact:
    """One increment path and bytes supplied by a trusted workspace inventory."""

    relative_path: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ProjectArtifactInventory:
    """One project roadmap and its canonical increment files from a pinned view."""

    roadmap_path: str
    roadmap_content: bytes
    increments: tuple[CanonicalIncrementArtifact, ...]


@dataclass(frozen=True, slots=True)
class ResolvedExistingIncrement:
    """Unique selected path, immutable plan snapshot and cross-checked metadata."""

    snapshot: PlanSnapshot
    roadmap: RoadmapMetadata
    increment: IncrementMetadata


AcquisitionChoice: TypeAlias = SelectExistingChoice | BootstrapNewProjectChoice | NeedsClarificationChoice  # noqa: UP040


class AcquisitionChoiceError(ValueError):
    """Sanitized closed diagnostic; never includes model-authored text."""

    def __init__(
        self,
        validator: Literal["selection", "bootstrap"],
        rule: Literal["choice-missing", "choice-malformed", "invalid-body", "too-large"],
    ) -> None:
        self.validator = validator
        self.rule = rule
        super().__init__(f"invalid acquisition choice: {validator}/{rule}")


class AcquisitionMetadataError(ValueError):
    """Sanitized metadata refusal that never includes source text or YAML errors."""

    def __init__(self) -> None:
        self.rule: Literal["invalid-metadata"] = "invalid-metadata"
        super().__init__("invalid acquisition metadata")


class _MalformedChoiceError(ValueError):
    """Internal JSON decoding failure that maps to the closed choice rule."""


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise _MalformedChoiceError
        value[key] = item
    return value


def _reject_json_constant(_value: str) -> None:
    raise _MalformedChoiceError


def _malformed() -> AcquisitionChoiceError:
    return AcquisitionChoiceError("selection", "choice-malformed")


def _decode_choice(final_text: object) -> dict[str, object]:
    if not isinstance(final_text, str):
        raise _malformed()
    if not final_text.strip():
        raise AcquisitionChoiceError("selection", "choice-missing")
    try:
        final_text.encode("utf-8", errors="strict")
        value = json.loads(
            final_text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeEncodeError, json.JSONDecodeError, _MalformedChoiceError, RecursionError, ValueError):
        raise _malformed() from None
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise _malformed()
    return value


def _valid_slug(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and len(value) <= _MAX_SLUG_LENGTH and _SLUG_RE.fullmatch(value) is not None


def _valid_body(value: object) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise AcquisitionChoiceError("bootstrap", "invalid-body")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise AcquisitionChoiceError("bootstrap", "invalid-body") from error
    if len(encoded) > _MAX_BOOTSTRAP_BODY_BYTES:
        raise AcquisitionChoiceError("bootstrap", "too-large")
    return value


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader variant that refuses duplicate and non-string mapping keys."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        if not isinstance(node, MappingNode):
            raise AcquisitionMetadataError
        result: dict[Hashable, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise AcquisitionMetadataError
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _frontmatter_yaml(content: bytes | str) -> str:
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise AcquisitionMetadataError from error
    elif isinstance(content, str):
        text = content
        try:
            text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise AcquisitionMetadataError from error
    else:
        raise AcquisitionMetadataError

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise AcquisitionMetadataError
    closing = next((index for index, line in enumerate(lines[1:], start=1) if line.rstrip("\r\n") == "---"), None)
    if closing is None:
        raise AcquisitionMetadataError
    frontmatter = "".join(lines[: closing + 1])
    try:
        if len(frontmatter.encode("utf-8", errors="strict")) > 4096:
            raise AcquisitionMetadataError
    except UnicodeEncodeError as error:
        raise AcquisitionMetadataError from error
    return "".join(lines[1:closing])


def _load_flat_metadata(yaml_text: str) -> dict[str, object]:
    try:
        for token in yaml.scan(yaml_text, Loader=yaml.SafeLoader):
            if isinstance(token, (AnchorToken, AliasToken)):
                raise AcquisitionMetadataError
        loader = _UniqueKeyLoader(yaml_text)
        try:
            parsed = loader.get_single_data()
        finally:
            loader.dispose()
    except AcquisitionMetadataError:
        raise
    except (yaml.YAMLError, RecursionError, ValueError):
        raise AcquisitionMetadataError from None
    if not isinstance(parsed, Mapping):
        raise AcquisitionMetadataError
    values = dict(parsed)
    if any(isinstance(value, (dict, list, tuple, set)) or value is None for value in values.values()):
        raise AcquisitionMetadataError
    return values


def _require_metadata_keys(
    values: dict[str, object], required: frozenset[str], optional: frozenset[str] = frozenset()
) -> None:
    if not required <= values.keys() or values.keys() - required - optional:
        raise AcquisitionMetadataError


def _metadata_string(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise AcquisitionMetadataError
    return value


def _metadata_date(value: object) -> str:
    if type(value) is date:
        return value.isoformat()
    if not isinstance(value, str):
        raise AcquisitionMetadataError
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise AcquisitionMetadataError from error
    if parsed.isoformat() != value:
        raise AcquisitionMetadataError
    return value


def _parse_roadmap_metadata(values: dict[str, object]) -> RoadmapMetadata:
    required = frozenset({"Roadmap-ID", "slug", "created", "status", "active-increment"})
    _require_metadata_keys(values, required, frozenset({"supersedes"}))
    roadmap_id = _metadata_string(values["Roadmap-ID"])
    slug = _metadata_string(values["slug"])
    status = values["status"]
    active_increment = values["active-increment"]
    supersedes = values.get("supersedes")
    if (
        re.fullmatch(r"RM-[a-z][a-z0-9]*(?:-[a-z0-9]+)*", roadmap_id) is None
        or not _valid_slug(slug)
        or status not in {"IN PROGRESS", "DONE"}
        or not isinstance(active_increment, str)
        or _INCREMENT_ID_RE.fullmatch(active_increment) is None
        or (supersedes is not None and (not isinstance(supersedes, str) or not supersedes))
    ):
        raise AcquisitionMetadataError
    if status == "IN PROGRESS":
        roadmap_status: Literal["IN PROGRESS", "DONE"] = "IN PROGRESS"
    else:
        roadmap_status = "DONE"
    return RoadmapMetadata(
        roadmap_id=roadmap_id,
        slug=slug,
        created=_metadata_date(values["created"]),
        status=roadmap_status,
        active_increment=active_increment,
        supersedes=supersedes,
    )


def _parse_increment_metadata(values: dict[str, object]) -> IncrementMetadata:
    required = frozenset({"Increment-ID", "Roadmap-ID", "status", "slices", "shipped"})
    _require_metadata_keys(values, required)
    increment_id = _metadata_string(values["Increment-ID"])
    roadmap_id = _metadata_string(values["Roadmap-ID"])
    status = values["status"]
    slices = values["slices"]
    shipped = values["shipped"]
    if (
        re.fullmatch(re.escape(roadmap_id) + r"-I[0-9]{2,}", increment_id) is None
        or re.fullmatch(r"RM-[a-z][a-z0-9]*(?:-[a-z0-9]+)*", roadmap_id) is None
        or status not in {"OUTLINED", "READY", "IN PROGRESS", "SHIPPED"}
        or type(slices) is not int
        or not 1 <= slices <= 7
        or not isinstance(shipped, str)
    ):
        raise AcquisitionMetadataError
    if status == "OUTLINED":
        increment_status: Literal["OUTLINED", "READY", "IN PROGRESS", "SHIPPED"] = "OUTLINED"
    elif status == "READY":
        increment_status = "READY"
    elif status == "IN PROGRESS":
        increment_status = "IN PROGRESS"
    else:
        increment_status = "SHIPPED"
    return IncrementMetadata(increment_id, roadmap_id, increment_status, slices, shipped)


def parse_artifact_metadata(
    content: bytes | str, *, kind: Literal["roadmap", "increment"]
) -> RoadmapMetadata | IncrementMetadata:
    """Strictly parse one canonical roadmap/increment frontmatter block.

    YAML is safe-loaded as a single flat scalar mapping. Anchors, aliases,
    duplicate/non-string keys, custom tags, nested values, extra metadata and
    frontmatter above four KiB all fail with one closed error.
    """
    values = _load_flat_metadata(_frontmatter_yaml(content))
    if kind == "roadmap":
        return _parse_roadmap_metadata(values)
    if kind == "increment":
        return _parse_increment_metadata(values)
    raise AcquisitionMetadataError


def _matching_project_inventories(
    choice: SelectExistingChoice, inventory: Iterable[ProjectArtifactInventory]
) -> list[ProjectArtifactInventory]:
    matches: list[ProjectArtifactInventory] = []
    if (
        not _valid_slug(choice.project_slug)
        or not isinstance(choice.increment_id, str)
        or _INCREMENT_ID_RE.fullmatch(choice.increment_id) is None
    ):
        raise AcquisitionMetadataError
    for project in inventory:
        if (
            not isinstance(project, ProjectArtifactInventory)
            or not isinstance(project.roadmap_path, str)
            or not isinstance(project.roadmap_content, bytes)
            or not isinstance(project.increments, tuple)
        ):
            raise AcquisitionMetadataError
        path_match = _ROADMAP_PATH_RE.fullmatch(project.roadmap_path)
        if path_match is None:
            raise AcquisitionMetadataError
        project_slug = path_match.group("project_slug")
        if not _valid_slug(project_slug):
            raise AcquisitionMetadataError
        if project_slug == choice.project_slug:
            matches.append(project)
    return matches


def _parse_inventory_roadmap(project: ProjectArtifactInventory, project_slug: str) -> RoadmapMetadata:
    if not isinstance(project.roadmap_content, bytes):
        raise AcquisitionMetadataError
    roadmap = parse_artifact_metadata(project.roadmap_content, kind="roadmap")
    if not isinstance(roadmap, RoadmapMetadata) or roadmap.slug != project_slug:
        raise AcquisitionMetadataError
    return roadmap


def _parse_inventory_increment(
    artifact: CanonicalIncrementArtifact, project_slug: str, roadmap: RoadmapMetadata
) -> IncrementMetadata:
    if (
        not isinstance(artifact, CanonicalIncrementArtifact)
        or not isinstance(artifact.relative_path, str)
        or not isinstance(artifact.content, bytes)
    ):
        raise AcquisitionMetadataError
    path_match = _CANONICAL_INCREMENT_PATH_RE.fullmatch(artifact.relative_path)
    if path_match is None or path_match.group("project_slug") != project_slug:
        raise AcquisitionMetadataError
    if not _valid_slug(path_match.group("increment_slug")):
        raise AcquisitionMetadataError
    increment = parse_artifact_metadata(artifact.content, kind="increment")
    if not isinstance(increment, IncrementMetadata) or increment.roadmap_id != roadmap.roadmap_id:
        raise AcquisitionMetadataError
    id_match = re.fullmatch(re.escape(roadmap.roadmap_id) + r"-I([0-9]{2,})", increment.increment_id)
    if id_match is None or id_match.group(1) != path_match.group("sequence"):
        raise AcquisitionMetadataError
    return increment


def resolve_existing_choice(
    choice: SelectExistingChoice,
    inventory: Iterable[ProjectArtifactInventory],
) -> ResolvedExistingIncrement | NeedsClarificationChoice:
    """Resolve a stable project/increment pair over a trusted pinned-view inventory.

    This pure resolver validates canonical path/metadata linkage; the caller is
    responsible for producing the inventory from regular files in its authorized
    view. It never opens paths, scans the host filesystem or infers IDs from
    slugs.
    """
    if not isinstance(choice, SelectExistingChoice):
        raise AcquisitionMetadataError
    project_matches = _matching_project_inventories(choice, inventory)
    if not project_matches:
        return NeedsClarificationChoice("MISSING_CONTEXT")
    if len(project_matches) != 1:
        return NeedsClarificationChoice("AMBIGUOUS_PROJECT")

    project = project_matches[0]
    roadmap = _parse_inventory_roadmap(project, choice.project_slug)
    increment_matches = [
        (artifact, _parse_inventory_increment(artifact, choice.project_slug, roadmap))
        for artifact in project.increments
    ]
    increment_matches = [
        pair for pair in increment_matches if pair[1].increment_id == f"{roadmap.roadmap_id}-{choice.increment_id}"
    ]
    if len(increment_matches) > 1:
        return NeedsClarificationChoice("AMBIGUOUS_PROJECT")
    if not increment_matches:
        return NeedsClarificationChoice("UNKNOWN_INCREMENT")

    artifact, increment = increment_matches[0]
    if (
        roadmap.status != "IN PROGRESS"
        or increment.status != "IN PROGRESS"
        or roadmap.active_increment != choice.increment_id
    ):
        return NeedsClarificationChoice("UNKNOWN_INCREMENT")
    snapshot = snapshot_from_bytes(artifact.relative_path, artifact.content, source_kind="EXISTING_SELECTION")
    return ResolvedExistingIncrement(snapshot=snapshot, roadmap=roadmap, increment=increment)


def _parse_existing_choice(value: dict[str, object]) -> SelectExistingChoice:
    if set(value) != {"kind", "project_slug", "increment_id"}:
        raise _malformed()
    project_slug, increment_id = value["project_slug"], value["increment_id"]
    if (
        not _valid_slug(project_slug)
        or not isinstance(increment_id, str)
        or _INCREMENT_ID_RE.fullmatch(increment_id) is None
    ):
        raise _malformed()
    return SelectExistingChoice(project_slug, increment_id)


def _parse_bootstrap_choice(value: dict[str, object]) -> BootstrapNewProjectChoice:
    if set(value) != {"kind", "project_slug", "increment_slug", "roadmap_body", "increment_body"}:
        raise _malformed()
    project_slug, increment_slug = value["project_slug"], value["increment_slug"]
    if not _valid_slug(project_slug) or not _valid_slug(increment_slug):
        raise _malformed()
    return BootstrapNewProjectChoice(
        project_slug=project_slug,
        increment_slug=increment_slug,
        roadmap_body=_valid_body(value["roadmap_body"]),
        increment_body=_valid_body(value["increment_body"]),
    )


def _parse_clarification_choice(value: dict[str, object]) -> NeedsClarificationChoice:
    if set(value) != {"kind", "reason"}:
        raise _malformed()
    reason = value["reason"]
    if reason == "AMBIGUOUS_PROJECT":
        return NeedsClarificationChoice("AMBIGUOUS_PROJECT")
    if reason == "MISSING_CONTEXT":
        return NeedsClarificationChoice("MISSING_CONTEXT")
    if reason == "UNKNOWN_INCREMENT":
        return NeedsClarificationChoice("UNKNOWN_INCREMENT")
    raise _malformed()


def parse_acquisition_choice(final_text: object) -> AcquisitionChoice:
    """Parse one exact Q60 choice from a real initial planner's final text.

    Empty final text is a missing choice. Every non-empty malformed shape,
    duplicate/unknown key, markdown wrapper, extra prose, invalid ID or JSON
    constant is a closed ``selection/choice-malformed`` refusal. Bootstrap
    bodies additionally require strict UTF-8 encodability and a one-MiB byte
    ceiling before the renderer performs its stricter final-file/bundle checks.
    """
    value = _decode_choice(final_text)
    kind = value["kind"]
    if kind == "SELECT_EXISTING":
        return _parse_existing_choice(value)
    if kind == "BOOTSTRAP_NEW_PROJECT":
        return _parse_bootstrap_choice(value)
    if kind == "NEEDS_CLARIFICATION":
        return _parse_clarification_choice(value)
    raise _malformed()
