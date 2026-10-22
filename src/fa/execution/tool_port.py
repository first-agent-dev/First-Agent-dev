"""Authority-backed implementation of the file-tool workspace port (E264).

One adapter owns everything the tool layer must not know: the peer/namespace
identity, the exact admitted ``ViewRef`` and capability, the per-call deadline and
the mapping from supervisor refusals to the port's closed codes. Every call goes
through ``WorkspaceAuthority.read_file``/``write_file``, so the tools inherit the
rooted descriptor IO, the byte bounds and the optimistic-concurrency write that
the substrate already implements — no second write path and no host fallback.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from fa.execution.protocol import MAX_TEXT_BYTES
from fa.execution.supervisor import PeerIdentity, SupervisorError
from fa.execution.types import ExecutionContractError, NamespaceRef, ViewRef
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.tools.workspace_port import PORT_READ_MAX_BYTES, PortRead, PortWrite, WorkspacePortError

#: Supervisor refusal codes translated into the port vocabulary. Anything not
#: listed is a substrate failure: the tool must report it as unavailable rather
#: than as a path or policy refusal the model could retry against.
_DENIED = frozenset(
    {
        "PATH_DENIED",
        "UNAUTHORIZED",
        "EXECUTION_UNKNOWN",
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

    def read_file(self, path: str, *, max_bytes: int = PORT_READ_MAX_BYTES) -> PortRead:
        if type(max_bytes) is not int or max_bytes < 1:
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
                offset_bytes=0,
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
    code = error.code
    if code in _STALE:
        return "stale"
    if code in _DENIED:
        return "denied"
    if code in _INPUT:
        return "input_policy"
    return "unavailable"


__all__ = ["AuthorityWorkspacePort"]
