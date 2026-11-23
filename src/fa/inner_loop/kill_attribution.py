"""Exact kill attribution over sealed nodeids (STEP9A item 3).

The slice-scoped gate asks "did anything fail after I removed the producer". That
question is not attribution: a failure anywhere in a test file, a broken import, a
skipped test or an empty run all look like "killed". This module answers the
narrower question the V2 schema promises: *this* kill target, mapped to *this*
contract and *this* stable `TEST-ID`, resolved to *one* nodeid in the sealed
revision, failed by assertion when — and only when — its producer was mutated.

The rules, in the order they are applied:

* The target must be bound: the contract in the plan must own the `TEST-ID`, that
  `TEST-ID` must be sealed, and the sealed nodeid must be the one this target
  names. An unmapped or contradictory target is never run.
* The baseline run happens on the **current unmutated** implementation, right
  before the mutation, and it must pass. T0 is not a valid baseline: a new
  behaviour may correctly be red there.
* The oracle run executes exactly one nodeid with the sealed configuration
  (``-c``/``--rootdir``/``no:cacheprovider``), and its report must contain exactly
  that one nodeid. Anything else is ``ERROR``, never a kill.
* ``FAILED`` on that nodeid under the mutation is ``SliceVerdict.PROVEN``. ``PASSED``
  is ``VACUOUS``. Collection/setup/skip/timeout/crash/report error or zero executed
  tests is ``ERROR``. Verdicts are :class:`SliceVerdict` members, not a second
  uppercase vocabulary (Q-V2-SLICE3-3): one axis, one spelling.
* Unassigned failures cannot prove anything because nothing unassigned is run
  here; a caller that also runs a wider suite must keep those results separate.

Two rules make the *record* honest rather than only the producer: ``kill-run-invalid`` (a run
whose outcome is not one of :class:`NodeOutcome`) and ``kill-attribution-invalid`` (a verdict
outside :data:`ATTRIBUTION_VERDICTS`, or a non-``PROVEN`` verdict with no detail). Before them,
``ATTRIBUTION_VERDICTS`` was exported and read by nothing, so a hand-built record could name any
string -- F1's shape, one entity over.

The mutation itself is not applied here: the existing ``mutation_overlay`` owns the
only mutated copy on disk, and ``apply_kill`` stays the only thing that rewrites
source. This module consumes the two runs and the sealed evidence.
"""

from __future__ import annotations

import enum
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .acceptance_bundle import AcceptanceBundle, verify_sealed_root
from .acceptance_closure import pytest_argv, shell_command
from .plan_v2 import KillTarget, PlanGraph
from .slice_verification import (
    CommandOutcome,
    SliceVerdict,
    VerifyCommandExecutor,
    parse_node_outcomes,
    run_commands,
)

__all__ = [
    "ATTRIBUTION_VERDICTS",
    "NODE_OUTCOMES",
    "KillAttribution",
    "KillAttributionError",
    "KillTargetBinding",
    "NodeOutcome",
    "NodeRun",
    "attribute",
    "bindings",
    "oracle_argv",
    "run_node_oracle",
]


class NodeOutcome(enum.StrEnum):
    """What one oracle run did to the one nodeid it was allowed to run.

    A *run outcome* and a *claim verdict* are different axes, and they stay different: a run
    can be ``MISSING``, which no verdict counterpart exists for, and a verdict can be
    ``VACUOUS``, which describes a comparison rather than one run. What must not exist is two
    spellings of the *same* axis -- which is what Q-V2-SLICE3-3 removed: the verdict is
    :class:`SliceVerdict`'s own, not a second uppercase vocabulary beside it.
    """

    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    MISSING = "MISSING"
    ERROR = "ERROR"


#: Derived, never restated: two literals for one axis is how the vocabularies drifted (F1).
NODE_OUTCOMES: Final = frozenset(NodeOutcome)

#: What a kill target may be declared. The members are :class:`SliceVerdict`'s own objects, so an
#: attribution verdict can be handed to ``MutationEvidence`` without a spelling translation, and a
#: reader compares it to the same ``proven`` the gate uses. ``PRODUCER_ABSENT`` stays out: the
#: pre-existing slice gate owns that outcome, and folding it in here would claim a kill this
#: module never measured.
ATTRIBUTION_VERDICTS: Final = frozenset({SliceVerdict.PROVEN, SliceVerdict.VACUOUS, SliceVerdict.ERROR})


class KillAttributionError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid kill attribution: {rule}")


