"""I03/SLICE6 STEP1-4: live-result schema and planner/coder E2E artifacts.

This checks artifact shape and producer coverage only. It cannot assign, infer,
or approve a deployed-host result; all live statuses remain operator/reviewer-owned.
Contracts: CT88, CT89, CT112 and Q63 (E231).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import fastjsonschema
import pytest

from scripts import check_execution_e2e_coverage as coverage_checker

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_E2E = REPO_ROOT / "worklogs" / "planning-topology-and-executable-contracts-loop" / "e2e"
E2E_INDEX = PROJECT_E2E / "README.md"
MASTER_SHEET = PROJECT_E2E / "I03" / "live-verification.md"
IMPLEMENTATION_HANDOFFS = PROJECT_E2E / "I03" / "implementation-handoffs.md"
LIVE_RESULT_SCHEMA = PROJECT_E2E / "I03" / "live-result.schema.json"
REGISTER = (
    REPO_ROOT
    / "worklogs"
    / "planning-topology-and-executable-contracts-loop"
    / "notes"
    / "e2e-live-verification-register.md"
)

LIVE_RESULTS = ("NOT RUN", "PASS", "FAIL", "BLOCKED")
CASE_ID = re.compile(r"I03-LIVE-(?:[0-9]{2}|S[0-9]{2})")

with LIVE_RESULT_SCHEMA.open(encoding="utf-8") as schema_file:
    _VALIDATE_ATTEMPT = fastjsonschema.compile(json.load(schema_file))


def _attempt(result: str, *, commentary: str | None = None) -> dict[str, Any]:
    """Return a complete CT88-shaped attempt, optionally with commentary."""
    record: dict[str, Any] = {
        "case_id": "I03-LIVE-01",
        "attempt": 1,
        "date": "2026-10-23",
        "result": result,
        "run_id": "run-example",
        "deployed_sha": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "profile": "approved-profile",
        "config": "approved-config",
        "command": "operator-supplied command",
        "rc_effect": "0 / expected effect observed",
        "evidence": "notes/evidence/i03-e2e/run-example/",
        "reviewer": "operator or independent evidence reviewer",
    }
    if commentary is not None:
        record["commentary"] = commentary
    return record


def _register_case_ids() -> set[str]:
    ids: set[str] = set()
    for line in REGISTER.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*(I03-LIVE-(?:[0-9]{2}|S[0-9]{2}))\b", line)
        if match:
            ids.add(match.group(1))
    return ids


def _heading_case_ids(text: str) -> list[str]:
    return re.findall(r"^### (I03-LIVE-(?:[0-9]{2}|S[0-9]{2}))\s*$", text, re.MULTILINE)


def test_live_result_schema_accepts_every_state_with_and_without_commentary() -> None:
    for result in LIVE_RESULTS:
        _VALIDATE_ATTEMPT(_attempt(result))
        _VALIDATE_ATTEMPT(_attempt(result, commentary="short, redacted operator note"))


def test_blocked_needs_no_reason_and_commentary_is_not_a_reason_code() -> None:
    _VALIDATE_ATTEMPT(_attempt("BLOCKED"))
    with pytest.raises(fastjsonschema.JsonSchemaException):
        _VALIDATE_ATTEMPT({**_attempt("BLOCKED"), "reason": "DOCKER_MISSING"})


@pytest.mark.parametrize("result", LIVE_RESULTS)
def test_commentary_limit_is_utf8_bytes_for_every_state(result: str) -> None:
    _VALIDATE_ATTEMPT(_attempt(result, commentary="é" * 256))  # exactly 512 UTF-8 bytes
    with pytest.raises(ValueError, match="512 UTF-8 bytes"):
        _validate_live_attempt(_attempt(result, commentary="é" * 257))


@pytest.mark.parametrize("commentary", ("one\ntwo", "one\rtwo"))
def test_commentary_must_be_single_line(commentary: str) -> None:
    with pytest.raises(fastjsonschema.JsonSchemaException):
        _VALIDATE_ATTEMPT(_attempt("FAIL", commentary=commentary))


def _validate_live_attempt(record: dict[str, Any]) -> None:
    """Apply the JSON Schema plus the UTF-8 byte constraint in Q63."""
    _VALIDATE_ATTEMPT(record)
    commentary = record.get("commentary")
    if commentary is not None and len(commentary.encode("utf-8")) > 512:
        raise ValueError("commentary must be at most 512 UTF-8 bytes")


def test_e2e_artifacts_are_project_scoped_without_a_root_duplicate() -> None:
    expected_package = Path("worklogs/planning-topology-and-executable-contracts-loop/e2e")
    assert coverage_checker.PROJECT_E2E_REL == expected_package
    assert PROJECT_E2E.is_dir()
    assert not (REPO_ROOT / "e2e").exists()
    coverage = json.loads((PROJECT_E2E / "I03" / "producer-coverage.json").read_text(encoding="utf-8"))
    assert coverage["baseline_path"] == (
        "worklogs/planning-topology-and-executable-contracts-loop/e2e/I03/producer-baseline.json"
    )


def test_live_case_ids_match_register_index_and_master_sheet_exactly() -> None:
    index = E2E_INDEX.read_text(encoding="utf-8")
    master = MASTER_SHEET.read_text(encoding="utf-8")
    index_ids = re.findall(r"\[`(I03-LIVE-(?:[0-9]{2}|S[0-9]{2}))`\]", index)
    master_ids = _heading_case_ids(master)
    register_ids = _register_case_ids()

    assert len(index_ids) == len(set(index_ids)), "duplicate case in planner index"
    assert len(master_ids) == len(set(master_ids)), "duplicate case heading in master sheet"
    assert set(index_ids) == register_ids
    assert set(master_ids) == register_ids
    assert "Expected live observation" in index
    assert "Fixture / run sheet" in index
    artifact_schema_doc = (
        REPO_ROOT
        / "worklogs"
        / "planning-topology-and-executable-contracts-loop"
        / "notes"
        / "artifact-schema-and-grammar.md"
    )
    assert (
        "worklogs/planning-topology-and-executable-contracts-loop/e2e/I03/live-result.schema.json"
        in artifact_schema_doc.read_text(encoding="utf-8")
    )


def test_index_table_has_a_complete_mapping_row_for_every_case() -> None:
    index = E2E_INDEX.read_text(encoding="utf-8")
    rows = [line for line in index.splitlines() if line.startswith("| [`I03-LIVE-")]
    assert len(rows) == len(_register_case_ids())
    for row in rows:
        # Case, kind, slice, CTs, phase, producer, local proof, oracle,
        # fixture/run sheet, live result, attempts.
        assert len(row.strip("|").split("|")) == 11
        assert "NOT RUN" in row


def test_master_sheet_keeps_live_result_and_attempt_identity_separate() -> None:
    master = MASTER_SHEET.read_text(encoding="utf-8")
    sections = re.split(r"(?=^### I03-LIVE-(?:[0-9]{2}|S[0-9]{2})\s*$)", master, flags=re.MULTILINE)
    case_sections = [section for section in sections if _heading_case_ids(section)]
    assert len(case_sections) == len(_register_case_ids())

    required_attempt_columns = (
        "#",
        "Date",
        "Result",
        "Run ID",
        "Deployed SHA",
        "Image digest",
        "Profile",
        "Config",
        "Command",
        "rc / effect",
        "Evidence",
        "Reviewer",
        "Commentary",
    )
    for section in case_sections:
        case_id = _heading_case_ids(section)[0]
        assert "| Live result | NOT RUN |" in section, case_id
        assert "| Commentary | |" in section, case_id
        assert "| " + " | ".join(required_attempt_columns) + " |" in section, case_id
        assert "#### Attempts - " + case_id in section, case_id
        assert "Fixture / run sheet | fixture not assigned" in section, case_id


def test_register_only_reuses_s06_for_its_explicit_extension() -> None:
    register = REGISTER.read_text(encoding="utf-8")
    ids = re.findall(r"^\|\s*(I03-LIVE-(?:[0-9]{2}|S[0-9]{2}))\b", register, re.MULTILINE)
    duplicates = {case_id for case_id in ids if ids.count(case_id) > 1}
    # The register intentionally retains the original S06 recovery obligation
    # and appends an explicit extended S06 row. The master sheet collapses them
    # into one case while preserving both observations; no other duplicate is
    # an allowed assumption for this STEP1-3 artifact work.
    assert duplicates == {"I03-LIVE-S06"}


def _producer_baseline_document() -> dict[str, Any]:
    return json.loads((PROJECT_E2E / "I03" / "producer-baseline.json").read_text(encoding="utf-8"))


def _producer_coverage_document() -> dict[str, Any]:
    return json.loads((PROJECT_E2E / "I03" / "producer-coverage.json").read_text(encoding="utf-8"))


def test_frozen_producer_snapshot_preserves_each_key_lineage_and_host_oracle() -> None:
    document = _producer_baseline_document()
    records = document["records"]

    assert document["counts"] == {
        "source_rows": 126,
        "unique_producers": 124,
        "legacy_cases": 89,
        "native_i03_cases": 34,
        "shared_i03_s06_extension_rows": 1,
    }
    assert document["duplicate_policy"]["only_exact_duplicates_collapsed"] == [
        "_classify",
        "_producer_absent",
    ]
    assert len(records) == 124
    assert len({record["producer_key"] for record in records}) == 124
    assert all(record["case_id"] for record in records)
    assert all(record["fixture_oracle"]["oracle"] for record in records)
    assert all(record["source_occurrences"] for record in records)
    assert all(record["live_result"] == "NOT RUN" for record in records)
    assert all(record["attempt_count"] == 0 for record in records)

    legacy_ids = [record["baseline_id"] for record in records if record["baseline_id"].startswith("I02-")]
    assert legacy_ids == [f"I02-LIVE-{number:03d}" for number in range(1, 90)]
    live_24 = next(record for record in records if record["case_id"] == "I03-LIVE-24")
    assert live_24["baseline_id"] == "I03-LIVE-24"
    assert live_24["ct_lineage"] == ["CT99"]
    assert live_24["slice_lineage"] == ["SLICE1"]
    assert live_24["step_lineage"] == ["STEP3"]
    live_25 = next(record for record in records if record["case_id"] == "I03-LIVE-25")
    assert live_25["ct_lineage"] == ["CT107"]
    assert live_25["slice_lineage"] == ["SLICE3"]
    assert live_25["step_lineage"] == ["STEP4"]
    live_26 = next(record for record in records if record["case_id"] == "I03-LIVE-26")
    assert live_26["ct_lineage"] == ["CT99"]
    assert live_26["slice_lineage"] == ["SLICE1"]
    assert live_26["step_lineage"] == ["STEP3"]
    for record in records:
        assert len(record["source_headers"]) == len(record["source_values"])
        assert isinstance(record["ct_lineage"], list)
        assert isinstance(record["slice_lineage"], list)
        assert isinstance(record["step_lineage"], list)
        for occurrence in record["source_occurrences"]:
            assert len(occurrence["normalized_headers"]) == len(occurrence["values"])


def test_legacy_host_oracles_match_the_merged_register_and_snapshot() -> None:
    document = _producer_baseline_document()
    by_key = {record["producer_key"]: record for record in document["records"]}
    spawn = by_key["_spawn_failure_result"]["fixture_oracle"]
    assert "verify` command naming a binary absent from the image" in spawn["fixture"]
    assert spawn["oracle"] == "`ERROR`, never `FAIL`; the message names the command"

    repair = by_key["validate_kill_directives"]["fixture_oracle"]
    assert repair["fixture"] == "a plan with a malformed directive, submitted at admission"
    assert repair["oracle"] == (
        "the run is **blocked before the coder stage starts** — "
        "the scheduling claim CT53 makes and no in-repo test can observe"
    )
    register = REGISTER.read_text(encoding="utf-8")
    assert "`ERROR`, never `FAIL`; the message names the command" in register
    assert "blocked before the coder stage starts" in register


def test_coverage_mapping_covers_every_frozen_baseline_id() -> None:
    baseline = _producer_baseline_document()
    mapping = _producer_coverage_document()
    baseline_ids = {record["baseline_id"] for record in baseline["records"]}
    mapping_ids = {record["baseline_id"] for record in mapping["records"]}

    assert baseline_ids == mapping_ids
    assert len(mapping_ids) == len(mapping["records"]) == 124
    assert all(record["coverage_case_ids"] for record in mapping["records"])
    assert all(record["current_producer_keys"] for record in mapping["records"])
    assert mapping["counts"]["frozen_producer_keys"] == 124
    assert all(record["successor_case_ids"] == [] for record in mapping["records"])
    assert any("successor_case_ids" in rule for rule in mapping["mapping_policy"])


def test_coverage_checker_compares_every_unique_producer_case(tmp_path: Path) -> None:
    document = _producer_coverage_document()
    source_paths = (
        coverage_checker.REGISTER_REL,
        coverage_checker.BASELINE_REL,
        coverage_checker.COVERAGE_REL,
        coverage_checker.INDEX_REL,
        coverage_checker.MASTER_REL,
    )
    # Build one isolated checkout view; only the mapping is mutated per case.
    root = tmp_path
    for relative in source_paths:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    coverage_path = root / coverage_checker.COVERAGE_REL
    for removed in document["records"]:
        mutated = {
            **document,
            "records": [record for record in document["records"] if record["producer_key"] != removed["producer_key"]],
        }
        coverage_path.write_text(json.dumps(mutated), encoding="utf-8")
        with pytest.raises(coverage_checker.CoverageError):
            coverage_checker.check_producer_coverage(root)


def test_checker_detects_removal_of_every_case_from_index_and_i03_master(tmp_path: Path) -> None:
    mapping = _producer_coverage_document()
    source_paths = (
        coverage_checker.REGISTER_REL,
        coverage_checker.BASELINE_REL,
        coverage_checker.COVERAGE_REL,
        coverage_checker.INDEX_REL,
        coverage_checker.MASTER_REL,
    )
    for relative in source_paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    index_path = tmp_path / coverage_checker.INDEX_REL
    master_path = tmp_path / coverage_checker.MASTER_REL
    original_index = index_path.read_text(encoding="utf-8")
    original_master = master_path.read_text(encoding="utf-8")
    case_ids = {case_id for record in mapping["records"] for case_id in record["coverage_case_ids"]}

    for case_id in sorted(case_ids):
        index_lines = original_index.splitlines()
        removed = [
            line
            for line in index_lines
            if (case_id.startswith("I02-") and line.startswith(f"| `{case_id}` |"))
            or (case_id.startswith("I03-") and line.startswith(f"| [`{case_id}`]"))
        ]
        assert len(removed) == 1, case_id
        index_path.write_text(
            "\n".join(line for line in index_lines if line not in removed) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(coverage_checker.CoverageError):
            coverage_checker.check_producer_coverage(tmp_path)
        index_path.write_text(original_index, encoding="utf-8")

        if not case_id.startswith("I03-"):
            continue
        pattern = rf"(?ms)^### {re.escape(case_id)}\n.*?(?=^### |\Z)"
        shortened_master, count = re.subn(pattern, "", original_master)
        assert count == 1, case_id
        master_path.write_text(shortened_master, encoding="utf-8")
        with pytest.raises(coverage_checker.CoverageError):
            coverage_checker.check_producer_coverage(tmp_path)
        master_path.write_text(original_master, encoding="utf-8")


def test_checker_requires_explicit_successor_for_a_renamed_producer(tmp_path: Path) -> None:
    source_paths = (
        coverage_checker.REGISTER_REL,
        coverage_checker.BASELINE_REL,
        coverage_checker.COVERAGE_REL,
        coverage_checker.INDEX_REL,
        coverage_checker.MASTER_REL,
    )
    for relative in source_paths:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)

    register_path = tmp_path / coverage_checker.REGISTER_REL
    register = register_path.read_text(encoding="utf-8")
    assert register.count("| `run_commands` |") == 1
    register_path.write_text(register.replace("| `run_commands` |", "| `run_commands_v2` |"), encoding="utf-8")

    coverage_path = tmp_path / coverage_checker.COVERAGE_REL
    mapping = json.loads(coverage_path.read_text(encoding="utf-8"))
    item = next(row for row in mapping["records"] if row["baseline_id"] == "I02-LIVE-001")
    item["current_producer_keys"] = ["run_commands_v2"]
    coverage_path.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(coverage_checker.CoverageError, match="lacks explicit successor_case_ids"):
        coverage_checker.check_producer_coverage(tmp_path)

    item["successor_case_ids"] = ["I03-LIVE-S08"]
    item["coverage_case_ids"] = ["I02-LIVE-001", "I03-LIVE-S08"]
    mapping["shared_case_ids"] = ["I03-LIVE-S06", "I03-LIVE-S08"]
    coverage_path.write_text(json.dumps(mapping), encoding="utf-8")
    assert coverage_checker.check_producer_coverage(tmp_path)["unique_producers"] == 124


def test_checker_entrypoint_calls_producer_coverage_and_reports_counts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(
        coverage_checker,
        "_check_producer_coverage",
        lambda root: (
            calls.append(root)
            or {
                "unique_producers": 124,
                "legacy_cases": 89,
                "i03_cases": 34,
                "exact_duplicate_keys": 2,
            }
        ),
    )
    root = REPO_ROOT
    assert coverage_checker.main(["--root", str(root)]) == 0
    assert calls == [root]
    assert "124 unique producers" in capsys.readouterr().out


def test_coverage_checker_cli_executes_and_reports_frozen_counts() -> None:
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_execution_e2e_coverage.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "124 unique producers" in completed.stdout
    assert "Q87 I01 gap remains" in completed.stdout
    assert "no PASS inferred" in completed.stdout


@pytest.mark.parametrize(
    ("case_id", "contract_tags", "producer", "proof_file"),
    (
        (
            "I03-LIVE-23",
            ("Q58", "CT107a", "E273"),
            "WorkspaceAuthority.publish_plan",
            "tests/test_workspace_publication.py",
        ),
        ("I03-LIVE-24", ("CT99", "E274"), "WorkspaceAuthority.authorize", "tests/test_workspace_authorize.py"),
    ),
)
def test_i03_implementation_handoffs_are_source_grounded_and_proposals_labeled(
    case_id: str, contract_tags: tuple[str, ...], producer: str, proof_file: str
) -> None:
    handoffs = IMPLEMENTATION_HANDOFFS.read_text(encoding="utf-8")
    match = re.search(rf"(?ms)^## {re.escape(case_id)}[^\n]*\n.*?(?=^## |\Z)", handoffs)
    assert match is not None, f"missing implementation handoff for {case_id}"
    section = match.group(0)

    required_fields = (
        "**Contracts / producers:**",
        "**Verified source references:**",
        "**Production path:**",
        "**Observable effect / artifact:**",
        "**Host prerequisites:**",
        "**Candidate fixture / command: [PROPOSAL]**",
        "**Local proof:**",
        "**Host-only assumptions / limitations:**",
        "**Evidence references:**",
        "**Planner disposition:** pending",
    )
    for field in required_fields:
        assert field in section, field

    for tag in contract_tags:
        assert tag in section, tag
    assert producer in section
    assert proof_file in section
    normalized_section = " ".join(section.split())
    assert "No fixture or copy/paste host command is created" in normalized_section
    assert "live result" in normalized_section.lower()
    assert "I03/implementation-handoffs.md" in E2E_INDEX.read_text(encoding="utf-8")
