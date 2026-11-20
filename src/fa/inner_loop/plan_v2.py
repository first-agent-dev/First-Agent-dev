"""The AI-NATIVE-PLAN-V2 plan grammar and its admission rules (STEP9A).

The grammar is deliberately small and closed: invariants with a typed evidence
mode, optional scenarios, and per-slice contracts, acceptance selectors, kill
targets and step-exit checks. Parsing yields a typed graph; admission proves the
graph's cardinalities and rejections; selector resolution is a separate step
because it needs the actual pytest collection.

``NON_EXECUTABLE`` evidence is legal only through the operator-ratified typed
disposition (Q-V2-ACC-2 = B-narrow): a closed reason code, a bounded evidence
reference, an owning lane, and a capped count. There is no free-text exception.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

__all__ = [
    "CONTRACT_CLASSES",
    "DISPOSITION_OWNERS",
    "DISPOSITION_REASONS",
    "MAX_DISPOSITIONS",
    "MAX_PLAN_BYTES",
    "PLAN_FORMAT",
    "Acceptance",
    "Contract",
    "ExitCheck",
    "Invariant",
    "KillTarget",
    "PlanGraph",
    "PlanV2Error",
    "Scenario",
    "SlicePlan",
    "Step",
    "parse_plan",
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
MAX_DISPOSITIONS = 16
CONTRACT_CLASSES = frozenset({"FUNCTIONAL", "CONSTRAINT", "PRESERVATION"})
_EVIDENCE_MODES = frozenset({"TEST_REQUIRED", "NON_EXECUTABLE"})
_STEP_MODES = frozenset({"prescriptive", "outcome"})

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
    kind: str
    text: str
    evidence: str
    reason: str | None = None
    evidence_ref: str | None = None
    owner: str | None = None


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
    kind = _field(entry.body, "KIND", rule=f"invariant-{inv_id}-kind")
    if kind not in {"HARD", "SOFT"}:
        raise PlanV2Error(f"invariant-{inv_id}-kind")
    text = _field(entry.body, "TEXT", rule=f"invariant-{inv_id}-text")
    evidence = _field(entry.body, "EVIDENCE", rule=f"invariant-{inv_id}-evidence")
    if evidence not in _EVIDENCE_MODES:
        raise PlanV2Error(f"invariant-{inv_id}-evidence")
    if evidence == "TEST_REQUIRED":
        if any(line.strip().startswith("DISPOSITION-") for line in entry.body):
            raise PlanV2Error("disposition-without-non-executable")
        return Invariant(id=inv_id, kind=kind, text=text, evidence=evidence)
    reason = _field(entry.body, "DISPOSITION-REASON", rule=f"invariant-{inv_id}-disposition-reason")
    evidence_ref = _field(entry.body, "DISPOSITION-EVIDENCE", rule=f"invariant-{inv_id}-disposition-evidence")
    owner = _field(entry.body, "DISPOSITION-OWNER", rule=f"invariant-{inv_id}-disposition-owner")
    if reason not in DISPOSITION_REASONS:
        raise PlanV2Error("disposition-reason-unratified")
    if owner not in DISPOSITION_OWNERS:
        raise PlanV2Error("disposition-owner-invalid")
    if len(evidence_ref) > 256:
        raise PlanV2Error(f"invariant-{inv_id}-disposition-evidence")
    return Invariant(
        id=inv_id,
        kind=kind,
        text=text,
        evidence=evidence,
        reason=reason,
        evidence_ref=evidence_ref,
        owner=owner,
    )


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
        if _SELECTOR_RE.match(fields["SELECTOR"]) is None:
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
    invariants = {item.id: item for item in graph.invariants}
    for contract in contracts.values():
        invariant = invariants[contract.inv]
        if invariant.kind != "HARD":
            continue
        if any(entry.ct == contract.id for entry in tests.values()):
            continue
        if invariant.evidence == "NON_EXECUTABLE" and invariant.reason and invariant.evidence_ref and invariant.owner:
            continue
        raise PlanV2Error("hard-contract-without-executable-evidence")


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
