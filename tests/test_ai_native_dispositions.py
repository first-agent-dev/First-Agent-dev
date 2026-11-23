"""R1/R5/R6 oracles: the caller's disposition grant (E577).

The plan *requests* a disposition by reason; only a caller declaration makes the
request legal, and the declaration is the sole source of owner, evidence and
review date. These tests pin the grant's closed vocabulary, its canonical
evidence forms, its 30-day life, and the binding that joins a grant to a request.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from fa.inner_loop.plan_admission import (
    MAX_EVIDENCE_CHARS,
    EvidenceRef,
    PlanRefError,
    bind_dispositions,
    parse_dispositions,
)
from fa.inner_loop.plan_v2 import (
    DISPOSITION_REASONS as _REASONS,
)
from fa.inner_loop.plan_v2 import (
    DISPOSITION_ROUTES,
    EVIDENCE_ROUTES,
    MAX_DISPOSITION_AGE_DAYS,
    MAX_DISPOSITIONS,
    PlanGraph,
    parse_plan,
)
from fa.inner_loop.tools.workspace_port import PortRead, WorkspacePortError
from fa.inner_loop.workflow_controller import _granted_dispositions as resolve_grants
from tests.test_ai_native_plan_v2 import ROADMAP_DOCUMENT, plan_document, plan_graph

_DIGEST = "a" * 64
_TODAY = date(2026, 11, 20)
_PROBE_REF = "probe:worklogs/demo/acceptance/probes/host_readiness.sh@host:w4-ubuntu"
_DOC_REF = f"doc:worklogs/demo/notes/approval.md@sha256:{_DIGEST}"


def _grant(**overrides: object) -> dict[str, object]:
    """A complete, legal grant: the default reason is a host claim, so is its artifact.

    D-V2-12 made the artifact's kind a function of the reason's route, so a default
    that paired ``HOST_READINESS`` with a document would describe a grant the
    system refuses. Tests about *documents* (the R6 section) therefore ask for the
    ``OWNER_APPROVAL`` route explicitly.
    """
    record: dict[str, object] = {
        "reason": "HOST_READINESS",
        "owner": "W4",
        "evidence": _PROBE_REF,
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
    assert declaration.evidence == EvidenceRef(
        kind="probe", target="worklogs/demo/acceptance/probes/host_readiness.sh", host="w4-ubuntu"
    )
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
    # A reference a human can open belongs to the approval lane (D-V2-12).
    (declaration,) = parse_dispositions([_grant(reason="OWNER_APPROVAL", evidence=evidence)])

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
TEXT: Host readiness is proven on the approved host.
EVIDENCE: NON_EXECUTABLE
DISPOSITION-REASON: HOST_READINESS
"""


_NO_REQUEST_INVARIANTS = """### INV-1
TEXT: The writer never publishes without a sealed acceptance revision.
EVIDENCE: TEST_REQUIRED

### INV-2
TEXT: Host readiness is proven on the approved host.
EVIDENCE: TEST_REQUIRED
"""


def _graph() -> PlanGraph:
    increment = plan_document(invariants=f"### INV-1\nTEXT: t\nEVIDENCE: TEST_REQUIRED\n\n{_DISPOSED_INVARIANT}")
    return parse_plan(roadmap=ROADMAP_DOCUMENT, increment=increment)


def test_a_granted_request_carries_the_owner_and_the_reference() -> None:
    graph = bind_dispositions(_graph(), parse_dispositions([_grant()]), today=_TODAY)

    granted = {item.id: item for item in graph.invariants}["INV-2"]
    assert granted.reason == "HOST_READINESS"
    assert granted.owner == "W4"
    assert granted.evidence_ref == _PROBE_REF
    assert granted.reviewed_at == _TODAY.isoformat()
    # the request itself is untouched: the plan still says only *why*
    assert {item.id: item for item in _graph().invariants}["INV-2"].owner is None


def test_a_request_without_a_grant_never_binds() -> None:
    assert _rule(lambda: bind_dispositions(_graph(), (), today=_TODAY)) == "disposition-undeclared"


