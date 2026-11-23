"""The AI-NATIVE-PLAN-V2 plan grammar and its admission rules (STEP9A).

The grammar is deliberately small and closed: invariants with a typed evidence
mode, optional scenarios, and per-slice contracts, acceptance selectors, kill
targets and step-exit checks. Parsing yields a typed graph; admission proves the
graph's cardinalities and rejections; selector resolution is a separate step
because it needs the actual pytest collection.

``NON_EXECUTABLE`` evidence is legal only through the operator-ratified typed
disposition (Q-V2-ACC-2 = B-narrow): a closed reason code and a capped count.
There is no free-text exception.

Who decided, against what, and when is *caller authority* (R1, E577): the plan
may only request a disposition by reason, and ``DISPOSITION-OWNER`` /
``DISPOSITION-EVIDENCE`` in a plan are refused outright -- self-ratification is
unrepresentable rather than merely checked. The declaring record and the binding
rule live in ``plan_admission``; ``owner``/``evidence_ref`` below are filled by
that binding, never parsed from a document.

A disposition is not a proof. ``contract_evidence`` grades every contract by the
strongest evidence the plan actually affords — an acceptance selector
(``EXECUTABLE``), else an out-of-sandbox disposition (``ATTESTED``), else
nothing (``UNCOVERED``) — so that no consumer can present an attested contract
as a proven one (R2).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "APPROVAL_EVIDENCE_KINDS",
    "CONTRACT_CLASSES",
    "DISPOSITION_OWNERS",
    "DISPOSITION_REASONS",
    "DISPOSITION_ROUTES",
    "EVIDENCE_ROUTES",
    "MAX_DISPOSITIONS",
    "MAX_DISPOSITION_AGE_DAYS",
    "MAX_PLAN_BYTES",
    "PLAN_FORMAT",
    "PROBE_EVIDENCE_KINDS",
    "Acceptance",
    "Attestation",
    "Contract",
    "EvidenceMode",
    "ExitCheck",
    "Invariant",
    "KillTarget",
    "PlanGraph",
    "PlanV2Error",
    "Scenario",
    "SlicePlan",
    "Step",
    "attested_contracts",
    "contract_attestations",
    "contract_evidence",
    "is_contract_id",
    "parse_plan",
    "pending_contracts",
    "resolve_selectors",
]

PLAN_FORMAT = "AI-NATIVE-PLAN-V2"
MAX_PLAN_BYTES = 1024 * 1024
#: Typed disposition vocabulary (Q-V2-ACC-2 = B-narrow). Closed on purpose: a new
#: reason is a ratified doc change, never a planner choice.
DISPOSITION_REASONS = frozenset(
    {
        "HOST_READINESS",
        "DEPLOYMENT_IDENTITY",
        "OWNER_APPROVAL",
        "DURABILITY_POWER_LOSS",
    }
)
DISPOSITION_OWNERS = frozenset({"W4", "operator"})
#: D-V2-12: the route a reason commits the caller to. A route is not a severity:
#: it says *where* the claim is checkable, and it decides the one legal kind of
#: artifact the caller must name. Deriving it from the reason keeps the axis
#: closed: a new reason must arrive with its route, never with a free choice.
DISPOSITION_ROUTES = {
    "HOST_READINESS": "HOST_PROBE",
    "DEPLOYMENT_IDENTITY": "HOST_PROBE",
    "DURABILITY_POWER_LOSS": "HOST_PROBE",
    "OWNER_APPROVAL": "APPROVAL",
}
#: The closed route axis (D-V2-12). ``TEST`` is the route of every contract a
#: selector covers; the other two belong to the disposition lane.
EVIDENCE_ROUTES = frozenset({"TEST", "HOST_PROBE", "APPROVAL"})
#: ``probe:<repo-relative path>@host:<label>``: an artifact that can be run where
#: the claim is checkable, plus the host it is owed to.
PROBE_EVIDENCE_KINDS = frozenset({"probe"})
#: A document, an issue or a review: a reference a human can open. The only
#: route that accepts this is ``APPROVAL``, which is why that route is expensive.
APPROVAL_EVIDENCE_KINDS = frozenset({"doc", "issue", "review"})
MAX_DISPOSITIONS = 16
#: R5 (E577): an out-of-sandbox claim is re-reviewed, not trusted forever.
MAX_DISPOSITION_AGE_DAYS = 30
CONTRACT_CLASSES = frozenset({"FUNCTIONAL", "CONSTRAINT", "PRESERVATION"})
_EVIDENCE_MODES = frozenset({"TEST_REQUIRED", "NON_EXECUTABLE"})
_STEP_MODES = frozenset({"prescriptive", "outcome"})


class EvidenceMode(StrEnum):
    """What a plan affords for one contract, strongest first.

    ``EXECUTABLE`` — an acceptance selector in the sealed closure will be run.
    ``ATTESTED`` — the contract's invariant carries an out-of-sandbox
    disposition, so the claim is carried by a typed human record, never by a
    test: it may be reported as attested and must not be reported as proven.
    ``UNCOVERED`` — neither; the plan does not yet say how the claim is checked.
    """

    EXECUTABLE = "executable"
    ATTESTED = "attested"
    UNCOVERED = "uncovered"


_ID = r"\d+[a-z]?"
_INV_RE = re.compile(rf"^INV-({_ID})$")
_SCN_RE = re.compile(rf"^SCN-({_ID})$")
_CT_RE = re.compile(rf"^CT-({_ID})\.({_ID})$")
_TEST_RE = re.compile(rf"^TEST-({_ID})\.({_ID})$")
_CHECK_RE = re.compile(rf"^CHECK-({_ID})$")
_SLICE_RE = re.compile(r"^##\s+SLICE(\d+[a-z]?)\s*:\s*(.+)$")
_INVARIANTS_RE = re.compile(r"^##\s+INVARIANTS\s*$")
_SCENARIOS_RE = re.compile(r"^##\s+SCENARIOS\s*$")
_SUBHEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
_STEP_LINE_RE = re.compile(rf"^\s*-\s+\[(?P<mark>[^\]]*)\]\s+STEP(?P<num>{_ID})\s*:\s*(?P<text>.+?)\s*$")
_EXIT_CHECK_REF_RE = re.compile(rf"EXIT-CHECK:\s*CHECK-({_ID})\s*$")
_CONTRACT_ENTRY_RE = re.compile(
    rf"^CT-({_ID})\.({_ID})\s+\[(FUNCTIONAL|CONSTRAINT|PRESERVATION)\]\s+INV:\s*INV-({_ID})\s*:\s*(\S.*)$"
)
_SELECTOR_RE = re.compile(
    r"^worklogs/(?P<slug>[a-z][a-z0-9]*(?:-[a-z0-9]+)*)/acceptance/tests/"
    r"(?P<path>[A-Za-z0-9_./-]+\.py)::(?P<node>[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*)$"
)
#: Path segments a selector may never contain. The character class above admits ``.`` and
#: ``/``, so ``../`` would otherwise be accepted and resolved by the verifier: the plan
#: requires absolute paths, ``..`` and symlink escape to be rejected, and only the last
#: two are reachable inside the character class.
_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})
_V1_TOKEN_RE = re.compile(r"^(?:TESTS|STEPS-NOTE|KILLS)\s*:")
_SLICE_SECTIONS = ("CONTRACTS", "ACCEPTANCE", "KILL-TARGETS", "STEP-EXIT-CHECKS")


class PlanV2Error(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid AI-NATIVE-PLAN-V2 document: {rule}")


@dataclass(frozen=True, slots=True)
class Invariant:
    id: str
    text: str
    evidence: str
    #: Requested only: the plan names *why* it cannot test the claim.
    reason: str | None = None
    #: Granted only: ``plan_admission.bind_dispositions`` fills these from the
    #: caller's declaration. A parsed plan never carries them.
    evidence_ref: str | None = None
    owner: str | None = None
    #: Granted only: the ISO date the caller says the evidence was reviewed. The
    #: seal records it, because "reviewed" without a date cannot be re-reviewed.
    reviewed_at: str | None = None


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    path: str
    trigger: str
    outcome: str
    ct_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Contract:
    id: str
    cls: str
    inv: str
    text: str


@dataclass(frozen=True, slots=True)
class Acceptance:
    test_id: str
    ct: str
    selector: str


@dataclass(frozen=True, slots=True)
class KillTarget:
    target_id: str
    ct: str
    test_id: str


@dataclass(frozen=True, slots=True)
class ExitCheck:
    check_id: str
    step: str
    test_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Step:
    number: str
    text: str
    check_id: str


@dataclass(frozen=True, slots=True)
class SlicePlan:
    number: str
    name: str
    steps_mode: str
    contracts: tuple[Contract, ...]
    acceptance: tuple[Acceptance, ...]
    kill_targets: tuple[KillTarget, ...]
    exit_checks: tuple[ExitCheck, ...]
    steps: tuple[Step, ...]


@dataclass(frozen=True, slots=True)
class PlanGraph:
    invariants: tuple[Invariant, ...]
    scenarios: tuple[Scenario, ...]
    slices: tuple[SlicePlan, ...]

    def contracts(self) -> dict[str, Contract]:
        return {contract.id: contract for planned in self.slices for contract in planned.contracts}

    def acceptance(self) -> dict[str, Acceptance]:
        return {entry.test_id: entry for planned in self.slices for entry in planned.acceptance}

    def kill_targets(self) -> tuple[KillTarget, ...]:
        """Every declared ``KILL-TARGETS`` row, in document order (N2/Q-V2-SLICE3-4).

        The V2 grammar's target is *attribution*: which contract and which test a mutation
        belongs to. It carries no *operator*, and no agreed shape for the id either (the
        authoring prompt teaches ``path::symbol``, the fixtures use dotted ids -- Q-V2-SLICE3-5),
        so nothing here is executable --
        but a plan that declares one and a report that says nothing about it are different
        facts, and only this accessor lets a report tell them apart.
        """
        return tuple(target for planned in self.slices for target in planned.kill_targets)


@dataclass(frozen=True, slots=True)
class _Section:
    """One top-level typed section; ``name`` is set only for slices."""

    family: str
    body: list[str]
    name: str | None = None


@dataclass(slots=True)
class _Entry:
    """One ``###`` heading plus the raw lines beneath it."""

    id: str
    body: list[str] = field(default_factory=list)


