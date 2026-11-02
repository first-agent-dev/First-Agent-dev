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

# v2 extends the closed v1 vocabulary without changing what an old v1 record
# accepts. Keep ADMISSION_RULES as the immutable v1 contract for existing callers.
ADMISSION_RULES_V2: dict[str, frozenset[str]] = {
    **ADMISSION_RULES,
    "bootstrap": ADMISSION_RULES["bootstrap"]
    | frozenset(
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
    ),
    "selection": frozenset(
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
    ),
    "workspace": frozenset(
        {
            "busy",
            "stale-generation",
            "stale-revision",
            "quarantined",
            "backend-unavailable",
            "terminality-unknown",
        }
    ),
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


def _record_diagnostics(value: object, *, rules: dict[str, frozenset[str]] = ADMISSION_RULES) -> tuple[bool, bool]:
    if not isinstance(value, list):
        raise AdmissionRecordError
    has_fail = has_error = False
    for item in value:
        diagnostic = _record_object(item, {"validator", "rule", "severity", "line"}, optional={"contract_id"})
        validator = _record_enum(diagnostic["validator"], frozenset(rules))
        _record_enum(diagnostic["rule"], rules[validator])
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


_V1_RECORD_KEYS = {"schema_version", "run_id", "status", "plan_ref", "attempts"}
_V1_ATTEMPT_KEYS = {
    "attempt",
    "dispatch_kind",
    "validation",
    "diagnostics",
    "source_sha256",
    "candidate_sha256",
    "promoted_sha256",
    "route",
}
_V2_RECORD_KEYS = _V1_RECORD_KEYS | {"workspace_id", "owner_run_id", "generation", "base_revision"}
_V2_ATTEMPT_KEYS = _V1_ATTEMPT_KEYS | {"input_revision", "output_revision", "operation_id", "bundle_sha256"}
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_WORKSPACE_ID_PATTERN = re.compile(r"ws-[0-9a-f]{32}")
_REVISION_ID_PATTERN = re.compile(r"rev-[0-9a-f]{32}")
_OPERATION_ID_PATTERN = re.compile(r"op-[0-9a-f]{32}")


def _validate_record_identity(data: dict[str, Any], run_id: str) -> str:
    if not isinstance(run_id, str) or _RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise AdmissionRecordError
    if data["run_id"] != run_id:
        raise AdmissionRecordError
    return _record_enum(data["status"], {"ACQUIRING", "ADMITTED", "BLOCKED"})


def _validate_v1_record(value: object, *, run_id: str) -> dict[str, Any]:
    """Keep the original complete-v1 reader exact; never synthesize v2 fields."""
    data = _record_object(value, _V1_RECORD_KEYS)
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise AdmissionRecordError
    status = _validate_record_identity(data, run_id)
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


def _v2_diagnostics(value: object) -> tuple[bool, bool, tuple[dict[str, Any], ...]]:
    diagnostics = value if isinstance(value, list) else None
    if diagnostics is None:
        raise AdmissionRecordError
    has_fail, has_error = _record_diagnostics(diagnostics, rules=ADMISSION_RULES_V2)
    return has_fail, has_error, tuple(diagnostics)


def _validate_v2_attempt_outcome(
    attempt: dict[str, Any], *, index: int, kind: str
) -> tuple[str, bool, bool, tuple[dict[str, Any], ...]]:
    if type(attempt["attempt"]) is not int or attempt["attempt"] != index:
        raise AdmissionRecordError
    if attempt["dispatch_kind"] != kind:
        raise AdmissionRecordError
    validation = _record_enum(attempt["validation"], {"PASS", "DIAGNOSTICS", "INDETERMINATE"})
    route = _record_enum(attempt["route"], {"RETRY", "ADMITTED", "BLOCKED"})
    has_fail, has_error, diagnostics = _v2_diagnostics(attempt["diagnostics"])
    if (validation == "PASS" and (has_fail or has_error)) or (validation == "DIAGNOSTICS" and not has_fail):
        raise AdmissionRecordError
    if (has_error or validation == "INDETERMINATE") and (validation != "INDETERMINATE" or route != "BLOCKED"):
        raise AdmissionRecordError
    if route == "RETRY" and (validation != "DIAGNOSTICS" or not has_fail):
        raise AdmissionRecordError
    if route == "ADMITTED" and validation != "PASS":
        raise AdmissionRecordError
    return validation, has_fail, has_error, diagnostics


def _validate_v2_attempt_revisions(attempt: dict[str, Any]) -> tuple[str, str | None, str | None]:
    input_revision = attempt["input_revision"]
    output_revision = attempt["output_revision"]
    operation_id = attempt["operation_id"]
    if not isinstance(input_revision, str) or _REVISION_ID_PATTERN.fullmatch(input_revision) is None:
        raise AdmissionRecordError
    if output_revision is not None and (
        not isinstance(output_revision, str) or _REVISION_ID_PATTERN.fullmatch(output_revision) is None
    ):
        raise AdmissionRecordError
    if operation_id is not None and (
        not isinstance(operation_id, str) or _OPERATION_ID_PATTERN.fullmatch(operation_id) is None
    ):
        raise AdmissionRecordError
    return input_revision, output_revision, operation_id


def _acquisition_hashes(attempt: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    source, candidate, promoted = (attempt[key] for key in ("source_sha256", "candidate_sha256", "promoted_sha256"))
    bundle = attempt["bundle_sha256"]
    for digest in (source, candidate, promoted, bundle):
        _record_hash(digest)
    return source, candidate, promoted


def _validate_v2_existing_selection(
    attempt: dict[str, Any],
    ref: dict[str, Any] | None,
    *,
    validation: str,
    route: str,
    diagnostics: tuple[dict[str, Any], ...],
) -> str:
    source, candidate, promoted = _acquisition_hashes(attempt)
    input_revision, output_revision, operation_id = _validate_v2_attempt_revisions(attempt)
    if (
        ref is None
        or ref["source_kind"] != "EXISTING_SELECTION"
        or source is None
        or candidate is not None
        or promoted is not None
        or attempt["bundle_sha256"] is not None
        or output_revision != input_revision
        or operation_id is not None
    ):
        raise AdmissionRecordError
    if route == "ADMITTED" and validation != "PASS":
        raise AdmissionRecordError
    if route == "RETRY" and (
        validation != "DIAGNOSTICS"
        or any(
            item["validator"] not in {"precheck", "kill-directives", "plan-ref"} or item["severity"] != "FAIL"
            for item in diagnostics
        )
    ):
        raise AdmissionRecordError
    if route == "BLOCKED" and (
        validation != "INDETERMINATE"
        or not any(
            item["validator"] in {"workspace", "plan-ref"} and item["severity"] == "ERROR" for item in diagnostics
        )
    ):
        raise AdmissionRecordError
    return source


def _validate_v2_bootstrap(
    attempt: dict[str, Any],
    ref: dict[str, Any] | None,
    *,
    validation: str,
    route: str,
    diagnostics: tuple[dict[str, Any], ...],
) -> str | None:
    source, candidate, promoted = _acquisition_hashes(attempt)
    input_revision, output_revision, operation_id = _validate_v2_attempt_revisions(attempt)
    bundle = attempt["bundle_sha256"]
    if source is not None:
        raise AdmissionRecordError
    if route == "ADMITTED":
        if (
            validation != "PASS"
            or ref is None
            or ref["source_kind"] != "BOOTSTRAP"
            or candidate is None
            or promoted != candidate
            or bundle is None
            or output_revision is None
            or output_revision == input_revision
            or operation_id is None
        ):
            raise AdmissionRecordError
        return promoted
    if route != "BLOCKED" or ref is not None or promoted is not None or output_revision is not None:
        raise AdmissionRecordError
    if (candidate is None) != (bundle is None):
        raise AdmissionRecordError
    if validation not in {"DIAGNOSTICS", "INDETERMINATE"}:
        raise AdmissionRecordError
    if candidate is None:
        if operation_id is not None:
            raise AdmissionRecordError
        if validation == "DIAGNOSTICS" and not any(
            item["validator"] == "bootstrap" and item["severity"] == "FAIL" for item in diagnostics
        ):
            raise AdmissionRecordError
        if validation == "INDETERMINATE" and not any(
            item["validator"] in {"bootstrap", "selection", "workspace"} and item["severity"] == "ERROR"
            for item in diagnostics
        ):
            raise AdmissionRecordError
    else:
        if any(item["validator"] == "selection" for item in diagnostics):
            raise AdmissionRecordError
        if validation == "DIAGNOSTICS" and not any(
            item["validator"] == "bootstrap" and item["severity"] == "FAIL" for item in diagnostics
        ):
            raise AdmissionRecordError
        if validation == "INDETERMINATE" and not any(
            item["validator"] in {"bootstrap", "workspace"} and item["severity"] == "ERROR" for item in diagnostics
        ):
            raise AdmissionRecordError
    if operation_id is not None and not any(
        (item["validator"], item["rule"])
        in {
            ("bootstrap", "install-failed"),
            ("bootstrap", "durability-unknown"),
            ("workspace", "terminality-unknown"),
        }
        for item in diagnostics
    ):
        raise AdmissionRecordError
    return None


def _validate_v2_acquisition(
    attempt: dict[str, Any], ref: dict[str, Any] | None, *, index: int, kind: str
) -> str | None:
    validation, _has_fail, _has_error, diagnostics = _validate_v2_attempt_outcome(attempt, index=index, kind=kind)
    route = attempt["route"]
    if index != 1:
        raise AdmissionRecordError
    if ref is not None and ref["source_kind"] == "EXISTING_SELECTION":
        return _validate_v2_existing_selection(
            attempt, ref, validation=validation, route=route, diagnostics=diagnostics
        )
    return _validate_v2_bootstrap(attempt, ref, validation=validation, route=route, diagnostics=diagnostics)


def _validate_v2_attempt(
    value: object, *, index: int, canonical_sha: str | None, ref: dict[str, Any] | None
) -> tuple[str | None, str, str, str | None, str | None]:
    attempt = _record_object(value, _V2_ATTEMPT_KEYS)
    kind = _record_enum(attempt["dispatch_kind"], {"EXPLICIT_INPUT", "ADMISSION_REPAIR", "EVAL_REPLAN", "ACQUISITION"})
    input_revision, output_revision, operation_id = _validate_v2_attempt_revisions(attempt)
    if attempt["bundle_sha256"] is not None:
        _record_hash(attempt["bundle_sha256"])
    if kind == "ACQUISITION":
        next_canonical = _validate_v2_acquisition(attempt, ref, index=index, kind=kind)
        if next_canonical is not None:
            canonical_sha = next_canonical
    else:
        if attempt["bundle_sha256"] is not None:
            raise AdmissionRecordError
        core_attempt = {key: attempt[key] for key in _V1_ATTEMPT_KEYS}
        canonical_sha, route = _record_attempt(core_attempt, index, canonical_sha)
        validation = attempt["validation"]
        if output_revision is not None and output_revision != input_revision and operation_id is None:
            raise AdmissionRecordError
        if (
            operation_id is not None
            and output_revision is None
            and (validation != "INDETERMINATE" or route != "BLOCKED")
        ):
            raise AdmissionRecordError
        if attempt["promoted_sha256"] is not None and (output_revision is None or operation_id is None):
            raise AdmissionRecordError
    return canonical_sha, attempt["route"], input_revision, output_revision, operation_id


def _validate_v2_record(value: object, *, run_id: str) -> dict[str, Any]:
    data = _record_object(value, _V2_RECORD_KEYS)
    if type(data["schema_version"]) is not int or data["schema_version"] != 2:
        raise AdmissionRecordError
    status = _validate_record_identity(data, run_id)
    owner_run_id = data["owner_run_id"]
    if (
        not isinstance(owner_run_id, str)
        or _RUN_ID_PATTERN.fullmatch(owner_run_id) is None
        or owner_run_id == run_id
        or not isinstance(data["workspace_id"], str)
        or _WORKSPACE_ID_PATTERN.fullmatch(data["workspace_id"]) is None
        or type(data["generation"]) is not int
        or data["generation"] < 1
        or not isinstance(data["base_revision"], str)
        or _REVISION_ID_PATTERN.fullmatch(data["base_revision"]) is None
    ):
        raise AdmissionRecordError
    ref = (
        None
        if data["plan_ref"] is None
        else _record_object(data["plan_ref"], {"workspace_relative_path", "source_kind", "sha256"})
    )
    ref_sha = _record_plan_ref(data["plan_ref"])
    attempts = data["attempts"]
    if not isinstance(attempts, list) or (not attempts and status != "ACQUIRING"):
        raise AdmissionRecordError
    canonical_sha: str | None = None
    previous_output: str | None = None
    previous_operation: str | None = None
    previous_route: str | None = None
    for index, item in enumerate(attempts, start=1):
        canonical_sha, route, input_revision, output_revision, operation_id = _validate_v2_attempt(
            item, index=index, canonical_sha=canonical_sha, ref=ref
        )
        if index == 1 and input_revision != data["base_revision"]:
            raise AdmissionRecordError
        if index > 1 and (previous_route == "BLOCKED" or (previous_operation is not None and previous_output is None)):
            raise AdmissionRecordError
        previous_output, previous_operation, previous_route = output_revision, operation_id, route
    if attempts:
        if status != {"RETRY": "ACQUIRING", "ADMITTED": "ADMITTED", "BLOCKED": "BLOCKED"}[attempts[-1]["route"]]:
            raise AdmissionRecordError
        if canonical_sha != ref_sha:
            raise AdmissionRecordError
    return data


def validate_admission_record(value: object, *, run_id: str) -> dict[str, Any]:
    """Validate complete v1/v2 records without upgrading or filling old history."""
    if not isinstance(value, dict):
        raise AdmissionRecordError
    version = value.get("schema_version")
    if type(version) is not int:
        raise AdmissionRecordError
    if version == 1:
        return _validate_v1_record(value, run_id=run_id)
    if version == 2:
        return _validate_v2_record(value, run_id=run_id)
    raise AdmissionRecordError
