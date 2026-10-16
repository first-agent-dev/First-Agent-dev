"""Immutable execution identities and grant-reply data (not authorization).

These are internal primitives, not a complete wire decoder. The dispatcher,
resource registry, durable operation journal and ExecutionReceipt remain separate
work. A well-shaped ViewRef does not prove that the view exists or is authorized.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from fa.session.manager import SessionManager, SessionManagerError


class ExecutionContractError(ValueError):
    """Sanitized structural failure; never include caller data or grants."""

    def __init__(self) -> None:
        super().__init__("execution_contract_invalid")


def _hex_id(value: object, prefix: str, length: int = 32) -> None:
    if not isinstance(value, str) or re.fullmatch(prefix + rf"[0-9a-f]{{{length}}}", value) is None:
        raise ExecutionContractError


def _positive_integer(value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ExecutionContractError


class Operation(StrEnum):
    """The nineteen closed v1 operation names; not executable callbacks."""

    HEALTH = "health"
    REGISTER_WORKSPACE = "register_workspace"
    ACQUIRE_WRITER = "acquire_writer"
    PIN_READER = "pin_reader"
    CREATE_VIEW = "create_view"
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EDIT_FILE = "edit_file"
    EXEC = "exec"
    INSPECT = "inspect"
    CANCEL = "cancel"
    STOP_VIEW = "stop_view"
    SEAL = "seal"
    PUBLISH = "publish"
    INSTALL_PROJECT = "install_project"
    RELEASE = "release"
    PTY_CONTROL = "pty_control"
    HANDOFF = "handoff"
    PREPARE_BUNDLE = "prepare_bundle"


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
