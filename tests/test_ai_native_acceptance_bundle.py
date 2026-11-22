"""C0 oracles for the controller-minted acceptance seal (STEP9A item 1)."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.acceptance_bundle import (
    MAX_ATTESTED,
    SCHEMA_VERSION,
    AcceptanceBundle,
    AcceptanceBundleError,
    PinnedIdentity,
    SealedSelector,
    load_seal,
    mint_seal,
    seal_bytes,
    seal_payload,
    verify_plan,
    verify_revision,
    verify_sealed_root,
    write_seal,
)
from fa.inner_loop.acceptance_closure import collect_acceptance_closure
from fa.inner_loop.acceptance_collection import AcceptanceCollectionError, verify_sealed_acceptance
from fa.inner_loop.plan_v2 import EvidenceMode, PlanV2Error, contract_evidence
from fa.inner_loop.slice_verification import JUNIT_BLOCK_END, JUNIT_BLOCK_START, CommandOutcome, CommandResult
from tests.test_ai_native_plan_v2 import GRANT_PROBE_FILES, granted_graph, plan_document, plan_graph
from tests.test_slice_verification_runner import _inband_executor

#: A file name the seal writer is given explicitly; custody is the store's business now.
_SEAL_FILE = "acceptance.seal.json"
_SEALED_ROOT = "worklogs/demo/acceptance"
_TEST_PATH = f"{_SEALED_ROOT}/tests/test_publish.py"
_NODEID = f"{_TEST_PATH}::test_publish"
_REVISION = "rev-" + "0" * 32
_PLAN = plan_document()
_PLAN_BYTES = _PLAN.encode("utf-8")
_NODEID_SECOND = f"{_TEST_PATH}::test_publish2"
_COLLECTED = {_TEST_PATH: [_NODEID, _NODEID_SECOND]}
_SLICE_WITH_FOREIGN_SELECTOR = """## SLICE1: sealed acceptance
STEPS: prescriptive
CONTRACTS:
  CT-1.1 [FUNCTIONAL] INV: INV-1: publication requires a sealed selection
ACCEPTANCE:
  TEST-ID: TEST-1.1 | CT: CT-1.1 | SELECTOR: worklogs/other/acceptance/tests/test_publish.py::test_publish
KILL-TARGETS:
STEP-EXIT-CHECKS:
"""

_INI = """[pytest]
python_files = test_*.py
addopts = -q --strict-markers
testpaths = tests
"""
_TEST = """from support.helper import publish


def test_publish():
    assert publish() == "published"


def test_publish2():
    assert publish() == "published"
"""
_HELPER = """def publish():
    return "published"
