"""C0 oracles for the sealed -> attempt projection (F10).

F10's finding: ``verify_plan`` answers a V2 route with nothing to check, so "the sealed run
passed" and "the gate has a verdict" were two different facts with only the first one measured.
``sealed_attempt`` is the join. These oracles hold the four things the join must not lose:
one claim per sealed selector, a missing outcome that stays missing, an identity that describes
the seal it is attached to, and a command that names the harness rather than a planner fence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from fa.inner_loop.acceptance_bundle import AcceptanceBundle
from fa.inner_loop.acceptance_collection import (
    AcceptanceCollectionError,
    SealedCollection,
    SealedRun,
    SealedVerification,
    _require_command,
    sealed_attempt,
    verify_sealed_acceptance,
)
from fa.inner_loop.slice_verification import CommandOutcome, CommandResult
from fa.inner_loop.verification_attempt import VerificationIdentity
from tests.test_ai_native_acceptance_collection import (
    _EXTRA_NODEID,
    _NODEID,
    _PLAN_BYTES,
    _REVISION,
    _mint,
    _tree,
)
from tests.test_slice_verification_runner import _inband_executor

_OTHER_REVISION = "rev-" + "1" * 32
_OTHER_SHA = "a" * 64


def _command(outcome: CommandOutcome = CommandOutcome.PASS, exit_code: int = 0) -> CommandResult:
    return CommandResult(
        command="python -m pytest -c worklogs/demo/acceptance/pytest.ini",
        outcome=outcome,
        exit_code=exit_code,
        stdout_tail="",
        stderr_tail="",
        duration_s=0.0,
    )


def _verification(
    bundle: AcceptanceBundle,
    *,
    outcomes: dict[str, bool],
    candidate_revision_id: str | None = None,
    command: CommandResult | None = None,
) -> SealedVerification:
    """The seal's run, as ``verify_sealed_acceptance`` returns it -- one field at a time."""
    return SealedVerification(
        run=SealedRun(
            seal_sha256=bundle.seal_sha256,
            revision_id=bundle.revision_id,
            closure_sha256=bundle.closure.digest,
            argv=("python", "-m", "pytest"),
            nodeids={_NODEID.rsplit("::", 1)[0]: tuple(outcomes)},
            outcomes=outcomes,
        ),
        sealed_root=bundle.sealed_root,
        sealed_revision_id=bundle.revision_id,
        candidate_revision_id=candidate_revision_id or bundle.revision_id,
        command=command or _command(),
    )


def _identity(bundle: AcceptanceBundle, **overrides: object) -> VerificationIdentity:
    fields: dict[str, object] = {
        "plan_sha256": hashlib.sha256(_PLAN_BYTES).hexdigest(),
        "candidate_revision_id": bundle.revision_id,
        "profile_id": "claude-code",
        "substrate": "docker",
        "run_id": "run-1",
        "attempt": 1,
        "repair_round": 0,
        "mode": "build",
        "seal_sha256": bundle.seal_sha256,
        "closure_sha256": bundle.closure.digest,
        "sealed_revision_id": bundle.revision_id,
    }
    fields.update(overrides)
    return VerificationIdentity(**fields)  # type: ignore[arg-type]


def _bundle(tmp_path: Path) -> AcceptanceBundle:
    return _mint(_tree(tmp_path))


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(AcceptanceCollectionError) as refused:
        callable_()
    return refused.value.rule


# -- the join ---------------------------------------------------------------


def test_the_projection_carries_one_claim_per_sealed_selector(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={_NODEID: True})

    attempt = sealed_attempt(bundle, verification, identity=_identity(bundle))

    assert attempt.route == "v2"
    assert [(claim.contract_id, claim.nodeid, claim.outcome) for claim in attempt.claims] == [
        (selector.ct_id, selector.nodeid, "passed") for selector in bundle.selectors
    ]
    assert len(attempt.claims) == len(bundle.selectors)
    assert all(claim.proven for claim in attempt.claims)
    assert attempt.contracts_total == bundle.contracts_total
    assert attempt.attested == bundle.attested
    assert attempt.pending == bundle.pending
    # F9/CT-3.4: the V2 grammar declares no executable mutation, so nothing is required.
    assert attempt.kill_required == ()
    assert all(claim.mutation is None for claim in attempt.claims)
    assert attempt.blocking is False
    assert attempt.first_reason == ""


def test_the_projection_records_the_harness_command_that_actually_ran(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={_NODEID: True})

    attempt = sealed_attempt(bundle, verification, identity=_identity(bundle))

    assert len(attempt.commands) == 1
    command = attempt.commands[0]
    # The seal's argv is the command; the attempt records the receipt, not a rephrasing of it.
    assert command.command == verification.command.command
    assert command.authored_by == "harness"
    assert command.outcome == "pass"
    assert command.exit_code == 0