def _mask_fences(lines: Sequence[str]) -> list[str]:
    """Blank fenced blocks, keeping line positions, so examples never parse."""
    masked = list(lines)
    marker: str | None = None
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if marker is None and (stripped.startswith("```") or stripped.startswith("~~~")):
            marker = stripped[:3]
            masked[index] = ""
            continue
        if marker is not None:
            masked[index] = ""
            if stripped.startswith(marker):
                marker = None
    if marker is not None:
        raise PlanV2Error("unterminated-fence")
    return masked


def _strip_front_matter(lines: Sequence[str]) -> list[str]:
    trimmed = list(lines)
    index = 0
    while index < len(trimmed) and not trimmed[index].strip():
        index += 1
    if index >= len(trimmed) or trimmed[index].strip() != "---":
        return trimmed
    index += 1
    while index < len(trimmed) and trimmed[index].strip() != "---":
        index += 1
    if index >= len(trimmed):
        raise PlanV2Error("unterminated-front-matter")
    return ["" for _ in trimmed[: index + 1]] + trimmed[index + 1 :]


def _require_marker(text: str, *, where: str) -> None:
    count = sum(1 for line in text.splitlines() if line.strip() == f"Plan-Format: {PLAN_FORMAT}")
    if count != 1:
        raise PlanV2Error(f"plan-format-marker-{where}")
    if re.search(r"Plan-Format:\s*(?!AI-NATIVE-PLAN-V2\b)[A-Za-z0-9-]+", text):
        raise PlanV2Error("plan-format-mismatch")


