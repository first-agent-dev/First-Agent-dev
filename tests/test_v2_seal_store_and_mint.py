"""N1 oracles: the seal is minted on the create route, and custody keeps it honest (D-V2-5).

Two halves, because the defect had two: **nothing minted** (so ``mint_seal`` was reachable only
from the defect route and from tests, and every V2 stage refused ``acceptance-seal/missing``), and
**custody was a plain file in the tracked tree** (so "the project at revision R" and "the bytes on
disk" stopped meaning the same thing at the artifact that proves custody). The store lives under
``.fa/``, which every canonical walk excludes and no file tool may address.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest import mock

import pytest

from fa.execution import workspace as workspace_module
from fa.inner_loop import workflow_controller as workflow
from fa.inner_loop.acceptance_bundle import (
    AcceptanceBundle,
    AcceptanceBundleError,
    mint_seal,
    write_seal,
)
from fa.inner_loop.acceptance_collection import AcceptanceCollectionError, verify_sealed_acceptance
from fa.inner_loop.acceptance_seal_store import SEAL_POINTER, SEAL_STORE_ROOT, SealStore
from fa.inner_loop.project_scaffold import scaffold_files
from fa.inner_loop.tools import workflow_tool
from fa.inner_loop.verification_attempt import (
    ClaimEvidence,
    VerificationAttempt,
    VerificationAttemptError,
    VerificationIdentity,
)
from tests.test_ai_native_acceptance_collection import _COLLECTED, _NODEID, _REVISION, _mint, _tree
from tests.test_ai_native_bootstrap import _DocumentPort, _yield
from tests.test_ai_native_plan_v2 import (
    grant_declarations,
    granted_graph,
    plan_document,
)
from tests.test_slice_verification_runner import _inband_executor

_SLUG = "demo"
_SEALED_ROOT = f"worklogs/{_SLUG}/acceptance"
_INCREMENT = f"worklogs/{_SLUG}/increments/increment-01-initial-plan.md"


def _seal(tmp_path: Path) -> AcceptanceBundle:
    return _mint(_tree(tmp_path))


def _store_rule(action: Any) -> str:
    with pytest.raises(AcceptanceBundleError) as refused:
        action()
    return refused.value.rule


# ── custody: the store is outside the tracked tree, and its rules are closed ──────────────────


def test_the_seal_lives_where_no_revision_walks_and_no_file_tool_reaches(tmp_path: Path) -> None:
    """C1: the custody artifact must not be inside the tree its own revision describes.

    ``.fa`` is the one name the canonical walk excludes at any depth, and the one the file tools
    refuse outright -- so this is a property of the *location*, asserted against the authorities
    that enforce it rather than against a comment.
    """
    assert SEAL_STORE_ROOT.split("/")[0] == ".fa"
    assert SEAL_POINTER.split("/")[0] == ".fa"
    assert ".fa" in workspace_module._PROTECTED_COMPONENTS

    bundle = _seal(tmp_path)
    store = SealStore(tmp_path)
    store.store(bundle)

    assert store.pointer_path == tmp_path / SEAL_POINTER
    assert (tmp_path / SEAL_STORE_ROOT / f"{bundle.seal_sha256}.json").is_file()
    # And nothing the seal names was written into the project tree.
    assert not (tmp_path / "acceptance.seal.json").exists()


def test_a_stored_seal_is_the_one_in_force(tmp_path: Path) -> None:
    bundle = _seal(tmp_path)
    SealStore(tmp_path).store(bundle)

    current = SealStore(tmp_path).current()

    assert current.seal_sha256 == bundle.seal_sha256
    assert current.plan_sha256 == bundle.plan_sha256
    assert [selector.nodeid for selector in current.selectors] == [_NODEID]


def test_storing_the_same_seal_twice_is_idempotent(tmp_path: Path) -> None:
    """E3/E9: a restart mints the same bytes from the same inputs, so storing must not refuse."""
    bundle = _seal(tmp_path)
    store = SealStore(tmp_path)

    store.store(bundle)
    store.store(bundle)

    assert len(list((tmp_path / SEAL_STORE_ROOT).iterdir())) == 1


def test_a_second_different_seal_has_to_declare_what_it_supersedes(tmp_path: Path) -> None:
    """E7: the pointer moves only for a supersede the caller declared (D-V2-5 §5).

    Overwriting in place would erase the rung a reviewer is reading; refusing outright would make
    the correction route impossible. So the *only* path is a record that names its predecessor.
    """
    first = _seal(tmp_path)
    SealStore(tmp_path).store(first)

    # A different revision is a different seal; the chain has to say so.
    second = mint_seal(
        graph=granted_graph(),
        plan_bytes=plan_document().encode("utf-8"),
        revision_id="rev-" + "1" * 32,
        sealed_root=_SEALED_ROOT,
        acceptance_root=tmp_path / _SEALED_ROOT,
        collected=_COLLECTED,
    )
    assert _store_rule(lambda: SealStore(tmp_path).store(second)) == "seal-supersede-required"

    chained = mint_seal(
        graph=granted_graph(),
        plan_bytes=plan_document().encode("utf-8"),
        revision_id="rev-" + "1" * 32,
        sealed_root=_SEALED_ROOT,
        acceptance_root=tmp_path / _SEALED_ROOT,
        collected=_COLLECTED,
        supersedes_sha256=first.seal_sha256,
    )
    SealStore(tmp_path).supersede(chained, supersedes_sha256=first.seal_sha256)

    # Both rungs stay on disk and the pointer names the new one: the chain is walkable.
    store = SealStore(tmp_path)
    assert len(list((tmp_path / SEAL_STORE_ROOT).iterdir())) == 2
    assert store.current().seal_sha256 == chained.seal_sha256
    assert store.current().supersedes_sha256 == first.seal_sha256


def test_absence_and_corruption_are_different_answers(tmp_path: Path) -> None:
    """D-V2-5 §4: no pointer is "not sealed yet"; a pointer with no record is corruption."""
    assert _store_rule(lambda: SealStore(tmp_path).current()) == "seal-pointer-missing"

    bundle = _seal(tmp_path)
    store = SealStore(tmp_path)
    store.store(bundle)
    (tmp_path / SEAL_STORE_ROOT / f"{bundle.seal_sha256}.json").unlink()

    assert _store_rule(lambda: SealStore(tmp_path).current()) == "seal-record-missing"


def test_a_torn_record_is_a_hard_error_and_never_a_re_mint(tmp_path: Path) -> None:
    """E4: re-minting over a corrupt record would launder the corruption into evidence."""
    bundle = _seal(tmp_path)
    store = SealStore(tmp_path)
    store.store(bundle)
    record = tmp_path / SEAL_STORE_ROOT / f"{bundle.seal_sha256}.json"
    record.write_bytes(b'{"schema_version": 2, "kind": "ACCEPTANCE-BUNDLE"')

    with pytest.raises(AcceptanceBundleError):
        SealStore(tmp_path).current()
    # ...and the store refuses to write over it rather than "fixing" the bytes.
    assert _store_rule(lambda: store.store(bundle)) == "seal-record-mismatch"


def test_a_pointer_that_is_not_the_closed_record_is_refused(tmp_path: Path) -> None:
    pointer = tmp_path / SEAL_POINTER
    pointer.parent.mkdir(parents=True)
    pointer.write_text("not json", encoding="utf-8")
    assert _store_rule(lambda: SealStore(tmp_path).current()) == "seal-pointer-invalid"

    pointer.write_text('{"schema_version": 1}', encoding="utf-8")
    assert _store_rule(lambda: SealStore(tmp_path).current()) == "seal-pointer-invalid"


def test_the_store_refuses_a_value_that_is_not_a_seal(tmp_path: Path) -> None:
    assert _store_rule(lambda: SealStore(tmp_path).store(cast("Any", "seal"))) == "seal-invalid"


def first_graph() -> Any:
    """The graph the mint fixtures use: the plan document with the caller's grants bound."""
    from fa.inner_loop.plan_admission import bind_dispositions
    from tests.test_ai_native_plan_v2 import plan_graph

    return bind_dispositions(plan_graph(), grant_declarations(), today=__import__("datetime").date(2026, 11, 20))


