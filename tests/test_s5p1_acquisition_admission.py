"""S5P1 STEP2 — an acquisition snapshot reaches admission as bytes, not a path.

The acquisition planner reads a candidate plan through a pinned view and hands the
controller a `PlanSnapshot`. This bank proves that input is a real admission
authority rather than a bypass:

Classes (knowledge/skills/tests-writing):
  C0 — the closed refusals on the new input's shape.
  C1 — a coder-bearing run is admitted from the snapshot with no host plan path,
       and the same run without either input is still blocked.

What must stay true (each test names the producer it kills):
  * a snapshot admits a coder without a host path (the S5P1 target behaviour);
  * the legacy missing-plan refusal is unchanged (no weakening by adjacency);
  * "snapshot and path" is a refusal, not a preference — two plan sources;
  * a snapshot with no coder is a refusal, not a silently discarded fact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fa.inner_loop.plan_admission import snapshot_from_bytes
from fa.inner_loop.workflow_controller import run_workflow, workflow_artifact_paths
from tests.test_plan_reference import _config, _SilentStage

PLAN_RELATIVE = "worklogs/demo-project/increments/increment-01-foundation.md"
PLAN_BODY = b"""# Increment: Foundation

## SLICE1: Foundation

Implement the foundation.
"""


def _snapshot():
    return snapshot_from_bytes(PLAN_RELATIVE, PLAN_BODY, source_kind="EXISTING_SELECTION")


def _run(tmp_path: Path, *, run_id: str, roles: list[str], **kwargs: Any) -> tuple[int, Any]:
    return run_workflow(
        roles=roles,
        task="do the thing",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id=run_id,
        config=_config(tmp_path),
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=_SilentStage(),
        **kwargs,
    )


def _blocked_reason(run_id: str) -> str:
    payload = json.loads(workflow_artifact_paths(run_id).flow_state.read_text(encoding="utf-8"))
    return str(payload["blocked_reason"])


def test_a_snapshot_admits_a_coder_with_no_host_plan_path(tmp_path: Path) -> None:
    """The S5P1 target behaviour: admission from bytes the controller already holds.

    `plan_path` is absent, so nothing can be read from `ctx.workspace`. If this
    were still refused as `plan-ref/missing`, the acquisition caller could not
    exist; if it were admitted *without* validating, the slice ids below would not
    reach the admission record.
    """
    exit_code, state = _run(tmp_path, run_id="aq-1", roles=["coder"], admission_snapshot=_snapshot())

    assert exit_code == 0, f"admission refused: {_blocked_reason('aq-1') if state else 'no state'}"
    assert state is not None and state.status == "DONE"
    # The admitted plan is the snapshot's, identified by its own digest.
    admission = json.loads(workflow_artifact_paths("aq-1").admission.read_bytes())
    assert admission["status"] == "ADMITTED"
    assert admission["plan_ref"]["sha256"] == _snapshot().ref.sha256
    assert admission["plan_ref"]["source_kind"] == "EXISTING_SELECTION"


def test_no_snapshot_and_no_path_is_still_the_legacy_missing_plan_refusal(tmp_path: Path) -> None:
    """Negative proof: the new input did not weaken plan-before-coder.

    Without either input a coder-bearing run must be blocked exactly as before.
    This is the oracle that kills "admit when a snapshot is absent too".
    """
    exit_code, state = _run(tmp_path, run_id="aq-2", roles=["coder"])

    assert exit_code == 2
    assert state is not None and state.status == "FAILED"
    assert state.blocked_reason == "plan-ref/missing"
    assert not workflow_artifact_paths("aq-2").eval_report.exists()


def test_a_snapshot_and_a_path_together_are_refused(tmp_path: Path) -> None:
    """Two plan sources must be a refusal, never a preference.

    Choosing between them would be a guess about the operator's intent at the one
    place where guessing costs correctness: which plan a coder is bound to.
    """
    from tests.workflow_fixtures import write_explicit_plan

    host_plan = write_explicit_plan(tmp_path)
    exit_code, state = _run(
        tmp_path,
        run_id="aq-3",
        roles=["coder"],
        plan_path=host_plan,
        admission_snapshot=_snapshot(),
    )

    assert exit_code == 2
    assert state is not None and state.status == "FAILED"
    assert state.blocked_reason == "plan-ref/conflict"
    assert not workflow_artifact_paths("aq-3").eval_report.exists()


def test_a_snapshot_without_a_coder_is_refused_not_ignored(tmp_path: Path) -> None:
    """A snapshot bounds what a coder writes; with no coder it bounds nothing.

    Silently accepting it would tell the caller its authority was honoured when
    the run never used it.
    """
    exit_code, state = _run(tmp_path, run_id="aq-4", roles=["planner"], admission_snapshot=_snapshot())

    assert exit_code == 2
    assert state is not None and state.status == "FAILED"
    assert state.blocked_reason == "plan-ref/admission-without-coder"


def test_the_snapshot_is_validated_not_trusted(tmp_path: Path) -> None:
    """An unvalidatable snapshot must block, so the input is not a rubber stamp.

    Empty bytes cannot even be constructed (`snapshot_from_bytes` refuses empty
    text), so the reachable shape is a non-empty plan with no parseable slice.
    If this admitted, the acquisition caller could hand over any prose and get a
    coder.
    """
    no_slices = snapshot_from_bytes(
        PLAN_RELATIVE, b"# Increment: Foundation\n\nProse with no slice record.\n", source_kind="EXISTING_SELECTION"
    )
    exit_code, state = _run(tmp_path, run_id="aq-5", roles=["coder"], admission_snapshot=no_slices)

    assert exit_code != 0
    assert state is not None and state.status == "FAILED"
    assert "admission" in (state.blocked_reason or "")
    assert not workflow_artifact_paths("aq-5").eval_report.exists()


def test_an_empty_snapshot_cannot_be_constructed_at_all() -> None:
    """The refusal happens one layer earlier, which is why the test above needs prose.

    Asserting this keeps the reachability reasoning honest: a future change that
    allowed empty snapshots would move the failure to admission, and this oracle
    would report it.
    """
    import pytest as _pytest

    from fa.inner_loop.plan_admission import PlanRefError

    with _pytest.raises(PlanRefError) as refused:
        snapshot_from_bytes(PLAN_RELATIVE, b"   \n\n", source_kind="EXISTING_SELECTION")
    assert refused.value.rule == "empty"


def test_a_non_snapshot_object_is_refused_by_type(tmp_path: Path) -> None:
    """Closed shape: a dict or a path is not a snapshot, and says so."""
    exit_code, state = _run(tmp_path, run_id="aq-6", roles=["coder"], admission_snapshot={"text": "x"})

    assert exit_code == 2
    assert state is not None and state.blocked_reason == "plan-ref/unreadable"


# ── C0: the source check is substrate-aware, and both branches still bite ──────


def _admission_ctx(tmp_path: Path, *, snapshot, snapshot_backed: bool):
    from dataclasses import replace

    from fa.inner_loop.workflow_controller import _WorkflowAdmission

    return replace(
        _base_ctx(tmp_path),
        admission=_WorkflowAdmission(snapshot, True, 1, snapshot_backed=snapshot_backed),
    )


def _base_ctx(tmp_path: Path):
    from tests.test_plan_reference import _ctx

    return _ctx(tmp_path, None)


def test_a_snapshot_backed_admission_does_not_read_the_host(tmp_path: Path) -> None:
    """The defect this branch removes: judging one tree by reading another.

    The host workspace holds nothing; only the snapshot has the plan. A host
    re-read would fail `unreadable`, so a passing check proves the branch.
    """
    from fa.inner_loop.workflow_controller import _check_admission_source

    _check_admission_source(_admission_ctx(tmp_path, snapshot=_snapshot(), snapshot_backed=True))


def test_a_snapshot_whose_bytes_no_longer_match_its_digest_is_source_changed(tmp_path: Path) -> None:
    """The snapshot branch is a real check, not a bypass.

    Replacing the recorded bytes after validation must be caught, which is what
    makes "no host read" safe rather than merely convenient.
    """
    import pytest as _pytest

    from fa.inner_loop.plan_admission import PlanRef, PlanRefError, PlanSnapshot, extract_plan_ids
    from fa.inner_loop.workflow_controller import _check_admission_source

    good = _snapshot()
    tampered = PlanSnapshot(
        ref=good.ref,
        utf8_bytes=good.utf8_bytes + b"\nedited after validation\n",
        text=good.text + "\nedited after validation\n",
        ids=extract_plan_ids(good.text + "\nedited after validation\n"),
    )
    assert isinstance(tampered.ref, PlanRef)
    with _pytest.raises(PlanRefError) as refused:
        _check_admission_source(_admission_ctx(tmp_path, snapshot=tampered, snapshot_backed=True))
    assert refused.value.rule == "source-changed"


def test_a_host_mode_admission_still_detects_a_changed_file(tmp_path: Path) -> None:
    """The legacy branch is unchanged: a file edited after admission is refused."""
    import pytest as _pytest

    from fa.inner_loop.plan_admission import PlanRefError, read_plan_snapshot
    from fa.inner_loop.workflow_controller import _check_admission_source

    plan = tmp_path / "plan.md"
    plan.write_text("# Increment: X\n\n## SLICE1: S\n\nDo.\n", encoding="utf-8")
    snapshot = read_plan_snapshot(tmp_path, Path("plan.md"))
    ctx = _admission_ctx(tmp_path, snapshot=snapshot, snapshot_backed=False)

    _check_admission_source(ctx)  # unchanged file passes
    plan.write_text("# Increment: X\n\n## SLICE1: S\n\nChanged.\n", encoding="utf-8")
    with _pytest.raises(PlanRefError) as refused:
        _check_admission_source(ctx)
    assert refused.value.rule == "source-changed"


# ── C2: a refused admission has no downstream effect ─────────────────────────


class _PoisonStage:
    """A stage dispatcher that records any call and fails the assertion if used.

    A refusal that still started a role would be a *different* refusal than the
    one advertised: the caller would see `blocked_reason` and be told nothing ran,
    while a model call had already been paid for.
    """

    def __init__(self) -> None:
        self.roles: list[str] = []

    def __call__(self, args: object, **kwargs: object) -> int:
        self.roles.append(str(getattr(args, "role", "?")))
        raise AssertionError(f"a refused admission dispatched role {args!r}")


def _record(run_id: str) -> dict[str, Any]:
    """The single admission record for this run (attempts live inside it)."""
    path = workflow_artifact_paths(run_id).admission
    assert path.exists(), f"a refused admission left no durable record: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_a_refused_snapshot_admission_dispatches_no_role_and_makes_no_model_call(tmp_path: Path) -> None:
    """The zero-effect proof, in both observable dimensions.

    The stage dispatcher is the only path to a provider call, so proving it was
    never invoked proves no coder turn happened. The ledger proves the refusal was
    still *recorded* -- a silent refusal would be an outage, not a safeguard.
    """
    stage = _PoisonStage()
    code, state = run_workflow(
        roles=["coder"],
        task="do the thing",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id="s5p1-zero-effect",
        config=_config(tmp_path),
        workspace=tmp_path,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=stage,
        admission_snapshot=_snapshot(),
        plan_path=tmp_path / "worklogs/demo-project/increments/increment-01-foundation.md",
    )

    assert code == 2
    assert stage.roles == [], "no role may be dispatched when admission is refused"
    assert state is not None and state.status == "FAILED"
    assert state.blocked_reason == "plan-ref/conflict"
    assert len(_record("s5p1-zero-effect")["attempts"]) == 1


def test_a_refused_admission_leaves_no_plan_bound_coder_state(tmp_path: Path) -> None:
    """A refused run must not claim a plan identity it never validated."""
    code, state = _run(
        tmp_path,
        run_id="s5p1-no-plan",
        roles=["coder"],
        admission_snapshot=snapshot_from_bytes(PLAN_RELATIVE, PLAN_BODY, source_kind="EXISTING_SELECTION"),
        plan_path=tmp_path / "worklogs/demo-project/increments/increment-01-foundation.md",
    )

    assert code == 2 and state is not None
    record = _record("s5p1-no-plan")
    entries = record["attempts"]
    assert len(entries) == 1
    assert record["status"] == "BLOCKED"
    assert entries[0]["validation"] == "INDETERMINATE"
    # The closed schema vocabulary cannot hold a controller-shape rule, so the
    # record carries `validator-error`. The exact reason survives in the flow
    # state, which is what an operator reads.
    assert entries[0]["diagnostics"][0]["rule"] == "validator-error"
    assert entries[0]["source_sha256"] is None
    assert entries[0]["promoted_sha256"] is None
