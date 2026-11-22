"""The verification attempt entity: what one attempt at proving a claim may record.

Why this exists (Q-V2-SLICE3-2). The artifact used to be a projection of whatever the legacy
verifier happened to hold -- per-slice commands plus a parallel ``kill_checks`` array -- so a
reader had to reconstruct three things it needed from four places:

* **which claim** an outcome belongs to (per contract, never per suite: CT-3.4),
* **which identity** it ran under (seal, closure, sealed revision, *candidate* revision), and
* **who authored** the command that produced it (planner text or harness build).

None of those were in the record. ``SliceVerification``/``PlanVerification`` carry executed
commands, failed nodeids and mutation verdicts, but no total, no seal, no revisions, and no
provenance -- so an attempt could not say which oracle it belonged to, and a contract whose
selector vanished was indistinguishable from one that passed.

This module is the entity, not the wiring: it is the shape an attempt must have before anything
writes one, with the rules that make it honest as **constructor** refusals rather than reader
conventions:

======================  =====================================================================
``claims-total-mismatch``  the attempt must cover the seal's own total (claims + attested +
                           pending = ``contracts_total``). A short list is not "some passed".
``claim-mutation-missing``  a contract that declares a kill target must carry its mutation
                           verdict; ``None`` therefore means "no kill target", never "did not
                           get to it" (F1/F9).
``fence-on-v2-route``      a ``v2`` attempt may not contain a ``planner``-authored command. This
                           is CT-3.6's retirement as an invariant instead of an omission.
``empty-attempt-unexplained``  an attempt with no claims must say why (``errors``), so "refused"
                           and "found nothing" cannot look alike (F4, an invariant rather than a
                           redundant field).
``identity-missing-on-v2``  a ``v2`` attempt must name its seal, closure and revisions (F8).
======================  =====================================================================

Two deliberate choices. ``attested``/``pending`` are carried as the seal's own two lists instead
of becoming claim outcomes: the seal already distinguishes "proven by the oracle" from "carried
by a named party" and "owed to a host", and re-encoding that distinction in this module would be
a second vocabulary for one idea. And every free-text field is bounded here, at construction,
because the eval renderer truncates by *head*: one long ``detail`` would evict every later slice
and error from the model's context (F6) -- a bound applied only at render time cannot fix that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from .slice_verification import CommandOutcome, CommandResult

__all__ = [
    "AUTHORSHIP",
    "CLAIM_OUTCOMES",
    "DETAIL_LIMIT",
    "ROUTES",
    "AttemptCommand",
    "ClaimEvidence",
    "MutationEvidence",
    "VerificationAttempt",
    "VerificationAttemptError",
    "VerificationIdentity",
]

#: Closed vocabularies. A string that is not in one of these is a programming error, not data.
ROUTES: Final = frozenset({"v2", "legacy"})
AUTHORSHIP: Final = frozenset({"planner", "harness"})
CLAIM_OUTCOMES: Final = frozenset({"passed", "failed", "skipped", "error"})

#: One field's budget inside the eval evidence block. ``EVAL_VERIFICATION_MAX_CHARS`` is the
#: block's budget and is applied by *truncating the head* of the rendering, so an unbounded
#: field does not merely bloat the artifact -- it deletes the evidence that follows it.
DETAIL_LIMIT: Final = 2000

_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_TRUNCATED = "…[truncated]"


class VerificationAttemptError(ValueError):
    """Closed diagnostic reason; never carries input paths or exception bodies."""

    def __init__(self, rule: str) -> None:
        self.rule = rule
        super().__init__(f"invalid verification attempt: {rule}")


def _bounded(text: object) -> str:
    """Single-line, bounded free text, with the cut marked.

    Never raises: a detail is diagnostic text, and refusing an attempt because a cell printed
    something long would turn a reporting problem into a verification failure.
    """
    if not isinstance(text, str):
        return ""
    collapsed = " ".join(text.split())
    if len(collapsed) <= DETAIL_LIMIT:
        return collapsed
    return collapsed[: DETAIL_LIMIT - len(_TRUNCATED)] + _TRUNCATED


def _sha256_or_none(value: object, rule: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256.match(value):
        raise VerificationAttemptError(rule)
    return value


@dataclass(frozen=True, slots=True)
class VerificationIdentity:
    """Which bytes, at which revision, on which substrate -- the evidence's validity.

    ``candidate_revision_id`` is the revision the code under test came from, and it must be the
    revision the substrate was actually pinned at. The producer proves that against the view
    (``ViewRef.base_revision``) and refuses a disagreement (``verifier-revision-mismatch``); this
    type can only require that the value is present, which is why the check lives at the seam
    that can see both.
    """

    plan_sha256: str
    candidate_revision_id: str
    profile_id: str
    substrate: str
    run_id: str
    attempt: int
    repair_round: int
    mode: str
    seal_sha256: str | None = None
    closure_sha256: str | None = None
    sealed_revision_id: str | None = None

    def __post_init__(self) -> None:
        _sha256_or_none(self.plan_sha256, "identity-invalid")
        _sha256_or_none(self.seal_sha256, "identity-invalid")
        _sha256_or_none(self.closure_sha256, "identity-invalid")
        for name in ("candidate_revision_id", "profile_id", "substrate", "run_id", "mode"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise VerificationAttemptError("identity-invalid")
        if type(self.attempt) is not int or self.attempt < 1:
            raise VerificationAttemptError("identity-invalid")
        if type(self.repair_round) is not int or self.repair_round < 0:
            raise VerificationAttemptError("identity-invalid")
        if self.sealed_revision_id is not None and (
            not isinstance(self.sealed_revision_id, str) or not self.sealed_revision_id
        ):
            raise VerificationAttemptError("identity-invalid")


@dataclass(frozen=True, slots=True)
class MutationEvidence:
    """What one declared kill target did: did the mutation die (``PROVEN``) or not."""

    operator: str
    target: str
    verdict: str
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.operator, str) or not self.operator:
            raise VerificationAttemptError("mutation-invalid")
        if not isinstance(self.target, str) or not self.target:
            raise VerificationAttemptError("mutation-invalid")
        if not isinstance(self.verdict, str) or not self.verdict:
            raise VerificationAttemptError("mutation-invalid")
        object.__setattr__(self, "detail", _bounded(self.detail))


@dataclass(frozen=True, slots=True)
class ClaimEvidence:
    """One contract's evidence: did its oracle execute, pass, and (if declared) kill.

    ``nodeid`` is the sealed selector's nodeid, so a failed claim can name the exact thing a
    coder must fix (D-V2-4) without the reader holding the seal.
    """

    contract_id: str
    test_id: str
    nodeid: str
    outcome: str
    mutation: MutationEvidence | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.contract_id, str) or not self.contract_id:
            raise VerificationAttemptError("claim-invalid")
        if not isinstance(self.test_id, str) or not self.test_id:
            raise VerificationAttemptError("claim-invalid")
        if not isinstance(self.nodeid, str) or "::" not in self.nodeid:
            raise VerificationAttemptError("claim-invalid")
        if self.outcome not in CLAIM_OUTCOMES:
            raise VerificationAttemptError("claim-invalid")
        if self.mutation is not None and not isinstance(self.mutation, MutationEvidence):
            raise VerificationAttemptError("claim-invalid")
        object.__setattr__(self, "detail", _bounded(self.detail))

    @property
    def proven(self) -> bool:
        """Passed *and* (when a kill target was declared) the mutation died."""
        if self.outcome != "passed":
            return False
        return self.mutation is None or self.mutation.verdict == "PROVEN"


@dataclass(frozen=True, slots=True)
class AttemptCommand:
    """One command an attempt ran, with the provenance the artifact used to lose.

    ``authored_by`` is the axis that lets CT-3.6 be a checkable statement: planner text must
    never drive a V2 result, and a ``planner`` value on a ``v2`` attempt is refused below.
    """

    command: str
    authored_by: str
    outcome: str
    exit_code: int | None
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration_s: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.command, str) or not self.command:
            raise VerificationAttemptError("command-invalid")
        if self.authored_by not in AUTHORSHIP:
            raise VerificationAttemptError("command-invalid")
        if self.outcome not in {outcome.value for outcome in CommandOutcome}:
            raise VerificationAttemptError("command-invalid")
        if self.exit_code is not None and type(self.exit_code) is not int:
            raise VerificationAttemptError("command-invalid")
        object.__setattr__(self, "stdout_tail", _bounded(self.stdout_tail))
        object.__setattr__(self, "stderr_tail", _bounded(self.stderr_tail))

    @classmethod
    def from_result(cls, result: CommandResult, *, authored_by: str) -> AttemptCommand:
        """Project a runner's result; the runner knows what it ran, the attempt records who built it."""
        if not isinstance(result, CommandResult):
            raise VerificationAttemptError("command-invalid")
        return cls(
            command=result.command,
            authored_by=authored_by,
            outcome=result.outcome.value,
            exit_code=result.exit_code,
            stdout_tail=result.stdout_tail,
            stderr_tail=result.stderr_tail,
            duration_s=result.duration_s,
        )


