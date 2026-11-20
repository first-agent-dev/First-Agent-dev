"""C0 oracles for the AI-NATIVE-PLAN-V2 grammar and admission rules (STEP9A)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from fa import cli
from fa.inner_loop import workflow_controller
from fa.inner_loop.plan_admission import (
    PLAN_V1,
    PLAN_V2,
    PlanIds,
    PlanRef,
    PlanRefError,
    PlanSnapshot,
    snapshot_from_bytes,
)
from fa.inner_loop.plan_v2 import (
    DISPOSITION_REASONS,
    MAX_DISPOSITIONS,
    PlanGraph,
    PlanV2Error,
    parse_plan,
    resolve_selectors,
)
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.runtime_limits import RuntimeLimits

_ROADMAP = """---
Roadmap-ID: RM-demo
slug: demo
---
Plan-Format: AI-NATIVE-PLAN-V2

# Roadmap — demo

## Intent

Prove the V2 grammar.

## Out of scope

Nothing here.
"""

_INVARIANT_1 = """### INV-1
KIND: HARD
TEXT: The writer never publishes without a sealed acceptance revision.
EVIDENCE: TEST_REQUIRED
"""

_INVARIANT_2 = """### INV-2
KIND: HARD
TEXT: Host readiness is proven on the approved host.
EVIDENCE: NON_EXECUTABLE
DISPOSITION-REASON: HOST_READINESS
DISPOSITION-EVIDENCE: W4 readiness run sheet row L-RCPT-2/6
DISPOSITION-OWNER: W4
"""

_INVARIANT_3 = """### INV-3
KIND: SOFT
TEXT: Logs stay human readable.
EVIDENCE: TEST_REQUIRED
"""

_INV_DUP = (
    "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: TEST_REQUIRED\n\n"
    "### INV-1\nKIND: SOFT\nTEXT: t\nEVIDENCE: TEST_REQUIRED\n"
)
_CHECK_ROW = "  CHECK-ID: CHECK-1 | STEP: STEP1 | TEST-ID[]: TEST-1.1\n"
_ACCEPT_ROW = (
    "  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish\n"
)
_SCN_DUP = (
    "### SCN-1\nPATH: p\nTRIGGER: t\nOUTCOME: o\nCT-ID[]: CT-1.1\n\n"
    "### SCN-1\nPATH: p\nTRIGGER: t\nOUTCOME: o\nCT-ID[]: CT-1.1\n"
)

_MINIMAL_SLICE = """## SLICE1: sealed acceptance
STEPS: outcome
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
ACCEPTANCE:
KILL-TARGETS:
STEP-EXIT-CHECKS:
"""

_SCENARIO = """### SCN-1
PATH: seal then coder
TRIGGER: coder starts
OUTCOME: refusal without a seal
CT-ID[]: CT-1.1
"""


def _increment(*, invariants: str = "", scenario: str = "", slice_body: str = "") -> str:
    body = slice_body or _SLICE
    return (
        "---\nIncrement-ID: I01\nstatus: OUTLINED\n---\n"
        "Plan-Format: AI-NATIVE-PLAN-V2\n\n"
        f"## INVARIANTS\n{invariants or (_INVARIANT_1 + chr(10) + _INVARIANT_2)}\n"
        f"## SCENARIOS\n{scenario or _SCENARIO}\n"
        f"{body}"
    )


_SLICE = """## SLICE1: sealed acceptance
STEPS: prescriptive
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish
KILL-TARGETS:
  TARGET-ID: publication.publish_plan | CT: CT-1.1 | TEST-ID: TEST-1.1
STEP-EXIT-CHECKS:
  CHECK-ID: CHECK-1 | STEP: STEP1 | TEST-ID[]: TEST-1.1