# ── the route: admission mints, and the stage that follows reads what it minted ───────────────


def _documents() -> dict[str, str]:
    """The published pair: the scaffold's front matter (the metadata table's half) + the plan.

    Admission cross-checks front matter against the *path*, and the grammar fixtures carry a
    parser-shaped header (``Increment-ID: I01``) that no project directory could satisfy. The
    scaffold header is the one a real create has, so the authored sections are appended to it
    instead of re-deriving a second header.
    """
    scaffold = scaffold_files(_SLUG, created="2026-11-21")
    increment_path = f"worklogs/{_SLUG}/increments/increment-01-initial-plan.md"
    authored = plan_document()
    assert "Plan-Format: AI-NATIVE-PLAN-V2" in authored
    body = authored.split("Plan-Format: AI-NATIVE-PLAN-V2", 1)[1]
    increment = scaffold[increment_path].replace("slices: 0", "slices: 1") + body
    return {f"worklogs/{_SLUG}/roadmap.md": scaffold[f"worklogs/{_SLUG}/roadmap.md"], _INCREMENT: increment}


def _route_ctx(tmp_path: Path) -> workflow.WorkflowContext:
    return workflow.WorkflowContext(
        run_id="n1-route",
        base_task="t",
        per_role_task={},
        artifact_paths=workflow.workflow_artifact_paths("n1-route", base_dir=tmp_path / "logs"),
        config=tmp_path / "models.yaml",
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        managed_execution=cast("Any", _ManagedStub()),
        project_hint=_SLUG,
        dispositions=cast("Any", grant_declarations()),
    )


