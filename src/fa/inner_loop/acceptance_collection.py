"""Sealed acceptance collection and the pinned verifier run (STEP9A item 1).

The seal says *what* the oracle is. This module is what makes the verifier
execute exactly that: it derives the test targets from the sealed closure (never
from the plan's free text or from the mutable tree), builds the harness argv
with ``-c``/``--rootdir``/``no:cacheprovider`` pinned to the sealed root, runs
it, and reads the nodeids with the same JUnit parser the rest of the gate uses.

Two properties are the whole point:

* **The nodeid report comes from the sealed bytes.** The only way to obtain one
  is :func:`collect_sealed_nodeids`, which refuses when the tree no longer
  matches the record — a collection run against the coder's mutable copy cannot
  be passed in. This is what turns the seal's "captured from a collection run
  against the sealed bytes" from a caller obligation into an enforced step.
* **The verifier runs the pinned digest.** :func:`run_sealed_acceptance` checks
  plan bytes and revision before running, and refuses if any sealed selector's
  nodeid did not execute.

Nodeids are reported by pytest relative to ``--rootdir`` (the sealed root), so
they are re-prefixed to workspace-relative form before anyone compares them with
the plan's selectors, which are workspace-relative.
"""

from __future__ import annotations

import shlex
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from .acceptance_bundle import (
    AcceptanceBundle,
    AcceptanceBundleError,
    require_revision_id,
    require_sealed_root,
    verify_plan,
    verify_revision,
    verify_sealed_root,
)
from .acceptance_closure import (
    AcceptanceClosure,
    AcceptanceClosureError,
    collect_acceptance_closure,
    pytest_argv,
    shell_command,
)
from .junit_properties import JUNIT_RUN_ID_ENV
from .plan_v2 import KillTarget
from .slice_verification import (
    CommandOutcome,
    CommandResult,
    VerifyCommandExecutor,
    _gate_subprocess_env,
    inband_junit_command,
    parse_inband_precode_outcomes,
    parse_nodeid_report,
    run_commands,
)
from .verification_attempt import (
    AttemptCommand,
    ClaimEvidence,
    VerificationAttempt,
    VerificationAttemptError,
    VerificationIdentity,
)

__all__ = [
    "AcceptanceCollectionError",
    "SealedCollection",
    "SealedRun",
    "SealedVerification",
    "collect_sealed_nodeids",
    "collect_sealed_nodeids_inband",
    "collect_sealed_tree",
    "run_sealed_acceptance",
    "sealed_attempt",
    "sealed_collection_argv",
    "sealed_collection_inband_command",
    "sealed_test_paths",
    "verify_sealed_acceptance",
]


