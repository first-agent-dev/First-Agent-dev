"""Single-attempt private-UDS client and managed BashExecutor, never host shell.

Not installed into the live controller until real authority/journal integration.
Local UUID allocation is not durable reservation; only the supervisor can attest
that. No transport failure here triggers a resend or replacement operation ID.
"""

from __future__ import annotations

import hashlib
import logging
import math
import socket
import stat
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import DeadlineConnection, decode_reply, decode_request, encode_json, read_frame, write_frame
from fa.execution.types import (
    Access,
    ExecutionContractError,
    ExecutionReceipt,
    GrantReply,
    JobState,
    NamespaceRef,
    Operation,
    OperationRef,
    ViewPurpose,
    ViewRef,
    _hex_id,
    _positive_integer,
)
from fa.inner_loop.plan_admission import PlanRef, PlanSnapshot
from fa.runtime.pty_pool import PtyResult


class ExecutionUnavailableError(RuntimeError):
    def __init__(self, *, operation_id: str | None = None) -> None:
        super().__init__("execution_unavailable")
        self.code = "BACKEND_UNAVAILABLE"
        self.operation_id = operation_id


class ExecutionUncertainError(RuntimeError):
    def __init__(self, operation_id: str | None, *, code: str = "EXECUTION_UNKNOWN") -> None:
        super().__init__("execution_unknown")
        self.operation_id = operation_id
        self.code = code


class ExecutionTimedOutError(ExecutionUncertainError):
    def __init__(self, receipt: ExecutionReceipt) -> None:
        super().__init__(receipt.operation_id)
        self.receipt = receipt


class ExecutionRejectedError(RuntimeError):
    def __init__(self, code: str, operation_id: str | None) -> None:
        super().__init__("execution_rejected")
        self.code = code
        self.operation_id = operation_id


