"""E284 — Q74/§6.1 stage checkpoints: the boundary order and the ONE sidecar.

Classes (knowledge/skills/tests-writing):
  C0 — the artifact's shape: the seven frozen record keys, the closed sidecar
       document, three distinct request ids; an extra field is invalid, not
       convenient;
  C1 — the boundary over the real authority, real views, real bytes and the real
       `seal_view`/`publish_view` producers; only the kernel descendant fact is
       doubled at its seam (it cannot be produced in this process);
  C3 — the same policy bound to the composed supervisor over the real socket,
       so the recorded `operation_ids` are the ones the dispatcher reserved.

What must stay true (each test names the producer it kills):
  * a boundary is *prove terminality → seal → publish → link one record*, so a
    view that cannot prove terminality gets no seal, no publish and no record;
  * the linked revision is the committed one, its base is the view's own
    `base_revision`, and the operation ids are the caller's three requests;
  * an adapter that disagrees with the producers it drove is `CORRUPT_STATE`,
    never a record;
  * a checkpoint is **not** success: there is no field to read as `DONE`, so a
    failed stage that still checkpointed its allowed edits cannot be mistaken
    for one;
  * the sidecar is append-only, ordered, durable across a restart, bound to one
    run and workspace, carries no capability, and never reads a corrupt document
    as "no records";
  * a replayed boundary refuses rather than double-counting, and a failed link
    leaves the committed publication intact (`DURABILITY_UNKNOWN`).

Not claimed here: a real cell, a real cgroup, a deployed service or a live host.
No new live surface is declared on purpose (A1's plan row): the durable effects
are CT106's publish, the barrier is CT104, and the host proof belongs to SLICE6.
"""

from __future__ import annotations

import fcntl
import json
import os
import secrets
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

import fa.execution.checkpoints as checkpoints_module
from fa.execution.checkpoints import (
    CheckpointKind,
    CheckpointRecord,
    CheckpointRequests,
    ExecutionSidecar,
    checkpoint_view,
)
from fa.execution.protocol import encode_json
from fa.execution.publication import PublishResult, SealResult, publish_view, seal_view
from fa.execution.service import SupervisorService
from fa.execution.supervisor import SupervisorError, TerminalVerdict, ViewStopper, ViewStopResult
from fa.execution.types import ExecutionContractError, NamespaceRef, Operation, ViewRef
from fa.execution.workspace import WorkspaceAuthority
from fa.inner_loop.workflow_artifacts import _replace_private_bytes
from tests.test_execution_readers import ref
from tests.test_execution_service import _config, _registered, _writer, exchange
from tests.test_execution_service import _view as wire_view
from tests.test_execution_views import create, native_profile
from tests.test_execution_workspace import ACTOR, PEER, Site, ok, until
from tests.test_execution_workspace import site as site

SHA = "a" * 64
PLAN = "b" * 64
RUN = "run-checkpoints"


def requests() -> CheckpointRequests:
    return CheckpointRequests(secrets.token_hex(16), secrets.token_hex(16), secrets.token_hex(16))


def sample_record() -> CheckpointRecord:
    return CheckpointRecord(
        kind=CheckpointKind.STAGE,
        artifact_sha256=SHA,
        plan_sha256=PLAN,
        revision_id="rev-" + "c" * 32,
        original_revision_id="rev-" + "d" * 32,
        tree_sha256="e" * 64,
        operation_ids=("op-" + "1" * 32,),
    )


class LocalCells:
    """The kernel fact doubled at its seam, exactly as CT104's own bank does."""

    def __init__(self, verdicts: list[bool | None]) -> None:
        self.verdicts = verdicts
        self.polls = 0

    def stop_cells(self, namespace: NamespaceRef, view_ref: ViewRef, *, deadline: float) -> None:
        assert isinstance(namespace, NamespaceRef) and isinstance(view_ref, ViewRef)

    def cells_terminal(self, namespace: NamespaceRef, view_ref: ViewRef) -> bool | None:
        self.polls += 1
        return self.verdicts[min(self.polls - 1, len(self.verdicts) - 1)]


