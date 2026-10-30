"""Q74/§6.1 stage checkpoints: the boundary ordering and the ONE run sidecar.

Two facts live here, and nothing else does:

* **the boundary order** — a mutating episode ends only as *prove terminality →
  seal → publish → link one record*. Every step is an existing producer
  (`ViewStopper`, `publication.seal_view`, `publication.publish_view`); this
  module decides *when* they may run and what a refusal costs, never how they
  work. It creates no view, writes no canonical byte itself, and reserves no
  supervisor operation;
* **the run sidecar** (`execution.json` v1, spec §6.1) — the append-only list of
  what a boundary bound, so a later *managed* consumer can require a matching
  sidecar plus supervisor receipt. It records links (hashes and supervisor
  operation ids), never capabilities and never a verdict.

Two properties are structural rather than promised, because they were the two
ways a checkpoint could lie:

1. **A checkpoint is not success.** `CheckpointRecord` has no pass/fail field and
   `checkpoint_view` accepts no stage outcome, so a failed or interrupted stage
   that still checkpointed its allowed edits cannot be read as `DONE`. The stage
   result stays the stage loop's fact; this module never sees it.
2. **A live or unknown view cannot checkpoint.** The stop leg must *prove*
   `terminal is True`; anything else raises `TERMINALITY_UNKNOWN` with no seal, no
   publish and no record, which leaves the view `STOPPING` and the workspace
   owned — exactly the quarantine rule of CT104.

The sidecar's shape is fixed by the spec, not by taste: `{schema_version, run_id,
workspace_id, records}` with each record exactly `{kind, artifact_sha256,
plan_sha256, revision_id, original_revision_id, tree_sha256, operation_ids}`. A
record that grows a field is invalid rather than convenient.

Kinds, and who writes them: `STAGE` here; `T0`, `VERIFY` and `KILL` are the managed
baseline, verifier and kill-check producers (SLICE4 STEP3 onward), which append
through `ExecutionSidecar.append` when they exist. Declaring all four now is what
lets a consumer validate a document it did not write.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import fastjsonschema  # type: ignore[import-untyped]  # Existing schema library has no typing metadata.

from fa.execution.protocol import _check, encode_json
from fa.execution.publication import PublishResult, SealResult
from fa.execution.supervisor import SupervisorError, ViewStopResult
from fa.execution.types import ExecutionContractError, ViewRef
from fa.execution.workspace import _budget, _read_json
from fa.inner_loop.workflow_artifacts import (
    AdmissionIOError,
    _admission_lock,
    _private_artifact_directory,
    _replace_private_bytes,
)

SIDECAR_NAME = "execution.json"
# A run sidecar is a summary, not an event log: one record per boundary. The cap
# keeps a pathological loop from turning it into unbounded protected storage, and
# it is enforced on WRITE as well as on read — otherwise an over-long document
# would be persisted and then be unreadable forever (CORRUPT_STATE on every open).
_MAX_SIDECAR_BYTES = 1024**2


class CheckpointKind(StrEnum):
    """The four boundary kinds §6.1 freezes; only `STAGE` is written here."""

    T0 = "T0"
    STAGE = "STAGE"
    VERIFY = "VERIFY"
    KILL = "KILL"


_SHA = {"type": "string", "pattern": "^[0-9a-f]{64}\\Z"}
_OPERATION_ID = {"type": "string", "pattern": "^op-[0-9a-f]{32}\\Z"}
_RECORD = {
    "type": "object",
    "properties": {
        "kind": {"enum": [kind.value for kind in CheckpointKind]},
        "artifact_sha256": _SHA,
        "plan_sha256": _SHA,
        "revision_id": {"type": "string", "pattern": "^rev-[0-9a-f]{32}\\Z"},
        "original_revision_id": {"type": "string", "pattern": "^rev-[0-9a-f]{32}\\Z"},
        "tree_sha256": _SHA,
        "operation_ids": {"type": "array", "items": _OPERATION_ID, "minItems": 1, "uniqueItems": True},
    },
    "required": [
        "kind",
        "artifact_sha256",
        "plan_sha256",
        "revision_id",
        "original_revision_id",
        "tree_sha256",
        "operation_ids",
    ],
    "additionalProperties": False,
}
_SIDECAR = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "run_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "workspace_id": {"type": "string", "pattern": "^ws-[0-9a-f]{32}\\Z"},
        "records": {"type": "array", "items": _RECORD},
    },
    "required": ["schema_version", "run_id", "workspace_id", "records"],
    "additionalProperties": False,
}
_VALIDATE_RECORD = fastjsonschema.compile(_RECORD)
_VALIDATE_SIDECAR = fastjsonschema.compile(_SIDECAR)


@dataclass(frozen=True)
class CheckpointRecord:
    """One boundary's binding: what it committed and which supervisors proved it.

    `artifact_sha256` is the digest of the evidence artifact the caller persisted
    **before** the record (§6.1); `plan_sha256` is the plan in force at the
    boundary; `original_revision_id` is the base the checkpoint moved away from;
    `operation_ids` are the supervisor operations that carried it out. There is
    deliberately no outcome field: a checkpoint states *which bytes are current*,
    never that the stage succeeded.
    """

    kind: CheckpointKind
    artifact_sha256: str
    plan_sha256: str
    revision_id: str
    original_revision_id: str
    tree_sha256: str
    operation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, CheckpointKind) or not isinstance(self.operation_ids, tuple):
            raise ExecutionContractError
        _check(
            _VALIDATE_RECORD,
            {
                "kind": self.kind.value,
                "artifact_sha256": self.artifact_sha256,
                "plan_sha256": self.plan_sha256,
                "revision_id": self.revision_id,
                "original_revision_id": self.original_revision_id,
                "tree_sha256": self.tree_sha256,
                "operation_ids": list(self.operation_ids),
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "artifact_sha256": self.artifact_sha256,
            "plan_sha256": self.plan_sha256,
            "revision_id": self.revision_id,
            "original_revision_id": self.original_revision_id,
            "tree_sha256": self.tree_sha256,
            "operation_ids": list(self.operation_ids),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CheckpointRecord:
        return cls(
            kind=CheckpointKind(raw["kind"]),
            artifact_sha256=str(raw["artifact_sha256"]),
            plan_sha256=str(raw["plan_sha256"]),
            revision_id=str(raw["revision_id"]),
            original_revision_id=str(raw["original_revision_id"]),
            tree_sha256=str(raw["tree_sha256"]),
            operation_ids=tuple(str(value) for value in raw["operation_ids"]),
        )


class ExecutionSidecar:
    """The run's ONE `execution.json`: append-only, durable, bound to one run.

    Append-only is enforced by construction: every write carries the complete
    previous list plus exactly one record, so no record can be edited or dropped
    without a visible rewrite. The document is bound to its `run_id` and
    `workspace_id` on the first write and refuses to serve a different pair,
    because "this run's proof" is the only meaning the file has.
    """

    def __init__(self, run_dir: Path, *, run_id: str, workspace_id: str) -> None:
        if not isinstance(run_dir, Path) or not run_dir.is_absolute() or ".." in run_dir.parts:
            raise ExecutionContractError
        if not isinstance(run_id, str) or not run_id or len(run_id) > 128 or "\0" in run_id:
            raise ExecutionContractError
        if not isinstance(workspace_id, str) or len(workspace_id) != 35 or not workspace_id.startswith("ws-"):
            raise ExecutionContractError
        self._run_dir = run_dir
        self._run_id = run_id
        self._workspace_id = workspace_id

    @property
    def path(self) -> Path:
        return self._run_dir / SIDECAR_NAME

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def records(self) -> tuple[CheckpointRecord, ...]:
        """The complete ordered list; a missing file is an empty list, not an error."""
        try:
            with _private_artifact_directory(self._run_dir) as fd:
                return self._read(fd)
        except OSError:
            # No private run directory: nothing was read and nothing was written.
            raise SupervisorError("BACKEND_UNAVAILABLE") from None

    def append(self, record: CheckpointRecord, *, deadline: float) -> None:
        """Link one record, or fail loudly without disturbing what is already there.

        A publication that already committed is **not** undone here: a failure in
        this method is `DURABILITY_UNKNOWN` for the *link*, and the caller must
        treat the boundary as indeterminate rather than re-publishing (§6.1: "a
        crash between artifact/link is indeterminate").
        """
        if not isinstance(record, CheckpointRecord):
            raise ExecutionContractError
        _budget(deadline)
        opened = False
        try:
            with _private_artifact_directory(self._run_dir) as fd:
                opened = True
                with _admission_lock(fd, deadline=deadline):
                    existing = self._read(fd)
                    if any(set(record.operation_ids) == set(other.operation_ids) for other in existing):
                        # The same supervisor operations cannot describe two
                        # boundaries: this is a replayed append, not a new one.
                        raise SupervisorError("INPUT_POLICY")
                    document = {
                        "schema_version": 1,
                        "run_id": self._run_id,
                        "workspace_id": self._workspace_id,
                        "records": [entry.to_dict() for entry in (*existing, record)],
                    }
                    encoded = encode_json(document)
                    if len(encoded) > _MAX_SIDECAR_BYTES:
                        # Refused before any byte is written: an over-long
                        # document could never be read back.
                        raise SupervisorError("INPUT_POLICY")
                    _replace_private_bytes(fd, SIDECAR_NAME, encoded)
                    if self._read(fd) != (*existing, record):
                        raise SupervisorError("DURABILITY_UNKNOWN")
        except AdmissionIOError as error:
            # Contention before any byte was written is unavailability, not an
            # uncertain write; a failed replace after it is uncertainty.
            raise SupervisorError(
                "BACKEND_UNAVAILABLE" if not opened or error.rule == "lock-failed" else "DURABILITY_UNKNOWN"
            ) from None
        except OSError:
            # The run directory itself was unusable before anything was opened;
            # once it was open, only the write is uncertain.
            raise SupervisorError("DURABILITY_UNKNOWN" if opened else "BACKEND_UNAVAILABLE") from None

    def _read(self, fd: int) -> tuple[CheckpointRecord, ...]:
        try:
            raw = _read_json(fd, SIDECAR_NAME, _VALIDATE_SIDECAR, _MAX_SIDECAR_BYTES)
        except FileNotFoundError:
            return ()
        except SupervisorError:
            raise
        except OSError:
            raise SupervisorError("CORRUPT_STATE") from None
        if raw["run_id"] != self._run_id or raw["workspace_id"] != self._workspace_id:
            raise SupervisorError("CORRUPT_STATE")
        return tuple(CheckpointRecord.from_dict(entry) for entry in raw["records"])


class StageConnector(Protocol):
    """The three existing supervisor operations a boundary drives.

    Implemented over the wire in production (one request each) and over the real
    producers in the local bank: the policy is transport-agnostic by construction,
    because the boundary runs in the controller process while stop/seal/publish
    are supervisor operations. The `request_id` is the caller's, so the recorded
    `op-<request_id>` is the operation the dispatcher really reserved.
    """

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> ViewStopResult: ...

    def seal(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> SealResult: ...

    def publish(
        self,
        view: ViewRef,
        capability: str,
        *,
        sealed_manifest_id: str,
        expected_base_revision: str,
        request_id: str,
        deadline: float,
    ) -> PublishResult: ...


@dataclass(frozen=True)
class CheckpointRequests:
    """The three request ids this boundary will use; each becomes one operation id."""

    stop: str
    seal: str
    publish: str

    def __post_init__(self) -> None:
        for value in (self.stop, self.seal, self.publish):
            _hex(value)
        if len({self.stop, self.seal, self.publish}) != 3:
            # Reusing one id for two operations would collapse two journal
            # records into one and break the replay contract.
            raise ExecutionContractError

    @property
    def operation_ids(self) -> tuple[str, str, str]:
        return ("op-" + self.stop, "op-" + self.seal, "op-" + self.publish)


def checkpoint_view(
    connector: StageConnector,
    sidecar: ExecutionSidecar,
    *,
    view: ViewRef,
    capability: str,
    requests: CheckpointRequests,
    artifact_sha256: str,
    plan_sha256: str,
    deadline: float,
) -> CheckpointRecord:
    """Checkpoint one mutating episode: terminality, seal, publish, then one link.

    Written kind is always `STAGE`. The base it publishes from is the view's own
    `base_revision` — never a caller-supplied base — so the CAS guarding the
    pointer is the one the view was opened with.
    """
    if not callable(getattr(connector, "stop_view", None)) or not isinstance(sidecar, ExecutionSidecar):
        raise ExecutionContractError
    if not isinstance(view, ViewRef) or not isinstance(requests, CheckpointRequests):
        raise ExecutionContractError
    _budget(deadline)

    stopped = connector.stop_view(view, capability, request_id=requests.stop, deadline=deadline)
    if not isinstance(stopped, ViewStopResult) or stopped.view_id != view.view_id:
        raise SupervisorError("CORRUPT_STATE")
    if stopped.terminal is not True:
        # Not terminal, or not observed: the view stays owned and unsealed. No
        # seal and no publish may be attempted on a live candidate.
        raise SupervisorError("TERMINALITY_UNKNOWN")
    _budget(deadline)

    sealed = connector.seal(view, capability, request_id=requests.seal, deadline=deadline)
    if not isinstance(sealed, SealResult):
        raise SupervisorError("CORRUPT_STATE")
    _budget(deadline)

    published = connector.publish(
        view,
        capability,
        sealed_manifest_id=sealed.sealed_manifest_id,
        expected_base_revision=view.base_revision,
        request_id=requests.publish,
        deadline=deadline,
    )
    if not isinstance(published, PublishResult):
        raise SupervisorError("CORRUPT_STATE")
    # Publish commits the bytes seal froze, under the id seal derived, as the
    # caller's own operation. A disagreement means the wire or an adapter lied.
    if (
        published.revision_id != sealed.revision_id
        or published.tree_sha256 != sealed.tree_sha256
        or published.operation_id != "op-" + requests.publish
        or published.projection_complete is not True
    ):
        raise SupervisorError("CORRUPT_STATE")

    record = CheckpointRecord(
        kind=CheckpointKind.STAGE,
        artifact_sha256=artifact_sha256,
        plan_sha256=plan_sha256,
        revision_id=published.revision_id,
        original_revision_id=view.base_revision,
        tree_sha256=published.tree_sha256,
        operation_ids=requests.operation_ids,
    )
    sidecar.append(record, deadline=deadline)
    return record


def _hex(value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 32
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ExecutionContractError


__all__ = [
    "SIDECAR_NAME",
    "CheckpointKind",
    "CheckpointRecord",
    "CheckpointRequests",
    "ExecutionSidecar",
    "StageConnector",
    "checkpoint_view",
]