- [ ] STEP1: publish through the sealed authority. EXIT-CHECK: CHECK-1
"""


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(PlanV2Error) as refused:
        callable_()
    return refused.value.rule


def _parse(increment: str) -> object:
    return parse_plan(roadmap=_ROADMAP, increment=increment)


def test_parses_a_complete_v2_plan_into_a_typed_graph() -> None:
    graph = parse_plan(roadmap=_ROADMAP, increment=_increment())

    assert [item.id for item in graph.invariants] == ["INV-1", "INV-2"]
    assert graph.invariants[1].evidence == "NON_EXECUTABLE"
    assert graph.invariants[1].reason == "HOST_READINESS"
    assert graph.invariants[1].owner == "W4"
    assert [scn.id for scn in graph.scenarios] == ["SCN-1"]
    assert graph.scenarios[0].ct_ids == ("CT-1.1",)
    planned = graph.slices[0]
    assert planned.number == "1" and planned.steps_mode == "prescriptive"
    assert [contract.id for contract in planned.contracts] == ["CT-1.1", "CT-1.2"]
    assert planned.contracts[0].inv == "INV-1"
    assert planned.acceptance[0].selector.endswith("::test_publish")
    assert planned.kill_targets[0].test_id == "TEST-1.1"
    assert planned.exit_checks[0].test_ids == ("TEST-1.1",)
    assert planned.steps[0].check_id == "CHECK-1"


def test_rejects_a_missing_or_duplicated_format_marker() -> None:
    missing = _increment().replace("Plan-Format: AI-NATIVE-PLAN-V2\n", "", 1)
    assert _rule(lambda: _parse(missing)) == "plan-format-marker-increment"

    duplicated = _increment().replace(
        "Plan-Format: AI-NATIVE-PLAN-V2\n", "Plan-Format: AI-NATIVE-PLAN-V2\nPlan-Format: AI-NATIVE-PLAN-V2\n", 1
    )
    assert _rule(lambda: _parse(duplicated)) == "plan-format-marker-increment"

    roadmap_missing = _ROADMAP.replace("Plan-Format: AI-NATIVE-PLAN-V2\n", "", 1)
    assert _rule(lambda: parse_plan(roadmap=roadmap_missing, increment=_increment())) == "plan-format-marker-roadmap"


def test_rejects_a_foreign_format_marker() -> None:
    foreign = _increment().replace("Plan-Format: AI-NATIVE-PLAN-V2", "Plan-Format: AI-NATIVE-PLAN-V1", 1)

    assert _rule(lambda: _parse(foreign)) == "plan-format-marker-increment"


def test_fenced_examples_are_never_parsed() -> None:
    fenced = _increment(slice_body="```markdown\n## SLICE9: example\nSTEPS: prescriptive\n```\n" + _SLICE)

    graph = parse_plan(roadmap=_ROADMAP, increment=fenced)
    assert [planned.number for planned in graph.slices] == ["1"]


def test_rejects_an_unterminated_fence() -> None:
    broken = _increment(slice_body="```markdown\n## SLICE9: example\n" + _SLICE)

    assert _rule(lambda: _parse(broken)) == "unterminated-fence"


@pytest.mark.parametrize(
    ("invariants", "rule"),
    [
        ("### INV-1\nKIND: MAYBE\nTEXT: t\nEVIDENCE: TEST_REQUIRED\n", "invariant-INV-1-kind"),
        ("### INV-1\nKIND: HARD\nEVIDENCE: TEST_REQUIRED\n", "invariant-INV-1-text"),
        ("### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: MAYBE\n", "invariant-INV-1-evidence"),
        ("### INV-1\nKIND: HARD\nTEXT: t\n", "invariant-INV-1-evidence"),
        (
            "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: NON_EXECUTABLE\n",
            "invariant-INV-1-disposition-reason",
        ),
        (
            "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: NON_EXECUTABLE\n"
            "DISPOSITION-REASON: BECAUSE\nDISPOSITION-EVIDENCE: e\nDISPOSITION-OWNER: W4\n",
            "disposition-reason-unratified",
        ),
        (
            "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: NON_EXECUTABLE\n"
            "DISPOSITION-REASON: HOST_READINESS\nDISPOSITION-EVIDENCE: e\nDISPOSITION-OWNER: coder\n",
            "disposition-owner-invalid",
        ),
        (
            "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: TEST_REQUIRED\nDISPOSITION-REASON: HOST_READINESS\n",
            "disposition-without-non-executable",
        ),
        (_INV_DUP, "duplicate-invariant-id"),
        ("### NOPE-1\nKIND: HARD\nTEXT: t\nEVIDENCE: TEST_REQUIRED\n", "invariants-unknown-heading"),
    ],
)
def test_invariant_rules_are_closed(invariants: str, rule: str) -> None:
    assert _rule(lambda: _parse(_increment(invariants=invariants))) == rule


def test_disposition_count_is_bounded() -> None:
    blocks = []
    for index in range(MAX_DISPOSITIONS + 1):
        blocks.append(
            f"### INV-{index + 1}\nKIND: HARD\nTEXT: t{index}\nEVIDENCE: NON_EXECUTABLE\n"
            "DISPOSITION-REASON: HOST_READINESS\nDISPOSITION-EVIDENCE: e\nDISPOSITION-OWNER: W4\n"
        )
    slashed = _increment(invariants="\n".join(blocks), slice_body=_SLICE.replace("INV-1", "INV-1"))

    assert _rule(lambda: _parse(slashed)) == "too-many-dispositions"


def test_the_ratified_reason_vocabulary_stays_closed() -> None:
    assert DISPOSITION_REASONS == frozenset(
        {"HOST_READINESS", "DEPLOYMENT_IDENTITY", "OWNER_APPROVAL", "DURABILITY_POWER_LOSS"}
    )


@pytest.mark.parametrize(
    ("slice_body", "rule"),
    [
        (_SLICE.replace("STEPS: prescriptive\n", ""), "slice-1-steps-mode"),
        (_SLICE.replace("STEPS: prescriptive", "STEPS: fancy"), "slice-1-steps-mode"),
        (_SLICE.replace("[FUNCTIONAL]", "[MAYBE]"), "slice-1-contract-entry"),
        (_SLICE.replace("INV: INV-1:", "INV: INV-9:"), "dangling-invariant-edge"),
        (_SLICE.replace("TEST-1.1 | CT: CT-1.1", "TEST-1.1 | CT: CT-1.9"), "dangling-contract-edge"),
        (_SLICE.replace("::test_publish", "::"), "acceptance-selector-invalid"),
        (
            _SLICE.replace("worklogs/demo/acceptance/tests/test_publish.py", "tests/test_publish.py"),
            "acceptance-selector-invalid",
        ),
        (
            _SLICE.replace("CT: CT-1.1 | TEST-ID: TEST-1.1", "CT: CT-1.2 | TEST-ID: TEST-1.1"),
            "kill-target-attribution-mismatch",
        ),
        (
            _SLICE.replace("TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR", "TEST-ID: TEST-2.1 | CT: CT-1.1 | SELECTOR"),
            "acceptance-test-id-invalid",
        ),
        (_SLICE.replace("TEST-ID[]: TEST-1.1", "TEST-ID[]: TEST-9.9"), "exit-check-test-unmapped"),
        (_SLICE.replace("EXIT-CHECK: CHECK-1\n", "EXIT-CHECK: CHECK-7\n"), "exit-check-unmapped"),
        (_SLICE.replace("EXIT-CHECK: CHECK-1\n", "\n"), "step-1-exit-check-missing"),
        (_SLICE.replace("- [ ] STEP1:", "TESTS: tests/test_a.py\n- [ ] STEP1:"), "orphan-v1-token"),
        (
            _SLICE.replace(_CHECK_ROW, _CHECK_ROW + _CHECK_ROW),
            "duplicate-exit-check-id",
        ),
        (_SLICE.replace("| STEP: STEP1 |", "| STEP: STEP2 |"), "exit-check-step-unmapped"),
        (_SLICE.replace("STEPS: prescriptive", "unknown line here\nSTEPS: prescriptive"), "slice-1-unknown-field"),
        (_SLICE + "stray exit-check line\n", "slice-1-exit-check-entry"),
    ],
)
def test_slice_rules_refuse_invalid_graphs(slice_body: str, rule: str) -> None:
    assert _rule(lambda: _parse(_increment(slice_body=slice_body))) == rule


def test_a_hard_contract_without_a_test_or_disposition_is_refused() -> None:
    assert _rule(lambda: _parse(_increment(slice_body=_MINIMAL_SLICE))) == "hard-contract-without-executable-evidence"


def test_a_hard_contract_with_a_typed_disposition_is_admitted() -> None:
    invariants = (
        _INVARIANT_1.replace("EVIDENCE: TEST_REQUIRED", "EVIDENCE: NON_EXECUTABLE")
        + "DISPOSITION-REASON: OWNER_APPROVAL\n"
        + "DISPOSITION-EVIDENCE: operator approval 2026-11-20\n"
        + "DISPOSITION-OWNER: operator\n\n"
        + _INVARIANT_2
    )

    graph = parse_plan(roadmap=_ROADMAP, increment=_increment(invariants=invariants, slice_body=_MINIMAL_SLICE))
    assert graph.invariants[0].evidence == "NON_EXECUTABLE"
    assert graph.invariants[0].reason == "OWNER_APPROVAL"


def test_top_level_sections_are_closed() -> None:
    breakage = _increment().replace("## SLICE1:", "## PHASE1:")
    assert _rule(lambda: _parse(breakage)) == "unknown-top-level-section"

    stray = _increment().replace("## INVARIANTS", "stray prose\n\n## INVARIANTS", 1)
    assert _rule(lambda: _parse(stray)) == "content-outside-sections"

    duplicated = _increment().replace(
        "## SCENARIOS", "## INVARIANTS\n### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: TEST_REQUIRED\n## SCENARIOS", 1
    )
    assert _rule(lambda: _parse(duplicated)) == "duplicate-section"


@pytest.mark.parametrize(
    ("scenario", "rule"),
    [
        ("### SCN-1\nPATH: p\nTRIGGER: t\nOUTCOME: o\nCT-ID[]: CT-9.9\n", "dangling-scenario-edge"),
        ("### SCN-1\nPATH: p\nTRIGGER: t\nOUTCOME: o\n", "scenario-SCN-1-ct-ids"),
        (
            "### SCN-1\nPATH: p\nTRIGGER: t\nOUTCOME: o\nCT-ID[]: CT-1.1, CT-1.1\n",
            "scenario-SCN-1-ct-ids",
        ),
        (_SCN_DUP, "duplicate-scenario-id"),
        ("### OTHER\nPATH: p\n", "scenarios-unknown-heading"),
    ],
)
def test_scenario_rules_are_closed(scenario: str, rule: str) -> None:
    assert _rule(lambda: _parse(_increment(scenario=scenario))) == rule


def test_duplicate_selector_ownership_is_refused() -> None:
    duplicated = _ACCEPT_ROW.replace("TEST-1.1", "TEST-1.2")
    body = _SLICE.replace("ACCEPTANCE:\n" + _ACCEPT_ROW, "ACCEPTANCE:\n" + _ACCEPT_ROW + duplicated)

    assert _rule(lambda: _parse(_increment(slice_body=body))) == "duplicate-selector-ownership"


def test_resolve_selectors_binds_one_exact_nodeid_and_fails_closed() -> None:
    graph = parse_plan(roadmap=_ROADMAP, increment=_increment())
    path = "worklogs/demo/acceptance/tests/test_publish.py"

    resolved = resolve_selectors(graph, {path: (f"{path}::test_publish",)})
    assert resolved == {"TEST-1.1": f"{path}::test_publish"}

    assert _rule(lambda: resolve_selectors(graph, {})) == "selector-uncollected"
    assert _rule(lambda: resolve_selectors(graph, {path: (f"{path}::test_other",)})) == "selector-uncollected"
    assert (
        _rule(lambda: resolve_selectors(graph, {path: (f"{path}::test_publish[a]", f"{path}::test_publish[b]")}))
        == "selector-ambiguous"
    )
    assert (
        _rule(lambda: resolve_selectors(graph, {"other/test_publish.py": ("other/test_publish.py::test_publish",)}))
        == "selector-uncollected"
    )


def test_duplicate_format_marker_in_one_document_is_refused() -> None:
    doubled = _increment().replace("## INVARIANTS", "Plan-Format: AI-NATIVE-PLAN-V2\n\n## INVARIANTS", 1)

    assert _rule(lambda: _parse(doubled)) == "plan-format-marker-increment"


# -- Public handles for sibling suites ---------------------------------------
# The seal and verifier banks need a real admitted V2 plan; they reuse these
# instead of growing a second copy of the grammar fixtures.
ROADMAP_DOCUMENT = _ROADMAP
SLICE_DOCUMENT = _SLICE


def plan_document(*, invariants: str = "", scenario: str = "", slice_body: str = "") -> str:
    """One complete V2 increment document, optionally with a replaced slice."""
    return _increment(invariants=invariants, scenario=scenario, slice_body=slice_body)


def plan_graph(*, invariants: str = "", scenario: str = "", slice_body: str = "") -> PlanGraph:
    """The admitted graph for ``plan_document``, or the closed grammar refusal."""
    return parse_plan(
        roadmap=ROADMAP_DOCUMENT,
        increment=plan_document(invariants=invariants, scenario=scenario, slice_body=slice_body),
    )


# --- SLICE1: the admission cutover (format, graph, and closed rules) ---------


def test_admission_format_comes_from_route_never_from_document_bytes() -> None:
    """The route picks the grammar; identical bytes must admit differently.

    The same V2 increment is captured twice: once by a route that declares
    ``PLAN-V2`` and once by the frozen V1 route. If the bytes decided the
    grammar, both snapshots would be identical — they are not, and the V1 one
    shows the concrete harm: the V1 extractor reads the V2 headings as V1
    slices and the V1 rules then judge them.
    """
    increment = _increment()
    path = "worklogs/demo/increments/increment-01-demo.md"

    v2 = snapshot_from_bytes(path, increment.encode("utf-8"), format=PLAN_V2, roadmap=_ROADMAP)
    assert v2.format == PLAN_V2
    assert v2.format_error is None
    assert isinstance(v2.graph, PlanGraph)
    assert v2.ids == PlanIds()  # the V1 extractor never ran on V2 bytes
    assert workflow_controller._validate_plan_admission(v2).outcome == "PASS"

    v1 = snapshot_from_bytes(path, increment.encode("utf-8"))
    assert v1.format == PLAN_V1
    assert v1.ids.slices == ("SLICE1",)  # V1 headings matched inside a V2 document
    v1_validation = workflow_controller._validate_plan_admission(v1)
    assert v1_validation.outcome != "PASS"
    assert {item.validator for item in v1_validation.diagnostics} == {"precheck"}

    with pytest.raises(PlanRefError) as refused:
        snapshot_from_bytes(path, increment.encode("utf-8"), format="PLAN-V3")
    assert refused.value.rule == "format-unknown"


def test_v2_admission_surfaces_closed_rule_codes_not_exceptions() -> None:
    """A malformed V2 document is a diagnostic, never an exception or a repair prompt."""
    broken = _increment().replace("Plan-Format: AI-NATIVE-PLAN-V2\n", "")
    snapshot = snapshot_from_bytes(
        "worklogs/demo/increments/increment-01-demo.md",
        broken.encode("utf-8"),
        format=PLAN_V2,
        roadmap=_ROADMAP,
    )

    assert snapshot.graph is None  # no partial graph escapes
    assert snapshot.format_error == "plan-format-marker-increment"
    validation = workflow_controller._validate_plan_admission(snapshot)
    assert validation.outcome == "INDETERMINATE"
    assert [(item.validator, item.rule, item.severity) for item in validation.diagnostics] == [
        ("plan-v2", "plan-format-marker-increment", "ERROR")
    ]


def test_v2_document_is_never_judged_by_v1_validators() -> None:
    """The V1-only requirements must not reach a V2 plan's verdict."""
    increment = _increment()
    assert "TESTS:" not in increment and "INTENT:" not in increment

    snapshot = snapshot_from_bytes(
        "worklogs/demo/increments/increment-01-demo.md",
        increment.encode("utf-8"),
        format=PLAN_V2,
        roadmap=_ROADMAP,
    )
    validation = workflow_controller._validate_plan_admission(snapshot)

    assert validation.outcome == "PASS"
    assert validation.diagnostics == ()
    assert snapshot.ids.slice_records == ()  # nothing for the V1 rules to judge
    # ...while the same document on the V1 route is judged and refused.
    v1 = workflow_controller._validate_plan_admission(
        snapshot_from_bytes("worklogs/demo/increments/increment-01-demo.md", increment.encode("utf-8"))
    )
    assert v1.outcome != "PASS"