class AcceptanceCollectionError(ValueError):
    """Closed diagnostic reason; never expose input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid sealed collection: {rule}")


#: The report basename inside the cell's own scratch. Only the name is chosen
#: here: the directory is ``$TMPDIR`` as the authority sets it, and a controller
#: path would be a guess (Q142 option A).
_INBAND_REPORT_NAME: Final = "sealed-collection.xml"

#: Paths a sealed closure may never live in or under. "Refuses a closure/code path
#: overlap" (CT-3.6): the closure is the oracle, the code roots are what the coder
#: edits, and if the two overlapped then "the sealed closure" and "the current
#: candidate revision" would name the same bytes -- a coder's edit would silently
#: become part of the oracle without a new seal.
_CODE_ROOTS: Final = frozenset({"src", "scripts", "tests"})

#: The one argv element whose value is the cell's scratch path, not ours.
_REPORT_FLAG: Final = "--junitxml="


@dataclass(frozen=True, slots=True)
class SealedCollection:
    """What one sealed collection run produced."""

    argv: tuple[str, ...]
    nodeids: Mapping[str, tuple[str, ...]]
    outcomes: Mapping[str, bool]
    #: The receipt's own command record. A collection that cannot name the command that
    #: produced it is not evidence, and the attempt entity requires provenance.
    command: CommandResult | None = None
    closure_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class SealedRun:
    """The evidence of a pinned run: which seal, which revision, which nodeids."""

    seal_sha256: str
    revision_id: str
    closure_sha256: str
    argv: tuple[str, ...]
    nodeids: Mapping[str, tuple[str, ...]]
    outcomes: Mapping[str, bool]


def _is_sealed_test(path: str) -> bool:
    return path.startswith("tests/") and path.endswith(".py") and PurePosixPath(path).name.startswith("test_")


def _test_paths(closure: AcceptanceClosure, sealed_root: str) -> tuple[str, ...]:
    """The sealed test modules, workspace-relative and sorted.

    Derived from the closure record, not from the plan: a test the planner named
    but never sealed is not a target, and a sealed module the plan forgot is.
    Takes the closure rather than a bundle because the collection that *precedes*
    a mint has no bundle yet (see :func:`collect_sealed_tree`).
    """
    paths = sorted(f"{sealed_root}/{entry.path}" for entry in closure.files if _is_sealed_test(entry.path))
    if not paths:
        raise AcceptanceCollectionError("no-sealed-tests")
    return tuple(paths)


def sealed_test_paths(bundle: AcceptanceBundle) -> tuple[str, ...]:
    """The sealed test modules of one seal, workspace-relative and sorted."""
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceCollectionError("seal-invalid")
    return _test_paths(bundle.closure, bundle.sealed_root)


def _argv_for(closure: AcceptanceClosure, sealed_root: str, *, report: str) -> tuple[str, ...]:
    """The harness-built invocation: sealed targets, sealed config, sealed root."""
    return pytest_argv(
        tests=_test_paths(closure, sealed_root),
        ini=f"{sealed_root}/pytest.ini",
        rootdir=sealed_root,
        report=report,
    )


def sealed_collection_argv(bundle: AcceptanceBundle, *, report: str) -> tuple[str, ...]:
    """The harness-built invocation for one seal: sealed targets, config and root."""
    return _argv_for(bundle.closure, bundle.sealed_root, report=report)


def _workspace_nodeids(bundle: AcceptanceBundle, outcomes: Mapping[str, bool]) -> dict[str, bool]:
    """Re-key one seal's nodeid report; the rule itself is :func:`_key_nodeids`."""
    return _key_nodeids(bundle.closure, bundle.sealed_root, outcomes)


def _key_nodeids(closure: AcceptanceClosure, sealed_root: str, outcomes: Mapping[str, bool]) -> dict[str, bool]:
    """Re-key pytest's rootdir-relative nodeids to workspace-relative ones.

    Every reported nodeid must address a file the closure holds; a report that
    escaped the sealed root (an absolute path, a ``..`` hop, a file outside the
    record) is refused rather than normalized.
    """
    paths = {entry.path for entry in closure.files}
    prefix = f"{sealed_root}/"
    keyed: dict[str, bool] = {}
    for nodeid, passed in outcomes.items():
        workspace_nodeid = f"{prefix}{nodeid}"
        if not workspace_nodeid.startswith(prefix) or workspace_nodeid[len(prefix) :].partition("::")[0] not in paths:
            raise AcceptanceCollectionError("collection-nodeid-outside-closure")
        keyed[workspace_nodeid] = passed
    return keyed