"""


def _sealed_tree(tmp_path: Path) -> Path:
    root = tmp_path / "worklogs" / "demo" / "acceptance"
    (root / "tests").mkdir(parents=True)
    (root / "support").mkdir()
    (root / "probes").mkdir()
    (root / "pytest.ini").write_text(_INI, encoding="utf-8")
    (root / "conftest.py").write_text("import pytest\n", encoding="utf-8")
    (root / "support" / "helper.py").write_text(_HELPER, encoding="utf-8")
    (root / "tests" / "test_publish.py").write_text(_TEST, encoding="utf-8")
    # D-V2-12: an attested HOST_PROBE names an artifact the seal must find in the
    # closure, so the fixture tree carries every probe its grants refer to.
    for probe in GRANT_PROBE_FILES:
        (root / "probes" / Path(probe).name).write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return root


def _mint(root: Path, **overrides: Any) -> AcceptanceBundle:
    arguments: dict[str, Any] = {
        # The seal grades *granted* evidence: a bare parse still carries only the
        # plan's request (R1), and grading a request as attested is the defect
        # P1-1 named (E585).
        "graph": granted_graph(),
        "plan_bytes": _PLAN_BYTES,
        "revision_id": _REVISION,
        "sealed_root": _SEALED_ROOT,
        "acceptance_root": root,
        "collected": _COLLECTED,
    }
    arguments.update(overrides)
    return mint_seal(**arguments)


def _rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(AcceptanceBundleError) as refused:
        callable_()
    return refused.value.rule


def _rehash(record: Mapping[str, Any]) -> bytes:
    """A hostile record that is *internally consistent*, so fields get read."""
    body = {key: value for key, value in record.items() if key != "seal_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    sealed = dict(body)
    sealed["seal_sha256"] = hashlib.sha256(canonical).hexdigest()
    return json.dumps(sealed, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _hostile(bundle: AcceptanceBundle, **overrides: Any) -> bytes:
    record = json.loads(seal_bytes(bundle))
    record.update(overrides)
    return _rehash(record)


# -- minting ----------------------------------------------------------------


def test_mints_a_seal_bound_to_plan_revision_closure_and_nodeids(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)

    assert bundle.plan_sha256 == hashlib.sha256(_PLAN_BYTES).hexdigest()
    assert bundle.revision_id == _REVISION
    assert bundle.sealed_root == _SEALED_ROOT
    assert bundle.mode == "A"
    assert bundle.identity == ()
    assert bundle.supersedes_sha256 is None
    assert bundle.closure.digest == collect_acceptance_closure(root).digest
    assert [entry.path for entry in bundle.closure.files] == [
        "conftest.py",
        "probes/deployment_identity.sh",
        "probes/host_readiness.sh",
        "probes/power_loss.sh",
        "pytest.ini",
        "support/helper.py",
        "tests/test_publish.py",
    ]
    assert bundle.selectors == (SealedSelector(test_id="TEST-1.1", ct_id="CT-1.1", selector=_NODEID, nodeid=_NODEID),)
    assert bundle.nodeids() == {"TEST-1.1": _NODEID}


def test_the_seal_digest_covers_every_field_but_itself(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    record = json.loads(seal_bytes(bundle))

    body = {key: value for key, value in record.items() if key != "seal_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    assert record["seal_sha256"] == hashlib.sha256(canonical).hexdigest()
    assert record["schema_version"] == SCHEMA_VERSION
    assert record["kind"] == "ACCEPTANCE-BUNDLE"
    assert b" " not in seal_bytes(bundle)


def test_the_same_inputs_always_mint_the_same_bytes(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    identity = (PinnedIdentity(name="uv-lock", sha256="a" * 64), PinnedIdentity(name="nodeid-plugin", sha256="b" * 64))

    first = _mint(root, identity=identity)
    second = _mint(root, identity=tuple(reversed(identity)))

    assert seal_bytes(first) == seal_bytes(second)
    assert [pin.name for pin in second.identity] == ["nodeid-plugin", "uv-lock"]


def test_a_superseding_seal_must_name_a_real_digest(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)

    assert _rule(lambda: _mint(root, supersedes_sha256="not-a-digest")) == "supersedes-invalid"


def test_two_identity_pins_cannot_share_one_name(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    duplicated = (
        PinnedIdentity(name="uv-lock", sha256="a" * 64),
        PinnedIdentity(name="uv-lock", sha256="b" * 64),
    )

    assert _rule(lambda: _mint(root, identity=duplicated)) == "identity-duplicate"


def test_an_identity_pin_needs_a_strict_label_and_digest(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    bad_label = (PinnedIdentity(name="Uv Lock", sha256="a" * 64),)
    bad_digest = (PinnedIdentity(name="uv-lock", sha256="A" * 64),)

    assert _rule(lambda: _mint(root, identity=bad_label)) == "identity-label-invalid"
    assert _rule(lambda: _mint(root, identity=bad_digest)) == "identity-digest-invalid"


def test_a_seal_round_trips_through_its_own_serialization(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    assert load_seal(seal_bytes(bundle)) == bundle
    assert seal_bytes(load_seal(seal_bytes(bundle))) == seal_bytes(bundle)


def test_a_superseding_seal_names_its_predecessor_and_leaves_it_readable(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    first = _mint(root)
    second = _mint(root, supersedes_sha256=first.seal_sha256)

    assert second.supersedes_sha256 == first.seal_sha256
    assert load_seal(seal_bytes(first)).seal_sha256 == first.seal_sha256
    assert second.seal_sha256 != first.seal_sha256


# -- refusal: mint inputs ---------------------------------------------------


@pytest.mark.parametrize("mode", ["B", "b", "", "C", "A ", None, 1])
def test_only_visibility_mode_a_is_implemented(tmp_path: Path, mode: Any) -> None:
    root = _sealed_tree(tmp_path)
    expected = "visibility-mode-unsupported" if mode == "B" else "visibility-mode-invalid"

    assert _rule(lambda: _mint(root, mode=mode)) == expected


@pytest.mark.parametrize(
    "revision",
    ["rev-", "rev-xyz", "rev-" + "0" * 31, "rev-" + "A" * 32, "0" * 32, "", None],
)
def test_an_unusable_revision_id_is_refused(tmp_path: Path, revision: Any) -> None:
    root = _sealed_tree(tmp_path)

    assert _rule(lambda: _mint(root, revision_id=revision)) == "revision-invalid"


@pytest.mark.parametrize("plan_bytes", [b"", "text", None, 7])
def test_the_plan_must_be_real_bytes(tmp_path: Path, plan_bytes: Any) -> None:
    root = _sealed_tree(tmp_path)

    assert _rule(lambda: _mint(root, plan_bytes=plan_bytes)) == "plan-invalid"


@pytest.mark.parametrize(
    "sealed_root",
    ["worklogs/demo", "worklogs/demo/acceptance/", "/worklogs/demo/acceptance", "../demo/acceptance", "", None],
)
def test_the_sealed_root_must_be_the_acceptance_directory_of_one_worklog(tmp_path: Path, sealed_root: Any) -> None:
    root = _sealed_tree(tmp_path)

    assert _rule(lambda: _mint(root, sealed_root=sealed_root)) == "sealed-root-invalid"


def test_the_acceptance_tree_must_be_named_acceptance(tmp_path: Path) -> None:
    other = tmp_path / "elsewhere"
    other.mkdir()

    assert _rule(lambda: _mint(other, acceptance_root=other)) == "sealed-root-invalid"


def test_an_incomplete_nodeid_report_never_reaches_the_seal(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)

    with pytest.raises(PlanV2Error):
        _mint(root, collected={})


def test_an_ambiguous_nodeid_report_never_reaches_the_seal(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    collected = {_TEST_PATH: [f"{_NODEID}[a]", f"{_NODEID}[b]"]}

    with pytest.raises(PlanV2Error):
        _mint(root, collected=collected)


def test_a_selector_outside_the_sealed_bytes_is_refused(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    other = "worklogs/other/acceptance/tests/test_publish.py"
    graph = plan_graph(slice_body=_SLICE_WITH_FOREIGN_SELECTOR)

    assert _rule(lambda: _mint(root, graph=graph, collected={other: [f"{other}::test_publish"]})) == (
        "selector-outside-closure"
    )


def test_an_unadmitted_plan_never_reaches_the_seal() -> None:
    with pytest.raises(PlanV2Error):
        plan_graph(slice_body="## SLICE1: broken\nSTEPS: outcome\n")


# -- refusal: writing --------------------------------------------------------


def test_a_seal_is_written_once_with_fixed_mode(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    path = tmp_path / "worklogs" / "demo" / _SEAL_FILE

    assert write_seal(bundle, path) == path
    assert path.read_bytes() == seal_bytes(bundle)
    assert os.stat(path).st_mode & 0o777 == 0o644
    assert load_seal(path.read_bytes()) == bundle


def test_an_existing_seal_is_never_replaced(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    path = tmp_path / "worklogs" / "demo" / _SEAL_FILE
    write_seal(bundle, path)

    assert _rule(lambda: write_seal(_mint(root, supersedes_sha256=bundle.seal_sha256), path)) == "seal-exists"
    assert path.read_bytes() == seal_bytes(bundle)


@pytest.mark.parametrize("path", [None, "seal.json", 3])
def test_a_seal_path_must_be_a_path(tmp_path: Path, path: Any) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: write_seal(bundle, path)) == "seal-path-invalid"


def test_a_missing_parent_directory_is_refused(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: write_seal(bundle, tmp_path / "absent" / _SEAL_FILE)) == "seal-path-invalid"


# -- refusal: loading a hostile record --------------------------------------


@pytest.mark.parametrize("raw", [b"", b"not json", b"\xff\xfe", 7, None])
def test_an_unreadable_record_is_malformed(tmp_path: Path, raw: Any) -> None:
    assert _rule(lambda: load_seal(raw)) == "seal-malformed"


def test_an_oversized_record_is_refused() -> None:
    assert _rule(lambda: load_seal(b" " * (1024**2 + 1))) == "seal-malformed"


# A literal version would rot the moment the schema moves: S2 moved this from 1 to
# 2, and the old literal ``2`` then read as *current*. The neighbours of the current
# version are what "unknown" means, whichever version is current.
@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": SCHEMA_VERSION + 1},
        {"schema_version": SCHEMA_VERSION - 1},
        {"kind": "BUNDLE"},
        {},
    ],
)
def test_an_unknown_schema_is_refused(tmp_path: Path, overrides: dict[str, Any]) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    raw = b"{}" if not overrides else _hostile(bundle, **overrides)

    assert _rule(lambda: load_seal(raw)) == "seal-schema-unknown"


def test_every_scaffolded_project_artifact_is_inside_a_protected_path() -> None:
    """Layout and enforcement are two modules; this binds them (CT-3.3/INV-07).

    ``project_scaffold`` owns the layout and lives in the inner loop; the refusal is
    the authority's (``execution.workspace.sealed_project_paths``) and the execution
    layer does not import upward. So the two are bound here instead of by a shared
    constant: every path the harness scaffolds -- and therefore every artifact a later
    admitted plan speaks for -- falls inside the directory a coder view cannot write,
    including the acceptance closure the seal digests.
    """
    from fa.execution.workspace import sealed_project_paths
    from fa.inner_loop.project_scaffold import scaffold_paths

    paths = scaffold_paths("demo")
    (protected,) = sealed_project_paths(paths[0])

    assert protected == "worklogs/demo"
    for path in paths:
        assert path.startswith(f"{protected}/"), path
    assert any(path.startswith(f"{protected}/acceptance/") for path in paths)
    assert any("/increments/" in path for path in paths)


# -- S2: seal totality, and the record of who carried the claim (P4-8/D-V2-12) --


def test_the_seal_carries_the_attestation_record(tmp_path: Path) -> None:
    """The record a reader could never reconstruct: who, on what, when, over which text."""
    bundle = _mint(_sealed_tree(tmp_path))

    assert bundle.contracts_total == 2
    assert bundle.attested == ("CT-1.2",)
    assert bundle.pending == ("CT-1.2",), "a host claim is a debt, not a decision"
    (record,) = bundle.attestations
    assert (record.contract_id, record.invariant_id, record.reason, record.route) == (
        "CT-1.2",
        "INV-2",
        "HOST_READINESS",
        "HOST_PROBE",
    )
    assert record.owner == "W4" and record.reviewed_at == "2026-11-19"
    assert record.artifact.startswith("probe:") and record.artifact.endswith("@host:w4-ubuntu")
    # Inside the digest, not beside it: an edited record breaks the seal.
    record_bytes = json.loads(seal_bytes(bundle))
    assert record_bytes["attestations"][0]["scope_sha256"] == record.scope_sha256
    assert record_bytes["contracts_total"] == 2


def test_a_seal_is_refused_while_a_contract_has_no_evidence(tmp_path: Path) -> None:
    """The hole S2 closes: a plan with an uncovered contract could be sealed.

    ``mint_seal`` used to record ``attested`` and nothing else, so a contract that
    was neither selected nor attested simply vanished from the record while the seal
    still read as the oracle for the whole plan.
    """
    assert _rule(lambda: _mint(_sealed_tree(tmp_path), graph=plan_graph())) == "seal-uncovered-contracts"


def test_a_probe_the_closure_does_not_hold_is_refused(tmp_path: Path) -> None:
    """A promise to run something that does not exist is not evidence.

    Admission cannot see the tree; the seal can, so this is where the artifact is
    checked. The rule names the artifact, not the input.
    """
    root = _sealed_tree(tmp_path)
    (root / "probes" / "host_readiness.sh").unlink()

    assert _rule(lambda: _mint(root)) == "seal-attestation-artifact-missing"


def test_a_graph_that_does_not_describe_the_plan_bytes_is_refused(tmp_path: Path) -> None:
    """``plan_sha256`` must name a plan the graph actually describes (D-V2-12)."""
    other = plan_document(
        slice_body="## SLICE1: other\nSTEPS: outcome\nCONTRACTS:\nACCEPTANCE:\nKILL-TARGETS:\nSTEP-EXIT-CHECKS:\n"
    )

    assert _rule(lambda: _mint(_sealed_tree(tmp_path), plan_bytes=other.encode("utf-8"))) == (
        "seal-plan-graph-mismatch"
    )


def test_a_block_that_does_not_describe_the_attested_set_is_refused(tmp_path: Path) -> None:
    """``load_seal`` re-proves the record's arithmetic instead of trusting the digest."""
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: load_seal(_hostile(bundle, attestations=[]))) == "seal-attestation-mismatch"