@dataclass(frozen=True, slots=True)
class KillTargetBinding:
    """One kill target tied to its contract, test, and sealed evidence."""

    target_id: str
    contract_id: str
    test_id: str
    nodeid: str
    test_sha256: str
    seal_sha256: str
    revision_id: str
    closure_sha256: str


@dataclass(frozen=True, slots=True)
class NodeRun:
    """The outcome of running one nodeid, with the command that produced it."""

    outcome: NodeOutcome
    command: str
    exit_code: int | None
    detail: str = ""

    def __post_init__(self) -> None:
        """A run whose outcome is not one of the five is a programming error, not data.

        Strict, not coercing: ``"PASSED"`` arriving as a bare string is a typing bug at the call
        site, and silently converting it would paper over the next one.
        """
        if not isinstance(self.outcome, NodeOutcome):
            raise KillAttributionError("kill-run-invalid")


@dataclass(frozen=True, slots=True)
class KillAttribution:
    """The recorded verdict for one target, with both runs as evidence."""

    binding: KillTargetBinding
    verdict: SliceVerdict
    detail: str
    baseline: NodeRun
    mutated: NodeRun

    def __post_init__(self) -> None:
        """Refuse a record the gate could not read: F1's shape, closed at the entity.

        ``ATTRIBUTION_VERDICTS`` was exported and read by nothing, so a hand-built attribution
        could name any string and a future writer would store it verbatim. The set is now the
        rule it always claimed to be, and a non-``PROVEN`` verdict must say what to look at --
        the same rule ``KillCheck`` already enforces, for the same reason.
        """
        if not isinstance(self.binding, KillTargetBinding):
            raise KillAttributionError("kill-binding-invalid")
        if not isinstance(self.verdict, SliceVerdict) or self.verdict not in ATTRIBUTION_VERDICTS:
            raise KillAttributionError("kill-attribution-invalid")
        if self.verdict is not SliceVerdict.PROVEN and not self.detail:
            raise KillAttributionError("kill-attribution-invalid")
        for run in (self.baseline, self.mutated):
            if not isinstance(run, NodeRun):
                raise KillAttributionError("kill-run-invalid")


def _sealed_test_digest(bundle: AcceptanceBundle, nodeid: str) -> str:
    path = nodeid.partition("::")[0]
    relative = f"{bundle.sealed_root}/"
    if not path.startswith(relative):
        raise KillAttributionError("kill-target-unsealed")
    entry = next((item for item in bundle.closure.files if item.path == path[len(relative) :]), None)
    if entry is None:
        raise KillAttributionError("kill-target-unsealed")
    return entry.sha256


def _binding(bundle: AcceptanceBundle, target: KillTarget) -> KillTargetBinding:
    """Bind one target, trusting only what plan admission cannot guarantee.

    Admission already proves the target's contract exists in its slice and owns
    the `TEST-ID` (`dangling-kill-target`, `kill-target-attribution-mismatch`), so
    re-checking that here would be dead code. What admission cannot know is which
    tests the *seal* selected.
    """
    sealed = bundle.nodeids()
    if target.test_id not in sealed:
        raise KillAttributionError("kill-target-unsealed")
    nodeid = sealed[target.test_id]
    return KillTargetBinding(
        target_id=target.target_id,
        contract_id=target.ct,
        test_id=target.test_id,
        nodeid=nodeid,
        test_sha256=_sealed_test_digest(bundle, nodeid),
        seal_sha256=bundle.seal_sha256,
        revision_id=bundle.revision_id,
        closure_sha256=bundle.closure.digest,
    )


def bindings(bundle: AcceptanceBundle, graph: PlanGraph) -> tuple[KillTargetBinding, ...]:
    """Every declared kill target, bound and evidence-stamped, in plan order."""
    if not isinstance(bundle, AcceptanceBundle) or not isinstance(graph, PlanGraph):
        raise KillAttributionError("kill-input-invalid")
    # Target ids are already unique per plan (`duplicate-kill-target-id`).
    return tuple(_binding(bundle, target) for planned in graph.slices for target in planned.kill_targets)


def oracle_argv(bundle: AcceptanceBundle, binding: KillTargetBinding, *, report: str) -> tuple[str, ...]:
    """The exact oracle invocation: one nodeid, sealed config, sealed root."""
    if not isinstance(binding, KillTargetBinding):
        raise KillAttributionError("kill-binding-invalid")
    return pytest_argv(
        tests=(binding.nodeid,),
        ini=f"{bundle.sealed_root}/pytest.ini",
        rootdir=bundle.sealed_root,
        report=report,
    )