def _group_nodeids(nodeids: Mapping[str, bool]) -> Mapping[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for nodeid in nodeids:
        grouped.setdefault(nodeid.partition("::")[0], []).append(nodeid)
    return {path: tuple(sorted(entries)) for path, entries in sorted(grouped.items())}


def collect_sealed_nodeids(
    bundle: AcceptanceBundle,
    *,
    workspace: Path,
    deadline: float | None = None,
    executor: VerifyCommandExecutor | None = None,
) -> SealedCollection:
    """Collect nodeids by running the sealed acceptance bytes themselves.

    Only a substrate whose writes the caller can read afterwards is supported:
    a managed cell returns its report inside the exec receipt, and reporting that
    as an unsupported substrate is honest where running the *unpinned* command
    would be a silent downgrade of the oracle.
    """
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceCollectionError("seal-invalid")
    if executor is not None and not getattr(executor, "writes_are_visible", True):
        raise AcceptanceCollectionError("substrate-unsupported")
    sealed_root = Path(workspace) / bundle.sealed_root
    # A tree that no longer is the sealed closure never runs: the refusal is the
    # seal's own closed rule, so this module does not re-label it.
    verify_sealed_root(bundle, sealed_root)
    with tempfile.TemporaryDirectory(prefix="fa-sealed-collection-") as directory:
        report = Path(directory) / "results.xml"
        argv = sealed_collection_argv(bundle, report=str(report))
        (result,) = run_commands(
            (shell_command(argv),), workspace=Path(workspace), deadline=deadline, executor=executor
        )
        if result.outcome is CommandOutcome.ERROR:
            raise AcceptanceCollectionError("collection-error")
        try:
            raw = report.read_bytes()
        except OSError:
            raise AcceptanceCollectionError("collection-no-report") from None
    outcomes, _detail = parse_nodeid_report(raw)
    if outcomes is None:
        raise AcceptanceCollectionError("collection-report-invalid")
    if not outcomes:
        raise AcceptanceCollectionError("collection-empty")
    if result.exit_code not in {0, 1}:
        raise AcceptanceCollectionError("collection-unusable")
    keyed = _workspace_nodeids(bundle, outcomes)
    return SealedCollection(argv=argv, nodeids=_group_nodeids(keyed), outcomes=keyed)


def sealed_collection_inband_command(bundle: AcceptanceBundle, *, report: str) -> str:
    """The sealed invocation with its report travelling in the receipt (Q142 A).

    Same harness argv as :func:`sealed_collection_argv` -- sealed targets, ``-c``,
    ``--rootdir``, no cache provider -- with one substitution: the report
    destination becomes the wrapper's ``$__fa_rep``, because a READ cell's only
    writable path is its own tmpfs scratch and the controller cannot name it.
    Exactly one argv element may carry the flag; anything else is refused rather
    than rendered, so the command that runs is always the argv that was checked.
    """
    return "export PYTHONDONTWRITEBYTECODE=1; " + _render_inband(
        sealed_collection_argv(bundle, report=report), report=report
    )


def _render_inband(argv: tuple[str, ...], *, report: str) -> str:
    """Render an argv with its report flag pointed at the wrapper's ``$__fa_rep``."""
    rendered: list[str] = []
    replaced = 0
    for part in argv:
        if part.startswith(_REPORT_FLAG):
            rendered.append(f'{_REPORT_FLAG}"$__fa_rep"')
            replaced += 1
        else:
            rendered.append(shlex.quote(part))
    if replaced != 1:
        raise AcceptanceCollectionError("collection-argv-invalid")
    return inband_junit_command(" ".join(rendered), report=report)


def _require_managed_substrate(executor: VerifyCommandExecutor | None) -> None:
    """No host fallback: a sealed verification runs on the authority or not at all.

    ``writes_are_visible is False`` is the property that makes a substrate the
    pinned cell (`ManagedVerifyCommandExecutor`). A host executor would run the
    oracle next to the code it is judging, which is the configuration CT61 forbids;
    reporting that as refused is honest where falling back is a silent downgrade.
    """
    if executor is None or getattr(executor, "writes_are_visible", True):
        raise AcceptanceCollectionError("verifier-substrate-required")


def _overlaps_code_root(sealed_root: str) -> bool:
    """Whether the sealed root names a code tree (CT-3.6's overlap refusal)."""
    parts = PurePosixPath(sealed_root).parts
    return not parts or any(part in _CODE_ROOTS for part in parts)


def collect_sealed_tree(
    acceptance_root: Path,
    *,
    sealed_root: str,
    workspace: Path,
    deadline: float | None = None,
    executor: VerifyCommandExecutor | None = None,
    expected_revision_id: str | None = None,
) -> SealedCollection:
    """Collect a sealed tree's nodeids **before** any seal exists.

    ``mint_seal`` requires a ``collected`` report, and every other collector here
    requires a minted ``AcceptanceBundle`` -- a cycle, which is why the controller
    has never minted a seal: there was no way to take the first step. The closure
    and the harness argv, however, depend only on the tree and the sealed root, so a
    tree can be collected on its own and the result handed straight to ``mint_seal``:

        collection = collect_sealed_tree(root, sealed_root=..., workspace=...)
        bundle = mint_seal(..., collected=collection.nodeids)

    The root is the tree the revision committed, read through the same closure walk
    the mint will perform, so the nodeids this returns are keyed exactly as the
    mint's ``resolve_selectors`` expects (workspace-relative, grouped by module).
    Nothing else about the seal is assumed: the revision binding, the plan digest
    and the totality checks stay in the mint, where they are one rule.

    No host fallback applies here for the same reason it applies to every sealed
    run: this executes the acceptance bytes, and it runs on the authority or not at
    all.
    """
    if not isinstance(acceptance_root, Path) or acceptance_root.name != "acceptance":
        # Same rule and same exception as ``mint_seal``'s check on the tree it seals: this is the
        # seal's vocabulary borrowed, not a second one, so a caller catches one type for one rule.
        raise AcceptanceBundleError("sealed-root-invalid")
    root = require_sealed_root(sealed_root)
    _require_managed_substrate(executor)
    if expected_revision_id is not None:
        _require_named_revision(executor, expected_revision_id)
    try:
        closure = collect_acceptance_closure(acceptance_root)
    except AcceptanceClosureError as error:
        raise AcceptanceCollectionError(f"closure-{error.rule}") from None
    argv = _argv_for(closure, root, report=_INBAND_REPORT_NAME)
    run_id = uuid.uuid4().hex
    env = _gate_subprocess_env(Path(workspace))
    env[JUNIT_RUN_ID_ENV] = run_id
    (result,) = run_commands(
        ("export PYTHONDONTWRITEBYTECODE=1; " + _render_inband(argv, report=_INBAND_REPORT_NAME),),
        workspace=Path(workspace),
        deadline=deadline,
        executor=executor,
        env=env,
    )
    if result.outcome is CommandOutcome.ERROR:
        raise AcceptanceCollectionError("collection-error")
    carried = result.inband_stdout if result.inband_stdout is not None else result.stdout_tail
    classified, _detail = parse_inband_precode_outcomes(carried, run_id=run_id)
    if classified is None:
        raise AcceptanceCollectionError("collection-report-invalid")
    if "other" in classified.values():
        raise AcceptanceCollectionError("collection-call-error")
    if "skipped" in classified.values():
        raise AcceptanceCollectionError("collection-skipped")
    outcomes = {nodeid: state == "passed" for nodeid, state in classified.items()}
    if not outcomes:
        raise AcceptanceCollectionError("collection-empty")
    expected_exit = 0 if all(outcomes.values()) else 1
    expected_outcome = CommandOutcome.PASS if expected_exit == 0 else CommandOutcome.FAIL
    if result.exit_code != expected_exit or result.outcome is not expected_outcome:
        raise AcceptanceCollectionError("collection-unusable")
    keyed = _key_nodeids(closure, root, outcomes)
    return SealedCollection(
        argv=argv, nodeids=_group_nodeids(keyed), outcomes=keyed, command=result, closure_sha256=closure.digest
    )


def collect_sealed_nodeids_inband(
    bundle: AcceptanceBundle,
    *,
    workspace: Path,
    deadline: float | None = None,
    executor: VerifyCommandExecutor | None = None,
) -> SealedCollection:
    """Collect the sealed closure's nodeids from a cell's in-band receipt."""
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceCollectionError("seal-invalid")
    _require_managed_substrate(executor)
    verify_sealed_root(bundle, Path(workspace) / bundle.sealed_root)
    argv = sealed_collection_argv(bundle, report=_INBAND_REPORT_NAME)
    run_id = uuid.uuid4().hex
    env = _gate_subprocess_env(Path(workspace))
    env[JUNIT_RUN_ID_ENV] = run_id
    (result,) = run_commands(
        (sealed_collection_inband_command(bundle, report=_INBAND_REPORT_NAME),),
        workspace=Path(workspace),
        deadline=deadline,
        executor=executor,
        env=env,
    )
    if result.outcome is CommandOutcome.ERROR:
        raise AcceptanceCollectionError("collection-error")
    carried = result.inband_stdout if result.inband_stdout is not None else result.stdout_tail
    classified, _detail = parse_inband_precode_outcomes(carried, run_id=run_id)
    if classified is None:
        raise AcceptanceCollectionError("collection-report-invalid")
    if "other" in classified.values():
        raise AcceptanceCollectionError("collection-call-error")
    if "skipped" in classified.values():
        raise AcceptanceCollectionError("collection-skipped")
    outcomes = {nodeid: state == "passed" for nodeid, state in classified.items()}
    if not outcomes:
        raise AcceptanceCollectionError("collection-empty")
    expected_exit = 0 if all(outcomes.values()) else 1
    expected_outcome = CommandOutcome.PASS if expected_exit == 0 else CommandOutcome.FAIL
    if result.exit_code != expected_exit or result.outcome is not expected_outcome:
        raise AcceptanceCollectionError("collection-unusable")
    keyed = _workspace_nodeids(bundle, outcomes)
    return SealedCollection(argv=argv, nodeids=_group_nodeids(keyed), outcomes=keyed, command=result)


@dataclass(frozen=True, slots=True)
class SealedVerification:
    """One sealed verification: which seal, which closure, which code it ran against.

    Both revision identities are recorded because they are different claims: the
    closure ran at ``sealed_revision_id`` (the revision the seal names, re-proved
    against the bytes), while the code under test came from
    ``candidate_revision_id`` -- the caller's explicit *current* candidate. Keeping
    them apart is what makes "the closure did not move while the code did" a
    checkable statement instead of a habit.
    """

    run: SealedRun
    sealed_root: str
    sealed_revision_id: str
    candidate_revision_id: str
    command: CommandResult


def verify_sealed_acceptance(
    bundle: AcceptanceBundle,
    *,
    workspace: Path,
    candidate_revision_id: str,
    plan_bytes: bytes,
    kill_required: tuple[str, ...] = (),
    deadline: float | None = None,
    executor: VerifyCommandExecutor | None = None,
) -> SealedVerification:
    """Run the seal's closure on the pinned cell against the current candidate (CT-3.6).

    The order of the refusals is deliberate: every check that can be made without
    executing anything is made first, so a bad call never becomes a command in a
    cell. Nothing here reads a planner ``verify`` fence -- the command is the
    harness-built argv over the sealed closure -- and nothing here falls back to a
    host run.

    ``kill_required`` is the contracts whose plan section declares a kill target
    (``KILL-TARGETS``). This function does **not** run mutations yet, and it refuses
    instead of proving without them (F9): a claim is "passed **and** the mutation
    died", so returning a result for a contract whose mutation never ran would be a
    proof the attempt does not have. The composition with STEP9A's existing runner
    (a public ``run_kill_checks`` seam -- not a second runner, which SLICE3's intent
    forbids) is what lifts this refusal; until then a plan that declares kill targets
    gets an honest ``claim-mutation-missing`` rather than a false ``PROVEN``.
    """
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceCollectionError("seal-invalid")
    _require_managed_substrate(executor)
    try:
        require_revision_id(candidate_revision_id)
    except AcceptanceBundleError:
        raise AcceptanceCollectionError("candidate-revision-invalid") from None
    if _overlaps_code_root(bundle.sealed_root):
        raise AcceptanceCollectionError("sealed-root-code-overlap")
    if kill_required:
        # Refused before the cell runs: a proof that omits the mutation is worse than
        # no proof, because it is indistinguishable from one that had it.
        raise AcceptanceCollectionError("claim-mutation-missing")
    verify_plan(bundle, plan_bytes)
    verify_revision(bundle, bundle.revision_id)
    # F5: the caller's revision becomes evidence only once the substrate names it.
    _require_named_revision(executor, candidate_revision_id)
    collection = collect_sealed_nodeids_inband(bundle, workspace=Path(workspace), deadline=deadline, executor=executor)
    missing = [selector.nodeid for selector in bundle.selectors if selector.nodeid not in collection.outcomes]
    if missing:
        raise AcceptanceCollectionError("sealed-test-missing")
    return SealedVerification(
        run=SealedRun(
            seal_sha256=bundle.seal_sha256,
            revision_id=bundle.revision_id,
            closure_sha256=bundle.closure.digest,
            argv=collection.argv,
            nodeids=collection.nodeids,
            outcomes=collection.outcomes,
        ),
        sealed_root=bundle.sealed_root,
        sealed_revision_id=bundle.revision_id,
        candidate_revision_id=candidate_revision_id,
        command=_require_command(collection),
    )


def _require_named_revision(executor: VerifyCommandExecutor | None, candidate_revision_id: str) -> None:
    """The substrate must *name* the revision it is pinned at, and name the candidate (F5).

    ``candidate_revision_id`` used to be taken on trust, so a verification could faithfully record a
    revision that never ran the oracle. The managed substrate holds the authority's view, whose
    ``base_revision`` is that answer; a substrate that cannot name one is not an identity ("I ran
    somewhere"), and one that names another is a different candidate -- both are refused before the
    cell runs, because neither can be repaired by executing anything.
    """
    named = getattr(executor, "view_revision_id", None)
    if not isinstance(named, str) or named != candidate_revision_id:
        raise AcceptanceCollectionError("verifier-revision-mismatch")


def _require_command(collection: SealedCollection) -> CommandResult:
    """The receipt a sealed collection always has, or a refusal -- never a guess."""
    if collection.command is None:
        raise AcceptanceCollectionError("collection-no-command")
    return collection.command


def _claim_outcome(outcomes: Mapping[str, bool], nodeid: str) -> tuple[str, str]:
    """One selector's outcome, keeping "did not execute" distinct from "failed"."""
    passed = outcomes.get(nodeid)
    if passed is None:
        return "error", "the sealed selector produced no nodeid in this run"
    return ("passed", "") if passed else ("failed", "")


def _require_identity_matches(bundle: AcceptanceBundle, identity: VerificationIdentity) -> None:
    """The identity an attempt records must describe the seal it claims to describe.

    Pairing one plan's bytes with another seal's graph is the defect E610 already paid for
    (``seal-plan-graph-mismatch``); the projection is the second place such a pair can be made, so
    it checks the pair rather than trusting the caller to have built both from one bundle.
    """
    recorded = {
        "plan": (identity.plan_sha256, bundle.plan_sha256),
        "seal": (identity.seal_sha256, bundle.seal_sha256),
        "closure": (identity.closure_sha256, bundle.closure.digest),
        "sealed revision": (identity.sealed_revision_id, bundle.revision_id),
    }
    for expected, actual in recorded.values():
        if expected != actual:
            raise AcceptanceCollectionError("verifier-identity-mismatch")


def _require_run_matches(bundle: AcceptanceBundle, verification: SealedVerification) -> None:
    """The measured run must be *this* seal's run, not one that was carried over.

    ``SealedRun`` is a frozen record of what executed; a caller who swaps it in after the fact can
    otherwise attach another seal's outcomes to this bundle's claims. The identity checks above
    cannot see that, because the run is a second statement of the same three digests.
    """
    run = verification.run
    if (
        run.seal_sha256 != bundle.seal_sha256
        or run.closure_sha256 != bundle.closure.digest
        or run.revision_id != bundle.revision_id
        or verification.sealed_revision_id != bundle.revision_id
        or verification.sealed_root != bundle.sealed_root
    ):
        raise AcceptanceCollectionError("verifier-identity-mismatch")


def sealed_attempt(
    bundle: AcceptanceBundle,
    verification: SealedVerification,
    *,
    identity: VerificationIdentity,
    kill_declared: tuple[KillTarget, ...] = (),
) -> VerificationAttempt:
    """Project one sealed verification into the attempt the gate reads (F10).

    This is the step that turns "the verifier measured the sealed closure" into "the gate has a
    verdict": one claim per sealed selector, the seal's attested/pending debt carried exactly as
    the seal states it, and one harness-authored command with its receipt. ``kill_required`` is
    empty because the V2 grammar declares no executable mutation (``KillTarget`` carries
    attribution only, ``plan_v2.py:509-518``); CT-3.4 calls a target pass on that route vacuous,
    and an attempt must not claim more than the grammar can express.
    """
    if not isinstance(bundle, AcceptanceBundle):
        raise AcceptanceCollectionError("seal-invalid")
    if not isinstance(verification, SealedVerification):
        raise AcceptanceCollectionError("verification-invalid")
    if verification.candidate_revision_id != identity.candidate_revision_id:
        raise AcceptanceCollectionError("verifier-revision-mismatch")
    _require_identity_matches(bundle, identity)
    _require_run_matches(bundle, verification)

    commands = (AttemptCommand.from_result(verification.command, authored_by="harness"),)
    claims = tuple(
        ClaimEvidence(
            contract_id=selector.ct_id,
            test_id=selector.test_id,
            nodeid=selector.nodeid,
            outcome=_claim_outcome(verification.run.outcomes, selector.nodeid)[0],
            detail=_claim_outcome(verification.run.outcomes, selector.nodeid)[1],
        )
        for selector in bundle.selectors
    )
    expected = {(selector.ct_id, selector.test_id, selector.nodeid) for selector in bundle.selectors}
    actual = {(claim.contract_id, claim.test_id, claim.nodeid) for claim in claims}
    if len(expected) != len(bundle.selectors) or len(actual) != len(claims) or actual != expected:
        raise AcceptanceCollectionError("attempt-claims-seal-mismatch")
    try:
        return VerificationAttempt(
            route="v2",
            identity=identity,
            claims=claims,
            commands=commands,
            attested=bundle.attested,
            pending=bundle.pending,
            contracts_total=bundle.contracts_total,
            attestations=bundle.attestations,
            kill_declared=kill_declared,
        )
    except VerificationAttemptError as error:
        raise AcceptanceCollectionError(f"attempt-{error.rule}") from None


def run_sealed_acceptance(
    bundle: AcceptanceBundle,
    *,
    workspace: Path,
    revision_id: str,
    plan_bytes: bytes,
    deadline: float | None = None,
    executor: VerifyCommandExecutor | None = None,
) -> SealedRun:
    """The pinned run: the seal's plan, the seal's revision, the seal's bytes.

    Refuses before executing anything when the plan or the revision moved, and
    refuses after it when a sealed selector did not execute — an oracle that was
    not part of the run cannot have proven the contract it is mapped to.
    """
    verify_plan(bundle, plan_bytes)
    verify_revision(bundle, revision_id)
    collection = collect_sealed_nodeids(bundle, workspace=workspace, deadline=deadline, executor=executor)
    missing = [selector.nodeid for selector in bundle.selectors if selector.nodeid not in collection.outcomes]
    if missing:
        raise AcceptanceCollectionError("sealed-test-missing")
    return SealedRun(
        seal_sha256=bundle.seal_sha256,
        revision_id=bundle.revision_id,
        closure_sha256=bundle.closure.digest,
        argv=collection.argv,
        nodeids=collection.nodeids,
        outcomes=collection.outcomes,
    )
