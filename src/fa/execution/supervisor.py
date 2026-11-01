"""Private-UDS dispatcher, memory-only completed-reply cache, stop barrier.

Requires real resource authority and operation journal; nothing here defaults or
invents one. `build_supervisor`/`main` are the §2.2 composition entry points and
construct the object in `service.py`; this module stays transport and ordering.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import logging
import math
import socket
import struct
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any, Protocol

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
    from fa.execution.service import ServiceConfig, SupervisorService
    from fa.execution.workspace import WorkspaceAuthority

logger = logging.getLogger(__name__)


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
    The optional byte budget counts retained immutable public-result bytes only;
    entry metadata, grants and transient copies are not an RSS measurement.
    """

    def __init__(self, *, max_entries: int, max_public_bytes: int | None = None) -> None:
        _positive_integer(max_entries)
        if max_public_bytes is not None:
            _positive_integer(max_public_bytes)
        self._max_entries = max_entries
        self._max_public_bytes = max_public_bytes
        self._public_bytes = 0
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
            size = len(reply.canonical_result) if isinstance(reply, PublicReply) else 0
            if len(self._entries) >= self._max_entries or (
                self._max_public_bytes is not None and self._public_bytes + size > self._max_public_bytes
            ):
                raise ReplyUnavailableError
            self._entries[binding.request_id] = _CompletedReply(binding, original_proof, reply)
            self._public_bytes += size

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


class RequestAuthorizer(Protocol):
    def __call__(
        self, peer: PeerIdentity, request: dict[str, Any], /, *, deadline: float
    ) -> ProtectedPlanContext | None: ...


class RequestHandler(Protocol):
    def __call__(
        self, peer: PeerIdentity, request: dict[str, Any], /, *, deadline: float
    ) -> GrantReply | dict[str, Any]: ...


# Spec §2.1 / E268: the operations that mutate canonical or supervisor state and
# therefore MUST pass the authority check before any reservation. Derived from
# the closed enum and validated at construction, never a parallel string list.
AUTHORITY_GATED_OPERATIONS = frozenset(
    {
        Operation.STOP_VIEW,
        Operation.SEAL,
        Operation.PUBLISH,
        Operation.INSTALL_PROJECT,
        Operation.PREPARE_BUNDLE,
        Operation.HANDOFF,
        Operation.RELEASE,
    }
)
# The only operations the dispatcher may serve without a durable reservation:
# health, an immutable read, and observation of an already-reserved operation.
READONLY_OPERATIONS = frozenset({Operation.HEALTH, Operation.READ_FILE, Operation.INSPECT})


