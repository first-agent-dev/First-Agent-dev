"""S4b — ``invoke_workflow``: the chat role's escalation path to the pipeline.

Test classes (per the ``tests-writing`` skill):

* **C1** — composition-root proof at ``cli._build_run_tool_registry``, the
  builder a live ``fa run`` actually uses. Registry membership alone is L2;
  the kill-checks below make it L3.
* **C0p** — pure/property coverage of the two total helpers (``child_run_id``,
  ``parse_roles``) where the interesting inputs are adversarial rather than
  representative.

**Fixture honesty.** ``run_workflow_fn`` is a REAL callable carrying
``run_workflow``'s true keyword-only signature, not a ``MagicMock``. A mock
would accept any kwargs at all, so it could not catch the failure this slice is
most likely to ship: calling the controller with a wrong or missing keyword.
``_RecordingWorkflow`` records what it was called with and the tests assert on
those kwargs.

**Oracle ranking.** (1) the structured ``ToolResult`` fields, (2) the kwargs
actually handed to the injected controller — above all the ``run_id``, and
(3) registry membership last, because membership is the weakest of the three.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.registry import ToolResult, ToolSpec, validate_tool_schema_portability
from fa.inner_loop.tool_names import is_valid_wire_name
from fa.inner_loop.tools.workflow_tool import (
    WorkflowInvocationContext,
    build_invoke_workflow_tool,
    child_run_id,
    parse_roles,
)
from fa.inner_loop.workflow_artifacts import FlowState
from fa.inner_loop.workflow_controller import (
    DEADLINE_REASON_MARKER,
    MAX_REPAIRS_CEILING,
    MAX_REPLANS_CEILING,
    WORKFLOW_DEADLINE_EXIT_CODE,
)
from tests._chat_registry_fixture import build_live_chat_registry

# The stricter of the two production validators (``session/manager.py``); a run
# id acceptable to it is also acceptable to ``cli.py``'s pattern.
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _TerminalState(  # noqa: N802 - factory named for the value it produces
    *, status: str = "DONE", route: str = "", reason: str = "done"
) -> FlowState:
    """Build a REAL ``FlowState``, not a stand-in.

    Type-honest fixtures (skill §5): the production type has fourteen fields
    and the tool reads three of them. A hand-rolled stub would keep passing if
    ``status`` were renamed or retyped, so the real dataclass is used and only
    the fields under test are varied.
    """
    return FlowState(
        run_id="child",
        task="t",
        status=status,  # type: ignore[arg-type]  # FlowStatus is a Literal; tests exercise it as str
        active_role="eval",
        active_plan_id="child",
        active_plan_version=1,
        last_route_decision=route,
        last_transition_reason=reason,
    )


class _RecordingWorkflow:
    """A real callable with ``run_workflow``'s keyword-only signature.

    Every parameter is spelled out so that a handler passing a wrong or unknown
    keyword raises ``TypeError`` here, exactly as the production controller
    would. That is the point of not using a mock.
    """

    def __init__(
        self,
        *,
        exit_code: int = 0,
        terminal_state: FlowState | None = None,
        raises: BaseException | None = None,
        on_call: Any = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._exit_code = exit_code
        self._terminal_state: FlowState | None = _TerminalState() if terminal_state is None else terminal_state
        self._raises = raises
        self._on_call = on_call

    def force_missing_terminal_state(self) -> None:
        """Model a corrupt/absent ``flow_state.json``.

        ``run_workflow`` legitimately returns ``None`` for the terminal state
        when the artifact is missing or unparseable, so the tool must survive
        it. Exposed as a method rather than poking a private attribute.
        """
        self._terminal_state = None

    def __call__(
        self,
        *,
        roles: list[str],
        task: str | None,
        per_role_task: Mapping[str, str | None],
        mode: str,
        max_repairs: int,
        max_replans: int,
        run_id: str,
        config: Path,
        workspace: Path,
        max_turns: int,
        output_mode: str = "console",
        run_stage_fn: Any,
        transport: Any = None,
        secrets: Mapping[str, str] | None = None,
        session_context: Any = None,
        run_context: Any = None,
        session_db: Any = None,
        deadline_mono: float | None = None,
    ) -> tuple[int, FlowState | None]:
        self.calls.append(
            {
                "roles": roles,
                "task": task,
                "per_role_task": per_role_task,
                "mode": mode,
                "max_repairs": max_repairs,
                "max_replans": max_replans,
                "run_id": run_id,
                "config": config,
                "workspace": workspace,
                "max_turns": max_turns,
                "output_mode": output_mode,
                "run_stage_fn": run_stage_fn,
                "deadline_mono": deadline_mono,
            }
        )
        if self._on_call is not None:
            self._on_call()
        if self._raises is not None:
            raise self._raises
        return self._exit_code, self._terminal_state


def _ctx(tmp_path: Path, *, parent_run_id: str = "run-parent", timeout: int = 1800) -> WorkflowInvocationContext:
    return WorkflowInvocationContext(
        parent_run_id=parent_run_id,
        config=tmp_path / "models.yaml",
        workspace=tmp_path,
        max_turns=4,
        run_stage_fn=lambda ns, **kw: 0,
        workflow_timeout_seconds=timeout,
    )


def _tool(workflow: _RecordingWorkflow, ctx: WorkflowInvocationContext | None) -> ToolSpec:
    return build_invoke_workflow_tool(workflow, lambda: ctx)


def _call(spec: ToolSpec, **params: object) -> ToolResult:
    return spec.handler(params)


def _payload(result: ToolResult) -> dict[str, Any]:
    """Return the structured result, asserting success first.

    ``ToolResult.result`` is ``Any | None``, so every read would otherwise need
    a type-ignore. Narrowing here keeps the tests type-honest AND makes each
    caller assert the happy path before indexing into it.
    """
    assert result.error is None, f"unexpected failure: {result.error}"
    assert isinstance(result.result, dict)
    return result.result


def _error_code(result: ToolResult) -> str:
    """Return the failure code, asserting that the call actually failed."""
    assert result.error is not None, f"expected a failure, got {result.summary!r}"
    return result.error.code


# ── C0p: pure helpers ───────────────────────────────────────────────────────


@pytest.mark.parametrize("parent_len", [1, 8, 100, 120, 124, 125, 126, 128, 200])
@pytest.mark.parametrize("n", [1, 2, 10, 99])
def test_child_run_id_always_satisfies_the_run_id_grammar(parent_len: int, n: int) -> None:
    """C0p — the derived id must be accepted by BOTH production validators.

    Naive concatenation overflows: a 125-character parent plus ``-wf1`` is 129
    characters, which ``^[A-Za-z0-9_.-]{1,128}$`` (cli.py) and
    ``[A-Za-z0-9][A-Za-z0-9_.-]{0,127}`` (session/manager.py) both reject.
    """
    derived = child_run_id("p" * parent_len, n)
    assert len(derived) <= 128
    assert _RUN_ID_RE.match(derived), f"{derived!r} violates the run-id grammar"


@pytest.mark.parametrize("parent_len", [1, 124, 125, 200])
def test_child_run_id_truncates_the_parent_never_the_discriminator(parent_len: int) -> None:
    """C0p — truncating the tail would destroy the thing that makes it unique."""
    assert child_run_id("p" * parent_len, 7).endswith("-wf7")


def test_child_run_ids_are_distinct_across_invocation_numbers() -> None:
    """C0p — even at the truncation boundary, ids must not collide."""
    parent = "p" * 130
    assert len({child_run_id(parent, n) for n in range(1, 21)}) == 20


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("planner,coder,eval", ["planner", "coder", "eval"]),
        ("  planner , coder ", ["planner", "coder"]),
        ("coder", ["coder"]),
        ("coder,,eval", ["coder", "eval"]),
        ("", []),
        (" , ", []),
        (",,,", []),
    ],
)
def test_parse_roles_is_total(raw: str, expected: list[str]) -> None:
    """C0p — parsing never raises; unusable input yields ``[]`` for the handler."""
    assert parse_roles(raw) == expected


# ── C1: the ToolSpec itself ────────────────────────────────────────────────


def test_tool_spec_is_provider_portable(tmp_path: Path) -> None:
    """C1 — the schema and wire name must survive a real provider request."""
    spec = _tool(_RecordingWorkflow(), _ctx(tmp_path))
    assert spec.name == "invoke_workflow"
    assert is_valid_wire_name(spec.name)
    assert spec.permission == "workspace", "a tool that runs a pipeline is not read-only"
    validate_tool_schema_portability(spec.name, spec.input_schema)


def test_schema_bounds_match_the_controller_ceilings(tmp_path: Path) -> None:
    """C1 — the advertised caps are read from source, not hardcoded here.

    A model that reads the schema and sends ``max_repairs: 5`` should be told
    by the schema itself that the ceiling is 3.
    """
    spec = _tool(_RecordingWorkflow(), _ctx(tmp_path))
    props = spec.input_schema["properties"]
    assert isinstance(props, dict)
    assert props["max_repairs"]["maximum"] == MAX_REPAIRS_CEILING
    assert props["max_replans"]["maximum"] == MAX_REPLANS_CEILING
    assert spec.input_schema["additionalProperties"] is False
    assert spec.input_schema["required"] == ["task"]


# ── C1: composition root — registration ────────────────────────────────────


def test_invoke_workflow_registered(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — removing the registration in ``cli`` fails this test.

    ``_build_run_tool_registry`` is the builder a live ``fa run`` uses, so this
    asserts the tool is in the corpus the model is actually offered.
    """
    registry = build_live_chat_registry(tmp_path, parent_run_id="run-x")
    assert "invoke_workflow" in {spec.name for spec in registry.specs()}


