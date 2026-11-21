"""Typed plan semantics and the one renderer for ``AI-NATIVE-PLAN-V2`` (D-V2-7).

The planner produces *semantics*, never Markdown: intent, out-of-scope prose, question
records, invariants, optional scenarios, and per-slice contracts, acceptance rows, kill
targets, exit checks and steps. This module is the only place those values become plan
bytes, so every fixed decision the grammar demands (section order, the single ``STEPS:``
mode line, the ``EXIT-CHECK:`` suffix, the selector prefix) is made once, here, instead
of in a prompt and in a parser that then disagree.

Two properties make the split safe, and both are tested as laws rather than spot checks:

* **Round trip.** For admissible semantics ``s`` and a valid slug,
  ``parse_plan(roadmap=render_roadmap(s), increment=render_increment(s, slug))`` equals the
  graph ``s`` describes.
* **Byte idempotence of the increment.** ``render_increment(from_graph(parse_plan(pair)))``
  reproduces the increment byte-for-byte. A seal digest over rendered bytes therefore
  survives a re-render, which is what makes "the seal names these bytes" meaningful.
  The roadmap is deliberately outside this law: it carries two prose sections the graph
  does not model, so it is only guaranteed to round-trip through ``parse_plan``.

**There is no second grammar.** ``parse_semantics`` checks only what a Python value can get
wrong on its own — types, closed key sets, empty or whitespace-padded fields, separators
that would be read as structure. Whether the *documents* are legal is decided by
``plan_v2.parse_plan`` on the output of this renderer, called from ``parse_semantics`` with a
probe slug and again from ``render_project`` with the real one. One vocabulary, one set of
refusal codes, and no chance for the renderer to emit something admission would reject for
a reason the payload was never told about.

**Selectors are project-relative in the payload** (``acceptance/tests/<path>.py::<node>``).
The project slug is caller authority and is applied at install time
(``_resolve_bootstrap_identity``), so a payload that embedded the slug would either carry a
model claim or break when the route names the project. The prefix is formed here and
nowhere else.

Front matter is *not* rendered here: the authority owns every metadata line
(``fa.execution.publication``), and ``ledger.md`` is a fixed harness body rather than a
semantic document. This module renders the documents the semantics own.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from fa.execution.protocol import CONFIG_ID
from fa.inner_loop.plan_v2 import (
    CONTRACT_CLASSES,
    DISPOSITION_REASONS,
    PLAN_FORMAT,
    Invariant,
    PlanGraph,
    PlanV2Error,
    SlicePlan,
    parse_plan,
)

__all__ = [
    "QUESTION_BLOCKS",
    "QUESTION_STATUSES",
    "PlanSemantics",
    "Question",
    "SemanticsContract",
    "SemanticsError",
    "SemanticsSlice",
    "SemanticsStep",
    "from_graph",
    "parse_semantics",
    "render_increment",
    "render_open_questions",
    "render_project",
    "render_roadmap",
]

_SLUG_RE = re.compile(str(CONFIG_ID["pattern"]))
_PROBE_SLUG = "plan"
_MARKER = f"Plan-Format: {PLAN_FORMAT}"
QUESTION_STATUSES = frozenset({"OPEN", "RESOLVED", "REPLAN"})
#: §7 fixes six compact fields so a prompt stays focused. ``Blocks`` names what the
#: question holds back; it never blocks admission, because admission does not read
#: ``open-questions.md`` at all.
QUESTION_BLOCKS = frozenset({"INV", "CT", "SLICE", "NON-GOAL", "RISK"})
_STEP_MODES = frozenset({"prescriptive", "outcome"})
_INVARIANT_KINDS = frozenset({"HARD", "SOFT"})
_EVIDENCE_MODES = frozenset({"TEST_REQUIRED", "NON_EXECUTABLE"})
_BLOCK_REF_RE = re.compile(r"^(?:INV-\d+[a-z]?|CT-\d+[a-z]?\.\d+[a-z]?|SLICE\d+[a-z]?)$")
#: The selector prefix is formed exactly once, here.
_SELECTOR_ROOT = "acceptance/tests/"


class SemanticsError(ValueError):
    """Closed refusal reason; never carries input text or an exception body."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid plan semantics: {rule}")


@dataclass(frozen=True, slots=True)
class Question:
    """One ``Q-###`` record, six fields as §7 fixes them."""

    number: str
    question: str
    blocks: str
    status: str
    decision: str
    updated: str

    @property
    def id(self) -> str:
        return f"Q-{self.number}"


