"""Closed admission.json v1 vocabulary and whole-history validation (CT92).

No raw diagnostics, path snippets or exception bodies belong in this record.
Validation proves record consistency, not that a plan was actually admitted.
"""

from __future__ import annotations

import re
from typing import Any

ADMISSION_RULES: dict[str, frozenset[str]] = {
    "precheck": frozenset(
        {
            "heading-near-miss",
            "step-marker-unknown",
            "step-near-miss",
            "slice-count-at-ceiling",
            "orphaned-slice-field",
            "slice-without-tests",
            "step-without-exit",
            "deps-undefined-slice",
            "deps-cycle",
            "contract-reference-undeclared",
            "contract-declared-twice",
            "contract-declaration-lost",
        }
    ),
    "kill-directives": frozenset(
        {
            "kill-directive-near-miss",
            "kill-directive-malformed",
            "kill-directive-ambiguous",
            "kill-directive-missing",
        }
    ),
    "plan-ref": frozenset(
        {
            "missing",
            "path-escape",
            "symlink",
            "not-regular",
            "unreadable",
            "invalid-utf8",
            "empty",
            "too-large",
            "zero-slices",
            "source-changed",
            "validator-error",
        }
    ),
    "promotion": frozenset(
        {
            "managed-execution-absent",
            "scope-denied",
            "symlink",
            "not-regular",
            "source-changed",
            "prepare-failed",
            "replace-failed",
            "durability-unknown",
            "hash-mismatch",
        }
    ),
    "artifact-io": frozenset({"corrupt-record", "lock-failed", "append-failed", "durability-unknown"}),
    "bootstrap": frozenset({"unavailable"}),
}


class AdmissionRecordError(ValueError):
    """Sanitized schema failure, including incompatible/corrupt old history."""

    def __init__(self) -> None:
        super().__init__("invalid admission record")


def _record_object(value: object, required: set[str], *, optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - (optional or set()):
        raise AdmissionRecordError
    return value


def _record_enum(value: object, allowed: set[str] | frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise AdmissionRecordError
    return value


def _record_hash(value: object) -> None:
    if value is not None and (not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None):
        raise AdmissionRecordError


def _record_plan_ref(value: object) -> str | None:
    if value is None:
        return None
    ref = _record_object(value, {"workspace_relative_path", "source_kind", "sha256"})
    path = ref["workspace_relative_path"]
    if not isinstance(path, str) or "\x00" in path or any(p in {"", ".", ".."} for p in path.split("/")):
        raise AdmissionRecordError
    _record_enum(ref["source_kind"], {"EXPLICIT", "EXISTING_SELECTION", "BOOTSTRAP"})
    _record_hash(ref["sha256"])
    if ref["sha256"] is None:
        raise AdmissionRecordError
    return str(ref["sha256"])


def _record_diagnostics(value: object) -> tuple[bool, bool]:
    if not isinstance(value, list):
        raise AdmissionRecordError
    has_fail = has_error = False
    for item in value:
        diagnostic = _record_object(item, {"validator", "rule", "severity", "line"}, optional={"contract_id"})
        validator = _record_enum(diagnostic["validator"], frozenset(ADMISSION_RULES))
        _record_enum(diagnostic["rule"], ADMISSION_RULES[validator])
        severity = _record_enum(diagnostic["severity"], {"FAIL", "WARN", "ERROR"})
        line = diagnostic["line"]
        if line is not None and (type(line) is not int or line < 1):
            raise AdmissionRecordError
        if "contract_id" in diagnostic and (
            not isinstance(diagnostic["contract_id"], str)
            or re.fullmatch(r"CT\d+[a-z]?", diagnostic["contract_id"]) is None
        ):
            raise AdmissionRecordError
        has_fail |= severity == "FAIL"
        has_error |= severity == "ERROR"
    return has_fail, has_error


def _record_attempt_hashes(
    attempt: dict[str, Any], kind: str, validation: str, route: str, canonical_sha: str | None
) -> str | None:
    source, candidate, promoted = (attempt[key] for key in ("source_sha256", "candidate_sha256", "promoted_sha256"))
    for digest in (source, candidate, promoted):
        _record_hash(digest)
    if kind == "EXPLICIT_INPUT":
        if candidate is not None or promoted is not None:
            raise AdmissionRecordError
        if source is not None:
            if canonical_sha is not None and source != canonical_sha:
                raise AdmissionRecordError
            canonical_sha = source
    elif kind in {"ADMISSION_REPAIR", "EVAL_REPLAN"}:
        if source is None or source != canonical_sha:
            raise AdmissionRecordError
    if promoted is not None:
        if promoted != candidate or validation != "PASS":
            raise AdmissionRecordError
        canonical_sha = promoted
    if route == "ADMITTED" and (source if kind == "EXPLICIT_INPUT" else promoted) is None:
        raise AdmissionRecordError
    return canonical_sha


def _record_attempt(value: object, index: int, canonical_sha: str | None) -> tuple[str | None, str]:
    attempt = _record_object(
        value,
        {
            "attempt",
            "dispatch_kind",
            "validation",
            "diagnostics",
            "source_sha256",
            "candidate_sha256",
            "promoted_sha256",
            "route",
        },
    )
    if type(attempt["attempt"]) is not int or attempt["attempt"] != index:
        raise AdmissionRecordError
    kind = _record_enum(attempt["dispatch_kind"], {"EXPLICIT_INPUT", "ADMISSION_REPAIR", "EVAL_REPLAN", "ACQUISITION"})
    validation = _record_enum(attempt["validation"], {"PASS", "DIAGNOSTICS", "INDETERMINATE"})
    route = _record_enum(attempt["route"], {"RETRY", "ADMITTED", "BLOCKED"})
    has_fail, has_error = _record_diagnostics(attempt["diagnostics"])
    if (validation == "PASS" and (has_fail or has_error)) or (validation == "DIAGNOSTICS" and not has_fail):
        raise AdmissionRecordError
    if (has_error or validation == "INDETERMINATE") and (validation != "INDETERMINATE" or route != "BLOCKED"):
        raise AdmissionRecordError
    if route == "RETRY" and (validation != "DIAGNOSTICS" or not has_fail):
        raise AdmissionRecordError
    if route == "ADMITTED" and validation != "PASS":
        raise AdmissionRecordError
    return _record_attempt_hashes(attempt, kind, validation, route, canonical_sha), route


def validate_admission_record(value: object, *, run_id: str) -> dict[str, Any]:
    """Validate exact keys, all old attempts and canonical-hash/route coherence."""
    data = _record_object(value, {"schema_version", "run_id", "status", "plan_ref", "attempts"})
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise AdmissionRecordError
    if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", run_id) is None:
        raise AdmissionRecordError
    if data["run_id"] != run_id:
        raise AdmissionRecordError
    status = _record_enum(data["status"], {"ACQUIRING", "ADMITTED", "BLOCKED"})
    ref_sha = _record_plan_ref(data["plan_ref"])
    attempts = data["attempts"]
    if not isinstance(attempts, list) or (not attempts and status != "ACQUIRING"):
        raise AdmissionRecordError
    canonical_sha: str | None = None
    for index, item in enumerate(attempts, start=1):
        canonical_sha, _route = _record_attempt(item, index, canonical_sha)
    if attempts:
        if status != {"RETRY": "ACQUIRING", "ADMITTED": "ADMITTED", "BLOCKED": "BLOCKED"}[attempts[-1]["route"]]:
            raise AdmissionRecordError
        if canonical_sha != ref_sha:
            raise AdmissionRecordError
    return data