def _connect_authenticated(connection: socket.socket, path: Path, server_uid: int) -> None:
    # Peer credentials after connect are authoritative even across a path
    # replacement race. A same-UID malicious server is inside the host TCB.
    parent = path.parent.stat(follow_symlinks=False)
    endpoint = path.stat(follow_symlinks=False)
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != server_uid
        or parent.st_mode & 0o022
        or not stat.S_ISSOCK(endpoint.st_mode)
        or endpoint.st_uid != server_uid
    ):
        raise ExecutionUnavailableError
    connection.connect(str(path))
    _, uid, _ = struct.unpack("3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
    if uid != server_uid:
        raise ExecutionUnavailableError


@dataclass(frozen=True)
class PlanPublication:
    """One candidate publication: the promoted ref, the revision, and whether it was a repeat.

    `already_published` is the authority's answer (CT117): true means the pinned
    plan was already the current bytes and no second revision was committed.
    """

    plan_ref: PlanRef
    revision_id: str
    already_published: bool


def _binding_identity(binding: object) -> tuple[NamespaceRef, str]:
    """Read the two identity fields a managed binding owns, and never infer others."""
    namespace = getattr(binding, "namespace", None)
    workspace_id = getattr(binding, "workspace_id", None)
    if not isinstance(namespace, NamespaceRef):
        raise ExecutionContractError
    _hex_id(workspace_id, "ws-")
    return namespace, workspace_id


def _plan_ref_dict(ref: PlanRef) -> dict[str, str]:
    """The wire shape of a plan identity; the only place it is spelled out."""
    if not isinstance(ref, PlanRef):
        raise ExecutionContractError
    return {
        "workspace_relative_path": ref.workspace_relative_path,
        "source_kind": ref.source_kind,
        "sha256": ref.sha256,
    }


def _grant(operation: Operation, result: dict[str, Any]) -> GrantReply:
    """The one place a grant reply becomes the typed grant a caller keeps (CT118)."""
    view_ref = result["view_ref"]
    return GrantReply(
        operation,
        result["capability"],
        None if view_ref is None else ViewRef.from_dict(view_ref),
        result.get("generation"),
        result.get("revision_id"),
    )


class ExecutionClient:
    def __init__(self, socket_path: Path, *, server_uid: int, rpc_timeout_ms: int) -> None:
        if type(server_uid) is not int or server_uid < 0:
            raise ExecutionContractError
        _positive_integer(rpc_timeout_ms)
        if not socket_path.is_absolute() or ".." in socket_path.parts:
            raise ExecutionContractError
        self._path = socket_path
        self._server_uid = server_uid
        self._timeout_ms = rpc_timeout_ms

    def _connect(self, connection: socket.socket) -> None:
        _connect_authenticated(connection, self._path, self._server_uid)

    def request(
        self,
        operation: Operation,
        *,
        request_id: str,
        namespace: NamespaceRef | None,
        view: ViewRef | None,
        grant: GrantReply | None,
        payload: dict[str, Any],
        deadline: float | None = None,
    ) -> dict[str, Any]:
        if grant is not None and not isinstance(grant, GrantReply):
            raise ExecutionContractError  # A raw string is not a grant a caller may pass on.
        raw = encode_json(
            {
                "protocol_version": 1,
                "request_id": request_id,
                "op": operation.value,
                "namespace": None if namespace is None else namespace.to_dict(),
                "view_ref": None if view is None else view.to_dict(),
                "capability": None if grant is None else grant.to_wire_capability(),
                "payload": payload,
            }
        )
        decode_request(raw)  # Reject caller bugs BEFORE connecting/sending.
        timeout_ms = self._timeout_ms
        if deadline is not None:
            if type(deadline) not in {int, float} or not math.isfinite(deadline):
                raise ExecutionContractError
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                raise ExecutionUnavailableError
            timeout_ms = min(timeout_ms, remaining_ms)
        attempted_send = False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                framed = DeadlineConnection(connection, timeout_ms=timeout_ms)
                connection.settimeout(framed.remaining())
                self._connect(connection)
                attempted_send = True  # sendall can lose a partial/completed write.
                write_frame(framed, raw)
                if operation is Operation.EXEC:
                    framed.add_execution_budget(payload["timeout_ms"])
                # The reader tolerates a reply written before an additive key existed;
                # the server's own self-check does not.
                response = decode_reply(
                    read_frame(framed), operation=operation, request_id=request_id, tolerate_legacy=True
                )
        except (OSError, ExecutionContractError):
            if attempted_send:
                raise ExecutionUncertainError("op-" + request_id) from None
            raise ExecutionUnavailableError from None
        if response["status"] == "ERROR":
            error = response["error"]
            if error["code"] in {"EXECUTION_UNKNOWN", "TERMINALITY_UNKNOWN", "DURABILITY_UNKNOWN", "CORRUPT_STATE"}:
                raise ExecutionUncertainError(error["operation_id"] or "op-" + request_id, code=error["code"])
            if error["code"] == "BACKEND_UNAVAILABLE":
                raise ExecutionUnavailableError(operation_id=error["operation_id"])
            raise ExecutionRejectedError(error["code"], error["operation_id"])
        return cast(dict[str, Any], response["result"])

    def publish_plan(
        self,
        binding: object,
        source: PlanSnapshot,
        candidate: PlanSnapshot,
        *,
        grant: GrantReply,
        deadline: float | None = None,
    ) -> PlanPublication:
        """Publish one validated candidate through a CANDIDATE view (CT116/CT118).

        `binding` is the run's execution identity — `namespace` and `workspace_id` —
        supplied by the managed composition (STEP8); this client infers neither.
        The source ref is pinned from `source`, so the model never supplies a target
        and candidate bytes travel only through the scoped WRITE_FILE. The CAS the
        PUBLISH carries is the base of the view the authority just minted, never a
        cached field: a concurrent commit cannot leave the pair stale. Every RPC is
        one-shot; a lost PUBLISH reply is not retried and never becomes a local write.
        """
        namespace, workspace_id = _binding_identity(binding)
        if not isinstance(grant, GrantReply) or grant.operation is not Operation.ACQUIRE_WRITER:
            raise ExecutionContractError
        if not isinstance(source, PlanSnapshot) or not isinstance(candidate, PlanSnapshot):
            raise ExecutionContractError
        raw = candidate.utf8_bytes
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != candidate.ref.sha256:
            raise ExecutionContractError
        plan_ref = _plan_ref_dict(source.ref)
        # CT120: the buffer's address is the plan's own canonical path, which the
        # authority already holds in `plan_ref`; it is a label, not a host path.
        buffer_label = source.ref.workspace_relative_path
        view: ViewRef | None = None
        view_grant: GrantReply | None = None
        uncertain = False
        try:
            created = self.request(
                Operation.CREATE_VIEW,
                request_id=uuid4().hex,
                namespace=namespace,
                view=None,
                grant=grant,
                payload={
                    "workspace_id": workspace_id,
                    # CANDIDATE may open on a null base (protocol.py:330): the
                    # authority names the base it mints, and PUBLISH CASes that one.
                    "base_revision": None,
                    "access": "READ",
                    "purpose": "CANDIDATE",
                    "candidate_scope": {"plan_ref": plan_ref},
                    "plan_ref": plan_ref,
                },
                deadline=deadline,
            )
            view = ViewRef.from_dict(created["view_ref"])
            view_grant = _grant(Operation.CREATE_VIEW, created)
            self.request(
                Operation.WRITE_FILE,
                request_id=uuid4().hex,
                namespace=namespace,
                view=view,
                grant=view_grant,
                payload={"path": buffer_label, "content": raw.decode("utf-8"), "expected_sha256": None},
                deadline=deadline,
            )
            stop_request_id = uuid4().hex
            stopped = self.request(
                Operation.STOP_VIEW,
                request_id=stop_request_id,
                namespace=namespace,
                view=view,
                grant=view_grant,
                payload={},
                deadline=deadline,
            )
            if stopped["terminal"] is not True:
                raise ExecutionUncertainError("op-" + stop_request_id, code="TERMINALITY_UNKNOWN")
            publish_request_id = uuid4().hex
            try:
                result = self.request(
                    Operation.PUBLISH,
                    request_id=publish_request_id,
                    namespace=namespace,
                    view=view,
                    grant=view_grant,
                    payload={"sealed_manifest_id": None, "expected_base_revision": view.base_revision},
                    deadline=deadline,
                )
            except ExecutionUncertainError:
                uncertain = True
                raise
            expected_ref = {**plan_ref, "sha256": hashlib.sha256(raw).hexdigest()}
            if result["plan_ref"] != expected_ref:
                uncertain = True
                raise ExecutionUncertainError("op-" + publish_request_id, code="DURABILITY_UNKNOWN")
            return PlanPublication(
                PlanRef(**expected_ref),
                str(result["revision_id"]),
                bool(result["already_published"]),
            )
        except ExecutionUncertainError:
            # The candidate view stays open: releasing it would assert that the
            # writer is settled, which is the one thing this client cannot prove.
            uncertain = True
            raise
        finally:
            if view is not None and view_grant is not None and not uncertain:
                self._release_view(namespace, view, view_grant, deadline)

    def open_view(
        self,
        binding: object,
        *,
        access: Access,
        purpose: ViewPurpose,
        base_revision: str | None,
        plan_ref: PlanRef | None = None,
        grant: GrantReply | None = None,
        deadline: float | None = None,
    ) -> GrantReply:
        """Open one purpose-bound view for this run and return the grant that owns it.

        ``base_revision`` is the caller's CAS precondition and is never inferred
        here: a caller that names bytes the authority no longer holds is refused
        with ``STALE_REVISION`` instead of being handed a newer view. The
        authority's closed purpose matrix decides what is legal
        (``workspace.py:1930``); this verb only carries it.

        One attempt, like every other request on this client: an uncertain
        CREATE_VIEW is reported, not retried, because a second attempt could
        open a second view against the same writer.
        """
        namespace, workspace_id = _binding_identity(binding)
        if not isinstance(access, Access) or not isinstance(purpose, ViewPurpose):
            raise ExecutionContractError
        if not isinstance(grant, GrantReply) or grant.operation is not Operation.ACQUIRE_WRITER:
            raise ExecutionContractError
        created = self.request(
            Operation.CREATE_VIEW,
            request_id=uuid4().hex,
            namespace=namespace,
            view=None,
            grant=grant,
            payload={
                "workspace_id": workspace_id,
                "base_revision": base_revision,
                "access": access.value,
                "purpose": purpose.value,
                "candidate_scope": None,
                "plan_ref": None if plan_ref is None else _plan_ref_dict(plan_ref),
            },
            deadline=deadline,
        )
        return _grant(Operation.CREATE_VIEW, created)

    def stop_view(
        self, namespace: NamespaceRef, *, view: ViewRef, grant: GrantReply, deadline: float | None = None
    ) -> bool:
        """End a view. ``True`` only when the authority proved it terminal.

        The two endings in the authority are different operations, so this verb
        follows the view's own access rather than guessing:

        * an EXECUTION view (WRITE) ends with ``STOP_VIEW``: irreversible closure,
          then one terminality verdict. ``RELEASE`` is not sent for it — the
          authority's release is the *reader pin* revocation
          (``workspace.py:1863``) and refuses a view that never held a pin.
        * a READ view additionally holds that pin, so the proved view is then
          released; a release whose answer was lost is an unproved end, while a
          refused one only says there is no pin left to revoke.

        A view that did not become terminal keeps its copy and stays owned: that
        is ``False``, which sends the caller to recovery instead of to a retry.
        """
        if not isinstance(namespace, NamespaceRef) or not isinstance(view, ViewRef):
            raise ExecutionContractError
        if not isinstance(grant, GrantReply) or grant.view_ref != view:
            raise ExecutionContractError  # A grant for another view authorizes nothing here.
        try:
            stopped = self.request(
                Operation.STOP_VIEW,
                request_id=uuid4().hex,
                namespace=namespace,
                view=view,
                grant=grant,
                payload={},
                deadline=deadline,
            )
            if stopped["terminal"] is not True:
                return False
            if view.access is Access.READ:
                self._release_view(namespace, view, grant, deadline, strict=True)
        except (ExecutionUncertainError, ExecutionUnavailableError, ExecutionRejectedError):
            return False
        return True

    def _release_view(
        self,
        namespace: NamespaceRef,
        view: ViewRef,
        grant: GrantReply,
        deadline: float | None,
        *,
        strict: bool = False,
    ) -> None:
        """Revoke a READ view's pin.

        ``strict`` is for the caller that must be told the truth, and the truth is
        the same distinction the rest of this client makes: an *indeterminate*
        release may have left the pin held, so it is raised; a *rejected* release is
        the authority saying it holds no such pin (``workspace.py:1875`` refuses a
        view that never held one), which leaves nothing to revoke. The best-effort
        caller keeps the difference visible in the log instead.
        """
        try:
            self.request(
                Operation.RELEASE,
                request_id=uuid4().hex,
                namespace=namespace,
                view=view,
                grant=grant,
                payload={},
                deadline=deadline,
            )
        except (ExecutionUncertainError, ExecutionUnavailableError):
            if strict:
                raise
            logging.getLogger(__name__).warning("candidate view cleanup was not confirmed")
        except ExecutionRejectedError:
            logging.getLogger(__name__).warning("candidate view cleanup was refused")


class ManagedBashExecutor:
    """All four BashExecutor methods, with a fixed trusted episode binding.

    The profile must be interactive to preserve stateful PTY semantics. A caller
    must supply current protected source/PlanRef metadata, never infer it from a
    worker response. This constructor does not authorize or create the view.
    """

    def __init__(
        self,
        client: ExecutionClient,
        *,
        namespace: NamespaceRef,
        view: ViewRef,
        grant: GrantReply,
        profile: ExecutionProfile,
        input_tree_sha256: str,
        plan_sha256: str | None,
        original_revision_id: str | None,
        controller_root: Path,
    ) -> None:
        if not isinstance(grant, GrantReply):
            raise ExecutionContractError
        if not profile.interactive or not controller_root.is_absolute() or ".." in controller_root.parts:
            raise ExecutionContractError
        self._client = client
        self._namespace = namespace
        self._view = view
        self._grant = grant
        self._profile = profile
        self._tree = input_tree_sha256
        self._plan = plan_sha256
        self._original_revision = original_revision_id
        self._root = controller_root

    def _request(self, operation: Operation, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
        return self._client.request(
            operation,
            request_id=request_id,
            namespace=self._namespace,
            view=self._view,
            grant=self._grant,
            payload=payload,
        )

    def _cwd(self, workdir: Path | None) -> str:
        if workdir is None:
            return "."
        try:
            return (workdir.relative_to(self._root) if workdir.is_absolute() else workdir).as_posix()
        except ValueError:
            raise ExecutionContractError from None

    def run(self, command: str, timeout: int = 30, workdir: Path | None = None, session_id: str = "main") -> PtyResult:
        _positive_integer(timeout)
        request_id = uuid4().hex
        return self._execute_once(command, timeout, workdir, session_id, request_id)

    # §execution-client-once: transport uncertainty never resends a shell command.
    def _execute_once(
        self, command: str, timeout: int, workdir: Path | None, session_id: str, request_id: str
    ) -> PtyResult:
        operation = OperationRef(
            "op-" + request_id, self._view.view_id, self._view.owner_run_id, self._view.generation, self._tree
        )
        result = self._request(
            Operation.EXEC,
            {
                "operation_id": operation.operation_id,
                "profile_id": self._profile.profile_id,
                "command": command,
                "cwd": self._cwd(workdir),
                "timeout_ms": min(timeout * 1000, self._profile.max_command_ms),
                "session_id": session_id,
            },
            request_id,
        )
        receipt = ExecutionReceipt.from_dict(result["receipt"])
        try:
            receipt.require_binding(
                operation=operation,
                namespace=self._namespace,
                view=self._view,
                profile_id=self._profile.profile_id,
                image_digest=self._profile.image_digest,
                revision_id=self._view.base_revision,
                original_revision_id=self._original_revision,
                plan_sha256=self._plan,
            )
        except ExecutionContractError:
            raise ExecutionUncertainError(operation.operation_id) from None
        if receipt.state is JobState.TIMED_OUT:
            raise ExecutionTimedOutError(receipt)
        if receipt.state is JobState.LAUNCH_FAILED:
            raise ExecutionUnavailableError
        if receipt.state is not JobState.EXITED or receipt.exit_code is None:
            raise ExecutionUncertainError(operation.operation_id)
        return PtyResult(
            receipt.stdout_tail + receipt.stderr_tail, receipt.exit_code, receipt.truncated, session_id, False
        )

    def _control(self, action: str, session_id: str | None) -> dict[str, Any]:
        return self._request(Operation.PTY_CONTROL, {"action": action, "session_id": session_id}, uuid4().hex)

    def send_ctrl_c(self, session_id: str) -> str:
        return str(self._control("INTERRUPT", session_id)["message"])

    def close(self, session_id: str) -> None:
        self._control("CLOSE", session_id)

    def list_sessions(self) -> list[str]:
        result = self._control("LIST", None)
        return list(result["sessions"])
