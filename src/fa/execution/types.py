"""Immutable execution identities and grant-reply data (not authorization).

Shape validation and memory snapshots do not attest actual backend observations.
The real resource authority and installed service integration remain separate.
A well-shaped ViewRef does not prove that the view exists or is authorized.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from fa.execution.primitives import (
    ExecutionContractError as ExecutionContractError,
)
from fa.execution.primitives import (
    Operation as Operation,
)
from fa.execution.primitives import (
    _hex_id as _hex_id,
)
from fa.execution.primitives import (
    _positive_integer as _positive_integer,
)
from fa.session.manager import SessionManager, SessionManagerError


@dataclass(frozen=True)
class NamespaceRef:
    session_id: str
    run_id: str
    parent_run_id: str | None = None

    def __post_init__(self) -> None:
        try:
            SessionManager.validate_session_id(self.session_id)
            SessionManager.validate_run_id(self.run_id)
            if self.parent_run_id is not None:
                SessionManager.validate_run_id(self.parent_run_id)
        except SessionManagerError:
            raise ExecutionContractError from None

    def to_dict(self) -> dict[str, str | None]:
        return {"session_id": self.session_id, "run_id": self.run_id, "parent_run_id": self.parent_run_id}


class Access(StrEnum):
    READ = "READ"
    WRITE = "WRITE"


class ViewPurpose(StrEnum):
    PROJECT = "PROJECT"
    PROVISIONING = "PROVISIONING"
    VERIFICATION = "VERIFICATION"
    MUTATION = "MUTATION"
    CANDIDATE = "CANDIDATE"


@dataclass(frozen=True)
class ViewRef:
    workspace_id: str
    view_id: str
    base_revision: str
    owner_run_id: str
    generation: int
    access: Access
    purpose: ViewPurpose

    def __post_init__(self) -> None:
        _hex_id(self.workspace_id, "ws-")
        _hex_id(self.view_id, "view-")
        _hex_id(self.base_revision, "rev-")
        _positive_integer(self.generation)
        try:
            SessionManager.validate_run_id(self.owner_run_id)
        except SessionManagerError:
            raise ExecutionContractError from None
        if not isinstance(self.access, Access) or not isinstance(self.purpose, ViewPurpose):
            raise ExecutionContractError

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "view_id": self.view_id,
            "base_revision": self.base_revision,
            "owner_run_id": self.owner_run_id,
            "generation": self.generation,
            "access": self.access.value,
            "purpose": self.purpose.value,
        }

    @classmethod
    def from_dict(cls, raw: object) -> ViewRef:
        """Construct one validated identity from an already decoded record."""
        keys = {
            "workspace_id",
            "view_id",
            "base_revision",
            "owner_run_id",
            "generation",
            "access",
            "purpose",
        }
        if type(raw) is not dict or set(raw) != keys:
            raise ExecutionContractError
        try:
            return cls(
                workspace_id=raw["workspace_id"],
                view_id=raw["view_id"],
                base_revision=raw["base_revision"],
                owner_run_id=raw["owner_run_id"],
                generation=raw["generation"],
                access=Access(raw["access"]),
                purpose=ViewPurpose(raw["purpose"]),
            )
        except (KeyError, TypeError, ValueError):
            raise ExecutionContractError from None


_OWNER_GRANT_OPERATIONS = frozenset({Operation.ACQUIRE_WRITER, Operation.HANDOFF})
_VIEW_GRANT_OPERATIONS = frozenset({Operation.PIN_READER, Operation.CREATE_VIEW})
GRANT_OPERATIONS = _OWNER_GRANT_OPERATIONS | _VIEW_GRANT_OPERATIONS


def validate_capability(value: object) -> None:
    """Wire representation of a 256-bit opaque grant; does not validate authority."""
    _hex_id(value, "", 64)


@dataclass(frozen=True, repr=False)
class GrantReply:
    """One original grant result, kept in memory only.

    Journal projection deliberately omits the grant, rather than persisting a
    full wire reply or a null/fabricated replacement grant. The owning operation
    record already supplies the operation discriminator. No ExecutionReceipt is
    invented for these non-execution operations.
    """

    operation: Operation
    capability: str
    view_ref: ViewRef | None
    generation: int | None
    revision_id: str | None

    def __post_init__(self) -> None:
        validate_capability(self.capability)
        if not isinstance(self.operation, Operation) or self.operation not in GRANT_OPERATIONS:
            raise ExecutionContractError
        if self.operation in _OWNER_GRANT_OPERATIONS:
            if self.view_ref is not None:
                raise ExecutionContractError
            _positive_integer(self.generation)
            _hex_id(self.revision_id, "rev-")
        elif not isinstance(self.view_ref, ViewRef) or self.generation is not None or self.revision_id is not None:
            raise ExecutionContractError
        if (
            self.operation is Operation.PIN_READER
            and self.view_ref is not None
            and self.view_ref.access is not Access.READ
        ):
            raise ExecutionContractError
        # A caller-selected identity must not smuggle even this known grant into
        # the durable projection. General output/credential policy is separate.
        self.to_journal_result(original_proof=None)

    def _public_result(self) -> dict[str, Any]:
        if self.operation in _OWNER_GRANT_OPERATIONS:
            result: dict[str, Any] = {
                "view_ref": None,
                "generation": self.generation,
                "revision_id": self.revision_id,
            }
        else:
            if self.view_ref is None:
                raise ExecutionContractError
            result = {"view_ref": self.view_ref.to_dict()}
        return result

    # §execution-grant-journal-projection: persist identities, never either known grant.
    def to_journal_result(self, *, original_proof: str | None) -> dict[str, Any]:
        """Call before durability, supplying the original request's actual proof."""
        if original_proof is not None:
            validate_capability(original_proof)
        result = self._public_result()
        try:
            encoded = json.dumps(result, sort_keys=True, separators=(",", ":"))
        except ValueError:
            raise ExecutionContractError from None
        if self.capability in encoded or (original_proof is not None and original_proof in encoded):
            raise ExecutionContractError
        return result

    def to_wire_result(self) -> dict[str, Any]:
        return {**self._public_result(), "capability": self.capability}

    def to_wire_capability(self) -> str:
        """Unwrap the stored grant into its wire string, once, at the transport.

        CT118: the grant a caller keeps is this object; only the client turns it
        back into the opaque string, so no other layer has a token to stash.
        """
        return self.capability


