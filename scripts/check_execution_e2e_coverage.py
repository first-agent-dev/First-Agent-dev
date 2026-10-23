"""Check the frozen I02/I03 producer-to-case coverage mapping.

This is a local artifact-integrity check. It never reads host evidence, executes
fixtures, or assigns a live result. The current frozen inventory covers I02-origin
and I03 rows only; I01 live coverage is an explicit open gap tracked by Q87, so an
OK result from this checker is not final I01-I03 acceptance. The frozen source inventory
is in
``worklogs/planning-topology-and-executable-contracts-loop/e2e/I03/producer-baseline.json``;
successor/case mappings are separate in
``worklogs/planning-topology-and-executable-contracts-loop/e2e/I03/producer-coverage.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTER_REL = Path("worklogs/planning-topology-and-executable-contracts-loop/notes/e2e-live-verification-register.md")
PROJECT_E2E_REL = Path("worklogs/planning-topology-and-executable-contracts-loop/e2e")
BASELINE_REL = PROJECT_E2E_REL / "I03" / "producer-baseline.json"
COVERAGE_REL = PROJECT_E2E_REL / "I03" / "producer-coverage.json"
INDEX_REL = PROJECT_E2E_REL / "README.md"
MASTER_REL = PROJECT_E2E_REL / "I03" / "live-verification.md"

# Scope is deliberately limited to the explicit legacy producer inventories,
# I03 production-surface tables, and the I03 cross-module join table. Mutation
# inventories, source-review evidence, and unrelated non-producer tables are
# excluded.
PRODUCER_HEADERS = {
    "producer",
    "new helper producer",
    "id / production surface",
    "producers / changed boundary",
    "producers / changed surface",
    "every new/changed producer/consumer surface",
}
EXPECTED_DUPLICATE_KEYS = {"_producer_absent", "_classify"}
I03_ID_RE = re.compile(r"\b(I03-LIVE-(?:\d{2}|S\d{2}))\b")
CASE_ID_RE = re.compile(r"^(?:I02-LIVE-\d{3}|I03-LIVE-(?:\d{2}|S\d{2}))$")
BASELINE_ID_RE = re.compile(r"^(?:I02-LIVE-\d{3}|I03-LIVE-(?:\d{2}|S\d{2})(?:-EXT)?)$")


class CoverageError(ValueError):
    """Raised when a producer is missing, duplicated, or not mapped to a case."""


def _split_table_row(line: str) -> list[str]:
    """Split a Markdown table row; literal cell pipes must be escaped as ``\\|``."""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if char == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        if char == "\\" and not escaped:
            escaped = True
        else:
            escaped = False
    cells.append("".join(current).strip())
    return cells


def _normalize_cell(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1]
    elif len(value) >= 4 and value.startswith("**") and value.endswith("**"):
        value = value[2:-2]
    return re.sub(r"\s+", " ", value).strip()


def _is_separator(row: list[str]) -> bool:
    return bool(row) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in row)


def _in_scope(headers: list[str]) -> tuple[bool, str]:
    normalized = [_normalize_cell(header).lower() for header in headers]
    first = normalized[0] if normalized else ""
    if first in PRODUCER_HEADERS:
        return True, "producer"
    if (
        first == "id"
        and len(normalized) >= 4
        and normalized[1] == "join"
        and "required live fixture/oracle" in normalized
    ):
        return True, "join"
    return False, ""


def _parse_register(path: Path) -> list[dict[str, Any]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict[str, Any]] = []
    section = ""
    index = 0
    while index < len(lines) - 1:
        heading = re.match(r"^(#{1,4}) (.+)$", lines[index])
        if heading:
            section = f"{heading.group(1)} {heading.group(2).strip()}"
        if lines[index].startswith("|") and lines[index + 1].startswith("|"):
            headers = _split_table_row(lines[index])
            separator = _split_table_row(lines[index + 1])
            in_scope, kind = _in_scope(headers)
            if len(headers) == len(separator) and _is_separator(separator) and in_scope:
                row_index = index + 2
                while row_index < len(lines) and lines[row_index].startswith("|"):
                    values = _split_table_row(lines[row_index])
                    if len(values) == len(headers):
                        key = _normalize_cell(values[0])
                        if key:
                            entries.append(
                                {
                                    "line": row_index + 1,
                                    "section": section,
                                    "kind": kind,
                                    "headers": headers,
                                    "values": values,
                                    "producer_key": key,
                                }
                            )
                    row_index += 1
                index = row_index
                continue
        index += 1
    return entries


def _group_entries(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[entry["producer_key"]].append(entry)
    return dict(grouped)


def _validate_duplicates(grouped: dict[str, list[dict[str, Any]]]) -> list[str]:
    duplicates = {key for key, rows in grouped.items() if len(rows) > 1}
    if duplicates != EXPECTED_DUPLICATE_KEYS:
        raise CoverageError(
            "duplicate producer keys differ from the exact-duplicate allowlist: "
            f"expected {sorted(EXPECTED_DUPLICATE_KEYS)}, got {sorted(duplicates)}"
        )
    for key in duplicates:
        comparable = {
            (
                row["section"],
                tuple(_normalize_cell(cell) for cell in row["headers"]),
                tuple(_normalize_cell(cell) for cell in row["values"]),
            )
            for row in grouped[key]
        }
        if len(comparable) != 1:
            raise CoverageError(f"duplicate producer {key!r} is not an exact duplicate")
    return sorted(duplicates)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CoverageError(f"{path} must contain a JSON object")
    return value


def _records(document: dict[str, Any], label: str) -> list[dict[str, Any]]:
    values = document.get("records")
    if not isinstance(values, list) or not all(isinstance(record, dict) for record in values):
        raise CoverageError(f"{label} is missing its records array")
    return values


def _validate_baseline(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    keys: set[str] = set()
    for record in records:
        baseline_id = record.get("baseline_id")
        key = record.get("producer_key")
        if not isinstance(baseline_id, str) or not BASELINE_ID_RE.fullmatch(baseline_id):
            raise CoverageError(f"invalid frozen baseline ID {baseline_id!r}")
        if baseline_id in by_id:
            raise CoverageError(f"duplicate frozen baseline ID {baseline_id!r}")
        if not isinstance(key, str) or not key or key in keys:
            raise CoverageError(f"empty or duplicate frozen producer key {key!r}")
        if record.get("live_result") != "NOT RUN" or record.get("attempt_count") != 0:
            raise CoverageError(f"baseline producer {key!r} contains a live result/attempt")
        fixture_oracle = record.get("fixture_oracle")
        if not isinstance(fixture_oracle, dict) or not fixture_oracle.get("oracle"):
            raise CoverageError(f"baseline producer {key!r} has no host oracle")
        for lineage in ("ct_lineage", "slice_lineage", "step_lineage"):
            if not isinstance(record.get(lineage), list):
                raise CoverageError(f"baseline producer {key!r} is missing {lineage}")
        occurrences = record.get("source_occurrences")
        if not isinstance(occurrences, list) or not occurrences:
            raise CoverageError(f"baseline producer {key!r} has no source occurrence")
        if record.get("occurrence_count") != len(occurrences):
            raise CoverageError(f"baseline producer {key!r} has stale occurrence_count")
        if not isinstance(record.get("case_id"), str) or not CASE_ID_RE.fullmatch(record["case_id"]):
            raise CoverageError(f"baseline producer {key!r} has an invalid case_id")
        keys.add(key)
        by_id[baseline_id] = record

    baseline_ids = [record["baseline_id"] for record in records if record["baseline_id"].startswith("I02-")]
    if baseline_ids != [f"I02-LIVE-{number:03d}" for number in range(1, len(baseline_ids) + 1)]:
        raise CoverageError("frozen legacy I02 IDs are not contiguous in original source order")
    case_ids = [record["case_id"] for record in records]
    if {case for case, count in Counter(case_ids).items() if count > 1} != {"I03-LIVE-S06"}:
        raise CoverageError("only the explicit I03-LIVE-S06 extension may share a case ID")
    return by_id


def _mapping_identity(
    record: dict[str, Any], baseline_by_id: dict[str, dict[str, Any]]
) -> tuple[str, bool, str | None, str | None]:
    baseline_id = record.get("baseline_id")
    if not isinstance(baseline_id, str):
        raise CoverageError(f"invalid coverage baseline_id {baseline_id!r}")
    is_new = baseline_id.startswith("NEW:")
    baseline = baseline_by_id.get(baseline_id)
    if not is_new and baseline is None:
        raise CoverageError(f"coverage mapping has orphan baseline ID {baseline_id!r}")
    if is_new:
        if record.get("producer_key") is not None:
            raise CoverageError(f"new producer mapping {baseline_id!r} cannot claim a frozen key")
        return baseline_id, True, None, None
    if baseline is None:
        raise CoverageError(f"coverage mapping has orphan baseline ID {baseline_id!r}")
    if record.get("producer_key") != baseline["producer_key"]:
        raise CoverageError(f"coverage mapping {baseline_id!r} changed its frozen producer key")
    return baseline_id, False, baseline["producer_key"], baseline["case_id"]


def _mapping_case_fields(record: dict[str, Any], baseline_id: str) -> tuple[list[str], list[str], list[str], str]:
    current_keys = record.get("current_producer_keys")
    if not isinstance(current_keys, list) or not all(isinstance(value, str) and value for value in current_keys):
        raise CoverageError(f"coverage mapping {baseline_id!r} has malformed current_producer_keys")
    if len(current_keys) != len(set(current_keys)):
        raise CoverageError(f"coverage mapping {baseline_id!r} repeats a current producer key")
    successors = record.get("successor_case_ids")
    if not isinstance(successors, list) or not all(
        isinstance(case, str) and CASE_ID_RE.fullmatch(case) for case in successors
    ):
        raise CoverageError(f"coverage mapping {baseline_id!r} has malformed successor_case_ids")
    coverage_ids = record.get("coverage_case_ids")
    if (
        not isinstance(coverage_ids, list)
        or not coverage_ids
        or not all(isinstance(case, str) and CASE_ID_RE.fullmatch(case) for case in coverage_ids)
    ):
        raise CoverageError(f"producer mapping {baseline_id!r} has no valid coverage case")
    if len(coverage_ids) != len(set(coverage_ids)):
        raise CoverageError(f"coverage mapping {baseline_id!r} repeats a case within one producer row")
    case_id = record.get("case_id")
    if not isinstance(case_id, str) or not CASE_ID_RE.fullmatch(case_id):
        raise CoverageError(f"coverage mapping {baseline_id!r} has an invalid case_id")
    return current_keys, successors, coverage_ids, case_id


def _validate_mapping_lineage(
    baseline_id: str,
    is_new: bool,
    baseline_key: str | None,
    baseline_case_id: str | None,
    current_keys: list[str],
    successors: list[str],
    coverage_ids: list[str],
    case_id: str,
) -> None:
    if is_new:
        if not current_keys or case_id not in coverage_ids:
            raise CoverageError(f"new producer mapping {baseline_id!r} is unmapped")
        return
    if case_id != baseline_case_id:
        raise CoverageError(f"coverage mapping {baseline_id!r} changed its frozen case identity")
    if current_keys == [baseline_key] and not successors:
        if case_id not in coverage_ids:
            raise CoverageError(f"retained producer {baseline_id!r} is not mapped to its stable case")
        return
    if not successors:
        raise CoverageError(f"renamed/replaced producer {baseline_id!r} lacks explicit successor_case_ids")
    if not set(successors).issubset(coverage_ids):
        raise CoverageError(f"successor mapping for {baseline_id!r} is not represented by coverage_case_ids")


def _validate_mapping_record(
    record: dict[str, Any], baseline_by_id: dict[str, dict[str, Any]]
) -> tuple[str, list[str], list[str], list[str]]:
    baseline_id, is_new, baseline_key, baseline_case_id = _mapping_identity(record, baseline_by_id)
    current_keys, successors, coverage_ids, case_id = _mapping_case_fields(record, baseline_id)
    _validate_mapping_lineage(
        baseline_id,
        is_new,
        baseline_key,
        baseline_case_id,
        current_keys,
        successors,
        coverage_ids,
        case_id,
    )
    return baseline_id, current_keys, coverage_ids, successors


def _validate_mapping(
    baseline_by_id: dict[str, dict[str, Any]],
    mapping_records: list[dict[str, Any]],
    shared_case_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    by_baseline: dict[str, dict[str, Any]] = {}
    current_key_owner: dict[str, str] = {}
    mapping_case_ids: list[str] = []
    mapping_successors: list[tuple[str, str]] = []
    for record in mapping_records:
        baseline_id, current_keys, coverage_ids, successors = _validate_mapping_record(record, baseline_by_id)
        if baseline_id in by_baseline:
            raise CoverageError(f"duplicate coverage baseline_id {baseline_id!r}")
        for key in current_keys:
            if key in current_key_owner:
                raise CoverageError(
                    f"current producer key {key!r} maps to both {current_key_owner[key]} and {baseline_id}"
                )
            current_key_owner[key] = baseline_id
        mapping_case_ids.extend(coverage_ids)
        mapping_successors.extend((baseline_id, successor) for successor in successors)
        by_baseline[baseline_id] = record

    mapped_baseline_ids = {baseline_id for baseline_id in by_baseline if not baseline_id.startswith("NEW:")}
    missing_baseline = sorted(set(baseline_by_id) - mapped_baseline_ids)
    orphan_baseline = sorted(mapped_baseline_ids - set(baseline_by_id))
    if missing_baseline or orphan_baseline:
        raise CoverageError(f"baseline mapping mismatch: missing={missing_baseline}, orphan={orphan_baseline}")
    duplicates = {case for case, count in Counter(mapping_case_ids).items() if count > 1}
    if duplicates != shared_case_ids:
        raise CoverageError(
            "reused coverage cases require an explicit shared_case_ids declaration and "
            f"per-producer mappings; expected={sorted(shared_case_ids)}, actual={sorted(duplicates)}"
        )
    case_set = set(mapping_case_ids)
    for baseline_id, successor in mapping_successors:
        if successor not in case_set:
            raise CoverageError(f"mapping {baseline_id!r} has orphan successor {successor!r}")
    return by_baseline, set(current_key_owner)


def _check_current_source_rows(
    current_grouped: dict[str, list[dict[str, Any]]],
    baseline_by_id: dict[str, dict[str, Any]],
    mapping_by_id: dict[str, dict[str, Any]],
) -> None:
    for baseline_id, baseline in baseline_by_id.items():
        mapping = mapping_by_id[baseline_id]
        current_keys = mapping["current_producer_keys"]
        original_key = baseline["producer_key"]
        if current_keys == [original_key]:
            current_rows = current_grouped.get(original_key, [])
            recorded_rows = baseline["source_occurrences"]
            if len(current_rows) != len(recorded_rows):
                raise CoverageError(f"producer {original_key!r} occurrence count changed")
            for recorded, current in zip(recorded_rows, current_rows, strict=True):
                normalized_headers = [_normalize_cell(value) for value in current["headers"]]
                normalized_values = [_normalize_cell(value) for value in current["values"]]
                if (
                    recorded.get("section") != current["section"]
                    or recorded.get("normalized_headers") != normalized_headers
                    or recorded.get("normalized_values") != normalized_values
                ):
                    raise CoverageError(f"producer {original_key!r} has changed source row without a new baseline")
        for key in current_keys:
            for row in current_grouped.get(key, []):
                headers = [_normalize_cell(header).lower() for header in row["headers"]]
                has_oracle = any(
                    "oracle" in header or "observable" in header or "what it must observe" in header
                    for header in headers
                )
                if not has_oracle:
                    raise CoverageError(f"current producer {key!r} has no host-oracle column")


def _check_legacy_index_rows(index_text: str, expected_ids: set[str]) -> None:
    rows = [line for line in index_text.splitlines() if line.startswith("| `I02-LIVE-")]
    parsed: dict[str, list[str]] = {}
    for line in rows:
        cells = _split_table_row(line)
        case_id = _normalize_cell(cells[0]) if cells else ""
        if case_id in parsed:
            raise CoverageError(f"legacy case {case_id} appears more than once in the planner index")
        if len(cells) != 9:
            raise CoverageError(f"legacy case {case_id} has an incomplete planner-index row")
        if not cells[1] or not cells[5] or not cells[6]:
            raise CoverageError(f"legacy case {case_id} is missing producer, fixture, or live oracle")
        if cells[7] != "NOT RUN" or cells[8] != "0":
            raise CoverageError(f"legacy case {case_id} has a result/attempt outside operator evidence")
        parsed[case_id] = cells
    actual_ids = set(parsed)
    if actual_ids != expected_ids:
        raise CoverageError(
            f"legacy planner-index rows differ: missing={sorted(expected_ids - actual_ids)}, "
            f"orphan={sorted(actual_ids - expected_ids)}"
        )


def _check_coverage(root: Path) -> dict[str, int]:
    current_entries = _parse_register(root / REGISTER_REL)
    current_grouped = _group_entries(current_entries)
    duplicates = _validate_duplicates(current_grouped)
    baseline_doc = _load_json(root / BASELINE_REL)
    mapping_doc = _load_json(root / COVERAGE_REL)
    baseline_records = _records(baseline_doc, "frozen baseline")
    mapping_records = _records(mapping_doc, "coverage mapping")
    shared_values = mapping_doc.get("shared_case_ids")
    if not isinstance(shared_values, list) or not all(
        isinstance(case, str) and CASE_ID_RE.fullmatch(case) for case in shared_values
    ):
        raise CoverageError("coverage mapping is missing its explicit shared_case_ids list")
    baseline_by_id = _validate_baseline(baseline_records)
    mapping_by_id, mapped_current_keys = _validate_mapping(baseline_by_id, mapping_records, set(shared_values))

    current_keys = set(current_grouped)
    missing = sorted(current_keys - mapped_current_keys)
    orphan = sorted(mapped_current_keys - current_keys)
    if missing or orphan:
        raise CoverageError(f"producer-key mismatch: missing={missing}, orphan={orphan}")
    _check_current_source_rows(current_grouped, baseline_by_id, mapping_by_id)

    all_case_ids = {case for record in mapping_records for case in record["coverage_case_ids"]}
    index_path = root / INDEX_REL
    master_path = root / MASTER_REL
    index_text = index_path.read_text(encoding="utf-8")
    master_text = master_path.read_text(encoding="utf-8")
    index_i03_ids = set(re.findall(r"\[`(I03-LIVE-(?:\d{2}|S\d{2}))`\]", index_text))
    master_i03_ids = set(re.findall(r"^### (I03-LIVE-(?:\d{2}|S\d{2}))\s*$", master_text, re.MULTILINE))
    register_i03_ids = {
        match.group(1) for entry in current_entries if (match := I03_ID_RE.search(entry["producer_key"])) is not None
    }
    mapped_i03_ids = {case for case in all_case_ids if case.startswith("I03-")}
    if index_i03_ids != register_i03_ids or master_i03_ids != register_i03_ids or mapped_i03_ids != register_i03_ids:
        raise CoverageError(
            "I03 register/index/master/coverage cases differ: "
            f"register={sorted(register_i03_ids)}, index={sorted(index_i03_ids)}, "
            f"master={sorted(master_i03_ids)}, coverage={sorted(mapped_i03_ids)}"
        )
    legacy_ids = {case for case in all_case_ids if case.startswith("I02-")}
    _check_legacy_index_rows(index_text, legacy_ids)
    if "producer-baseline.json" not in index_text or "producer-coverage.json" not in index_text:
        raise CoverageError("planner index does not link both frozen baseline and case mapping")

    return {
        "source_rows": len(current_entries),
        "unique_producers": len(current_grouped),
        "legacy_cases": len(legacy_ids),
        "i03_cases": len(mapped_i03_ids),
        "exact_duplicate_keys": len(duplicates),
    }


def _check_producer_coverage(root: Path) -> dict[str, int]:
    """Internal producer checker called by the CLI entrypoint (CT112 seam)."""
    return _check_coverage(root)


def check_producer_coverage(root: Path = REPO_ROOT) -> dict[str, int]:
    """Public pure-check entry point for the artifact contract tests."""
    return _check_producer_coverage(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="repository root (defaults to this script's checkout)",
    )
    args = parser.parse_args(argv)
    try:
        counts = _check_producer_coverage(args.root)
    except (CoverageError, OSError) as exc:
        print(f"E2E coverage check FAILED: {exc}", file=sys.stderr)
        return 1
    print(
        "E2E artifact coverage OK (current I02-origin/I03 subset only; Q87 I01 gap remains): "
        f"{counts['unique_producers']} unique producers across "
        f"{counts['legacy_cases']} I02-origin and {counts['i03_cases']} I03 cases; "
        f"{counts['exact_duplicate_keys']} exact duplicate keys collapsed; "
        "all live results remain artifact-owned (no PASS inferred)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