def _require_budget(deadline: float) -> None:
    if type(deadline) not in {int, float} or not math.isfinite(deadline):
        raise ExecutionContractError
    if time.monotonic() >= deadline:
        raise TimeoutError


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
        authorize: RequestAuthorizer,
        handle: RequestHandler,
    ) -> None:
        if not client_uids or any(type(uid) is not int or uid < 0 for uid in client_uids):
            raise ExecutionContractError
        _positive_integer(rpc_timeout_ms)
        if not profiles or len({profile.profile_id for profile in profiles}) != len(profiles):
            raise ExecutionContractError
        if not callable(authorize) or not callable(handle):
            raise ExecutionContractError
        # A classed-as-readonly mutator would skip the authority check and the
        # reservation entirely, so the classification is refused, not repaired.
        if not AUTHORITY_GATED_OPERATIONS <= frozenset(Operation) or READONLY_OPERATIONS & AUTHORITY_GATED_OPERATIONS:
            raise ExecutionContractError
        self._uids = frozenset(client_uids)
        self._timeout_ms = rpc_timeout_ms
        self._profiles = {profile.profile_id: profile for profile in profiles}
        self._journal, self._replies = journal, replies
        self._authorize, self._handle = authorize, handle

    def _authorize_request(
        self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float
    ) -> ProtectedPlanContext | None:
        _require_budget(deadline)
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
        context = self._authorize(
            peer, copy.deepcopy(request), deadline=deadline
        )  # Actual resource authority REQUIRED.
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
        self,
        peer: PeerIdentity,
        request: dict[str, Any],
        binding: ReplayBinding,
        context: ProtectedPlanContext | None,
        *,
        deadline: float,
    ) -> dict[str, Any]:
        operation_id = "op-" + binding.request_id
        _require_budget(deadline)
        self._journal.begin(operation_id, binding.namespace, deadline=deadline)
        _require_budget(deadline)
        produced = self._handle(peer, copy.deepcopy(request), deadline=deadline)
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
        # The handler may return a truthful result just after the caller-facing
        # deadline. Persist that result using the journal's bounded lock timeout;
        # write_frame still enforces the independent transport/reply deadline.
        self._journal.complete(
            operation_id,
            binding.namespace,
            produced,
            original_proof=request["capability"],
        )
        self._replies.remember_completed(binding, request["capability"], snapshot)
        return snapshot.to_wire_result()

    def _dispatch(self, peer: PeerIdentity, request: dict[str, Any], *, deadline: float) -> dict[str, Any]:
        from fa.execution.journal import JournalError

        reserved_id: str | None = None
        namespace: NamespaceRef | None = None
        try:
            operation = Operation(request["op"])
            readonly = operation in READONLY_OPERATIONS
            readonly = readonly or (operation is Operation.PTY_CONTROL and request["payload"]["action"] == "LIST")
            if readonly:
                self._authorize_request(peer, request, deadline=deadline)
                _require_budget(deadline)
                produced = self._handle(peer, copy.deepcopy(request), deadline=deadline)
                if not isinstance(produced, dict):
                    raise ExecutionContractError
                response = self._reply(request["request_id"], result=produced)
            else:
                namespace = NamespaceRef(**request["namespace"])
                # The wire-validated ViewRef is included in the exact-input hash;
                # never use its mere shape as proof that a resource exists.
                view_data = request["view_ref"]
                view = None if view_data is None else ViewRef.from_dict(view_data)
                binding = ReplayBinding(
                    peer.principal,
                    namespace,
                    operation,
                    request["request_id"],
                    operation_input_sha256(operation, namespace, view, request["payload"]),
                )
                existing = self._journal.lookup("op-" + binding.request_id, namespace, deadline=deadline)
                if existing is not None:
                    value = self._completed(existing, binding, request["capability"])
                else:
                    context = self._authorize_request(peer, request, deadline=deadline)
                    reserved = self._journal.reserve(request, deadline=deadline)
                    if reserved.fresh:
                        reserved_id = reserved.record["operation_id"]
                        value = self._execute_reserved(peer, request, binding, context, deadline=deadline)
                    else:
                        value = self._completed(reserved.record, binding, request["capability"])
                response = self._reply(request["request_id"], result=value)
            return decode_reply(encode_json(response), operation=operation, request_id=request["request_id"])
        except Exception as exc:  # noqa: BLE001 — private boundary must sanitize arbitrary backend exceptions.
            if reserved_id is not None and namespace is not None:
                try:
                    # Closing an already-reserved operation is safe journal
                    # finalization, not fresh work. It retains its own bounded
                    # lock timeout so an expired request does not strand the
                    # record in EXECUTING and invite ambiguous recovery.
                    self._journal.mark_unknown(reserved_id, namespace)
                except JournalError as mark_error:
                    code = "EXECUTION_UNKNOWN" if mark_error.code == "BACKEND_UNAVAILABLE" else "DURABILITY_UNKNOWN"
                    return self._reply(request["request_id"], error=SupervisorError(code, reserved_id))
                except (OSError, ExecutionContractError):
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
                deadline = framed.deadline
                try:
                    request = decode_request(read_frame(framed))
                except InvalidRequestError as exc:
                    if exc.request_id is not None:
                        write_frame(
                            framed, encode_json(self._reply(exc.request_id, error=SupervisorError("INVALID_REQUEST")))
                        )
                    return
                if request["op"] == "exec":
                    profile = self._profiles.get(request["payload"]["profile_id"])
                    if (
                        profile is not None
                        and request["payload"]["timeout_ms"] <= profile.max_command_ms
                        and profile.interactive == (request["payload"]["session_id"] is not None)
                    ):
                        framed.add_execution_budget(request["payload"]["timeout_ms"])
                        # Reply waiting may include the control allowance; execution
                        # consumes its requested budget from the original receipt.
                        deadline = framed.started_at + request["payload"]["timeout_ms"] / 1000
                response = self._dispatch(PeerIdentity(pid, uid, gid), request, deadline=deadline)
                write_frame(framed, encode_json(response))
            except (OSError, ExecutionContractError):
                # Lost replies never roll back durable state or replay a handler.
                return


