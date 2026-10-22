"""Single protected operation journal, not workspace/execution authority.

The trusted supervisor must authorize requests and reconcile Docker/workspace
state before admitting work. Reservation/transition data alone is not a grant.
Reuse the existing private IO primitives, not a second database/history.
"""

from __future__ import annotations

import copy
import math
import os
import stat
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import get_ident
from typing import Any

import fastjsonschema  # type: ignore[import-untyped]  # Existing library lacks typing metadata.

from fa.execution.protocol import (
    BOOL,
    MAX_FRAME_BYTES,
    NAMESPACE,
    RESULTS,
    SHA,
    VIEW,
    _check,
    _enum,
    _id,
    _loads,
    _nullable,
    _object,
    decode_request,
    encode_json,
    validate_receipt,
)
from fa.execution.supervisor import operation_input_sha256
from fa.execution.types import (
    GRANT_OPERATIONS,
    ExecutionContractError,
    GrantReply,
    NamespaceRef,
    Operation,
    ViewRef,
    _hex_id,
    _positive_integer,
)
from fa.inner_loop.workflow_artifacts import _admission_lock, _private_artifact_directory, _replace_private_bytes


class JournalError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__("execution_journal_unavailable")
        self.code = code


@dataclass(frozen=True)
class Reservation:
    fresh: bool
    record: dict[str, Any]


_RECORD = fastjsonschema.compile(
    _object(
        schema_version={"type": "integer", "const": 1},
        operation_id=_id("op-"),
        request_id=_id(""),
        op=_enum(*(op.value for op in Operation if op is not Operation.HEALTH)),
        namespace=NAMESPACE,
        view_ref=_nullable(VIEW),
        input_sha256=SHA,
        state=_enum("RESERVED", "EXECUTING", "DONE", "UNKNOWN"),
        container_id=_nullable(SHA),
        cancel_requested=BOOL,
        result=_nullable({"type": "object"}),
    )
)


def _projection_schema(op: Operation) -> dict[str, Any]:
    schema = copy.deepcopy(RESULTS[op])
    if op in GRANT_OPERATIONS:
        del schema["properties"]["capability"]
        schema["required"].remove("capability")
    return schema


_RESULTS = {op: fastjsonschema.compile(_projection_schema(op)) for op in Operation}


def _validate_completed_receipt(record: dict[str, Any], receipt: dict[str, Any]) -> None:
    validate_receipt(receipt)
    if receipt["state"] in {"RESERVED", "RUNNING", "UNKNOWN"}:
        raise ExecutionContractError
    if receipt["state"] == "EXITED" and record["container_id"] is None:
        raise ExecutionContractError
    if receipt["operation_id"] != record["operation_id"] or receipt["namespace"] != record["namespace"]:
        raise ExecutionContractError
    view = record["view_ref"]
    if view is not None and any(
        receipt[key] != view[key]
        for key in (
            "workspace_id",
            "view_id",
            "owner_run_id",
            "generation",
        )
    ):
        raise ExecutionContractError


def _validate_record(record: dict[str, Any]) -> None:
    _check(_RECORD, record)
    if record["operation_id"] != "op-" + record["request_id"]:
        raise ExecutionContractError
    if record["op"] != "exec" and record["container_id"] is not None:
        raise ExecutionContractError
    op = Operation(record["op"])
    no_view = op in GRANT_OPERATIONS | {
        Operation.REGISTER_WORKSPACE,
        Operation.PREPARE_BUNDLE,
        Operation.INSTALL_PROJECT,
    }
    if op is not Operation.RELEASE and (record["view_ref"] is None) != no_view:
        raise ExecutionContractError
    if record["state"] == "DONE":
        _check(_RESULTS[Operation(record["op"])], record["result"])
        if record["op"] == "exec":
            _validate_completed_receipt(record, record["result"]["receipt"])
        if op is Operation.PIN_READER and record["result"]["view_ref"]["access"] != "READ":
            raise ExecutionContractError
    elif record["result"] is not None:
        raise ExecutionContractError