def _field(block: Sequence[str], name: str, *, rule: str) -> str:
    prefix = f"{name}:"
    values = [line.strip()[len(prefix) :].strip() for line in block if line.strip().startswith(prefix)]
    if len(values) != 1 or not values[0]:
        raise PlanV2Error(rule)
    return values[0]


def _collect_entries(
    lines: Sequence[str],
    *,
    pattern: re.Pattern[str],
    heading_rule: str,
    orphan_rule: str,
) -> list[_Entry]:
    """Split a typed section into ``###`` entries; stray prose is refused."""
    entries: list[_Entry] = []
    current: _Entry | None = None
    for line in lines:
        sub = _SUBHEADING_RE.match(line)
        if sub:
            match = pattern.match(sub.group(1))
            if match is None:
                raise PlanV2Error(heading_rule)
            current = _Entry(id=sub.group(1))
            entries.append(current)
            continue
        if not line.strip():
            continue
        if current is None:
            raise PlanV2Error(orphan_rule)
        current.body.append(line)
    return entries


def _build_invariant(entry: _Entry) -> Invariant:
    inv_id = entry.id
    # D-V2-10: severity is not part of the grammar. Its only reader exempted the
    # invariant from evidence, and a label that reads as policy while obliging
    # nothing is how an uncovered contract reached an admitted plan. A document
    # that still writes it is told the field is gone -- silently ignoring it would
    # leave the model believing the label did something.
    if any(line.strip().startswith("KIND:") for line in entry.body):
        raise PlanV2Error("invariant-kind-removed")
    text = _field(entry.body, "TEXT", rule=f"invariant-{inv_id}-text")
    evidence = _field(entry.body, "EVIDENCE", rule=f"invariant-{inv_id}-evidence")
    if evidence not in _EVIDENCE_MODES:
        raise PlanV2Error(f"invariant-{inv_id}-evidence")
    # R1 (E577): the grant is not a plan field. Checked before the vocabulary so
    # a document that tries to own its own waiver is told *that*, not that its
    # reason code was spelled differently.
    if any(line.strip().startswith(("DISPOSITION-OWNER", "DISPOSITION-EVIDENCE")) for line in entry.body):
        raise PlanV2Error("disposition-not-caller-authority")
    if evidence == "TEST_REQUIRED":
        if any(line.strip().startswith("DISPOSITION-") for line in entry.body):
            raise PlanV2Error("disposition-without-non-executable")
        return Invariant(id=inv_id, text=text, evidence=evidence)
    reason = _field(entry.body, "DISPOSITION-REASON", rule=f"invariant-{inv_id}-disposition-reason")
    if reason not in DISPOSITION_REASONS:
        raise PlanV2Error("disposition-reason-unratified")
    return Invariant(id=inv_id, text=text, evidence=evidence, reason=reason)


