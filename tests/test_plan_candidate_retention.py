"""CT119 (SLICE7 STEP3): refused bytes survive as ``plan-<sha256>.md``.

The controller deletes the planner's candidate before publication, so after a
refused promotion the only copy of the rejected bytes is the snapshot in memory.
These tests pin the two halves of that: the file writer (deterministic name,
no-clobber semantics, private modes) and the wiring in ``_run_admission_repair``
that keeps the promotion's own rule while retaining the draft.
"""

from __future__ import annotations

import hashlib
import stat
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.inner_loop import workflow_controller
from fa.inner_loop.plan_admission import PlanRef, read_plan_snapshot
from fa.inner_loop.plan_promotion import PlanPromotionError, retain_plan_draft
from fa.inner_loop.planner_dispatch import PlannerDispatch, PlannerDispatchKind

PLAN = "worklogs/planning-topology-and-executable-contracts-loop/increments/increment-99-retention.md"
GOOD = (
    b"Plan-ID: PLAN-retention\n\n## SLICE1: retained draft\n"
    b"CONTRACTS:\n  CT9001 [CONSTRAINT]: fixture input remains present.\n"
    b"TESTS: tests/test_fixture_contract.py\n"
)
BAD = b"## SLICE 1: not a slice heading\n"
RUN = "run-retain"


def _digest_name(raw: bytes) -> str:
    return f"plan-{hashlib.sha256(raw).hexdigest()}.md"


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / PLAN).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / PLAN).write_bytes(BAD)
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / "test_fixture_contract.py").write_text("def test_ok(): pass\n", encoding="utf-8")
    return tmp_path


@dataclass
class _Ctx:
    """Only the fields ``_run_admission_repair`` reads; ``dataclasses.replace`` compatible."""

    workspace: Path
    run_id: str
    admission: Any
    base_task: str = "retain the draft"
    per_role_task: dict[str, str] = field(default_factory=dict)
    deadline_mono: float | None = None


def test_a_refused_promotion_retains_the_exact_bytes_under_their_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """C1: the branch is wired, and the retained name is the candidate's digest.

    The ordinary path's control lives in ``tests/test_s8_workflow_controller.py``:
    an admitted plan never reaches promotion, so nothing is retained for it.
    """
    workspace = _workspace(tmp_path)
    source = read_plan_snapshot(workspace, Path(PLAN))
    target = f".fa/admission/{RUN}/candidate-fixed.md"

    def _seed(*_: Any, **__: Any) -> PlannerDispatch:
        path = workspace / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(GOOD)  # what the planner would have written
        return PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, RUN, PLAN, target)

    monkeypatch.setattr(workflow_controller, "seed_plan_candidate", _seed)
    monkeypatch.setattr(
        workflow_controller, "_run_stage", lambda *a, **k: workflow_controller.StageResult("planner", 0)
    )

    class _Refusing:
        def publish_candidate(self, source: Any, candidate: Any, *, deadline: float | None = None) -> Any:
            raise PlanPromotionError("hash-mismatch")

    ctx = _Ctx(workspace, RUN, SimpleNamespace(snapshot=source, candidate=None))
    with pytest.raises(PlanPromotionError) as error:
        workflow_controller._run_admission_repair(
            ctx,
            None,  # progress: unused because the stage dispatcher is replaced
            lambda **kwargs: 0,
            kind=PlannerDispatchKind.ADMISSION_REPAIR,
            draft=source,
            publisher=_Refusing(),
        )

    assert error.value.rule == "hash-mismatch"  # retention never renames the fault
    kept = workspace / f".fa/admission/{RUN}/{_digest_name(GOOD)}"
    assert kept.read_bytes() == GOOD
    assert stat.S_IMODE(kept.stat().st_mode) == 0o600
    assert not (workspace / target).exists()  # the candidate itself is still cleaned up
    assert (workspace / PLAN).read_bytes() == BAD  # canonical bytes untouched