def test_v2_snapshot_without_a_roadmap_is_refused_not_downgraded() -> None:
    """The pair is required; a missing roadmap never falls back to a single-document parse."""
    snapshot = snapshot_from_bytes(
        "worklogs/demo/increments/increment-01-demo.md",
        _increment().encode("utf-8"),
        format=PLAN_V2,
    )

    assert snapshot.graph is None
    assert snapshot.format_error == "roadmap-missing"
    assert workflow_controller._validate_plan_admission(snapshot).outcome == "INDETERMINATE"


def test_coder_never_dispatches_without_bound_admission_on_a_v2_route() -> None:
    """The legacy fail-open for stage fixtures does not extend to a PLAN-V2 run."""
    legacy = SimpleNamespace(admission=None, plan_format=PLAN_V1)
    v2 = SimpleNamespace(admission=None, plan_format=PLAN_V2)

    assert workflow_controller._admit_plan(legacy, None, None) is True  # unchanged legacy behaviour
    assert workflow_controller._admit_plan(v2, None, None) is False


def test_a_hand_built_v2_snapshot_without_a_graph_never_passes() -> None:
    """The dataclass is public, so admission cannot trust it to be well formed."""
    forged = PlanSnapshot(
        ref=PlanRef("worklogs/demo/increments/increment-01-demo.md", "BOOTSTRAP", "0" * 64),
        utf8_bytes=_increment().encode("utf-8"),
        text=_increment(),
        ids=PlanIds(),
        format=PLAN_V2,
    )

    validation = workflow_controller._validate_plan_admission(forged)

    assert validation.outcome == "INDETERMINATE"
    assert [item.rule for item in validation.diagnostics] == ["graph-missing"]


