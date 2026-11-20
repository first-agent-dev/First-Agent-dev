"""C0 oracles for the AI-NATIVE-PLAN-V2 grammar and admission rules (STEP9A)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from fa.inner_loop.plan_v2 import (
    DISPOSITION_REASONS,
    MAX_DISPOSITIONS,
    PlanGraph,
    PlanV2Error,
    parse_plan,
    resolve_selectors,
)

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
