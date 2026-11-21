"""R1/R5/R6 oracles: the caller's disposition grant (E577).

The plan *requests* a disposition by reason; only a caller declaration makes the
request legal, and the declaration is the sole source of owner, evidence and
review date. These tests pin the grant's closed vocabulary, its canonical
evidence forms, its 30-day life, and the binding that joins a grant to a request.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest

from fa.inner_loop.plan_admission import (
    MAX_EVIDENCE_CHARS,
    EvidenceRef,
    PlanRefError,
    bind_dispositions,
    parse_dispositions,
)
from fa.inner_loop.plan_v2 import MAX_DISPOSITION_AGE_DAYS, MAX_DISPOSITIONS, PlanGraph, parse_plan
from tests.test_ai_native_plan_v2 import ROADMAP_DOCUMENT, plan_document, plan_graph

_DIGEST = "a" * 64
_TODAY = date(2026, 11, 20)


def _grant(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "reason": "HOST_READINESS",
        "owner": "W4",
        "evidence": f"doc:worklogs/demo/notes/readiness.md@sha256:{_DIGEST}",
        "reviewed_at": _TODAY.isoformat(),
    }
    record.update(overrides)
    return record


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(PlanRefError) as refused:
        callable_()
    return refused.value.rule


# -- the grant's shape -------------------------------------------------------


def test_no_declaration_means_no_grant() -> None:
    assert parse_dispositions(None) == ()
    assert parse_dispositions([]) == ()


def test_a_complete_declaration_parses_into_its_parts() -> None:
    (declaration,) = parse_dispositions([_grant()])

    assert declaration.reason == "HOST_READINESS"
    assert declaration.owner == "W4"
    assert declaration.evidence == EvidenceRef(kind="doc", target="worklogs/demo/notes/readiness.md", digest=_DIGEST)
    assert declaration.reviewed_at == _TODAY


@pytest.mark.parametrize(
    ("evidence", "kind", "target", "digest"),
    [
        (f"doc:knowledge/adr/0001.md@sha256:{_DIGEST}", "doc", "knowledge/adr/0001.md", _DIGEST),
        ("issue:FIRST-42", "issue", "FIRST-42", None),
        ("review:pr-91-round-2", "review", "pr-91-round-2", None),
    ],
)
def test_every_evidence_kind_is_typed_and_round_trips_to_its_text(
    evidence: str, kind: str, target: str, digest: str | None
) -> None:
    (declaration,) = parse_dispositions([_grant(evidence=evidence)])

    assert (declaration.evidence.kind, declaration.evidence.target, declaration.evidence.digest) == (
        kind,
        target,
        digest,
    )
    assert declaration.evidence.text() == evidence


@pytest.mark.parametrize("raw", ["nope", {"reason": "HOST_READINESS"}, 7])
def test_a_grant_must_be_a_list_of_records(raw: object) -> None:
    assert _rule(lambda: parse_dispositions(raw)) == "disposition-invalid"


def test_a_record_must_carry_exactly_the_four_fields() -> None:
    missing = _grant()
    del missing["reviewed_at"]
    extra = _grant()
    extra["note"] = "see the run sheet"

    assert _rule(lambda: parse_dispositions([missing])) == "disposition-invalid"
    assert _rule(lambda: parse_dispositions([extra])) == "disposition-invalid"


def test_the_grant_vocabulary_is_closed() -> None:
    assert _rule(lambda: parse_dispositions([_grant(reason="BECAUSE")])) == "disposition-reason-unratified"
    assert _rule(lambda: parse_dispositions([_grant(reason=7)])) == "disposition-reason-unratified"
    assert _rule(lambda: parse_dispositions([_grant(owner="coder")])) == "disposition-owner-invalid"
    assert _rule(lambda: parse_dispositions([_grant(owner=None)])) == "disposition-owner-invalid"


def test_the_grant_count_is_bounded() -> None:
    reasons = ["HOST_READINESS", "DEPLOYMENT_IDENTITY", "OWNER_APPROVAL", "DURABILITY_POWER_LOSS"]
    oversized = [_grant(reason=reasons[index % len(reasons)]) for index in range(MAX_DISPOSITIONS + 1)]

    assert _rule(lambda: parse_dispositions(oversized)) == "disposition-too-many"


def test_two_grants_for_one_reason_are_ambiguous() -> None:
    assert _rule(lambda: parse_dispositions([_grant(), _grant(owner="operator")])) == "disposition-duplicate-reason"


# -- the evidence reference (R6) ---------------------------------------------


@pytest.mark.parametrize(
    "evidence",
    [
        "readiness run sheet row L-RCPT-2/6",  # the old free-text form, refused on purpose
        "",
        "doc:worklogs/demo/notes/readiness.md",  # no digest
        f"doc:worklogs/demo/notes/readiness.md@sha256:{'a' * 63}",  # short digest
        f"doc:worklogs/demo/notes/readiness.md@sha256:{'A' * 64}",  # uppercase is not a digest
        "doc:@sha256:" + _DIGEST,
        "issue:42",
        "review:",
        f"doc:{'a' * (MAX_EVIDENCE_CHARS + 1)}@sha256:{_DIGEST}",
        None,
        7,
    ],
)
def test_an_untyped_or_malformed_reference_is_refused(evidence: object) -> None:
    assert _rule(lambda: parse_dispositions([_grant(evidence=evidence)])) == "disposition-evidence-invalid"


@pytest.mark.parametrize("reviewed_at", ["20-11-2026", "2026-11-20T00:00:00", "2026-13-01", "", 20261120, None])
def test_the_review_date_must_be_an_iso_date(reviewed_at: object) -> None:
    assert _rule(lambda: parse_dispositions([_grant(reviewed_at=reviewed_at)])) == "disposition-reviewed-at-invalid"


# -- the binding (R1) --------------------------------------------------------

_DISPOSED_INVARIANT = """### INV-2
KIND: HARD
TEXT: Host readiness is proven on the approved host.
EVIDENCE: NON_EXECUTABLE
DISPOSITION-REASON: HOST_READINESS
"""


_NO_REQUEST_INVARIANTS = """### INV-1
KIND: HARD
TEXT: The writer never publishes without a sealed acceptance revision.
EVIDENCE: TEST_REQUIRED

