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
from uuid import uuid4

from fa.execution.client import (
    ExecutionClient,
    ExecutionRejectedError,
    ExecutionUnavailableError,
    ExecutionUncertainError,
)
from fa.execution.protocol import MAX_TEXT_BYTES
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import Access, ExecutionContractError, GrantReply, NamespaceRef, Operation, ViewRef
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.tools.workspace_port import PORT_READ_MAX_BYTES, PortRead, PortWrite, WorkspacePortError

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


class AuthorityWorkspacePort:
    """Bind one admitted view and translate its refusals into port codes."""

    __slots__ = ("_authority", "_cache_dir", "_capability", "_deadline_factory", "_namespace", "_peer", "_view_ref")

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
    ) -> None:
        if not isinstance(authority, WorkspaceAuthority):
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

    @property
    def cache_dir(self) -> Path | None:
        """The view's private cache home (``ViewInputs.cache``), supplied by the composition."""
        return self._cache_dir

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

    __slots__ = ("_cache_dir", "_client", "_grant", "_namespace", "_view")

    def __init__(
        self,
        client: ExecutionClient,
        *,
        namespace: NamespaceRef,
        view: ViewRef,
        grant: GrantReply,
        cache_dir: Path | None = None,
    ) -> None:
        if not isinstance(client, ExecutionClient):
            raise ExecutionContractError
        if not isinstance(namespace, NamespaceRef) or not isinstance(view, ViewRef):
            raise ExecutionContractError
        if not isinstance(grant, GrantReply) or grant.view_ref != view:
            raise ExecutionContractError  # A grant for another view authorizes nothing here.
        if cache_dir is not None and not isinstance(cache_dir, Path):
            raise ExecutionContractError
        self._client = client
        self._namespace = namespace
        self._view = view
        self._grant = grant
        self._cache_dir = cache_dir

    @property
    def cache_dir(self) -> Path | None:
        """The view's private cache home, supplied by the composition (``None`` = no home)."""
        return self._cache_dir

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
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
                view=self._view,
                grant=self._grant,
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

    def write_file(self, path: str, content: str, *, expected_sha256: str | None = None) -> PortWrite:
        if self._view.access is not Access.WRITE:
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
                view=self._view,
                grant=self._grant,
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


__all__ = ["AuthorityWorkspacePort", "ClientWorkspacePort"]
