"""C0 oracles for the AI-NATIVE-PLAN-V2 grammar and admission rules (STEP9A)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
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
    bind_dispositions,
    parse_dispositions,
    snapshot_from_bytes,
)
from fa.inner_loop.plan_v2 import (
    DISPOSITION_REASONS,
    MAX_DISPOSITIONS,
    EvidenceMode,
    PlanGraph,
    PlanV2Error,
    attested_contracts,
    contract_evidence,
    is_contract_id,
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
    assert graph.invariants[1].owner is None  # granted at admission, never parsed (R1)
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
            "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: NON_EXECUTABLE\nDISPOSITION-REASON: BECAUSE\n",
            "disposition-reason-unratified",
        ),
        (
            "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: NON_EXECUTABLE\n"
            "DISPOSITION-REASON: HOST_READINESS\nDISPOSITION-OWNER: W4\n",
            "disposition-not-caller-authority",
        ),
        (
            "### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: NON_EXECUTABLE\n"
            "DISPOSITION-REASON: HOST_READINESS\nDISPOSITION-EVIDENCE: doc:x@sha256:" + "0" * 64 + "\n",
            "disposition-not-caller-authority",
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
            "DISPOSITION-REASON: HOST_READINESS\n"
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


def test_a_hard_contract_with_a_requested_disposition_is_admitted_unbound() -> None:
    """The grammar checks the *request*; only admission can grant it (R1)."""
    invariants = (
        _INVARIANT_1.replace("EVIDENCE: TEST_REQUIRED", "EVIDENCE: NON_EXECUTABLE")
        + "DISPOSITION-REASON: OWNER_APPROVAL\n\n"
        + _INVARIANT_2
    )

    graph = parse_plan(roadmap=_ROADMAP, increment=_increment(invariants=invariants, slice_body=_MINIMAL_SLICE))
    assert graph.invariants[0].evidence == "NON_EXECUTABLE"
    assert graph.invariants[0].reason == "OWNER_APPROVAL"
    assert graph.invariants[0].owner is None  # nobody has granted anything yet
    assert graph.invariants[0].evidence_ref is None


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


#: A grant for every reason the fixtures use, reviewed inside its 30-day life.
_GRANTS = parse_dispositions(
    [
        {
            "reason": reason,
            "owner": "W4",
            "evidence": "review:r1",
            "reviewed_at": "2026-11-19",
        }
        for reason in sorted(DISPOSITION_REASONS)
    ]
)


def granted_graph(*, invariants: str = "", scenario: str = "", slice_body: str = "") -> PlanGraph:
    """The graph as the run actually sees it: requests bound to the caller's grants.

    ``ATTESTED`` is a claim somebody authorised, so it is graded only after
    ``bind_dispositions`` has copied the caller's owner onto the invariant (R2 over
    R1, E585). A bare parse is the *request* half and reports ``UNCOVERED``.
    """
    return bind_dispositions(
        plan_graph(invariants=invariants, scenario=scenario, slice_body=slice_body),
        _GRANTS,
        today=date(2026, 11, 20),
    )


def test_a_disposition_request_without_a_grant_is_never_attested() -> None:
    """The defect P1-1 named: a request is not an authorisation.

    ``parse_plan`` alone produces ``NON_EXECUTABLE`` with a reason but no owner,
    because R1 made the owner the caller's. Grading that as ``ATTESTED`` would put
    a verdict in the seal that nobody granted, so the bare graph must report the
    contract as uncovered and only the bound graph may attest it.
    """
    bare = plan_graph()
    assert contract_evidence(bare)["CT-1.2"] is EvidenceMode.UNCOVERED
    assert attested_contracts(bare) == ()

    bound = granted_graph()
    assert contract_evidence(bound)["CT-1.2"] is EvidenceMode.ATTESTED
    assert attested_contracts(bound) == ("CT-1.2",)



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


# --- R2: evidence grades a contract by what the plan affords -----------------

_SOFT_INVARIANT_2 = """### INV-2
KIND: SOFT
TEXT: Host readiness is proven on the approved host.
EVIDENCE: TEST_REQUIRED
"""

_DISPOSED_INVARIANT_1 = """### INV-1
KIND: HARD
TEXT: The writer never publishes without a sealed acceptance revision.
EVIDENCE: NON_EXECUTABLE
DISPOSITION-REASON: HOST_READINESS
"""

#: Two *separate* granted invariants: R3 forbids one grant from backing a cluster.
_TWO_DISPOSED_INVARIANTS = (
    _INVARIANT_1
    + "\n"
    + _INVARIANT_2
    + "\n### INV-3\nKIND: HARD\nTEXT: Deployment identity is proven by the release record.\n"
    + "EVIDENCE: NON_EXECUTABLE\nDISPOSITION-REASON: DEPLOYMENT_IDENTITY\n"
)

_TWO_DISPOSED_CONTRACTS = _SLICE.replace(
    "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host",
    "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host\n"
    "  CT-1.3 [CONSTRAINT] INV: INV-3: readiness is proven on the host",
)


def test_a_selector_grades_executable_and_a_granted_disposition_grades_attested() -> None:
    """The default plan tests CT-1.1 and only *disposes* of CT-1.2 (INV-2)."""
    graph = granted_graph()

    assert contract_evidence(graph) == {
        "CT-1.1": EvidenceMode.EXECUTABLE,
        "CT-1.2": EvidenceMode.ATTESTED,
    }
    assert attested_contracts(graph) == ("CT-1.2",)


def test_several_granted_invariants_are_all_attested_sorted() -> None:
    graph = granted_graph(invariants=_TWO_DISPOSED_INVARIANTS, slice_body=_TWO_DISPOSED_CONTRACTS)

    assert attested_contracts(graph) == ("CT-1.2", "CT-1.3")


def test_attestation_is_sorted_not_declaration_ordered() -> None:
    """Declaration order is the planner's; the seal's list is canonical."""
    declared_out_of_order = _SLICE.replace(
        "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host",
        "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host\n"
        "  CT-1.10 [CONSTRAINT] INV: INV-3: readiness is proven on the host",
    )

    graph = granted_graph(invariants=_TWO_DISPOSED_INVARIANTS, slice_body=declared_out_of_order)
    assert attested_contracts(graph) == ("CT-1.10", "CT-1.2")


def test_a_contract_with_neither_a_selector_nor_a_disposition_is_uncovered() -> None:
    """A soft invariant needs no executable evidence, so the gap is legal — and visible."""
    graph = plan_graph(invariants=_INVARIANT_1 + "\n" + _SOFT_INVARIANT_2)

    assert contract_evidence(graph)["CT-1.2"] is EvidenceMode.UNCOVERED
    assert attested_contracts(graph) == ()


def test_a_selector_outranks_a_disposition_on_its_own_invariant() -> None:
    """A disposition never weakens evidence that exists: the run still executes it."""
    graph = plan_graph(invariants=_DISPOSED_INVARIANT_1 + "\n" + _SOFT_INVARIANT_2)

    assert contract_evidence(graph)["CT-1.1"] is EvidenceMode.EXECUTABLE
    assert "CT-1.1" not in attested_contracts(graph)


@pytest.mark.parametrize("value", ["CT-1.1", "CT-12.3b", "CT-1b.2a"])
def test_the_contract_id_grammar_accepts_what_the_parser_accepts(value: str) -> None:
    assert is_contract_id(value)


@pytest.mark.parametrize("value", ["CT-1", "ct-1.1", "CT-1.1 ", "CT-1.1.2", "CT-", "", "TEST-1.1", 1, None])
def test_the_contract_id_grammar_refuses_everything_else(value: object) -> None:
    assert not is_contract_id(value)


# --- R3: the policy matrix (contract class x invariant kind) -----------------

_PRESERVING_SLICE = _SLICE.replace(
    "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host",
    "  CT-1.2 [PRESERVATION] INV: INV-2: the published shape does not change",
)

_CLUSTERED_SLICE = _SLICE.replace(
    "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host",
    "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host\n"
    "  CT-1.3 [CONSTRAINT] INV: INV-2: readiness is proven on the host",
)


@pytest.mark.parametrize("kind", ["HARD", "SOFT"])
def test_a_preservation_claim_always_needs_a_test(kind: str) -> None:
    """No disposition may carry "what worked still works": that is how regressions ship green."""
    invariants = _INVARIANT_1 + "\n" + _INVARIANT_2.replace("KIND: HARD", f"KIND: {kind}")

    assert _rule(lambda: plan_graph(invariants=invariants, slice_body=_PRESERVING_SLICE)) == (
        "preservation-without-executable-evidence"
    )


@pytest.mark.parametrize(
    ("kind", "evidence"),
    [("HARD", "TEST_REQUIRED"), ("SOFT", "TEST_REQUIRED"), ("HARD", "NON_EXECUTABLE"), ("SOFT", "NON_EXECUTABLE")],
)
def test_a_preservation_claim_is_refused_whatever_the_invariant_says(kind: str, evidence: str) -> None:
    """The class rule is independent of the invariant: no mode makes it attestable."""
    invariant = _INVARIANT_2.replace("KIND: HARD", f"KIND: {kind}").replace(
        "EVIDENCE: NON_EXECUTABLE", f"EVIDENCE: {evidence}"
    )
    if evidence == "TEST_REQUIRED":
        invariant = invariant.replace("DISPOSITION-REASON: HOST_READINESS\n", "")
    invariants = _INVARIANT_1 + "\n" + invariant

    assert _rule(lambda: plan_graph(invariants=invariants, slice_body=_PRESERVING_SLICE)) == (
        "preservation-without-executable-evidence"
    )


def test_a_preservation_claim_with_a_test_is_admitted() -> None:
    """The rule is about the *evidence*, not the class: a tested one is fine."""
    tested = _PRESERVING_SLICE.replace(
        "KILL-TARGETS:",
        "  TEST-ID: TEST-1.2 | CT: CT-1.2 | SELECTOR: "
        "worklogs/demo/acceptance/tests/test_publish.py::test_publish2\nKILL-TARGETS:",
    )

    graph = plan_graph(slice_body=tested)

    assert contract_evidence(graph)["CT-1.2"] is EvidenceMode.EXECUTABLE
    assert "CT-1.2" not in attested_contracts(graph)


def test_one_grant_may_not_back_a_cluster_of_contracts() -> None:
    assert _rule(lambda: plan_graph(slice_body=_CLUSTERED_SLICE)) == "disposition-covers-several-contracts"


def test_a_tested_contract_does_not_count_against_the_cluster_bound() -> None:
    """The bound counts claims *leaning* on the grant, not everything it mentions."""
    mixed = _CLUSTERED_SLICE.replace(
        "KILL-TARGETS:",
        "  TEST-ID: TEST-1.3 | CT: CT-1.3 | SELECTOR: "
        "worklogs/demo/acceptance/tests/test_publish.py::test_publish3\nKILL-TARGETS:",
    )

    graph = granted_graph(slice_body=mixed)

    assert attested_contracts(graph) == ("CT-1.2",)  # CT-1.3 is executable, so it is not attested


def test_a_soft_invariant_may_still_stay_uncovered() -> None:
    """The matrix tightens PRESERVATION and clusters; it does not make SOFT executable."""
    graph = plan_graph(invariants=_INVARIANT_1 + "\n" + _SOFT_INVARIANT_2)

    assert contract_evidence(graph)["CT-1.2"] is EvidenceMode.UNCOVERED


# --- P1-1 second half: the grant must survive the read-back (E585) ----------


def _snapshot(increment: str) -> PlanSnapshot:
    return snapshot_from_bytes(
        "worklogs/demo/increments/increment-01-demo.md",
        increment.encode("utf-8"),
        source_kind="BOOTSTRAP",
        format=PLAN_V2,
        roadmap=ROADMAP_DOCUMENT,
    )


def test_the_authorised_graph_reaches_the_seal_when_the_installed_plan_is_the_same() -> None:
    """Without this the seal grades requests: the grant would be checked and dropped.

    The authority wraps the plan in its own front matter, so the read-back is a
    different document with the same plan. The run's granted graph must therefore be
    reconciled by *graph*, not by byte digest, or a legitimately granted contract is
    sealed as uncovered and the operator's decision is lost.
    """
    increment = plan_document()
    authorised = granted_graph()
    installed = _snapshot(increment)

    admitted = workflow_controller._authorised_graph(installed, authorised)

    assert admitted is not None
    assert attested_contracts(admitted) == ("CT-1.2",)
    assert {item.id: item for item in admitted.invariants}["INV-2"].owner == "W4"


def test_a_bare_read_back_is_not_attested_without_a_carried_grant() -> None:
    """No grant was made, so nothing may be attested however often it is parsed."""
    installed = _snapshot(plan_document())

    assert workflow_controller._authorised_graph(installed, None) is None
    assert attested_contracts(installed.graph) == ()  # a request is not an authorisation


def test_a_grant_is_never_repointed_at_a_plan_it_did_not_authorise() -> None:
    """The install could in principle return other bytes; the grant must not follow.

    ``_authorised_graph`` is the one place a pre-install authorisation is carried
    across an irreversible step, so it refuses on any graph difference rather than
    "mostly matching": the read-back must describe exactly the plan that was bound.
    """
    authorised = granted_graph()
    drifted = _snapshot(plan_document(slice_body=_SLICE.replace("publish", "publish_v2")))

    assert workflow_controller._authorised_graph(drifted, authorised) is None


def test_a_refused_read_back_carries_no_grant() -> None:
    """A malformed installed plan has no graph, so there is nothing to authorise."""
    authorised = granted_graph()
    broken = snapshot_from_bytes(
        "worklogs/demo/increments/increment-01-demo.md",
        plan_document().replace("## SLICE1:", "## PHASE1:").encode("utf-8"),
        source_kind="BOOTSTRAP",
        format=PLAN_V2,
        roadmap=ROADMAP_DOCUMENT,
    )

    assert broken.graph is None
    assert workflow_controller._authorised_graph(broken, authorised) is None


# --- P1-2: one grant, one claim (E585) -------------------------------------


_REUSED_REASON_INVARIANTS = """### INV-1
KIND: HARD
TEXT: Host readiness is proven on the approved host.
EVIDENCE: NON_EXECUTABLE
DISPOSITION-REASON: HOST_READINESS

