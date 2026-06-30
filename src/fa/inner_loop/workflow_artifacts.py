"""Workflow-side structured artifacts for planner/coder/eval orchestration.

These artifacts intentionally split narrative and controller truth:

- ``pr_draft.md`` remains the human-readable session narrative.
- ``eval_report.json`` is the machine-readable evaluator verdict and route.
- ``flow_state.json`` is the machine-readable workflow controller state.

This module does NOT yet orchestrate the full adaptive workflow. It only
establishes the durable artifact contracts and atomic persistence needed
for later phases of the workflow implementation plan.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

__all__ = [
    "EvalFinding",
    "EvalReport",
    "EvalVerdict",
    "FindingClass",
    "FindingRoute",
    "FindingSeverity",
    "FlowState",
    "FlowStatus",
    "RouteDecision",
    "StepResult",
    "StepVerdict",
    "default_route_for_verdict",
    "load_eval_report",
    "load_flow_state",
    "parse_eval_report",
    "write_eval_report",
    "write_flow_state",
]

FindingSeverity = Literal["critical", "major", "minor", "info"]
FindingClass = Literal["implementation", "plan", "environment", "scope", "regression"]
FindingRoute = Literal["coder", "planner", "human"]
EvalVerdict = Literal["PASS", "REPAIR_REQUIRED", "REPLAN_REQUIRED", "BLOCKED"]
RouteDecision = Literal["complete", "return_to_coder", "return_to_planner", "blocked"]
StepVerdict = Literal["pass", "fail", "partial", "not_evaluated"]
FlowStatus = Literal[
    "INIT",
    "PLANNING",
    "PLAN_READY",
    "CODING",
    "CODER_BLOCKED",
    "EVALUATING",
    "REPAIR_REQUIRED",
    "REPLAN_REQUIRED",
    "DELTA_PLANNING",
    "DONE",
    "FAILED",
]


_FINDING_SEVERITIES: frozenset[str] = frozenset(("critical", "major", "minor", "info"))
_FINDING_CLASSES: frozenset[str] = frozenset(
    ("implementation", "plan", "environment", "scope", "regression")
)
_FINDING_ROUTES: frozenset[str] = frozenset(("coder", "planner", "human"))
_EVAL_VERDICTS: frozenset[str] = frozenset(
    ("PASS", "REPAIR_REQUIRED", "REPLAN_REQUIRED", "BLOCKED")
)
_ROUTE_DECISIONS: frozenset[str] = frozenset(
    ("complete", "return_to_coder", "return_to_planner", "blocked")
)
_STEP_VERDICTS: frozenset[str] = frozenset(("pass", "fail", "partial", "not_evaluated"))
_FLOW_STATUSES: frozenset[str] = frozenset(
    (
        "INIT",
        "PLANNING",
        "PLAN_READY",
        "CODING",
        "CODER_BLOCKED",
        "EVALUATING",
        "REPAIR_REQUIRED",
        "REPLAN_REQUIRED",
        "DELTA_PLANNING",
        "DONE",
        "FAILED",
    )
)


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {type(value).__name__}")
    return value


def _as_int(value: object) -> int:
    # JSON booleans are ints in Python; reject them so verdict-version-style
    # fields cannot be silently coerced from `true`/`false`.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"expected an integer, got {type(value).__name__}")
    return value


def _as_literal(value: object, allowed: frozenset[str], field_name: str) -> str:
    text = _as_str(value)
    if text not in allowed:
        raise ValueError(f"{field_name}={text!r} is not one of {sorted(allowed)}")
    return text


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"expected a list of strings, got {type(value).__name__}")
    return tuple(_as_str(item) for item in value)


def _as_dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"expected a list of objects, got {type(value).__name__}")
    result: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"expected an object, got {type(item).__name__}")
        result.append(item)
    return result


@dataclass(frozen=True)
class StepResult:
    step_id: str
    verdict: StepVerdict
    acceptance_matched: bool
    evidence: str
    notes: str = ""

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> StepResult:
        return cls(
            step_id=_as_str(data["step_id"]),
            verdict=_as_literal(data["verdict"], _STEP_VERDICTS, "verdict"),  # type: ignore[arg-type]
            acceptance_matched=bool(data["acceptance_matched"]),
            evidence=_as_str(data["evidence"]),
            notes=_as_str(data.get("notes", "")),
        )


@dataclass(frozen=True)
class EvalFinding:
    finding_id: str
    severity: FindingSeverity
    finding_class: FindingClass
    blocking: bool
    route: FindingRoute
    claim: str
    evidence: str
    expected: str
    actual: str
    required_action: str
    step_id: str | None = None
    location: str = ""
    suggested_check: str = ""

    def to_json_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["class"] = data.pop("finding_class")
        return data

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> EvalFinding:
        step_id = data.get("step_id")
        return cls(
            finding_id=_as_str(data["finding_id"]),
            severity=_as_literal(data["severity"], _FINDING_SEVERITIES, "severity"),  # type: ignore[arg-type]
            finding_class=_as_literal(data["class"], _FINDING_CLASSES, "class"),  # type: ignore[arg-type]
            blocking=bool(data["blocking"]),
            route=_as_literal(data["route"], _FINDING_ROUTES, "route"),  # type: ignore[arg-type]
            claim=_as_str(data["claim"]),
            evidence=_as_str(data["evidence"]),
            expected=_as_str(data["expected"]),
            actual=_as_str(data["actual"]),
            required_action=_as_str(data["required_action"]),
            step_id=None if step_id is None else _as_str(step_id),
            location=_as_str(data.get("location", "")),
            suggested_check=_as_str(data.get("suggested_check", "")),
        )


@dataclass(frozen=True)
class EvalReport:
    run_id: str
    plan_id: str
    plan_version: int
    evaluation_id: str
    verdict: EvalVerdict
    route_decision: RouteDecision
    summary: str
    step_results: tuple[StepResult, ...] = ()
    findings: tuple[EvalFinding, ...] = ()
    integration_checks: tuple[str, ...] = ()
    regression_checks: tuple[str, ...] = ()
    confidence: str = ""

    def to_json_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "evaluation_id": self.evaluation_id,
            "verdict": self.verdict,
            "route_decision": self.route_decision,
            "summary": self.summary,
            "step_results": [asdict(step) for step in self.step_results],
            "findings": [item.to_json_dict() for item in self.findings],
            "integration_checks": list(self.integration_checks),
            "regression_checks": list(self.regression_checks),
            "confidence": self.confidence,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> EvalReport:
        return cls(
            run_id=_as_str(data["run_id"]),
            plan_id=_as_str(data["plan_id"]),
            plan_version=_as_int(data["plan_version"]),
            evaluation_id=_as_str(data["evaluation_id"]),
            verdict=_as_literal(data["verdict"], _EVAL_VERDICTS, "verdict"),  # type: ignore[arg-type]
            route_decision=_as_literal(  # type: ignore[arg-type]
                data["route_decision"], _ROUTE_DECISIONS, "route_decision"
            ),
            summary=_as_str(data["summary"]),
            step_results=tuple(
                StepResult.from_json_dict(item)
                for item in _as_dict_list(data.get("step_results", []))
            ),
            findings=tuple(
                EvalFinding.from_json_dict(item) for item in _as_dict_list(data.get("findings", []))
            ),
            integration_checks=_as_str_tuple(data.get("integration_checks", [])),
            regression_checks=_as_str_tuple(data.get("regression_checks", [])),
            confidence=_as_str(data.get("confidence", "")),
        )


@dataclass(frozen=True)
class FlowState:
    run_id: str
    task: str
    status: FlowStatus
    active_role: str
    active_plan_id: str
    active_plan_version: int
    repair_round: int = 0
    replan_round: int = 0
    last_actor: str = ""
    last_transition_reason: str = ""
    last_route_decision: str = ""
    blocked_reason: str = ""
    completed_steps: tuple[str, ...] = field(default_factory=tuple)
    invalidated_steps: tuple[str, ...] = field(default_factory=tuple)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "task": self.task,
            "status": self.status,
            "active_role": self.active_role,
            "active_plan_id": self.active_plan_id,
            "active_plan_version": self.active_plan_version,
            "repair_round": self.repair_round,
            "replan_round": self.replan_round,
            "last_actor": self.last_actor,
            "last_transition_reason": self.last_transition_reason,
            "last_route_decision": self.last_route_decision,
            "blocked_reason": self.blocked_reason,
            "completed_steps": list(self.completed_steps),
            "invalidated_steps": list(self.invalidated_steps),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> FlowState:
        return cls(
            run_id=_as_str(data["run_id"]),
            task=_as_str(data["task"]),
            status=_as_literal(data["status"], _FLOW_STATUSES, "status"),  # type: ignore[arg-type]
            active_role=_as_str(data["active_role"]),
            active_plan_id=_as_str(data["active_plan_id"]),
            active_plan_version=_as_int(data["active_plan_version"]),
            repair_round=_as_int(data.get("repair_round", 0)),
            replan_round=_as_int(data.get("replan_round", 0)),
            last_actor=_as_str(data.get("last_actor", "")),
            last_transition_reason=_as_str(data.get("last_transition_reason", "")),
            last_route_decision=_as_str(data.get("last_route_decision", "")),
            blocked_reason=_as_str(data.get("blocked_reason", "")),
            completed_steps=_as_str_tuple(data.get("completed_steps", [])),
            invalidated_steps=_as_str_tuple(data.get("invalidated_steps", [])),
        )


# ── Deterministic eval-output parsing (step-as-function) ────────────────────
#
# The evaluator role emits a deterministic ``## Verification Summary`` block
# (see ``EVAL_SYSTEM_PROMPT`` §"Final output contract"). The workflow
# controller must read controller truth (verdict + route) from a machine
# artifact, not by re-parsing prose at every decision point. This parser is the
# single translation seam from narrative eval output to the ``EvalReport``
# artifact. It is intentionally fail-closed: unrecognized output yields a
# ``BLOCKED`` / ``blocked`` report so the controller never mistakes malformed
# output for a passing run.

_VERDICT_TO_ROUTE: dict[EvalVerdict, RouteDecision] = {
    "PASS": "complete",
    "REPAIR_REQUIRED": "return_to_coder",
    "REPLAN_REQUIRED": "return_to_planner",
    "BLOCKED": "blocked",
}

_VALID_VERDICTS: frozenset[str] = frozenset(_VERDICT_TO_ROUTE)
_VALID_ROUTES: frozenset[str] = frozenset(_VERDICT_TO_ROUTE.values())

# Per-step verdict tokens emitted under "### Step results" (e.g. "S1: PASS — ...").
_STEP_VERDICT_TOKENS: dict[str, StepVerdict] = {
    "PASS": "pass",
    "FAIL": "fail",
    "PARTIAL": "partial",
}

_VERDICT_LINE_RE = re.compile(
    r"^\s*(?:###\s*Verdict\b.*|verdict\s*[:=])?\s*"
    r"(PASS|REPAIR_REQUIRED|REPLAN_REQUIRED|BLOCKED)\b",
    re.IGNORECASE,
)
_ROUTE_LINE_RE = re.compile(
    r"^\s*(?:###\s*Route\s*decision\b.*|route(?:_decision)?\s*[:=])?\s*"
    r"(complete|return_to_coder|return_to_planner|blocked)\b",
    re.IGNORECASE,
)
_STEP_LINE_RE = re.compile(
    r"^\s*[-*]\s*(S\d+[A-Za-z0-9_.-]*)\s*[:\-—]\s*(PASS|FAIL|PARTIAL)\b\s*[-—:]?\s*(.*)$",
    re.IGNORECASE,
)


def default_route_for_verdict(verdict: EvalVerdict) -> RouteDecision:
    """Return the documented default route decision for a verdict."""
    return _VERDICT_TO_ROUTE[verdict]


def _scan_verdict(text: str) -> EvalVerdict | None:
    """Find the verdict the evaluator committed to.

    Prefers the explicit ``### Verdict`` section; falls back to the last
    standalone verdict token elsewhere in the output. Returns ``None`` if no
    valid verdict token is present.
    """
    lines = text.splitlines()
    # Pass 1: token on the line(s) following a "### Verdict" header.
    for index, line in enumerate(lines):
        if re.match(r"^\s*###\s*Verdict\b", line, re.IGNORECASE):
            for candidate in [line, *lines[index + 1 : index + 4]]:
                token = _match_verdict_token(candidate)
                if token is not None:
                    return token
    # Pass 2: last bare verdict token anywhere (deterministic: last wins).
    found: EvalVerdict | None = None
    for line in lines:
        token = _match_verdict_token(line)
        if token is not None:
            found = token
    return found


def _match_verdict_token(line: str) -> EvalVerdict | None:
    match = _VERDICT_LINE_RE.match(line)
    if match is None:
        return None
    upper = match.group(1).upper()
    return upper if upper in _VALID_VERDICTS else None  # type: ignore[return-value]


def _scan_route(text: str) -> RouteDecision | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.match(r"^\s*###\s*Route\s*decision\b", line, re.IGNORECASE):
            for candidate in [line, *lines[index + 1 : index + 4]]:
                token = _match_route_token(candidate)
                if token is not None:
                    return token
    found: RouteDecision | None = None
    for line in lines:
        token = _match_route_token(line)
        if token is not None:
            found = token
    return found


def _match_route_token(line: str) -> RouteDecision | None:
    match = _ROUTE_LINE_RE.match(line)
    if match is None:
        return None
    lower = match.group(1).lower()
    return lower if lower in _VALID_ROUTES else None  # type: ignore[return-value]


def _scan_step_results(text: str) -> tuple[StepResult, ...]:
    results: list[StepResult] = []
    seen: set[str] = set()
    for line in text.splitlines():
        match = _STEP_LINE_RE.match(line)
        if match is None:
            continue
        step_id = match.group(1)
        if step_id in seen:
            continue
        seen.add(step_id)
        verdict = _STEP_VERDICT_TOKENS[match.group(2).upper()]
        evidence = match.group(3).strip()
        results.append(
            StepResult(
                step_id=step_id,
                verdict=verdict,
                acceptance_matched=verdict == "pass",
                evidence=evidence,
            )
        )
    return tuple(results)


def parse_eval_report(
    final_text: str,
    *,
    run_id: str,
    plan_id: str,
    evaluation_id: str,
    plan_version: int = 1,
) -> EvalReport:
    """Translate the evaluator's final message into an :class:`EvalReport`.

    Reads the deterministic ``## Verification Summary`` contract emitted by the
    eval role. The verdict drives the route decision; an explicit, consistent
    ``### Route decision`` token is honored, but a route that contradicts the
    verdict is overridden by the verdict-derived default (the verdict is the
    primary judgement, the route is its routing consequence).

    Fail-closed: if no valid verdict token is found, returns a ``BLOCKED`` /
    ``blocked`` report whose summary records that the eval output was
    unparseable, so the controller never treats malformed output as success.
    """
    text = final_text or ""
    verdict = _scan_verdict(text)
    step_results = _scan_step_results(text)

    if verdict is None:
        return EvalReport(
            run_id=run_id,
            plan_id=plan_id,
            plan_version=plan_version,
            evaluation_id=evaluation_id,
            verdict="BLOCKED",
            route_decision="blocked",
            summary="eval output did not contain a recognizable verdict token",
            step_results=step_results,
            confidence="parsed:none",
        )

    default_route = default_route_for_verdict(verdict)
    parsed_route = _scan_route(text)
    route: RouteDecision
    if parsed_route is not None and parsed_route == default_route:
        route = parsed_route
    else:
        route = default_route

    return EvalReport(
        run_id=run_id,
        plan_id=plan_id,
        plan_version=plan_version,
        evaluation_id=evaluation_id,
        verdict=verdict,
        route_decision=route,
        summary=_first_summary_line(text, verdict),
        step_results=step_results,
        confidence="parsed:contract" if parsed_route is not None else "parsed:verdict",
    )


def _first_summary_line(text: str, verdict: EvalVerdict) -> str:
    """Derive a one-line summary from the eval output for the artifact.

    Prefers an explicit prose ``summary:`` line if the evaluator wrote one;
    otherwise falls back to a compact verdict-anchored sentence. List items
    (``- ...`` / ``* ...``) belong to structured sections (step results,
    findings) and are deliberately not used as the summary.
    """
    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"^summary\s*[:=]\s*(.+)$", stripped, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:280]
    return f"verdict {verdict}"


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        raise


def write_eval_report(path: Path, report: EvalReport) -> None:
    _write_json_atomic(path, report.to_json_dict())


def load_eval_report(path: Path) -> EvalReport:
    return EvalReport.from_json_dict(json.loads(path.read_text(encoding="utf-8")))


def write_flow_state(path: Path, state: FlowState) -> None:
    _write_json_atomic(path, state.to_json_dict())


def load_flow_state(path: Path) -> FlowState:
    return FlowState.from_json_dict(json.loads(path.read_text(encoding="utf-8")))
