"""Private-UDS dispatcher and memory-only completed-reply cache.

Requires real resource authority, operation journal and backend; no defaults or
service main. These components do not implement workspace authority or Docker.
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import socket
import struct
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING, Any

from fa.execution.plans import ProtectedPlanContext
from fa.execution.profiles import ExecutionProfile
from fa.execution.protocol import (
    ERROR_CODES,
    DeadlineConnection,
    InvalidRequestError,
    decode_reply,
    decode_request,
    encode_json,
    read_frame,
    write_frame,
)
from fa.execution.types import (
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    PublicReply,
    ViewRef,
    _hex_id,
    _positive_integer,
    validate_capability,
)

if TYPE_CHECKING:
    from fa.execution.journal import OperationJournal


class ReplyUnavailableError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("execution_reply_unavailable")


class ReplayConflictError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("execution_replay_conflict")


def operation_input_sha256(
    operation: Operation,
    namespace: NamespaceRef,
    view_ref: ViewRef | None,
    payload: Mapping[str, object],
) -> str:
    """Hash already wire-validated input, excluding request_id and capability.

    Not a wire-schema validator. JSON key ordering is insignificant; operation,
    namespace, full ViewRef and payload values remain significant. No raw input
    or proof is retained here. The four-MiB request limit is checked upstream.
    """
    if not isinstance(operation, Operation) or not isinstance(namespace, NamespaceRef):
        raise ExecutionContractError
    if view_ref is not None and not isinstance(view_ref, ViewRef):
        raise ExecutionContractError
    if not isinstance(payload, Mapping):
        raise ExecutionContractError
    try:
        encoded = json.dumps(
            {
                "op": operation.value,
                "namespace": namespace.to_dict(),
                "view_ref": None if view_ref is None else view_ref.to_dict(),
                "payload": dict(payload),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        raise ExecutionContractError from None
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, repr=False)
class ReplayBinding:
    """Principal is supplied by authentication, NEVER by a model/wire field."""

    principal: str
    namespace: NamespaceRef
    operation: Operation
    request_id: str
    input_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.namespace, NamespaceRef):
            raise ExecutionContractError
        if not isinstance(self.operation, Operation) or self.operation is Operation.HEALTH:
            raise ExecutionContractError
        _hex_id(self.request_id, "", 32)
        _hex_id(self.input_sha256, "", 64)
        if not isinstance(self.principal, str) or not self.principal or "\0" in self.principal:
            raise ExecutionContractError
        try:
            if len(self.principal.encode("utf-8")) > 256:
                raise ExecutionContractError
        except UnicodeError:
            raise ExecutionContractError from None


def _validate_original_proof(binding: ReplayBinding, proof: str | None) -> None:
    if binding.operation in {Operation.ACQUIRE_WRITER, Operation.PIN_READER, Operation.REGISTER_WORKSPACE}:
        if proof is not None:
            raise ExecutionContractError
    else:
        validate_capability(proof)


@dataclass(frozen=True, repr=False)
class _CompletedReply:
    binding: ReplayBinding
    original_proof: str | None
    reply: GrantReply | PublicReply


# §execution-original-reply-replay: revoked proof retrieves only the bound cached original.
def _authorize_replay(entry: _CompletedReply, binding: ReplayBinding, proof: str | None) -> None:
    # This check is ONLY for reading the original cached result. In particular,
    # it cannot validate a revoked parent proof for fresh work or renew a grant.
    proof_matches = (
        proof is None
        if entry.original_proof is None
        else proof is not None and hmac.compare_digest(entry.original_proof, proof)
    )
    if entry.binding != binding or not proof_matches:
        raise ReplayConflictError


class CompletedReplyCache:
    """Bounded, process-local, thread-safe; no eviction/recovery/serialization.

    Saturation refuses new entries; existing ones are not replaced. Like cache
    loss/restart, failure to retain a completed reply requires safe reconciliation
    via the durable operation state, not another execution. There is deliberately
    no callback that can generate a missing result or manufacture fresh authority.
    """

    def __init__(self, *, max_entries: int) -> None:
        _positive_integer(max_entries)
        self._max_entries = max_entries
        self._entries: dict[str, _CompletedReply] = {}
        self._lock = Lock()

    def remember_completed(
        self,
        binding: ReplayBinding,
        original_proof: str | None,
        reply: GrantReply | PublicReply,
    ) -> None:
        """Trusted journal owner calls ONLY after its durable DONE validation."""
        _validate_original_proof(binding, original_proof)
        if reply.operation != binding.operation:
            raise ReplayConflictError
        reply.to_journal_result(original_proof=original_proof)
        with self._lock:
            existing = self._entries.get(binding.request_id)
            if existing is not None:
                _authorize_replay(existing, binding, original_proof)
                if existing.reply != reply:
                    raise ReplayConflictError
                return
            if len(self._entries) >= self._max_entries:
                raise ReplyUnavailableError
            self._entries[binding.request_id] = _CompletedReply(binding, original_proof, reply)

    def replay(self, binding: ReplayBinding, original_proof: str | None) -> GrantReply | PublicReply:
        _validate_original_proof(binding, original_proof)
        with self._lock:
            entry = self._entries.get(binding.request_id)
            if entry is None:
                raise ReplyUnavailableError
            _authorize_replay(entry, binding, original_proof)
            return entry.reply


@dataclass(frozen=True)
class PeerIdentity:
    pid: int
    uid: int
    gid: int

    @property
    def principal(self) -> str:
        return f"uid:{self.uid}:gid:{self.gid}"


class SupervisorError(RuntimeError):
    def __init__(self, code: str, operation_id: str | None = None) -> None:
        if code not in ERROR_CODES:
            raise ExecutionContractError
        if operation_id is not None:
            _hex_id(operation_id, "op-")
        super().__init__("execution_request_rejected")
        self.code, self.operation_id = code, operation_id


class SupervisorDispatcher:
    """Transport + ordering, NOT authority/backend implementation or activation.

    Callers supply actual side-effect-free authority and bounded real backend.
    No defaults, implicit allow, host-shell fallback or grant reconstruction.
    Startup owner must reconcile/quarantine durable uncertain operations before
    accepting requests. Each accepted connection is served once then closed.
    """

    def __init__(
        self,
        *,
        client_uids: frozenset[int],
        rpc_timeout_ms: int,
        profiles: tuple[ExecutionProfile, ...],
        journal: OperationJournal,
        replies: CompletedReplyCache,
        authorize: Callable[[PeerIdentity, dict[str, Any]], ProtectedPlanContext | None],
        handle: Callable[[dict[str, Any]], GrantReply | dict[str, Any]],
    ) -> None:
        if not client_uids or any(type(uid) is not int or uid < 0 for uid in client_uids):
            raise ExecutionContractError
        _positive_integer(rpc_timeout_ms)
        if not profiles or len({profile.profile_id for profile in profiles}) != len(profiles):
            raise ExecutionContractError
        if not callable(authorize) or not callable(handle):
            raise ExecutionContractError
        self._uids = frozenset(client_uids)
        self._timeout_ms = rpc_timeout_ms
        self._profiles = {profile.profile_id: profile for profile in profiles}
        self._journal, self._replies = journal, replies
        self._authorize, self._handle = authorize, handle

    def _authorize_request(self, peer: PeerIdentity, request: dict[str, Any]) -> ProtectedPlanContext | None:
        if peer.uid not in self._uids:
            raise SupervisorError("UNAUTHORIZED")
        if request["op"] == "exec":
            profile = self._profiles.get(request["payload"]["profile_id"])
            if profile is None:
                raise SupervisorError("UNAPPROVED_PROFILE")
            if request["payload"]["timeout_ms"] > profile.max_command_ms or profile.interactive != (
                request["payload"]["session_id"] is not None
            ):
                raise SupervisorError("INPUT_POLICY")
        context = self._authorize(peer, copy.deepcopy(request))  # Actual resource authority REQUIRED.
        if request["op"] in {"pin_reader", "create_view", "exec"}:
            if not isinstance(context, ProtectedPlanContext):
                raise SupervisorError("UNAUTHORIZED")
            try:
                context.recheck()
            except ExecutionContractError:
                raise SupervisorError("INPUT_POLICY") from None
            if request["op"] != "exec" and request["payload"]["plan_ref"] != context.to_plan_ref():
                raise SupervisorError("INPUT_POLICY")
            if (
                request["op"] == "exec"
                and request["view_ref"]["purpose"] in {"VERIFICATION", "MUTATION", "CANDIDATE"}
                and context.plan_ref is None
            ):
                raise SupervisorError("INPUT_POLICY")
        return context

    @staticmethod
    def _reply(
        request_id: str, *, result: dict[str, Any] | None = None, error: SupervisorError | None = None
    ) -> dict[str, Any]:
        return {
            "protocol_version": 1,
            "request_id": request_id,
            "status": "OK" if error is None else "ERROR",
            "result": result,
            "error": None
            if error is None
            else {"code": error.code, "retryable": False, "operation_id": error.operation_id},
        }

    def _completed(self, record: dict[str, Any], binding: ReplayBinding, proof: str | None) -> dict[str, Any]:
        if record["input_sha256"] != binding.input_sha256 or record["op"] != binding.operation.value:
            raise SupervisorError("COLLISION", record["operation_id"])
        if record["state"] != "DONE":
            raise SupervisorError("EXECUTION_UNKNOWN", record["operation_id"])
        try:
            # Cache loss never invokes fresh authority, handler or issuer.
            return self._replies.replay(binding, proof).to_wire_result()
        except ReplyUnavailableError:
            raise SupervisorError("EXECUTION_UNKNOWN", record["operation_id"]) from None
        except ReplayConflictError:
            raise SupervisorError("UNAUTHORIZED", record["operation_id"]) from None

    def _execute_reserved(
        self, request: dict[str, Any], binding: ReplayBinding, context: ProtectedPlanContext | None
    ) -> dict[str, Any]:
        operation_id = "op-" + binding.request_id
        self._journal.begin(operation_id, binding.namespace)
        produced = self._handle(copy.deepcopy(request))
        if binding.operation in {
            Operation.ACQUIRE_WRITER,
            Operation.PIN_READER,
            Operation.CREATE_VIEW,
            Operation.HANDOFF,
        }:
            if not isinstance(produced, GrantReply):
                raise ExecutionContractError
            snapshot: GrantReply | PublicReply = produced
        else:
            if not isinstance(produced, dict):
                raise ExecutionContractError
            snapshot = PublicReply.from_result(binding.operation, produced)
        response = self._reply(binding.request_id, result=snapshot.to_wire_result())
        decode_reply(encode_json(response), operation=binding.operation, request_id=binding.request_id)
        if binding.operation is Operation.EXEC:
            if context is None:
                raise ExecutionContractError
            context.check_receipt_plan(snapshot.to_wire_result()["receipt"]["plan_sha256"])
        self._journal.complete(operation_id, binding.namespace, produced, original_proof=request["capability"])
        self._replies.remember_completed(binding, request["capability"], snapshot)
        return snapshot.to_wire_result()

    def _dispatch(self, peer: PeerIdentity, request: dict[str, Any]) -> dict[str, Any]:
        from fa.execution.journal import JournalError

        reserved_id: str | None = None
        namespace: NamespaceRef | None = None
        try:
            operation = Operation(request["op"])
            readonly = operation in {Operation.HEALTH, Operation.READ_FILE, Operation.INSPECT}
            readonly = readonly or (operation is Operation.PTY_CONTROL and request["payload"]["action"] == "LIST")
            if readonly:
                self._authorize_request(peer, request)
                produced = self._handle(copy.deepcopy(request))
                if not isinstance(produced, dict):
                    raise ExecutionContractError
                response = self._reply(request["request_id"], result=produced)
            else:
                namespace = NamespaceRef(**request["namespace"])
                # The wire-validated ViewRef is included in the exact-input hash;
                # never use its mere shape as proof that a resource exists.
                from fa.execution.types import Access, ViewPurpose

                view_data = request["view_ref"]
                view = (
                    None
                    if view_data is None
                    else ViewRef(
                        **{
                            **view_data,
                            "access": Access(view_data["access"]),
                            "purpose": ViewPurpose(view_data["purpose"]),
                        }
                    )
                )
                binding = ReplayBinding(
                    peer.principal,
                    namespace,
                    operation,
                    request["request_id"],
                    operation_input_sha256(operation, namespace, view, request["payload"]),
                )
                existing = self._journal.lookup("op-" + binding.request_id, namespace)
                if existing is not None:
                    value = self._completed(existing, binding, request["capability"])
                else:
                    context = self._authorize_request(peer, request)
                    reserved = self._journal.reserve(request)
                    if reserved.fresh:
                        reserved_id = reserved.record["operation_id"]
                        value = self._execute_reserved(request, binding, context)
                    else:
                        value = self._completed(reserved.record, binding, request["capability"])
                response = self._reply(request["request_id"], result=value)
            return decode_reply(encode_json(response), operation=operation, request_id=request["request_id"])
        except Exception as exc:  # noqa: BLE001 — private boundary must sanitize arbitrary backend exceptions.
            if reserved_id is not None and namespace is not None:
                try:
                    self._journal.mark_unknown(reserved_id, namespace)
                except (JournalError, OSError, ExecutionContractError):
                    return self._reply(request["request_id"], error=SupervisorError("DURABILITY_UNKNOWN", reserved_id))
            if isinstance(exc, SupervisorError):
                error = exc
            elif isinstance(exc, JournalError):
                error = SupervisorError(exc.code, reserved_id)
            else:
                error = SupervisorError("EXECUTION_UNKNOWN" if reserved_id else "BACKEND_UNAVAILABLE", reserved_id)
            return self._reply(request["request_id"], error=error)

    def serve_connection(self, connection: socket.socket) -> None:
        with connection:
            try:
                pid, uid, gid = struct.unpack(
                    "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
                )
                if uid not in self._uids:
                    return  # Authenticate before reading attacker-controlled frames.
                framed = DeadlineConnection(connection, timeout_ms=self._timeout_ms)
                try:
                    request = decode_request(read_frame(framed))
                except InvalidRequestError as exc:
                    if exc.request_id is not None:
                        write_frame(
                            framed, encode_json(self._reply(exc.request_id, error=SupervisorError("INVALID_REQUEST")))
                        )
                    return
                response = self._dispatch(PeerIdentity(pid, uid, gid), request)
                write_frame(framed, encode_json(response))
            except (OSError, ExecutionContractError):
                # Lost replies never roll back durable state or replay a handler.
                return