class LocalStages:
    """The three existing producers bound in-process (C1's half of the seam)."""

    def __init__(self, owner: WorkspaceAuthority, *, verdicts: list[bool | None] | None = None) -> None:
        self.owner = owner
        self.verdicts: list[bool | None] = [True] if verdicts is None else verdicts
        self.calls: list[str] = []

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> ViewStopResult:
        self.calls.append("stop")
        stopper = ViewStopper(self.owner, cells=LocalCells(self.verdicts), poll_interval_s=0.001)
        return stopper.stop_view(PEER, ACTOR, view_ref=view, capability=capability, deadline=deadline)

    def seal(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> SealResult:
        self.calls.append("seal")
        return seal_view(self.owner, PEER, ACTOR, view_ref=view, capability=capability, deadline=deadline)

    def publish(
        self,
        view: ViewRef,
        capability: str,
        *,
        sealed_manifest_id: str,
        expected_base_revision: str,
        request_id: str,
        deadline: float,
    ) -> PublishResult:
        self.calls.append("publish")
        return publish_view(
            self.owner,
            PEER,
            ACTOR,
            view_ref=view,
            capability=capability,
            sealed_manifest_id=sealed_manifest_id,
            expected_base_revision=expected_base_revision,
            operation_id="op-" + request_id,
            deadline=deadline,
        )


class LyingStages(LocalStages):
    """A stage adapter that reports something the producers did not do."""

    def __init__(self, owner: WorkspaceAuthority, lie: str) -> None:
        super().__init__(owner)
        self.lie = lie

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> ViewStopResult:
        result = super().stop_view(view, capability, request_id=request_id, deadline=deadline)
        if self.lie == "unknown-view":
            return ViewStopResult("view-" + "0" * 32, result.terminal, result.verdict)
        return result

    def publish(
        self,
        view: ViewRef,
        capability: str,
        *,
        sealed_manifest_id: str,
        expected_base_revision: str,
        request_id: str,
        deadline: float,
    ) -> PublishResult:
        result = super().publish(
            view,
            capability,
            sealed_manifest_id=sealed_manifest_id,
            expected_base_revision=expected_base_revision,
            request_id=request_id,
            deadline=deadline,
        )
        if self.lie == "revision":
            return replace(result, revision_id="rev-" + "0" * 32)
        if self.lie == "tree":
            return replace(result, tree_sha256="d" * 64)
        if self.lie == "operation":
            return replace(result, operation_id="op-" + "0" * 32)
        if self.lie == "incomplete":
            return replace(result, projection_complete=False)
        return result


class SilentStages:
    """An adapter with the right method names and no answers at all."""

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> Any:
        return None

    def seal(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> Any:
        return None

    def publish(
        self,
        view: ViewRef,
        capability: str,
        *,
        sealed_manifest_id: str,
        expected_base_revision: str,
        request_id: str,
        deadline: float,
    ) -> Any:
        return None


class TruthyStop(LocalStages):
    """A real terminal stop, reported as truthy-but-not-``True``."""

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> ViewStopResult:
        super().stop_view(view, capability, request_id=request_id, deadline=deadline)
        return ViewStopResult(view.view_id, cast(bool, 1), TerminalVerdict.TERMINAL)


class WrongTypes:
    """A stop answer of the right type, then a seal that is not a `SealResult`."""

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> Any:
        return ViewStopResult(view.view_id, True, TerminalVerdict.TERMINAL)

    def seal(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> Any:
        return "sealed"

    def publish(
        self,
        view: ViewRef,
        capability: str,
        *,
        sealed_manifest_id: str,
        expected_base_revision: str,
        request_id: str,
        deadline: float,
    ) -> Any:
        return None


class WrongPublish:
    """A well-typed seal reply, then a publish that is not a `PublishResult`."""

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> Any:
        return ViewStopResult(view.view_id, True, TerminalVerdict.TERMINAL)

    def seal(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> Any:
        return SealResult("seal-" + "0" * 32, "rev-" + "0" * 32, "f" * 64)

    def publish(
        self,
        view: ViewRef,
        capability: str,
        *,
        sealed_manifest_id: str,
        expected_base_revision: str,
        request_id: str,
        deadline: float,
    ) -> Any:
        return None


def dummy_view() -> ViewRef:
    return ViewRef.from_dict(
        {
            "workspace_id": "ws-" + "0" * 32,
            "view_id": "view-" + "0" * 32,
            "base_revision": "rev-" + "0" * 32,
            "owner_run_id": "run-a",
            "generation": 1,
            "access": "WRITE",
            "purpose": "PROJECT",
        }
    )


def sidecar(site: Site, workspace_id: str, run: str = RUN) -> ExecutionSidecar:
    return ExecutionSidecar(site.state.parent / run, run_id=run, workspace_id=workspace_id)


def root_of(site: Site, grant: Any) -> Path:
    reference = ref(grant)
    return site.state / "workspaces" / reference.workspace_id / "views" / reference.view_id


def state_of(site: Site, grant: Any) -> str:
    value = json.loads((root_of(site, grant) / "view.json").read_text())
    assert isinstance(value, dict)
    return str(value["state"])


def open_view(site: Site, owner: WorkspaceAuthority) -> tuple[dict[str, str], Any, Any]:
    """Register a workspace, claim it, open one writable view, write one file."""
    ids = ok(lambda: site.register(owner))
    lease = ok(lambda: site.claim(owner, ids))
    view = create(owner, ids, lease)
    written = owner.write_file(
        PEER,
        ACTOR,
        view_ref=ref(view),
        capability=view.capability,
        path="episode.txt",
        content="checked in\n",
        expected_sha256=None,
        deadline=until(),
    )
    assert written["bytes"] == len("checked in\n")
    return ids, lease, view


# ---------------------------------------------------------------------------
# C0 — the artifact's shape
# ---------------------------------------------------------------------------


def test_a_record_is_exactly_the_seven_frozen_keys() -> None:
    """producer-kill-check: smuggle a stage verdict or a capability into a record."""
    record = CheckpointRecord(
        kind=CheckpointKind.STAGE,
        artifact_sha256=SHA,
        plan_sha256=PLAN,
        revision_id="rev-" + "c" * 32,
        original_revision_id="rev-" + "d" * 32,
        tree_sha256="e" * 64,
        operation_ids=("op-" + "1" * 32, "op-" + "2" * 32, "op-" + "3" * 32),
    )
    assert list(record.to_dict()) == [
        "kind",
        "artifact_sha256",
        "plan_sha256",
        "revision_id",
        "original_revision_id",
        "tree_sha256",
        "operation_ids",
    ]
    # "A checkpoint is not success" is structural: there is no field to read.
    assert not {"status", "passed", "outcome", "result", "success", "verdict"} & set(record.to_dict())
    assert CheckpointRecord.from_dict(record.to_dict()) == record
    # A kind is the closed enum, not its text; operation ids are one tuple.
    for broken in ({**record.to_dict(), "kind": "STAGE"}, {**record.to_dict(), "operation_ids": ["op-" + "1" * 32]}):
        with pytest.raises(ExecutionContractError):
            CheckpointRecord(**broken)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("artifact_sha256", "not-a-sha"),
        ("plan_sha256", "B" * 64),
        ("revision_id", "rev-short"),
        ("tree_sha256", "e" * 63),
        ("operation_ids", ()),
        ("operation_ids", ("op-" + "1" * 32, "op-" + "1" * 32)),
        ("operation_ids", ("1" * 32,)),
    ],
)
def test_a_record_with_an_invalid_field_is_refused(field: str, value: Any) -> None:
    """producer-kill-check: validate a record leniently (or not at all)."""
    values: dict[str, Any] = {
        "kind": CheckpointKind.STAGE,
        "artifact_sha256": SHA,
        "plan_sha256": PLAN,
        "revision_id": "rev-" + "c" * 32,
        "original_revision_id": "rev-" + "d" * 32,
        "tree_sha256": "e" * 64,
        "operation_ids": ("op-" + "1" * 32,),
    }
    values[field] = value
    with pytest.raises(ExecutionContractError):
        CheckpointRecord(**values)


def test_an_unknown_kind_is_not_a_kind() -> None:
    """producer-kill-check: accept a free-text kind a consumer cannot validate."""
    # The four kinds §6.1 freezes: SLICE4's producers append the other three.
    assert {kind.value for kind in CheckpointKind} == {"T0", "STAGE", "VERIFY", "KILL"}
    with pytest.raises(ValueError):
        CheckpointKind("STAGE-DONE")


def test_the_three_request_ids_must_be_distinct_and_hex() -> None:
    """producer-kill-check: let one request id describe two supervisor operations."""
    three = requests()
    assert three.operation_ids == ("op-" + three.stop, "op-" + three.seal, "op-" + three.publish)
    with pytest.raises(ExecutionContractError):
        CheckpointRequests("1" * 32, "1" * 32, "3" * 32)
    with pytest.raises(ExecutionContractError):
        CheckpointRequests("z" * 32, "2" * 32, "3" * 32)
    with pytest.raises(ExecutionContractError):
        CheckpointRequests("1" * 31, "2" * 32, "3" * 32)


def test_the_sidecar_refuses_its_own_construction_outside_one_run(site: Site) -> None:
    """producer-kill-check: accept a relative path, an empty run or a fake workspace id."""
    workspace_id = "ws-" + "1" * 32
    proof = ExecutionSidecar(site.state.parent / RUN, run_id=RUN, workspace_id=workspace_id)
    assert proof.run_id == RUN and proof.workspace_id == workspace_id
    for run_dir, run_id, owner in (
        (Path("relative"), RUN, workspace_id),
        (site.state.parent / RUN, "", workspace_id),
        (site.state.parent / RUN, RUN, "ws-short"),
        (site.state.parent / RUN / ".." / RUN, RUN, workspace_id),
    ):
        with pytest.raises(ExecutionContractError):
            ExecutionSidecar(run_dir, run_id=run_id, workspace_id=owner)


def plant(run_dir: Path, document: object, *, mode: int = 0o600) -> ExecutionSidecar:
    """Write a sidecar as the private 0600 artifact it must be, then open it."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "execution.json"
    path.write_text(document if isinstance(document, str) else json.dumps(document))
    path.chmod(mode)
    return ExecutionSidecar(run_dir, run_id=RUN, workspace_id="ws-" + "1" * 32)


def test_the_sidecar_refuses_another_runs_or_workspaces_document(site: Site) -> None:
    """producer-kill-check: read a sidecar without checking whose proof it is."""
    run_dir = site.state.parent / RUN
    document = {"schema_version": 1, "run_id": RUN, "workspace_id": "ws-" + "1" * 32, "records": []}
    assert plant(run_dir, document).records() == ()
    for run_id, workspace_id in (("run-other", "ws-" + "1" * 32), (RUN, "ws-" + "2" * 32)):
        with pytest.raises(SupervisorError) as refusal:
            ExecutionSidecar(run_dir, run_id=run_id, workspace_id=workspace_id).records()
        assert refusal.value.code == "CORRUPT_STATE"


def test_a_corrupt_sidecar_is_never_read_as_no_records(site: Site) -> None:
    """producer-kill-check: swallow an unreadable document and answer 'no records'."""
    run_dir = site.state.parent / RUN
    good = {"schema_version": 1, "run_id": RUN, "workspace_id": "ws-" + "1" * 32, "records": []}
    broken_documents: tuple[object, ...] = (
        {**good, "unexpected": True},
        {**good, "schema_version": 2},
        {**good, "records": [{"kind": "STAGE"}]},
        {**good, "records": [{**sample_record().to_dict(), "verdict": "DONE"}]},
        json.dumps(good)[:-12],
        "not json at all",
    )
    for broken in broken_documents:
        with pytest.raises(SupervisorError) as refusal:
            plant(run_dir, broken).records()
        assert refusal.value.code == "CORRUPT_STATE", broken


def test_a_symlinked_sidecar_or_run_directory_is_refused(site: Site) -> None:
    """producer-kill-check: follow a link into someone else's proof."""
    real_dir = site.state.parent / "real-run"
    real_dir.mkdir(parents=True)
    (real_dir / "execution.json").write_text(
        json.dumps({"schema_version": 1, "run_id": RUN, "workspace_id": "ws-" + "1" * 32, "records": []})
    )
    (real_dir / "execution.json").chmod(0o600)
    linked = site.state.parent / RUN
    linked.symlink_to(real_dir)
    outside = ExecutionSidecar(linked, run_id=RUN, workspace_id="ws-" + "1" * 32)
    with pytest.raises(SupervisorError) as refusal:
        outside.records()
    assert refusal.value.code == "BACKEND_UNAVAILABLE"
    # A write through a linked run directory is unavailability, not an uncertain
    # write: it never reached a byte of this run's document.
    with pytest.raises(SupervisorError) as refusal:
        outside.append(sample_record(), deadline=until())
    assert refusal.value.code == "BACKEND_UNAVAILABLE"

    # And a link *inside* the run directory is not a sidecar.
    (real_dir / "execution.json").unlink()
    (site.state.parent / "target.json").write_text("{}")
    (site.state.parent / "target.json").chmod(0o600)
    (real_dir / "execution.json").symlink_to(site.state.parent / "target.json")
    with pytest.raises(SupervisorError) as refusal:
        ExecutionSidecar(real_dir, run_id=RUN, workspace_id="ws-" + "1" * 32).records()
    assert refusal.value.code == "CORRUPT_STATE"


def test_a_sidecar_another_user_could_edit_is_corrupt_not_empty(site: Site) -> None:
    """producer-kill-check: drop the private-mode check and trust a shared file."""
    good = {"schema_version": 1, "run_id": RUN, "workspace_id": "ws-" + "1" * 32, "records": []}
    with pytest.raises(SupervisorError) as refusal:
        plant(site.state.parent / RUN, good, mode=0o644).records()
    assert refusal.value.code == "CORRUPT_STATE"


def test_the_boundary_refuses_inputs_it_cannot_prove(site: Site) -> None:
    """producer-kill-check: accept a non-record, a non-connector or a spent budget."""
    proof = sidecar(site, "ws-" + "1" * 32)
    record = sample_record()
    with pytest.raises(ExecutionContractError):
        proof.append(cast(Any, "not-a-record"), deadline=until())
    with pytest.raises(ExecutionContractError):
        proof.append(record, deadline=float("nan"))
    with pytest.raises(SupervisorError) as spent:
        proof.append(record, deadline=time.monotonic() - 1)
    assert spent.value.code == "BACKEND_UNAVAILABLE"
    with pytest.raises(ExecutionContractError):
        checkpoint_view(
            cast(Any, object()),
            proof,
            view=cast(Any, "nope"),
            capability="c",
            requests=requests(),
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )
    with pytest.raises(ExecutionContractError):
        checkpoint_view(
            cast(Any, SilentStages()),
            proof,
            view=cast(Any, "nope"),
            capability="c",
            requests=requests(),
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )
    # An adapter that answers nothing, or the wrong type, is CORRUPT_STATE — the
    # module never coerces a missing reply into a boundary.
    for connector in (SilentStages(), WrongTypes(), WrongPublish()):
        with pytest.raises(SupervisorError) as refusal:
            checkpoint_view(
                cast(Any, connector),
                proof,
                view=dummy_view(),
                capability="c",
                requests=requests(),
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=until(),
            )
        assert refusal.value.code == "CORRUPT_STATE"
    assert proof.records() == ()


def test_an_absent_sidecar_reads_as_no_records_and_is_not_created(site: Site) -> None:
    """producer-kill-check: fail a first boundary because the file does not exist yet."""
    proof = sidecar(site, "ws-" + "1" * 32)
    assert proof.records() == ()
    assert not proof.path.exists()


# ---------------------------------------------------------------------------
# C1 — the boundary over the real authority and the real producers
# ---------------------------------------------------------------------------


def test_a_checkpoint_publishes_the_episode_and_links_exactly_one_record(site: Site) -> None:
    """producer-kill-check: drop the stop, the seal, the publish or the link."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, lease, view = open_view(site, owner)
        stages = LocalStages(owner)
        planned = requests()

        record = checkpoint_view(
            stages,
            sidecar(site, ids["workspace_id"]),
            view=ref(view),
            capability=view.capability,
            requests=planned,
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )

        # The order IS the policy: nothing may run before terminality is proved.
        assert stages.calls == ["stop", "seal", "publish"]
        assert record.kind is CheckpointKind.STAGE
        assert record.artifact_sha256 == SHA and record.plan_sha256 == PLAN
        assert record.original_revision_id == ids["revision_id"] == ref(view).base_revision
        assert record.operation_ids == planned.operation_ids
        assert record.revision_id != record.original_revision_id

        # The bytes are canonical and the pointer moved to exactly this revision.
        assert (site.source / "episode.txt").read_text() == "checked in\n"
        current = json.loads((site.state / "workspaces" / ids["workspace_id"] / "current.json").read_text())
        assert current["revision_id"] == record.revision_id
        assert current["tree_sha256"] == record.tree_sha256
        assert state_of(site, view) == "PUBLISHED"

        # Exactly one record in the frozen document, with no capability in it.
        raw = sidecar(site, ids["workspace_id"]).path.read_bytes()
        document = json.loads(raw)
        assert document["schema_version"] == 1 and document["run_id"] == RUN
        assert document["workspace_id"] == ids["workspace_id"]
        assert document["records"] == [record.to_dict()]
        assert view.capability.encode() not in raw and lease.capability.encode() not in raw

        assert ok(lambda: site.release(owner, ids, lease)) == {"released": True}


@pytest.mark.parametrize("verdict", [False, None])
def test_a_view_that_cannot_prove_terminality_never_seals(site: Site, verdict: bool | None) -> None:
    """producer-kill-check: treat 'not yet empty' or 'unobservable' as terminality."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, lease, view = open_view(site, owner)
        stages = LocalStages(owner, verdicts=[verdict])
        # A populated observation is polled to the deadline; keep that short.
        deadline = until() if verdict is None else time.monotonic() + 0.25

        with pytest.raises(SupervisorError) as refusal:
            checkpoint_view(
                stages,
                sidecar(site, ids["workspace_id"]),
                view=ref(view),
                capability=view.capability,
                requests=requests(),
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=deadline,
            )

        assert refusal.value.code == "TERMINALITY_UNKNOWN"
        # The refusal is honest about where it stopped: no seal, no publish, no record.
        assert stages.calls == ["stop"]
        assert state_of(site, view) == "STOPPING"
        assert not (root_of(site, view) / "sealed.json").exists()
        assert sidecar(site, ids["workspace_id"]).records() == ()

        # And the workspace is still owned: an unsettled view keeps the grant.
        with pytest.raises(SupervisorError) as busy:
            site.release(owner, ids, lease)
        assert busy.value.code == "WORKSPACE_BUSY"


def test_only_a_positive_true_is_terminality(site: Site) -> None:
    """producer-kill-check: accept truthiness instead of the wire's `True`."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        stages = TruthyStop(owner)
        with pytest.raises(SupervisorError) as refusal:
            checkpoint_view(
                stages,
                sidecar(site, ids["workspace_id"]),
                view=ref(view),
                capability=view.capability,
                requests=requests(),
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=until(),
            )
        assert refusal.value.code == "TERMINALITY_UNKNOWN"
        assert stages.calls == ["stop"]
        assert sidecar(site, ids["workspace_id"]).records() == ()
        assert not (root_of(site, view) / "sealed.json").exists()


@pytest.mark.parametrize("lie", ["unknown-view", "revision", "tree", "operation", "incomplete"])
def test_an_adapter_that_lies_is_never_linked(site: Site, lie: str) -> None:
    """producer-kill-check: trust the adapter's stop/seal/publish replies."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        with pytest.raises(SupervisorError) as refusal:
            checkpoint_view(
                LyingStages(owner, lie),
                sidecar(site, ids["workspace_id"]),
                view=ref(view),
                capability=view.capability,
                requests=requests(),
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=until(),
            )
        assert refusal.value.code == "CORRUPT_STATE"
        assert sidecar(site, ids["workspace_id"]).records() == ()


def test_a_replayed_boundary_cannot_append_a_second_record(site: Site) -> None:
    """producer-kill-check: append a duplicate record for a repeated boundary."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        stages = LocalStages(owner)
        planned = requests()
        first = checkpoint_view(
            stages,
            sidecar(site, ids["workspace_id"]),
            view=ref(view),
            capability=view.capability,
            requests=planned,
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )
        before = sidecar(site, ids["workspace_id"]).path.read_bytes()

        # The same boundary retried: a PUBLISHED view is closed, so the replay
        # refuses before it can reach the link again.
        with pytest.raises(SupervisorError) as refusal:
            checkpoint_view(
                stages,
                sidecar(site, ids["workspace_id"]),
                view=ref(view),
                capability=view.capability,
                requests=planned,
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=until(),
            )
        assert refusal.value.code == "VIEW_CLOSED"
        assert sidecar(site, ids["workspace_id"]).path.read_bytes() == before
        assert sidecar(site, ids["workspace_id"]).records() == (first,)


def test_the_sidecar_refuses_one_record_twice(site: Site) -> None:
    """producer-kill-check: append a record whose operations already have a link."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        proof = sidecar(site, ids["workspace_id"])
        first = checkpoint_view(
            LocalStages(owner),
            proof,
            view=ref(view),
            capability=view.capability,
            requests=requests(),
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )
        before = proof.path.read_bytes()

        with pytest.raises(SupervisorError) as refusal:
            proof.append(first, deadline=until())
        assert refusal.value.code == "INPUT_POLICY"
        assert proof.path.read_bytes() == before
        assert proof.records() == (first,)


def test_the_sidecar_survives_a_restart_and_keeps_its_order(site: Site) -> None:
    """producer-kill-check: rewrite the document from scratch on each append."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, lease, first_view = open_view(site, owner)
        first = checkpoint_view(
            LocalStages(owner),
            sidecar(site, ids["workspace_id"]),
            view=ref(first_view),
            capability=first_view.capability,
            requests=requests(),
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )
        assert ok(lambda: site.release(owner, ids, lease)) == {"released": True}

    # A new process opens the same run directory: the proof is still there and a
    # second boundary appends after it rather than replacing it.
    with site.owner(view_profile=native_profile()) as owner:
        assert site.metadata(ids)["status"] == "AVAILABLE"
        lease = ok(lambda: site.claim(owner, ids))
        second_view = create(owner, ids, lease)
        owner.write_file(
            PEER,
            ACTOR,
            view_ref=ref(second_view),
            capability=second_view.capability,
            path="second.txt",
            content="after restart\n",
            expected_sha256=None,
            deadline=until(),
        )
        second = checkpoint_view(
            LocalStages(owner),
            sidecar(site, ids["workspace_id"]),
            view=ref(second_view),
            capability=second_view.capability,
            requests=requests(),
            artifact_sha256="c" * 64,
            plan_sha256=PLAN,
            deadline=until(),
        )

    assert sidecar(site, ids["workspace_id"]).records() == (first, second)
    # The second boundary moved away from the first one's committed revision.
    assert second.original_revision_id == first.revision_id
    assert second.revision_id != first.revision_id
    assert (site.source / "second.txt").read_text() == "after restart\n"


def test_a_failed_link_is_uncertainty_and_keeps_the_committed_publication(
    site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    """producer-kill-check: swallow a failed append, or roll the commit back."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        stages = LocalStages(owner)

        def broken(directory_fd: int, name: str, raw: bytes) -> None:
            raise OSError("no space")

        monkeypatch.setattr(checkpoints_module, "_replace_private_bytes", broken)
        with pytest.raises(SupervisorError) as failure:
            checkpoint_view(
                stages,
                sidecar(site, ids["workspace_id"]),
                view=ref(view),
                capability=view.capability,
                requests=requests(),
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=until(),
            )

        assert failure.value.code == "DURABILITY_UNKNOWN"
        # The publish really happened and is NOT undone by the failed link.
        assert stages.calls == ["stop", "seal", "publish"]
        assert (site.source / "episode.txt").read_text() == "checked in\n"
        assert state_of(site, view) == "PUBLISHED"
        assert sidecar(site, ids["workspace_id"]).records() == ()


def test_an_over_long_sidecar_is_refused_before_it_is_written(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: persist a document that the reader will refuse forever."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        proof = sidecar(site, ids["workspace_id"])
        # One record is a few hundred bytes; cap the document just above it.
        monkeypatch.setattr(checkpoints_module, "_MAX_SIDECAR_BYTES", 700)
        first = checkpoint_view(
            LocalStages(owner),
            proof,
            view=ref(view),
            capability=view.capability,
            requests=requests(),
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )
        size = len(proof.path.read_bytes())
        assert 0 < size <= 700, size
        before = proof.path.read_bytes()

        monkeypatch.setattr(checkpoints_module, "_MAX_SIDECAR_BYTES", size + 10)
        second = replace(first, operation_ids=("op-" + "9" * 32,))
        with pytest.raises(SupervisorError) as refusal:
            proof.append(second, deadline=until())
        assert refusal.value.code == "INPUT_POLICY"
        assert proof.path.read_bytes() == before
        assert proof.records() == (first,)


def test_a_link_that_does_not_read_back_is_uncertain(site: Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """producer-kill-check: skip the read-back equality after the replace."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        stages = LocalStages(owner)
        real = _replace_private_bytes

        def forgetful(directory_fd: int, name: str, raw: bytes) -> None:
            document = json.loads(raw)
            document["records"] = []
            real(directory_fd, name, encode_json(document))

        monkeypatch.setattr(checkpoints_module, "_replace_private_bytes", forgetful)
        with pytest.raises(SupervisorError) as failure:
            checkpoint_view(
                stages,
                sidecar(site, ids["workspace_id"]),
                view=ref(view),
                capability=view.capability,
                requests=requests(),
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=until(),
            )

        assert failure.value.code == "DURABILITY_UNKNOWN"
        assert stages.calls == ["stop", "seal", "publish"]
        assert sidecar(site, ids["workspace_id"]).records() == ()


def test_contention_on_the_run_sidecar_is_unavailability_not_uncertainty(site: Site) -> None:
    """producer-kill-check: report every admission failure as DURABILITY_UNKNOWN."""
    run_dir = site.state.parent / RUN
    run_dir.mkdir(parents=True)
    run_dir.chmod(0o700)
    lock = os.open(run_dir / ".admission.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        record = sample_record()
        with pytest.raises(SupervisorError) as refusal:
            sidecar(site, "ws-" + "1" * 32).append(record, deadline=time.monotonic() + 0.3)
        assert refusal.value.code == "BACKEND_UNAVAILABLE"
        assert not sidecar(site, "ws-" + "1" * 32).path.exists()
    finally:
        os.close(lock)


def test_a_failed_stage_still_checkpoints_its_allowed_edits(site: Site) -> None:
    """producer-kill-check: gate the boundary on a stage outcome, or record one."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        # The stage loop's own fact. §6.1: a nonzero/interrupted stage makes the
        # same bounded stop/seal attempt, and the checkpoint never turns it into
        # DONE — the boundary is not even told, which is what makes that structural.
        stage_failed = True

        record = checkpoint_view(
            LocalStages(owner),
            sidecar(site, ids["workspace_id"]),
            view=ref(view),
            capability=view.capability,
            requests=requests(),
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )

        assert stage_failed is True
        assert state_of(site, view) == "PUBLISHED"
        raw = sidecar(site, ids["workspace_id"]).path.read_bytes().decode()
        assert json.loads(raw)["records"] == [record.to_dict()]
        assert "DONE" not in raw and "success" not in raw and "passed" not in raw


def test_a_quarantined_workspace_cannot_checkpoint(site: Site) -> None:
    """producer-kill-check: let a stale grant checkpoint after a restart."""
    with site.owner(view_profile=native_profile()) as owner:
        ids, _lease, view = open_view(site, owner)
        proof = sidecar(site, ids["workspace_id"])
    # The grant was never released, so startup must quarantine the workspace.
    with site.owner(view_profile=native_profile()) as recovered:
        assert site.metadata(ids)["status"] == "QUARANTINED"
        with pytest.raises(SupervisorError) as refusal:
            checkpoint_view(
                LocalStages(recovered),
                proof,
                view=ref(view),
                capability=view.capability,
                requests=requests(),
                artifact_sha256=SHA,
                plan_sha256=PLAN,
                deadline=until(),
            )
        assert refusal.value.code == "UNAUTHORIZED"
        assert proof.records() == ()
        assert state_of(site, view) == "OPEN"


# ---------------------------------------------------------------------------
# C3 — the policy bound to the composed service over the real socket
# ---------------------------------------------------------------------------


class WireStages:
    """The same three operations as supervisor requests, as production drives them."""

    def __init__(self, service: SupervisorService) -> None:
        self.service = service
        self.requests: list[tuple[str, str]] = []

    def stop_view(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> ViewStopResult:
        self.requests.append(("stop_view", request_id))
        reply = exchange(
            self.service, Operation.STOP_VIEW, {}, request_id=request_id, view_ref=view.to_dict(), capability=capability
        )
        assert reply["status"] == "OK", reply
        result = reply["result"]
        # The wire fact is `terminal` alone; the adapter may not invent a verdict
        # beyond it, and the policy only ever reads `.terminal`.
        verdict = TerminalVerdict.TERMINAL if result["terminal"] else TerminalVerdict.UNKNOWN
        return ViewStopResult(str(result["view_id"]), bool(result["terminal"]), verdict)

    def seal(self, view: ViewRef, capability: str, *, request_id: str, deadline: float) -> SealResult:
        self.requests.append(("seal", request_id))
        reply = exchange(
            self.service, Operation.SEAL, {}, request_id=request_id, view_ref=view.to_dict(), capability=capability
        )
        assert reply["status"] == "OK", reply
        return SealResult(**reply["result"])

    def publish(
        self,
        view: ViewRef,
        capability: str,
        *,
        sealed_manifest_id: str,
        expected_base_revision: str,
        request_id: str,
        deadline: float,
    ) -> PublishResult:
        self.requests.append(("publish", request_id))
        reply = exchange(
            self.service,
            Operation.PUBLISH,
            {"sealed_manifest_id": sealed_manifest_id, "expected_base_revision": expected_base_revision},
            request_id=request_id,
            view_ref=view.to_dict(),
            capability=capability,
        )
        assert reply["status"] == "OK", reply
        return PublishResult(**reply["result"])


def test_the_recorded_operation_ids_are_the_ones_the_dispatcher_reserved(site: Site) -> None:
    """producer-kill-check: record invented or recycled operation ids."""
    with SupervisorService(_config(site)) as service:
        workspace_id = _registered(service)
        capability, revision_id = _writer(service, workspace_id, request_id="c" * 32)
        view_ref, view_capability = wire_view(service, workspace_id, revision_id, capability, request_id="d" * 32)
        written = exchange(
            service,
            Operation.WRITE_FILE,
            {"path": "note.txt", "content": "wire checkpoint\n", "expected_sha256": None},
            request_id="2" * 32,
            view_ref=view_ref,
            capability=view_capability,
        )
        assert written["status"] == "OK", written

        stages = WireStages(service)
        planned = requests()
        record = checkpoint_view(
            stages,
            sidecar(site, workspace_id),
            view=ViewRef.from_dict(view_ref),
            capability=view_capability,
            requests=planned,
            artifact_sha256=SHA,
            plan_sha256=PLAN,
            deadline=until(),
        )

        assert [name for name, _ in stages.requests] == ["stop_view", "seal", "publish"]
        for operation_id, (_, request_id) in zip(record.operation_ids, stages.requests, strict=True):
            assert operation_id == "op-" + request_id
            stored = service.authority.journal.lookup(operation_id, ACTOR)
            assert stored is not None and stored["state"] == "DONE", operation_id
        assert (
            record.revision_id
            == json.loads((site.state / "workspaces" / workspace_id / "current.json").read_text())["revision_id"]
        )
        assert (site.source / "note.txt").read_text() == "wire checkpoint\n"
        assert sidecar(site, workspace_id).records() == (record,)