def test_a_grant_for_another_reason_does_not_authorise_this_one() -> None:
    other = parse_dispositions([_grant(reason="OWNER_APPROVAL", evidence=_DOC_REF)])

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


#: Every contract tested, so no invariant asks for a grant: the plan this test needs
#: in order to observe "binding with nothing is a no-op". Before D-V2-10 the second
#: contract could simply go uncovered, which is exactly the hole that was closed.
_TWO_TESTED_CONTRACTS = """## SLICE1: sealed acceptance
STEPS: prescriptive
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
  CT-1.2 [CONSTRAINT] INV: INV-2: readiness is proven on the host
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish
  TEST-ID: TEST-1.2 | CT: CT-1.2 | SELECTOR: worklogs/demo/acceptance/tests/test_publish.py::test_publish2
KILL-TARGETS:
STEP-EXIT-CHECKS:
  CHECK-ID: CHECK-1 | STEP: STEP1 | TEST-ID[]: TEST-1.1
- [ ] STEP1: publish through the sealed authority. EXIT-CHECK: CHECK-1
"""


def test_a_plan_with_no_request_binds_unchanged() -> None:
    graph = plan_graph(invariants=_NO_REQUEST_INVARIANTS, slice_body=_TWO_TESTED_CONTRACTS)

    assert bind_dispositions(graph, (), today=_TODAY) == graph
    assert bind_dispositions(_graph(), parse_dispositions([_grant()]), today=_TODAY).invariants[0].owner is None


def test_binding_is_a_pure_function_of_its_inputs() -> None:
    graph = _graph()
    grant = parse_dispositions([_grant()])

    first = bind_dispositions(graph, grant, today=_TODAY)
    second = bind_dispositions(graph, grant, today=_TODAY)
    assert first == second
    assert graph.invariants[1].owner is None  # the input graph is never mutated


# -- the route decides the artifact (D-V2-12) -------------------------------

_HOST_PROBE_REASONS = sorted(reason for reason, route in DISPOSITION_ROUTES.items() if route == "HOST_PROBE")


@pytest.mark.parametrize("reason", _HOST_PROBE_REASONS)
def test_a_host_claim_is_discharged_by_a_probe_not_by_a_document(reason: str) -> None:
    """The whole point of the route: "we cannot test it here" names *where* it is tested.

    Before D-V2-12 all four reasons accepted every reference kind, so a review
    document could stand in for a host run and the two cost the same signature.
    """
    (probe,) = parse_dispositions([_grant(reason=reason, evidence=_PROBE_REF)])
    assert probe.evidence.kind == "probe"
    assert probe.evidence.host == "w4-ubuntu"

    assert _rule(lambda: parse_dispositions([_grant(reason=reason, evidence=_DOC_REF)])) == (
        "disposition-evidence-route-mismatch"
    )
    assert _rule(lambda: parse_dispositions([_grant(reason=reason, evidence="issue:FIRST-42")])) == (
        "disposition-evidence-route-mismatch"
    )


@pytest.mark.parametrize("evidence", [_DOC_REF, "issue:FIRST-42", "review:pr-91-round-2"])
def test_an_approval_takes_a_reference_a_human_can_open(evidence: str) -> None:
    (approval,) = parse_dispositions([_grant(reason="OWNER_APPROVAL", evidence=evidence)])

    assert approval.evidence.text() == evidence


def test_an_approval_refuses_a_probe() -> None:
    """`APPROVAL` is the route with no artifact to run; a probe there is a category error."""
    assert _rule(lambda: parse_dispositions([_grant(reason="OWNER_APPROVAL", evidence=_PROBE_REF)])) == (
        "disposition-evidence-route-mismatch"
    )


@pytest.mark.parametrize(
    "evidence",
    [
        "probe:/etc/passwd@host:w4-ubuntu",  # absolute
        "probe:worklogs/demo/acceptance/../../evil.sh@host:w4-ubuntu",  # traversal
        "probe:worklogs/demo/notes/p.sh@host:w4-ubuntu",  # outside the sealed tree
        "probe:worklogs/demo/acceptance/p.sh",  # no host
        "probe:worklogs/demo/acceptance/p.sh@host:",  # empty host
        "probe:worklogs/DEMO/acceptance/p.sh@host:w4",  # slug shape
    ],
)
def test_a_probe_names_a_file_inside_a_project_and_a_host(evidence: str) -> None:
    """Shape only: whether the file *exists* is the seal's check, not admission's."""
    assert _rule(lambda: parse_dispositions([_grant(evidence=evidence)])) == "disposition-evidence-invalid"


