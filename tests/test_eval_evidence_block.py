"""S13 — the judge is handed the contract and the evidence.

**The defect.** The eval prompt asks whether the coder satisfied "the
planner's execution contract", but the eval stage received only
``ctx.task_for(role)``. The contract was never delivered, and because
``fresh=index == 0`` only makes stage 0 fresh, eval *resumes the coder's
session* — judging from inside the defendant's transcript, reading its
success narration as context.

**Three failure modes this pins**, each of which passes a naive test:

1. ``git diff HEAD`` **cannot see untracked files**. A slice whose entire
   contribution is a new file shows an EMPTY diff, so a judge could pass it
   having seen nothing. Verified against real git below, not asserted.
2. A workspace that is not a git repo (or a missing git binary) must degrade
   to a block without a diff — the plan is advisory input and must never take
   the run down.
3. "No changes" must be stated explicitly. An omitted section reads as "diff
   unavailable" when the truth is "the coder changed nothing" — itself a
   finding worth a FAIL.

Real git repositories are used rather than a mocked ``subprocess``: the whole
point of hazard 1 is what git *actually does*, which a mock would encode as
the author's belief. The runner seam is injected only where the goal is to
simulate git being absent or hanging.

Classes: **C0** for the block builder, **C1** for the composition root.

Kill-check target: the ``_eval_evidence_block`` append at the eval
``stage_kwargs`` site in ``_run_stage``. Removing it fails
``test_eval_stage_receives_the_evidence_block``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from fa.inner_loop.workflow_controller import (
    EVAL_DIFF_MAX_CHARS,
    WorkflowContext,
    _eval_evidence_block,
    workflow_artifact_paths,
)

_PLAN = """# PLAN: worked example    Plan-ID: PLAN-example