def build_supervisor(config: ServiceConfig | None = None, **kwargs: Any) -> SupervisorService:
    """The one production composition: authority + journal + cache + dispatcher.

    `supervisor.build_supervisor` is the name §2.2 fixes; the object itself lives
    in `service.py` so this module stays the transport/ordering owner. Lazy
    import keeps the dependency direction one-way (service imports supervisor).
    """
    from fa.execution.service import ServiceConfig as _ServiceConfig
    from fa.execution.service import SupervisorService

    if config is None:
        config = _ServiceConfig(**kwargs)
    if not isinstance(config, _ServiceConfig):
        raise ExecutionContractError
    return SupervisorService(config)


def main(argv: Sequence[str] | None = None) -> int:
    """Operator entry point: one JSON config, one private socket, bounded life.

    Refuses to start on any configuration, ownership, recovery or binding error
    (exit 2) rather than serving from a default or partial composition. SIGINT
    and SIGTERM stop acceptance and wait for in-flight handlers to finish.
    """
    import signal
    import sys
    import threading

    from fa.execution.service import read_config_file

    parser = argparse.ArgumentParser(prog="fa-execution-supervisor", add_help=True)
    parser.add_argument("--config", required=True, type=Path, help="absolute path to the service JSON config")
    arguments = parser.parse_args(argv)
    try:
        service = build_supervisor(read_config_file(arguments.config))
    except (ExecutionContractError, OSError, ValueError):
        print("execution_supervisor: invalid configuration", file=sys.stderr)
        return 2
    stop = threading.Event()

    def _stop(_signum: int, _frame: object) -> None:
        stop.set()

    previous = {signal.SIGINT: signal.signal(signal.SIGINT, _stop)}
    previous[signal.SIGTERM] = signal.signal(signal.SIGTERM, _stop)
    try:
        with service:
            service.serve_forever(stop)
    except (ExecutionContractError, OSError):
        print("execution_supervisor: startup refused", file=sys.stderr)
        return 2
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    return 0


class TerminalVerdict(StrEnum):
    """The only three answers a descendant observation may give.

    There is no "probably" and no timeout-as-success: a view that cannot be
    *observed* empty stays owned and unsealed.
    """

    TERMINAL = "terminal"
    POPULATED = "populated"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ViewStopResult:
    """Outcome of one stop flow. ``terminal`` is the only wire fact (STOP_VIEW)."""

    view_id: str
    terminal: bool
    verdict: TerminalVerdict
    reason: str | None = None

    def to_wire(self) -> dict[str, Any]:
        """The protocol's STOP_VIEW reply is exactly ``{view_id, terminal}``."""
        return {"view_id": self.view_id, "terminal": self.terminal}


class CellTermination(Protocol):
    """Backend seam: stop this view's cells, then answer the kernel question.

    Two methods, not one, because stopping is a request and emptiness is an
    observation. ``cells_terminal`` returns True (proven empty), False (still
    populated) or None (cannot tell); the caller never infers the first from the
    other two.
    """

    def stop_cells(self, namespace: NamespaceRef, view_ref: ViewRef, *, deadline: float) -> None: ...

    def cells_terminal(self, namespace: NamespaceRef, view_ref: ViewRef) -> bool | None: ...


