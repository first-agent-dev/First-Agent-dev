"""Bounded canonical artifact inventory over one authorized workspace port.

The inventory producer never accepts a host ``Path``. It obtains exact direct
child metadata from the view-bound execution port, then reads each candidate
through that same port so names and bytes belong to one immutable READ view.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from fa.inner_loop.managed_acquisition import CanonicalIncrementArtifact, ProjectArtifactInventory, _valid_slug
from fa.inner_loop.tools.workspace_port import PortProjectArtifactListing, WorkspacePort, WorkspacePortError

__all__ = ["AcquisitionInventoryError", "inventory_project_artifacts"]

_MAX_ARTIFACT_BYTES = 1024 * 1024
_MAX_INCREMENT_FILES = 64
_MAX_INVENTORY_BYTES = 8 * 1024 * 1024
_CANONICAL_INCREMENT_NAME_RE = re.compile(r"increment-[0-9]{2,}-.+\.md\Z")


class AcquisitionInventoryError(ValueError):
    """Sanitized refusal for incomplete, unsafe, or oversized inventory reads."""

    def __init__(self, rule: Literal["unavailable", "unsafe-entry", "too-large", "too-many"]) -> None:
        self.rule = rule
        super().__init__(f"acquisition inventory unavailable: {rule}")


def _port_error(error: WorkspacePortError) -> AcquisitionInventoryError:
    if error.code == "unavailable":
        rule: Literal["unavailable", "unsafe-entry", "too-large", "too-many"] = "unavailable"
    elif error.code == "input_policy":
        rule = "too-many"
    else:
        rule = "unsafe-entry"
    return AcquisitionInventoryError(rule)


def _read_file(workspace_view: WorkspacePort, relative_path: str) -> bytes:
    try:
        result = workspace_view.read_file(relative_path, offset_bytes=0, max_bytes=_MAX_ARTIFACT_BYTES)
    except WorkspacePortError as error:
        raise _port_error(error) from None
    if not result.eof:
        raise AcquisitionInventoryError("too-large")
    try:
        content = result.content.encode("utf-8")
    except UnicodeError:
        raise AcquisitionInventoryError("unsafe-entry") from None
    if len(content) > _MAX_ARTIFACT_BYTES or hashlib.sha256(content).hexdigest() != result.sha256:
        raise AcquisitionInventoryError("unsafe-entry")
    return content


def _validate_listing(listing: PortProjectArtifactListing) -> None:
    if not isinstance(listing, PortProjectArtifactListing):
        raise AcquisitionInventoryError("unsafe-entry")
    if listing.project_kind == "missing":
        if listing.roadmap_kind != "missing" or listing.increments_kind != "missing" or listing.entries:
            raise AcquisitionInventoryError("unsafe-entry")
        return
    if listing.project_kind != "directory":
        raise AcquisitionInventoryError("unsafe-entry")
    if listing.roadmap_kind not in {"missing", "file"}:
        raise AcquisitionInventoryError("unsafe-entry")
    if listing.increments_kind not in {"missing", "directory"}:
        raise AcquisitionInventoryError("unsafe-entry")
    if listing.increments_kind != "directory" and listing.entries:
        raise AcquisitionInventoryError("unsafe-entry")
    if len(listing.entries) > _MAX_INCREMENT_FILES:
        raise AcquisitionInventoryError("too-many")


def inventory_project_artifacts(workspace_view: WorkspacePort, project_slug: str) -> ProjectArtifactInventory | None:
    """Read one selected project's roadmap and canonical increments fail-closed.

    ``workspace_view`` is a bound managed port, not a filesystem path. ``None``
    means the project or canonical roadmap is absent; malformed, unsafe,
    oversized, or unavailable data raises a sanitized inventory refusal.
    """
    if not _valid_slug(project_slug):
        raise AcquisitionInventoryError("unsafe-entry")
    try:
        listing = workspace_view.list_project_artifacts(project_slug)
    except WorkspacePortError as error:
        raise _port_error(error) from None
    _validate_listing(listing)
    if listing.project_kind == "missing" or listing.roadmap_kind == "missing":
        return None

    roadmap_path = f"worklogs/{project_slug}/roadmap.md"
    roadmap_content = _read_file(workspace_view, roadmap_path)
    total_bytes = len(roadmap_content)
    if total_bytes > _MAX_INVENTORY_BYTES:
        raise AcquisitionInventoryError("too-large")

    canonical_entries = [entry for entry in listing.entries if _CANONICAL_INCREMENT_NAME_RE.fullmatch(entry.name)]
    if len(canonical_entries) > _MAX_INCREMENT_FILES:
        raise AcquisitionInventoryError("too-many")
    if any(entry.kind != "file" for entry in canonical_entries):
        raise AcquisitionInventoryError("unsafe-entry")

    increments: list[CanonicalIncrementArtifact] = []
    for entry in canonical_entries:
        relative_path = f"worklogs/{project_slug}/increments/{entry.name}"
        content = _read_file(workspace_view, relative_path)
        total_bytes += len(content)
        if total_bytes > _MAX_INVENTORY_BYTES:
            raise AcquisitionInventoryError("too-large")
        increments.append(CanonicalIncrementArtifact(relative_path, content))

    return ProjectArtifactInventory(roadmap_path, roadmap_content, tuple(increments))
