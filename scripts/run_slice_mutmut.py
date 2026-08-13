#!/usr/bin/env python3
"""Run mutmut for an explicit or configured production slice without touching it.

The runner stages source, tests, dependencies, and a generated mutmut table in a
private root-backed directory. It treats mutmut 3.6.0's process status as harness
status only and derives the quality verdict from reconciled per-mutant results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MUTMUT_VERSION = "mutmut, version 3.6.0"
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_RESULT = Path("mutants/mutmut-slice-result.json")
DEFAULT_DIFF = Path("mutants/mutmut-slice-diffs.md")
_MIN_FREE_BYTES = 64 * 1024 * 1024
_VERSION_TIMEOUT_SECONDS = 30
_COMMAND_TIMEOUT_SECONDS = 120

Mode = Literal["explicit", "configured"]
Verdict = Literal["clean", "action_required", "infrastructure_failure"]
Status = Literal[
    "type_invalid",
    "survived",
    "no_tests",
    "timeout",
    "suspicious",
    "skipped",
    "interrupted",
    "segfault",
    "not_checked",
]

_STATUS_MAP: dict[str, Status] = {
    "caught by type check": "type_invalid",
    "survived": "survived",
    "no tests": "no_tests",
    "timeout": "timeout",
    "suspicious": "suspicious",
    "skipped": "skipped",
    "check was interrupted by user": "interrupted",
    "segfault": "segfault",
    "not checked": "not_checked",
}
_EXPORT_KEYS = {
    "killed",
    "survived",
    "total",
    "no_tests",
    "skipped",
    "suspicious",
    "timeout",
    "check_was_interrupted_by_user",
    "segfault",
}
_ACTIONABLE = frozenset(_STATUS_MAP.values()) - {"type_invalid"}
_PRESERVED_MUTMUT_KEYS = (
    "only_mutate",
    "do_not_mutate",
    "do_not_mutate_patterns",
    "max_stack_depth",
    "debug",
    "mutate_only_covered_lines",
    "timeout_multiplier",
    "timeout_constant",
    "use_setproctitle",
)
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class InputError(ValueError):
    """The caller supplied an invalid or unsafe runner request."""


class InfrastructureError(RuntimeError):
    """The mutation harness could not produce trustworthy complete results."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class SliceRequest:
    repo_root: Path
    mode: Mode
    source_paths: tuple[str, ...]
    test_paths: tuple[str, ...]
    also_copy: tuple[str, ...]
    tmp_root: Path
    result_json: Path
    diff_report: Path
    max_children: int
    timeout_seconds: int
    base_mutmut_config: dict[str, Any]


@dataclass(frozen=True)
class SliceResult:
    exit_code: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class Tools:
    mutmut: str
    mutmut_version: str
    pyrefly: str
    pyrefly_version: str


@dataclass(frozen=True)
class MutantRecord:
    name: str
    status: Status


@dataclass(frozen=True)
class ClassifiedResults:
    counts: dict[str, int]
    mutants: tuple[MutantRecord, ...]


def _log(message: str) -> None:
    print(f"[slice-mutmut] {message}", file=sys.stderr, flush=True)


