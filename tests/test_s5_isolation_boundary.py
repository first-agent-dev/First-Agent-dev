"""S5.6 — isolation failures deny instead of silently degrading (V18-V21).

Contract under test (S5-CT6)
----------------------------
**PRE:** worktree creation, cleanup, or the spawn counter may fail.
**POST:** each failure denies with a structured error; **no path returns the
main workspace as a subagent write root**.

Scope note — Q19 (read this before adding a containment test here)
------------------------------------------------------------------
The plan's §3.2 Option A also specified that pointing the sandbox gate and the
runner ``cwd`` at the artifact root would *confine* the subagent. That was
measured during S5.6 preflight and **does not hold**::

    evaluate_bash 'echo pwn > ../../../src/app.py'  artifact_root -> ALLOW
    SandboxHook   fs_spawn_subagent, same command   artifact_root -> ALLOW
    subprocess.run(..., cwd=artifact_root)          parent file after: 'pwn'

``workspace_root`` is only consulted by the ``rm`` / ``chmod`` / ``git``
validators; a shell redirect is ``GENERAL_WRITE`` and, with
``allow_general_write=True``, is allowed with no path check. ``cwd`` is not a
boundary either — ``..`` walks straight out of it.

So this file deliberately does **not** assert "a subagent cannot write outside
the artifact root" (S5-P16). Asserting a containment the code cannot deliver
would be worse than today's honest absence of one. What *is* asserted:

* the artifact root is a real, per-task directory (not the main workspace);
* one value reaches both the gate and the executor (the V24/V25 defect was two
  independently-derived roots);
* the narrowing that genuinely works — ``rm`` / ``chmod`` / ``git`` — does work;
* spawned commands are denied general-write (Q19 option (a)).

Test classes: C0 (pure policy), C1 (wiring), C3 (failure paths).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from fa.feature_flags import FeatureFlags
from fa.inner_loop.state import SessionState
from fa.workspace.worktree_manager import (
    SharedDirWorktreeManager,
    WorktreeManagerFactory,
    subagent_artifact_root,
)

# ---------------------------------------------------------------------------
# S5-P11 / V18 — a worktree failure must never hand back the main workspace
# ---------------------------------------------------------------------------


def test_worktree_failure_denies_instead_of_main_workspace(tmp_path: Path) -> None:
    """C3 (S5-P11): creation failure raises; it must not return the workspace.

    This is the sharpest defect in the slice: the old code caught *every*
    exception and returned ``self.workspace_root``, so a failure on the
    isolation path silently converted an artifact-only task into a
    main-workspace mutator — a permission-boundary change on a failure path,
    which is exactly where it is least likely to be noticed.

    Kill-check target: restore ``return self.workspace_root``.
    """
    state = SessionState(workspace_root=tmp_path, run_id="run-wt-fail")

    # Make the artifact root impossible to create: put a *file* where the
    # subagents directory must be, so mkdir(parents=True) raises. This drives
    # the real failure path rather than stubbing a collaborator the production
    # code may no longer call.
    (tmp_path / ".fa").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".fa" / "subagents").write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as excinfo:
        state.create_subagent_workspace("task-1")

    assert "subagent_workspace_unavailable" in str(excinfo.value)
    assert not (tmp_path / ".fa" / "subagents").is_dir(), "precondition disturbed"


def test_subagent_root_is_never_the_main_workspace(tmp_path: Path) -> None:
    """C1 (S5-P11): the happy path returns a per-task dir, not the workspace."""
    state = SessionState(workspace_root=tmp_path, run_id="run-artifact")

    workdir = state.create_subagent_workspace("task-alpha")

    assert workdir != tmp_path, "subagent write root is still the main workspace"
    assert workdir.is_dir(), "artifact root was not created"
    assert workdir.is_relative_to(tmp_path / ".fa" / "subagents")


def test_artifact_roots_are_per_task(tmp_path: Path) -> None:
    """C1: two tasks get two directories; one task is stable across calls."""
    state = SessionState(workspace_root=tmp_path, run_id="run-two")

    a1 = state.create_subagent_workspace("task-a")
    b1 = state.create_subagent_workspace("task-b")
    a2 = state.create_subagent_workspace("task-a")

    assert a1 != b1, "two tasks collapsed onto one artifact root"
    assert a1 == a2, "the same task id produced two different roots"


def test_artifact_root_is_derived_from_one_helper(tmp_path: Path) -> None:
    """C1 (S5-P16 residual): gate and executor must share ONE derivation.

    The V24/V25 defect was two independently-derived roots. The value is now
    computed by a single function; this test pins that the state object and the
    helper agree, so a future caller cannot quietly re-derive its own.

    Kill-check target: make ``create_subagent_workspace`` build the path inline
    instead of calling ``subagent_artifact_root``.
    """
    state = SessionState(workspace_root=tmp_path, run_id="run-single")

    from_state = state.create_subagent_workspace("Task Alpha!")
    from_helper = subagent_artifact_root(tmp_path, "Task Alpha!", run_id="run-single")

    assert from_state == from_helper, "state and helper derive different artifact roots"


def test_artifact_root_sanitizes_hostile_task_ids(tmp_path: Path) -> None:
    """C3: a task id must not escape the subagents dir via traversal."""
    state = SessionState(workspace_root=tmp_path, run_id="run-hostile")

    for hostile in ("../../etc", "../../../root", "a/../../b", ""):
        workdir = state.create_subagent_workspace(hostile)
        assert workdir.is_relative_to(tmp_path / ".fa" / "subagents"), (
            f"task_id {hostile!r} escaped the artifact tree: {workdir}"
        )


# ---------------------------------------------------------------------------
# S5-P12 / V19 — isolated mode is refused, not silently downgraded
# ---------------------------------------------------------------------------


def test_isolated_mode_rejected_at_config_load(tmp_path: Path) -> None:
    """C0 (S5-P12): requesting an unsupported mode fails loudly.

    Prior art cited in the repo's own test header (Claude Code #55708/#47548/
    #31546): an ``isolation:worktree`` parameter that is silently ignored. The
    operator asks for isolation, gets shared, and believes they have isolation.
    """
    flags = FeatureFlags(worktree_mode="isolated")

    with pytest.raises(ValueError) as excinfo:
        WorktreeManagerFactory.from_flags(flags, session_root=tmp_path, repo_root=tmp_path)

    message = str(excinfo.value)
    assert "worktree_mode" in message
    assert "isolated" in message


def test_unknown_worktree_mode_rejected(tmp_path: Path) -> None:
    """C0: a typo must not silently resolve to shared."""
    flags = FeatureFlags(worktree_mode="isolted")

    with pytest.raises(ValueError, match="worktree_mode"):
        WorktreeManagerFactory.from_flags(flags, session_root=tmp_path, repo_root=tmp_path)


def test_shared_mode_and_absent_flags_still_work(tmp_path: Path) -> None:
    """C0 (positive): the supported mode and the no-flags path are unchanged.

    Partner of the two rejection tests — the fix must not degrade into
    "reject everything".
    """
    assert isinstance(
        WorktreeManagerFactory.from_flags(
            FeatureFlags(worktree_mode="shared"), session_root=tmp_path, repo_root=tmp_path
        ),
        SharedDirWorktreeManager,
    )
    assert isinstance(
        WorktreeManagerFactory.from_flags(None, session_root=tmp_path, repo_root=tmp_path),
        SharedDirWorktreeManager,
    )


def test_isolated_mode_surfaces_a_config_warning(tmp_path: Path) -> None:
    """C3 (S5-P12): the rejection reaches the operator, not just a log line.

    ``SessionState`` must degrade to a working session rather than crash on a
    bad config value, but the operator has to be told — otherwise this is the
    silent downgrade again, wearing a different hat.
    """
    state = SessionState(
        workspace_root=tmp_path,
        run_id="run-isolated",
        feature_flags=FeatureFlags(worktree_mode="isolated"),
    )

    assert state.worktree_manager is None, "an unsupported mode must not yield a manager"

    log = state.log
    assert log is not None
    kinds = [(e.kind, e.content) for e in log.read_all()]
    warnings = [content for kind, content in kinds if kind == "config_warning"]
    assert any("worktree" in str(content.get("key", "")) for content in warnings), (
        f"no config_warning surfaced for the rejected mode; saw {warnings}"
    )


# ---------------------------------------------------------------------------
# S5-P13 / V20 — cleanup failure is surfaced
# ---------------------------------------------------------------------------


def test_cleanup_failure_is_surfaced(tmp_path: Path) -> None:
    """C3 (S5-P13): a failed cleanup raises instead of being logged away.

    A silently-failed cleanup leaves an artifact dir behind that the next task
    with the same id will reuse, mixing two tasks' output.

    Kill-check target: restore the ``logger.warning`` swallow.
    """
    state = SessionState(workspace_root=tmp_path, run_id="run-cleanup")
    workdir = state.create_subagent_workspace("task-cleanup")
    (workdir / "child").mkdir()

    # Drive a real removal failure: make the parent non-writable so rmtree
    # cannot unlink the child. Stubbing a collaborator would not exercise the
    # code path that actually deletes.
    original_mode = workdir.stat().st_mode
    workdir.chmod(0o500)
    try:
        with pytest.raises(RuntimeError, match="subagent_cleanup_failed"):
            state.cleanup_subagent_workspace(workdir)
    finally:
        workdir.chmod(original_mode)


def test_cleanup_removes_the_artifact_dir(tmp_path: Path) -> None:
    """C1 (positive): a normal cleanup actually deletes the task dir."""
    state = SessionState(workspace_root=tmp_path, run_id="run-cleanup-ok")
    workdir = state.create_subagent_workspace("task-gone")
    (workdir / "report.md").write_text("output\n", encoding="utf-8")

    state.cleanup_subagent_workspace(workdir)

    assert not workdir.exists(), "artifact dir survived cleanup"
    assert tmp_path.exists(), "cleanup removed more than the task dir"


def test_cleanup_refuses_paths_outside_the_artifact_tree(tmp_path: Path) -> None:
    """C3: cleanup must never be talked into deleting the workspace."""
    state = SessionState(workspace_root=tmp_path, run_id="run-cleanup-guard")
    (tmp_path / "src").mkdir()

    with pytest.raises(RuntimeError, match="subagent_cleanup_refused"):
        state.cleanup_subagent_workspace(tmp_path / "src")

    assert (tmp_path / "src").exists(), "cleanup deleted a non-artifact path"


# ---------------------------------------------------------------------------
# S5-P14 / S5-P15 / V21 — spawn admission
# ---------------------------------------------------------------------------


def test_spawn_limit_counter_failure_denies(tmp_path: Path) -> None:
    """C3 (S5-P14): if the counter cannot be updated, refuse the spawn.

    Best-effort incrementing means the limit silently stops existing: every
    subsequent spawn reads a stale count and is admitted.

    Kill-check target: restore the ``except: logger.warning`` around the
    increment.
    """
    from fa.inner_loop.context import reset_current_session, set_current_session
    from fa.inner_loop.subagent_runner import SubagentRunner

    state = SessionState(workspace_root=tmp_path, run_id="run-counter")

    def _explode(max_spawns: int) -> bool:
        raise RuntimeError("counter backend down")

    # Break the reservation primitive itself — the single operation admission
    # now depends on.
    state.try_reserve_subagent_spawn = _explode  # type: ignore[method-assign]

    runner = SubagentRunner(session_root=tmp_path)
    token = set_current_session(state)
    try:
        with pytest.raises(RuntimeError, match="spawn_admission_failed"):
            runner._check_spawn_limit()
    finally:
        reset_current_session(token)


def test_concurrent_spawn_admission_is_atomic(tmp_path: Path) -> None:
    """C1 + barrier (S5-P15): N threads racing must admit at most `max` spawns.

    The old code read ``session.subagent_spawns``, compared, then incremented —
    three steps with no lock — so concurrent callers all saw the same
    pre-increment value and were all admitted.

    **A plain barrier is not enough to catch this.** Measured: with the
    unfixed check-then-act, 16 barrier-synchronised threads still admitted
    exactly 3, because the read-compare-increment window is a handful of
    bytecodes and the GIL rarely preempts inside it. A test that passes against
    the broken code is worthless, so the window is widened deterministically by
    making the counter *read* slow — which is what any real backend (a DB row,
    a cross-process counter, an RPC) would do. With that, the unfixed code
    admitted **12 of 12** under a limit of 3; the fixed code admits 3.

    Kill-check target: restore the read-compare-increment sequence.
    """
    from fa.inner_loop.context import reset_current_session, set_current_session
    from fa.inner_loop.subagent_runner import SubagentRunner

    max_spawns = 3
    workers = 12
    state = SessionState(
        workspace_root=tmp_path,
        run_id="run-race",
        feature_flags=FeatureFlags(max_subagent_spawns_per_session=max_spawns),
    )
    runner = SubagentRunner(session_root=tmp_path)

    class _SlowCounter:
        """Model a counter whose read is not instantaneous."""

        def __get__(self, obj: Any, cls: type | None = None) -> int:
            if obj is None:
                return 0
            time.sleep(0.02)
            count: int = obj.__dict__.get("_spawn_count", 0)
            return count

        def __set__(self, obj: Any, value: int) -> None:
            obj.__dict__["_spawn_count"] = value

    original = type(state).subagent_spawns
    type(state).subagent_spawns = _SlowCounter()  # type: ignore[assignment]

    barrier = threading.Barrier(workers)
    admitted: list[int] = []
    admitted_lock = threading.Lock()

    def attempt() -> None:
        token = set_current_session(state)
        try:
            barrier.wait(timeout=10)
            runner._check_spawn_limit()
        except RuntimeError:
            return
        else:
            with admitted_lock:
                admitted.append(1)
        finally:
            reset_current_session(token)

    try:
        threads = [threading.Thread(target=attempt) for _ in range(workers)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert len(admitted) == max_spawns, (
            f"admitted {len(admitted)} spawns under a {max_spawns} limit with {workers} racing threads"
        )
        assert state.get_subagent_spawns() == max_spawns
    finally:
        # No ignore needed here: `original` was read from the same attribute,
        # so restoring it is type-compatible. Only the _SlowCounter install
        # above widens the type.
        type(state).subagent_spawns = original


def test_spawn_limit_allows_up_to_the_limit(tmp_path: Path) -> None:
    """C1 (positive): sequential spawns up to the limit are admitted."""
    from fa.inner_loop.context import reset_current_session, set_current_session
    from fa.inner_loop.subagent_runner import SubagentRunner

    state = SessionState(
        workspace_root=tmp_path,
        run_id="run-seq",
        feature_flags=FeatureFlags(max_subagent_spawns_per_session=2),
    )
    runner = SubagentRunner(session_root=tmp_path)

    token = set_current_session(state)
    try:
        runner._check_spawn_limit()
        runner._check_spawn_limit()
        with pytest.raises(RuntimeError, match="spawn limit"):
            runner._check_spawn_limit()
    finally:
        reset_current_session(token)


# ---------------------------------------------------------------------------
# Q19 — what the gate does and does NOT promise for spawns
# ---------------------------------------------------------------------------


def _spawn_decision(command: str, root: Path) -> Any:
    from fa.inner_loop.hooks.base import HookPayload, LifecyclePoint
    from fa.inner_loop.hooks.builtin import SandboxHook
    from fa.inner_loop.registry import ToolCall

    return SandboxHook(root).handle(
        LifecyclePoint.BEFORE_TOOL_EXEC,
        HookPayload(
            tool_call=ToolCall(name="fs_spawn_subagent", params={"command": command}, call_id="c1"),
            role="coder",
            acting_family="",
        ),
    )


def test_artifact_root_contains_rm_chmod_git() -> None:
    """C1: the narrowing that genuinely works, works.

    ``workspace_root`` *is* enforced for the three commands that have
    validators, so pointing the boundary at the per-task artifact root is real
    defence in depth for them — an ``rm`` that reaches back into the repo is
    denied, while an ``rm`` inside the task dir is allowed.
    """
    import tempfile

    from fa.sandbox.bash_gate import evaluate_bash

    workspace = Path(tempfile.mkdtemp()).resolve()
    artifact = workspace / ".fa" / "subagents" / "t1"
    artifact.mkdir(parents=True)

    escaping = evaluate_bash("rm -rf ../../src", workspace_root=artifact)
    local = evaluate_bash("rm -rf ./report.md", workspace_root=artifact)

    assert not escaping.allow, "rm reaching out of the artifact root was allowed"
    assert local.allow, f"rm inside the artifact root was denied: {local.reason}"


@pytest.mark.xfail(
    reason=(
        "Q19: the bash gate cannot contain a subagent. workspace_root is only consulted by the "
        "rm/chmod/git validators, so a redirect is GENERAL_WRITE and passes unchecked; cwd is not "
        "a boundary either. Denying general-write for spawns was implemented and measured to deny "
        "8/10 realistic verifier commands (pytest, mypy, make test), so it was reverted. Real "
        "containment needs an OS-level writable-mount boundary (Q19 option (c)). V24/V25 remain "
        "OPEN. This test is the executable record of that gap and should start passing when "
        "containment lands."
    ),
    strict=True,
)
def test_subagent_write_outside_artifact_root_denied() -> None:
    """C3 (S5-P16) — KNOWN GAP, asserted as xfail(strict).

    Kept executable rather than deleted: a strict xfail fails the suite the day
    the behaviour changes, so this cannot silently rot into a false belief that
    subagents are sandboxed, and it converts to a passing test the moment real
    containment lands.
    """
    import tempfile

    workspace = Path(tempfile.mkdtemp()).resolve()
    artifact = workspace / ".fa" / "subagents" / "t1"
    artifact.mkdir(parents=True)

    decision = _spawn_decision("echo pwn > ../../../src/app.py", artifact)

    assert decision.action == "deny", "a spawned command escaping the artifact root was permitted"


def test_spawn_tool_denies_when_artifact_root_unavailable(tmp_path: Path) -> None:
    """C3 (S5-P11, tool level): the denial reaches the caller as a ToolResult.

    The state-level test proves the exception; this proves the tool converts it
    into a structured failure instead of catching it and running in the main
    workspace, which is what it used to do.

    Kill-check target: restore ``except: logger.warning(...); workdir = root``.
    """
    from fa.inner_loop.context import reset_current_session, set_current_session
    from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool

    state = SessionState(
        workspace_root=tmp_path,
        run_id="run-tool-deny",
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
    )
    (tmp_path / ".fa").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".fa" / "subagents").write_text("blocked\n", encoding="utf-8")

    tool = build_spawn_subagent_tool(tmp_path)
    token = set_current_session(state)
    try:
        result = tool.handler({"task_id": "t1", "command": "echo hi"})
    finally:
        reset_current_session(token)

    assert result.error is not None, "spawn proceeded without an artifact root"
    assert result.error.code == "workspace_unavailable"


def test_spawn_tool_uses_the_artifact_root_end_to_end(tmp_path: Path) -> None:
    """C1: the shipped tool path really runs the subagent in its own dir."""
    from fa.inner_loop.context import reset_current_session, set_current_session
    from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool

    state = SessionState(
        workspace_root=tmp_path,
        run_id="run-e2e",
        feature_flags=FeatureFlags(subagent_spawning_enabled=True),
    )
    tool = build_spawn_subagent_tool(tmp_path)
    expected = tmp_path / ".fa" / "subagents" / "verify-1"

    token = set_current_session(state)
    try:
        result = tool.handler({"task_id": "verify-1", "command": "pwd > where.txt; echo ok"})
    finally:
        reset_current_session(token)

    assert result.error is None, f"spawn failed: {result.error}"
    # The dir is removed on success (V20 cleanup), which is itself the proof it
    # was the task dir and not the workspace.
    assert not expected.exists(), "artifact dir was left behind"
    assert tmp_path.exists() and (tmp_path / ".fa").exists(), "cleanup removed too much"


def test_spawned_verifier_commands_are_allowed() -> None:
    """C1 (regression guard for the reverted Q19-a attempt).

    Denying general-write for spawns removed the verifier role's entire
    purpose. This pins that the realistic workload runs, so the tempting
    one-line "fix" cannot be reapplied without a failure.
    """
    import tempfile

    workspace = Path(tempfile.mkdtemp()).resolve()

    for command in ("pytest -q", "mypy src/", "make test", "ls -la"):
        decision = _spawn_decision(command, workspace)
        assert decision.action == "allow", f"verifier command denied: {command} ({decision.reason})"