@dataclass(frozen=True, slots=True)
class VerificationAttempt:
    """One append-only entry: the identity, every claim's evidence, and what ran.

    ``blocking`` is derived, never stored as authority. ``pending`` is *not* folded into it: a
    contract owed to a host is a deploy debt (D-V2-12), which is a different question from "may
    this candidate proceed", and answering both with one boolean is how a deploy gate becomes a
    verification failure.
    """

    route: str
    commands: tuple[AttemptCommand, ...]
    claims: tuple[ClaimEvidence, ...] = ()
    identity: VerificationIdentity | None = None
    attested: tuple[str, ...] = ()
    pending: tuple[str, ...] = ()
    contracts_total: int = 0
    kill_required: tuple[str, ...] = ()
    errors: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        self._check_members()
        if self.route == "v2":
            self._check_v2()
        if not self.claims and not self.errors:
            raise VerificationAttemptError("empty-attempt-unexplained")

    def _check_members(self) -> None:
        if self.route not in ROUTES:
            raise VerificationAttemptError("route-invalid")
        if self.identity is not None and not isinstance(self.identity, VerificationIdentity):
            raise VerificationAttemptError("identity-invalid")
        if any(not isinstance(claim, ClaimEvidence) for claim in self.claims):
            raise VerificationAttemptError("claim-invalid")
        if any(not isinstance(command, AttemptCommand) for command in self.commands):
            raise VerificationAttemptError("command-invalid")
        if any(not isinstance(error, str) for error in self.errors):
            raise VerificationAttemptError("attempt-invalid")

    def _check_v2(self) -> None:
        """The rules that only bind the route whose oracle is sealed (F2, F3, F8, F9)."""
        identity = self.identity
        if identity is None or identity.seal_sha256 is None or identity.closure_sha256 is None:
            raise VerificationAttemptError("identity-missing-on-v2")
        if identity.sealed_revision_id is None:
            raise VerificationAttemptError("identity-missing-on-v2")
        if any(command.authored_by == "planner" for command in self.commands):
            raise VerificationAttemptError("fence-on-v2-route")
        covered = {claim.contract_id: claim for claim in self.claims}
        if len(covered) != len(self.claims):
            # One contract with two claims is ambiguous evidence, and it would also let the
            # totals below add up while a contract is missing.
            raise VerificationAttemptError("claims-total-mismatch")
        excused = set(self.attested) | set(self.pending)
        if set(covered) & excused:
            raise VerificationAttemptError("claims-total-mismatch")
        # Every contract is accounted for exactly once. ``pending`` is a deploy qualifier, so a
        # contract that is attested *and* pending counts once -- the seal's own partition
        # (``acceptance_bundle`` requires ``pending`` ⊆ ``attested``), which is why this is a
        # coverage count and not a sum of the three list lengths.
        if len(covered) + len(excused) != self.contracts_total:
            raise VerificationAttemptError("claims-total-mismatch")
        for contract_id in self.kill_required:
            claim = covered.get(contract_id)
            if claim is None or claim.mutation is None:
                raise VerificationAttemptError("claim-mutation-missing")

    @property
    def blocking(self) -> bool:
        """Whether this attempt forbids the candidate from proceeding."""
        if self.errors:
            return True
        return any(not claim.proven for claim in self.claims)

    @property
    def first_reason(self) -> str:
        """One deterministic sentence naming the first thing that blocked, else ``""``."""
        if self.errors:
            return self.errors[0]
        for claim in self.claims:
            if claim.outcome != "passed":
                return f"{claim.contract_id} {claim.test_id}: {claim.outcome} at {claim.nodeid}"
            if claim.mutation is not None and claim.mutation.verdict != "PROVEN":
                return (
                    f"{claim.contract_id} {claim.test_id}: mutation {claim.mutation.verdict} "
                    f"({claim.mutation.operator} {claim.mutation.target})"
                )
        return ""

    def repair_nodeids(self) -> tuple[str, ...]:
        """The nodeids a coder must look at: exactly the claims that are not proven."""
        return tuple(claim.nodeid for claim in self.claims if not claim.proven)