def _read_mutmut_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "pyproject.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        raw = data["tool"]["mutmut"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise InputError(f"cannot read [tool.mutmut] from {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise InputError("[tool.mutmut] must be a table")
    return cast(dict[str, Any], raw)


def _string_list(config: dict[str, Any], key: str, *, required: bool) -> tuple[str, ...]:
    value = config.get(key)
    if value is None and not required:
        return ()
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
        raise InputError(f"[tool.mutmut].{key} must be a non-empty string array")
    return tuple(cast(list[str], value))


def _strict_utf8(value: str, *, field: str) -> None:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise InputError(f"{field} is not strict UTF-8: {value!r}") from exc


def _contains_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    if not path.is_dir():
        return False
    for root, directories, files in os.walk(path, followlinks=False):
        root_path = Path(root)
        for name in (*directories, *files):
            if (root_path / name).is_symlink():
                return True
    return False


def _validate_repo_path(repo_root: Path, raw: str, *, role: str) -> str:
    _strict_utf8(raw, field=role)
    relative = Path(raw)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise InputError(f"{role} path must be repository-relative without '..': {raw!r}")
    candidate = repo_root / relative
    try:
        resolved = candidate.resolve(strict=True)
        canonical_root = repo_root.resolve(strict=True)
        normalized = resolved.relative_to(canonical_root).as_posix()
    except (OSError, ValueError) as exc:
        raise InputError(f"{role} path is missing or escapes repository: {raw!r}") from exc
    expected_root = "src" if role == "source" else "tests" if role == "test" else None
    if expected_root is not None and (not Path(normalized).parts or Path(normalized).parts[0] != expected_root):
        raise InputError(f"{role} path must be under {expected_root}/: {raw!r}")
    if not resolved.is_file() and not resolved.is_dir():
        raise InputError(f"{role} path must be a regular file or directory: {raw!r}")
    if _contains_symlink(candidate):
        raise InputError(f"{role} path contains a symlink: {raw!r}")
    _strict_utf8(normalized, field=role)
    return normalized


def _reject_overlaps(paths: tuple[str, ...], *, role: str) -> None:
    normalized = [Path(path) for path in paths]
    for index, path in enumerate(normalized):
        for other in normalized[index + 1 :]:
            if path == other or path in other.parents or other in path.parents:
                raise InputError(f"{role} paths overlap: {path.as_posix()!r} and {other.as_posix()!r}")


def _safe_output(repo_root: Path, raw: Path, *, field: str) -> Path:
    if raw.is_absolute() or not raw.parts or ".." in raw.parts or raw.parts[0] != "mutants":
        raise InputError(f"{field} must be a repository-relative path under mutants/: {raw}")
    _strict_utf8(raw.as_posix(), field=field)
    current = repo_root
    for part in raw.parent.parts:
        current /= part
        if current.is_symlink():
            raise InputError(f"{field} parent must not be a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise InputError(f"{field} parent is not a directory: {current}")
    return repo_root / raw


def _validated_request(
    *,
    repo_root: Path,
    mode: Mode,
    source_paths: tuple[str, ...],
    test_paths: tuple[str, ...],
    also_copy: tuple[str, ...],
    tmp_root: Path,
    result_json: Path,
    diff_report: Path,
    max_children: int,
    timeout_seconds: int,
    base_mutmut_config: dict[str, Any],
) -> SliceRequest:
    if os.name != "posix":
        raise InputError("mutmut 3 requires POSIX/fork; use the configured pytest-gremlins mirror on Windows")
    if not source_paths or not test_paths:
        raise InputError("at least one --source and one --test are required")
    if max_children < 1 or max_children > 128:
        raise InputError("--max-children must be between 1 and 128")
    if timeout_seconds < 1 or timeout_seconds > 86_400:
        raise InputError("--timeout-seconds must be between 1 and 86400")
    if not tmp_root.is_absolute():
        raise InputError("--tmp-root must be absolute")

    sources = tuple(_validate_repo_path(repo_root, item, role="source") for item in source_paths)
    tests = tuple(_validate_repo_path(repo_root, item, role="test") for item in test_paths)
    copies = tuple(_validate_repo_path(repo_root, item, role="also_copy") for item in also_copy)
    _reject_overlaps(sources, role="source")
    _reject_overlaps(tests, role="test")
    if set(sources) & set(tests):
        raise InputError("source and test paths must be disjoint")

    result = _safe_output(repo_root, result_json, field="result JSON")
    diff = _safe_output(repo_root, diff_report, field="diff report")
    if result == diff:
        raise InputError("result JSON and diff report must be different paths")

    return SliceRequest(
        repo_root=repo_root,
        mode=mode,
        source_paths=sources,
        test_paths=tests,
        also_copy=copies,
        tmp_root=tmp_root,
        result_json=result,
        diff_report=diff,
        max_children=max_children,
        timeout_seconds=timeout_seconds,
        base_mutmut_config=base_mutmut_config,
    )


def request_from_configured_scope(
    repo_root: Path,
    *,
    source_override: tuple[str, ...] | None = None,
    tmp_root: Path | None = None,
    result_json: Path = DEFAULT_RESULT,
    diff_report: Path = DEFAULT_DIFF,
    max_children: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> SliceRequest:
    config = _read_mutmut_config(repo_root)
    sources = source_override or _string_list(config, "source_paths", required=True)
    tests = _string_list(config, "pytest_add_cli_args_test_selection", required=True)
    copies = _string_list(config, "also_copy", required=False)
    return _validated_request(
        repo_root=repo_root,
        mode="configured" if source_override is None else "explicit",
        source_paths=sources,
        test_paths=tests,
        also_copy=copies,
        tmp_root=tmp_root or repo_root.parent / ".fa-mutmut-runs",
        result_json=result_json,
        diff_report=diff_report,
        max_children=max_children if max_children is not None else min(os.cpu_count() or 4, 128),
        timeout_seconds=timeout_seconds,
        base_mutmut_config=config,
    )


def _resolve_tool(name: str, repo_root: Path) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    candidate = repo_root / ".venv" / "bin" / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def _capture(argv: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise InfrastructureError("tool_execution_failed", f"cannot execute {argv[0]!r}: {exc}") from exc


def _resolve_tools(repo_root: Path) -> Tools:
    mutmut = _resolve_tool("mutmut", repo_root)
    pyrefly = _resolve_tool("pyrefly", repo_root)
    if mutmut is None:
        raise InfrastructureError("tool_missing", "mutmut is not installed")
    if pyrefly is None:
        raise InfrastructureError("tool_missing", "pyrefly is not installed")

    mutmut_version_run = _capture([mutmut, "--version"], cwd=repo_root, timeout=_VERSION_TIMEOUT_SECONDS)
    mutmut_version = mutmut_version_run.stdout.strip()
    if mutmut_version_run.returncode != 0 or mutmut_version != EXPECTED_MUTMUT_VERSION:
        raise InfrastructureError(
            "tool_version_mismatch",
            f"expected {EXPECTED_MUTMUT_VERSION!r}, got rc={mutmut_version_run.returncode} {mutmut_version!r}",
        )
    pyrefly_version_run = _capture([pyrefly, "--version"], cwd=repo_root, timeout=_VERSION_TIMEOUT_SECONDS)
    pyrefly_version = pyrefly_version_run.stdout.strip()
    if pyrefly_version_run.returncode != 0 or not pyrefly_version.startswith("pyrefly "):
        raise InfrastructureError(
            "tool_version_failed",
            f"pyrefly --version failed: rc={pyrefly_version_run.returncode} output={pyrefly_version!r}",
        )
    return Tools(mutmut=mutmut, mutmut_version=mutmut_version, pyrefly=pyrefly, pyrefly_version=pyrefly_version)


def _iter_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for root, directories, names in os.walk(path, followlinks=False):
        root_path = Path(root)
        for name in (*directories, *names):
            if (root_path / name).is_symlink():
                raise InputError(f"staged input contains a symlink: {root_path / name}")
        files.extend(root_path / name for name in names)
    return sorted(files)


def _input_roots(request: SliceRequest) -> tuple[Path, ...]:
    roots = [request.repo_root / path for path in (*request.source_paths, *request.also_copy)]
    roots.extend((request.repo_root / "tests", request.repo_root / "pyproject.toml"))
    return tuple(roots)


def _input_digest(request: SliceRequest) -> str:
    digest = hashlib.sha256()
    seen: set[Path] = set()
    for root in _input_roots(request):
        for path in _iter_files(root):
            resolved = path.resolve(strict=True)
            if resolved in seen:
                continue
            seen.add(resolved)
            relative = resolved.relative_to(request.repo_root.resolve(strict=True)).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _ensure_scratch(request: SliceRequest) -> None:
    root = request.tmp_root
    if root.is_symlink():
        raise InfrastructureError("scratch_unsafe", f"scratch root is a symlink: {root}")
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
    except OSError as exc:
        raise InfrastructureError("scratch_failed", f"cannot create scratch root {root}: {exc}") from exc
    if not root.is_dir():
        raise InfrastructureError("scratch_failed", f"scratch root is not a directory: {root}")
    input_bytes = sum(path.stat().st_size for item in _input_roots(request) for path in _iter_files(item))
    required = max(input_bytes * 3, _MIN_FREE_BYTES)
    free = shutil.disk_usage(root).free
    if free < required:
        raise InfrastructureError("scratch_space_failed", f"scratch has {free} bytes free; need at least {required}")


def _copy_path(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in value) + "]"
    raise InputError(f"unsupported preserved mutmut config value: {value!r}")


def _mutmut_table(request: SliceRequest) -> str:
    type_command = [
        "pyrefly",
        "check",
        *request.source_paths,
        "--output-format=json",
        "--summary=none",
        "--progress-bar=no",
    ]
    lines = [
        "[tool.mutmut]\n",
        f"source_paths = {_toml_value(list(request.source_paths))}\n",
        f"pytest_add_cli_args_test_selection = {_toml_value(list(request.test_paths))}\n",
        f"also_copy = {_toml_value(list(request.also_copy))}\n",
        f"type_check_command = {_toml_value(type_command)}\n",
    ]
    for key in _PRESERVED_MUTMUT_KEYS:
        if key in request.base_mutmut_config:
            lines.append(f"{key} = {_toml_value(request.base_mutmut_config[key])}\n")
    return "".join(lines)


def _replace_mutmut_table(text: str, replacement: str) -> str:
    lines = text.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.strip() == "[tool.mutmut]"]
    if len(starts) != 1:
        raise InputError(f"expected exactly one [tool.mutmut] section, found {len(starts)}")
    start = starts[0]
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break
    generated = "".join((*lines[:start], replacement, "\n", *lines[end:]))
    try:
        tomllib.loads(generated)
    except tomllib.TOMLDecodeError as exc:
        raise InputError(f"generated staged pyproject is invalid: {exc}") from exc
    return generated


def _stage(request: SliceRequest) -> Path:
    _ensure_scratch(request)
    stage: Path | None = None
    try:
        stage = Path(tempfile.mkdtemp(prefix="mutmut-", dir=request.tmp_root))
        stage.chmod(0o700)
        for relative in request.source_paths:
            _copy_path(request.repo_root / relative, stage / relative)
        for relative in request.also_copy:
            _copy_path(request.repo_root / relative, stage / relative)
        _copy_path(request.repo_root / "tests", stage / "tests")
        base = (request.repo_root / "pyproject.toml").read_text(encoding="utf-8")
        (stage / "pyproject.toml").write_text(_replace_mutmut_table(base, _mutmut_table(request)), encoding="utf-8")
        return stage
    except (OSError, UnicodeError) as exc:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)
        raise InfrastructureError("staging_failed", f"cannot stage mutation inputs: {exc}") from exc


def _tool_environment(tools: Tools) -> dict[str, str]:
    env = os.environ.copy()
    tool_dirs = list(dict.fromkeys((str(Path(tools.mutmut).parent), str(Path(tools.pyrefly).parent))))
    env["PATH"] = os.pathsep.join((*tool_dirs, env.get("PATH", "")))
    env["NO_COLOR"] = "1"
    return env


def _terminate_process_group(process_group: int) -> None:
    try:
        os.killpg(process_group, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.killpg(process_group, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    try:
        os.killpg(process_group, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_process_group(argv: list[str], *, cwd: Path, timeout: int, env: dict[str, str]) -> int:
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True)
    except OSError as exc:
        raise InfrastructureError("tool_execution_failed", f"cannot start {argv[0]!r}: {exc}") from exc
    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        _terminate_process_group(process.pid)
        process.wait()
        raise InfrastructureError("mutation_timeout", f"mutmut exceeded {timeout} seconds") from exc
    _terminate_process_group(process.pid)
    return return_code


def _parse_results(output: str) -> tuple[MutantRecord, ...]:
    records: list[MutantRecord] = []
    seen: set[str] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        name, separator, raw_status = line.rpartition(": ")
        if not separator or not name or raw_status not in _STATUS_MAP:
            raise InfrastructureError("result_parse_failed", f"unknown mutmut results line: {raw_line!r}")
        if name in seen:
            raise InfrastructureError("result_parse_failed", f"duplicate mutmut result: {name}")
        seen.add(name)
        records.append(MutantRecord(name=name, status=_STATUS_MAP[raw_status]))
    return tuple(records)


def _load_export(stage: Path) -> dict[str, int]:
    path = stage / "mutants" / "mutmut-cicd-stats.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InfrastructureError("result_export_failed", f"cannot read mutmut stats: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != _EXPORT_KEYS:
        raise InfrastructureError("result_export_failed", f"unexpected mutmut stats keys: {raw!r}")
    result: dict[str, int] = {}
    for key, value in raw.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise InfrastructureError("result_export_failed", f"invalid mutmut count {key}={value!r}")
        result[key] = value
    return result


def _classify(exported: dict[str, int], records: tuple[MutantRecord, ...]) -> ClassifiedResults:
    by_status: dict[Status, int] = dict.fromkeys(_STATUS_MAP.values(), 0)
    for record in records:
        by_status[record.status] += 1
    export_map: dict[str, Status] = {
        "survived": "survived",
        "no_tests": "no_tests",
        "skipped": "skipped",
        "suspicious": "suspicious",
        "timeout": "timeout",
        "check_was_interrupted_by_user": "interrupted",
        "segfault": "segfault",
    }
    for export_key, status in export_map.items():
        if exported[export_key] != by_status[status]:
            raise InfrastructureError(
                "result_identity_failed",
                f"{export_key} export={exported[export_key]} results={by_status[status]}",
            )
    counts = {
        "total": exported["total"],
        "killed": exported["killed"],
        "type_invalid": by_status["type_invalid"],
        "survived": by_status["survived"],
        "no_tests": by_status["no_tests"],
        "timeout": by_status["timeout"],
        "suspicious": by_status["suspicious"],
        "skipped": by_status["skipped"],
        "interrupted": by_status["interrupted"],
        "segfault": by_status["segfault"],
        "not_checked": by_status["not_checked"],
    }
    if counts["total"] <= 0 or counts["total"] != sum(value for key, value in counts.items() if key != "total"):
        raise InfrastructureError("result_identity_failed", f"mutation counts do not close: {counts}")
    return ClassifiedResults(counts=counts, mutants=records)


def _clean_output(text: str) -> str:
    text = _ANSI_ESCAPE.sub("", text)
    return "".join(character for character in text if character in "\n\t" or ord(character) >= 32)


def _diff_report(tools: Tools, stage: Path, classified: ClassifiedResults) -> tuple[str, dict[str, str]]:
    lines = ["# Actionable mutation diffs\n\n"]
    anchors: dict[str, str] = {}
    actionable = [record for record in classified.mutants if record.status in _ACTIONABLE]
    if not actionable:
        lines.append("No actionable mutants. Type-invalid mutants are listed in the JSON result.\n")
        return "".join(lines), anchors
    for index, record in enumerate(actionable, start=1):
        shown = _capture([tools.mutmut, "show", record.name], cwd=stage, timeout=_COMMAND_TIMEOUT_SECONDS)
        if shown.returncode != 0:
            raise InfrastructureError(
                "mutant_show_failed",
                f"mutmut show failed for {record.name}: rc={shown.returncode}",
            )
        anchor = f"mutant-{index}"
        anchors[record.name] = anchor
        lines.extend((f"## {index}. `{record.name}` {{#{anchor}}}\n\n", f"Status: `{record.status}`\n\n"))
        for line in _clean_output(shown.stdout).splitlines():
            lines.append(f"    {line}\n")
        lines.append("\n")
    return "".join(lines), anchors


def _ensure_output_parent(path: Path, repo_root: Path) -> None:
    relative_parent = path.parent.relative_to(repo_root)
    current = repo_root
    for part in relative_parent.parts:
        current /= part
        if current.is_symlink():
            raise InfrastructureError("artifact_failed", f"artifact parent is a symlink: {current}")
        try:
            current.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise InfrastructureError("artifact_failed", f"cannot create artifact directory {current}: {exc}") from exc
        if not current.is_dir():
            raise InfrastructureError("artifact_failed", f"artifact parent is not a directory: {current}")


def _atomic_write(path: Path, content: str, repo_root: Path) -> None:
    _ensure_output_parent(path, repo_root)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = -1
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise InfrastructureError("artifact_failed", f"cannot write artifact {path}: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _artifact_payload(
    request: SliceRequest,
    tools: Tools,
    classified: ClassifiedResults,
    anchors: dict[str, str],
    *,
    started_at: datetime,
    duration_seconds: float,
) -> dict[str, Any]:
    actionable = any(record.status in _ACTIONABLE for record in classified.mutants)
    denominator = classified.counts["total"] - classified.counts["type_invalid"]
    score = classified.counts["killed"] / denominator if denominator else None
    return {
        "schema_version": 1,
        "completed": True,
        "verdict": "action_required" if actionable else "clean",
        "reason": None,
        "mode": request.mode,
        "source_paths": list(request.source_paths),
        "test_paths": list(request.test_paths),
        "also_copy": list(request.also_copy),
        "tools": {"mutmut": tools.mutmut_version, "pyrefly": tools.pyrefly_version},
        "type_filter_enabled": True,
        "started_at": started_at.isoformat(),
        "duration_seconds": round(duration_seconds, 6),
        "counts": classified.counts,
        "mutation_score_non_type_invalid": score,
        "mutants": [
            {"name": record.name, "status": record.status, "diff_anchor": anchors.get(record.name)}
            for record in classified.mutants
        ],
    }


def _failure_payload(request: SliceRequest, error: InfrastructureError, started_at: datetime) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "completed": False,
        "verdict": "infrastructure_failure",
        "reason": error.reason,
        "detail": error.detail,
        "mode": request.mode,
        "source_paths": list(request.source_paths),
        "test_paths": list(request.test_paths),
        "also_copy": list(request.also_copy),
        "started_at": started_at.isoformat(),
    }


def _write_failure_best_effort(request: SliceRequest, payload: dict[str, Any]) -> None:
    try:
        _atomic_write(request.result_json, json.dumps(payload, indent=2, sort_keys=True) + "\n", request.repo_root)
    except InfrastructureError:
        pass


def _cleanup_stage(stage: Path) -> None:
    try:
        shutil.rmtree(stage)
    except OSError as exc:
        raise InfrastructureError("stage_cleanup_failed", f"cannot remove mutation stage {stage}: {exc}") from exc
    if stage.exists() or stage.is_symlink():
        raise InfrastructureError("stage_cleanup_failed", f"mutation stage still exists: {stage}")


def run_slice(request: SliceRequest) -> SliceResult:
    started_at = datetime.now(UTC)
    started = time.monotonic()
    stage: Path | None = None
    try:
        digest_before = _input_digest(request)
        tools = _resolve_tools(request.repo_root)
        stage = _stage(request)
        run_rc = _run_process_group(
            [tools.mutmut, "run", "--max-children", str(request.max_children)],
            cwd=stage,
            timeout=request.timeout_seconds,
            env=_tool_environment(tools),
        )
        if run_rc != 0:
            raise InfrastructureError("mutmut_run_failed", f"mutmut run returned {run_rc}")
        results = _capture([tools.mutmut, "results"], cwd=stage, timeout=_COMMAND_TIMEOUT_SECONDS)
        if results.returncode != 0:
            raise InfrastructureError("result_command_failed", f"mutmut results returned {results.returncode}")
        exported = _capture([tools.mutmut, "export-cicd-stats"], cwd=stage, timeout=_COMMAND_TIMEOUT_SECONDS)
        if exported.returncode != 0:
            raise InfrastructureError("result_command_failed", f"mutmut export returned {exported.returncode}")
        classified = _classify(_load_export(stage), _parse_results(results.stdout))
        report, anchors = _diff_report(tools, stage, classified)
        if _input_digest(request) != digest_before:
            raise InfrastructureError(
                "input_integrity_failed",
                "repository source, tests, or pyproject changed during run",
            )
        _cleanup_stage(stage)
        stage = None
        payload = _artifact_payload(
            request,
            tools,
            classified,
            anchors,
            started_at=started_at,
            duration_seconds=time.monotonic() - started,
        )
        _atomic_write(request.diff_report, report, request.repo_root)
        _atomic_write(request.result_json, json.dumps(payload, indent=2, sort_keys=True) + "\n", request.repo_root)
        return SliceResult(exit_code=1 if payload["verdict"] == "action_required" else 0, payload=payload)
    except InfrastructureError as exc:
        payload = _failure_payload(request, exc, started_at)
        _write_failure_best_effort(request, payload)
        return SliceResult(exit_code=3, payload=payload)
    except (InputError, OSError, UnicodeError) as exc:
        wrapped = InfrastructureError("runtime_input_failed", str(exc))
        payload = _failure_payload(request, wrapped, started_at)
        _write_failure_best_effort(request, payload)
        return SliceResult(exit_code=3, payload=payload)
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configured-scope", action="store_true")
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--test", action="append", default=[])
    parser.add_argument("--also-copy", action="append", default=[])
    parser.add_argument("--tmp-root", type=Path)
    parser.add_argument("--result-json", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--diff-report", type=Path, default=DEFAULT_DIFF)
    parser.add_argument("--max-children", type=int, default=min(os.cpu_count() or 4, 128))
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def _request_from_args(args: argparse.Namespace) -> SliceRequest:
    config = _read_mutmut_config(REPO_ROOT)
    cli_sources = tuple(cast(list[str], args.source))
    cli_tests = tuple(cast(list[str], args.test))
    cli_copies = tuple(cast(list[str], args.also_copy))
    if args.configured_scope:
        if cli_sources or cli_tests or cli_copies:
            raise InputError("--configured-scope is mutually exclusive with --source/--test/--also-copy")
        sources = _string_list(config, "source_paths", required=True)
        tests = _string_list(config, "pytest_add_cli_args_test_selection", required=True)
        copies = _string_list(config, "also_copy", required=False)
        mode: Mode = "configured"
    else:
        sources, tests, copies, mode = cli_sources, cli_tests, cli_copies, "explicit"
    return _validated_request(
        repo_root=REPO_ROOT,
        mode=mode,
        source_paths=sources,
        test_paths=tests,
        also_copy=copies,
        tmp_root=cast(Path | None, args.tmp_root) or REPO_ROOT.parent / ".fa-mutmut-runs",
        result_json=cast(Path, args.result_json),
        diff_report=cast(Path, args.diff_report),
        max_children=cast(int, args.max_children),
        timeout_seconds=cast(int, args.timeout_seconds),
        base_mutmut_config=config,
    )


def main() -> int:
    try:
        request = _request_from_args(_parser().parse_args())
    except InputError as exc:
        _log(f"invalid request: {exc}")
        return 2
    result = run_slice(request)
    if result.exit_code == 3:
        _log(f"infrastructure failure [{result.payload['reason']}]: {result.payload.get('detail', '')}")
    else:
        counts = result.payload["counts"]
        _log(
            f"{result.payload['verdict']}: total={counts['total']} killed={counts['killed']} "
            f"type_invalid={counts['type_invalid']} survived={counts['survived']}"
        )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