class ViewStopper:
    """CT104's terminal barrier: close admission, drain, stop cells, then OBSERVE.

    The authority stays the single owner of view state and of the durable
    receipt; this class only decides *when* to ask it. Every step is bounded by
    the caller's deadline and the flow is idempotent: a view that already has a
    terminal receipt is returned as terminal without touching a cell.
    """

    def __init__(
        self,
        authority: WorkspaceAuthority,
        *,
        cells: CellTermination | None = None,
        poll_interval_s: float = 0.05,
    ) -> None:
        # Lazy import: workspace imports this module for SupervisorError/PeerIdentity.
        from fa.execution.workspace import WorkspaceAuthority

        if not isinstance(authority, WorkspaceAuthority):
            raise ExecutionContractError
        if cells is not None and (
            not callable(getattr(cells, "stop_cells", None)) or not callable(getattr(cells, "cells_terminal", None))
        ):
            raise ExecutionContractError
        if type(poll_interval_s) is not float or not math.isfinite(poll_interval_s) or poll_interval_s <= 0:
            raise ExecutionContractError
        self._authority = authority
        self._cells = cells
        self._poll_interval_s = poll_interval_s

    def stop_view(
        self,
        peer: PeerIdentity,
        namespace: NamespaceRef,
        *,
        view_ref: ViewRef,
        capability: str,
        deadline: float,
    ) -> ViewStopResult:
        if not isinstance(namespace, NamespaceRef) or not isinstance(view_ref, ViewRef):
            raise ExecutionContractError
        _require_budget(deadline)
        # Idempotence first: an already-proven view costs no cell traffic.
        if self._authority.terminal_receipt(peer, namespace, view_ref=view_ref, capability=capability) is not None:
            return ViewStopResult(view_ref.view_id, True, TerminalVerdict.TERMINAL, "already terminal")

        # Irreversible closure, then a drained handler set. A drain that cannot
        # finish inside the budget raises; the view then stays STOPPING, owned.
        self._authority.close_admission(peer, namespace, view_ref=view_ref, capability=capability, deadline=deadline)
        self._authority.drain(peer, namespace, view_ref=view_ref, capability=capability, deadline=deadline)

        if self._cells is None:
            return ViewStopResult(view_ref.view_id, False, TerminalVerdict.UNKNOWN, "no descendant observer configured")
        self._cells.stop_cells(namespace, view_ref, deadline=deadline)
        verdict, reason = self._wait_descendants_terminal(namespace, view_ref, deadline)
        if verdict is not TerminalVerdict.TERMINAL:
            return ViewStopResult(view_ref.view_id, False, verdict, reason)
        self._authority.record_terminal(peer, namespace, view_ref=view_ref, capability=capability, deadline=deadline)
        return ViewStopResult(view_ref.view_id, True, TerminalVerdict.TERMINAL)

    def _wait_descendants_terminal(
        self, namespace: NamespaceRef, view_ref: ViewRef, deadline: float
    ) -> tuple[TerminalVerdict, str | None]:
        """Poll the observation to the deadline; nothing but True is terminality."""
        cells = self._cells
        if cells is None:  # caller checked; keep mypy honest without an assert
            return TerminalVerdict.UNKNOWN, "no descendant observer configured"
        while True:
            try:
                observed = cells.cells_terminal(namespace, view_ref)
            except Exception as exc:  # noqa: BLE001 - an unreadable kernel fact is UNKNOWN, not terminal
                logger.warning("descendant observation failed for %s: %s", view_ref.view_id, exc)
                return TerminalVerdict.UNKNOWN, "descendant observation failed"
            if observed is True:
                return TerminalVerdict.TERMINAL, None
            if observed is None:
                return TerminalVerdict.UNKNOWN, "descendant observation unavailable"
            if observed is not False:
                return TerminalVerdict.UNKNOWN, "descendant observation was not a verdict"
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return TerminalVerdict.POPULATED, "descendants still populated at the deadline"
            time.sleep(min(self._poll_interval_s, remaining))