def test_a_failing_sealed_nodeid_blocks_and_names_the_nodeid(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    verification = _verification(
        bundle,
        outcomes={_NODEID: False},
        command=_command(CommandOutcome.FAIL, 1),
    )

    attempt = sealed_attempt(bundle, verification, identity=_identity(bundle))

    assert attempt.blocking is True
    assert attempt.repair_nodeids() == (_NODEID,)
    assert _NODEID in attempt.first_reason
    failing = attempt.claims[0]
    assert attempt.first_reason.startswith(f"{failing.contract_id} {failing.test_id}: failed")


def test_a_selector_without_an_outcome_is_an_error_never_a_skip(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={})

    attempt = sealed_attempt(bundle, verification, identity=_identity(bundle))

    assert [claim.outcome for claim in attempt.claims] == ["error"]
    assert "no nodeid" in attempt.claims[0].detail
    assert "skipped" not in {claim.outcome for claim in attempt.claims}
    assert attempt.blocking is True


def test_an_outcome_the_seal_does_not_map_never_becomes_a_claim(tmp_path: Path) -> None:
    """The claims are the seal's selectors, not whatever the run happened to report."""
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={_NODEID: True, _EXTRA_NODEID: True})

    attempt = sealed_attempt(bundle, verification, identity=_identity(bundle))

    assert len(attempt.claims) == len(bundle.selectors)
    assert _EXTRA_NODEID not in {claim.nodeid for claim in attempt.claims}


# -- the identity the attempt claims to describe ---------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("plan_sha256", _OTHER_SHA),
        ("seal_sha256", _OTHER_SHA),
        ("closure_sha256", _OTHER_SHA),
        ("sealed_revision_id", _OTHER_REVISION),
    ],
)
def test_the_projection_refuses_an_identity_from_another_seal(tmp_path: Path, field: str, value: str) -> None:
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={_NODEID: True})

    assert (
        _rule(lambda: sealed_attempt(bundle, verification, identity=_identity(bundle, **{field: value})))
        == "verifier-identity-mismatch"
    )


def test_the_projection_refuses_an_identity_from_another_candidate_revision(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={_NODEID: True})
    stale = _identity(bundle, candidate_revision_id=_OTHER_REVISION)

    assert _rule(lambda: sealed_attempt(bundle, verification, identity=stale)) == "verifier-revision-mismatch"


def test_a_collection_that_cannot_name_its_command_is_refused() -> None:
    without = SealedCollection(argv=(), nodeids={}, outcomes={})

    with pytest.raises(AcceptanceCollectionError) as refused:
        _require_command(without)
    assert refused.value.rule == "collection-no-command"


def test_a_seal_projection_never_authors_a_planner_command(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={_NODEID: True})

    attempt = sealed_attempt(bundle, verification, identity=_identity(bundle))

    # The attempt type refuses "planner" on a V2 route; this holds the projection's side of it.
    assert {command.authored_by for command in attempt.commands} == {"harness"}


# -- the real path ---------------------------------------------------------


def test_the_real_verification_projects_its_own_receipt(tmp_path: Path) -> None:
    """CT-3.6 end to end: a real in-band run, then the attempt keeps that command."""
    bundle = _mint(_tree(tmp_path))
    prepared: dict[str, object] = {}
    verification = verify_sealed_acceptance(
        bundle,
        workspace=tmp_path,
        candidate_revision_id=_REVISION,
        plan_bytes=_PLAN_BYTES,
        executor=_inband_executor(writes_visible=False, prepared=prepared),
    )

    attempt = sealed_attempt(bundle, verification, identity=_identity(bundle))

    assert verification.command.command == prepared["command"]
    attempt_command = attempt.commands[0]
    assert attempt_command.command == verification.command.command
    assert attempt_command.outcome == verification.command.outcome.value
    assert attempt_command.exit_code == verification.command.exit_code == 0
    assert attempt.blocking is False


def test_replace_keeps_the_projection_honest_when_the_run_moves(tmp_path: Path) -> None:
    """A verification from another seal cannot be re-labelled by swapping the run."""
    bundle = _bundle(tmp_path)
    verification = _verification(bundle, outcomes={_NODEID: True})
    foreign = replace(verification, run=replace(verification.run, seal_sha256=_OTHER_SHA))

    assert _rule(lambda: sealed_attempt(bundle, foreign, identity=_identity(bundle))) == "verifier-identity-mismatch"