@dataclass(frozen=True, slots=True)
class SemanticsContract:
    """One ``CT-<slice>.<n>`` line; the slice number supplies the id prefix."""

    number: str
    cls: str
    inv: str
    text: str


@dataclass(frozen=True, slots=True)
class SemanticsStep:
    """One step; the exit check it names must exist in the same slice."""

    number: str
    text: str
    check: str


@dataclass(frozen=True, slots=True)
class SemanticsSlice:
    """One slice's declarations, in the order the renderer emits them."""

    number: str
    name: str
    steps_mode: str
    contracts: tuple[SemanticsContract, ...] = ()
    acceptance: tuple[tuple[str, str, str], ...] = ()
    kill_targets: tuple[tuple[str, str, str], ...] = ()
    exit_checks: tuple[tuple[str, str, tuple[str, ...]], ...] = ()
    steps: tuple[SemanticsStep, ...] = ()


@dataclass(frozen=True, slots=True)
class PlanSemantics:
    """The whole payload: prose, records, and the declarations admission will judge."""

    intent: str
    out_of_scope: str
    questions: tuple[Question, ...] = ()
    invariants: tuple[Invariant, ...] = ()
    scenarios: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = ()
    slices: tuple[SemanticsSlice, ...] = ()


def _text(value: object, field: str, *, allow_newline: bool = False) -> str:
    """One prose field: non-empty, unpadded, and free of characters that read as structure."""
    if not isinstance(value, str) or not value:
        raise SemanticsError(f"{field}-invalid")
    if value != value.strip() or "\x00" in value or "\r" in value:
        raise SemanticsError(f"{field}-invalid")
    if not allow_newline and "\n" in value:
        raise SemanticsError(f"{field}-invalid")
    if "|" in value:
        # Every row format in the grammar is pipe-separated; a pipe inside a value
        # would be read as a column boundary and silently reshape the document.
        raise SemanticsError(f"{field}-invalid")
    return value