def _parse_invariants(lines: Sequence[str]) -> tuple[Invariant, ...]:
    entries = [
        _build_invariant(entry)
        for entry in _collect_entries(
            lines,
            pattern=_INV_RE,
            heading_rule="invariants-unknown-heading",
            orphan_rule="invariants-orphan-content",
        )
    ]
    if len({entry.id for entry in entries}) != len(entries):
        raise PlanV2Error("duplicate-invariant-id")
    if sum(1 for entry in entries if entry.evidence == "NON_EXECUTABLE") > MAX_DISPOSITIONS:
        raise PlanV2Error("too-many-dispositions")
    # A reason is a one-shot capability, not a label (E585). The grant is keyed by
    # reason, so two invariants naming one reason would both be authorised by a
    # single declaration: the caller decided one thing and silently attested two
    # claims. This lives on the invariant rather than on the contract so it stays
    # orthogonal to the cluster rule, which bounds contracts per invariant.
    reasons = [entry.reason for entry in entries if entry.evidence == "NON_EXECUTABLE"]
    if len(set(reasons)) != len(reasons):
        raise PlanV2Error("disposition-reason-reused")
    return tuple(entries)


def _build_scenario(entry: _Entry) -> Scenario:
    scn = entry.id
    path = _field(entry.body, "PATH", rule=f"scenario-{scn}-path")
    trigger = _field(entry.body, "TRIGGER", rule=f"scenario-{scn}-trigger")
    outcome = _field(entry.body, "OUTCOME", rule=f"scenario-{scn}-outcome")
    raw = _field(entry.body, "CT-ID[]", rule=f"scenario-{scn}-ct-ids")
    ct_ids = tuple(item.strip() for item in raw.split(",") if item.strip())
    if not ct_ids or len(set(ct_ids)) != len(ct_ids):
        raise PlanV2Error(f"scenario-{scn}-ct-ids")
    if any(_CT_RE.match(ct_id) is None for ct_id in ct_ids):
        raise PlanV2Error(f"scenario-{scn}-ct-ids")
    return Scenario(id=scn, path=path, trigger=trigger, outcome=outcome, ct_ids=ct_ids)


def _parse_scenarios(lines: Sequence[str]) -> tuple[Scenario, ...]:
    entries = [
        _build_scenario(entry)
        for entry in _collect_entries(
            lines,
            pattern=_SCN_RE,
            heading_rule="scenarios-unknown-heading",
            orphan_rule="scenarios-orphan-content",
        )
    ]
    if len({entry.id for entry in entries}) != len(entries):
        raise PlanV2Error("duplicate-scenario-id")
    return tuple(entries)


def _steps_mode(lines: Sequence[str], number: str) -> str:
    declared = [line.strip() for line in lines if line.strip().startswith("STEPS:")]
    if len(declared) != 1:
        raise PlanV2Error(f"slice-{number}-steps-mode")
    mode = declared[0][len("STEPS:") :].strip()
    if mode not in _STEP_MODES:
        raise PlanV2Error(f"slice-{number}-steps-mode")
    return mode


def _slice_sections(lines: Sequence[str], number: str) -> dict[str, list[str]]:
    """Bucket the slice body by typed section; steps get their own bucket."""
    buckets: dict[str, list[str]] = {name: [] for name in _SLICE_SECTIONS}
    steps: list[str] = []
    buckets["STEPS"] = steps
    section: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("STEPS:"):
            section = None
            continue
        if stripped[:-1] in _SLICE_SECTIONS and stripped.endswith(":"):
            section = stripped[:-1]
            continue
        if _STEP_LINE_RE.match(line) is not None:
            steps.append(line)
            continue
        if _V1_TOKEN_RE.match(stripped):
            raise PlanV2Error("orphan-v1-token")
        if section is None:
            raise PlanV2Error(f"slice-{number}-unknown-field")
        buckets[section].append(stripped)
    return buckets