def test_a_successful_promotion_retains_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: retention is a property of the failure, not a side effect of promotion."""
    workspace = _workspace(tmp_path)
    source = read_plan_snapshot(workspace, Path(PLAN))
    target = f".fa/admission/{RUN}/candidate-fixed.md"

    def _seed(*_: Any, **__: Any) -> PlannerDispatch:
        path = workspace / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(GOOD)
        return PlannerDispatch(PlannerDispatchKind.ADMISSION_REPAIR, RUN, PLAN, target)

    monkeypatch.setattr(workflow_controller, "seed_plan_candidate", _seed)
    monkeypatch.setattr(
        workflow_controller, "_run_stage", lambda *a, **k: workflow_controller.StageResult("planner", 0)
    )
    published: list[Any] = []

    class _Accepting:
        def publish_candidate(self, source: Any, candidate: Any, *, deadline: float | None = None) -> Any:
            # The port answers with the canonical identity it committed to, which is
            # what `_promote_validated_plan` compares against (source path + digest).
            ref = PlanRef(source.ref.workspace_relative_path, source.ref.source_kind, candidate.ref.sha256)
            published.append(ref)
            return ref

    ctx = _Ctx(workspace, RUN, SimpleNamespace(snapshot=source, candidate=None))
    _, promoted = workflow_controller._run_admission_repair(
        ctx,
        None,
        lambda **kwargs: 0,
        kind=PlannerDispatchKind.ADMISSION_REPAIR,
        draft=source,
        publisher=_Accepting(),
    )

    assert promoted is not None and published == [promoted.ref]
    admission_dir = workspace / ".fa" / "admission" / RUN
    assert not [item for item in admission_dir.iterdir() if item.name.startswith("plan-")]


def test_the_same_rejection_twice_is_one_file(tmp_path: Path) -> None:
    first = retain_plan_draft(tmp_path, RUN, GOOD)
    second = retain_plan_draft(tmp_path, RUN, GOOD)
    assert first == second
    assert len(list((tmp_path / ".fa" / "admission" / RUN).iterdir())) == 1


def test_different_bytes_keep_two_files_without_evicting_the_first(tmp_path: Path) -> None:
    first = retain_plan_draft(tmp_path, RUN, GOOD)
    second = retain_plan_draft(tmp_path, RUN, GOOD + b"\n")
    assert first != second
    assert first.read_bytes() == GOOD
    assert second.read_bytes() == GOOD + b"\n"


def test_a_foreign_file_under_the_digest_is_never_overwritten(tmp_path: Path) -> None:
    """The name promises content, so a mismatch there is corruption, not a retry."""
    path = tmp_path / ".fa" / "admission" / RUN / _digest_name(GOOD)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"someone else wrote this\n")

    with pytest.raises(PlanPromotionError) as error:
        retain_plan_draft(tmp_path, RUN, GOOD)

    assert error.value.rule == "prepare-failed"
    assert path.read_bytes() == b"someone else wrote this\n"


def test_a_symlink_under_the_digest_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_bytes(GOOD)
    path = tmp_path / ".fa" / "admission" / RUN / _digest_name(GOOD)
    path.parent.mkdir(parents=True)
    path.symlink_to(outside)

    with pytest.raises(PlanPromotionError):
        retain_plan_draft(tmp_path, RUN, GOOD)

    assert path.is_symlink() and outside.read_bytes() == GOOD


def test_a_run_id_that_is_a_path_is_refused(tmp_path: Path) -> None:
    with pytest.raises(PlanPromotionError) as error:
        retain_plan_draft(tmp_path, "../escape", GOOD)
    assert error.value.rule == "scope-denied"
    assert not (tmp_path / ".fa").exists()


def test_a_draft_is_not_retained_after_the_run_deadline(tmp_path: Path) -> None:
    with pytest.raises(PlanPromotionError) as error:
        retain_plan_draft(tmp_path, RUN, GOOD, deadline=0.0)
    assert error.value.rule == "prepare-failed"
    assert not (tmp_path / ".fa").exists()
