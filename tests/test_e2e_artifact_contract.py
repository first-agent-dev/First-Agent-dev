"""I01 Q88 / I03 SLICE6: live-result schema and E2E artifact contracts.

This checks artifact shape and source-to-case coverage only. It cannot assign, infer,
or approve a deployed-host result; all live statuses remain operator/reviewer-owned.
Contracts: CT88, CT89, CT112 and Q63 (E231), plus the resolved Q88 I01 mapping.
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

I01_MASTER_SHEET = PROJECT_E2E / "I01" / "live-verification.md"
I01_BASELINE = PROJECT_E2E / "I01" / "producer-baseline.json"
I01_COVERAGE = PROJECT_E2E / "I01" / "producer-coverage.json"
I01_PLAN = (
    REPO_ROOT
    / "worklogs"
    / "planning-topology-and-executable-contracts-loop"
    / "increments"
    / "increment-01-plan-grammar-and-extractor.md"
)
DEFERRED_REGISTER = (
    REPO_ROOT
    / "worklogs"
    / "planning-topology-and-executable-contracts-loop"
    / "notes"
    / "deferred-verification-register.md"
)
COVERAGE_SOURCE_PATHS = (
    coverage_checker.REGISTER_REL,
    coverage_checker.BASELINE_REL,
    coverage_checker.COVERAGE_REL,
    coverage_checker.INDEX_REL,
    coverage_checker.MASTER_REL,
    coverage_checker.I01_PLAN_REL,
    coverage_checker.I01_DEFERRED_REL,
    coverage_checker.I01_BASELINE_REL,
    coverage_checker.I01_COVERAGE_REL,
    coverage_checker.I01_MASTER_REL,
)

LIVE_RESULTS = ("NOT RUN", "PASS", "FAIL", "BLOCKED")

with LIVE_RESULT_SCHEMA.open(encoding="utf-8") as schema_file:
    _VALIDATE_ATTEMPT = fastjsonschema.compile(json.load(schema_file))


def _attempt(result: str, *, case_id: str = "I03-LIVE-01", commentary: str | None = None) -> dict[str, Any]:
    """Return a complete CT88-shaped attempt, optionally with commentary."""
    record: dict[str, Any] = {
        "case_id": case_id,
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
        _VALIDATE_ATTEMPT(_attempt(result, case_id="I01-LIVE-01"))
        _VALIDATE_ATTEMPT(_attempt(result, case_id="I01-LIVE-01", commentary="short, redacted operator note"))
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


def test_i01_contracts_deferred_obligations_and_case_ids_are_mapped_exactly() -> None:
    baseline = json.loads(I01_BASELINE.read_text(encoding="utf-8"))
    mapping = json.loads(I01_COVERAGE.read_text(encoding="utf-8"))
    plan = I01_PLAN.read_text(encoding="utf-8")
    declared = re.findall(
        r"^\s+CT(\d+[a-z]?)\s+\[(?:FUNCTIONAL|CONSTRAINT|PRESERVATION)\]:",
        plan,
        re.MULTILINE,
    )
    expected_baseline_ids = [f"I01-CT{contract_id}" for contract_id in declared]
    assert len(declared) == 42
    assert [row["baseline_id"] for row in baseline["records"]] == expected_baseline_ids
    assert [row["baseline_id"] for row in mapping["records"]] == expected_baseline_ids
    expected_contract_cases = {
        "I01-LIVE-01": {
            "CT14",
            "CT21",
            "CT21b",
            "CT22",
            "CT23",
            "CT24",
            "CT31",
            "CT32",
            "CT40",
            "CT41",
            "CT42",
            "CT43",
        },
        "I01-LIVE-02": {
            "CT1",
            "CT2",
            "CT3",
            "CT4",
            "CT4b",
            "CT4c",
            "CT5",
            "CT6",
            "CT7",
            "CT11",
            "CT12",
            "CT13",
            "CT16",
            "CT17",
            "CT18",
            "CT19",
            "CT20",
            "CT33",
        },
        "I01-LIVE-03": {"CT8", "CT9", "CT10", "CT25", "CT26", "CT27", "CT34", "CT35", "CT36", "CT37", "CT38", "CT39"},
    }
    actual_contract_cases = {
        case_id: {row["contract_id"] for row in mapping["records"] if row["case_id"] == case_id}
        for case_id in mapping["case_ids"]
    }
    assert actual_contract_cases == expected_contract_cases

    expected_deferred_cases = {
        "D1a": "I01-LIVE-02",
        "D1b": "I01-LIVE-01",
        "D2": "I01-LIVE-03",
        "D3": "I01-LIVE-01",
        "D4": "I01-LIVE-02",
        "D5": "I01-LIVE-01",
        "D8": "I01-LIVE-02",
    }
    expected_deferred = set(expected_deferred_cases)
    assert {row["obligation_id"] for row in baseline["deferred_obligations"]} == expected_deferred
    assert {row["obligation_id"] for row in mapping["deferred_obligations"]} == expected_deferred
    assert {
        row["obligation_id"]: row["coverage_case_ids"][0] for row in mapping["deferred_obligations"]
    } == expected_deferred_cases
    assert {row["obligation_id"] for row in baseline["excluded_deferred_obligations"]} == {"D6", "D7"}
    assert mapping["case_ids"] == ["I01-LIVE-01", "I01-LIVE-02", "I01-LIVE-03"]

    index = E2E_INDEX.read_text(encoding="utf-8")
    master = I01_MASTER_SHEET.read_text(encoding="utf-8")
    index_ids = re.findall(r"\[`(I01-LIVE-[0-9]{2})`\]", index)
    master_ids = re.findall(r"^## (I01-LIVE-[0-9]{2}) —", master, re.MULTILINE)
    assert index_ids == master_ids == mapping["case_ids"]
    case_rows = [line for line in index.splitlines() if line.startswith("| [`I01-LIVE-")]
    assert len(case_rows) == 3
    assert all(_split_index_row_status(line) == ("NOT RUN", "0") for line in case_rows)
    for case_id in mapping["case_ids"]:
        section = re.search(rf"(?ms)^## {re.escape(case_id)} —.*?(?=^## |\Z)", master)
        assert section is not None, case_id
        assert "| Live result | NOT RUN |" in section.group(0), case_id
        assert f"#### Attempts — {case_id}" in section.group(0), case_id


def _split_index_row_status(line: str) -> tuple[str, str]:
    cells = line.strip("|").split("|")
    return cells[9].strip(), cells[10].strip()


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
        "source_rows": 127,
        "unique_producers": 125,
        "legacy_cases": 89,
        "native_i03_cases": 35,
        "shared_i03_s06_extension_rows": 1,
    }
    assert document["duplicate_policy"]["only_exact_duplicates_collapsed"] == [
        "_classify",
        "_producer_absent",
    ]
    assert len(records) == 125
    assert len({record["producer_key"] for record in records}) == 125
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
    assert "all nineteen over real owners" in live_26["source_values"][1]
    assert "register{create:true}" in live_26["fixture_oracle"]["oracle"]
    live_27 = next(record for record in records if record["case_id"] == "I03-LIVE-27")
    assert live_27["baseline_id"] == "I03-LIVE-27"
    assert "workspace.py::handoff" in live_27["producer_key"]
    assert live_27["ct_lineage"] == ["CT113"]
    assert live_27["slice_lineage"] == ["SLICE2"]
    assert live_27["step_lineage"] == ["STEP6"]
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


def test_checker_rejects_i01_contract_or_deferred_case_reassignment(tmp_path: Path) -> None:
    for relative in COVERAGE_SOURCE_PATHS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    mapping_path = tmp_path / coverage_checker.I01_COVERAGE_REL
    baseline_path = tmp_path / coverage_checker.I01_BASELINE_REL
    original_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    contract_mutation = json.loads(json.dumps(original_mapping))
    contract_row = next(row for row in contract_mutation["records"] if row["contract_id"] == "CT1")
    contract_row["case_id"] = "I01-LIVE-01"
    contract_row["coverage_case_ids"] = ["I01-LIVE-01"]
    mapping_path.write_text(json.dumps(contract_mutation), encoding="utf-8")
    with pytest.raises(coverage_checker.CoverageError, match="expected 'I01-LIVE-02'"):
        coverage_checker.check_producer_coverage(tmp_path)

    mapping_path.write_text(json.dumps(original_mapping), encoding="utf-8")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    deferred_mapping = next(row for row in original_mapping["deferred_obligations"] if row["obligation_id"] == "D2")
    deferred_mapping["coverage_case_ids"] = ["I01-LIVE-02"]
    baseline_row = next(row for row in baseline["deferred_obligations"] if row["obligation_id"] == "D2")
    baseline_row["case_id"] = "I01-LIVE-02"
    mapping_path.write_text(json.dumps(original_mapping), encoding="utf-8")
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    with pytest.raises(coverage_checker.CoverageError, match="D2 has the wrong I01 case"):
        coverage_checker.check_producer_coverage(tmp_path)


def test_checker_rejects_missing_i01_contract_mapping(tmp_path: Path) -> None:
    for relative in COVERAGE_SOURCE_PATHS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    mapping_path = tmp_path / coverage_checker.I01_COVERAGE_REL
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["records"].pop()
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    with pytest.raises(coverage_checker.CoverageError, match="I01 coverage mapping is missing"):
        coverage_checker.check_producer_coverage(tmp_path)


def test_checker_rejects_missing_i01_case_row_from_index_or_master(tmp_path: Path) -> None:
    for relative in COVERAGE_SOURCE_PATHS:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    index_path = tmp_path / coverage_checker.INDEX_REL
    master_path = tmp_path / coverage_checker.I01_MASTER_REL
    original_index = index_path.read_text(encoding="utf-8")
    original_master = master_path.read_text(encoding="utf-8")
    removed_index_row = next(line for line in original_index.splitlines() if line.startswith("| [`I01-LIVE-02`]"))
    index_path.write_text(original_index.replace(removed_index_row + "\n", "", 1), encoding="utf-8")
    with pytest.raises(coverage_checker.CoverageError, match="I01 README/master case IDs differ"):
        coverage_checker.check_producer_coverage(tmp_path)
    index_path.write_text(original_index, encoding="utf-8")

    shortened_master, count = re.subn(r"(?ms)^## I01-LIVE-02 —.*?(?=^## |\Z)", "", original_master)
    assert count == 1
    master_path.write_text(shortened_master, encoding="utf-8")
    with pytest.raises(coverage_checker.CoverageError, match="I01 README/master case IDs differ"):
        coverage_checker.check_producer_coverage(tmp_path)


def test_coverage_mapping_covers_every_frozen_baseline_id() -> None:
    baseline = _producer_baseline_document()
    mapping = _producer_coverage_document()
    baseline_ids = {record["baseline_id"] for record in baseline["records"]}
    mapping_ids = {record["baseline_id"] for record in mapping["records"]}

    assert baseline_ids == mapping_ids
    assert len(mapping_ids) == len(mapping["records"]) == 125
    assert all(record["coverage_case_ids"] for record in mapping["records"])
    assert all(record["current_producer_keys"] for record in mapping["records"])
    assert mapping["counts"]["frozen_producer_keys"] == 125
    assert all(record["successor_case_ids"] == [] for record in mapping["records"])
    assert any("successor_case_ids" in rule for rule in mapping["mapping_policy"])


def test_coverage_checker_compares_every_unique_producer_case(tmp_path: Path) -> None:
    document = _producer_coverage_document()
    source_paths = COVERAGE_SOURCE_PATHS
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
    source_paths = COVERAGE_SOURCE_PATHS
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
    source_paths = COVERAGE_SOURCE_PATHS
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
    assert coverage_checker.check_producer_coverage(tmp_path)["unique_producers"] == 125


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
                "unique_producers": 125,
                "legacy_cases": 89,
                "i03_cases": 35,
                "exact_duplicate_keys": 2,
                "i01_contracts": 42,
                "i01_deferred": 7,
                "i01_cases": 3,
            }
        ),
    )
    root = REPO_ROOT
    assert coverage_checker.main(["--root", str(root)]) == 0
    assert calls == [root]
    output = capsys.readouterr().out
    assert "125 I02-origin/I03 producers" in output
    assert "I01 42 CTs/7 deferred obligations across 3 cases" in output
    assert "no live PASS inferred" in output


def test_coverage_checker_cli_executes_and_reports_frozen_counts() -> None:
    completed = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_execution_e2e_coverage.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "I01 42 CTs/7 deferred obligations across 3 cases" in completed.stdout
    assert "125 I02-origin/I03 producers" in completed.stdout
    assert "no live PASS inferred" in completed.stdout


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
        (
            "I03-LIVE-27",
            ("Q85", "CT113", "SLICE2 STEP6", "CT108", "SLICE5 STEP2", "E283"),
            "WorkspaceAuthority.handoff",
            "tests/test_execution_handoff.py",
        ),
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
    assert "No fixture or copy/paste host command is created" in normalized_section or (
        case_id == "I03-LIVE-27" and "no new fixture, host command" in normalized_section.lower()
    )
    assert "live result" in normalized_section.lower()
    assert "I03/implementation-handoffs.md" in E2E_INDEX.read_text(encoding="utf-8")
    if case_id == "I03-LIVE-27":
        for link in ("I03-LIVE-27", "L-HAND-1", "L-HAND-2", "I03-LIVE-S08"):
            assert link in section, link
        assert "PLANNED / UNEXECUTED" in section
        assert "NOT RUN" in section
