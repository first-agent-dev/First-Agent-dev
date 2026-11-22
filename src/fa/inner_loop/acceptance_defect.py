"""The ``TEST-DEFECT`` lifecycle (STEP9A item 2).

A coder who believes a sealed acceptance test is wrong may not edit it. The only
supported path is a report against the seal, and a planner decision against the
pinned invariant:

* ``UPHELD`` — the tests stay byte-identical and the planner records why no test
  change is warranted. Nothing is re-sealed, so nothing re-runs.
* ``CORRECTED`` — the planner supplies a **new** seal that supersedes the old
  one. The old seal and its evidence stay on disk and stay loadable; the new seal
  has a different digest and therefore different evidence. A "correction" that
  leaves the acceptance bytes untouched is refused, and so is one that changes the
  plan bytes: changing the invariant or the expected semantics is owner/replan
  work, not a silent test correction.

Both branches hand the work back to the coder; neither rewrites sealed bytes in
place. Affected kill gates are re-derived from the graph so the caller knows what
must be re-proven against the new revision.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .acceptance_bundle import (
    AcceptanceBundle,
    AcceptanceBundleError,
    PinnedIdentity,
    mint_seal,
    write_seal,
)
from .plan_v2 import PlanGraph

__all__ = [
    "DECISION_KINDS",
    "MAX_REPORT_TEXT",
    "DefectDecision",
    "DefectError",
    "DefectReport",
    "affected_scope",
    "correct",
    "report_defect",
    "seal_path",
    "uphold",
    "write_revision_seal",
]

#: The two decisions a planner may record. Anything else is a replan, not a decision.
DECISION_KINDS = frozenset({"UPHELD", "CORRECTED"})
#: A report is a short factual claim (which assertion, against which invariant),
#: not an essay: the same 2 KiB bound the reasoner already reads per line.
MAX_REPORT_TEXT = 2048

_SLUG_RE = re.compile(r"\Aworklogs/(?P<slug>[a-z0-9][a-z0-9._-]*)/acceptance\Z")
_SEAL_NAME_RE = re.compile(r"\A[0-9a-f]{64}\Z")


class DefectError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid test-defect handling: {rule}")


@dataclass(frozen=True, slots=True)
class DefectReport:
    """A coder's claim, pinned to one seal, one revision and one exact nodeid."""

    seal_sha256: str
    revision_id: str
    test_id: str
    nodeid: str
    assertion: str
    invariant_id: str


@dataclass(frozen=True, slots=True)
class DefectDecision:
    """The planner's answer, plus what it obliges the coder to re-prove."""

    report: DefectReport
    kind: str
    rationale: str
    replacement: AcceptanceBundle | None
    affected_tests: tuple[str, ...]
    affected_kill_targets: tuple[str, ...]