def _rootdir_nodeid(bundle: AcceptanceBundle, binding: KillTargetBinding) -> str:
    """The nodeid pytest will report: relative to ``--rootdir``, not the workspace."""
    prefix = f"{bundle.sealed_root}/"
    if not binding.nodeid.startswith(prefix):
        raise KillAttributionError("kill-target-unsealed")
    return binding.nodeid[len(prefix) :]


def _classify(expected: str, outcomes: Mapping[str, str]) -> tuple[NodeOutcome, str]:
    """A single reported row decides: pass, assertion failure, or nothing at all."""
    if len(outcomes) != 1 or expected not in outcomes:
        return NodeOutcome.ERROR, "oracle-report-not-exact"
    state = outcomes[expected]
    if state == "passed":
        return NodeOutcome.PASSED, ""
    if state == "failed":
        return NodeOutcome.FAILED, ""
    return NodeOutcome.SKIPPED, "oracle-skipped"


def run_node_oracle(
    bundle: AcceptanceBundle,
    binding: KillTargetBinding,
    *,
    workspace: Path,
    executor: VerifyCommandExecutor | None = None,
    deadline: float | None = None,
) -> NodeRun:
    """Run one kill target's oracle and classify what that single run did.

    A skipped or errored run is ``SKIPPED``/``ERROR``: pytest's own exit status is
    not evidence that an assertion failed, so it is never read as a kill.
    """
    if not isinstance(bundle, AcceptanceBundle) or not isinstance(binding, KillTargetBinding):
        raise KillAttributionError("kill-binding-invalid")
    # The oracle is the sealed bytes. A tree that drifted — including one where
    # the coder's overlay reached the acceptance directory — never runs.
    verify_sealed_root(bundle, Path(workspace) / bundle.sealed_root)
    with tempfile.TemporaryDirectory(prefix="fa-kill-oracle-") as directory:
        report = Path(directory) / "oracle.xml"
        argv = oracle_argv(bundle, binding, report=str(report))
        command = shell_command(argv)
        (result,) = run_commands((command,), workspace=Path(workspace), deadline=deadline, executor=executor)
        if result.outcome is CommandOutcome.ERROR:
            return NodeRun(
                outcome=NodeOutcome.ERROR, command=command, exit_code=result.exit_code, detail="oracle-run-errored"
            )
        try:
            raw = report.read_bytes()
        except OSError:
            return NodeRun(
                outcome=NodeOutcome.MISSING, command=command, exit_code=result.exit_code, detail="oracle-no-report"
            )
    outcomes, _detail = parse_node_outcomes(raw)
    if outcomes is None:
        return NodeRun(
            outcome=NodeOutcome.ERROR, command=command, exit_code=result.exit_code, detail="oracle-report-invalid"
        )
    outcome, detail = _classify(_rootdir_nodeid(bundle, binding), outcomes)
    return NodeRun(outcome=outcome, command=command, exit_code=result.exit_code, detail=detail)


def attribute(
    binding: KillTargetBinding,
    *,
    baseline: NodeRun,
    mutated: NodeRun,
) -> KillAttribution:
    """Decide the verdict from the two runs. Pure, and total.

    Every path that is not "the baseline passed and the same single nodeid failed
    by assertion afterwards" is ``ERROR``; the only other reachable verdict is
    ``VACUOUS``, when the oracle still passes with the producer removed.
    """
    if not isinstance(binding, KillTargetBinding):
        raise KillAttributionError("kill-binding-invalid")
    # The outcome is validated where it is written (``NodeRun``), so this only refuses a value
    # that is not a run at all -- one rule per fact instead of two copies of one rule.
    for run in (baseline, mutated):
        if not isinstance(run, NodeRun):
            raise KillAttributionError("kill-run-invalid")
    verdict, detail = _verdict(baseline, mutated)
    return KillAttribution(binding=binding, verdict=verdict, detail=detail, baseline=baseline, mutated=mutated)


def _verdict(baseline: NodeRun, mutated: NodeRun) -> tuple[SliceVerdict, str]:
    if baseline.outcome is not NodeOutcome.PASSED:
        return SliceVerdict.ERROR, f"baseline_{baseline.outcome.lower()}"
    if mutated.outcome is NodeOutcome.FAILED:
        return SliceVerdict.PROVEN, ""
    if mutated.outcome is NodeOutcome.PASSED:
        return SliceVerdict.VACUOUS, "the oracle still passes with the producer mutated"
    return SliceVerdict.ERROR, f"mutated_{mutated.outcome.lower()}"