@pytest.mark.parametrize("role", ["coder", "planner", "eval", "researcher"])
def test_invoke_workflow_is_chat_only(role: str, tmp_path: Path) -> None:
    """C1 — a pipeline stage must not be able to launch another pipeline.

    This is the static half of the recursion argument: the thread-local guard
    stops a chat session re-entering, and this stops the stage roles from ever
    holding the tool in the first place.
    """
    registry = build_live_chat_registry(tmp_path, parent_run_id="run-x", role=role)
    assert "invoke_workflow" not in {spec.name for spec in registry.specs()}


def test_chat_without_workflow_context_degrades_observably(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """C1 (failure-observable) — no silent skip.

    A chat registry built outside a live run legitimately has nothing to
    escalate into. It must still build, and it must say why the tool is absent.
    """
    with caplog.at_level("WARNING"):
        registry = build_live_chat_registry(tmp_path, with_workflow_ctx=False)
    names = {spec.name for spec in registry.specs()}
    assert "invoke_workflow" not in names
    assert "fs_read_file" in names, "the rest of the chat corpus must survive"
    assert any("invoke_workflow is unavailable" in r.message for r in caplog.records)


def test_registered_tool_is_never_batched_in_parallel(tmp_path: Path) -> None:
    """C1 — a nested pipeline must not run concurrently with other tools.

    Asserted through the real scheduler rather than by reading the constant:
    ``permission="workspace"`` already forces serial dispatch, and the
    ``_NEVER_PARALLEL_TOOLS`` entry restates that intent. Either mechanism
    alone satisfies this, which is what makes the assertion robust.
    """
    from fa.inner_loop.loop import classify_batches
    from fa.inner_loop.registry import ToolCall, ToolRegistry

    registry = ToolRegistry()
    registry.register(_tool(_RecordingWorkflow(), _ctx(tmp_path)))
    from fa.inner_loop.tools import build_read_file_tool

    registry.register(build_read_file_tool(tmp_path))
    batches = classify_batches(
        [
            ToolCall(name="fs_read_file", params={"path": "a.py"}, call_id="r"),
            ToolCall(name="invoke_workflow", params={"task": "t"}, call_id="w"),
        ],
        registry,
    )
    assert len(batches) == 2, "invoke_workflow shared a batch with another tool"


# ── C1: handler behaviour, happy path ──────────────────────────────────────


def test_handler_invokes_run_workflow_once_with_a_child_run_id(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — reusing the parent run id fails this test.

    A shared run id was measured to corrupt three things: the parent's
    telemetry (shared ``events.jsonl``), the ``global_history`` row (PRIMARY
    KEY + INSERT OR REPLACE, so the parent's later write erases the child's),
    and the child's own artifacts on a second call.
    """
    workflow = _RecordingWorkflow()
    result = _call(_tool(workflow, _ctx(tmp_path)), task="ship the thing")

    assert result.error is None
    assert len(workflow.calls) == 1, "the pipeline must run exactly once per tool call"
    passed = workflow.calls[0]["run_id"]
    assert passed != "run-parent", "the child must not reuse the parent run id"
    assert passed.startswith("run-parent"), "the child id must remain traceable to its parent"
    assert _payload(result)["run_id"] == passed, "the reported id must be the one actually used"


def test_successive_calls_allocate_distinct_child_ids(tmp_path: Path) -> None:
    """C1 — a second escalation must not overwrite the first one's artifacts."""
    workflow = _RecordingWorkflow()
    spec = _tool(workflow, _ctx(tmp_path))
    first = _call(spec, task="one")
    second = _call(spec, task="two")
    assert _payload(first)["run_id"].endswith("-wf1")
    assert _payload(second)["run_id"].endswith("-wf2")
    assert [c["run_id"] for c in workflow.calls] == [
        _payload(first)["run_id"],
        _payload(second)["run_id"],
    ]


def test_long_parent_run_id_stays_valid(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — concatenating without truncating fails this test."""
    workflow = _RecordingWorkflow()
    spec = _tool(workflow, _ctx(tmp_path, parent_run_id="p" * 125))
    result = _call(spec, task="x")
    assert result.error is None
    child = _payload(result)["run_id"]
    assert len(child) <= 128
    assert _RUN_ID_RE.match(child), f"{child!r} would be rejected by the session manager"


def test_defaults_are_applied_in_the_handler(tmp_path: Path) -> None:
    """C1 — the documented defaults reach the controller, not just the schema.

    The schema deliberately carries no ``default`` keys, so if the handler did
    not apply them the controller would receive nothing.
    """
    workflow = _RecordingWorkflow()
    _call(_tool(workflow, _ctx(tmp_path)), task="x")
    call = workflow.calls[0]
    assert call["mode"] == "linear"
    assert call["roles"] == ["planner", "coder", "eval"]
    assert call["max_repairs"] == 2
    assert call["max_replans"] == 1
    assert call["per_role_task"] == {}
    assert call["output_mode"] == "quiet", "a nested pipeline must not print over the chat turn"


def test_explicit_arguments_are_forwarded(tmp_path: Path) -> None:
    """C1 — operator/model-supplied values must not be silently ignored."""
    workflow = _RecordingWorkflow()
    _call(
        _tool(workflow, _ctx(tmp_path)),
        task="x",
        mode="adaptive",
        roles="coder,eval",
        max_repairs=3,
        max_replans=0,
    )
    call = workflow.calls[0]
    assert call["mode"] == "adaptive"
    assert call["roles"] == ["coder", "eval"]
    assert call["max_repairs"] == 3
    assert call["max_replans"] == 0


def test_out_of_range_budgets_are_clamped_to_the_ceilings(tmp_path: Path) -> None:
    """C1 — the ceilings hold even for a caller that bypasses schema validation."""
    workflow = _RecordingWorkflow()
    _call(_tool(workflow, _ctx(tmp_path)), task="x", max_repairs=99, max_replans=99)
    assert workflow.calls[0]["max_repairs"] == MAX_REPAIRS_CEILING
    assert workflow.calls[0]["max_replans"] == MAX_REPLANS_CEILING


def test_context_values_are_forwarded_to_the_controller(tmp_path: Path) -> None:
    """C1 — the tool must drive the pipeline with the LIVE session's values."""
    workflow = _RecordingWorkflow()
    ctx = _ctx(tmp_path)
    _call(_tool(workflow, ctx), task="x")
    call = workflow.calls[0]
    assert call["config"] == ctx.config
    assert call["workspace"] == ctx.workspace
    assert call["max_turns"] == ctx.max_turns
    assert call["run_stage_fn"] is ctx.run_stage_fn, "the injected dispatcher must be used"


def test_a_deadline_is_always_supplied(tmp_path: Path) -> None:
    """C1 (RK6) — an escalation must never be able to run unbounded.

    ``deadline_mono=None`` means "no deadline" in the controller, so the tool
    passing None would silently reinstate the unbounded behaviour RK6 exists to
    remove.
    """
    workflow = _RecordingWorkflow()
    _call(_tool(workflow, _ctx(tmp_path, timeout=60)), task="x")
    assert workflow.calls[0]["deadline_mono"] is not None


# ── C1: handler behaviour, failure paths ───────────────────────────────────


def test_invalid_mode_is_refused(tmp_path: Path) -> None:
    """C1 — ``repair`` was removed (Q3); the handler is the fail-closed half."""
    result = _call(_tool(_RecordingWorkflow(), _ctx(tmp_path)), task="x", mode="repair")
    assert _error_code(result) == "invalid_mode"


def test_invalid_roles_are_refused(tmp_path: Path) -> None:
    """C1 — an empty role list would otherwise reach the controller."""
    workflow = _RecordingWorkflow()
    result = _call(_tool(workflow, _ctx(tmp_path)), task="x", roles=" , ")
    assert _error_code(result) == "invalid_roles"
    assert workflow.calls == [], "the pipeline must not start on invalid input"


def test_empty_task_is_refused(tmp_path: Path) -> None:
    """C1 — a whitespace-only task is not a task."""
    result = _call(_tool(_RecordingWorkflow(), _ctx(tmp_path)), task="   ")
    assert _error_code(result) == "invalid_params"


def test_missing_context_is_reported_not_crashed(tmp_path: Path) -> None:
    """C1 (failure-observable) — no live run means a structured refusal."""
    result = _call(_tool(_RecordingWorkflow(), None), task="x")
    assert _error_code(result) == "workflow_unavailable"


def test_workflow_error_is_contained(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — letting the exception propagate fails this test.

    An escaping exception would end the operator's chat turn over a failure in
    a nested pipeline whose artifacts are already on disk and inspectable.
    """
    workflow = _RecordingWorkflow(raises=RuntimeError("pipeline blew up"))
    result = _call(_tool(workflow, _ctx(tmp_path)), task="x")
    assert _error_code(result) == "workflow_error"
    assert result.error is not None
    assert "pipeline blew up" in result.error.message


def test_reentrant_call_is_refused(tmp_path: Path) -> None:
    """C1 (KILL-CHECK) — dropping the guard fails this test.

    Simulates the recursion case directly: the pipeline, while running, causes
    the same tool to be dispatched again on the same thread.
    """
    holder: dict[str, ToolResult] = {}

    def reenter() -> None:
        holder["inner"] = _call(spec, task="nested")

    workflow = _RecordingWorkflow(on_call=reenter)
    spec = _tool(workflow, _ctx(tmp_path))

    outer = _call(spec, task="outer")

    assert _error_code(holder["inner"]) == "workflow_reentrant"
    assert outer.error is None, "the outer call must still succeed"
    assert len(workflow.calls) == 1, "the nested call must not have started a pipeline"


def test_guard_is_released_after_a_failed_run(tmp_path: Path) -> None:
    """C1 — a crashed pipeline must not wedge the tool for the whole session.

    The guard is released in a ``finally``; without it the first failure would
    make every later escalation return ``workflow_reentrant``.
    """
    spec = _tool(_RecordingWorkflow(raises=RuntimeError("boom")), _ctx(tmp_path))
    assert _error_code(_call(spec, task="first")) == "workflow_error"

    ok_spec = _tool(_RecordingWorkflow(), _ctx(tmp_path))
    assert _call(ok_spec, task="second").error is None


def test_guard_is_thread_local_not_process_global(tmp_path: Path) -> None:
    """C1 — one thread's in-flight pipeline must not refuse another thread.

    Read-only tool batches are dispatched on a ThreadPoolExecutor, so a plain
    module-level bool would be observable across unrelated workers.
    """
    started = threading.Event()
    release = threading.Event()

    def block() -> None:
        started.set()
        release.wait(timeout=5)

    slow = _tool(_RecordingWorkflow(on_call=block), _ctx(tmp_path))
    other = _tool(_RecordingWorkflow(), _ctx(tmp_path, parent_run_id="run-other"))
    outcome: dict[str, ToolResult] = {}

    worker = threading.Thread(target=lambda: outcome.setdefault("slow", _call(slow, task="slow")))
    worker.start()
    try:
        assert started.wait(timeout=5), "the blocking pipeline never started"
        outcome["fast"] = _call(other, task="fast")
    finally:
        release.set()
        worker.join(timeout=5)

    assert outcome["fast"].error is None, "a different thread was wrongly refused"
    assert outcome["slow"].error is None


# ── C1: result contract ────────────────────────────────────────────────────


def test_result_carries_the_ct4_fields(tmp_path: Path) -> None:
    """C1 — the model reads these fields; their names are a contract.

    Note the absence of ``verdict``: ``run_workflow`` returns
    ``(exit_code, FlowState)`` and FlowState has no verdict, while the status
    mapping is lossy (BLOCKED -> FAILED), so it cannot be reconstructed here.
    """
    workflow = _RecordingWorkflow(exit_code=0, terminal_state=_TerminalState(status="DONE", route="complete"))
    result = _call(_tool(workflow, _ctx(tmp_path)), task="x")
    assert set(_payload(result)) == {"run_id", "exit_code", "status", "route", "timed_out"}
    assert _payload(result)["exit_code"] == 0
    assert _payload(result)["status"] == "DONE"
    assert _payload(result)["route"] == "complete"
    assert _payload(result)["timed_out"] is False


def test_timed_out_is_reported_distinctly_from_failure(tmp_path: Path) -> None:
    """C1 (RK6) — "ran out of time" and "failed" must be tellable apart.

    Keyed off ``DEADLINE_REASON_MARKER``, the controller-side constant, so the
    two sides cannot drift.
    """
    workflow = _RecordingWorkflow(
        exit_code=WORKFLOW_DEADLINE_EXIT_CODE,
        terminal_state=_TerminalState(status="FAILED", reason=f"{DEADLINE_REASON_MARKER} after 12s"),
    )
    result = _call(_tool(workflow, _ctx(tmp_path)), task="x")
    assert _payload(result)["timed_out"] is True
    assert _payload(result)["exit_code"] == WORKFLOW_DEADLINE_EXIT_CODE

    ordinary = _RecordingWorkflow(exit_code=1, terminal_state=_TerminalState(status="FAILED", reason="stage exited 1"))
    assert _payload(_call(_tool(ordinary, _ctx(tmp_path)), task="x"))["timed_out"] is False


def test_missing_terminal_state_degrades_to_empty_strings(tmp_path: Path) -> None:
    """C1 — ``run_workflow`` may legitimately return ``None`` for the state.

    A corrupt or missing ``flow_state.json`` must surface as empty fields, not
    an ``AttributeError`` inside the tool.
    """
    workflow = _RecordingWorkflow(exit_code=1)
    workflow.force_missing_terminal_state()
    result = _call(_tool(workflow, _ctx(tmp_path)), task="x")
    assert result.error is None
    assert _payload(result)["status"] == ""
    assert _payload(result)["route"] == ""
    assert _payload(result)["timed_out"] is False