# --- CT-1.5: one workflow entry point, callable by a human -------------------


@dataclass
class _Recorder:
    """Captures what the CLI front asks the tool to do."""

    params: dict[str, object] | None = None
    ctx_provider: object | None = None
    result: ToolResult | None = None

    def build(self, run_workflow_fn: object, ctx_provider: object) -> ToolSpec:
        self.ctx_provider = ctx_provider

        def handler(params: Mapping[str, object]) -> ToolResult:
            self.params = dict(params)
            return self.result or ToolResult.ok("done", result={"exit_code": 0, "status": "DONE"})

        return ToolSpec(
            name="invoke_workflow",
            description="recorder",
            input_schema={"type": "object", "properties": {}},
            permission="workspace",
            handler=handler,
        )


def _invoke_args(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "task": "ship the sealed project",
        "task_flag": None,
        "roles": "planner,coder,eval",
        "mode": "linear",
        "run_id": "wf-manual-test",
        "max_turns": 3,
        "config": Path("config/models.yaml"),
        "workspace": Path("/tmp/workspace"),
        "session_id": None,
        "project_action": "CREATE_NEW",
        "project_slug": "demo-project",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_invoke_workflow_cli_calls_the_same_tool_the_chat_registers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The human front is the tool, not a second pipeline: same builder, same params."""
    recorder = _Recorder()
    monkeypatch.setattr(cli, "build_invoke_workflow_tool", recorder.build)
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda args, run_id: (run_id, None, None, None))
    monkeypatch.setattr(cli, "load_runtime_limits_from_path", lambda: SimpleNamespace(limits=RuntimeLimits()))

    exit_code = cli._cmd_invoke_workflow(_invoke_args())

    assert exit_code == 0
    assert recorder.params == {
        "task": "ship the sealed project",
        "roles": "planner,coder,eval",
        "mode": "linear",
        "project_action": "CREATE_NEW",
        "project_slug": "demo-project",
    }
    # The provider the CLI hands the tool is the same closure shape the chat
    # registry uses, so the child run is assembled by the same code.
    assert callable(recorder.ctx_provider)


def test_invoke_workflow_cli_maps_a_tool_refusal_to_a_failed_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tool refusal is an operator-visible failure, never a silent success."""
    recorder = _Recorder()
    recorder.result = ToolResult.fail("invalid_project_slug", "slug must be lowercase kebab-case")
    monkeypatch.setattr(cli, "build_invoke_workflow_tool", recorder.build)
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda args, run_id: (run_id, None, None, None))
    monkeypatch.setattr(cli, "load_runtime_limits_from_path", lambda: SimpleNamespace(limits=RuntimeLimits()))

    assert cli._cmd_invoke_workflow(_invoke_args()) == 2


