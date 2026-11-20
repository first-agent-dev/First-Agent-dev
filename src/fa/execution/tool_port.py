"""The file-tool workspace port over its two transports (E264, SLICE4 STEP2a).

One adapter owns everything the tool layer must not know: the peer/namespace
identity, the exact admitted ``ViewRef`` and capability, the per-call deadline and
the mapping from refusals to the port's closed codes. The same behaviour is
supplied twice, because the authority is reachable twice:

* ``AuthorityWorkspacePort`` calls ``WorkspaceAuthority`` in process — the local
  bank's transport, and the only one that can run where the authority lives.
* ``ClientWorkspacePort`` speaks the supervisor wire through ``ExecutionClient``,
  for the controller, which holds no authority after E277.

Both refuse before the first round trip what the substrate would refuse, keep the
same byte bounds, and pass ``expected_sha256`` through instead of comparing it: only
the authority can compare a precondition against the bytes it actually holds.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
)
from fa.execution.protocol import MAX_TEXT_BYTES
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import Access, ExecutionContractError, GrantReply, NamespaceRef, Operation, ViewPurpose, ViewRef
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.plan_admission import PlanRef
from fa.inner_loop.tools.workspace_port import (
    PORT_READ_MAX_BYTES,
    PortDirectoryEntry,
    PortProjectArtifactListing,
    PortProjectNames,
    PortRead,
    PortWrite,
    WorkspacePortError,
)

#: Supervisor refusal codes translated into the port vocabulary. Anything not
#: listed is a substrate failure: the tool must report it as unavailable rather
#: than as a path or policy refusal the model could retry against.
_DENIED = frozenset(
    {
        "PATH_DENIED",
        "UNAUTHORIZED",
        "ADMISSION_CLOSED",
        "GRANT_REVOKED",
        "STALE_GRANT",
        "PERMISSION_DENIED",
    }
)
_STALE = frozenset({"STALE_REVISION"})
_INPUT = frozenset({"INPUT_POLICY", "INVALID_REQUEST", "TOO_LARGE", "NOT_TEXT"})
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _project_names(projects: Any, incomplete: Any) -> PortProjectNames:
    """Build the port's names type from an already-projected reply.

    Two callers hand this two different, equally legitimate projections: the
    authority returns wire rows (``{"project_slug": ...}``), the client returns
    plain strings. Accept exactly those two shapes and refuse everything else --
    coercing an unexpected shape would put a reply-derived string into the
    model's candidate list.
    """
    try:

        def names(raw: Any, *, rows: bool) -> tuple[str, ...]:
            if type(raw) is not list:
                raise WorkspacePortError("invalid_request")
            if rows:
                return tuple(item["project_slug"] for item in raw)
            return tuple(raw)

        projects_rows = type(projects) is list and bool(projects) and type(projects[0]) is dict
        return PortProjectNames(
            projects=names(projects, rows=projects_rows),
            incomplete=names(incomplete, rows=False),
        )
    except (KeyError, TypeError, WorkspacePortError):
        raise WorkspacePortError("invalid_request") from None


def _project_listing(result: dict[str, Any]) -> PortProjectArtifactListing:
    try:
        raw_entries = result["entries"]
        if type(raw_entries) is not list:
            raise WorkspacePortError("invalid_request")
        entries = tuple(PortDirectoryEntry(name=item["name"], kind=item["kind"]) for item in raw_entries)
        return PortProjectArtifactListing(
            project_kind=result["project_kind"],
            roadmap_kind=result["roadmap_kind"],
            increments_kind=result["increments_kind"],
            entries=entries,
        )
    except (KeyError, TypeError, WorkspacePortError):
        raise WorkspacePortError("invalid_request") from None


class AuthorityWorkspacePort:
    """Bind one admitted view and translate its refusals into port codes."""

    __slots__ = (
        "_authority",
        "_buffer_label",
        "_cache_dir",
        "_capability",
        "_deadline_factory",
        "_namespace",
        "_peer",
        "_view_ref",
    )

    def __init__(
        self,
        authority: WorkspaceAuthority,
        *,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        view_ref: ViewRef,
        capability: str,
        deadline_factory: Callable[[], float],
        cache_dir: Path | None = None,
        plan_ref: PlanRef | None = None,
    ) -> None:
        if not isinstance(authority, WorkspaceAuthority):
            raise ExecutionContractError
        if plan_ref is not None and not isinstance(plan_ref, PlanRef):
            raise ExecutionContractError
        if not isinstance(peer, PeerIdentity) or not isinstance(namespace, NamespaceRef):
            raise ExecutionContractError
        if not isinstance(view_ref, ViewRef) or not isinstance(capability, str) or capability == "":
            raise ExecutionContractError
        if not callable(deadline_factory):
            raise ExecutionContractError
        if cache_dir is not None and not isinstance(cache_dir, Path):
            raise ExecutionContractError
        self._authority = authority
        self._peer = peer
        self._namespace = namespace
        self._view_ref = view_ref
        self._capability = capability
        self._deadline_factory = deadline_factory
        self._cache_dir = cache_dir
        # Same binding as the wire twin: the buffer's address is the plan
        # identity the view pinned, never a label the caller supplies.
        self._buffer_label: str | None = None
        if view_ref.purpose is ViewPurpose.CANDIDATE and isinstance(plan_ref, PlanRef):
            self._buffer_label = plan_ref.workspace_relative_path

    @property
    def cache_dir(self) -> Path | None:
        """The view's private cache home (``ViewInputs.cache``), supplied by the composition."""
        return self._cache_dir

    @property
    def base_revision_id(self) -> str:
        """Authority-pinned revision underlying this view; never read from the host tree."""
        return self._view_ref.base_revision

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        if type(offset_bytes) is not int or offset_bytes < 0 or type(max_bytes) is not int or max_bytes < 1:
            raise WorkspacePortError("invalid_request")
        if max_bytes > min(PORT_READ_MAX_BYTES, MAX_TEXT_BYTES):
            # One read is capped by the substrate; refuse rather than truncate.
            raise WorkspacePortError("input_policy")
        try:
            result = self._authority.read_file(
                self._peer,
                self._namespace,
                view_ref=self._view_ref,
                capability=self._capability,
                path=path,
                offset_bytes=offset_bytes,
                max_bytes=max_bytes,
                deadline=self._deadline_factory(),
            )
        except (SupervisorError, ExecutionContractError) as error:
            raise WorkspacePortError(_code(error)) from None
        return PortRead(content=result["content"], sha256=result["sha256"], eof=result["eof"])

    def list_project_names(self) -> PortProjectNames:
        if self._view_ref.access is not Access.READ or self._view_ref.purpose.value != "PROJECT":
            raise WorkspacePortError("denied")
        try:
            result = self._authority.list_projects(
                self._peer,
                self._namespace,
                view_ref=self._view_ref,
                capability=self._capability,
                deadline=self._deadline_factory(),
            )
        except (SupervisorError, ExecutionContractError) as error:
            raise WorkspacePortError(_code(error)) from None
        return _project_names(result.get("projects"), result.get("incomplete"))

    def list_project_artifacts(self, project_slug: str) -> PortProjectArtifactListing:
        if self._view_ref.access is not Access.READ or self._view_ref.purpose.value != "PROJECT":
            raise WorkspacePortError("denied")
        try:
            result = self._authority.list_project_artifacts(
                self._peer,
                self._namespace,
                view_ref=self._view_ref,
                capability=self._capability,
                project_slug=project_slug,
                deadline=self._deadline_factory(),
            )
        except (SupervisorError, ExecutionContractError) as error:
            raise WorkspacePortError(_code(error)) from None
        return _project_listing(result)

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        if not isinstance(content, str):
            raise WorkspacePortError("invalid_request")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None
        ):
            raise WorkspacePortError("invalid_request")
        try:
            result = self._authority.write_file(
                self._peer,
                self._namespace,
                view_ref=self._view_ref,
                capability=self._capability,
                path=path,
                content=content,
                expected_sha256=expected_sha256,
                deadline=self._deadline_factory(),
            )
        except (SupervisorError, ExecutionContractError) as error:
            raise WorkspacePortError(_code(error)) from None
        return PortWrite(sha256=result["sha256"], bytes=result["bytes"])

    def candidate_label(self) -> str:
        """The one label this view's candidate buffer answers to (in-process twin)."""
        if self._view_ref.purpose is not ViewPurpose.CANDIDATE or self._view_ref.access is not Access.READ:
            raise WorkspacePortError("denied")
        if self._buffer_label is None:
            raise WorkspacePortError("unavailable")
        return self._buffer_label

    def write_candidate(self, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        """Stage candidate bytes in process; same purpose gate as the wire twin."""
        if self._view_ref.purpose is not ViewPurpose.CANDIDATE or self._view_ref.access is not Access.READ:
            raise WorkspacePortError("denied")
        label = self._buffer_label
        if label is None:
            raise WorkspacePortError("unavailable")
        if not isinstance(content, str):
            raise WorkspacePortError("invalid_request")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None
        ):
            raise WorkspacePortError("invalid_request")
        try:
            result = self._authority.write_candidate(
                self._peer,
                self._namespace,
                view_ref=self._view_ref,
                capability=self._capability,
                path=label,
                content=content,
                expected_sha256=expected_sha256,
                deadline=self._deadline_factory(),
            )
        except (SupervisorError, ExecutionContractError) as error:
            raise WorkspacePortError(_code(error)) from None
        return PortWrite(sha256=result["sha256"], bytes=result["bytes"])

    def read_candidate(self, *, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        """Read the staged candidate buffer in process; same window contract."""
        if self._view_ref.purpose is not ViewPurpose.CANDIDATE or self._view_ref.access is not Access.READ:
            raise WorkspacePortError("denied")
        label = self._buffer_label
        if label is None:
            raise WorkspacePortError("unavailable")
        if type(max_bytes) is not int or max_bytes < 1:
            raise WorkspacePortError("invalid_request")
        if max_bytes > min(PORT_READ_MAX_BYTES, MAX_TEXT_BYTES):
            raise WorkspacePortError("input_policy")
        try:
            result = self._authority.read_candidate(
                self._peer,
                self._namespace,
                view_ref=self._view_ref,
                capability=self._capability,
                path=label,
                offset_bytes=0,
                max_bytes=max_bytes,
                deadline=self._deadline_factory(),
            )
        except (SupervisorError, ExecutionContractError) as error:
            raise WorkspacePortError(_code(error)) from None
        return PortRead(content=result["content"], sha256=result["sha256"], eof=result["eof"])


def _code(error: SupervisorError | ExecutionContractError) -> str:
    if isinstance(error, ExecutionContractError):
        return "invalid_request"
    return _code_name(error.code)


def _code_name(code: str) -> str:
    """One closed mapping from an authority code to the port vocabulary."""
    if code in _STALE:
        return "stale"
    if code in _DENIED:
        return "denied"
    if code in _INPUT:
        return "input_policy"
    return "unavailable"


def _client_code(error: BaseException) -> str:
    """Map a client refusal onto the same vocabulary, without inventing certainty.

    Uncertainty is ``unavailable`` and never ``denied``: a lost reply means the
    bytes may or may not have landed, and telling the model "refused" would invite
    exactly the retry a landed write must not get. A rejection carries the
    authority's own closed code, so one mapping serves both transports.
    """
    if isinstance(error, ExecutionContractError):
        return "invalid_request"
    if isinstance(error, (ExecutionUnavailableError, ExecutionUncertainError)):
        return "unavailable"
    return _code_name(str(getattr(error, "code", "")))


class ClientWorkspacePort:
    """The tool layer's view IO over the supervisor wire (SLICE4 STEP2a).

    The grant and the ``ViewRef`` are bound at construction and travel with every
    call, so a tool can never name a view of its own choosing, and a grant for
    another view is refused here rather than spent on a request the authority
    would deny. Each call is bounded by the client's own rpc timeout: a stage
    budget is added by the caller that has one, not assumed here.
    """

    __slots__ = (
        "_active",
        "_buffer_label",
        "_cache_dir",
        "_client",
        "_grant",
        "_namespace",
        "_purpose",
        "_view",
        "_workspace_id",
    )

    def __init__(
        self,
        client: ExecutionClient,
        *,
        namespace: NamespaceRef,
        view: ViewRef,
        grant: GrantReply,
        cache_dir: Path | None = None,
        plan_ref: PlanRef | None = None,
    ) -> None:
        if not isinstance(client, ExecutionClient):
            raise ExecutionContractError
        if plan_ref is not None and not isinstance(plan_ref, PlanRef):
            raise ExecutionContractError
        if not isinstance(namespace, NamespaceRef) or not isinstance(view, ViewRef):
            raise ExecutionContractError
        if not isinstance(grant, GrantReply) or grant.view_ref != view or view.owner_run_id != namespace.run_id:
            raise ExecutionContractError  # A grant for another view authorizes nothing here.
        if cache_dir is not None and not isinstance(cache_dir, Path):
            raise ExecutionContractError
        self._client = client
        self._namespace = namespace
        self._workspace_id = view.workspace_id
        self._purpose = view.purpose
        self._view: ViewRef | None = view
        self._grant: GrantReply | None = grant
        self._active = True
        self._cache_dir = cache_dir
        # S3P3: the staged-candidate buffer is one file per CANDIDATE view, and
        # its address is the plan identity the view already pinned (CT120). Held
        # here so a caller never supplies the label it is authorised by.
        self._buffer_label: str | None = None
        if view.purpose is ViewPurpose.CANDIDATE and isinstance(plan_ref, PlanRef):
            self._buffer_label = plan_ref.workspace_relative_path

    def suspend(self) -> None:
        """Disarm this binding before its managed view is published or handed off."""
        self._active = False
        self._grant = None
        self._view = None

    def rebind(self, *, namespace: NamespaceRef, view: ViewRef, grant: GrantReply) -> None:
        """Bind the same port to a newly admitted view of its original namespace."""
        if (
            not isinstance(namespace, NamespaceRef)
            or namespace != self._namespace
            or not isinstance(view, ViewRef)
            or not isinstance(grant, GrantReply)
            or grant.operation is not Operation.CREATE_VIEW
            or grant.view_ref != view
            or view.access is not Access.WRITE
            or view.workspace_id != self._workspace_id
            or view.owner_run_id != self._namespace.run_id
            or view.purpose is not self._purpose
        ):
            raise ExecutionContractError
        self._view = view
        self._grant = grant
        self._active = True

    def _require_active(self) -> tuple[ViewRef, GrantReply]:
        if not self._active or self._view is None or self._grant is None:
            raise WorkspacePortError("unavailable")
        return self._view, self._grant

    @property
    def cache_dir(self) -> Path | None:
        """The view's private cache home, supplied by the composition (``None`` = no home)."""
        return self._cache_dir

    @property
    def base_revision_id(self) -> str:
        """Authority-pinned revision underlying this view; never read from the host tree."""
        view, _grant = self._require_active()
        return view.base_revision

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        view, grant = self._require_active()
        if type(offset_bytes) is not int or offset_bytes < 0 or type(max_bytes) is not int or max_bytes < 1:
            raise WorkspacePortError("invalid_request")
        if max_bytes > min(PORT_READ_MAX_BYTES, MAX_TEXT_BYTES):
            # One read is capped by the substrate; refuse rather than truncate.
            raise WorkspacePortError("input_policy")
        try:
            result = self._client.request(
                Operation.READ_FILE,
                request_id=uuid4().hex,
                namespace=self._namespace,
                view=view,
                grant=grant,
                payload={"path": path, "offset_bytes": offset_bytes, "max_bytes": max_bytes},
                deadline=None,
            )
        except (
            ExecutionRejectedError,
            ExecutionUnavailableError,
            ExecutionUncertainError,
            ExecutionContractError,
        ) as error:
            raise WorkspacePortError(_client_code(error)) from None
        return PortRead(content=str(result["content"]), sha256=str(result["sha256"]), eof=bool(result["eof"]))

    def list_project_names(self) -> PortProjectNames:
        view, grant = self._require_active()
        if view.access is not Access.READ or view.purpose.value != "PROJECT":
            raise WorkspacePortError("denied")
        try:
            result = self._client.list_projects(self._namespace, view=view, grant=grant)
        except (
            ExecutionRejectedError,
            ExecutionUnavailableError,
            ExecutionUncertainError,
            ExecutionContractError,
        ) as error:
            raise WorkspacePortError(_client_code(error)) from None
        return _project_names(result.get("projects"), result.get("incomplete"))

    def list_project_artifacts(self, project_slug: str) -> PortProjectArtifactListing:
        view, grant = self._require_active()
        if view.access is not Access.READ or view.purpose.value != "PROJECT":
            raise WorkspacePortError("denied")
        try:
            result = self._client.list_project_artifacts(
                self._namespace,
                view=view,
                grant=grant,
                project_slug=project_slug,
            )
        except (
            ExecutionRejectedError,
            ExecutionUnavailableError,
            ExecutionUncertainError,
            ExecutionContractError,
        ) as error:
            raise WorkspacePortError(_client_code(error)) from None
        return _project_listing(result)

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        view, grant = self._require_active()
        if view.access is not Access.WRITE:
            # The view the authority minted has no write path at all (E259); saying so
            # here costs no round trip that could not have succeeded.
            raise WorkspacePortError("denied")
        if not isinstance(content, str):
            raise WorkspacePortError("invalid_request")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None
        ):
            raise WorkspacePortError("invalid_request")
        try:
            result = self._client.request(
                Operation.WRITE_FILE,
                request_id=uuid4().hex,
                namespace=self._namespace,
                view=view,
                grant=grant,
                payload={"path": path, "content": content, "expected_sha256": expected_sha256},
                deadline=None,
            )
        except (
            ExecutionRejectedError,
            ExecutionUnavailableError,
            ExecutionUncertainError,
            ExecutionContractError,
        ) as error:
            raise WorkspacePortError(_client_code(error)) from None
        return PortWrite(sha256=str(result["sha256"]), bytes=int(result["bytes"]))

    def candidate_label(self) -> str:
        """The one label this view's candidate buffer answers to.

        A staging address, not a host path: the authority compares it against the
        plan identity pinned into the view and refuses anything else
        (``workspace.py:2755``). Exposed so the composition can hand the model the
        same label the wire will demand, instead of inventing a second one.
        """
        view, _grant = self._require_active()
        if view.purpose is not ViewPurpose.CANDIDATE or view.access is not Access.READ:
            raise WorkspacePortError("denied")
        if self._buffer_label is None:
            raise WorkspacePortError("unavailable")
        return self._buffer_label

    def write_candidate(self, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        """Stage candidate bytes in this view's buffer.

        Deliberately NOT ``write_file``: the buffer is a purpose-bound operation
        on a READ view (E259), while ``write_file`` is general-purpose IO that
        must stay confined to ``Access.WRITE``. Keeping them apart is what stops
        the READ view from acquiring a write path to arbitrary project files.
        """
        view, grant = self._require_active()
        if view.purpose is not ViewPurpose.CANDIDATE or view.access is not Access.READ:
            raise WorkspacePortError("denied")
        label = self._buffer_label
        if label is None:
            raise WorkspacePortError("unavailable")
        if not isinstance(content, str):
            raise WorkspacePortError("invalid_request")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None
        ):
            raise WorkspacePortError("invalid_request")
        try:
            result = self._client.request(
                Operation.WRITE_FILE,
                request_id=uuid4().hex,
                namespace=self._namespace,
                view=view,
                grant=grant,
                payload={"path": label, "content": content, "expected_sha256": expected_sha256},
                deadline=None,
            )
        except (
            ExecutionRejectedError,
            ExecutionUnavailableError,
            ExecutionUncertainError,
            ExecutionContractError,
        ) as error:
            raise WorkspacePortError(_client_code(error)) from None
        return PortWrite(sha256=str(result["sha256"]), bytes=int(result["bytes"]))

    def read_candidate(self, *, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        """Read the staged candidate back through the same view it was written to.

        This is the managed read-back: the controller validates the buffer rather
        than a host copy, so the candidate never needs a canonical path to be
        valid. One window starting at zero is enough for a plan (``MAX_PLAN_BYTES``
        is far below the port cap) and the returned sha256 is over the WHOLE
        buffer, which is what a later CAS needs.
        """
        view, grant = self._require_active()
        if view.purpose is not ViewPurpose.CANDIDATE or view.access is not Access.READ:
            raise WorkspacePortError("denied")
        label = self._buffer_label
        if label is None:
            raise WorkspacePortError("unavailable")
        if type(max_bytes) is not int or max_bytes < 1:
            raise WorkspacePortError("invalid_request")
        if max_bytes > min(PORT_READ_MAX_BYTES, MAX_TEXT_BYTES):
            raise WorkspacePortError("input_policy")
        try:
            result = self._client.request(
                Operation.READ_FILE,
                request_id=uuid4().hex,
                namespace=self._namespace,
                view=view,
                grant=grant,
                payload={"path": label, "offset_bytes": 0, "max_bytes": max_bytes},
                deadline=None,
            )
        except (
            ExecutionRejectedError,
            ExecutionUnavailableError,
            ExecutionUncertainError,
            ExecutionContractError,
        ) as error:
            raise WorkspacePortError(_client_code(error)) from None
        return PortRead(content=str(result["content"]), sha256=str(result["sha256"]), eof=bool(result["eof"]))
