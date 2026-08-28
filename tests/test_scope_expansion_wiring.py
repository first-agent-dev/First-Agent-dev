"""S10.4 — scope expansion C1 wiring at drive_session (CT2/CT4/CT5).

Root: ``drive_session``. Provider I/O is mocked; EventLog, SessionState,
transaction counters, and prompt composition are real. Oracles: the composed
request body (ConditionalSkills + turn_context) and durable scope_expansion
events — not intermediate lists.

Kill-checks (each must discriminate):
  - remove the per-turn rebuild (accumulate turn_context) -> stale L2 text at L3
  - omit skills_conditional at a compose call site -> request lacks ConditionalSkills
  - remove the scope_expansion log.append -> durable-event tests fail
  - drop the F3 binding -> the skill body never reaches the request
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from fa.inner_loop import EventLog, SessionState
from fa.inner_loop.coder_loop import drive_session
from fa.inner_loop.hooks import HookRegistry
from fa.inner_loop.registry import ToolCall, ToolRegistry
from tests.fixtures.session_wiring import (
    make_mock_chain,
    mock_success_response,
    mock_tool_call_response,
)

S3_HINT_MARKER = "ZZ-PREEXISTING-TURN-CONTEXT-ZZ"


def _expansion_events(state: SessionState) -> list[Any]:
    log = state.log
    assert log is not None
    return [e for e in log.read_all() if e.kind == "scope_expansion"]


def _state_with_files(
    tmp_path: Path,
    *,
    reads: list[str] | None = None,
    writes: list[str] | None = None,
) -> SessionState:
    """Real SessionState; drive counters through record_tool_call (prod path)."""
    log = EventLog(tmp_path / "events.jsonl", run_id="expansion-c1")
    state = SessionState(workspace_root=tmp_path, run_id="expansion-c1", log=log)
    for path in reads or []:
        state.record_tool_call(ToolCall(name="fs_read_file", params={"path": path}, call_id=""))
    for path in writes or []:
        state.record_tool_call(ToolCall(name="fs_write_file", params={"path": path}, call_id=""))
    return state


def _drive(
    state: SessionState,
    *,
    scope_mode: str,
    max_turns: int = 1,
    registry: ToolRegistry | None = None,
) -> MagicMock:
    chain = make_mock_chain(context_limit=100_000, compaction_threshold=None)
    if max_turns > 1:
        tool_turns = [
            mock_tool_call_response(f"call-{i}", "fs_read_file", {"path": f"loop{i}.py"}) for i in range(max_turns - 1)
        ]
        chain.request.side_effect = [*tool_turns, mock_success_response("done")]
    else:
        chain.request.return_value = mock_success_response("done")
    drive_session(
        "expansion C1",
        provider_chain=chain,
        registry=registry if registry is not None else ToolRegistry(),
        hooks=HookRegistry(),
        state=state,
        role="chat",
        max_turns=max_turns,
        turn_context=S3_HINT_MARKER,
        scope_mode=scope_mode,
    )
    return chain


def _sent_payloads(chain: MagicMock) -> list[str]:
    out: list[str] = []
    for call in chain.request.call_args_list:
        out.append(repr(call.args) + repr(call.kwargs))
    return out


# ── P1/P6: high-tier write escalates to L3 ─────────────────────────────────


def test_high_tier_write_emits_escalation_and_event(tmp_path: Path) -> None:
    """C1: a src/ write at the boundary escalates; the request names
    invoke_workflow and a durable scope_expansion row is written."""
    state = _state_with_files(tmp_path, writes=["src/fa/cli.py"])
    chain = _drive(state, scope_mode="chat_direct")

    body = "\n".join(_sent_payloads(chain))
    assert "Scope escalation" in body
    assert "Do exactly" in body
    events = _expansion_events(state)
    assert len(events) == 1
    assert events[0].content["level_to"] == 3
    assert events[0].content["evidence"] == "high_tier_write"
    assert events[0].content["write_tier"] == 5


def test_escalation_preserves_preexisting_context(tmp_path: Path) -> None:
    """RK-H: the rebuilt turn_context must not clobber the S3 hint channel."""
    state = _state_with_files(tmp_path, writes=["src/fa/x.py"])
    chain = _drive(state, scope_mode="chat_direct")
    body = "\n".join(_sent_payloads(chain))
    assert S3_HINT_MARKER in body


# ── P2: high-tier read arms L2 and injects skill (F3 / CT5) ────────────────


def test_high_tier_read_arms_l2_and_injects_skill_block(tmp_path: Path) -> None:
    """C1: a src/ READ (no write) arms level 2; the request carries a
    ConditionalSkills block with a real planner-skill body, frontmatter
    stripped, and a scope_expansion event to level 2."""
    # Point the reader at the repo's real skills tree.
    repo_skills = Path(__file__).resolve().parents[1] / "knowledge" / "skills"
    state = _state_with_files(tmp_path, reads=["src/fa/state.py"])
    # The state's workspace is tmp_path; symlink the skills dir so the reader
    # resolves <workspace>/knowledge/skills the same way production does.
    (tmp_path / "knowledge").mkdir(exist_ok=True)
    skills_link = tmp_path / "knowledge" / "skills"
    if not skills_link.exists():
        skills_link.symlink_to(repo_skills, target_is_directory=True)

    chain = _drive(state, scope_mode="chat_direct")

    body = "\n".join(_sent_payloads(chain))
    assert "ConditionalSkills" in body, "L2 entry request must carry the skill block channel"
    assert "plan-authoring" in body
    # frontmatter never reaches the request
    assert "triggers:" not in body.split("ConditionalSkills", 1)[1]
    events = _expansion_events(state)
    assert len(events) == 1
    assert events[0].content["level_to"] == 2
    assert events[0].content["evidence"] == "read_high_arm"


def test_no_skill_block_when_not_armed(tmp_path: Path) -> None:
    """A clean level-1 run never carries ConditionalSkills."""
    state = _state_with_files(tmp_path, writes=["worklogs/archive/note.md"])
    chain = _drive(state, scope_mode="chat_direct")
    body = "\n".join(_sent_payloads(chain))
    assert "ConditionalSkills" not in body
    assert _expansion_events(state) == []


# ── P5: tier-gated counters — safe bulk stays silent ───────────────────────


def test_safe_bulk_archive_stays_silent(tmp_path: Path) -> None:
    """C1 (P5): 15 safe archive writes, no high tier -> no escalation event,
    no invoke_workflow advice."""
    state = _state_with_files(tmp_path, writes=[f"worklogs/archive/2026/08/note{i}.md" for i in range(15)])
    chain = _drive(state, scope_mode="chat_direct")
    body = "\n".join(_sent_payloads(chain))
    assert _expansion_events(state) == []
    assert "Scope escalation" not in body


# ── RK-I: workflow_linear never re-escalates ───────────────────────────────


def test_workflow_linear_seed_is_silent(tmp_path: Path) -> None:
    state = _state_with_files(tmp_path, writes=["src/fa/x.py"], reads=["src/fa/y.py"])
    _drive(state, scope_mode="workflow_linear")
    assert _expansion_events(state) == []


# ── F4: no scope_tripwire producer remains ─────────────────────────────────


def test_retired_tripwire_kind_not_emitted(tmp_path: Path) -> None:
    state = _state_with_files(tmp_path, reads=["src/fa/a.py"] * 15)
    _drive(state, scope_mode="chat_direct")
    log = state.log
    assert log is not None
    assert all(e.kind != "scope_tripwire" for e in log.read_all())


# ── CT4: verification posture line at high write ───────────────────────────


def test_high_write_carries_verification_posture(tmp_path: Path) -> None:
    state = _state_with_files(tmp_path, writes=["src/fa/z.py"])
    chain = _drive(state, scope_mode="chat_direct")
    body = "\n".join(_sent_payloads(chain))
    assert "erification" in body
    assert "Risk tier high" in body


# ── CT6 SA-2: budget-exhausted tool denial surfaces the terminal observation ──


def test_workflow_budget_exhausted_latches_terminal_observation(tmp_path: Path) -> None:
    """C1: when a tool returns workflow_budget_exhausted, the NEXT request must
    carry the explicit 'exhausted' terminal line and a durable expansion_exhausted
    event is written. Producer kill-check: removing the latch in coder_loop must
    break this (it was a mutation survivor)."""
    from fa.inner_loop.registry import ToolResult, ToolSpec
    from fa.inner_loop.tools import build_baseline_registry

    log = EventLog(tmp_path / "events.jsonl", run_id="exhausted-c1")
    state = SessionState(workspace_root=tmp_path, run_id="exhausted-c1", log=log)

    registry = build_baseline_registry(tmp_path, bash_timeout_seconds=30)
    # Register a fake invoke_workflow that refuses with the budget code.
    registry.register(
        ToolSpec(
            name="invoke_workflow",
            description="fake escalating tool that has spent its budget",
            input_schema={"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"]},
            permission="workspace",
            handler=lambda params: ToolResult.fail(
                "workflow_budget_exhausted",
                "workflow escalation budget of 2 invocation(s) used; report state to operator",
            ),
        )
    )

    chain = make_mock_chain(context_limit=100_000, compaction_threshold=None)
    # Turn 1: the model calls the (refusing) tool; turn 2: text reply.
    chain.request.side_effect = [
        mock_tool_call_response("ex-1", "invoke_workflow", {"task": "handle it"}),
        mock_success_response("done"),
    ]

    drive_session(
        "exhausted C1",
        provider_chain=chain,
        registry=registry,
        hooks=HookRegistry(),
        state=state,
        role="chat",
        max_turns=2,
        scope_mode="chat_direct",
    )

    # Durable signal landed.
    exhausted_events = [e for e in log.read_all() if e.kind == "expansion_exhausted"]
    assert len(exhausted_events) == 1, "workflow_budget_exhausted must log expansion_exhausted once"

    # The terminal observation reaches a later request body.
    payloads = []
    for call in chain.request.call_args_list:
        payloads.append(repr(call.args) + repr(call.kwargs))
    full = "\n".join(payloads)
    assert "budget" in full.lower() and "operator" in full.lower(), (
        "the SA-2 terminal 'budget used -> report to operator' line never reached the model"
    )