class JobState(StrEnum):
    RESERVED = "RESERVED"
    RUNNING = "RUNNING"
    EXITED = "EXITED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    LAUNCH_FAILED = "LAUNCH_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OperationRef:
    operation_id: str
    view_id: str
    owner_run_id: str
    generation: int
    input_tree_sha256: str

    def __post_init__(self) -> None:
        _hex_id(self.operation_id, "op-")
        _hex_id(self.view_id, "view-")
        _hex_id(self.input_tree_sha256, "", 64)
        _positive_integer(self.generation)
        try:
            SessionManager.validate_run_id(self.owner_run_id)
        except SessionManagerError:
            raise ExecutionContractError from None


@dataclass(frozen=True)
class ExecutionReceipt:
    """Complete v1 receipt data; construction cannot attest backend observations."""

    schema_version: int
    operation_id: str
    namespace: NamespaceRef
    workspace_id: str
    view_id: str
    owner_run_id: str
    generation: int
    revision_id: str | None
    original_revision_id: str | None
    input_tree_sha256: str
    plan_sha256: str | None
    profile_id: str
    image_digest: str
    state: JobState
    exit_code: int | None
    timed_out: bool
    stdout_tail: str
    stderr_tail: str
    truncated: bool
    duration_ms: int
    terminal_barrier: bool

    def __post_init__(self) -> None:
        # Local import keeps the single wire-schema authority independent of
        # construction order, rather than duplicating receipt validation here.
        from fa.execution.protocol import validate_receipt

        if not isinstance(self.namespace, NamespaceRef) or not isinstance(self.state, JobState):
            raise ExecutionContractError
        validate_receipt(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, record: dict[str, Any]) -> ExecutionReceipt:
        from fa.execution.protocol import validate_receipt

        validate_receipt(record)
        values = dict(record)
        values["namespace"] = NamespaceRef(**record["namespace"])
        values["state"] = JobState(record["state"])
        return cls(**values)

    def require_binding(
        self,
        *,
        operation: OperationRef,
        namespace: NamespaceRef,
        view: ViewRef,
        profile_id: str,
        image_digest: str,
        revision_id: str | None,
        original_revision_id: str | None,
        plan_sha256: str | None,
    ) -> None:
        """Compare against trusted reserved identity, not worker-supplied values."""
        actual = (
            self.operation_id,
            self.namespace,
            self.workspace_id,
            self.view_id,
            self.owner_run_id,
            self.generation,
            self.input_tree_sha256,
            self.profile_id,
            self.image_digest,
            self.revision_id,
            self.original_revision_id,
            self.plan_sha256,
        )
        expected = (
            operation.operation_id,
            namespace,
            view.workspace_id,
            view.view_id,
            operation.owner_run_id,
            operation.generation,
            operation.input_tree_sha256,
            profile_id,
            image_digest,
            revision_id,
            original_revision_id,
            plan_sha256,
        )
        if actual != expected or (operation.view_id, operation.owner_run_id, operation.generation) != (
            view.view_id,
            view.owner_run_id,
            view.generation,
        ):
            raise ExecutionContractError


@dataclass(frozen=True, repr=False)
class PublicReply:
    """Immutable successful non-grant result snapshot; never execution authority."""

    operation: Operation
    canonical_result: bytes

    def __post_init__(self) -> None:
        from fa.execution.protocol import _RESULT_CHECKS, _check, _loads, validate_receipt

        if (
            not isinstance(self.operation, Operation)
            or self.operation in GRANT_OPERATIONS
            or self.operation is Operation.HEALTH
        ):
            raise ExecutionContractError
        if type(self.canonical_result) is not bytes:
            raise ExecutionContractError
        record = _loads(self.canonical_result)
        _check(_RESULT_CHECKS[self.operation], record)
        if self.operation in {Operation.EXEC, Operation.INSPECT, Operation.CANCEL}:
            validate_receipt(record["receipt"])

    @classmethod
    def from_result(cls, operation: Operation, result: dict[str, Any]) -> PublicReply:
        from fa.execution.protocol import encode_json

        return cls(operation, encode_json(result))

    def to_wire_result(self) -> dict[str, Any]:
        from fa.execution.protocol import _loads

        return _loads(self.canonical_result)

    def to_journal_result(self, *, original_proof: str | None) -> dict[str, Any]:
        if original_proof is not None:
            validate_capability(original_proof)
            if original_proof.encode() in self.canonical_result:
                raise ExecutionContractError
        return self.to_wire_result()