class _ManagedStub:
    """What the route needs from a managed run: the revision it published, and its profile."""

    current_revision_id = _REVISION
    read_only_profile = SimpleNamespace(profile_id="managed-readonly")


def _admit(tmp_path: Path) -> tuple[workflow.WorkflowContext, Any]:
    substrate = workflow.AcquisitionSubstrate(port=_DocumentPort(_documents()), project_names=())  # type: ignore[arg-type]
    with (
        mock.patch.object(workflow, "_pinned_acquisition_substrate", _yield(substrate)),
        mock.patch.object(
            workflow,
            "_pinned_verify_substrate",
            _yield(
                workflow._VerifySubstrate(
                    executor=_inband_executor(writes_visible=False, revision=_REVISION), port=None
                )
            ),
        ),
    ):
        return workflow._admit_published_project(_route_ctx(tmp_path))


def test_admission_mints_the_seal_and_the_next_stage_reads_it(tmp_path: Path) -> None:
    """N1's whole point: before this, ``mint_seal`` had no caller on the route at all."""
    _tree(tmp_path)

    bound, refusal = _admit(tmp_path)

    assert refusal is None, refusal
    sealed = SealStore(tmp_path).current()
    assert bound.admission is not None and bound.admission.snapshot.graph is not None
    assert sealed.plan_sha256 == bound.admission.snapshot.ref.sha256
    assert sealed.revision_id == _REVISION
    # The stage that follows admission finds the seal through the one reader, with no error.
    bundle, errors = workflow._stage_acceptance_bundle(bound)
    assert errors == ()
    assert bundle is not None and bundle.seal_sha256 == sealed.seal_sha256


def test_an_uncollectable_acceptance_tree_refuses_before_any_coder_runs(tmp_path: Path) -> None:
    """A plan whose selector nothing can collect is a *content* refusal, and it is repairable."""
    root = _tree(tmp_path)
    (root / "tests" / "test_publish.py").write_text("VALUE = 1\n", encoding="utf-8")

    bound, refusal = _admit(tmp_path)

    assert refusal is not None and refusal.rule == "bootstrap-acceptance-unsealed"
    # The parser's own rule travels as ``detail`` (P4-3): "the tree has no tests" is not what a
    # planner can act on, "selector-uncollected" is. The rule is content, so the repair runs.
    assert refusal.detail == "selector-uncollected"
    assert bound.admission is None, "an unsealed project must not bind an admission"
    assert not (tmp_path / SEAL_POINTER).exists(), "a refusal must leave no seal behind"
    # The planner can fix this: `acceptance/` is inside the repair scope (S1 item 4).
    ctx = replace(_route_ctx(tmp_path), authored_repairs=0, replans_allowed=1)
    assert workflow._may_repair_authored_project(ctx, refusal) is True