def _text(value: object, rule: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_REPORT_TEXT or "\x00" in value:
        raise DefectError(rule)
    return value


def _contract_of(graph: PlanGraph, test_id: str) -> str:
    acceptance = graph.acceptance()
    if test_id not in acceptance:
        raise DefectError("defect-unknown-test")
    return acceptance[test_id].ct


def report_defect(
    bundle: AcceptanceBundle,
    graph: PlanGraph,
    *,
    test_id: str,
    nodeid: str,
    assertion: str,
    invariant_id: str,
) -> DefectReport:
    """Validate a coder's claim against the seal and the admitted plan.

    A claim that names a test the seal does not hold, a nodeid that is not the one
    the seal resolved, or an invariant that does not own the contract the test
    belongs to is not a test defect — it is a stale or invented claim, and it is
    refused instead of being forwarded to the planner.
    """
    if not isinstance(bundle, AcceptanceBundle) or not isinstance(graph, PlanGraph):
        raise DefectError("defect-input-invalid")
    sealed = bundle.nodeids()
    contract = _contract_of(graph, test_id)
    if test_id not in sealed:
        raise DefectError("defect-test-not-sealed")
    if nodeid != sealed[test_id]:
        raise DefectError("defect-nodeid-mismatch")
    invariant = graph.contracts()[contract].inv
    if invariant_id != invariant:
        raise DefectError("defect-invariant-mismatch")
    return DefectReport(
        seal_sha256=bundle.seal_sha256,
        revision_id=bundle.revision_id,
        test_id=test_id,
        nodeid=nodeid,
        assertion=_text(assertion, "defect-text-invalid"),
        invariant_id=invariant_id,
    )


def _same_contract_tests(graph: PlanGraph, test_id: str) -> tuple[str, ...]:
    contract = graph.acceptance()[test_id].ct
    return tuple(sorted(entry.test_id for entry in graph.acceptance().values() if entry.ct == contract))


def affected_scope(graph: PlanGraph, test_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What a correction to ``test_id`` obliges to be re-proven.

    A contract's other tests can encode the same expectation, and a kill target's
    oracle is the test it was bound to, so the affected set is the contract's
    tests plus every kill target bound to any of them. Targets bound to other
    contracts are untouched: their oracle bytes did not change meaning.
    """
    if not isinstance(graph, PlanGraph) or test_id not in graph.acceptance():
        raise DefectError("defect-unknown-test")
    tests = _same_contract_tests(graph, test_id)
    bound = tuple(
        sorted(
            target.target_id for planned in graph.slices for target in planned.kill_targets if target.test_id in tests
        )
    )
    return tests, bound


def uphold(report: DefectReport, *, rationale: str) -> DefectDecision:
    """The tests stay byte-identical. Nothing is re-sealed and nothing re-runs."""
    if not isinstance(report, DefectReport):
        raise DefectError("decision-report-invalid")
    text = _text(rationale, "decision-rationale-invalid")
    return DefectDecision(
        report=report,
        kind="UPHELD",
        rationale=text,
        replacement=None,
        affected_tests=(),
        affected_kill_targets=(),
    )


def _slug(bundle: AcceptanceBundle) -> str:
    match = _SLUG_RE.match(bundle.sealed_root)
    if match is None:
        raise DefectError("defect-sealed-root-invalid")
    return match.group("slug")


def seal_path(bundle: AcceptanceBundle) -> str:
    """The content-addressed, repo-relative location of one revision's seal."""
    if not isinstance(bundle, AcceptanceBundle) or not _SEAL_NAME_RE.match(bundle.seal_sha256):
        raise DefectError("defect-seal-invalid")
    return f"worklogs/{_slug(bundle)}/seals/{bundle.seal_sha256}.json"


def write_revision_seal(bundle: AcceptanceBundle, worklogs: Path) -> Path:
    """Store one revision's seal beside its predecessors; never replace one.

    Content addressing is the retention mechanism: the revision that was sealed
    first keeps its own file and therefore its own evidence, and a new revision
    cannot overwrite it because its digest — and so its name — differs.
    """
    if not isinstance(worklogs, Path):
        raise DefectError("defect-seal-path-invalid")
    path = Path(worklogs) / _slug(bundle) / "seals" / f"{bundle.seal_sha256}.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise DefectError("defect-seal-path-invalid") from None
    try:
        return write_seal(bundle, path)
    except AcceptanceBundleError as error:
        raise DefectError(f"defect-{error.rule}") from None


def correct(
    report: DefectReport,
    *,
    rationale: str,
    bundle_before: AcceptanceBundle,
    graph: PlanGraph,
    plan_bytes: bytes,
    revision_id: str,
    acceptance_root: Path,
    collected: Mapping[str, Iterable[str]],
    identity: Sequence[PinnedIdentity] = (),
) -> DefectDecision:
    """Record a corrected revision: a new seal that supersedes the reported one.

    Three refusals keep this a *test* correction: the plan bytes must be the ones
    the report was made against (else it is owner/replan work), the new revision
    must actually differ from the sealed one (one revision, one closure), and the
    acceptance bytes must actually change (a re-seal over identical bytes is not a
    correction and would only manufacture a new digest).
    """
    if not isinstance(report, DefectReport) or not isinstance(bundle_before, AcceptanceBundle):
        raise DefectError("decision-report-invalid")
    text = _text(rationale, "decision-rationale-invalid")
    if report.seal_sha256 != bundle_before.seal_sha256:
        raise DefectError("defect-seal-superseded")
    if hashlib.sha256(plan_bytes).hexdigest() != bundle_before.plan_sha256:
        raise DefectError("defect-requires-replan")
    if revision_id == bundle_before.revision_id:
        raise DefectError("defect-revision-unchanged")
    try:
        replacement = mint_seal(
            graph=graph,
            plan_bytes=plan_bytes,
            revision_id=revision_id,
            sealed_root=bundle_before.sealed_root,
            acceptance_root=acceptance_root,
            collected=collected,
            mode=bundle_before.mode,
            identity=tuple(identity),
            supersedes_sha256=bundle_before.seal_sha256,
        )
    except AcceptanceBundleError as error:
        # One closed vocabulary per module: a seal refusal reached through the
        # correction route is still a defect decision, not a raw bundle error.
        raise DefectError(f"defect-{error.rule}") from None
    if replacement.closure.digest == bundle_before.closure.digest:
        raise DefectError("defect-no-change")
    tests, targets = affected_scope(graph, report.test_id)
    return DefectDecision(
        report=report,
        kind="CORRECTED",
        rationale=text,
        replacement=replacement,
        affected_tests=tests,
        affected_kill_targets=targets,
    )
