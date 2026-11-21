"""C0 oracles for the typed plan semantics and the one V2 renderer (D-V2-7).

The two laws this module exists for are tested as laws, not spot checks:

* ``parse_plan(render_*) == the graph the payload described`` over a seeded corpus, so a
  renderer that is right for one example and wrong for the next cannot hide;
* ``render_increment(from_graph(parse_plan(pair))) == increment`` byte-for-byte, so a seal
  digest over rendered bytes survives a re-render.

The rest are the refusal contracts: a payload that cannot be rendered is told which field
is wrong, and the renderer cannot emit bytes admission would reject for a rule the payload
was never told about.
"""

from __future__ import annotations

import random

import pytest

from fa.inner_loop.plan_semantics import (
    PlanSemantics,
    Question,
    SemanticsContract,
    SemanticsError,
    SemanticsSlice,
    SemanticsStep,
    from_graph,
    parse_semantics,
    render_increment,
    render_open_questions,
    render_project,
    render_roadmap,
)
from fa.inner_loop.plan_v2 import PlanGraph, PlanV2Error, parse_plan

_QUESTIONS = (
    Question(
        number="001",
        question="Which host proves the readiness claim?",
        blocks="INV-2, SLICE1",
        status="OPEN",
        decision="Awaiting the W4 run sheet.",
        updated="2026-11-20",
    ),
    Question(
        number="002",
        question="Is the widget id part of the public surface?",
        blocks="RISK",
        status="RESOLVED",
        decision="Yes; see the schema note.",
        updated="2026-11-20",
    ),
)


def _slice() -> SemanticsSlice:
    return SemanticsSlice(
        number="1",
        name="Parse the widget id",
        steps_mode="prescriptive",
        contracts=(
            SemanticsContract(number="1", cls="FUNCTIONAL", inv="INV-1", text="a widget id parses"),
            SemanticsContract(number="2", cls="CONSTRAINT", inv="INV-2", text="readiness is proven on the host"),
            SemanticsContract(number="3", cls="PRESERVATION", inv="INV-1", text="known ids keep their route"),
        ),
        acceptance=(
            ("TEST-1.1", "CT-1.1", "acceptance/tests/test_widget.py::test_parse"),
            ("TEST-1.2", "CT-1.3", "acceptance/tests/test_widget.py::test_known_route"),
        ),
        kill_targets=(("src/widget.py::parse", "CT-1.1", "TEST-1.1"),),
        exit_checks=(("CHECK-1", "STEP1", ("TEST-1.1",)),),
        steps=(SemanticsStep(number="1", text="write the failing test", check="CHECK-1"),),
    )


def _semantics() -> PlanSemantics:
    from fa.inner_loop.plan_v2 import Invariant

    return PlanSemantics(
        intent="Ship the widget slice.",
        out_of_scope="Everything outside SLICE1.",
        questions=_QUESTIONS,
        invariants=(
            Invariant(id="INV-1", kind="HARD", text="a widget id parses", evidence="TEST_REQUIRED"),
            Invariant(
                id="INV-2",
                kind="HARD",
                text="readiness is proven on the host",
                evidence="NON_EXECUTABLE",
                reason="HOST_READINESS",
            ),
        ),
        scenarios=(("SCN-1", "widget entry", "a known id", "the old route", ("CT-1.3",)),),
        slices=(_slice(),),
    )


def _pair(semantics: PlanSemantics, *, project_slug: str = "demo-project") -> dict[str, str]:
    return render_project(semantics, project_slug=project_slug)


def _graph(semantics: PlanSemantics, *, project_slug: str = "demo-project") -> PlanGraph:
    files = _pair(semantics, project_slug=project_slug)
    return parse_plan(
        roadmap=files["roadmap.md"],
        increment=files["increments/increment-01-initial-plan.md"],
    )


# --- the two laws -------------------------------------------------------------


def test_rendering_then_parsing_is_the_graph_the_payload_described() -> None:
    """CT-2.3 renderer law: the graph is the payload, field for field."""
    semantics = _semantics()
    graph = _graph(semantics)

    assert graph.invariants == semantics.invariants
    assert [(item.id, item.ct_ids) for item in graph.scenarios] == [("SCN-1", ("CT-1.3",))]
    rendered_slice = graph.slices[0]
    assert (rendered_slice.number, rendered_slice.name, rendered_slice.steps_mode) == (
        "1",
        "Parse the widget id",
        "prescriptive",
    )
    assert [contract.id for contract in rendered_slice.contracts] == ["CT-1.1", "CT-1.2", "CT-1.3"]
    assert [contract.cls for contract in rendered_slice.contracts] == ["FUNCTIONAL", "CONSTRAINT", "PRESERVATION"]
    # Selectors are expanded from the payload's project-relative form, once.
    assert [entry.selector for entry in rendered_slice.acceptance] == [
        "worklogs/demo-project/acceptance/tests/test_widget.py::test_parse",
        "worklogs/demo-project/acceptance/tests/test_widget.py::test_known_route",
    ]
    assert [(step.number, step.text, step.check_id) for step in rendered_slice.steps] == [
        ("1", "write the failing test", "CHECK-1")
    ]


