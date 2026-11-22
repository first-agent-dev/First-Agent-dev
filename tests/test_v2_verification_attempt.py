"""C0 oracles for the verification attempt entity (Q-V2-SLICE3-2).

Each test names the defect it prevents, because the entity exists to stop a specific class of
untruth: a claim with no identity, a mutation that never ran reading as proven, a planner command
on the sealed route, an empty attempt that looks like a clean one, and a free-text field that can
evict the rest of the evidence.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from fa.inner_loop.slice_verification import CommandOutcome, CommandResult
from fa.inner_loop.verification_attempt import (
    DETAIL_LIMIT,
    AttemptCommand,
    ClaimEvidence,
    MutationEvidence,
    VerificationAttempt,
    VerificationAttemptError,
    VerificationIdentity,
)

_PLAN = "a" * 64
_SEAL = "b" * 64
_CLOSURE = "c" * 64
_SEALED_REVISION = "rev-" + "0" * 32
_CANDIDATE = "rev-" + "1" * 32
_NODEID = "worklogs/demo/acceptance/tests/test_publish.py::test_publish"


def _identity(**overrides: object) -> VerificationIdentity:
    fields: dict[str, object] = {
        "plan_sha256": _PLAN,
        "candidate_revision_id": _CANDIDATE,
        "profile_id": "readonly-v1",
        "substrate": "managed-readonly",
        "run_id": "run-1",
        "attempt": 1,
        "repair_round": 0,
        "mode": "enforce",
        "seal_sha256": _SEAL,
        "closure_sha256": _CLOSURE,
        "sealed_revision_id": _SEALED_REVISION,
    }
    fields.update(overrides)
    return cast(Callable[..., VerificationIdentity], VerificationIdentity)(**fields)


def _claim(**overrides: object) -> ClaimEvidence:
    fields: dict[str, object] = {
        "contract_id": "CT-1.1",
        "test_id": "TEST-1.1",
        "nodeid": _NODEID,
        "outcome": "passed",
    }
    fields.update(overrides)
    return cast(Callable[..., ClaimEvidence], ClaimEvidence)(**fields)


def _command(*, authored_by: str = "harness") -> AttemptCommand:
    return AttemptCommand(command="python -m pytest", authored_by=authored_by, outcome="pass", exit_code=0)


def _attempt(**overrides: object) -> VerificationAttempt:
    fields: dict[str, object] = {
        "route": "v2",
        "identity": _identity(),
        "claims": (_claim(),),
        "commands": (_command(),),
        "contracts_total": 1,
    }
    fields.update(overrides)
    return cast(Callable[..., VerificationAttempt], VerificationAttempt)(**fields)


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(VerificationAttemptError) as refused:
        callable_()
    return refused.value.rule


# ── the valid shapes ─────────────────────────────────────────────────────────


def test_a_sealed_attempt_records_identity_claims_and_provenance() -> None:
    """The entity carries all three things the old artifact lost: claim, identity, authorship."""
    attempt = _attempt()

    assert attempt.identity is not None
    assert attempt.identity.candidate_revision_id == _CANDIDATE
    assert attempt.identity.sealed_revision_id == _SEALED_REVISION
    assert attempt.commands[0].authored_by == "harness"
    assert attempt.blocking is False
    assert attempt.first_reason == ""
    assert attempt.repair_nodeids() == ()


def test_a_failed_claim_names_its_contract_and_nodeid_for_repair() -> None:
    """D-V2-4's repair target is derivable from the attempt alone, without the seal."""
    attempt = _attempt(claims=(_claim(outcome="failed", detail="assert 1 == 2"),))

    assert attempt.blocking is True
    assert attempt.first_reason == f"CT-1.1 TEST-1.1: failed at {_NODEID}"
    assert attempt.repair_nodeids() == (_NODEID,)


# ── F1/F9: a mutation that did not run may not read as proven ────────────────


def test_a_declared_kill_target_without_evidence_is_refused() -> None:
    """F9: 'no kill target' and 'never got to it' must not be the same value.

    Without this rule the sealed verifier could record a claim as proven while the mutation it
    declares had never been attempted -- the defect the landed verifier actually had.
    """
    assert _rule(lambda: _attempt(kill_required=("CT-1.1",))) == "claim-mutation-missing"


def test_a_declared_kill_target_that_survived_blocks_even_though_the_test_passed() -> None:
    """F1: the mutation verdict is part of the claim, not a parallel array a reader may miss."""
    survived = MutationEvidence(operator="operator", target="fa/x.py", verdict="SURVIVED", detail="still passes")
    attempt = _attempt(kill_required=("CT-1.1",), claims=(_claim(mutation=survived),))

    assert attempt.blocking is True
    assert "mutation SURVIVED" in attempt.first_reason
    assert attempt.repair_nodeids() == (_NODEID,)


def test_a_killed_mutation_completes_the_claim() -> None:
    killed = MutationEvidence(operator="operator", target="fa/x.py", verdict="PROVEN")
    attempt = _attempt(kill_required=("CT-1.1",), claims=(_claim(mutation=killed),))

    assert attempt.blocking is False
    assert attempt.repair_nodeids() == ()


# ── F2: the fence cannot come back unnoticed ─────────────────────────────────


def test_a_planner_authored_command_on_the_sealed_route_is_refused() -> None:
    """CT-3.6 as an invariant: the retirement of the fence is checkable, not an omission."""
    assert _rule(lambda: _attempt(commands=(_command(), _command(authored_by="planner")))) == "fence-on-v2-route"