## SLICE1: first
## SLICE7: second
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repository with one commit, so ``HEAD`` resolves."""
    _git(tmp_path, "init", "-q", ".")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init")
    return tmp_path


def _ctx(workspace: Path, plan_path: Path | None = None) -> WorkflowContext:
    return WorkflowContext(
        run_id="r",
        base_task="judge the work",
        per_role_task={},
        artifact_paths=workflow_artifact_paths("r"),
        config=workspace / "models.yaml",
        workspace=workspace,
        max_turns=1,
        output_mode="quiet",
        plan_path=plan_path,
    )


# ── C0: T17 — plan + diff reach the block ──────────────────────────────────


def test_block_carries_plan_path_slice_ids_and_diff(repo: Path) -> None:
    """T17 — the contract and the change both arrive."""
    tracked = repo / "mod.py"
    tracked.write_text("original\n", encoding="utf-8")
    _git(repo, "add", "mod.py")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "add")
    tracked.write_text("MUTATED\n", encoding="utf-8")

    plan = repo / "PLAN.md"
    plan.write_text(_PLAN, encoding="utf-8")

    block = _eval_evidence_block(_ctx(repo, plan))

    assert str(plan) in block
    assert "SLICE1, SLICE7" in block, "the declared slice IDs must reach the judge"
    assert "MUTATED" in block, "the actual change must reach the judge"
    assert "do not infer it from the transcript" in block


def test_staged_and_unstaged_changes_are_both_visible(repo: Path) -> None:
    """``git diff HEAD``, not ``diff`` or ``--cached``.

    Either alone sees half the work, so whether the coder happened to stage
    its changes would decide what the judge is allowed to see.
    """
    # Commit the baseline FIRST. An earlier version staged staged.py before
    # the commit, so the commit swept it in and nothing was actually staged
    # when the assertion ran.
    staged = repo / "staged.py"
    unstaged = repo / "tracked.py"
    staged.write_text("v0\n", encoding="utf-8")
    unstaged.write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "staged.py", "tracked.py")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c")

    staged.write_text("ALPHA_ONLY_IN_STAGED\n", encoding="utf-8")
    _git(repo, "add", "staged.py")  # staged, not committed
    unstaged.write_text("BETA_ONLY_IN_WORKTREE\n", encoding="utf-8")  # worktree only

    staged_only = subprocess.run(
        ["git", "diff", "--cached"], cwd=repo, capture_output=True, text=True, check=False
    ).stdout
    assert "ALPHA_ONLY_IN_STAGED" in staged_only, "precondition: the staged change is really staged"
    assert "BETA_ONLY_IN_WORKTREE" not in staged_only, "precondition: the worktree change is really unstaged"

    block = _eval_evidence_block(_ctx(repo))

    # Distinct, non-overlapping markers on purpose: an earlier version used
    # "STAGED_CONTENT"/"UNSTAGED_CONTENT", and because the former is a
    # SUBSTRING of the latter the staged assertion passed on the unstaged
    # text alone -- the `git diff HEAD` -> `git diff` mutant survived.
    assert "ALPHA_ONLY_IN_STAGED" in block, "staged work is invisible to plain `git diff`"
    assert "BETA_ONLY_IN_WORKTREE" in block, "unstaged work is invisible to `git diff --cached`"


# ── C0: T17e — the untracked-file blind spot (D-6) ─────────────────────────


def test_untracked_new_file_is_named(repo: Path) -> None:
    """T17e — the add-only slice must not look like an empty diff.

    First proves the hazard is real against actual git, then proves the block
    compensates. Without the porcelain status this file is invisible.
    """
    (repo / "brand_new.py").write_text("def f(): ...\n", encoding="utf-8")

    raw_diff = subprocess.run(["git", "diff", "HEAD"], cwd=repo, capture_output=True, text=True, check=False).stdout
    assert raw_diff.strip() == "", "precondition: git diff HEAD really is blind to untracked files"

    block = _eval_evidence_block(_ctx(repo))

    assert "brand_new.py" in block, "an add-only slice would otherwise show the judge nothing"
    assert "NOT in the diff" in block, "the judge must be told to go read it"
    assert "Changed files: NONE" not in block, "there ARE changes; claiming none would be a lie"


# ── C0: T17c — no changes is stated, not implied ───────────────────────────


def test_clean_worktree_says_so_explicitly(repo: Path) -> None:
    """T17c — silence is indistinguishable from "the diff failed"."""
    block = _eval_evidence_block(_ctx(repo))

    assert "Changed files: NONE" in block
    assert "unavailable" not in block, "a clean repo is a known state, not an unavailable one"


# ── C0: T17d — degradation ─────────────────────────────────────────────────


def test_non_git_workspace_degrades_without_raising(tmp_path: Path) -> None:
    """T17d — advisory input must never fail the run."""
    plan = tmp_path / "PLAN.md"
    plan.write_text(_PLAN, encoding="utf-8")

    block = _eval_evidence_block(_ctx(tmp_path, plan))

    assert "unavailable" in block
    assert str(plan) in block, "losing git must not cost the judge the plan"


def test_missing_git_binary_degrades(repo: Path) -> None:
    """T17d — git absent from PATH is a FileNotFoundError, not a crash."""

    def runner(*_args: object, **_kwargs: object) -> object:
        raise FileNotFoundError("git")

    block = _eval_evidence_block(_ctx(repo), runner=runner)
    assert "unavailable" in block


def test_hung_git_is_bounded_and_degrades(repo: Path) -> None:
    """T17d — a hung git must not consume the workflow deadline."""
    calls: list[object] = []

    def runner(*_args: object, **kwargs: object) -> object:
        calls.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(cmd="git", timeout=15)

    block = _eval_evidence_block(_ctx(repo), runner=runner)

    assert "unavailable" in block
    assert calls and all(t is not None for t in calls), "every git call must carry a timeout"


def test_git_nonzero_exit_is_treated_as_no_answer(repo: Path) -> None:
    """A non-zero exit must not be read as a real (empty) diff."""

    class Result:
        returncode = 128
        stdout = ""

    block = _eval_evidence_block(_ctx(repo), runner=lambda *a, **k: Result())
    assert "unavailable" in block


def test_git_is_invoked_without_check_true(repo: Path) -> None:
    """The advisory contract, pinned at the call.

    ``hygiene.pr_intent._run_git`` passes ``check=True`` and raises on
    non-zero. Reusing it here would turn a detached HEAD into a failed run.
    """
    seen: list[object] = []

    class Result:
        returncode = 0
        stdout = ""

    def runner(*_args: object, **kwargs: object) -> object:
        seen.append(kwargs.get("check"))
        return Result()

    _eval_evidence_block(_ctx(repo), runner=runner)
    assert seen and all(c is False for c in seen), f"git must be called check=False; got {seen}"


# ── C0: T17f — no plan ─────────────────────────────────────────────────────


def test_absent_plan_omits_plan_lines_entirely(repo: Path) -> None:
    """T17f — an empty heading reads as "checked, nothing there"."""
    (repo / "f.py").write_text("x\n", encoding="utf-8")

    block = _eval_evidence_block(_ctx(repo, plan_path=None))

    assert "Plan:" not in block
    assert "Plan slices" not in block
    assert "f.py" in block, "the diff must survive the plan's absence"


def test_plan_with_no_declared_slices_omits_the_slice_line(repo: Path) -> None:
    """A legacy plan must not emit an empty slice list."""
    plan = repo / "legacy.md"
    plan.write_text("# prose only, no step headings\n", encoding="utf-8")

    block = _eval_evidence_block(_ctx(repo, plan))

    assert str(plan) in block
    assert "Plan slices" not in block


def test_only_docs_that_exist_are_listed() -> None:
    """A reference the judge cannot open is worse than no reference.

    Added because the mutant replacing the existence filter with the full
    constant list SURVIVED the first battery: every other test ran against
    this repo-shaped tmp_path where the docs are absent either way.
    """
    import tempfile

    from fa.inner_loop.workflow_controller import EVAL_DOC_PATHS

    with tempfile.TemporaryDirectory() as raw:
        workspace = Path(raw)
        _git(workspace, "init", "-q", ".")
        _git(
            workspace,
            "-c",
            "user.email=t@t",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        )

        # No docs on disk yet -> nothing may be advertised.
        assert "Reference docs" not in _eval_evidence_block(_ctx(workspace))

        present = EVAL_DOC_PATHS[0]
        target = workspace / present
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# digest\n", encoding="utf-8")

        block = _eval_evidence_block(_ctx(workspace))
        assert present in block, "an existing doc must be offered"
        for absent in EVAL_DOC_PATHS[1:]:
            assert absent not in block, f"{absent} does not exist and must not be advertised"


# ── C0: T17b — truncation is announced ─────────────────────────────────────


def test_oversized_diff_is_truncated_with_a_marker(repo: Path) -> None:
    """T17b — bounded, but never silently dropped."""
    big = repo / "big.py"
    big.write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "big.py")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "b")
    big.write_text("".join(f"line_{i} = {i}\n" for i in range(20_000)), encoding="utf-8")

    block = _eval_evidence_block(_ctx(repo))

    assert "[diff truncated" in block
    assert "fs_read_file" in block, "the judge must be told how to see the rest"
    assert len(block) < EVAL_DIFF_MAX_CHARS * 2, "the cap must actually bound the block"


def test_diff_under_the_cap_is_not_truncated(repo: Path) -> None:
    """T17b (negative) — a normal slice must arrive whole."""
    (repo / "small.py").write_text("y = 2\n", encoding="utf-8")
    _git(repo, "add", "small.py")

    block = _eval_evidence_block(_ctx(repo))

    assert "[diff truncated" not in block


# ── C1: the live path ──────────────────────────────────────────────────────


def test_eval_stage_receives_the_evidence_block(repo: Path) -> None:
    """C1 (KILL-CHECK) — the block reaches the dispatched eval task.

    Asserting on the builder alone proves only that a string can be built.
    This boots the real ``run_workflow`` and captures the ``task`` each stage
    is actually dispatched with.
    """
    import argparse
    from typing import Any

    from fa.inner_loop.coder_loop import SessionOutcome
    from fa.inner_loop.workflow_controller import run_workflow

    (repo / "changed.py").write_text("NEW_CODE\n", encoding="utf-8")
    plan = repo / "PLAN.md"
    plan.write_text(_PLAN, encoding="utf-8")
    config = repo / "models.yaml"
    config.write_text("providers: {}\n", encoding="utf-8")

    dispatched: dict[str, str] = {}

    def stage(args: argparse.Namespace, **kwargs: Any) -> int:
        dispatched[args.role] = args.task or ""
        sink = kwargs.get("outcome_sink")
        if args.role == "eval" and sink is not None:
            sink.append(
                SessionOutcome(
                    exit_code=0,
                    stop_reason="stopped_by_llm",
                    turns=1,
                    final_text="### Verdict\nPASS\n### Step results\n- S1: PASS - ok\n- S7: PASS - ok\n",
                )
            )
        return 0

    run_workflow(
        roles=["coder", "eval"],
        task="judge the work",
        per_role_task={},
        mode="linear",
        max_repairs=0,
        max_replans=0,
        run_id="s13-live",
        config=config,
        workspace=repo,
        max_turns=1,
        output_mode="quiet",
        run_stage_fn=stage,
        plan_path=plan,
    )

    eval_task = dispatched["eval"]
    assert "judge the work" in eval_task, "the original task must be kept, not replaced"
    assert "Evidence supplied by the harness" in eval_task
    assert str(plan) in eval_task
    assert "changed.py" in eval_task, "the judge must see what actually changed"

    assert "Evidence supplied by the harness" not in dispatched["coder"], (
        "only the judge needs the evidence block; the coder is the one being judged"
    )