def test_rendering_the_parsed_graph_reproduces_the_same_bytes() -> None:
    """Byte idempotence: what the seal digests survives a re-render."""
    semantics = _semantics()
    files = _pair(semantics)
    increment = files["increments/increment-01-initial-plan.md"]
    graph = parse_plan(roadmap=files["roadmap.md"], increment=increment)

    again = from_graph(graph, project_slug="demo-project")
    assert render_increment(again, project_slug="demo-project") == increment


def test_the_round_trip_holds_over_a_seeded_corpus() -> None:
    """The law, not one example: 60 seeded variants, each rendered and re-derived."""
    rng = random.Random(20261120)
    for index in range(60):
        slices: list[SemanticsSlice] = []
        for number in range(1, rng.randint(1, 3) + 1):
            contracts = tuple(
                SemanticsContract(
                    number=str(row),
                    cls=rng.choice(["FUNCTIONAL", "CONSTRAINT", "PRESERVATION"]),
                    inv="INV-1",
                    text=f"contract {index}-{number}-{row} holds",
                )
                for row in range(1, rng.randint(1, 2) + 1)
            )
            # Every contract gets its own row: an uncovered claim is a *grammar* refusal,
            # so a payload missing one would test the matrix rather than the renderer.
            acceptance = tuple(
                (
                    f"TEST-{number}.{contract.number}",
                    f"CT-{number}.{contract.number}",
                    f"acceptance/tests/test_case_{index}_{number}.py::test_{contract.number}",
                )
                for contract in contracts
            )
            first_test = acceptance[0][0]
            slices.append(
                SemanticsSlice(
                    number=str(number),
                    name=f"slice {number} of case {index}",
                    steps_mode=rng.choice(["prescriptive", "outcome"]),
                    contracts=contracts,
                    acceptance=acceptance,
                    kill_targets=((f"src/case_{index}.py::fn_{number}", acceptance[0][1], first_test),),
                    exit_checks=((f"CHECK-{number}", f"STEP{number}", (first_test,)),),
                    steps=(SemanticsStep(number=str(number), text="act", check=f"CHECK-{number}"),),
                )
            )
        from fa.inner_loop.plan_v2 import Invariant

        semantics = PlanSemantics(
            intent=f"case {index}",
            out_of_scope="nothing",
            invariants=(Invariant(id="INV-1", kind="HARD", text="a", evidence="TEST_REQUIRED"),),
            slices=tuple(slices),
        )
        files = _pair(semantics, project_slug="demo")
        graph = parse_plan(roadmap=files["roadmap.md"], increment=files["increments/increment-01-initial-plan.md"])
        assert [planned.number for planned in graph.slices] == [planned.number for planned in semantics.slices]
        assert (
            render_increment(from_graph(graph, project_slug="demo"), project_slug="demo")
            == files["increments/increment-01-initial-plan.md"]
        )


# --- payload refusals ---------------------------------------------------------


def _payload(**overrides: object) -> dict[str, object]:
    """A minimal admissible payload as a plain mapping, so refusals are driven from the wire."""
    from fa.inner_loop.plan_v2 import Invariant

    base: dict[str, object] = {
        "intent": "Ship it.",
        "out_of_scope": "Everything else.",
        "questions": [],
        "invariants": [{"number": "1", "kind": "HARD", "text": "a", "evidence": "TEST_REQUIRED", "reason": None}],
        "scenarios": [],
        "slices": [
            {
                "number": "1",
                "name": "Do",
                "steps_mode": "prescriptive",
                "contracts": [{"number": "1", "cls": "FUNCTIONAL", "inv": "INV-1", "text": "a"}],
                "acceptance": [
                    {"test_id": "TEST-1.1", "ct": "CT-1.1", "selector": "acceptance/tests/test_a.py::test_a"}
                ],
                "kill_targets": [],
                "exit_checks": [{"check": "CHECK-1", "step": "STEP1", "test_ids": ["TEST-1.1"]}],
                "steps": [{"number": "1", "text": "act", "check": "CHECK-1"}],
            }
        ],
    }
    del Invariant
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("payload", "rule"),
    [
        (_payload(intent=""), "intent-invalid"),
        (_payload(intent="  padded"), "intent-invalid"),
        (_payload(out_of_scope=""), "out-of-scope-invalid"),
        (_payload(intent="line\rbreak"), "intent-invalid"),
        (_payload(extra=True), "payload-invalid"),
        ({key: value for key, value in _payload().items() if key != "slices"}, "payload-invalid"),
    ],
)
def test_payload_prose_and_keys_are_refused_by_name(payload: dict[str, object], rule: str) -> None:
    with pytest.raises(SemanticsError) as refused:
        parse_semantics(payload)
    assert refused.value.rule == rule