### INV-2
KIND: SOFT
TEXT: Host readiness is proven on the approved host.
EVIDENCE: TEST_REQUIRED
"""


def _graph() -> PlanGraph:
    increment = plan_document(
        invariants=f"### INV-1\nKIND: HARD\nTEXT: t\nEVIDENCE: TEST_REQUIRED\n\n{_DISPOSED_INVARIANT}"
    )
    return parse_plan(roadmap=ROADMAP_DOCUMENT, increment=increment)


def test_a_granted_request_carries_the_owner_and_the_reference() -> None:
    graph = bind_dispositions(_graph(), parse_dispositions([_grant()]), today=_TODAY)

    granted = {item.id: item for item in graph.invariants}["INV-2"]
    assert granted.reason == "HOST_READINESS"
    assert granted.owner == "W4"
    assert granted.evidence_ref == f"doc:worklogs/demo/notes/readiness.md@sha256:{_DIGEST}"
    # the request itself is untouched: the plan still says only *why*
    assert {item.id: item for item in _graph().invariants}["INV-2"].owner is None


def test_a_request_without_a_grant_never_binds() -> None:
    assert _rule(lambda: bind_dispositions(_graph(), (), today=_TODAY)) == "disposition-undeclared"


def test_a_grant_for_another_reason_does_not_authorise_this_one() -> None:
    other = parse_dispositions([_grant(reason="OWNER_APPROVAL")])

    assert _rule(lambda: bind_dispositions(_graph(), other, today=_TODAY)) == "disposition-undeclared"


@pytest.mark.parametrize("age", [0, MAX_DISPOSITION_AGE_DAYS])
def test_a_grant_inside_its_life_authorises(age: int) -> None:
    grant = parse_dispositions([_grant(reviewed_at=(_TODAY - timedelta(days=age)).isoformat())])

    assert bind_dispositions(_graph(), grant, today=_TODAY).invariants[1].owner in {"W4", None}


def test_a_grant_older_than_its_life_authorises_nothing() -> None:
    stale = parse_dispositions(
        [_grant(reviewed_at=(_TODAY - timedelta(days=MAX_DISPOSITION_AGE_DAYS + 1)).isoformat())]
    )

    assert _rule(lambda: bind_dispositions(_graph(), stale, today=_TODAY)) == "disposition-review-stale"


def test_a_stale_grant_is_refused_even_when_the_plan_does_not_use_it() -> None:
    """A stale review says the review is stale, not that some other claim is fine."""
    stale = parse_dispositions(
        [_grant(reviewed_at=(_TODAY - timedelta(days=MAX_DISPOSITION_AGE_DAYS + 1)).isoformat())]
    )

    assert _rule(lambda: bind_dispositions(plan_graph(), stale, today=_TODAY)) == "disposition-review-stale"


def test_a_grant_reviewed_in_the_future_is_refused() -> None:
    future = parse_dispositions([_grant(reviewed_at=(_TODAY + timedelta(days=1)).isoformat())])

    assert _rule(lambda: bind_dispositions(_graph(), future, today=_TODAY)) == "disposition-reviewed-at-invalid"


def test_a_plan_with_no_request_binds_unchanged() -> None:
    graph = plan_graph(invariants=_NO_REQUEST_INVARIANTS)

    assert bind_dispositions(graph, (), today=_TODAY) == graph
    assert bind_dispositions(_graph(), parse_dispositions([_grant()]), today=_TODAY).invariants[0].owner is None


def test_binding_is_a_pure_function_of_its_inputs() -> None:
    graph = _graph()
    grant = parse_dispositions([_grant()])

    first = bind_dispositions(graph, grant, today=_TODAY)
    second = bind_dispositions(graph, grant, today=_TODAY)
    assert first == second
    assert graph.invariants[1].owner is None  # the input graph is never mutated