def _closed(value: object, allowed: frozenset[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise SemanticsError(f"{field}-invalid")
    return value


def _list(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, (list, tuple)):
        raise SemanticsError(f"{field}-invalid")
    return value


def _mapping(value: object, keys: frozenset[str], field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise SemanticsError(f"{field}-invalid")
    return value


def _parse_question(raw: object) -> Question:
    fields = frozenset({"number", "question", "blocks", "status", "decision", "updated"})
    item = _mapping(raw, fields, "question")
    number = _text(item["number"], "question-number")
    if not number.isdigit():
        raise SemanticsError("question-number-invalid")
    blocks = _text(item["blocks"], "question-blocks")
    for ref in (part.strip() for part in blocks.split(",")):
        if ref not in QUESTION_BLOCKS and _BLOCK_REF_RE.match(ref) is None:
            raise SemanticsError("question-blocks-invalid")
    return Question(
        number=number,
        question=_text(item["question"], "question-text"),
        blocks=blocks,
        status=_closed(item["status"], QUESTION_STATUSES, "question-status"),
        decision=_text(item["decision"], "question-decision", allow_newline=True),
        updated=_text(item["updated"], "question-updated"),
    )


def _parse_invariant(raw: object) -> Invariant:
    fields = frozenset({"number", "kind", "text", "evidence", "reason"})
    item = _mapping(raw, fields, "invariant")
    number = _text(item["number"], "invariant-number")
    if not number.isdigit():
        raise SemanticsError("invariant-number-invalid")
    evidence = _closed(item["evidence"], _EVIDENCE_MODES, "invariant-evidence")
    reason = item["reason"]
    if evidence == "NON_EXECUTABLE":
        reason = _closed(reason, DISPOSITION_REASONS, "invariant-reason")
    elif reason is not None:
        # The grammar refuses a disposition line on a TEST_REQUIRED invariant, so
        # accepting it here would only move the refusal one step later.
        raise SemanticsError("invariant-reason-invalid")
    return Invariant(
        id=f"INV-{number}",
        kind=_closed(item["kind"], _INVARIANT_KINDS, "invariant-kind"),
        text=_text(item["text"], "invariant-text"),
        evidence=evidence,
        reason=reason,
    )


def _parse_scenario(raw: object) -> tuple[str, str, str, str, tuple[str, ...]]:
    fields = frozenset({"number", "path", "trigger", "outcome", "ct_ids"})
    item = _mapping(raw, fields, "scenario")
    number = _text(item["number"], "scenario-number")
    if not number.isdigit():
        raise SemanticsError("scenario-number-invalid")
    ct_ids = tuple(_text(entry, "scenario-ct") for entry in _list(item["ct_ids"], "scenario-ct"))
    if not ct_ids:
        raise SemanticsError("scenario-ct-invalid")
    return (
        f"SCN-{number}",
        _text(item["path"], "scenario-path"),
        _text(item["trigger"], "scenario-trigger"),
        _text(item["outcome"], "scenario-outcome"),
        ct_ids,
    )


def _parse_contract(raw: object) -> SemanticsContract:
    item = _mapping(raw, frozenset({"number", "cls", "inv", "text"}), "contract")
    return SemanticsContract(
        number=_text(item["number"], "contract-number"),
        cls=_closed(item["cls"], CONTRACT_CLASSES, "contract-class"),
        inv=_text(item["inv"], "contract-inv"),
        text=_text(item["text"], "contract-text"),
    )


def _parse_step(raw: object) -> SemanticsStep:
    item = _mapping(raw, frozenset({"number", "text", "check"}), "step")
    text = _text(item["text"], "step-text")
    if "EXIT-CHECK:" in text:
        # The parser reads the first ``EXIT-CHECK:`` it finds; a second one inside the
        # prose would silently shorten the step it describes.
        raise SemanticsError("step-text-invalid")
    return SemanticsStep(
        number=_text(item["number"], "step-number"), text=text, check=_text(item["check"], "step-check")
    )


_ACCEPTANCE_FIELDS = frozenset({"test_id", "ct", "selector"})
_KILL_FIELDS = frozenset({"target_id", "ct", "test_id"})
_CHECK_FIELDS = frozenset({"check", "step", "test_ids"})


def _parse_acceptance_row(raw: object) -> tuple[str, str, str]:
    row = _mapping(raw, _ACCEPTANCE_FIELDS, "acceptance")
    return (
        _text(row["test_id"], "acceptance-id"),
        _text(row["ct"], "acceptance-ct"),
        _text(row["selector"], "acceptance-selector"),
    )


def _parse_kill_row(raw: object) -> tuple[str, str, str]:
    row = _mapping(raw, _KILL_FIELDS, "kill-target")
    return (
        _text(row["target_id"], "target-id"),
        _text(row["ct"], "target-ct"),
        _text(row["test_id"], "target-test"),
    )


def _parse_check_row(raw: object) -> tuple[str, str, tuple[str, ...]]:
    row = _mapping(raw, _CHECK_FIELDS, "exit-check")
    return (
        _text(row["check"], "exit-check-id"),
        _text(row["step"], "exit-check-step"),
        tuple(_text(entry, "exit-check-test") for entry in _list(row["test_ids"], "exit-check-test")),
    )


def _parse_slice(raw: object) -> SemanticsSlice:
    fields = frozenset(
        {"number", "name", "steps_mode", "contracts", "acceptance", "kill_targets", "exit_checks", "steps"}
    )
    item = _mapping(raw, fields, "slice")
    return SemanticsSlice(
        number=_text(item["number"], "slice-number"),
        name=_text(item["name"], "slice-name"),
        steps_mode=_closed(item["steps_mode"], _STEP_MODES, "slice-steps-mode"),
        contracts=tuple(map(_parse_contract, _list(item["contracts"], "contracts"))),
        acceptance=tuple(map(_parse_acceptance_row, _list(item["acceptance"], "acceptance"))),
        kill_targets=tuple(map(_parse_kill_row, _list(item["kill_targets"], "kill_targets"))),
        exit_checks=tuple(map(_parse_check_row, _list(item["exit_checks"], "exit_checks"))),
        steps=tuple(map(_parse_step, _list(item["steps"], "steps"))),
    )


_PAYLOAD_FIELDS = frozenset({"intent", "out_of_scope", "questions", "invariants", "scenarios", "slices"})


def parse_semantics(raw: object) -> PlanSemantics:
    """Validate the planner payload's own shape, then prove the bytes it renders.

    Shape errors name the payload field (``slice-steps-mode``, ``contract-class``); grammar
    errors are raised by ``plan_v2.parse_plan`` on the rendered pair, so the payload is
    judged by the same vocabulary admission uses and there is no second copy of the rules.
    """
    item = _mapping(raw, _PAYLOAD_FIELDS, "payload")
    semantics = PlanSemantics(
        intent=_text(item["intent"], "intent", allow_newline=True),
        out_of_scope=_text(item["out_of_scope"], "out-of-scope", allow_newline=True),
        questions=tuple(map(_parse_question, _list(item["questions"], "questions"))),
        invariants=tuple(map(_parse_invariant, _list(item["invariants"], "invariants"))),
        scenarios=tuple(map(_parse_scenario, _list(item["scenarios"], "scenarios"))),
        slices=tuple(map(_parse_slice, _list(item["slices"], "slices"))),
    )
    numbers = [question.number for question in semantics.questions]
    if len(set(numbers)) != len(numbers):
        raise SemanticsError("duplicate-question-id")
    # The probe slug is fixed and valid, so a refusal here is a property of the payload,
    # never of the name the caller will install it under.
    render_project(semantics, project_slug=_PROBE_SLUG)
    return semantics


def _heading_free(prose: str) -> str:
    """Refuse prose that would open a top-level section if it were concatenated verbatim."""
    for line in prose.splitlines():
        if line.startswith("#"):
            raise SemanticsError("prose-heading")
    return prose


def render_roadmap(semantics: PlanSemantics) -> str:
    """The roadmap body: marker plus the two prose sections, no ``# `` heading.

    The authority prepends its own ``# Roadmap — <slug>`` and front matter
    (``publication.render_bundle``), so emitting either here would duplicate metadata
    the planner does not own.
    """
    return (
        f"{_MARKER}\n\n"
        "## Intent\n\n"
        f"{_heading_free(semantics.intent)}\n\n"
        "## Out of scope\n\n"
        f"{_heading_free(semantics.out_of_scope)}\n"
    )


def _selector_row(selector: str, project_slug: str) -> str:
    """Expand one project-relative selector, or refuse a payload that pre-empted the slug."""
    if not selector.startswith(_SELECTOR_ROOT) or "::" not in selector:
        raise SemanticsError("acceptance-selector-invalid")
    if selector.count("::") != 1:
        raise SemanticsError("acceptance-selector-invalid")
    return f"worklogs/{project_slug}/{selector}"


def _contract_rows(planned: SemanticsSlice) -> list[str]:
    return [
        f"  CT-{planned.number}.{contract.number} [{contract.cls}] INV: {contract.inv}: {contract.text}"
        for contract in planned.contracts
    ]


def _acceptance_rows(planned: SemanticsSlice, project_slug: str) -> list[str]:
    return [
        f"  TEST-ID: {test_id} | CT: {ct} | SELECTOR: {_selector_row(selector, project_slug)}"
        for test_id, ct, selector in planned.acceptance
    ]


def _kill_rows(planned: SemanticsSlice) -> list[str]:
    return [
        f"  TARGET-ID: {target_id} | CT: {ct} | TEST-ID: {test_id}" for target_id, ct, test_id in planned.kill_targets
    ]


def _check_rows(planned: SemanticsSlice) -> list[str]:
    return [
        f"  CHECK-ID: {check_id} | STEP: {step} | TEST-ID[]: {', '.join(test_ids)}"
        for check_id, step, test_ids in planned.exit_checks
    ]


def _step_rows(planned: SemanticsSlice) -> list[str]:
    return [f"- [ ] STEP{step.number}: {step.text} EXIT-CHECK: {step.check}" for step in planned.steps]


def _section(title: str, rows: list[str]) -> list[str]:
    """One typed section. An empty section emits its header only: the parser accepts that."""
    return [f"{title}:", *rows]


def render_increment(semantics: PlanSemantics, *, project_slug: str) -> str:
    """Render the increment body: marker, then the typed sections in canonical order.

    ``STEPS: <mode>`` is the slice's single mode line and the step list is a bare list of
    items beneath its own section — emitting a second ``STEPS:`` header is refused by the
    parser as ``slice-<n>-steps-mode``, and a step inside another section would be bucketed
    away from the slice.
    """
    if _SLUG_RE.fullmatch(project_slug) is None:
        raise SemanticsError("project-slug-invalid")
    lines = [_MARKER, ""]
    if semantics.invariants:
        lines.append("## INVARIANTS")
        for invariant in semantics.invariants:
            lines += [
                f"### {invariant.id}",
                f"KIND: {invariant.kind}",
                f"TEXT: {invariant.text}",
                f"EVIDENCE: {invariant.evidence}",
            ]
            if invariant.reason is not None:
                lines.append(f"DISPOSITION-REASON: {invariant.reason}")
            lines.append("")
    if semantics.scenarios:
        lines.append("## SCENARIOS")
        for scenario_id, path, trigger, outcome, ct_ids in semantics.scenarios:
            lines += [
                f"### {scenario_id}",
                f"PATH: {path}",
                f"TRIGGER: {trigger}",
                f"OUTCOME: {outcome}",
                f"CT-ID[]: {', '.join(ct_ids)}",
                "",
            ]
    for planned in semantics.slices:
        lines += [
            f"## SLICE{planned.number}: {planned.name}",
            "",
            f"STEPS: {planned.steps_mode}",
            *_section("CONTRACTS", _contract_rows(planned)),
            *_section("ACCEPTANCE", _acceptance_rows(planned, project_slug)),
            *_section("KILL-TARGETS", _kill_rows(planned)),
            *_section("STEP-EXIT-CHECKS", _check_rows(planned)),
            *_step_rows(planned),
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"


def render_open_questions(semantics: PlanSemantics) -> str:
    """The ``open-questions.md`` projection: six fields per record (§7).

    Admission never reads this document — it is sealed with the plan and projected for the
    agent, the same reasoning that keeps status ticks outside the admitted bytes. A Q that
    must block work is honoured by omitting that work from the payload, not by a resolver
    state machine over prose.
    """
    lines = [
        "# Open questions",
        "",
        "| Q-ID | Question | Blocks | Status | Decision / Evidence | Updated |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for question in semantics.questions:
        lines.append(
            f"| {question.id} | {question.question} | {question.blocks} | {question.status} "
            f"| {question.decision} | {question.updated} |"
        )
    return "\n".join(lines) + "\n"


def render_project(semantics: PlanSemantics, *, project_slug: str) -> dict[str, str]:
    """Render every document the semantics own, and prove the pair admits before returning.

    The self-check is the point: a renderer that can emit inadmissible bytes makes the
    parser's vocabulary advisory. Rendering then parsing with the *real* slug also proves
    the selector expansion produces the same graph the probe did.
    """
    roadmap = render_roadmap(semantics)
    increment = render_increment(semantics, project_slug=project_slug)
    try:
        parse_plan(roadmap=roadmap, increment=increment)
    except PlanV2Error as error:
        raise SemanticsError(error.rule) from None
    return {
        "roadmap.md": roadmap,
        "increments/increment-01-initial-plan.md": increment,
        "open-questions.md": render_open_questions(semantics),
    }


def _graph_invariants(graph: PlanGraph) -> tuple[Invariant, ...]:
    return tuple(replace(invariant, owner=None, evidence_ref=None) for invariant in graph.invariants)


def _graph_slice(planned: SlicePlan, *, project_slug: str) -> SemanticsSlice:
    prefix = f"worklogs/{project_slug}/"
    return SemanticsSlice(
        number=planned.number,
        name=planned.name,
        steps_mode=planned.steps_mode,
        contracts=tuple(
            SemanticsContract(
                number=contract.id.split(".", 1)[1], cls=contract.cls, inv=contract.inv, text=contract.text
            )
            for contract in planned.contracts
        ),
        acceptance=tuple(
            (entry.test_id, entry.ct, entry.selector.removeprefix(prefix)) for entry in planned.acceptance
        ),
        kill_targets=tuple((target.target_id, target.ct, target.test_id) for target in planned.kill_targets),
        exit_checks=tuple((check.check_id, check.step, tuple(check.test_ids)) for check in planned.exit_checks),
        steps=tuple(SemanticsStep(number=step.number, text=step.text, check=step.check_id) for step in planned.steps),
    )


def from_graph(
    graph: PlanGraph,
    *,
    project_slug: str,
    intent: str = "",
    out_of_scope: str = "",
    questions: tuple[Question, ...] = (),
) -> PlanSemantics:
    """Invert ``parse_plan`` for the increment, so a rendered plan can be re-rendered.

    The graph does not model the roadmap's two prose sections or the question records, so
    they are supplied (or left empty). Step marks are normalised to ``[ ]``: a tick never
    enters sealed bytes (Q-V2-STATUS-1), which is why the increment — not the roadmap — is
    the half with a byte-idempotence law.
    """
    prefix = f"worklogs/{project_slug}/"
    stray = [
        entry.selector
        for planned in graph.slices
        for entry in planned.acceptance
        if not entry.selector.startswith(prefix)
    ]
    if stray:
        # A selector from another project would silently render as a foreign path.
        raise SemanticsError("selector-outside-project")
    return PlanSemantics(
        intent=intent,
        out_of_scope=out_of_scope,
        questions=questions,
        invariants=_graph_invariants(graph),
        scenarios=tuple(
            (scenario.id, scenario.path, scenario.trigger, scenario.outcome, tuple(scenario.ct_ids))
            for scenario in graph.scenarios
        ),
        slices=tuple(_graph_slice(planned, project_slug=project_slug) for planned in graph.slices),
    )