def test_a_pending_list_that_is_not_the_host_subset_is_refused(tmp_path: Path) -> None:
    """``pending`` is derived, so a record that drops it is describing another plan."""
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: load_seal(_hostile(bundle, pending=[]))) == "seal-attestation-mismatch"


def test_a_route_that_contradicts_its_reason_is_refused(tmp_path: Path) -> None:
    """The route is a function of the reason; a record cannot claim both halves."""
    bundle = _mint(_sealed_tree(tmp_path))
    record = json.loads(seal_bytes(bundle))["attestations"][0]
    record["route"] = "APPROVAL"

    assert _rule(lambda: load_seal(_hostile(bundle, attestations=[record]))) == "seal-attestation-route-invalid"


def test_the_totals_identity_is_re_checked_on_load(tmp_path: Path) -> None:
    """Covered + attested == total is the seal's whole claim; it is re-proved on read."""
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: load_seal(_hostile(bundle, contracts_total=3))) == "seal-totality-mismatch"


def test_an_edited_field_breaks_the_seal_digest(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    record = json.loads(seal_bytes(bundle))
    record["mode"] = "A"
    record["plan_sha256"] = "f" * 64

    assert _rule(lambda: load_seal(json.dumps(record).encode("utf-8"))) == "seal-digest-mismatch"


@pytest.mark.parametrize(
    "overrides",
    [
        {"files": []},
        {"files": "tests"},
        {"files": [{"path": "pytest.ini"}]},
        {"files": [{"path": "pytest.ini", "sha256": "x", "size": 1, "mode": 420}]},
        {"files": [{"path": "pytest.ini", "sha256": "a" * 64, "size": -1, "mode": 420}]},
        {"files": [{"path": "pytest.ini", "sha256": "a" * 64, "size": 1, "mode": 999}]},
        {"selectors": []},
        {"selectors": [{"test_id": "TEST-1.1"}]},
        {"selectors": [{"test_id": "", "ct_id": "CT-1.1", "selector": _NODEID, "nodeid": _NODEID}]},
        {"identity": [{"name": "Bad Label", "sha256": "a" * 64}]},
        {"identity": "uv-lock"},
        {"plan_sha256": "short"},
        {"closure_sha256": None},
        {"sealed_root": "worklogs/demo"},
        {"revision_id": "rev-1"},
        {"mode": "B"},
        {"supersedes_sha256": "nope"},
    ],
)
def test_a_well_formed_but_hostile_record_is_refused(tmp_path: Path, overrides: dict[str, Any]) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    with pytest.raises(AcceptanceBundleError):
        load_seal(_hostile(bundle, **overrides))


def test_a_record_with_the_same_file_twice_is_refused(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    row = json.loads(seal_bytes(bundle))["files"][0]

    assert _rule(lambda: load_seal(_hostile(bundle, files=[row, row]))) == "seal-malformed"


def test_a_record_with_two_rows_for_one_test_id_is_refused(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    row = json.loads(seal_bytes(bundle))["selectors"][0]

    assert _rule(lambda: load_seal(_hostile(bundle, selectors=[row, row]))) == "seal-malformed"


# -- verification against the workspace ------------------------------------


def test_an_untouched_tree_still_verifies_and_yields_its_payload(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)

    verify_sealed_root(bundle, root)
    payload = seal_payload(bundle, root)

    assert set(payload) == {entry.path for entry in bundle.closure.files}
    assert payload["tests/test_publish.py"] == _TEST.encode("utf-8")


def test_a_changed_sealed_byte_is_refused(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    (root / "tests" / "test_publish.py").write_text(_TEST.replace("published", "silent"), encoding="utf-8")

    assert _rule(lambda: verify_sealed_root(bundle, root)) == "seal-byte-drift"
    assert _rule(lambda: seal_payload(bundle, root)) == "seal-drift"


def test_a_deleted_sealed_file_is_refused(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    (root / "support" / "helper.py").unlink()

    assert _rule(lambda: verify_sealed_root(bundle, root)) == "seal-missing-bytes"
    assert _rule(lambda: seal_payload(bundle, root)) == "seal-missing-bytes"


def test_an_added_file_is_refused(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    (root / "tests" / "test_smuggled.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")

    assert _rule(lambda: verify_sealed_root(bundle, root)) == "seal-extra-bytes"
    assert _rule(lambda: seal_payload(bundle, root)) == "seal-extra-bytes"


def test_a_record_whose_closure_digest_contradicts_its_file_table_is_refused(tmp_path: Path) -> None:
    root = _sealed_tree(tmp_path)
    tampered = load_seal(_hostile(_mint(root), closure_sha256="b" * 64))

    assert _rule(lambda: verify_sealed_root(tampered, root)) == "seal-digest-mismatch"


def test_an_unreadable_tree_fails_closed(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: verify_sealed_root(bundle, tmp_path / "absent")) == "closure-root-unreadable"


def test_the_seal_is_bound_to_the_plan_bytes_it_was_minted_from(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    verify_plan(bundle, _PLAN_BYTES)
    assert _rule(lambda: verify_plan(bundle, _PLAN_BYTES + b"\n")) == "plan-digest-mismatch"
    assert _rule(lambda: verify_plan(bundle, b"")) == "plan-invalid"


def test_the_seal_is_bound_to_one_immutable_revision(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    verify_revision(bundle, _REVISION)
    assert _rule(lambda: verify_revision(bundle, "rev-" + "1" * 32)) == "seal-stale"
    assert _rule(lambda: verify_revision(bundle, "rev-1")) == "revision-invalid"


# -- R2: the seal names what it cannot prove --------------------------------

#: The default plan with INV-2's disposition removed: the same two contracts, no
#: attestation anywhere, so CT-1.2 is merely *uncovered* rather than attested.
_NO_DISPOSITION_INVARIANTS = """### INV-1
TEXT: The writer never publishes without a sealed acceptance revision.
EVIDENCE: TEST_REQUIRED

### INV-2
TEXT: Host readiness is proven on the approved host.
EVIDENCE: TEST_REQUIRED
"""
#: Both contracts tested, no request anywhere: the plan that legitimately produces a
#: seal with an empty attestation. Before D-V2-10 the second contract could go
#: uncovered instead, which is the shape admission now refuses.
_NO_DISPOSITION_SLICE = """## SLICE1: sealed acceptance
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
_NO_DISPOSITION_PLAN = plan_document(invariants=_NO_DISPOSITION_INVARIANTS, slice_body=_NO_DISPOSITION_SLICE)


def _executable_only(root: Path) -> AcceptanceBundle:
    return _mint(
        root,
        graph=plan_graph(invariants=_NO_DISPOSITION_INVARIANTS, slice_body=_NO_DISPOSITION_SLICE),
        plan_bytes=_NO_DISPOSITION_PLAN.encode("utf-8"),
    )


def test_the_seal_names_the_contracts_that_only_a_disposition_covers(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    assert bundle.attested == ("CT-1.2",)
    assert json.loads(seal_bytes(bundle))["attested"] == ["CT-1.2"]
    assert set(bundle.nodeids()) == {"TEST-1.1"}  # custody is unchanged by attestation


def test_a_plan_that_disposes_of_nothing_seals_an_empty_attestation(tmp_path: Path) -> None:
    """No request anywhere: every contract is executable, so nothing is attested.

    D-V2-10 made the neighbouring shape -- a contract with neither a selector nor a
    request -- unreachable at admission, so an empty ``attested`` list now means
    "everything here is tested", not "one contract slipped through".
    """
    bundle = _executable_only(_sealed_tree(tmp_path))

    graded = contract_evidence(plan_graph(invariants=_NO_DISPOSITION_INVARIANTS, slice_body=_NO_DISPOSITION_SLICE))
    assert graded == {"CT-1.1": EvidenceMode.EXECUTABLE, "CT-1.2": EvidenceMode.EXECUTABLE}
    assert bundle.attested == ()
    assert json.loads(seal_bytes(bundle))["attested"] == []
    assert load_seal(seal_bytes(bundle)).attested == ()


def test_the_seal_digest_covers_the_attestation(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    record = json.loads(seal_bytes(bundle))
    record["attested"] = []

    raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    assert _rule(lambda: load_seal(raw)) == "seal-digest-mismatch"


def test_a_missing_attestation_field_is_refused(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    record = json.loads(seal_bytes(bundle))
    del record["attested"]

    assert _rule(lambda: load_seal(_rehash(record))) == "seal-malformed"


@pytest.mark.parametrize(
    "attested",
    [
        ["CT-1.2", "CT-1.1"],
        ["CT-1.2", "CT-1.2"],
        ["not-a-contract"],
        ["CT-1.2", 7],
        "CT-1.2",
        {"CT-1.2": True},
    ],
)
def test_a_non_canonical_attestation_is_refused(tmp_path: Path, attested: Any) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: load_seal(_hostile(bundle, attested=attested))) == "seal-malformed"


def test_an_attestation_longer_than_the_bound_is_refused(tmp_path: Path) -> None:
    bundle = _mint(_sealed_tree(tmp_path))
    oversized = sorted(f"CT-1.{index}" for index in range(MAX_ATTESTED + 1))

    assert _rule(lambda: load_seal(_hostile(bundle, attested=oversized))) == "seal-malformed"


@pytest.mark.parametrize("attested", [("CT-1.2", "CT-1.1"), ("CT-1.2", "CT-1.2"), None, "CT-1.2"])
def test_an_out_of_band_attestation_never_reaches_the_bytes(tmp_path: Path, attested: Any) -> None:
    bundle = _mint(_sealed_tree(tmp_path))

    assert _rule(lambda: seal_bytes(replace(bundle, attested=attested))) == "seal-malformed"


# ── CT-3.6: the verifier runs the sealed closure, not the plan's fence ────────


def _collection_rule(callable_: Callable[[], object]) -> str:
    with pytest.raises(AcceptanceCollectionError) as refused:
        callable_()
    return refused.value.rule


def _candidate() -> str:
    """A revision that is not the sealed one: the code moved, the oracle did not."""
    return "rev-" + "1" * 32


def test_v2_verifier_uses_sealed_closure_with_current_candidate_revision(tmp_path: Path) -> None:
    """CT-3.6 — the oracle is the sealed argv, and both revisions are recorded.

    The run is real: the in-band substrate executes the harness-built command in a
    private ``$TMPDIR``, so the nodeids can only appear if pytest collected the
    sealed bytes under the sealed ``pytest.ini`` and the report travelled back
    inside the receipt. Nothing in the plan supplies a command here.
    """
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    candidate = _candidate()
    prepared: dict[str, Any] = {}

    verification = verify_sealed_acceptance(
        bundle,
        workspace=tmp_path,
        candidate_revision_id=candidate,
        plan_bytes=_PLAN_BYTES,
        executor=_inband_executor(writes_visible=False, prepared=prepared, revision=candidate),
    )

    # Two identities, two claims: the closure stayed at the sealed revision while
    # the code came from the caller's explicit current candidate.
    assert verification.sealed_revision_id == _REVISION
    assert verification.candidate_revision_id == candidate
    assert verification.sealed_root == _SEALED_ROOT
    assert verification.run.closure_sha256 == bundle.closure.digest

    command = prepared["command"]
    assert f"-c {_SEALED_ROOT}/pytest.ini" in command
    assert f"--rootdir {_SEALED_ROOT}" in command
    assert "-p fa.inner_loop.junit_nodeid_plugin" in command
    # The report went to the cell's scratch, never to a path this controller chose.
    assert '--junitxml="$__fa_rep"' in command
    assert "${TMPDIR:-/tmp}" in command
    # ... and the controller never names that path: only the cell's own env does.
    assert str(prepared["tmpdir"]) not in command

    # The sealed selectors are what executed, re-keyed to workspace-relative form.
    assert verification.run.outcomes == {_NODEID: True, _NODEID_SECOND: True}
    assert verification.run.nodeids == {_TEST_PATH: (_NODEID, _NODEID_SECOND)}


def test_the_sealed_verifier_refuses_before_it_runs_a_cell_command(tmp_path: Path) -> None:
    """CT-3.6 — every refusal that needs no execution happens before the command."""
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    prepared: dict[str, Any] = {}
    managed = _inband_executor(writes_visible=False, prepared=prepared)
    common: dict[str, Any] = {"workspace": tmp_path, "plan_bytes": _PLAN_BYTES, "candidate_revision_id": _candidate()}

    # No substrate at all: there is no host fallback to fall back to.
    assert _collection_rule(lambda: verify_sealed_acceptance(bundle, executor=None, **common)) == (
        "verifier-substrate-required"
    )
    # A substrate whose writes this controller can see is the host, not the cell.
    assert (
        _collection_rule(
            lambda: verify_sealed_acceptance(bundle, executor=_inband_executor(writes_visible=True), **common)
        )
        == "verifier-substrate-required"
    )
    # The candidate revision is recorded, so it must at least be an identity.
    assert (
        _collection_rule(
            lambda: verify_sealed_acceptance(
                bundle, executor=managed, workspace=tmp_path, plan_bytes=_PLAN_BYTES, candidate_revision_id=""
            )
        )
        == "candidate-revision-invalid"
    )
    # The seal is only valid for the plan it was minted from, on this route too.
    assert (
        _rule(
            lambda: verify_sealed_acceptance(
                bundle, executor=managed, workspace=tmp_path, candidate_revision_id=_candidate(), plan_bytes=b"other"
            )
        )
        == "plan-digest-mismatch"
    )
    # A closure that overlaps a code root would let an edit become part of the oracle.
    overlapped = replace(bundle, sealed_root="tests/acceptance")
    assert _collection_rule(lambda: verify_sealed_acceptance(overlapped, executor=managed, **common)) == (
        "sealed-root-code-overlap"
    )

    assert prepared == {}, "a refused call must not have reached a cell"


def test_a_declared_kill_target_is_refused_rather_than_proved_without_its_mutation(tmp_path: Path) -> None:
    """F9 — the verifier cannot prove a contract whose mutation it never ran.

    `claim` proof is "the sealed test passed *and* its mutation died". This route has no mutation
    runner yet, so a plan that declares `KILL-TARGETS` must be refused before the cell runs; the
    alternative is an attempt that reads as proven while the kill check never happened.
    """
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    prepared: dict[str, Any] = {}

    assert (
        _collection_rule(
            lambda: verify_sealed_acceptance(
                bundle,
                workspace=tmp_path,
                candidate_revision_id=_candidate(),
                plan_bytes=_PLAN_BYTES,
                kill_required=("CT-1.1",),
                executor=_inband_executor(writes_visible=False, prepared=prepared, revision=_candidate()),
            )
        )
        == "claim-mutation-missing"
    )
    assert prepared == {}, "the refusal must happen before a cell command exists"


def test_the_sealed_verifier_still_refuses_a_drifted_closure(tmp_path: Path) -> None:
    """CT-3.6 — the pinned route keeps the seal's own byte-drift rule."""
    root = _sealed_tree(tmp_path)
    bundle = _mint(root)
    (root / "tests" / "test_publish.py").write_text(_TEST + "\n\ndef test_late():\n    assert True\n", encoding="utf-8")

    assert (
        _rule(
            lambda: verify_sealed_acceptance(
                bundle,
                workspace=tmp_path,
                candidate_revision_id=_candidate(),
                plan_bytes=_PLAN_BYTES,
                executor=_inband_executor(writes_visible=False, revision=_candidate()),
            )
        )
        == "seal-byte-drift"
    )


def test_a_report_from_outside_the_closure_is_refused(tmp_path: Path) -> None:
    """CT-3.6 EDGE — a nodeid the closure does not hold is not evidence about it."""

    class _ForeignReport:
        writes_are_visible = False
        view_revision_id = _candidate()

        def run_verify_command(
            self, command: str, *, cwd: Path, timeout_s: float, env: dict[str, str]
        ) -> CommandResult:
            del cwd, timeout_s, env
            body = (
                '<testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0">'
                '<testcase classname="x" name="y"><properties>'
                '<property name="fa_pytest_nodeid" value="tests/test_elsewhere.py::test_other"/>'
                "</properties></testcase></testsuite>"
            )
            return CommandResult(
                command=command,
                outcome=CommandOutcome.PASS,
                exit_code=0,
                stdout_tail=f"{JUNIT_BLOCK_START}\n{body}\n{JUNIT_BLOCK_END}\n",
                stderr_tail="",
                duration_s=0.0,
            )

    root = _sealed_tree(tmp_path)
    bundle = _mint(root)

    assert (
        _collection_rule(
            lambda: verify_sealed_acceptance(
                bundle,
                workspace=tmp_path,
                candidate_revision_id=_candidate(),
                plan_bytes=_PLAN_BYTES,
                executor=_ForeignReport(),
            )
        )
        == "collection-nodeid-outside-closure"
    )