def test_a_pipe_in_a_field_is_refused_because_every_row_is_pipe_separated() -> None:
    payload = _payload()
    payload["slices"] = [dict(payload["slices"][0], name="a | b")]  # type: ignore[index]
    with pytest.raises(SemanticsError) as refused:
        parse_semantics(payload)
    assert refused.value.rule == "slice-name-invalid"


def test_an_invariant_reason_on_test_required_is_refused_where_the_grammar_refuses_it() -> None:
    payload = _payload()
    payload["invariants"] = [
        {"number": "1", "kind": "HARD", "text": "a", "evidence": "TEST_REQUIRED", "reason": "HOST_READINESS"}
    ]
    with pytest.raises(SemanticsError) as refused:
        parse_semantics(payload)
    assert refused.value.rule == "invariant-reason-invalid"


def test_a_non_executable_invariant_without_a_ratified_reason_is_refused() -> None:
    payload = _payload()
    payload["invariants"] = [
        {"number": "1", "kind": "HARD", "text": "a", "evidence": "NON_EXECUTABLE", "reason": "BECAUSE"}
    ]
    with pytest.raises(SemanticsError) as refused:
        parse_semantics(payload)
    assert refused.value.rule == "invariant-reason-invalid"


def test_the_payload_is_judged_by_the_grammar_not_by_a_second_copy_of_its_rules() -> None:
    """A payload that renders an inadmissible pair is refused with the *grammar's* code."""
    payload = _payload()
    payload["slices"] = [
        dict(
            payload["slices"][0],  # type: ignore[index]
            contracts=[{"number": "1", "cls": "PRESERVATION", "inv": "INV-1", "text": "still works"}],
            acceptance=[],
            exit_checks=[],
            steps=[],
        )
    ]
    with pytest.raises(SemanticsError) as refused:
        parse_semantics(payload)
    assert refused.value.rule == "preservation-without-executable-evidence"


def test_duplicate_question_ids_are_refused() -> None:
    payload = _payload()
    record = {
        "number": "1",
        "question": "q",
        "blocks": "RISK",
        "status": "OPEN",
        "decision": "d",
        "updated": "2026-11-20",
    }
    payload["questions"] = [record, dict(record)]
    with pytest.raises(SemanticsError) as refused:
        parse_semantics(payload)
    assert refused.value.rule == "duplicate-question-id"


# --- renderer refusal contracts ----------------------------------------------


def test_a_selector_that_pre_empts_the_project_slug_is_refused() -> None:
    """The payload may not carry the slug: it is caller authority and can be substituted."""
    planned = _slice()
    broken = SemanticsSlice(
        number=planned.number,
        name=planned.name,
        steps_mode=planned.steps_mode,
        contracts=planned.contracts,
        acceptance=(("TEST-1.1", "CT-1.1", "worklogs/demo-project/acceptance/tests/test_widget.py::test_parse"),),
        kill_targets=planned.kill_targets,
        exit_checks=planned.exit_checks,
        steps=planned.steps,
    )
    with pytest.raises(SemanticsError) as refused:
        render_increment(_semantics_with(broken), project_slug="demo-project")
    assert refused.value.rule == "acceptance-selector-invalid"


def _semantics_with(planned: SemanticsSlice) -> PlanSemantics:
    base = _semantics()
    return PlanSemantics(
        intent=base.intent,
        out_of_scope=base.out_of_scope,
        questions=base.questions,
        invariants=base.invariants,
        scenarios=base.scenarios,
        slices=(planned,),
    )


def test_prose_that_would_open_a_section_is_refused() -> None:
    base = _semantics()
    with pytest.raises(SemanticsError) as refused:
        render_roadmap(PlanSemantics(intent="## Intent\n\nsneaky", out_of_scope=base.out_of_scope))
    assert refused.value.rule == "prose-heading"


def test_an_invalid_project_slug_is_refused_before_any_byte_is_rendered() -> None:
    with pytest.raises(SemanticsError) as refused:
        render_increment(_semantics(), project_slug="../escape")
    assert refused.value.rule == "project-slug-invalid"


def test_a_selector_from_another_project_cannot_be_inverted() -> None:
    graph = _graph(_semantics())
    with pytest.raises(SemanticsError) as refused:
        from_graph(graph, project_slug="other-project")
    assert refused.value.rule == "selector-outside-project"


# --- rendered documents -------------------------------------------------------


