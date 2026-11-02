"""SLICE5 STEP3/STEP1 — versioned managed-admission fixtures and invariants.

These fixtures freeze the exact record contract before the acquisition producer
is wired into the workflow. They deliberately exercise the schema authority, not
an imagined runtime path; the later controller tests must prove the producer.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Literal

import pytest

from fa.inner_loop.admission_schema import (
    ADMISSION_RULES,
    ADMISSION_RULES_V2,
    AdmissionRecordError,
    validate_admission_record,
)
from fa.inner_loop.managed_acquisition import (
    AcquisitionChoiceError,
    AcquisitionMetadataError,
    BootstrapNewProjectChoice,
    CanonicalIncrementArtifact,
    IncrementMetadata,
    NeedsClarificationChoice,
    ProjectArtifactInventory,
    ResolvedExistingIncrement,
    RoadmapMetadata,
    SelectExistingChoice,
    parse_acquisition_choice,
    parse_artifact_metadata,
    resolve_existing_choice,
)
from fa.inner_loop.managed_inventory import AcquisitionInventoryError, inventory_project_artifacts
from fa.inner_loop.plan_admission import PlanRef
from fa.inner_loop.workflow_artifacts import AdmissionIOError, ManagedAdmissionBinding, write_admission_record

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_REV_A = "rev-" + "1" * 32
_REV_B = "rev-" + "2" * 32
_OP_A = "op-" + "3" * 32
_WS_A = "ws-" + "4" * 32


def _diagnostic(validator: str, rule: str, severity: str) -> dict[str, object]:
    return {"validator": validator, "rule": rule, "severity": severity, "line": None}


def _v1_attempt(**changes: Any) -> dict[str, Any]:
    return {
        "attempt": 1,
        "dispatch_kind": "EXPLICIT_INPUT",
        "validation": "PASS",
        "diagnostics": [],
        "source_sha256": _SHA_A,
        "candidate_sha256": None,
        "promoted_sha256": None,
        "route": "ADMITTED",
    } | changes


def _v1_record() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": "child-run",
        "status": "ADMITTED",
        "plan_ref": {"workspace_relative_path": "plans/p.md", "source_kind": "EXPLICIT", "sha256": _SHA_A},
        "attempts": [_v1_attempt()],
    }


def _v2_attempt(**changes: Any) -> dict[str, Any]:
    return {
        "attempt": 1,
        "dispatch_kind": "ACQUISITION",
        "validation": "PASS",
        "diagnostics": [],
        "source_sha256": _SHA_A,
        "candidate_sha256": None,
        "promoted_sha256": None,
        "route": "ADMITTED",
        "input_revision": _REV_A,
        "output_revision": _REV_A,
        "operation_id": None,
        "bundle_sha256": None,
    } | changes


def _v2_record(*, plan_ref: dict[str, str] | None, attempt: dict[str, Any] | None = None) -> dict[str, Any]:
    route = "BLOCKED" if attempt is not None and attempt["route"] == "BLOCKED" else "ADMITTED"
    return {
        "schema_version": 2,
        "run_id": "child-run",
        "status": route,
        "plan_ref": plan_ref,
        "attempts": [_v2_attempt() if attempt is None else attempt],
        "workspace_id": _WS_A,
        "owner_run_id": "root-run",
        "generation": 7,
        "base_revision": _REV_A,
    }


def _selection_record() -> dict[str, Any]:
    ref = {
        "workspace_relative_path": "worklogs/demo/increments/increment-02-build.md",
        "source_kind": "EXISTING_SELECTION",
        "sha256": _SHA_A,
    }
    attempt = _v2_attempt(
        source_sha256=_SHA_A,
        output_revision=_REV_A,
        operation_id=None,
        bundle_sha256=None,
    )
    return _v2_record(plan_ref=ref, attempt=attempt)


def _bootstrap_record() -> dict[str, Any]:
    ref = {
        "workspace_relative_path": "worklogs/new-project/increments/increment-01-core.md",
        "source_kind": "BOOTSTRAP",
        "sha256": _SHA_B,
    }
    attempt = _v2_attempt(
        source_sha256=None,
        candidate_sha256=_SHA_B,
        promoted_sha256=_SHA_B,
        output_revision=_REV_B,
        operation_id=_OP_A,
        bundle_sha256=_SHA_C,
    )
    return _v2_record(plan_ref=ref, attempt=attempt)


def _blocked_clarification_record() -> dict[str, Any]:
    attempt = _v2_attempt(
        validation="INDETERMINATE",
        diagnostics=[_diagnostic("selection", "needs-clarification", "ERROR")],
        source_sha256=None,
        route="BLOCKED",
        output_revision=None,
        bundle_sha256=None,
    )
    return _v2_record(plan_ref=None, attempt=attempt)


def _rejected_bootstrap_record() -> dict[str, Any]:
    attempt = _v2_attempt(
        validation="DIAGNOSTICS",
        diagnostics=[_diagnostic("bootstrap", "invalid-grammar", "FAIL")],
        source_sha256=None,
        candidate_sha256=_SHA_B,
        promoted_sha256=None,
        route="BLOCKED",
        output_revision=None,
        operation_id=None,
        bundle_sha256=_SHA_C,
    )
    return _v2_record(plan_ref=None, attempt=attempt)


def test_complete_v1_fixture_remains_v1_and_is_not_upgraded() -> None:
    record = _v1_record()
    assert validate_admission_record(record, run_id="child-run") == record
    assert record["schema_version"] == 1
    assert not ({"workspace_id", "owner_run_id", "generation", "base_revision"} & record.keys())
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record | {"workspace_id": _WS_A}, run_id="child-run")


def test_managed_bundle_rendering_is_frozen_as_exact_three_file_output() -> None:
    from fa.execution.publication import render_bundle

    roadmap_body = "## Intent\n\nShip the thing.\n\n## Out of scope\n\nEverything else.\n"
    increment_body = "## SLICE1: first\n\nSteps.\n\n## SLICE2: second\n\nSteps.\n"
    files = render_bundle("demo-project", "first-increment", roadmap_body, increment_body, created="2026-10-22")
    expected = {
        "worklogs/demo-project/roadmap.md": (
            "---\n"
            "Roadmap-ID: RM-demo-project\n"
            "slug: demo-project\n"
            "created: 2026-10-22\n"
            "status: IN PROGRESS\n"
            "active-increment: I01\n"
            "---\n\n"
            "# Roadmap — demo-project\n\n"
            "## Artifacts\n\n"
            "| Artifact | Path | Status |\n"
            "| --- | --- | --- |\n"
            "| Roadmap | `worklogs/demo-project/roadmap.md` | IN PROGRESS |\n"
            "| Increment | `worklogs/demo-project/increments/increment-01-first-increment.md` | IN PROGRESS |\n"
            "| Ledger | `worklogs/demo-project/ledger.md` | — |\n\n"
            "## Increments\n\n"
            "| ID | Slug | Status |\n"
            "| --- | --- | --- |\n"
            "| I01 | [first-increment](worklogs/demo-project/"
            "increments/increment-01-first-increment.md) | IN PROGRESS |\n\n"
            "## Intent\n\nShip the thing.\n\n## Out of scope\n\nEverything else.\n"
        ).encode(),
        "worklogs/demo-project/ledger.md": (
            "# Ledger — decision and evidence log\n\nFixed heading only; entries are appended by the run.\n"
        ).encode(),
        "worklogs/demo-project/increments/increment-01-first-increment.md": (
            "---\n"
            "Increment-ID: RM-demo-project-I01\n"
            "Roadmap-ID: RM-demo-project\n"
            "status: IN PROGRESS\n"
            "slices: 2\n"
            "shipped: —\n"
            "---\n\n"
            "## SLICE1: first\n\nSteps.\n\n## SLICE2: second\n\nSteps.\n"
        ).encode(),
    }
    assert files == expected


def test_managed_bundle_renderer_rejects_the_superseded_hyphenated_heading() -> None:
    from fa.execution.publication import render_bundle
    from fa.execution.supervisor import SupervisorError

    roadmap_body = "## Intent\n\nScope.\n\n## Out-of-scope\n\nEverything else.\n"
    increment_body = "## SLICE1: first\n\nSteps.\n"
    with pytest.raises(SupervisorError) as rejected:
        render_bundle("demo-project", "first-increment", roadmap_body, increment_body, created="2026-10-22")
    assert rejected.value.code == "INPUT_POLICY"


def test_acquisition_choice_parser_accepts_only_the_three_closed_variants() -> None:
    selected = parse_acquisition_choice('{"kind":"SELECT_EXISTING","project_slug":"demo-project","increment_id":"I03"}')
    assert selected == SelectExistingChoice("demo-project", "I03")

    bootstrap = parse_acquisition_choice(
        json.dumps(
            {
                "kind": "BOOTSTRAP_NEW_PROJECT",
                "project_slug": "demo-project",
                "increment_slug": "first-increment",
                "roadmap_body": "## Intent\n\nGoal.\n\n## Out of scope\n\nNo extras.\n",
                "increment_body": "## SLICE1: first\n\nWork.\n",
            }
        )
    )
    assert bootstrap == BootstrapNewProjectChoice(
        "demo-project",
        "first-increment",
        "## Intent\n\nGoal.\n\n## Out of scope\n\nNo extras.\n",
        "## SLICE1: first\n\nWork.\n",
    )

    clarification = parse_acquisition_choice('{"kind":"NEEDS_CLARIFICATION","reason":"UNKNOWN_INCREMENT"}')
    assert clarification == NeedsClarificationChoice("UNKNOWN_INCREMENT")


def test_acquisition_choice_parser_distinguishes_missing_from_malformed() -> None:
    with pytest.raises(AcquisitionChoiceError) as missing:
        parse_acquisition_choice("  ")
    assert (missing.value.validator, missing.value.rule) == ("selection", "choice-missing")
    with pytest.raises(AcquisitionChoiceError) as malformed:
        parse_acquisition_choice(None)
    assert (malformed.value.validator, malformed.value.rule) == ("selection", "choice-malformed")


@pytest.mark.parametrize(
    "raw",
    [
        '{"kind":"SELECT_EXISTING","kind":"SELECT_EXISTING","project_slug":"demo","increment_id":"I01"}',
        '{"kind":"SELECT_EXISTING","project_slug":"demo","increment_id":"I01","path":"worklogs/demo"}',
        '{"kind":"SELECT_EXISTING","project_slug":"demo","increment_id":"I01"} trailing',
        '```json\n{"kind":"NEEDS_CLARIFICATION","reason":"MISSING_CONTEXT"}\n```',
        '{"kind":"NEEDS_CLARIFICATION","reason":"free-form"}',
        '{"kind":"UNKNOWN"}',
        '{"kind":"SELECT_EXISTING","project_slug":"demo","increment_id":"I01","extra":{"x":NaN}}',
    ],
)
def test_acquisition_choice_parser_rejects_ambiguous_or_open_json(raw: str) -> None:
    with pytest.raises(AcquisitionChoiceError) as refused:
        parse_acquisition_choice(raw)
    assert (refused.value.validator, refused.value.rule) == ("selection", "choice-malformed")
    assert raw not in str(refused.value)


@pytest.mark.parametrize(
    ("project_slug", "increment_id"),
    [
        ("Demo", "I01"),
        ("../demo", "I01"),
        ("demo-", "I01"),
        ("d" * 49, "I01"),
        ("demo", "I1"),
        ("demo", "I01/../../other"),
    ],
)
def test_acquisition_choice_parser_rejects_noncanonical_stable_ids(project_slug: str, increment_id: str) -> None:
    raw = json.dumps({"kind": "SELECT_EXISTING", "project_slug": project_slug, "increment_id": increment_id})
    with pytest.raises(AcquisitionChoiceError) as refused:
        parse_acquisition_choice(raw)
    assert (refused.value.validator, refused.value.rule) == ("selection", "choice-malformed")


def test_acquisition_choice_parser_rejects_nontext_invalid_utf8_and_oversized_bootstrap_bodies() -> None:
    invalid_fields: list[dict[str, Any]] = [
        {"project_slug": "demo", "increment_slug": "inc", "roadmap_body": [], "increment_body": "x"},
        {"project_slug": "demo", "increment_slug": "inc", "roadmap_body": "\u0000", "increment_body": "x"},
    ]
    for fields in invalid_fields:
        raw = json.dumps(
            {
                "kind": "BOOTSTRAP_NEW_PROJECT",
                "project_slug": fields["project_slug"],
                "increment_slug": fields["increment_slug"],
                "roadmap_body": fields["roadmap_body"],
                "increment_body": fields["increment_body"],
            }
        )
        with pytest.raises(AcquisitionChoiceError) as refused:
            parse_acquisition_choice(raw)
        assert (refused.value.validator, refused.value.rule) == ("bootstrap", "invalid-body")

    with pytest.raises(AcquisitionChoiceError) as invalid_utf8:
        parse_acquisition_choice(
            '{"kind":"BOOTSTRAP_NEW_PROJECT","project_slug":"demo","increment_slug":"inc",'
            '"roadmap_body":"\\ud800","increment_body":"x"}'
        )
    assert (invalid_utf8.value.validator, invalid_utf8.value.rule) == ("bootstrap", "invalid-body")

    oversized = json.dumps(
        {
            "kind": "BOOTSTRAP_NEW_PROJECT",
            "project_slug": "demo",
            "increment_slug": "inc",
            "roadmap_body": "x" * (1024 * 1024 + 1),
            "increment_body": "x",
        }
    )
    with pytest.raises(AcquisitionChoiceError) as too_large:
        parse_acquisition_choice(oversized)
    assert (too_large.value.validator, too_large.value.rule) == ("bootstrap", "too-large")


_ROADMAP_SLUG = "planning-topology-and-executable-contracts-loop"
_ROADMAP_SLUG_LINE = f"slug: {_ROADMAP_SLUG}"
_ROADMAP_METADATA = (
    "---\n"
    "Roadmap-ID: RM-planning-topology\n"
    "slug: planning-topology-and-executable-contracts-loop\n"
    "created: 2026-09-09\n"
    "status: IN PROGRESS\n"
    "active-increment: I01\n"
    "supersedes: worklogs/legacy-plan.md\n"
    "---\n"
)
_INCREMENT_METADATA = (
    "---\n"
    "Increment-ID: RM-planning-topology-I01\n"
    "Roadmap-ID: RM-planning-topology\n"
    "status: IN PROGRESS\n"
    "slices: 6\n"
    "shipped: SLICE1, SLICE1b\n"
    "---\n"
)


def _current_project_inventory() -> ProjectArtifactInventory:
    plan_body = "\n\n".join(f"## SLICE{number}: section\n" for number in range(1, 7))
    content = (_INCREMENT_METADATA + "\n" + plan_body).encode("utf-8")
    return ProjectArtifactInventory(
        f"worklogs/{_ROADMAP_SLUG}/roadmap.md",
        _ROADMAP_METADATA.encode("utf-8"),
        (
            CanonicalIncrementArtifact(
                f"worklogs/{_ROADMAP_SLUG}/increments/increment-01-plan-grammar-and-extractor.md",
                content,
            ),
        ),
    )


def test_resolver_maps_current_stable_pair_to_the_exact_canonical_plan_snapshot() -> None:
    resolved = resolve_existing_choice(
        SelectExistingChoice(_ROADMAP_SLUG, "I01"), (_current_project_inventory(),)
    )
    assert isinstance(resolved, ResolvedExistingIncrement)
    assert resolved.snapshot.ref.workspace_relative_path == (
        f"worklogs/{_ROADMAP_SLUG}/increments/increment-01-plan-grammar-and-extractor.md"
    )
    assert resolved.snapshot.ref.source_kind == "EXISTING_SELECTION"
    assert resolved.snapshot.ids.slices == tuple(f"SLICE{number}" for number in range(1, 7))
    assert resolved.increment.increment_id == "RM-planning-topology-I01"


def test_resolver_accepts_controller_rendered_increment_without_slug_frontmatter() -> None:
    from fa.execution.publication import render_bundle

    files = render_bundle(
        "demo-project",
        "foundation",
        "## Intent\n\nA project.\n\n## Out of scope\n\nOther work.\n",
        "## SLICE1: Foundation\n\nImplement the foundation.\n",
        created="2026-11-02",
    )
    roadmap_path = "worklogs/demo-project/roadmap.md"
    increment_path = "worklogs/demo-project/increments/increment-01-foundation.md"
    resolved = resolve_existing_choice(
        SelectExistingChoice("demo-project", "I01"),
        (
            ProjectArtifactInventory(
                roadmap_path,
                files[roadmap_path],
                (CanonicalIncrementArtifact(increment_path, files[increment_path]),),
            ),
        ),
    )
    assert isinstance(resolved, ResolvedExistingIncrement)
    assert resolved.snapshot.ref.workspace_relative_path == increment_path
    assert resolved.snapshot.ref.source_kind == "EXISTING_SELECTION"
    assert resolved.snapshot.ids.slices == ("SLICE1",)


def test_resolver_returns_clarification_for_missing_unknown_inactive_or_duplicate_matches() -> None:
    assert resolve_existing_choice(SelectExistingChoice("absent", "I01"), ()) == NeedsClarificationChoice(
        "MISSING_CONTEXT"
    )
    current = _current_project_inventory()
    assert resolve_existing_choice(
        SelectExistingChoice(_ROADMAP_SLUG, "I99"), (current,)
    ) == NeedsClarificationChoice("UNKNOWN_INCREMENT")
    assert resolve_existing_choice(
        SelectExistingChoice(_ROADMAP_SLUG, "I01"), (current, current)
    ) == NeedsClarificationChoice("AMBIGUOUS_PROJECT")

    duplicate_artifact = CanonicalIncrementArtifact(
        f"worklogs/{_ROADMAP_SLUG}/increments/increment-01-second-name.md",
        current.increments[0].content,
    )
    duplicate = ProjectArtifactInventory(
        current.roadmap_path,
        current.roadmap_content,
        (*current.increments, duplicate_artifact),
    )
    assert resolve_existing_choice(
        SelectExistingChoice(_ROADMAP_SLUG, "I01"), (duplicate,)
    ) == NeedsClarificationChoice("AMBIGUOUS_PROJECT")

    inactive_roadmap = _ROADMAP_METADATA.replace("active-increment: I01", "active-increment: I02")
    inactive = ProjectArtifactInventory(current.roadmap_path, inactive_roadmap.encode(), current.increments)
    assert resolve_existing_choice(
        SelectExistingChoice(_ROADMAP_SLUG, "I01"), (inactive,)
    ) == NeedsClarificationChoice("UNKNOWN_INCREMENT")

    outlined_roadmap = _ROADMAP_METADATA.replace("active-increment: I01", "active-increment: I03")
    outlined_increment = _INCREMENT_METADATA.replace("I01", "I03").replace("IN PROGRESS", "OUTLINED")
    outlined = ProjectArtifactInventory(
        current.roadmap_path,
        outlined_roadmap.encode(),
        (
            CanonicalIncrementArtifact(
                f"worklogs/{_ROADMAP_SLUG}/increments/increment-03-foundation.md",
                (outlined_increment + "\n## SLICE1: section\n").encode(),
            ),
        ),
    )
    assert resolve_existing_choice(
        SelectExistingChoice(_ROADMAP_SLUG, "I03"), (outlined,)
    ) == NeedsClarificationChoice("UNKNOWN_INCREMENT")


def test_resolver_rejects_noncanonical_paths_and_inconsistent_linkage() -> None:
    current = _current_project_inventory()
    artifact = current.increments[0]
    bad_path = ProjectArtifactInventory(
        current.roadmap_path,
        current.roadmap_content,
        (CanonicalIncrementArtifact("worklogs/../plan.md", artifact.content),),
    )
    with pytest.raises(AcquisitionMetadataError):
        resolve_existing_choice(SelectExistingChoice(_ROADMAP_SLUG, "I01"), (bad_path,))

    wrong_sequence = ProjectArtifactInventory(
        current.roadmap_path,
        current.roadmap_content,
        (
            CanonicalIncrementArtifact(
                f"worklogs/{_ROADMAP_SLUG}/increments/increment-02-plan-grammar-and-extractor.md",
                artifact.content,
            ),
        ),
    )
    with pytest.raises(AcquisitionMetadataError):
        resolve_existing_choice(SelectExistingChoice(_ROADMAP_SLUG, "I01"), (wrong_sequence,))

    wrong_roadmap = _ROADMAP_METADATA.replace("Roadmap-ID: RM-planning-topology", "Roadmap-ID: RM-different")
    bad_linkage = ProjectArtifactInventory(current.roadmap_path, wrong_roadmap.encode(), current.increments)
    with pytest.raises(AcquisitionMetadataError):
        resolve_existing_choice(SelectExistingChoice(_ROADMAP_SLUG, "I01"), (bad_linkage,))


def _write_rendered_inventory_project(root: Any) -> dict[str, bytes]:
    from fa.execution.publication import render_bundle

    files = render_bundle(
        "demo-project",
        "foundation",
        "## Intent\n\nA project.\n\n## Out of scope\n\nOther work.\n",
        "## SLICE1: Foundation\n\nImplement the foundation.\n",
        created="2026-11-02",
    )
    for relative_path, content in files.items():
        destination = root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return files


def test_inventory_reads_only_canonical_artifacts_then_resolves_the_exact_plan(tmp_path: Any) -> None:
    _write_rendered_inventory_project(tmp_path)
    increments_dir = tmp_path / "worklogs/demo-project/increments"
    (increments_dir / "README.txt").write_text("not a canonical increment", encoding="utf-8")

    inventory = inventory_project_artifacts(tmp_path, "demo-project")
    assert inventory is not None
    assert [item.relative_path for item in inventory.increments] == [
        "worklogs/demo-project/increments/increment-01-foundation.md"
    ]
    resolved = resolve_existing_choice(SelectExistingChoice("demo-project", "I01"), (inventory,))
    assert isinstance(resolved, ResolvedExistingIncrement)
    assert resolved.snapshot.ref.workspace_relative_path == inventory.increments[0].relative_path
    assert resolved.snapshot.ref.source_kind == "EXISTING_SELECTION"


def test_inventory_missing_project_or_roadmap_returns_no_partial_inventory(tmp_path: Any) -> None:
    assert inventory_project_artifacts(tmp_path, "missing-project") is None

    project = tmp_path / "worklogs/no-roadmap"
    (project / "increments").mkdir(parents=True)
    (project / "increments/increment-01-plan.md").write_text("content", encoding="utf-8")
    assert inventory_project_artifacts(tmp_path, "no-roadmap") is None


def test_inventory_rejects_canonical_symlink_and_nonregular_entries(tmp_path: Any) -> None:
    _write_rendered_inventory_project(tmp_path)
    increments = tmp_path / "worklogs/demo-project/increments"
    target = tmp_path / "outside.md"
    target.write_text("not a project artifact", encoding="utf-8")
    (increments / "increment-02-link.md").symlink_to(target)
    with pytest.raises(AcquisitionInventoryError) as symlink:
        inventory_project_artifacts(tmp_path, "demo-project")
    assert symlink.value.rule == "unsafe-entry"
    (increments / "increment-02-link.md").unlink()

    (increments / "increment-02-directory.md").mkdir()
    with pytest.raises(AcquisitionInventoryError) as nonregular:
        inventory_project_artifacts(tmp_path, "demo-project")
    assert nonregular.value.rule == "unsafe-entry"
    (increments / "increment-02-directory.md").rmdir()

    saved_increments = increments.with_name("increments-saved")
    increments.rename(saved_increments)
    increments.symlink_to(saved_increments, target_is_directory=True)
    with pytest.raises(AcquisitionInventoryError) as directory_symlink:
        inventory_project_artifacts(tmp_path, "demo-project")
    assert directory_symlink.value.rule == "unsafe-entry"


def test_inventory_enforces_file_count_per_file_and_total_byte_bounds(tmp_path: Any, monkeypatch: Any) -> None:
    files = _write_rendered_inventory_project(tmp_path)
    increments = tmp_path / "worklogs/demo-project/increments"
    increment_path = increments / "increment-01-foundation.md"
    (increments / "increment-02-second.md").write_bytes(b"x")
    monkeypatch.setattr("fa.inner_loop.managed_inventory._MAX_INCREMENT_FILES", 1)
    with pytest.raises(AcquisitionInventoryError) as too_many:
        inventory_project_artifacts(tmp_path, "demo-project")
    assert too_many.value.rule == "too-many"

    (increments / "increment-02-second.md").unlink()
    monkeypatch.setattr("fa.inner_loop.managed_inventory._MAX_INCREMENT_FILES", 64)
    monkeypatch.setattr("fa.inner_loop.managed_inventory._MAX_ARTIFACT_BYTES", 32)
    with pytest.raises(AcquisitionInventoryError) as too_large:
        inventory_project_artifacts(tmp_path, "demo-project")
    assert too_large.value.rule == "too-large"

    monkeypatch.setattr("fa.inner_loop.managed_inventory._MAX_ARTIFACT_BYTES", 1024 * 1024)
    roadmap_length = len(files["worklogs/demo-project/roadmap.md"])
    moved_increment_path = increments / "foundation.txt"
    increment_path.rename(moved_increment_path)
    monkeypatch.setattr("fa.inner_loop.managed_inventory._MAX_INVENTORY_BYTES", roadmap_length - 1)
    with pytest.raises(AcquisitionInventoryError) as roadmap_too_large:
        inventory_project_artifacts(tmp_path, "demo-project")
    assert roadmap_too_large.value.rule == "too-large"

    moved_increment_path.rename(increment_path)
    total_length = roadmap_length + len(files["worklogs/demo-project/increments/increment-01-foundation.md"])
    monkeypatch.setattr("fa.inner_loop.managed_inventory._MAX_INVENTORY_BYTES", total_length - 1)
    with pytest.raises(AcquisitionInventoryError) as total_too_large:
        inventory_project_artifacts(tmp_path, "demo-project")
    assert total_too_large.value.rule == "too-large"


def test_artifact_metadata_parser_accepts_current_and_rendered_metadata_without_slug_guessing() -> None:
    roadmap = parse_artifact_metadata(_ROADMAP_METADATA.encode("utf-8"), kind="roadmap")
    assert roadmap == RoadmapMetadata(
        "RM-planning-topology",
        "planning-topology-and-executable-contracts-loop",
        "2026-09-09",
        "IN PROGRESS",
        "I01",
        "worklogs/legacy-plan.md",
    )
    increment = parse_artifact_metadata(_INCREMENT_METADATA, kind="increment")
    assert increment == IncrementMetadata(
        "RM-planning-topology-I01",
        "RM-planning-topology",
        "IN PROGRESS",
        6,
        "SLICE1, SLICE1b",
    )

    rendered_increment = (
        "---\n"
        "Increment-ID: RM-demo-project-I01\n"
        "Roadmap-ID: RM-demo-project\n"
        "status: IN PROGRESS\n"
        "slices: 1\n"
        "shipped: —\n"
        "---\n"
    )
    assert parse_artifact_metadata(rendered_increment, kind="increment") == IncrementMetadata(
        "RM-demo-project-I01", "RM-demo-project", "IN PROGRESS", 1, "—"
    )


def test_artifact_metadata_parser_rejects_unsafe_yaml_and_noncanonical_metadata() -> None:
    invalid: list[tuple[bytes | str, Literal["roadmap", "increment"]]] = [
        (
            _ROADMAP_METADATA.replace(_ROADMAP_SLUG_LINE + "\n", "slug: demo\nslug: other\n"),
            "roadmap",
        ),
        (_ROADMAP_METADATA.replace(_ROADMAP_SLUG_LINE, "slug: &shared demo"), "roadmap"),
        (_ROADMAP_METADATA.replace(_ROADMAP_SLUG_LINE, "slug: !custom demo"), "roadmap"),
        (_ROADMAP_METADATA.replace(_ROADMAP_SLUG_LINE, "slug:\n  nested: value"), "roadmap"),
        (_INCREMENT_METADATA.replace("slices: 6", "slices: true"), "increment"),
        (_INCREMENT_METADATA.replace("slices: 6", "slices: 8"), "increment"),
        (_INCREMENT_METADATA.replace("RM-planning-topology-I01", "RM-other-I01"), "increment"),
        (_INCREMENT_METADATA.replace("shipped: SLICE1, SLICE1b", "slug: plan-slug\nshipped: —"), "increment"),
        (_ROADMAP_METADATA.replace("created: 2026-09-09", "created: 2026-99-99"), "roadmap"),
        ("no frontmatter\n", "roadmap"),
        (b"---\nslug: \xff\n---\n", "roadmap"),
    ]
    for content, kind in invalid:
        with pytest.raises(AcquisitionMetadataError) as rejected:
            parse_artifact_metadata(content, kind=kind)
        assert rejected.value.rule == "invalid-metadata"
        diagnostic_input = content if isinstance(content, str) else content.decode("utf-8", errors="ignore")
        assert diagnostic_input[:30] not in str(rejected.value)


def test_artifact_metadata_parser_rejects_yaml_aliases_and_oversized_frontmatter() -> None:
    alias = _ROADMAP_METADATA.replace(
        "slug: planning-topology-and-executable-contracts-loop\n",
        "slug: &stable demo\nactive-copy: *stable\n",
    )
    with pytest.raises(AcquisitionMetadataError):
        parse_artifact_metadata(alias, kind="roadmap")

    oversized = _ROADMAP_METADATA.replace("---\n", "---\nsupersedes: " + "x" * 4100 + "\n", 1)
    with pytest.raises(AcquisitionMetadataError):
        parse_artifact_metadata(oversized, kind="roadmap")


def test_v1_and_v2_diagnostic_vocabularies_are_separate() -> None:
    assert "selection" not in ADMISSION_RULES
    assert "workspace" not in ADMISSION_RULES
    assert ADMISSION_RULES_V2["selection"] == frozenset(
        {
            "choice-malformed",
            "choice-missing",
            "unknown-project",
            "unknown-increment",
            "ambiguous-project",
            "ambiguous-increment",
            "status-not-active",
            "needs-clarification",
        }
    )
    assert ADMISSION_RULES_V2["workspace"] == frozenset(
        {"busy", "stale-generation", "stale-revision", "quarantined", "backend-unavailable", "terminality-unknown"}
    )
    assert ADMISSION_RULES_V2["bootstrap"] == ADMISSION_RULES["bootstrap"] | frozenset(
        {
            "invalid-body",
            "invalid-metadata",
            "invalid-grammar",
            "too-large",
            "collision",
            "prepare-failed",
            "install-failed",
            "durability-unknown",
            "hash-mismatch",
        }
    )


@pytest.mark.parametrize("record", [_selection_record(), _bootstrap_record()])
def test_admitted_v2_selection_and_bootstrap_fixtures_validate(record: dict[str, Any]) -> None:
    assert validate_admission_record(record, run_id="child-run") == record


def test_v2_selection_does_not_fabricate_publication_or_bundle_hash() -> None:
    record = _selection_record()
    attempt = record["attempts"][0]
    assert attempt["source_sha256"] == record["plan_ref"]["sha256"]
    assert attempt["candidate_sha256"] is None
    assert attempt["promoted_sha256"] is None
    assert attempt["bundle_sha256"] is None
    assert attempt["input_revision"] == attempt["output_revision"] == record["base_revision"]
    assert attempt["operation_id"] is None
    assert validate_admission_record(record, run_id="child-run") == record


def test_v2_bootstrap_plan_hash_and_rendered_bundle_hash_are_distinct() -> None:
    record = _bootstrap_record()
    attempt = record["attempts"][0]
    assert attempt["candidate_sha256"] == attempt["promoted_sha256"] == record["plan_ref"]["sha256"]
    assert attempt["bundle_sha256"] == _SHA_C
    assert attempt["bundle_sha256"] != attempt["candidate_sha256"]
    assert attempt["input_revision"] == record["base_revision"]
    assert attempt["output_revision"] == _REV_B
    assert attempt["operation_id"] == _OP_A
    assert validate_admission_record(record, run_id="child-run") == record


def test_v2_clarification_blocks_without_plan_or_invented_effect() -> None:
    record = _blocked_clarification_record()
    attempt = record["attempts"][0]
    assert record["status"] == "BLOCKED" and record["plan_ref"] is None
    assert all(attempt[key] is None for key in ("source_sha256", "candidate_sha256", "promoted_sha256"))
    assert all(attempt[key] is None for key in ("output_revision", "operation_id", "bundle_sha256"))
    assert validate_admission_record(record, run_id="child-run") == record


def test_v2_rejected_rendered_bootstrap_keeps_candidate_evidence_without_claiming_commit() -> None:
    record = _rejected_bootstrap_record()
    attempt = record["attempts"][0]
    assert record["plan_ref"] is None
    assert attempt["candidate_sha256"] == _SHA_B and attempt["bundle_sha256"] == _SHA_C
    assert attempt["promoted_sha256"] is None
    assert attempt["output_revision"] is None and attempt["operation_id"] is None
    assert validate_admission_record(record, run_id="child-run") == record


def test_v2_selected_plan_may_retry_only_for_determinate_plan_validation_fail() -> None:
    record = _selection_record()
    record["status"] = "ACQUIRING"
    attempt = record["attempts"][0]
    attempt.update(
        validation="DIAGNOSTICS",
        diagnostics=[_diagnostic("precheck", "slice-without-tests", "FAIL")],
        route="RETRY",
    )
    assert validate_admission_record(record, run_id="child-run") == record
    attempt["diagnostics"] = [_diagnostic("workspace", "busy", "ERROR")]
    attempt["validation"] = "INDETERMINATE"
    attempt["route"] = "BLOCKED"
    record["status"] = "BLOCKED"
    assert validate_admission_record(record, run_id="child-run") == record


def test_v2_selection_retry_and_shared_repair_keep_revision_and_plan_hash_chain() -> None:
    record = _selection_record()
    record["status"] = "ADMITTED"
    first = record["attempts"][0]
    first.update(
        validation="DIAGNOSTICS",
        diagnostics=[_diagnostic("precheck", "slice-without-tests", "FAIL")],
        route="RETRY",
    )
    repair = _v2_attempt(
        attempt=2,
        dispatch_kind="ADMISSION_REPAIR",
        validation="PASS",
        diagnostics=[],
        source_sha256=_SHA_A,
        candidate_sha256=_SHA_B,
        promoted_sha256=_SHA_B,
        route="ADMITTED",
        input_revision=_REV_A,
        output_revision=_REV_B,
        operation_id=_OP_A,
        bundle_sha256=None,
    )
    record["attempts"].append(repair)
    record["plan_ref"]["sha256"] = _SHA_B
    record["status"] = "ADMITTED"
    assert validate_admission_record(record, run_id="child-run") == record


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(schema_version=True),
        lambda r: r.update(workspace_id="WS-" + "4" * 32),
        lambda r: r.update(owner_run_id="../root"),
        lambda r: r.update(generation=True),
        lambda r: r.update(generation=0),
        lambda r: r.update(base_revision="revision"),
        lambda r: r.update(extra="secret"),
        lambda r: r.pop("owner_run_id"),
    ],
)
def test_v2_top_level_rejects_bad_version_binding_and_unknown_fields(mutate: Any) -> None:
    record = _selection_record()
    mutate(record)
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("workspace_id", "x"),
        ("owner_run_id", ""),
        ("generation", True),
        ("generation", -1),
        ("base_revision", "rev-" + "A" * 32),
    ],
)
def test_v2_required_binding_fields_are_strictly_typed(key: str, value: object) -> None:
    record = _selection_record()
    record[key] = value
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


@pytest.mark.parametrize("missing", ["input_revision", "output_revision", "operation_id", "bundle_sha256"])
def test_v2_attempt_requires_all_versioned_receipt_fields(missing: str) -> None:
    record = _selection_record()
    del record["attempts"][0][missing]
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("input_revision", "bad"),
        ("output_revision", "rev-" + "A" * 32),
        ("operation_id", "op-short"),
        ("bundle_sha256", "B" * 64),
        ("extra", "raw path"),
    ],
)
def test_v2_attempt_rejects_invalid_receipt_ids_hashes_and_extra_keys(key: str, value: object) -> None:
    record = _selection_record()
    record["attempts"][0][key] = value
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


@pytest.mark.parametrize(
    "change",
    [
        "selection-source",
        "selection-candidate",
        "selection-promoted",
        "selection-bundle",
        "selection-revision",
        "selection-operation",
        "selection-kind",
    ],
)
def test_v2_existing_selection_cross_fields_reject_publication_smuggling(change: str) -> None:
    record = _selection_record()
    attempt = record["attempts"][0]
    if change == "selection-source":
        attempt["source_sha256"] = _SHA_B
    elif change == "selection-candidate":
        attempt["candidate_sha256"] = _SHA_B
    elif change == "selection-promoted":
        attempt["promoted_sha256"] = _SHA_A
    elif change == "selection-bundle":
        attempt["bundle_sha256"] = _SHA_C
    elif change == "selection-revision":
        attempt["output_revision"] = _REV_B
    elif change == "selection-operation":
        attempt["operation_id"] = _OP_A
    else:
        record["plan_ref"]["source_kind"] = "EXPLICIT"
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


@pytest.mark.parametrize(
    "change",
    [
        "bootstrap-source",
        "bootstrap-plan-hash",
        "bootstrap-bundle-missing",
        "bootstrap-operation-missing",
        "bootstrap-output-missing",
        "bootstrap-output-same",
        "bootstrap-kind",
    ],
)
def test_v2_bootstrap_requires_distinct_plan_bundle_and_committed_receipt(change: str) -> None:
    record = _bootstrap_record()
    attempt = record["attempts"][0]
    if change == "bootstrap-source":
        attempt["source_sha256"] = _SHA_A
    elif change == "bootstrap-plan-hash":
        attempt["promoted_sha256"] = _SHA_C
        record["plan_ref"]["sha256"] = _SHA_C
    elif change == "bootstrap-bundle-missing":
        attempt["bundle_sha256"] = None
    elif change == "bootstrap-operation-missing":
        attempt["operation_id"] = None
    elif change == "bootstrap-output-missing":
        attempt["output_revision"] = None
    elif change == "bootstrap-output-same":
        attempt["output_revision"] = _REV_A
    else:
        record["plan_ref"]["source_kind"] = "EXISTING_SELECTION"
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


@pytest.mark.parametrize(
    "change",
    [
        "candidate-without-bundle",
        "promotion-without-commit",
        "uncommitted-ref",
        "op-without-uncertainty",
        "clarification-with-rendered-hash",
    ],
)
def test_v2_blocked_bootstrap_cannot_claim_promotion_or_partial_bundle(change: str) -> None:
    record = _rejected_bootstrap_record()
    attempt = record["attempts"][0]
    if change == "candidate-without-bundle":
        attempt["bundle_sha256"] = None
    elif change == "promotion-without-commit":
        attempt["promoted_sha256"] = _SHA_B
    elif change == "uncommitted-ref":
        record["plan_ref"] = {
            "workspace_relative_path": "worklogs/new-project/increments/increment-01-core.md",
            "source_kind": "BOOTSTRAP",
            "sha256": _SHA_B,
        }
    elif change == "op-without-uncertainty":
        attempt["operation_id"] = _OP_A
    else:
        attempt["validation"] = "INDETERMINATE"
        attempt["diagnostics"] = [_diagnostic("selection", "needs-clarification", "ERROR")]
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


def test_v2_selected_plan_does_not_route_determinate_fail_as_blocked() -> None:
    record = _selection_record()
    attempt = record["attempts"][0]
    attempt.update(
        validation="DIAGNOSTICS",
        diagnostics=[_diagnostic("precheck", "slice-without-tests", "FAIL")],
        route="BLOCKED",
    )
    record["status"] = "BLOCKED"
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


def test_v2_revisions_chain_and_no_retry_after_unresolved_operation() -> None:
    record = _selection_record()
    first = record["attempts"][0]
    first.update(
        validation="DIAGNOSTICS",
        diagnostics=[_diagnostic("precheck", "slice-without-tests", "FAIL")],
        route="RETRY",
    )
    repair = _v2_attempt(
        attempt=2,
        dispatch_kind="ADMISSION_REPAIR",
        validation="INDETERMINATE",
        diagnostics=[_diagnostic("promotion", "durability-unknown", "ERROR")],
        source_sha256=_SHA_A,
        candidate_sha256=_SHA_B,
        promoted_sha256=None,
        route="BLOCKED",
        input_revision=_REV_A,
        output_revision=None,
        operation_id=_OP_A,
        bundle_sha256=None,
    )
    record["attempts"].append(repair)
    record["status"] = "BLOCKED"
    assert validate_admission_record(record, run_id="child-run") == record
    later = deepcopy(repair) | {"attempt": 3, "input_revision": _REV_A, "operation_id": None}
    record["attempts"].append(later)
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


def test_v2_revision_input_can_advance_between_admission_attempts_after_stage_commit() -> None:
    record = _selection_record()
    replan = _v2_attempt(
        attempt=2,
        dispatch_kind="EVAL_REPLAN",
        validation="PASS",
        diagnostics=[],
        source_sha256=_SHA_A,
        candidate_sha256=_SHA_D,
        promoted_sha256=_SHA_D,
        route="ADMITTED",
        input_revision="rev-" + "5" * 32,
        output_revision="rev-" + "6" * 32,
        operation_id="op-" + "7" * 32,
    )
    record["attempts"].append(replan)
    record["plan_ref"]["sha256"] = _SHA_D
    assert validate_admission_record(record, run_id="child-run") == record


def test_v2_wrong_actor_or_record_owner_is_rejected() -> None:
    record = _selection_record()
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="other-child")
    record["owner_run_id"] = record["run_id"]
    with pytest.raises(AdmissionRecordError):
        validate_admission_record(record, run_id="child-run")


def _managed_binding() -> ManagedAdmissionBinding:
    return ManagedAdmissionBinding(
        workspace_id=_WS_A,
        owner_run_id="root-run",
        generation=7,
        base_revision=_REV_A,
    )


def test_workflow_writer_persists_v2_acquiring_before_selection_receipt(tmp_path: Any) -> None:
    path = tmp_path / "admission.json"
    binding = _managed_binding()
    acquiring = write_admission_record(
        path,
        run_id="child-run",
        plan_ref=None,
        managed_binding=binding,
    )
    assert acquiring["schema_version"] == 2
    assert acquiring["status"] == "ACQUIRING"
    assert acquiring["attempts"] == []
    assert validate_admission_record(acquiring, run_id="child-run") == acquiring

    selected = _selection_record()
    source_attempt = selected["attempts"][0]
    attempt = {key: value for key, value in source_attempt.items() if key != "attempt"}
    final = write_admission_record(
        path,
        run_id="child-run",
        plan_ref=PlanRef(**selected["plan_ref"]),
        attempt=attempt,
        status="ADMITTED",
        managed_binding=binding,
    )
    assert final == selected
    assert validate_admission_record(final, run_id="child-run") == final


@pytest.mark.parametrize("start_version", [1, 2])
def test_workflow_writer_refuses_admission_schema_upgrade_or_downgrade(tmp_path: Any, start_version: int) -> None:
    path = tmp_path / "admission.json"
    binding = _managed_binding()
    write_admission_record(
        path,
        run_id="child-run",
        plan_ref=None,
        managed_binding=binding if start_version == 2 else None,
    )
    before = path.read_bytes()
    if start_version == 1:
        with pytest.raises(AdmissionIOError) as caught:
            write_admission_record(
                path,
                run_id="child-run",
                plan_ref=None,
                managed_binding=binding,
            )
    else:
        with pytest.raises(AdmissionIOError) as caught:
            write_admission_record(path, run_id="child-run", plan_ref=None)
    assert caught.value.rule == "corrupt-record"
    assert path.read_bytes() == before


def test_workflow_writer_refuses_managed_binding_change_without_replacing_history(tmp_path: Any) -> None:
    path = tmp_path / "admission.json"
    binding = _managed_binding()
    write_admission_record(path, run_id="child-run", plan_ref=None, managed_binding=binding)
    before = path.read_bytes()
    changed = ManagedAdmissionBinding(
        workspace_id=_WS_A,
        owner_run_id="root-run",
        generation=8,
        base_revision=_REV_A,
    )
    with pytest.raises(AdmissionIOError) as caught:
        write_admission_record(path, run_id="child-run", plan_ref=None, managed_binding=changed)
    assert caught.value.rule == "corrupt-record"
    assert path.read_bytes() == before


def test_workflow_writer_rejects_invalid_v2_append_without_replacing_history(tmp_path: Any) -> None:
    path = tmp_path / "admission.json"
    binding = _managed_binding()
    write_admission_record(path, run_id="child-run", plan_ref=None, managed_binding=binding)
    before = path.read_bytes()
    selected = _selection_record()
    attempt = {key: value for key, value in selected["attempts"][0].items() if key != "attempt"}
    attempt["output_revision"] = _REV_B
    with pytest.raises(AdmissionIOError) as caught:
        write_admission_record(
            path,
            run_id="child-run",
            plan_ref=PlanRef(**selected["plan_ref"]),
            attempt=attempt,
            status="ADMITTED",
            managed_binding=binding,
        )
    assert caught.value.rule == "corrupt-record"
    assert path.read_bytes() == before