def test_the_consistency_half_of_a_seal_refusal_is_not_a_content_repair(tmp_path: Path) -> None:
    """Admission accepted what the seal refused: that is our defect, not the planner's prose."""
    from fa.inner_loop.plan_admission import PlanRefError

    refusal = PlanRefError("bootstrap-acceptance-unsealed", detail="seal-uncovered-contracts")
    ctx = replace(_route_ctx(tmp_path), authored_repairs=0, replans_allowed=1)

    assert workflow._may_repair_authored_project(ctx, refusal) is False
    # The caller code is the same family: attempts are spent, so a retry repeats the work.
    assert workflow_tool._V2_CREATE_FAILURES["bootstrap-acceptance-unsealed"] == ("bootstrap_content_invalid", False)


def test_without_a_pinned_cell_there_is_no_seal_and_the_run_says_so(tmp_path: Path) -> None:
    """No host fallback (CT61): a collection next to the code the coder edits is not evidence."""
    _tree(tmp_path)
    substrate = workflow.AcquisitionSubstrate(port=_DocumentPort(_documents()), project_names=())  # type: ignore[arg-type]
    with (
        mock.patch.object(workflow, "_pinned_acquisition_substrate", _yield(substrate)),
        mock.patch.object(workflow, "_pinned_verify_substrate", _yield(None)),
    ):
        _bound, refusal = workflow._admit_published_project(_route_ctx(tmp_path))

    assert refusal is not None and refusal.rule == "bootstrap-unavailable"
    assert not (tmp_path / SEAL_POINTER).exists()


def test_the_written_seal_is_the_bytes_the_store_reloads(tmp_path: Path) -> None:
    """A seal that cannot be reloaded is not a seal: the store round-trips through ``load_seal``."""
    bundle = _seal(tmp_path)
    SealStore(tmp_path).store(bundle)
    raw = (tmp_path / SEAL_STORE_ROOT / f"{bundle.seal_sha256}.json").read_bytes()

    reloaded = SealStore(tmp_path).current()

    assert reloaded.seal_sha256 == bundle.seal_sha256
    assert write_seal(bundle, tmp_path / "copy.json").read_bytes() == raw


# ── N2/N3: what the attempt states about a grant and about a declared target ─────────────────


def _sealed(tmp_path: Path, *, kill_declared: tuple[Any, ...] = ()) -> Any:
    from fa.inner_loop.acceptance_collection import sealed_attempt

    bundle = _seal(tmp_path)
    verification = verify_for(bundle, tmp_path)
    identity = VerificationIdentity(
        plan_sha256=bundle.plan_sha256,
        candidate_revision_id=bundle.revision_id,
        profile_id="managed-readonly",
        substrate="managed-readonly",
        run_id="n1-route",
        attempt=1,
        repair_round=0,
        mode="A",
        seal_sha256=bundle.seal_sha256,
        closure_sha256=bundle.closure.digest,
        sealed_revision_id=bundle.revision_id,
    )
    return sealed_attempt(bundle, verification, identity=identity, kill_declared=kill_declared)


def verify_for(bundle: Any, tmp_path: Path) -> Any:
    """One real sealed run over the fixture tree, with the in-band substrate."""
    return verify_sealed_acceptance(
        bundle,
        workspace=tmp_path,
        candidate_revision_id=bundle.revision_id,
        plan_bytes=plan_document().encode("utf-8"),
        executor=_inband_executor(writes_visible=False, revision=bundle.revision_id),
    )


def test_the_attempt_carries_the_seal_attestations_not_only_their_ids(tmp_path: Path) -> None:
    """N3/P4-8: "CT-1.2 was attested" without who/what/when is the half-closed mitigation."""

    attempt = _sealed(tmp_path)

    assert attempt.attested == ("CT-1.2",)
    (record,) = attempt.attestations
    assert (record.contract_id, record.invariant_id, record.reason) == ("CT-1.2", "INV-2", "HOST_READINESS")
    assert record.owner == "W4" and record.reviewed_at is not None
    assert record.artifact.startswith("probe:worklogs/demo/acceptance/probes/")

    payload = workflow._sealed_attempt_payload(attempt)
    assert payload["attestations"] == [
        {
            "contract_id": "CT-1.2",
            "invariant_id": "INV-2",
            "reason": record.reason,
            "route": record.route,
            "artifact": record.artifact,
            "owner": "W4",
            "reviewed_at": record.reviewed_at,
            "scope_sha256": record.scope_sha256,
        }
    ]
    rendered = "\n".join(workflow._claim_evidence_lines(attempt))
    assert "CT-1.2 attested (untrusted): reason=HOST_READINESS" in rendered
    assert "owner=W4" in rendered