def _parse_contracts(rows: Sequence[str], number: str) -> tuple[Contract, ...]:
    contracts: list[Contract] = []
    for row in rows:
        match = _CONTRACT_ENTRY_RE.match(row)
        if match is None:
            raise PlanV2Error(f"slice-{number}-contract-entry")
        if match.group(1) != number:
            raise PlanV2Error("contract-slice-mismatch")
        contracts.append(
            Contract(
                id=f"CT-{match.group(1)}.{match.group(2)}",
                cls=match.group(3),
                inv=f"INV-{match.group(4)}",
                text=match.group(5).strip(),
            )
        )
    return tuple(contracts)


def _labelled(row: str, expected: set[str], *, rule: str) -> dict[str, str]:
    parts = [part.strip() for part in row.split("|")]
    fields: dict[str, str] = {}
    for part in parts:
        if ":" not in part:
            raise PlanV2Error(rule)
        key, value = part.split(":", 1)
        fields[key.strip()] = value.strip()
    if len(parts) != len(expected) or set(fields) != expected:
        raise PlanV2Error(rule)
    return fields


def _parse_acceptance(rows: Sequence[str], number: str) -> tuple[Acceptance, ...]:
    entries: list[Acceptance] = []
    for row in rows:
        fields = _labelled(row, {"TEST-ID", "CT", "SELECTOR"}, rule=f"slice-{number}-acceptance-entry")
        test_match = _TEST_RE.match(fields["TEST-ID"])
        if test_match is None or test_match.group(1) != number:
            raise PlanV2Error("acceptance-test-id-invalid")
        if _CT_RE.match(fields["CT"]) is None:
            raise PlanV2Error("acceptance-ct-invalid")
        match = _SELECTOR_RE.match(fields["SELECTOR"])
        if match is None:
            raise PlanV2Error("acceptance-selector-invalid")
        if _FORBIDDEN_SEGMENTS.intersection(match.group("path").split("/")):
            raise PlanV2Error("acceptance-selector-invalid")
        entries.append(Acceptance(test_id=fields["TEST-ID"], ct=fields["CT"], selector=fields["SELECTOR"]))
    return tuple(entries)


def _parse_kill_targets(rows: Sequence[str], number: str) -> tuple[KillTarget, ...]:
    targets: list[KillTarget] = []
    for row in rows:
        fields = _labelled(row, {"TARGET-ID", "CT", "TEST-ID"}, rule=f"slice-{number}-kill-target-entry")
        if not fields["TARGET-ID"] or len(fields["TARGET-ID"]) > 256:
            raise PlanV2Error("kill-target-id-invalid")
        if _CT_RE.match(fields["CT"]) is None or _TEST_RE.match(fields["TEST-ID"]) is None:
            raise PlanV2Error("kill-target-attribution-invalid")
        targets.append(KillTarget(target_id=fields["TARGET-ID"], ct=fields["CT"], test_id=fields["TEST-ID"]))
    return tuple(targets)


def _parse_exit_checks(rows: Sequence[str], number: str) -> tuple[ExitCheck, ...]:
    checks: list[ExitCheck] = []
    for row in rows:
        fields = _labelled(row, {"CHECK-ID", "STEP", "TEST-ID[]"}, rule=f"slice-{number}-exit-check-entry")
        if _CHECK_RE.match(fields["CHECK-ID"]) is None:
            raise PlanV2Error("exit-check-id-invalid")
        if re.fullmatch(rf"STEP{_ID}", fields["STEP"]) is None:
            raise PlanV2Error("exit-check-step-invalid")
        test_ids = tuple(item.strip() for item in fields["TEST-ID[]"].split(",") if item.strip())
        if not test_ids or any(_TEST_RE.match(item) is None for item in test_ids):
            raise PlanV2Error("exit-check-test-ids-invalid")
        checks.append(ExitCheck(check_id=fields["CHECK-ID"], step=fields["STEP"], test_ids=test_ids))
    return tuple(checks)


def _parse_steps(rows: Sequence[str]) -> tuple[Step, ...]:
    steps: list[Step] = []
    for row in rows:
        match = _STEP_LINE_RE.match(row)
        if match is None:
            raise PlanV2Error("step-entry-invalid")
        exit_ref = _EXIT_CHECK_REF_RE.search(match.group("text"))
        if exit_ref is None:
            raise PlanV2Error(f"step-{match.group('num')}-exit-check-missing")
        steps.append(
            Step(
                number=match.group("num"),
                text=match.group("text")[: exit_ref.start()].strip(),
                check_id=f"CHECK-{exit_ref.group(1)}",
            )
        )
    return tuple(steps)


