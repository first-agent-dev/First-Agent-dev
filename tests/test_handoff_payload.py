"""S10.5 — workflow handoff payload + K budget (CT6, G3; audits F1/F2).

root=workflow_tool class=C0/C1 claim=CT6
oracle=handoff task text sections, ToolResult budget denial, provider facts.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult
from fa.inner_loop.tools.workflow_tool import (
    WorkflowInvocationContext,
    build_handoff_task,
    build_invoke_workflow_tool,
)


def _ctx(
    *,
    facts: dict[str, Any] | None = None,
    max_invocations: int = 2,
    blackboard_writer: Callable[[Any], None] | None = None,
) -> WorkflowInvocationContext:
    return WorkflowInvocationContext(
        parent_run_id="parent-run",
        config=Path("/tmp/cfg"),
        workspace=Path("/tmp/ws"),
        max_turns=5,
        run_stage_fn=lambda *a, **k: 0,
        workflow_timeout_seconds=1,
        max_invocations=max_invocations,
        session_facts_provider=(lambda: facts) if facts is not None else None,
        blackboard_writer=blackboard_writer,
    )


# ── build_handoff_task (C0) ────────────────────────────────────────────────


def test_handoff_goal_first_and_verbatim() -> None:
    out = build_handoff_task(goal="Fix the thing", read_paths=[], write_paths=[], search_paths=[])
    assert out.startswith("Goal: Fix the thing")
    assert "Do exactly:" in out


def test_handoff_start_here_lists_high_tier_capped_at_five() -> None:
    reads = [f"src/fa/mod{i}.py" for i in range(12)]
    out = build_handoff_task(goal="g", read_paths=reads, write_paths=[], search_paths=[])
    assert "Start here:" in out
    start_section = out.split("Start here:")[1].split("Observed")[0]
    # cap 5
    assert start_section.count("- src/") == 5


def test_handoff_observed_grouped_by_tier() -> None:
    reads = ["src/fa/x.py", "tests/t.py", "worklogs/archive/n.md"]
    out = build_handoff_task(goal="g", read_paths=reads, write_paths=[], search_paths=[])
    assert "high risk (1)" in out
    assert "medium risk (1)" in out
    assert "safe (1)" in out


def test_handoff_modified_section_lists_writes() -> None:
    out = build_handoff_task(goal="g", read_paths=[], write_paths=["src/fa/a.py", "tests/test_a.py"], search_paths=[])
    mod = (
        out.split("Modified:")[1].split("Candidate leads:")[0]
        if "Candidate leads:" in out
        else out.split("Modified:")[1]
    )
    assert "src/fa/a.py" in mod
    assert "tests/test_a.py" in mod


def test_handoff_candidate_leads_exclude_already_read_cap_10() -> None:
    reads = ["src/read0.py"]
    searches = [f"src/lead{i}.py" for i in range(15)] + ["src/read0.py"]
    out = build_handoff_task(goal="g", read_paths=reads, write_paths=[], search_paths=searches)
    leads = out.split("Candidate leads:")[1].split("Do exactly:")[0]
    # read0 already observed -> not a lead; cap 10
    assert "src/read0.py" not in leads
    assert leads.count("- src/") == 10


def test_handoff_total_paths_capped_at_30() -> None:
    reads = [f"src/r{i}.py" for i in range(40)]
    writes = [f"src/w{i}.py" for i in range(5)]
    out = build_handoff_task(goal="g", read_paths=reads, write_paths=writes, search_paths=[])
    # Start here (5) + writes (5) + observed <= 20, never blow past 30 total
    listed = out.count("- ")
    assert listed <= 31  # tolerance for the 3 "Do exactly" numbered lines


def test_handoff_no_facts_degrades_to_goal() -> None:
    out = build_handoff_task(goal="just the goal", read_paths=[], write_paths=[], search_paths=[])
    assert "Start here:" not in out
    assert "Observed (already read):" not in out
    assert "Modified:" not in out
    assert "Candidate leads:" not in out
    assert out.startswith("Goal: just the goal")


def test_handoff_uses_backslash_normalised_paths() -> None:
    out = build_handoff_task(goal="g", read_paths=["src\\fa\\x.py"], write_paths=[], search_paths=[])
    assert "src/fa/x.py" in out


# ── K budget (C1 through the tool handler) ─────────────────────────────────


def _run_tool(
    ctx: WorkflowInvocationContext,
    calls: list[dict[str, Any]],
    runner: Callable[..., tuple[int, Any]],
) -> list[ToolResult]:
    spec = build_invoke_workflow_tool(lambda **kw: runner(kw), lambda: ctx)
    results = []
    for params in calls:
        results.append(spec.handler(params))
    return results


def test_k_budget_third_call_denied_k2() -> None:
    """K=2: first two invocations run, third returns workflow_budget_exhausted."""
    runner_calls: list[dict[str, Any]] = []

    def runner(kw: dict[str, Any]) -> tuple[int, None]:
        runner_calls.append(kw)
        return 0, None

    ctx = _ctx(facts={}, max_invocations=2)
    params = {"task": "do the thing"}
    results = _run_tool(ctx, [params, params, params], runner)

    assert results[0].error is None
    assert results[1].error is None
    assert results[2].error is not None
    assert results[2].error.code == "workflow_budget_exhausted"
    assert len(runner_calls) == 2, "the third call must never reach run_workflow"


def test_handoff_reaches_run_workflow_task() -> None:
    runner_calls: list[dict[str, Any]] = []

    def runner(kw: dict[str, Any]) -> tuple[int, None]:
        runner_calls.append(kw)
        return 0, None

    facts = {
        "read_paths": ["src/fa/cli.py"],
        "write_paths": [],
        "last_search_paths": [],
    }
    ctx = _ctx(facts=facts, max_invocations=2)
    results = _run_tool(ctx, [{"task": "Refactor CLI"}], runner)
    assert results[0].error is None
    task_sent = runner_calls[0]["task"]
    assert "Goal: Refactor CLI" in task_sent
    assert "Start here:" in task_sent
    assert "src/fa/cli.py" in task_sent


def test_missing_facts_provider_degrades_goal_only() -> None:
    runner_calls: list[dict[str, Any]] = []

    def runner(kw: dict[str, Any]) -> tuple[int, None]:
        runner_calls.append(kw)
        return 0, None

    ctx = _ctx(facts=None, max_invocations=2)
    results = _run_tool(ctx, [{"task": "plain goal"}], runner)
    assert results[0].error is None
    task_sent = runner_calls[0]["task"]
    assert task_sent == "plain goal", "no facts -> the raw goal is passed through"


def test_facts_provider_exception_does_not_kill_chat() -> None:
    runner_calls: list[dict[str, Any]] = []

    def runner(kw: dict[str, Any]) -> tuple[int, None]:
        runner_calls.append(kw)
        return 0, None

    def boom() -> dict[str, Any]:
        raise RuntimeError("state gone")

    ctx = WorkflowInvocationContext(
        parent_run_id="p",
        config=Path("/c"),
        workspace=Path("/w"),
        max_turns=1,
        run_stage_fn=lambda *a, **k: 0,
        workflow_timeout_seconds=1,
        max_invocations=2,
        session_facts_provider=boom,
    )
    spec = build_invoke_workflow_tool(lambda **kw: runner(kw), lambda: ctx)
    result = spec.handler({"task": "still works"})
    assert result.error is None
    assert len(runner_calls) == 1


def test_blackboard_writer_called_with_handoff() -> None:
    written: list[dict[str, Any]] = []

    def runner(kw: dict[str, Any]) -> tuple[int, None]:
        return 0, None

    ctx = _ctx(
        facts={"read_paths": ["src/fa/a.py"], "write_paths": ["src/fa/b.py"], "last_search_paths": []},
        max_invocations=2,
        blackboard_writer=lambda entry: written.append(entry),
    )
    spec = build_invoke_workflow_tool(lambda **kw: runner(kw), lambda: ctx)
    result = spec.handler({"task": "g"})
    assert result.error is None
    assert len(written) == 1
    assert written[0]["type"] == "workflow_handoff"
    assert "src/fa/a.py" in written[0]["read_paths"]


def test_no_live_ctx_returns_workflow_unavailable() -> None:
    spec = build_invoke_workflow_tool(lambda **kw: (0, None), lambda: None)
    result = spec.handler({"task": "g"})
    assert result.error is not None
    assert result.error.code == "workflow_unavailable"


# ── CT6 (SA-3): K is read from runtime_limits, not hardcoded in the CLI seam ──


def test_cli_ctx_provider_reads_k_from_limits(tmp_path: Path) -> None:
    """C2: the CLI workflow-context provider must pass limits.max_workflow_invocations
    into the tool context. Producer kill-check: hardcoding the constant in cli.py
    (the S10.8 mutation) must fail this test.

    Fact provider + blackboard writer are wired against a live SessionState.
    """
    from fa.cli import _make_workflow_ctx_provider
    from fa.inner_loop import EventLog, SessionState
    from fa.inner_loop.registry import ToolCall
    from fa.inner_loop.runtime_limits import RuntimeLimits

    limits = RuntimeLimits(
        max_workflow_invocations=3,
        calibration_epsilon=0.1,
        min_flag_runs=7,
        chat_escalation_gate=False,
    )
    state_ref: list[SessionState | None] = [None]
    provider = _make_workflow_ctx_provider(
        parent_run_id="parent-run",
        config=tmp_path / "config.yaml",
        workspace=tmp_path,
        max_turns=5,
        limits=limits,
        session_context=None,
        run_context=None,
        session_db=None,
        transport=None,
        secrets=None,
        state_ref=state_ref,
    )
    # Before state exists: facts degrade to {} (goal-only), context still carries K.
    ctx_pre = provider()
    assert ctx_pre.max_invocations == 3

    # After a live state records paths, the facts provider reads them live.
    log = EventLog(tmp_path / "events.jsonl", run_id="p")
    state = SessionState(workspace_root=tmp_path, run_id="p", log=log)
    state.record_tool_call(ToolCall(name="fs_read_file", params={"path": "src/fa/cli.py"}, call_id=""))
    state_ref[0] = state

    ctx_post = provider()
    facts_fn = ctx_post.session_facts_provider
    assert facts_fn is not None
    facts = facts_fn()
    assert facts["read_paths"] == ["src/fa/cli.py"]
    assert ctx_post.max_invocations == 3
    # default-K sanity: a stock RuntimeLimits yields the documented default 2
    assert RuntimeLimits().max_workflow_invocations == 2


def test_hardcoded_k_constant_breaks_config_override(tmp_path: Path) -> None:
    """Re-statement that pins the contract: overriding the knob in RuntimeLimits
    changes the enforced budget end-to-end through _check_budget."""
    from fa.inner_loop.tools.workflow_tool import _check_budget

    ctx = _ctx(facts={}, max_invocations=4)
    # invocation_count 0..3 allowed; the 4th denied
    assert _check_budget(3, ctx) is None
    denied = _check_budget(4, ctx)
    assert denied is not None
    assert denied.error is not None
    assert denied.error.code == "workflow_budget_exhausted"