class OperationJournal:
    def __init__(self, directory: Path, *, lock_timeout_ms: int) -> None:
        _positive_integer(lock_timeout_ms)
        if not directory.is_absolute() or ".." in directory.parts or directory == Path("/"):
            raise ExecutionContractError
        self._directory = directory
        self._lock_timeout = lock_timeout_ms / 1000
        self._supervisor_thread: int | None = None

    @contextmanager
    def single_supervisor(self) -> Iterator[None]:
        """Hold before startup recovery, through the accepting service lifetime."""
        try:
            with _private_artifact_directory(self._directory / ".supervisor") as fd:
                with _admission_lock(fd, deadline=time.monotonic() + self._lock_timeout):
                    self._supervisor_thread = get_ident()
                    try:
                        yield
                    finally:
                        self._supervisor_thread = None
        except OSError:
            raise JournalError("DURABILITY_UNKNOWN") from None

    @contextmanager
    def _transaction(self, *, deadline: float | None = None) -> Iterator[int]:
        if deadline is not None and (type(deadline) not in {int, float} or not math.isfinite(deadline)):
            raise ExecutionContractError
        if deadline is not None and deadline <= time.monotonic():
            raise JournalError("BACKEND_UNAVAILABLE")
        limit = time.monotonic() + self._lock_timeout
        if deadline is not None:
            limit = min(limit, deadline)
        acquired = False
        try:
            with _private_artifact_directory(self._directory) as fd:
                try:
                    with _admission_lock(fd, deadline=limit):
                        acquired = True
                        if deadline is not None and deadline <= time.monotonic():
                            raise JournalError("BACKEND_UNAVAILABLE")
                        yield fd
                except JournalError:
                    raise
                except OSError:
                    if not acquired:
                        # No transaction body ran: a contended/expired lock is
                        # backend unavailability, not uncertain durable state.
                        raise JournalError("BACKEND_UNAVAILABLE") from None
                    # A replace may already be visible when directory fsync fails.
                    raise JournalError("DURABILITY_UNKNOWN") from None
        except JournalError:
            raise
        except OSError:
            # Opening the private directory failed before any mutation began.
            raise JournalError("BACKEND_UNAVAILABLE") from None

    @staticmethod
    def _before_deadline(deadline: float | None) -> None:
        if deadline is not None and deadline <= time.monotonic():
            raise JournalError("BACKEND_UNAVAILABLE")

    @staticmethod
    def _name(operation_id: str) -> str:
        _hex_id(operation_id, "op-")
        return operation_id + ".json"

    def _read(self, fd: int, operation_id: str) -> dict[str, Any] | None:
        try:
            source = os.open(
                self._name(operation_id), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd
            )
        except FileNotFoundError:
            return None
        try:
            info = os.fstat(source)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_size > MAX_FRAME_BYTES
            ):
                raise JournalError("CORRUPT_STATE")
            raw = bytearray()
            while len(raw) <= MAX_FRAME_BYTES:
                chunk = os.read(source, min(65536, MAX_FRAME_BYTES + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            record = _loads(bytes(raw))
            _validate_record(record)
            if record["operation_id"] != operation_id:
                raise ExecutionContractError
            return record
        except ExecutionContractError:
            raise JournalError("CORRUPT_STATE") from None
        finally:
            os.close(source)

    @staticmethod
    def _write(fd: int, record: dict[str, Any], proof: str | None = None, issued: str | None = None) -> None:
        _validate_record(record)
        raw = encode_json(record)
        if any(secret.encode() in raw for secret in (proof, issued) if secret is not None):
            raise ExecutionContractError
        _replace_private_bytes(fd, record["operation_id"] + ".json", raw)

    def reserve(self, request: dict[str, Any], *, deadline: float | None = None) -> Reservation:
        req = decode_request(encode_json(request))  # Capture/validate, never retain raw credentials/input.
        self._before_deadline(deadline)
        op = Operation(req["op"])
        if op is Operation.HEALTH:
            raise ExecutionContractError
        namespace = NamespaceRef(**req["namespace"])
        view = None if req["view_ref"] is None else ViewRef.from_dict(req["view_ref"])
        record = {
            "schema_version": 1,
            "operation_id": "op-" + req["request_id"],
            "request_id": req["request_id"],
            "op": op.value,
            "namespace": req["namespace"],
            "view_ref": req["view_ref"],
            "input_sha256": operation_input_sha256(op, namespace, view, req["payload"]),
            "state": "RESERVED",
            "container_id": None,
            "cancel_requested": False,
            "result": None,
        }
        with self._transaction(deadline=deadline) as fd:
            previous = self._read(fd, record["operation_id"])
            self._before_deadline(deadline)
            if previous is not None:
                if any(
                    previous[key] != record[key]
                    for key in ("request_id", "op", "namespace", "view_ref", "input_sha256")
                ):
                    raise JournalError("COLLISION")
                return Reservation(False, previous)
            self._write(fd, record, req["capability"])
            return Reservation(True, record)

    def lookup(
        self, operation_id: str, namespace: NamespaceRef, *, deadline: float | None = None
    ) -> dict[str, Any] | None:
        with self._transaction(deadline=deadline) as fd:
            return self._bound(fd, operation_id, namespace, missing_ok=True)

    def _bound(
        self, fd: int, operation_id: str, namespace: NamespaceRef, *, missing_ok: bool = False
    ) -> dict[str, Any] | None:
        record = self._read(fd, operation_id)
        if record is None:
            if not missing_ok:
                raise JournalError("EXECUTION_UNKNOWN")
        elif record["namespace"] != namespace.to_dict():
            raise JournalError("UNAUTHORIZED")
        return record

    def begin(self, operation_id: str, namespace: NamespaceRef, *, deadline: float | None = None) -> None:
        """One claim BEFORE side effects/Docker create. Retry/restart never reclaims."""
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if record is None or record["state"] != "RESERVED" or record["cancel_requested"]:
                raise JournalError("EXECUTION_UNKNOWN")
            self._before_deadline(deadline)
            record["state"] = "EXECUTING"
            self._write(fd, record)

    def create_once(
        self,
        operation_id: str,
        namespace: NamespaceRef,
        *,
        input_sha256: str,
        create: Callable[[], str],
        deadline: float | None = None,
    ) -> str:
        """One bounded create RPC, write-ahead uncertainty, then durable CID.

        The dispatcher already claimed begin(). Hold the journal lock through
        create so cancellation linearizes before/after it, never in the middle.
        A lost create/CID-fsync reply NEVER regains creation permission.
        """
        _hex_id(input_sha256, "", 64)
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if (
                record is None
                or record["op"] != "exec"
                or record["state"] != "EXECUTING"
                or record["container_id"] is not None
                or record["cancel_requested"]
            ):
                raise JournalError("EXECUTION_UNKNOWN")
            if record["input_sha256"] != input_sha256:
                raise JournalError("COLLISION")
            self._before_deadline(deadline)
            record["state"] = "UNKNOWN"
            self._write(fd, record)
            self._before_deadline(deadline)
            container_id = create()
            _hex_id(container_id, "", 64)
            record.update(state="EXECUTING", container_id=container_id)
            self._write(fd, record)
            return container_id

    def record_container(
        self, operation_id: str, namespace: NamespaceRef, container_id: str, *, deadline: float | None = None
    ) -> None:
        _hex_id(container_id, "", 64)
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if record is None or record["op"] != "exec" or record["state"] != "EXECUTING":
                raise JournalError("EXECUTION_UNKNOWN")
            if record["container_id"] not in {None, container_id}:
                raise JournalError("COLLISION")
            self._before_deadline(deadline)
            record["container_id"] = container_id
            self._write(fd, record)

    @contextmanager
    def start_once(self, operation_id: str, namespace: NamespaceRef, *, deadline: float | None = None) -> Iterator[str]:
        """Write-ahead uncertainty and lock through ONE bounded Docker start RPC.

        The caller must set a finite daemon RPC timeout. Persisted cancellation
        linearizes before or after this critical section, never inside it. No
        retry can regain this claim; actual completion/reconciliation follows.
        """
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if (
                record is None
                or record["op"] != "exec"
                or record["state"] != "EXECUTING"
                or record["container_id"] is None
                or record["cancel_requested"]
            ):
                raise JournalError("EXECUTION_UNKNOWN")
            self._before_deadline(deadline)
            record["state"] = "UNKNOWN"
            self._write(fd, record)
            self._before_deadline(deadline)
            yield record["container_id"]

    def request_cancel(
        self,
        operation_id: str,
        namespace: NamespaceRef,
        *,
        view: ViewRef,
        deadline: float | None = None,
    ) -> None:
        if not isinstance(view, ViewRef):
            raise ExecutionContractError
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if record is None or record["op"] != "exec":
                raise JournalError("EXECUTION_UNKNOWN")
            if record["view_ref"] != view.to_dict():
                raise JournalError("UNAUTHORIZED")
            self._before_deadline(deadline)
            record["cancel_requested"] = True
            self._write(fd, record)

    def complete(
        self,
        operation_id: str,
        namespace: NamespaceRef,
        result: GrantReply | dict[str, Any],
        *,
        original_proof: str | None,
        deadline: float | None = None,
    ) -> None:
        """Trusted owner supplies an observed result; not an attestation factory."""
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if record is None:
                raise JournalError("EXECUTION_UNKNOWN")
            op = Operation(record["op"])
            if op in GRANT_OPERATIONS:
                if not isinstance(result, GrantReply) or result.operation != op:
                    raise ExecutionContractError
                public = result.to_journal_result(original_proof=original_proof)
                issued = result.capability
            else:
                if not isinstance(result, dict):
                    raise ExecutionContractError
                public, issued = copy.deepcopy(result), None
            _check(_RESULTS[op], public)
            if op is Operation.EXEC:
                _validate_completed_receipt(record, public["receipt"])
            self._before_deadline(deadline)
            if record["state"] == "DONE":
                if record["result"] != public:
                    raise JournalError("COLLISION")
                return
            if record["state"] not in {"EXECUTING", "UNKNOWN"}:
                raise JournalError("EXECUTION_UNKNOWN")
            record.update(state="DONE", result=public)
            self._write(fd, record, original_proof, issued)

    def mark_unknown(self, operation_id: str, namespace: NamespaceRef, *, deadline: float | None = None) -> None:
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if record is None:
                raise JournalError("EXECUTION_UNKNOWN")
            if record["state"] != "DONE":
                self._before_deadline(deadline)
                record.update(state="UNKNOWN", result=None)
                self._write(fd, record)

    def recover_uncertain(self) -> int:
        """Persist uncertainty only. Does NOT inspect Docker, drain or renew grants."""
        if self._supervisor_thread != get_ident():
            raise JournalError("EXECUTION_UNKNOWN")
        changed = 0
        with self._transaction() as fd:
            for name in os.listdir(fd):
                if name.startswith("op-") and name.endswith(".json"):
                    operation_id = name.removesuffix(".json")
                    try:
                        record = self._read(fd, operation_id)
                    except ExecutionContractError:
                        raise JournalError("CORRUPT_STATE") from None
                    if record is not None and record["state"] in {"RESERVED", "EXECUTING"}:
                        record.update(state="UNKNOWN", result=None)
                        self._write(fd, record)
                        changed += 1
        return changed

    def unfinished(self, *, deadline: float | None = None) -> list[dict[str, Any]]:
        """Read-only listing of uncertain exec records for restart reconciliation.

        This never creates, starts, re-runs or completes anything.
        """
        with self._transaction(deadline=deadline) as fd:
            records: list[dict[str, Any]] = []
            for name in sorted(os.listdir(fd)):
                self._before_deadline(deadline)
                if not name.startswith("op-") or not name.endswith(".json"):
                    continue
                try:
                    record = self._read(fd, name.removesuffix(".json"))
                except ExecutionContractError:
                    raise JournalError("CORRUPT_STATE") from None
                if record is None or record["op"] != "exec" or record["state"] == "DONE":
                    continue
                records.append(record)
            return records

    def owned_cells(self, *, deadline: float | None = None) -> list[dict[str, Any]]:
        """Read-only inventory of every exec record that still binds a cell ID.

        DONE is included: an interactive cell can outlive the command that
        created it. This inventory never starts, re-runs, completes or grants.
        """
        with self._transaction(deadline=deadline) as fd:
            records: list[dict[str, Any]] = []
            for name in sorted(os.listdir(fd)):
                self._before_deadline(deadline)
                if not name.startswith("op-") or not name.endswith(".json"):
                    continue
                try:
                    record = self._read(fd, name.removesuffix(".json"))
                except ExecutionContractError:
                    raise JournalError("CORRUPT_STATE") from None
                if record is not None and record["op"] == "exec" and record["container_id"] is not None:
                    records.append(record)
            return records

    @contextmanager
    def send_guard(
        self, operation_id: str, namespace: NamespaceRef, *, view: ViewRef, input_sha256: str, deadline: float
    ) -> Generator[None]:
        """Serialize cancel with ONE bounded frame write, never with reply waiting.

        This is a read-only guard, NOT begin/reclaim or a second RUN journal.
        The backend owns the sole send; original start may have left UNKNOWN.
        """
        _hex_id(input_sha256, "", 64)
        with self._transaction(deadline=deadline) as fd:
            record = self._bound(fd, operation_id, namespace)
            if (
                record is None
                or record["op"] != "exec"
                or record["state"] not in {"EXECUTING", "UNKNOWN"}
                or record["cancel_requested"]
                or record["view_ref"] != view.to_dict()
                or record["input_sha256"] != input_sha256
            ):
                raise JournalError("EXECUTION_UNKNOWN")
            yield