def test_the_route_axis_is_closed_and_derived_from_the_reason() -> None:
    """A new reason must arrive with its route; the planner never chooses one."""
    assert set(DISPOSITION_ROUTES) == set(_REASONS)
    assert set(DISPOSITION_ROUTES.values()) <= set(EVIDENCE_ROUTES)
    assert "TEST" not in set(DISPOSITION_ROUTES.values()), "a disposition is never the executable route"


# -- resolving a doc: grant against bytes (R6) ------------------------------


class _Port:
    """A pinned view double: one stored read, or one refusal code."""

    def __init__(self, read: PortRead | None = None, code: str = "denied") -> None:
        self.read = read
        self.code = code
        self.paths: list[str] = []

    def read_file(self, path: str, *, offset_bytes: int = 0, max_bytes: int = 1024 * 1024) -> PortRead:
        self.paths.append(path)
        if self.read is None:
            raise WorkspacePortError(self.code)
        return self.read


def _substrate(port: _Port) -> object:
    return SimpleNamespace(port=port)


def _grant_for(evidence: str) -> tuple[object, ...]:
    """A document-backed grant: the ``OWNER_APPROVAL`` route, by D-V2-12."""
    return parse_dispositions([_grant(reason="OWNER_APPROVAL", evidence=evidence)])


def test_a_matching_doc_grant_is_returned_unchanged() -> None:
    port = _Port(PortRead(content="readiness: pass\n", sha256=_DIGEST, eof=True))
    granted = _grant_for(_DOC_REF)

    assert resolve_grants(port, granted) == granted
    assert port.paths == ["worklogs/demo/notes/approval.md"]


def test_a_missing_doc_refuses_the_grant() -> None:
    assert _rule(lambda: resolve_grants(_Port(), _grant_for(_DOC_REF))) == "disposition-evidence-missing"


def test_bytes_that_do_not_match_the_digest_refuse_the_grant() -> None:
    port = _Port(PortRead(content="readiness: pass\n", sha256="b" * 64, eof=True))

    assert _rule(lambda: resolve_grants(port, _grant_for(_DOC_REF))) == "disposition-evidence-mismatch"


def test_a_file_too_large_for_one_bounded_read_refuses_the_grant() -> None:
    port = _Port(PortRead(content="...", sha256=_DIGEST, eof=False))

    assert _rule(lambda: resolve_grants(port, _grant_for(_DOC_REF))) == "disposition-evidence-invalid"


def test_a_path_the_substrate_will_not_name_is_an_invalid_reference() -> None:
    traversal = _Port(code="invalid_request")

    assert _rule(lambda: resolve_grants(traversal, _grant_for(_DOC_REF))) == "disposition-evidence-invalid"


def test_a_doc_grant_without_a_view_is_refused_before_the_read() -> None:
    """There is no "verify without a view" path: the caller must supply a pinned one.

    Before D-V2-9 the installer accepted ``None`` and answered with its own rule. The
    authoring route refuses earlier, at ``bootstrap-unreadable``, because a run with no
    pinned view has no revision to admit either -- so the guarantee is now that the
    verification is unreachable without a view rather than that it names one.
    """
    with pytest.raises(AttributeError):  # no port, nothing to read: unreachable by design
        resolve_grants(None, _grant_for(_DOC_REF))  # type: ignore[arg-type]


@pytest.mark.parametrize("evidence", ["issue:FIRST-42", "review:pr-91-round-2"])
def test_a_reference_this_system_cannot_resolve_never_reads_anything(evidence: str) -> None:
    port = _Port()

    assert resolve_grants(port, _grant_for(evidence)) == _grant_for(evidence)
    assert port.paths == []  # no view was needed, and none was invented