def test_a_declared_kill_target_is_recorded_as_declared_and_not_executed(tmp_path: Path) -> None:
    """N2 (Q-V2-SLICE3-4 = A): attribution is a fact, and its absence of execution is too."""
    declared = granted_graph().kill_targets()
    assert [target.ct for target in declared] == ["CT-1.1"]

    attempt = _sealed(tmp_path, kill_declared=declared)

    assert attempt.kill_required == ()
    assert [target.target_id for target in attempt.kill_declared] == ["publication.publish_plan"]
    payload = workflow._sealed_attempt_payload(attempt)
    assert payload["kill_required"] == []
    assert payload["kill_declared"] == [
        {"target_id": "publication.publish_plan", "ct_id": "CT-1.1", "test_id": "TEST-1.1", "executed": False}
    ]
    rendered = "\n".join(workflow._claim_evidence_lines(attempt))
    assert "kill target publication.publish_plan (TEST-1.1): declared, not executed" in rendered


def test_a_declared_target_that_is_not_a_cover_contract_is_refused(tmp_path: Path) -> None:
    target = granted_graph().kill_targets()[0]
    stranger = replace(target, ct="CT-9.9", target_id="other.target")

    with pytest.raises(AcceptanceCollectionError) as refused:
        _sealed(tmp_path, kill_declared=(stranger,))

    assert refused.value.rule == "attempt-kill-target-unknown"


def test_one_contract_cannot_be_both_declared_and_required(tmp_path: Path) -> None:
    """A contradiction in the record: required means a mutation *must* be carried."""
    _tree(tmp_path)
    target = granted_graph().kill_targets()[0]

    with pytest.raises(VerificationAttemptError) as refused:
        VerificationAttempt(
            route="legacy",
            commands=(),
            claims=(
                ClaimEvidence(contract_id="CT-1.1", test_id="TEST-1.1", nodeid="w/a/t.py::test_x", outcome="passed"),
            ),
            kill_required=("CT-1.1",),
            kill_declared=(target,),
            errors=(),
        )

    assert refused.value.rule == "kill-target-conflict"


def test_an_attestation_the_seal_does_not_list_is_refused(tmp_path: Path) -> None:
    """The report may not carry a grant the seal does not: that is how a waiver gets laundered."""
    attempt = _sealed(tmp_path)
    (record,) = attempt.attestations

    with pytest.raises(VerificationAttemptError) as refused:
        replace(attempt, attested=(), attestations=(record,))

    assert refused.value.rule == "attestation-unowned"


def test_the_stage_takes_its_declared_targets_from_the_admitted_plan(tmp_path: Path) -> None:
    """The wiring, not just the entity: ``kill_declared`` must come from the snapshot.

    A test that hands ``kill_declared`` to ``sealed_attempt`` itself proves the constructor and
    nothing about the route, which is exactly where the field could be dropped again (N2).
    """
    _tree(tmp_path)
    bound, refusal = _admit(tmp_path)
    assert refusal is None, refusal
    assert bound.admission is not None
    snapshot = bound.admission.snapshot
    assert snapshot.graph is not None and snapshot.graph.kill_targets()

    verification, attempt = workflow._sealed_stage_verification(
        bound,
        snapshot,
        workflow._VerifySubstrate(executor=_inband_executor(writes_visible=False, revision=_REVISION), port=None),
        attempt=1,
        repair_round=0,
    )

    assert attempt is not None, verification.errors
    assert [target.ct for target in attempt.kill_declared] == ["CT-1.1"]
    assert attempt.kill_required == ()
    assert attempt.blocking is False