def _parse_slice(number: str, name: str, lines: Sequence[str]) -> SlicePlan:
    buckets = _slice_sections(lines, number)
    return SlicePlan(
        number=number,
        name=name,
        steps_mode=_steps_mode(lines, number),
        contracts=_parse_contracts(buckets["CONTRACTS"], number),
        acceptance=_parse_acceptance(buckets["ACCEPTANCE"], number),
        kill_targets=_parse_kill_targets(buckets["KILL-TARGETS"], number),
        exit_checks=_parse_exit_checks(buckets["STEP-EXIT-CHECKS"], number),
        steps=_parse_steps(buckets["STEPS"]),
    )


def _admit_contracts(graph: PlanGraph, contracts: Mapping[str, Contract]) -> None:
    if len(contracts) != sum(len(planned.contracts) for planned in graph.slices):
        raise PlanV2Error("duplicate-contract-id")
    invariants = {item.id for item in graph.invariants}
    for contract in contracts.values():
        if contract.inv not in invariants:
            raise PlanV2Error("dangling-invariant-edge")


def _admit_acceptance(graph: PlanGraph, contracts: Mapping[str, Contract]) -> dict[str, Acceptance]:
    tests = graph.acceptance()
    if len(tests) != sum(len(planned.acceptance) for planned in graph.slices):
        raise PlanV2Error("duplicate-test-id")
    selectors = [entry.selector for entry in tests.values()]
    if len(set(selectors)) != len(selectors):
        raise PlanV2Error("duplicate-selector-ownership")
    for entry in tests.values():
        if entry.ct not in contracts:
            raise PlanV2Error("dangling-contract-edge")
    return tests


def _admit_scenarios(graph: PlanGraph, contracts: Mapping[str, Contract]) -> None:
    for scenario in graph.scenarios:
        for ct_id in scenario.ct_ids:
            if ct_id not in contracts:
                raise PlanV2Error("dangling-scenario-edge")


def _admit_kill_targets(planned: SlicePlan, tests: Mapping[str, Acceptance]) -> None:
    slice_contracts = {contract.id for contract in planned.contracts}
    for target in planned.kill_targets:
        if target.ct not in slice_contracts or target.test_id not in tests:
            raise PlanV2Error("dangling-kill-target")
        if tests[target.test_id].ct != target.ct:
            raise PlanV2Error("kill-target-attribution-mismatch")


def _admit_steps(planned: SlicePlan, tests: Mapping[str, Acceptance]) -> None:
    check_ids = [check.check_id for check in planned.exit_checks]
    if len(set(check_ids)) != len(check_ids):
        raise PlanV2Error("duplicate-exit-check-id")
    referenced = [step.check_id for step in planned.steps]
    if len(set(referenced)) != len(referenced):
        raise PlanV2Error("exit-check-reused")
    if set(referenced) != set(check_ids):
        raise PlanV2Error("exit-check-unmapped")
    numbers = [f"STEP{step.number}" for step in planned.steps]
    if len(set(numbers)) != len(numbers):
        raise PlanV2Error("duplicate-step-id")
    slice_contracts = {contract.id for contract in planned.contracts}
    for check in planned.exit_checks:
        if check.step not in numbers:
            raise PlanV2Error("exit-check-step-unmapped")
        for test_id in check.test_ids:
            if test_id not in tests or tests[test_id].ct not in slice_contracts:
                raise PlanV2Error("exit-check-test-unmapped")


def _admit_evidence(graph: PlanGraph, contracts: Mapping[str, Contract], tests: Mapping[str, Acceptance]) -> None:
    """Evidence totality (D-V2-10): every contract is discharged exactly once.

    Two ways to discharge a contract, and no third: an acceptance row whose
    selector names its test, or a ``NON_EXECUTABLE`` invariant that states why the
    claim cannot be tested -- and that one is only a *request* until the caller
    grants it (``bind_dispositions``). Nothing exempts a contract: there is no
    severity field, no class that may skip the check, and no "soft" invitation to
    reason from. A ``TEST_REQUIRED`` contract with no selector is refused here, at
    the point the plan is read, which is also the point a repair round is still
    possible.

    ``PRESERVATION`` is checked first and separately: "what worked still works" is
    the one claim a test can always express, so attesting it away is how a
    regression ships green. That refusal is independent of the evidence mode,
    which is why it cannot be reached through the disposition branch.

    A request is structurally sufficient here; whether it was *granted* is checked
    by ``bind_dispositions`` at admission, where the caller's declaration exists
    and the grammar cannot be asked to know it. The one-shot bound on a *reason*
    lives in ``_parse_invariants`` (E585), so this function keeps a single job:
    one invariant may back at most one untested claim.
    """
    invariants = {item.id: item for item in graph.invariants}
    covered = {entry.ct for entry in tests.values()}
    granted: dict[str, int] = {}
    for contract in contracts.values():
        if contract.id in covered:
            continue
        invariant = invariants[contract.inv]
        if contract.cls == "PRESERVATION":
            raise PlanV2Error("preservation-without-executable-evidence")
        if invariant.evidence == "NON_EXECUTABLE" and invariant.reason:
            granted[invariant.id] = granted.get(invariant.id, 0) + 1
            continue
        raise PlanV2Error("contract-without-evidence")
    # One waiver frees one claim: an invariant that backs a cluster would attest
    # every contract under it with a single decision nobody re-read.
    if any(count > 1 for count in granted.values()):
        raise PlanV2Error("disposition-covers-several-contracts")