def test_invoke_workflow_cli_requires_a_task_before_any_lifecycle(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No task, no run: the refusal happens before a session or a tool is built."""
    built: list[object] = []
    monkeypatch.setattr(cli, "build_invoke_workflow_tool", lambda *a: built.append(a))

    assert cli._cmd_invoke_workflow(_invoke_args(task=None)) == 2
    assert built == []
    assert "provide a task" in capsys.readouterr().err


def test_the_retired_manual_route_points_at_the_single_entry_point() -> None:
    """The legacy parser stays for its call sites but tells the operator where to go."""
    parser = cli.build_parser()
    actions = [action for action in parser._actions if getattr(action, "choices", None) is not None]
    subparsers = next(action for action in actions if "invoke-workflow" in action.choices)
    workflow_help = subparsers.choices["workflow"].description

    assert "invoke-workflow" in workflow_help
    assert "DEPRECATED" in workflow_help


def test_invoke_workflow_cli_returns_the_child_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """An ok tool result still carries the child's own exit code; the operator sees it."""
    recorder = _Recorder()
    recorder.result = ToolResult.ok("child finished", result={"exit_code": 3, "status": "DONE"})
    monkeypatch.setattr(cli, "build_invoke_workflow_tool", recorder.build)
    monkeypatch.setattr(cli, "_resolve_workflow_lifecycle", lambda args, run_id: (run_id, None, None, None))
    monkeypatch.setattr(cli, "load_runtime_limits_from_path", lambda: SimpleNamespace(limits=RuntimeLimits()))

    assert cli._cmd_invoke_workflow(_invoke_args()) == 3