def test_the_legacy_route_may_still_run_planner_commands() -> None:
    """The frozen route keeps its fences; the rule binds the route whose oracle is sealed."""
    attempt = _attempt(route="legacy", identity=None, commands=(_command(authored_by="planner"),))

    assert attempt.route == "legacy"
    assert attempt.blocking is False


# ── F3: the attempt must cover the seal's total ──────────────────────────────


def test_claims_must_cover_the_seal_total_including_attested_and_pending() -> None:
    """F3: 'the seal promised three, this attempt shows one' is refused, not smoothed over."""
    assert _rule(lambda: _attempt(contracts_total=3)) == "claims-total-mismatch"

    attempt = _attempt(contracts_total=3, attested=("CT-1.2",), pending=("CT-1.3",))
    assert attempt.blocking is False


def test_a_pending_contract_that_is_also_attested_is_counted_once() -> None:
    """The seal requires ``pending`` ⊆ ``attested`` (``acceptance_bundle``), so the totals are a
    coverage count, not a sum of three list lengths -- otherwise every real seal double-counts."""
    attempt = _attempt(contracts_total=2, attested=("CT-1.2",), pending=("CT-1.2",))

    assert attempt.blocking is False
    assert attempt.attested == ("CT-1.2",)
    assert attempt.pending == ("CT-1.2",)


def test_a_contract_cannot_be_claimed_and_also_excused() -> None:
    assert _rule(lambda: _attempt(contracts_total=2, attested=("CT-1.1",))) == "claims-total-mismatch"
    assert _rule(lambda: _attempt(claims=(_claim(), _claim()), contracts_total=1)) == "claims-total-mismatch"


def test_pending_blocks_deploy_but_not_this_attempt() -> None:
    """D-V2-12: a debt owed to a host is a deploy question, not a verification failure."""
    attempt = _attempt(contracts_total=2, pending=("CT-1.2",))

    assert attempt.blocking is False
    assert attempt.first_reason == ""


# ── F4: refused must not look like empty ─────────────────────────────────────


def test_an_attempt_with_no_claims_must_say_why() -> None:
    """F4 as an invariant instead of a redundant field: no claims needs a stated reason."""
    assert _rule(lambda: _attempt(claims=(), contracts_total=0, commands=())) == "empty-attempt-unexplained"

    refused = _attempt(claims=(), contracts_total=0, commands=(), errors=("verifier-substrate-required",))
    assert refused.blocking is True
    assert refused.first_reason == "verifier-substrate-required"


# ── F8: identity is mandatory where the oracle is sealed ─────────────────────


@pytest.mark.parametrize("missing", ["seal_sha256", "closure_sha256", "sealed_revision_id"])
def test_a_sealed_attempt_without_its_identity_is_refused(missing: str) -> None:
    """F8/F5: an attempt that cannot name its seal cannot be evidence about that seal."""
    assert _rule(lambda: _attempt(identity=_identity(**{missing: None}))) == "identity-missing-on-v2"


def test_a_sealed_attempt_without_any_identity_is_refused() -> None:
    assert _rule(lambda: _attempt(identity=None)) == "identity-missing-on-v2"


def test_a_caller_may_not_invent_a_substring_identity() -> None:
    """Malformed digests are refused rather than recorded: a near-miss digest is worse than none."""
    assert _rule(lambda: _identity(seal_sha256="not-a-digest")) == "identity-invalid"
    assert _rule(lambda: _identity(attempt=0)) == "identity-invalid"


# ── F6: one field may not evict the rest of the evidence ────────────────────


def test_a_long_detail_is_bounded_at_construction_with_a_marker() -> None:
    """F6: the renderer truncates by head, so the bound has to be per field and earlier."""
    claim = _claim(detail="x" * (DETAIL_LIMIT * 3))

    assert len(claim.detail) == DETAIL_LIMIT
    assert claim.detail.endswith("…[truncated]")


def test_a_multi_line_detail_becomes_one_line() -> None:
    """Untrusted text stays readable in a rendering that is line-oriented."""
    claim = _claim(detail="first line\nsecond\tline")

    assert claim.detail == "first line second line"


def test_command_tails_are_bounded_too() -> None:
    result = CommandResult(
        command="python -m pytest",
        outcome=CommandOutcome.FAIL,
        exit_code=1,
        stdout_tail="y" * (DETAIL_LIMIT * 2),
        stderr_tail="",
        duration_s=0.5,
    )
    command = AttemptCommand.from_result(result, authored_by="harness")

    assert len(command.stdout_tail) == DETAIL_LIMIT
    assert command.exit_code == 1


# ── closed vocabularies ─────────────────────────────────────────────────────


def _attempt_with_unknown_claim_outcome() -> VerificationAttempt:
    return _attempt(
        claims=(
            cast(Callable[..., ClaimEvidence], ClaimEvidence)(
                contract_id="CT-1.1", test_id="TEST-1.1", nodeid=_NODEID, outcome="maybe"
            ),
        )
    )


def _attempt_with_unknown_authorship() -> VerificationAttempt:
    # The command is built through the cast as well: an out-of-vocabulary value must be refused
    # by the entity, which means the test cannot let the constructor refuse it earlier.
    command = cast(Callable[..., Any], AttemptCommand)(command="x", authored_by="model", outcome="pass", exit_code=0)
    return _attempt(commands=(command,))


@pytest.mark.parametrize(
    ("build", "rule"),
    [
        (lambda: _attempt(route="v1"), "route-invalid"),
        (_attempt_with_unknown_claim_outcome, "claim-invalid"),
        (_attempt_with_unknown_authorship, "command-invalid"),
    ],
)
def test_a_value_outside_a_closed_vocabulary_is_refused(build: Callable[[], object], rule: str) -> None:
    assert _rule(build) == rule