def _admit(graph: PlanGraph) -> None:
    """Prove the graph's cardinalities; every refusal is a closed rule."""
    contracts = graph.contracts()
    _admit_contracts(graph, contracts)
    tests = _admit_acceptance(graph, contracts)
    _admit_scenarios(graph, contracts)
    for planned in graph.slices:
        _admit_kill_targets(planned, tests)
        _admit_steps(planned, tests)
    _admit_evidence(graph, contracts, tests)


def _split_sections(lines: Sequence[str]) -> list[_Section]:
    """Top-level split: typed sections only, with a legal title and marker."""
    sections: list[_Section] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        family = ""
        if _INVARIANTS_RE.match(line):
            family = "INVARIANTS"
        elif _SCENARIOS_RE.match(line):
            family = "SCENARIOS"
        elif _SLICE_RE.match(line):
            family = "SLICE"
        if family:
            body: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith("## "):
                body.append(lines[index])
                index += 1
            if family == "SLICE":
                match = _SLICE_RE.match(line)
                if match is None:  # unreachable: the family test above matched
                    raise PlanV2Error("slice-heading-invalid")
                sections.append(_Section(family=f"SLICE{match.group(1)}", body=body, name=match.group(2).strip()))
            else:
                if any(section.family == family for section in sections):
                    raise PlanV2Error("duplicate-section")
                sections.append(_Section(family=family, body=body))
            continue
        if line.startswith("## "):
            raise PlanV2Error("unknown-top-level-section")
        stripped = line.strip()
        if stripped and not line.startswith("# ") and not stripped.startswith("Plan-Format:"):
            raise PlanV2Error("content-outside-sections")
        index += 1
    return sections


def parse_plan(*, roadmap: str, increment: str) -> PlanGraph:
    """Parse and admit one V2 roadmap/increment pair, or refuse with a closed rule."""
    if not isinstance(roadmap, str) or not isinstance(increment, str):
        raise PlanV2Error("document-invalid")
    for text in (roadmap, increment):
        if len(text.encode("utf-8")) > MAX_PLAN_BYTES or "\x00" in text:
            raise PlanV2Error("document-invalid")
    _require_marker(roadmap, where="roadmap")
    _require_marker(increment, where="increment")
    sections = _split_sections(_mask_fences(_strip_front_matter(increment.splitlines())))
    invariants: tuple[Invariant, ...] = ()
    scenarios: tuple[Scenario, ...] = ()
    slices: list[SlicePlan] = []
    for section in sections:
        if section.family == "INVARIANTS":
            invariants = _parse_invariants(section.body)
        elif section.family == "SCENARIOS":
            scenarios = _parse_scenarios(section.body)
        else:
            slices.append(_parse_slice(section.family[len("SLICE") :], section.name or "", section.body))
    if not slices:
        raise PlanV2Error("missing-slice")
    if not invariants:
        raise PlanV2Error("missing-invariants")
    graph = PlanGraph(invariants=invariants, scenarios=scenarios, slices=tuple(slices))
    _admit(graph)
    return graph


def resolve_selectors(graph: PlanGraph, collected: Mapping[str, Iterable[str]]) -> dict[str, str]:
    """Bind every acceptance selector to exactly one collected nodeid.

    ``collected`` maps a collected test file (workspace-relative) to the nodeids
    pytest reported for it. Missing, ambiguous or foreign nodeids fail closed.
    """
    resolved: dict[str, str] = {}
    for entry in graph.acceptance().values():
        path, _, node = entry.selector.partition("::")
        available = tuple(collected.get(path, ()))
        if not available:
            raise PlanV2Error("selector-uncollected")
        prefix = f"{path}::{node}"
        matching = [candidate for candidate in available if candidate == prefix or candidate.startswith(f"{prefix}[")]
        if not matching:
            raise PlanV2Error("selector-uncollected")
        if len(matching) > 1:
            raise PlanV2Error("selector-ambiguous")
        resolved[entry.test_id] = matching[0]
    if len(set(resolved.values())) != len(resolved):
        raise PlanV2Error("selector-duplicate-nodeid")
    return resolved