def test_a_selector_that_climbs_out_of_its_project_is_refused_by_the_grammar() -> None:
    """The plan forbids ``..``; the character class admits ``.`` and ``/``, so it was not enforced."""
    payload = _payload()
    payload["slices"] = [
        dict(
            payload["slices"][0],  # type: ignore[index]
            acceptance=[
                {
                    "test_id": "TEST-1.1",
                    "ct": "CT-1.1",
                    "selector": "acceptance/tests/../../../etc/test_a.py::test_a",
                }
            ],
        )
    ]
    with pytest.raises(SemanticsError) as refused:
        parse_semantics(payload)
    assert refused.value.rule == "acceptance-selector-invalid"


def test_a_second_steps_header_is_refused_where_the_parser_refuses_it() -> None:
    """A renderer that emits a step-list heading produces bytes admission rejects."""
    semantics = _semantics()
    increment = render_increment(semantics, project_slug="demo-project")
    broken = increment.replace("STEP-EXIT-CHECKS:", "STEPS:\nSTEP-EXIT-CHECKS:")

    with pytest.raises(PlanV2Error) as refused:
        parse_plan(roadmap=render_roadmap(semantics), increment=broken)
    assert refused.value.rule == "slice-1-steps-mode"


def test_the_roadmap_round_trips_through_parse_even_though_the_graph_does_not_model_it() -> None:
    """The roadmap half has no byte-idempotence law; it still has to admit."""
    semantics = _semantics()
    files = _pair(semantics)

    graph = parse_plan(roadmap=files["roadmap.md"], increment=files["increments/increment-01-initial-plan.md"])
    # The graph carries no prose, so from_graph needs it supplied; empty prose must still admit,
    # which is what proves the roadmap's sections are prose and not parsed structure.
    re_rendered = render_roadmap(from_graph(graph, project_slug="demo-project"))
    assert (
        parse_plan(roadmap=re_rendered, increment=files["increments/increment-01-initial-plan.md"]).invariants
        == graph.invariants
    )


def test_the_rendered_roadmap_carries_the_marker_and_exactly_two_prose_sections() -> None:
    roadmap = render_roadmap(_semantics())

    assert roadmap.startswith("Plan-Format: AI-NATIVE-PLAN-V2\n")
    headings = [line for line in roadmap.splitlines() if line.startswith("## ")]
    assert headings == ["## Intent", "## Out of scope"]
    # The authority owns "# Roadmap — <slug>"; a second title here would be a second owner.
    assert not any(line.startswith("# ") for line in roadmap.splitlines())


def test_open_questions_renders_one_row_per_record_with_the_six_fixed_fields() -> None:
    rendered = render_open_questions(_semantics())
    rows = [line for line in rendered.splitlines() if line.startswith("| Q-") and not line.startswith("| Q-ID")]

    cells = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]
    assert cells == [
        [
            "Q-001",
            "Which host proves the readiness claim?",
            "INV-2, SLICE1",
            "OPEN",
            "Awaiting the W4 run sheet.",
            "2026-11-20",
        ],
        [
            "Q-002",
            "Is the widget id part of the public surface?",
            "RISK",
            "RESOLVED",
            "Yes; see the schema note.",
            "2026-11-20",
        ],
    ]


def test_render_project_returns_the_three_documents_the_authority_wraps() -> None:
    files = _pair(_semantics())

    assert set(files) == {"roadmap.md", "increments/increment-01-initial-plan.md", "open-questions.md"}


def test_a_rendered_pair_admits_the_documents_on_disk_path() -> None:
    """The increment the renderer emits is the exact shape admission reads back."""
    files = _pair(_semantics(), project_slug="demo-project")
    increment = files["increments/increment-01-initial-plan.md"]

    assert parse_plan(roadmap=files["roadmap.md"], increment=increment).invariants[0].evidence == "TEST_REQUIRED"
    # A bare `STEPS:` header would be read as a second mode line; the renderer never emits one.
    assert increment.count("\nSTEPS:") == 1


def test_an_empty_optional_section_does_not_break_the_pair() -> None:
    from fa.inner_loop.plan_v2 import Invariant

    semantics = PlanSemantics(
        intent="Ship it.",
        out_of_scope="Nothing else.",
        invariants=(Invariant(id="INV-1", kind="HARD", text="a", evidence="TEST_REQUIRED"),),
        slices=(
            SemanticsSlice(
                number="1",
                name="Do",
                steps_mode="outcome",
                contracts=(SemanticsContract(number="1", cls="FUNCTIONAL", inv="INV-1", text="a"),),
                acceptance=(("TEST-1.1", "CT-1.1", "acceptance/tests/test_a.py::test_a"),),
                exit_checks=(("CHECK-1", "STEP1", ("TEST-1.1",)),),
                steps=(SemanticsStep(number="1", text="act", check="CHECK-1"),),
            ),
        ),
    )
    graph = _graph(semantics, project_slug="demo")

    assert graph.scenarios == () and graph.slices[0].kill_targets == ()
