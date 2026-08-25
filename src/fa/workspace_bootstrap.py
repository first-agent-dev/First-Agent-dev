"""Deterministic readiness transaction for First-Agent managed workspaces.

The engine is stdlib-only. It validates active environment and hook state,
serializes repair under a workspace lock, and returns typed degraded state
instead of raising ordinary failures through agent admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, overload

from fa.hygiene.hooks._util import HOOK_NAMES, resolve_default_hooks_dir, resolve_hooks_dir
from fa.hygiene.hooks.install import install_hooks

ReadyReason = Literal[
    "ready_fast_path",
    "ready_repaired",
    "lock_timeout",
    "tool_missing",
    "sync_failed",
    "sync_timeout",
    "precommit_prewarm_failed",
    "precommit_prewarm_timeout",
    "locked_check_failed",
    "hook_status_failed",
    "custom_hooks_unmanaged",
    "hook_seat_collision",
    "invalid_workspace",
    "fingerprint_failed",
    "state_io_failed",
    "unexpected_internal_error",
]

_BOOTSTRAP_SCHEMA = 2
_LOCK_TIMEOUT_SECONDS = 120.0
_LOCK_POLL_SECONDS = 0.1
_COMMAND_TIMEOUT_SECONDS = 120.0
_SYNC_TIMEOUT_SECONDS = 900.0
_PRECOMMIT_TIMEOUT_SECONDS = 900.0
_PRIVATE_DIR_MODE = 0o700
_PRIVATE_FILE_MODE = 0o600
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_VENV_BIN = "Scripts" if os.name == "nt" else "bin"
_PROJECT_PYTHON = "python.exe" if os.name == "nt" else "python"
_PRECOMMIT = "pre-commit.exe" if os.name == "nt" else "pre-commit"
_RUNTIME_PYTHON_MINOR = f"{sys.version_info.major}.{sys.version_info.minor}"

_REQUIRED_ROOT_FILES = (
    Path("knowledge/llms.txt"),
    Path("pyproject.toml"),
    Path("uv.lock"),
    Path(".pre-commit-config.yaml"),
)
_HOOK_SOURCE_RELATIVE = Path("src/fa/hygiene/hooks")
_MARKER_RELATIVE = Path(".fa/ready-state.json")
_LOG_RELATIVE = Path(".fa/bootstrap.log")
_LOCK_RELATIVE = Path(".fa/bootstrap.lock")
_UV_VERSION_ARGV = ("uv", "--version")
_UV_SYNC_ARGV = ("uv", "sync", "--locked", "--extra", "dev")
_UV_CHECK_ARGV = (*_UV_SYNC_ARGV, "--check")
_PRECOMMIT_ARGV = (".venv/bin/pre-commit", "install-hooks")
_PYTHON_ARGV = (".venv/bin/python", "-c", "<version-probe>")

_ENVIRONMENT_REASONS: frozenset[ReadyReason] = frozenset(
    {
        "lock_timeout",
        "tool_missing",
        "sync_failed",
        "sync_timeout",
        "precommit_prewarm_failed",
        "precommit_prewarm_timeout",
        "locked_check_failed",
        "hook_status_failed",
        "custom_hooks_unmanaged",
        "hook_seat_collision",
    }
)
_TELEMETRY: dict[ReadyReason, tuple[str, tuple[str, ...]]] = {
    "ready_fast_path": ("fast_validate", ()),
    "ready_repaired": ("ready", ()),
    "lock_timeout": ("lock", ()),
    "tool_missing": ("uv_version", _UV_VERSION_ARGV),
    "sync_failed": ("uv_sync", _UV_SYNC_ARGV),
    "sync_timeout": ("uv_sync", _UV_SYNC_ARGV),
    "precommit_prewarm_failed": ("precommit_prewarm", _PRECOMMIT_ARGV),
    "precommit_prewarm_timeout": ("precommit_prewarm", _PRECOMMIT_ARGV),
    "locked_check_failed": ("uv_locked_check", _UV_CHECK_ARGV),
    "hook_status_failed": ("hook_status", ("check_hooks",)),
    "custom_hooks_unmanaged": ("hook_ownership", ()),
    "hook_seat_collision": ("hook_ownership", ()),
    "invalid_workspace": ("validate_workspace", ()),
    "fingerprint_failed": ("fingerprint", ()),
    "state_io_failed": ("state_io", ()),
    "unexpected_internal_error": ("unexpected", ()),
}


class ReadyStatus(StrEnum):
    """Closed readiness result classes consumed by lifecycle adapters."""

    READY = "ready"
    DEGRADED_ENVIRONMENT = "degraded_environment"
    DEGRADED_INTERNAL = "degraded_internal"


@dataclass(frozen=True, slots=True)
class ReadyState:
    """One observable readiness outcome."""

    status: ReadyStatus
    fingerprint: str | None
    reason_code: ReadyReason
    log_path: Path
    repaired: bool
    elapsed_ms: int


@dataclass(slots=True)
class _ReadinessError(Exception):
    reason_code: ReadyReason
    return_code: int | None = None
    fingerprint: str | None = None


class _LockTimeoutError(Exception):
    pass


class _Hash(Protocol):
    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


def _status_for(reason_code: ReadyReason) -> ReadyStatus:
    if reason_code in ("ready_fast_path", "ready_repaired"):
        return ReadyStatus.READY
    if reason_code in _ENVIRONMENT_REASONS:
        return ReadyStatus.DEGRADED_ENVIRONMENT
    return ReadyStatus.DEGRADED_INTERNAL


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _state(
    reason_code: ReadyReason,
    workspace: Path,
    started: float,
    *,
    fingerprint: str | None = None,
) -> ReadyState:
    return ReadyState(
        status=_status_for(reason_code),
        fingerprint=fingerprint,
        reason_code=reason_code,
        log_path=(workspace / _LOG_RELATIVE).resolve(),
        repaired=reason_code == "ready_repaired",
        elapsed_ms=_elapsed_ms(started),
    )


def _validate_workspace(workspace: Path) -> tuple[Path, Path]:
    resolved = Path(workspace).expanduser().resolve()
    dot_git = resolved / ".git"
    if not resolved.is_dir() or not (dot_git.is_dir() or dot_git.is_file()):
        raise ValueError
    if any(not (resolved / relative).is_file() for relative in _REQUIRED_ROOT_FILES):
        raise ValueError
    hook_source_dir = (resolved / _HOOK_SOURCE_RELATIVE).resolve()
    hook_inputs = tuple(hook_source_dir / name for name in (*HOOK_NAMES, "install.py", "status.py"))
    if not hook_source_dir.is_relative_to(resolved) or any(
        not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(hook_source_dir)
        for source in hook_inputs
    ):
        raise ValueError
    return resolved, hook_source_dir


def _open_private(path: Path, flags: int) -> int:
    if path.is_symlink():
        raise OSError
    descriptor = os.open(path, flags | _O_NOFOLLOW, _PRIVATE_FILE_MODE)
    os.fchmod(descriptor, _PRIVATE_FILE_MODE)
    return descriptor


def _ensure_private_state_paths(workspace: Path) -> None:
    state_dir = workspace / ".fa"
    if state_dir.is_symlink():
        raise OSError
    state_dir.mkdir(exist_ok=True)
    state_dir.chmod(_PRIVATE_DIR_MODE)
    descriptor = _open_private(workspace / _LOG_RELATIVE, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    os.close(descriptor)


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    """Acquire the CT3 non-blocking flock with a monotonic bounded wait."""

    import fcntl

    descriptor = _open_private(path, os.O_RDWR | os.O_CREAT)
    deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise _LockTimeoutError from None
                time.sleep(_LOCK_POLL_SECONDS)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _command_environment(workspace: Path | None = None) -> dict[str, str]:
    """Return a hermetic env for uv/pre-commit subprocesses.

    Production-grade: pop VIRTUAL_ENV leaks so uv doesn't reuse a parent
    venv, and explicitly pin UV_PROJECT_ENVIRONMENT to workspace/.venv
    when workspace is known (operator chose pop+set explicit pinning).
    """

    environment = os.environ.copy()
    for key in (
        "VIRTUAL_ENV",
        "VIRTUAL_ENV_PROMPT",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
        "PYTHONHOME",
    ):
        environment.pop(key, None)
    environment.update(GIT_TERMINAL_PROMPT="0", UV_LINK_MODE="copy")
    if workspace is not None:
        environment["UV_PROJECT_ENVIRONMENT"] = str((workspace / ".venv").resolve())
    return environment


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    timeout: float,
    failure_reason: ReadyReason,
    timeout_reason: ReadyReason | None = None,
    missing_reason: ReadyReason | None = None,
    fingerprint: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            env=_command_environment(cwd),
        )
    except FileNotFoundError as exc:
        raise _ReadinessError(missing_reason or failure_reason, fingerprint=fingerprint) from exc
    except subprocess.TimeoutExpired as exc:
        raise _ReadinessError(timeout_reason or failure_reason, fingerprint=fingerprint) from exc
    if completed.returncode != 0:
        raise _ReadinessError(failure_reason, completed.returncode, fingerprint)
    return completed


def _uv_executable(workspace: Path) -> tuple[str, str]:
    uv = shutil.which("uv")
    if uv is None:
        raise _ReadinessError("tool_missing")
    completed = _run_process(
        [uv, "--version"],
        cwd=workspace,
        timeout=_COMMAND_TIMEOUT_SECONDS,
        failure_reason="tool_missing",
    )
    version = completed.stdout.strip()
    if not version:
        raise _ReadinessError("tool_missing", completed.returncode)
    return uv, version


def _project_python_path(workspace: Path) -> Path:
    return workspace / ".venv" / _VENV_BIN / _PROJECT_PYTHON


def _precommit_path(workspace: Path) -> Path:
    return workspace / ".venv" / _VENV_BIN / _PRECOMMIT


@overload
def _read_python_minor(workspace: Path, *, strict: Literal[True], fingerprint: str | None = None) -> str: ...


@overload
def _read_python_minor(workspace: Path, *, strict: Literal[False], fingerprint: str | None = None) -> str | None: ...


def _read_python_minor(workspace: Path, *, strict: bool, fingerprint: str | None = None) -> str | None:
    python = _project_python_path(workspace)
    if not python.is_file() or (os.name != "nt" and not os.access(python, os.X_OK)):
        if strict:
            raise _ReadinessError("locked_check_failed", fingerprint=fingerprint)
        return None
    try:
        completed = _run_process(
            [str(python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            cwd=workspace,
            timeout=_COMMAND_TIMEOUT_SECONDS,
            failure_reason="locked_check_failed",
            fingerprint=fingerprint,
        )
    except _ReadinessError:
        if strict:
            raise
        return None
    minor = completed.stdout.strip()
    if minor:
        return minor
    if strict:
        raise _ReadinessError("locked_check_failed", completed.returncode, fingerprint)
    return None


def _fingerprint_input(hasher: _Hash, label: str, payload: bytes) -> None:
    encoded_label = label.encode()
    hasher.update(len(encoded_label).to_bytes(8))
    hasher.update(encoded_label)
    hasher.update(len(payload).to_bytes(8))
    hasher.update(payload)


def _compute_fingerprint(workspace: Path, hook_source_dir: Path, *, python_minor: str, uv_version: str) -> str:
    hasher = hashlib.sha256()
    _fingerprint_input(hasher, "schema", str(_BOOTSTRAP_SCHEMA).encode())
    for relative in (Path("pyproject.toml"), Path("uv.lock"), Path(".pre-commit-config.yaml")):
        _fingerprint_input(hasher, relative.as_posix(), (workspace / relative).read_bytes())
    for name in HOOK_NAMES:
        source = hook_source_dir / name
        _fingerprint_input(hasher, f"hook:{name}:mode", f"{stat.S_IMODE(source.stat().st_mode):o}".encode())
        _fingerprint_input(hasher, f"hook:{name}:bytes", source.read_bytes())
    for name in ("install.py", "status.py"):
        _fingerprint_input(hasher, f"hook-utility:{name}", (hook_source_dir / name).read_bytes())
    _fingerprint_input(hasher, "project-python", python_minor.encode())
    _fingerprint_input(hasher, "uv-version", uv_version.encode())
    return f"sha256:{hasher.hexdigest()}"


def _precommit_home() -> Path:
    configured = os.environ.get("PRE_COMMIT_HOME")
    return Path(configured).expanduser().resolve() if configured else (Path.home() / ".cache" / "pre-commit").resolve()


def _sentinel_path(fingerprint: str) -> Path:
    return _precommit_home() / ".fa-ready" / fingerprint


def _marker_matches(workspace: Path, *, fingerprint: str, python_minor: str, uv_version: str) -> bool:
    marker = workspace / _MARKER_RELATIVE
    try:
        if marker.is_symlink() or stat.S_IMODE(marker.stat().st_mode) != _PRIVATE_FILE_MODE:
            return False
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data == {
        "checked_at": data.get("checked_at"),
        "fingerprint": fingerprint,
        "project_python": python_minor,
        "schema": _BOOTSTRAP_SCHEMA,
        "state": "ready",
        "uv_version": uv_version,
    } and isinstance(data.get("checked_at"), str)


def _hooks_current(workspace: Path, hook_source_dir: Path) -> bool:
    try:
        hooks_dir = resolve_hooks_dir(workspace)
    except SystemExit:
        return False
    for name in HOOK_NAMES:
        source = hook_source_dir / name
        target = hooks_dir / name
        if not target.is_file() or (os.name != "nt" and not os.access(target, os.X_OK)):
            return False
        try:
            if target.read_bytes() != source.read_bytes():
                return False
            if target.is_symlink() and target.resolve() != source.resolve():
                return False
        except OSError:
            return False
    return True


def _uv_check(uv: str, workspace: Path, *, fingerprint: str, strict: bool) -> bool:
    try:
        _run_process(
            [uv, *_UV_CHECK_ARGV[1:]],
            cwd=workspace,
            timeout=_COMMAND_TIMEOUT_SECONDS,
            failure_reason="locked_check_failed",
            fingerprint=fingerprint,
        )
    except _ReadinessError:
        if strict:
            raise
        return False
    return True


def _fast_ready(
    workspace: Path,
    hook_source_dir: Path,
    *,
    uv: str,
    uv_version: str,
    python_minor: str,
    fingerprint: str,
) -> bool:
    sentinel = _sentinel_path(fingerprint)
    try:
        sentinel_matches = (
            sentinel.is_file()
            and not sentinel.is_symlink()
            and stat.S_IMODE(sentinel.stat().st_mode) == _PRIVATE_FILE_MODE
            and sentinel.read_text(encoding="utf-8") == fingerprint + "\n"
        )
    except OSError:
        sentinel_matches = False
    return (
        _marker_matches(workspace, fingerprint=fingerprint, python_minor=python_minor, uv_version=uv_version)
        and _hooks_current(workspace, hook_source_dir)
        and sentinel_matches
        and _uv_check(uv, workspace, fingerprint=fingerprint, strict=False)
    )


def _write_atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(_PRIVATE_DIR_MODE)
    temp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        descriptor = _open_private(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.chmod(_PRIVATE_FILE_MODE)
        os.replace(temp_path, path)
        path.chmod(_PRIVATE_FILE_MODE)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _remove_marker(workspace: Path) -> None:
    try:
        (workspace / _MARKER_RELATIVE).unlink()
    except FileNotFoundError:
        pass


def _hook_seat_is_manageable(source: Path, target: Path) -> bool:
    """Return whether an absent or current FA-owned seat may be replaced."""

    try:
        if not target.exists() and not target.is_symlink():
            return True
        if target.is_symlink():
            # strict=True vs False is dead defensive guard for valid hook seats:
            # source is guaranteed regular file (validated in _validate_workspace),
            # target broken symlink is already not manageable via except or comparison.
            # Mutmut changes strict=True → False survive with same boolean.
            return target.resolve(strict=True) == source.resolve(strict=True)  # pragma: no mutate
        return target.is_file() and target.read_bytes() == source.read_bytes()
    except OSError:
        return False


def _assert_managed_hook_ownership(
    workspace: Path,
    hook_source_dir: Path,
    *,
    fingerprint: str | None = None,
) -> None:
    """Reject custom paths and unowned default seats without mutating either."""

    try:
        effective = resolve_hooks_dir(workspace).resolve()
        default = resolve_default_hooks_dir(workspace).resolve()
    except (OSError, SystemExit) as exc:
        raise _ReadinessError("hook_status_failed", fingerprint=fingerprint) from exc
    if effective != default:
        raise _ReadinessError("custom_hooks_unmanaged", fingerprint=fingerprint)
    if any(not _hook_seat_is_manageable(hook_source_dir / name, default / name) for name in HOOK_NAMES):
        raise _ReadinessError("hook_seat_collision", fingerprint=fingerprint)


def _install_workspace_hooks(
    workspace: Path,
    hook_source_dir: Path,
    *,
    fingerprint: str | None = None,
) -> None:
    _assert_managed_hook_ownership(workspace, hook_source_dir, fingerprint=fingerprint)
    try:
        install_hooks(workspace, force=True, hook_source_dir=hook_source_dir)
    except Exception as exc:
        raise _ReadinessError("hook_status_failed", fingerprint=fingerprint) from exc


def _fingerprint(
    workspace: Path,
    hook_source_dir: Path,
    *,
    python_minor: str,
    uv_version: str,
) -> str:
    try:
        return _compute_fingerprint(
            workspace,
            hook_source_dir,
            python_minor=python_minor,
            uv_version=uv_version,
        )
    except Exception as exc:
        raise _ReadinessError("fingerprint_failed") from exc


def _ensure_locked(workspace: Path, hook_source_dir: Path, *, started: float) -> ReadyState:
    uv, uv_version = _uv_executable(workspace)
    existing_minor = _read_python_minor(workspace, strict=False)
    fingerprint = _fingerprint(
        workspace,
        hook_source_dir,
        python_minor=existing_minor or _RUNTIME_PYTHON_MINOR,
        uv_version=uv_version,
    )
    _assert_managed_hook_ownership(workspace, hook_source_dir, fingerprint=fingerprint)
    if existing_minor and _fast_ready(
        workspace,
        hook_source_dir,
        uv=uv,
        uv_version=uv_version,
        python_minor=existing_minor,
        fingerprint=fingerprint,
    ):
        return _state("ready_fast_path", workspace, started, fingerprint=fingerprint)

    try:
        _remove_marker(workspace)
        _install_workspace_hooks(workspace, hook_source_dir, fingerprint=fingerprint)
    except _ReadinessError:
        raise
    except OSError as exc:
        raise _ReadinessError("state_io_failed", fingerprint=fingerprint) from exc

    _run_process(
        [uv, *_UV_SYNC_ARGV[1:]],
        cwd=workspace,
        timeout=_SYNC_TIMEOUT_SECONDS,
        failure_reason="sync_failed",
        timeout_reason="sync_timeout",
        fingerprint=fingerprint,
    )
    _run_process(
        [str(_precommit_path(workspace)), "install-hooks"],
        cwd=workspace,
        timeout=_PRECOMMIT_TIMEOUT_SECONDS,
        failure_reason="precommit_prewarm_failed",
        timeout_reason="precommit_prewarm_timeout",
        fingerprint=fingerprint,
    )
    _install_workspace_hooks(workspace, hook_source_dir, fingerprint=fingerprint)
    actual_minor = _read_python_minor(workspace, strict=True, fingerprint=fingerprint)
    fingerprint = _fingerprint(
        workspace,
        hook_source_dir,
        python_minor=actual_minor,
        uv_version=uv_version,
    )
    _uv_check(uv, workspace, fingerprint=fingerprint, strict=True)
    if not _hooks_current(workspace, hook_source_dir):
        raise _ReadinessError("hook_status_failed", fingerprint=fingerprint)

    marker_payload = {
        "checked_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "fingerprint": fingerprint,
        "project_python": actual_minor,
        "schema": _BOOTSTRAP_SCHEMA,
        "state": "ready",
        "uv_version": uv_version,
    }
    try:
        _write_atomic_text(_sentinel_path(fingerprint), fingerprint + "\n")
        _write_atomic_text(
            workspace / _MARKER_RELATIVE,
            json.dumps(marker_payload) + "\n",
        )
    except OSError as exc:
        raise _ReadinessError("state_io_failed", fingerprint=fingerprint) from exc
    return _state("ready_repaired", workspace, started, fingerprint=fingerprint)


def _append_log(state: ReadyState, *, workspace: Path, return_code: int | None) -> None:
    stage, argv = _TELEMETRY[state.reason_code]
    record = {
        "argv": list(argv),
        "elapsed_ms": state.elapsed_ms,
        "reason_code": state.reason_code,
        "return_code": return_code,
        "stage": stage,
        "status": state.status.value,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "workspace": str(workspace),
    }
    descriptor = _open_private(state.log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _record_locked(
    state: ReadyState,
    *,
    workspace: Path,
    return_code: int | None,
    started: float,
) -> ReadyState:
    if state.status is not ReadyStatus.READY:
        try:
            _remove_marker(workspace)
        except OSError:
            state = _state("state_io_failed", workspace, started, fingerprint=state.fingerprint)
    try:
        _append_log(state, workspace=workspace, return_code=return_code)
    except OSError:
        try:
            _remove_marker(workspace)
        except OSError:
            pass
        return _state("state_io_failed", workspace, started)
    return state


def _private_state_current_for_check(workspace: Path) -> bool:
    state_dir = workspace / ".fa"
    if state_dir.is_symlink():
        raise OSError
    if not state_dir.is_dir() or stat.S_IMODE(state_dir.stat().st_mode) != _PRIVATE_DIR_MODE:
        return False
    for relative in (_LOG_RELATIVE, _LOCK_RELATIVE):
        path = workspace / relative
        if path.is_symlink():
            raise OSError
        if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != _PRIVATE_FILE_MODE:
            return False
    return True


def check_workspace_ready(workspace: Path) -> ReadyState:
    """Return current readiness without acquiring locks, repairing, logging, or writing state."""

    started = time.monotonic()
    unresolved = Path(workspace).expanduser()
    try:
        resolved, hook_source_dir = _validate_workspace(unresolved)
    except (OSError, RuntimeError, ValueError):
        return _state("invalid_workspace", unresolved.absolute(), started)
    try:
        _assert_managed_hook_ownership(resolved, hook_source_dir)
        if not _private_state_current_for_check(resolved):
            return _state("locked_check_failed", resolved, started)
        uv, uv_version = _uv_executable(resolved)
        python_minor = _read_python_minor(resolved, strict=True)
        fingerprint = _fingerprint(
            resolved,
            hook_source_dir,
            python_minor=python_minor,
            uv_version=uv_version,
        )
        if _fast_ready(
            resolved,
            hook_source_dir,
            uv=uv,
            uv_version=uv_version,
            python_minor=python_minor,
            fingerprint=fingerprint,
        ):
            return _state("ready_fast_path", resolved, started, fingerprint=fingerprint)
        return _state("locked_check_failed", resolved, started, fingerprint=fingerprint)
    except _ReadinessError as exc:
        return _state(exc.reason_code, resolved, started)
    except OSError:
        return _state("state_io_failed", resolved, started)
    except Exception:  # noqa: BLE001 - read-only status must retain CT3's total-result boundary.
        return _state("unexpected_internal_error", resolved, started)


def ensure_workspace_ready(workspace: Path) -> ReadyState:
    """Return READY or one typed degraded state for a managed workspace."""

    started = time.monotonic()
    unresolved = Path(workspace).expanduser()
    try:
        resolved, hook_source_dir = _validate_workspace(unresolved)
    except (OSError, RuntimeError, ValueError):
        return _state("invalid_workspace", unresolved.absolute(), started)
    try:
        _ensure_private_state_paths(resolved)
    except OSError:
        return _state("state_io_failed", resolved, started)

    try:
        with _exclusive_lock(resolved / _LOCK_RELATIVE):
            return_code: int | None = 0
            try:
                state = _ensure_locked(resolved, hook_source_dir, started=started)
            except _ReadinessError as exc:
                state = _state(exc.reason_code, resolved, started, fingerprint=exc.fingerprint)
                return_code = exc.return_code
            except Exception:  # noqa: BLE001 - CT3 maps every ordinary internal failure to typed degradation.
                state = _state("unexpected_internal_error", resolved, started)
                return_code = None
            return _record_locked(
                state,
                workspace=resolved,
                return_code=return_code,
                started=started,
            )
    except _LockTimeoutError:
        return _state("lock_timeout", resolved, started)
    except OSError:
        return _state("state_io_failed", resolved, started)
    except Exception:  # noqa: BLE001 - lock/platform failures must not escape lifecycle admission.
        return _state("unexpected_internal_error", resolved, started)


def _exit_code(state: ReadyState) -> int:
    if state.status is ReadyStatus.READY:
        return 0
    if state.status is ReadyStatus.DEGRADED_ENVIRONMENT:
        return 75
    return 70


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m fa.workspace_bootstrap")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("ensure", "check"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--workspace", required=True)
    args = parser.parse_args(argv)

    operation = ensure_workspace_ready if args.command == "ensure" else check_workspace_ready
    state = operation(Path(args.workspace))
    payload = {
        "elapsed_ms": state.elapsed_ms,
        "fingerprint": state.fingerprint,
        "log_path": str(state.log_path),
        "reason_code": state.reason_code,
        "repaired": state.repaired,
        "status": state.status.value,
    }
    print(json.dumps(payload))
    if state.status is not ReadyStatus.READY:
        print(
            f"[WORKSPACE_BOOTSTRAP] {state.status.value}: {state.reason_code}; log={state.log_path}",
            file=sys.stderr,
        )
    return _exit_code(state)


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = ["ReadyReason", "ReadyState", "ReadyStatus", "check_workspace_ready", "ensure_workspace_ready"]