### INV-2
KIND: HARD
TEXT: The operator signed off the dashboard copy.
EVIDENCE: NON_EXECUTABLE
DISPOSITION-REASON: HOST_READINESS
"""

_TWO_CLAIMS = """## SLICE1: two claims, one waiver
STEPS: prescriptive
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: readiness is proven on the host
  CT-1.2 [FUNCTIONAL] INV: INV-2: the copy was signed off
"""


def test_one_grant_may_not_authorise_two_different_invariants() -> None:
    """The grant is keyed by reason, so a reused reason turns one decision into two.

    A caller declaring ``HOST_READINESS`` decided that *host readiness* is out of
    scope for a test. If two invariants name that reason, both are authorised by that
    one declaration and the seal attests a claim the caller never named -- the R3
    property (one decision, one claim) reached through the other door, because R3
    bounds contracts per invariant while the grant travels by reason.
    """
    assert (
        _rule(lambda: plan_graph(invariants=_REUSED_REASON_INVARIANTS, slice_body=_TWO_CLAIMS))
        == "disposition-reason-reused"
    )


def test_distinct_reasons_on_distinct_invariants_are_admitted_and_both_attested() -> None:
    """The rule is about reuse, not about having several dispositions."""
    distinct = _REUSED_REASON_INVARIANTS.replace(
        "TEXT: The operator signed off the dashboard copy.\n"
        "EVIDENCE: NON_EXECUTABLE\n"
        "DISPOSITION-REASON: HOST_READINESS",
        "TEXT: The operator signed off the dashboard copy.\n"
        "EVIDENCE: NON_EXECUTABLE\n"
        "DISPOSITION-REASON: OWNER_APPROVAL",
    )

    graph = granted_graph(invariants=distinct, slice_body=_TWO_CLAIMS)

    assert attested_contracts(graph) == ("CT-1.1", "CT-1.2")


def test_the_reuse_refusal_is_not_the_cluster_refusal_scaled_up() -> None:
    """Two *invariants* is a different defect from two *contracts* on one invariant.

    The cluster rule bounds how many claims lean on one invariant; the reuse rule
    bounds how many invariants spend one reason. Keeping them apart is what lets an
    operator read the refusal and know which mistake the plan made.
    """
    clustered = _SLICE.replace(
        "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host",
        "  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host\n"
        "  CT-1.3 [CONSTRAINT] INV: INV-2: readiness is proven on the host",
    )
    assert _rule(lambda: plan_graph(slice_body=clustered)) == "disposition-covers-several-contracts"
    assert (
        _rule(lambda: plan_graph(invariants=_REUSED_REASON_INVARIANTS, slice_body=_TWO_CLAIMS))
        == "disposition-reason-reused"
    )
