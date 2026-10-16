"""Supervisor-owned completed grant-reply cache: Q75(a), not a running service.

The future single durable journal must establish DONE before remember_completed;
this cache does not attest completion, reserve operations, mint grants, authorize
fresh work, or implement dispatcher/service/kernel isolation. The dispatcher
must authenticate the principal and distinguish new requests from journaled
operations BEFORE using this cache. Missing cached state is uncertainty, never
permission to execute or reconstruct a grant from durable metadata.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from threading import Lock

from fa.execution.types import (
    GRANT_OPERATIONS,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewRef,
    _hex_id,
    _positive_integer,
    validate_capability,
)


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
        if not isinstance(self.operation, Operation) or self.operation not in GRANT_OPERATIONS:
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
    if binding.operation in {Operation.ACQUIRE_WRITER, Operation.PIN_READER}:
        if proof is not None:
            raise ExecutionContractError
    else:
        validate_capability(proof)


@dataclass(frozen=True, repr=False)
class _CompletedReply:
    binding: ReplayBinding
    original_proof: str | None
    reply: GrantReply


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
        reply: GrantReply,
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

    def replay(self, binding: ReplayBinding, original_proof: str | None) -> GrantReply:
        _validate_original_proof(binding, original_proof)
        with self._lock:
            entry = self._entries.get(binding.request_id)
            if entry is None:
                raise ReplyUnavailableError
            _authorize_replay(entry, binding, original_proof)
            return entry.reply