def is_contract_id(value: object) -> bool:
    """True only for this grammar's contract id (``_CT_RE``, fullmatch)."""
    return isinstance(value, str) and _CT_RE.fullmatch(value) is not None


def contract_evidence(graph: PlanGraph) -> dict[str, EvidenceMode]:
    """Grade every contract in the graph by the evidence that actually backs it.

    Precedence is "strongest wins": a contract that has both a selector and a
    disposition on its invariant is ``EXECUTABLE`` — the disposition never
    weakens evidence that exists.

    ``ATTESTED`` is a claim that *somebody authorised this*, so it needs the grant,
    not the request. R1 (E577) made ``NON_EXECUTABLE`` nothing but a request: the
    plan names why it cannot test the claim, and the caller's declaration supplies
    the owner and the reference. A bare ``parse_plan`` output therefore carries a
    request with ``owner is None`` and no reference, and grading that as attested
    would publish a verdict nobody gave. Only ``bind_dispositions`` fills those
    fields, so their presence is the observable proof that a grant was bound
    (R2 over R1, E585).
    """
    covered = {entry.ct for planned in graph.slices for entry in planned.acceptance}
    #: A granted invariant, not merely a disposed one: the reason alone is a request.
    granted = {item.id for item in graph.invariants if item.evidence == "NON_EXECUTABLE" and item.owner is not None}
    graded: dict[str, EvidenceMode] = {}
    for planned in graph.slices:
        for contract in planned.contracts:
            if contract.id in covered:
                graded[contract.id] = EvidenceMode.EXECUTABLE
            elif contract.inv in granted:
                graded[contract.id] = EvidenceMode.ATTESTED
            else:
                graded[contract.id] = EvidenceMode.UNCOVERED
    return graded


def attested_contracts(graph: PlanGraph) -> tuple[str, ...]:
    """The sorted contract ids whose only evidence is a disposition (R2)."""
    graded = contract_evidence(graph)
    return tuple(sorted(contract_id for contract_id, mode in graded.items() if mode is EvidenceMode.ATTESTED))


@dataclass(frozen=True, slots=True)
class Attestation:
    """One granted claim, in the form a reader can audit (D-V2-12, P4-8).

    ``scope_sha256`` is the digest of the two sentences the grant covers — the
    invariant's authored fields (id, text, evidence, reason) and the contract's
    (id, class, invariant, text). ``plan_sha256`` already invalidates a seal on any
    plan edit; the scope is what lets a reader see *which* sentence was attested,
    and what makes a re-review prove that it covered the new wording rather than
    the old one.
    """

    contract_id: str
    invariant_id: str
    reason: str
    route: str
    artifact: str
    owner: str | None
    reviewed_at: str | None
    scope_sha256: str


def _attestation_scope(invariant: Invariant, contract: Contract) -> str:
    payload = json.dumps(
        {
            "invariant": [invariant.id, invariant.text, invariant.evidence, invariant.reason],
            "contract": [contract.id, contract.cls, contract.inv, contract.text],
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def contract_attestations(graph: PlanGraph) -> tuple[Attestation, ...]:
    """Every contract carried by a disposition, with its route and artifact.

    Ordered by contract id so the seal record is canonical. A ``HOST_PROBE``
    contract is a **pending** claim — it names an artifact that must be run where
    the claim is checkable — while ``APPROVAL`` is a decision nobody can test.
    Both are *attested* in the sense that a named party carries them; only the
    first is still owed to a host, which is why ``pending_contracts`` exists
    instead of a single flag.
    """
    invariants = {item.id: item for item in graph.invariants}
    graded = contract_evidence(graph)
    records: list[Attestation] = []
    for contract in graph.contracts().values():
        if graded.get(contract.id) is not EvidenceMode.ATTESTED:
            continue
        invariant = invariants[contract.inv]
        reason = invariant.reason or ""
        records.append(
            Attestation(
                contract_id=contract.id,
                invariant_id=invariant.id,
                reason=reason,
                route=DISPOSITION_ROUTES.get(reason, ""),
                artifact=invariant.evidence_ref or "",
                owner=invariant.owner,
                reviewed_at=invariant.reviewed_at,
                scope_sha256=_attestation_scope(invariant, contract),
            )
        )
    return tuple(sorted(records, key=lambda item: item.contract_id))


def pending_contracts(graph: PlanGraph) -> tuple[str, ...]:
    """Contracts whose evidence is owed to a host that has not run it (D-V2-12)."""
    return tuple(item.contract_id for item in contract_attestations(graph) if item.route == "HOST_PROBE")
