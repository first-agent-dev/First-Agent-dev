"""C0/C1/C3 contracts for deterministic managed-workspace readiness.

Pyramid A only: real temporary Git workspaces and filesystem state, with uv and
pre-commit process boundaries replaced by deterministic local executables.

Path inventory:
  A: cold repair -> READY marker, cache sentinel, environment, and four seats
  B: active fast path -> no sync/prewarm mutation
  C: cache loss -> repair even when the workspace marker survives
  D: every closed degraded reason -> exact status/exit/no marker
  E: concurrent callers -> one repair and one fast-path consumer
  F: CLI JSON/stderr exit-code contract and secret-free NDJSON
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import pytest

import fa.workspace_bootstrap as bootstrap
from fa.hygiene.hooks._util import HOOK_NAMES
from fa.session.manager import SessionManager
from fa.workspace_bootstrap import ReadyState, ReadyStatus, ensure_workspace_ready
from tests._capabilities import requires_posix_modes, requires_symlinks


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main", str(workspace)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    (workspace / "knowledge").mkdir()
    (workspace / "knowledge" / "llms.txt").write_text("workspace marker\n", encoding="utf-8")
    (workspace / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nrequires-python = ">=3.13"\n',
        encoding="utf-8",
    )
    (workspace / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (workspace / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    source_dir = workspace / "src" / "fa" / "hygiene" / "hooks"
    source_dir.mkdir(parents=True)
    for name in HOOK_NAMES:
        _write_executable(source_dir / name, f"#!/bin/sh\necho workspace-{name}\n")
    (source_dir / "install.py").write_text("# fingerprint installer\n", encoding="utf-8")
    (source_dir / "status.py").write_text("# fingerprint status\n", encoding="utf-8")
    return workspace


def _install_fake_uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "tool-calls.jsonl"
    fake_uv = bin_dir / "uv"
    _write_executable(
        fake_uv,
        f"""#!{sys.executable}
import json
import os
from pathlib import Path
import sys
import time

calls = Path(os.environ["FA_TEST_TOOL_CALLS"])
with calls.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(["uv", *sys.argv[1:]]) + "\\n")
args = sys.argv[1:]
if args == ["--version"]:
    print("uv 0.test")
    raise SystemExit(0)
if "--check" in args:
    raise SystemExit(int(os.environ.get("FA_TEST_UV_CHECK_RC", "0")))
time.sleep(float(os.environ.get("FA_TEST_UV_SYNC_SLEEP", "0")))
rc = int(os.environ.get("FA_TEST_UV_SYNC_RC", "0"))
if rc:
    print("sync failed token=must-not-leak", file=sys.stderr)
    raise SystemExit(rc)
bin_dir = Path.cwd() / ".venv" / "bin"
bin_dir.mkdir(parents=True, exist_ok=True)
python_target = bin_dir / "python"
if python_target.exists() or python_target.is_symlink():
    python_target.unlink()
python_target.symlink_to(Path(os.environ["FA_TEST_PYTHON"]))
precommit = bin_dir / "pre-commit"
precommit.write_text(
    "#!" + os.environ["FA_TEST_PYTHON"] + "\\n"
    "import json, os, pathlib, sys, time\\n"
    "calls = pathlib.Path(os.environ['FA_TEST_TOOL_CALLS'])\\n"
    "with calls.open('a', encoding='utf-8') as handle:\\n"
    "    handle.write(json.dumps(['pre-commit', *sys.argv[1:]]) + '\\\\n')\\n"
    "time.sleep(float(os.environ.get('FA_TEST_PRECOMMIT_SLEEP', '0')))\\n"
    "raise SystemExit(int(os.environ.get('FA_TEST_PRECOMMIT_RC', '0')))\\n",
    encoding="utf-8",
)
precommit.chmod(0o755)
""",
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FA_TEST_TOOL_CALLS", str(calls))
    monkeypatch.setenv("FA_TEST_PYTHON", sys.executable)
    monkeypatch.setenv("PRE_COMMIT_HOME", str(tmp_path / "pre-commit-cache"))
    return calls


def _calls(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _marker(workspace: Path) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((workspace / ".fa" / "ready-state.json").read_text(encoding="utf-8")),
    )


def _sentinel(tmp_path: Path, fingerprint: str) -> Path:
    return tmp_path / "pre-commit-cache" / ".fa-ready" / fingerprint


def test_elapsed_ms_uses_monotonic_milliseconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """C0: elapsed units are integer milliseconds, not seconds or wall clock."""

    monkeypatch.setattr("fa.workspace_bootstrap.time.monotonic", lambda: 11.0)

    assert bootstrap._elapsed_ms(10.0) == 1000


def test_process_runner_uses_bounded_captured_noninteractive_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0/C3: every network-capable command uses the closed subprocess policy."""

    seen: dict[str, Any] = {}

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr("fa.workspace_bootstrap.subprocess.run", run)

    result = bootstrap._run_process(
        ["tool", "arg"],
        cwd=tmp_path,
        timeout=17,
        failure_reason="sync_failed",
    )

    assert result.stdout == "ok\n"
    assert seen["command"] == ["tool", "arg"]
    assert seen["cwd"] == tmp_path
    assert seen["timeout"] == 17
    assert seen["check"] is False
    assert seen["capture_output"] is True
    assert seen["text"] is True
    assert seen["stdin"] is subprocess.DEVNULL
    environment = seen["env"]
    assert isinstance(environment, dict)
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["UV_LINK_MODE"] == "copy"


@pytest.mark.parametrize(
    ("outcome", "expected_reason", "expected_rc"),
    [
        ("missing", "tool_missing", None),
        ("timeout", "sync_timeout", None),
        ("failed", "sync_failed", 7),
    ],
)
def test_process_runner_preserves_failure_reason_code_and_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    expected_reason: str,
    expected_rc: int | None,
) -> None:
    """C0/C3: process faults retain the closed reason and diagnostic metadata."""

    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if outcome == "missing":
            raise FileNotFoundError
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, timeout=3)
        return subprocess.CompletedProcess(command, 7, "", "failed")

    monkeypatch.setattr("fa.workspace_bootstrap.subprocess.run", run)

    with pytest.raises(bootstrap._ReadinessError) as caught:
        bootstrap._run_process(
            ["tool"],
            cwd=tmp_path,
            timeout=3,
            failure_reason="sync_failed",
            timeout_reason="sync_timeout",
            missing_reason="tool_missing",
            fingerprint="sha256:fault",
        )

    assert caught.value.reason_code == expected_reason
    assert caught.value.return_code == expected_rc
    assert caught.value.fingerprint == "sha256:fault"


@pytest.mark.parametrize("version", ["uv direct", ""])
def test_uv_version_probe_uses_workspace_timeout_and_rejects_empty_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    """C0: uv discovery/version is bounded and empty output is tool_missing."""

    seen: dict[str, Any] = {}
    monkeypatch.setattr("fa.workspace_bootstrap.shutil.which", lambda name: "/tools/uv")

    def run_process(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, version + "\n" if version else "", "")

    monkeypatch.setattr(bootstrap, "_run_process", run_process)

    if version:
        assert bootstrap._uv_executable(tmp_path) == ("/tools/uv", version)
    else:
        with pytest.raises(bootstrap._ReadinessError) as caught:
            bootstrap._uv_executable(tmp_path)
        assert caught.value.reason_code == "tool_missing"
        assert caught.value.return_code == 0
    assert seen["command"] == ["/tools/uv", "--version"]
    assert seen["cwd"] == tmp_path
    assert seen["timeout"] == 120.0
    assert seen["failure_reason"] == "tool_missing"


def test_python_minor_probe_strictness_and_process_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0/C3: interpreter validation repairs softly, then verifies strictly."""

    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("not executable\n", encoding="utf-8")
    python.chmod(0o644)
    assert bootstrap._read_python_minor(tmp_path, strict=False) is None
    with pytest.raises(bootstrap._ReadinessError) as missing:
        bootstrap._read_python_minor(tmp_path, strict=True, fingerprint="sha256:missing")
    assert missing.value.reason_code == "locked_check_failed"
    assert missing.value.fingerprint == "sha256:missing"

    python.chmod(0o755)
    seen: dict[str, Any] = {}

    def run_process(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, **kwargs)
        return subprocess.CompletedProcess(command, 0, "3.15\n", "")

    monkeypatch.setattr(bootstrap, "_run_process", run_process)
    assert bootstrap._read_python_minor(tmp_path, strict=True, fingerprint="sha256:python") == "3.15"
    assert seen["command"][0] == str(python)
    assert seen["cwd"] == tmp_path
    assert seen["timeout"] == 120.0
    assert seen["failure_reason"] == "locked_check_failed"
    assert seen["fingerprint"] == "sha256:python"

    monkeypatch.setattr(
        bootstrap,
        "_run_process",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    with pytest.raises(bootstrap._ReadinessError) as empty:
        bootstrap._read_python_minor(tmp_path, strict=True, fingerprint="sha256:empty")
    assert empty.value.reason_code == "locked_check_failed"
    assert empty.value.return_code == 0
    assert empty.value.fingerprint == "sha256:empty"


_FINGERPRINT_INPUTS = [
    "pyproject",
    "lock",
    "precommit_config",
    "hook_bytes",
    "hook_mode",
    "installer",
    "status",
    "python_minor",
    "uv_version",
]


@pytest.mark.parametrize("changed_input", _FINGERPRINT_INPUTS)
def test_fingerprint_changes_for_every_declared_input(tmp_path: Path, changed_input: str) -> None:
    """C0p: CT4 fingerprint consumes every declared source/environment authority."""

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    baseline = bootstrap._compute_fingerprint(
        workspace,
        hook_source,
        python_minor="3.13",
        uv_version="uv baseline",
    )
    assert baseline == "sha256:7c1abc0e93d69eb863b217196edac05bbc6de6af62c0c25f4fc4d3a8b755dabd"
    python_minor = "3.13"
    uv_version = "uv baseline"
    if changed_input == "pyproject":
        (workspace / "pyproject.toml").write_text("changed\n", encoding="utf-8")
    elif changed_input == "lock":
        (workspace / "uv.lock").write_text("changed\n", encoding="utf-8")
    elif changed_input == "precommit_config":
        (workspace / ".pre-commit-config.yaml").write_text("changed\n", encoding="utf-8")
    elif changed_input == "hook_bytes":
        (hook_source / HOOK_NAMES[0]).write_text("changed\n", encoding="utf-8")
    elif changed_input == "hook_mode":
        (hook_source / HOOK_NAMES[0]).chmod(0o644)
    elif changed_input == "installer":
        (hook_source / "install.py").write_text("changed\n", encoding="utf-8")
    elif changed_input == "status":
        (hook_source / "status.py").write_text("changed\n", encoding="utf-8")
    elif changed_input == "python_minor":
        python_minor = "3.14"
    elif changed_input == "uv_version":
        uv_version = "uv changed"

    changed = bootstrap._compute_fingerprint(
        workspace,
        hook_source,
        python_minor=python_minor,
        uv_version=uv_version,
    )

    assert changed != baseline
    assert changed.startswith("sha256:")


@pytest.mark.parametrize(
    ("configured", "expected_relative"),
    [(None, ".cache/pre-commit"), ("", ".cache/pre-commit"), ("~/custom-precommit", "custom-precommit")],
)
def test_precommit_home_honors_unset_empty_and_explicit_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured: str | None,
    expected_relative: str,
) -> None:
    """C0: CT4 cache root follows exact PRE_COMMIT_HOME empty semantics."""

    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    if configured is None:
        monkeypatch.delenv("PRE_COMMIT_HOME", raising=False)
    else:
        monkeypatch.setenv("PRE_COMMIT_HOME", configured)

    assert bootstrap._precommit_home() == (home / expected_relative).resolve()


def test_cold_repair_then_active_fast_path_has_exact_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1 A/B: marker is a hint; active environment/hooks/sentinel remain authority."""

    workspace = _make_workspace(tmp_path)
    calls_path = _install_fake_uv(tmp_path, monkeypatch)

    repaired = ensure_workspace_ready(workspace)

    assert repaired.status is ReadyStatus.READY
    assert repaired.reason_code == "ready_repaired"
    assert repaired.repaired is True
    assert repaired.fingerprint is not None
    assert repaired.log_path == (workspace / ".fa" / "bootstrap.log").resolve()
    assert repaired.elapsed_ms >= 0
    marker = _marker(workspace)
    assert marker["checked_at"].endswith("Z")
    datetime.fromisoformat(marker["checked_at"].replace("Z", "+00:00"))
    assert marker == {
        "checked_at": marker["checked_at"],
        "fingerprint": repaired.fingerprint,
        "project_python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "schema": 2,
        "state": "ready",
        "uv_version": "uv 0.test",
    }
    sentinel = _sentinel(tmp_path, repaired.fingerprint)
    assert sentinel.read_text(encoding="utf-8") == repaired.fingerprint + "\n"
    assert stat.S_IMODE(sentinel.stat().st_mode) == 0o600
    assert stat.S_IMODE((workspace / ".fa").stat().st_mode) == 0o700
    assert stat.S_IMODE((workspace / ".fa" / "ready-state.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((workspace / ".fa" / "bootstrap.lock").stat().st_mode) == 0o600
    assert stat.S_IMODE(repaired.log_path.stat().st_mode) == 0o600
    source_dir = workspace / "src" / "fa" / "hygiene" / "hooks"
    for name in HOOK_NAMES:
        seat = workspace / ".git" / "hooks" / name
        assert seat.read_text(encoding="utf-8") == (source_dir / name).read_text(encoding="utf-8")
        assert os.access(seat, os.X_OK)

    marker_before = (workspace / ".fa" / "ready-state.json").read_bytes()
    calls_before = _calls(calls_path)
    fast = ensure_workspace_ready(workspace)
    new_calls = _calls(calls_path)[len(calls_before) :]

    assert fast.status is ReadyStatus.READY
    assert fast.reason_code == "ready_fast_path"
    assert fast.repaired is False
    assert fast.fingerprint == repaired.fingerprint
    assert (workspace / ".fa" / "ready-state.json").read_bytes() == marker_before
    assert [call[0] for call in new_calls] == ["uv", "uv"]
    assert new_calls[0] == ["uv", "--version"]
    assert new_calls[1] == ["uv", "sync", "--locked", "--extra", "dev", "--check"]
    rows = [json.loads(line) for line in fast.log_path.read_text(encoding="utf-8").splitlines()]
    assert [row["reason_code"] for row in rows] == ["ready_repaired", "ready_fast_path"]
    assert [row["return_code"] for row in rows] == [0, 0]
    assert set(rows[-1]) == {
        "argv",
        "elapsed_ms",
        "reason_code",
        "return_code",
        "stage",
        "status",
        "timestamp",
        "workspace",
    }
    assert rows[-1]["timestamp"].endswith("Z")
    datetime.fromisoformat(rows[-1]["timestamp"].replace("Z", "+00:00"))


@pytest.mark.parametrize(
    ("ownership_case", "expected_reason"),
    [
        ("custom-path", "custom_hooks_unmanaged"),
        ("default-collision", "hook_seat_collision"),
    ],
)
def test_hook_ownership_conflict_preserves_operator_state_and_invalidates_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ownership_case: str,
    expected_reason: str,
) -> None:
    """C1/C3 M17: automatic readiness preserves custom/unowned executable code."""

    workspace = _make_workspace(tmp_path)
    calls_path = _install_fake_uv(tmp_path, monkeypatch)
    assert ensure_workspace_ready(workspace).reason_code == "ready_repaired"
    marker = workspace / ".fa" / "ready-state.json"
    assert marker.is_file()

    if ownership_case == "custom-path":
        operator_hooks = tmp_path / "operator-hooks"
        operator_hooks.mkdir()
        operator_hook = operator_hooks / HOOK_NAMES[0]
        subprocess.run(
            ["git", "config", "core.hooksPath", str(operator_hooks)],
            cwd=workspace,
            check=True,
        )
    else:
        operator_hook = workspace / ".git" / "hooks" / HOOK_NAMES[0]
        operator_hook.unlink()
    operator_hook.write_bytes(b"#!/bin/sh\nprintf 'operator-owned\\n'\n")
    operator_hook.chmod(0o751)

    config = workspace / ".git" / "config"
    config_before = config.read_bytes()
    hook_before = (operator_hook.read_bytes(), stat.S_IMODE(operator_hook.lstat().st_mode))
    calls_before = len(_calls(calls_path))

    state = ensure_workspace_ready(workspace)
    checked = bootstrap.check_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert state.reason_code == expected_reason
    assert state.fingerprint is not None
    assert checked.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert checked.reason_code == expected_reason
    assert not marker.exists()
    assert (operator_hook.read_bytes(), stat.S_IMODE(operator_hook.lstat().st_mode)) == hook_before
    assert config.read_bytes() == config_before
    new_calls = _calls(calls_path)[calls_before:]
    assert new_calls == [["uv", "--version"]]
    row = json.loads(state.log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert row["reason_code"] == expected_reason
    assert row["stage"] == "hook_ownership"
    assert row["argv"] == []


def test_custom_path_with_current_fa_copies_cannot_reuse_fast_ready_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1/C3 M17: custom-path ownership check precedes content-based fast validation."""

    workspace = _make_workspace(tmp_path)
    calls_path = _install_fake_uv(tmp_path, monkeypatch)
    assert ensure_workspace_ready(workspace).reason_code == "ready_repaired"
    custom_hooks = tmp_path / "custom-current-hooks"
    custom_hooks.mkdir()
    source_dir = workspace / "src" / "fa" / "hygiene" / "hooks"
    for name in HOOK_NAMES:
        shutil.copy2(source_dir / name, custom_hooks / name)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(custom_hooks)],
        cwd=workspace,
        check=True,
    )
    hooks_before = {name: (custom_hooks / name).read_bytes() for name in HOOK_NAMES}
    calls_before = len(_calls(calls_path))

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert state.reason_code == "custom_hooks_unmanaged"
    assert not (workspace / ".fa" / "ready-state.json").exists()
    assert {name: (custom_hooks / name).read_bytes() for name in HOOK_NAMES} == hooks_before
    assert _calls(calls_path)[calls_before:] == [["uv", "--version"]]


def test_git_session_manager_repairs_on_create_and_fast_validates_on_attach(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 P3/P4: real manager producer consumes the real readiness transaction."""

    source = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    subprocess.run(
        ["git", "-C", str(source), "add", "."],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    commit_environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Source",
        "GIT_AUTHOR_EMAIL": "source@example.invalid",
        "GIT_COMMITTER_NAME": "Source",
        "GIT_COMMITTER_EMAIL": "source@example.invalid",
    }
    subprocess.run(
        ["git", "-C", str(source), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        env=commit_environment,
    )
    push_url = "git@github.com:first-agent-dev/First-Agent-dev.git"
    subprocess.run(
        ["git", "-C", str(source), "remote", "add", "origin", push_url],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    states: list[ReadyState] = []

    def prepare(workspace: Path) -> ReadyState:
        state = ensure_workspace_ready(workspace)
        states.append(state)
        return state

    manager = SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "managed-workspaces",
        source_workspace=source,
        workspace_preparer=prepare,
    )

    created = manager.create_or_attach_session(session_id=None, workspace_override=None)
    attached = manager.create_or_attach_session(
        session_id=created.session_id,
        workspace_override=created.workspace_path,
    )

    assert attached.workspace_path == created.workspace_path
    assert [state.reason_code for state in states] == ["ready_repaired", "ready_fast_path"]
    assert all(state.status is ReadyStatus.READY for state in states)
    assert _marker(created.workspace_path)["state"] == "ready"
    assert json.loads(created.manifest_path.read_text(encoding="utf-8"))["status"] == "active"


def test_missing_cache_sentinel_forces_prewarm_and_marker_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 C: persisted workspace marker cannot outlive tmpfs cache authority."""

    workspace = _make_workspace(tmp_path)
    calls_path = _install_fake_uv(tmp_path, monkeypatch)
    first = ensure_workspace_ready(workspace)
    assert first.fingerprint is not None
    _sentinel(tmp_path, first.fingerprint).unlink()
    calls_before = _calls(calls_path)

    resumed = ensure_workspace_ready(workspace)
    new_calls = _calls(calls_path)[len(calls_before) :]

    assert resumed.reason_code == "ready_repaired"
    assert resumed.repaired is True
    assert _sentinel(tmp_path, resumed.fingerprint or "missing").is_file()
    assert ["pre-commit", "install-hooks"] in new_calls
    assert ["uv", "sync", "--locked", "--extra", "dev"] in new_calls


_EXPECTED_TELEMETRY: dict[str, tuple[str, list[str]]] = {
    "ready_repaired": ("ready", []),
    "ready_fast_path": ("fast_validate", []),
    "tool_missing": ("uv_version", ["uv", "--version"]),
    "sync_failed": ("uv_sync", ["uv", "sync", "--locked", "--extra", "dev"]),
    "sync_timeout": ("uv_sync", ["uv", "sync", "--locked", "--extra", "dev"]),
    "precommit_prewarm_failed": ("precommit_prewarm", [".venv/bin/pre-commit", "install-hooks"]),
    "precommit_prewarm_timeout": ("precommit_prewarm", [".venv/bin/pre-commit", "install-hooks"]),
    "locked_check_failed": ("uv_locked_check", ["uv", "sync", "--locked", "--extra", "dev", "--check"]),
    "hook_status_failed": ("hook_status", ["check_hooks"]),
    "custom_hooks_unmanaged": ("hook_ownership", []),
    "hook_seat_collision": ("hook_ownership", []),
    "fingerprint_failed": ("fingerprint", []),
    "state_io_failed": ("state_io", []),
    "unexpected_internal_error": ("unexpected", []),
}

_EXPECTED_RETURN_CODES: dict[str, int | None] = {
    "ready_repaired": 0,
    "ready_fast_path": 0,
    "tool_missing": None,
    "sync_failed": 7,
    "sync_timeout": None,
    "precommit_prewarm_failed": 9,
    "precommit_prewarm_timeout": None,
    "locked_check_failed": 4,
    "hook_status_failed": None,
    "custom_hooks_unmanaged": None,
    "hook_seat_collision": None,
    "fingerprint_failed": None,
    "state_io_failed": None,
    "unexpected_internal_error": None,
}

_FINGERPRINTED_FAILURES = {
    "sync_failed",
    "sync_timeout",
    "precommit_prewarm_failed",
    "precommit_prewarm_timeout",
    "locked_check_failed",
    "hook_status_failed",
    "custom_hooks_unmanaged",
    "hook_seat_collision",
    "state_io_failed",
}

_REASON_CASES = [
    ("ready_repaired", ReadyStatus.READY),
    ("ready_fast_path", ReadyStatus.READY),
    ("invalid_workspace", ReadyStatus.DEGRADED_INTERNAL),
    ("lock_timeout", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("tool_missing", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("sync_failed", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("sync_timeout", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("precommit_prewarm_failed", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("precommit_prewarm_timeout", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("locked_check_failed", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("hook_status_failed", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("custom_hooks_unmanaged", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("hook_seat_collision", ReadyStatus.DEGRADED_ENVIRONMENT),
    ("fingerprint_failed", ReadyStatus.DEGRADED_INTERNAL),
    ("state_io_failed", ReadyStatus.DEGRADED_INTERNAL),
    ("unexpected_internal_error", ReadyStatus.DEGRADED_INTERNAL),
]


@pytest.mark.parametrize(("reason", "expected_status"), _REASON_CASES)
def test_every_reason_code_has_exact_status_repair_and_marker_contract(  # noqa: C901 - explicit closed-reason matrix.
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reason: str,
    expected_status: ReadyStatus,
) -> None:
    """C0/C3 D: closed reason map is failure-observable and marker-safe."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)

    if reason == "ready_fast_path":
        assert ensure_workspace_ready(workspace).reason_code == "ready_repaired"
    elif reason == "invalid_workspace":
        (workspace / "uv.lock").unlink()
    elif reason == "lock_timeout":

        @contextmanager
        def timed_out_lock(_path: Path) -> Iterator[None]:
            raise bootstrap._LockTimeoutError
            yield

        monkeypatch.setattr(bootstrap, "_exclusive_lock", timed_out_lock)
    elif reason == "tool_missing":
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()
        monkeypatch.setenv("PATH", str(empty_path))
    elif reason == "sync_failed":
        monkeypatch.setenv("FA_TEST_UV_SYNC_RC", "7")
    elif reason == "sync_timeout":
        monkeypatch.setenv("FA_TEST_UV_SYNC_SLEEP", "0.2")
        monkeypatch.setattr(bootstrap, "_SYNC_TIMEOUT_SECONDS", 0.01)
    elif reason == "precommit_prewarm_failed":
        monkeypatch.setenv("FA_TEST_PRECOMMIT_RC", "9")
    elif reason == "precommit_prewarm_timeout":
        monkeypatch.setenv("FA_TEST_PRECOMMIT_SLEEP", "0.2")
        monkeypatch.setattr(bootstrap, "_PRECOMMIT_TIMEOUT_SECONDS", 0.01)
    elif reason == "locked_check_failed":
        monkeypatch.setenv("FA_TEST_UV_CHECK_RC", "4")
    elif reason == "hook_status_failed":
        monkeypatch.setattr(bootstrap, "_hooks_current", lambda *_args: False)
    elif reason == "custom_hooks_unmanaged":
        custom_hooks = tmp_path / "operator-hooks"
        custom_hooks.mkdir()
        subprocess.run(
            ["git", "config", "core.hooksPath", str(custom_hooks)],
            cwd=workspace,
            check=True,
        )
    elif reason == "hook_seat_collision":
        operator_hook = workspace / ".git" / "hooks" / HOOK_NAMES[0]
        operator_hook.write_text("#!/bin/sh\necho operator-owned\n", encoding="utf-8")
        operator_hook.chmod(0o751)
    elif reason == "fingerprint_failed":
        monkeypatch.setattr(
            bootstrap,
            "_compute_fingerprint",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fingerprint failure")),
        )
    elif reason == "state_io_failed":
        monkeypatch.setattr(
            bootstrap,
            "_write_atomic_text",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("state write failure")),
        )
    elif reason == "unexpected_internal_error":
        monkeypatch.setattr(
            bootstrap,
            "_ensure_locked",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unexpected")),
        )

    state = ensure_workspace_ready(workspace)

    assert state.status is expected_status
    assert state.reason_code == reason
    assert state.repaired is (reason == "ready_repaired")
    marker = workspace / ".fa" / "ready-state.json"
    assert marker.is_file() is (expected_status is ReadyStatus.READY)
    if reason in _FINGERPRINTED_FAILURES:
        assert state.fingerprint is not None
        assert state.fingerprint.startswith("sha256:")
    elif expected_status is not ReadyStatus.READY:
        assert state.fingerprint is None
    if reason in _EXPECTED_TELEMETRY:
        rows = [json.loads(line) for line in state.log_path.read_text(encoding="utf-8").splitlines()]
        stage, argv = _EXPECTED_TELEMETRY[reason]
        assert rows[-1]["reason_code"] == reason
        assert rows[-1]["status"] == expected_status.value
        assert rows[-1]["stage"] == stage
        assert rows[-1]["argv"] == argv
        assert rows[-1]["return_code"] == _EXPECTED_RETURN_CODES[reason]


def test_lock_platform_failure_is_typed_unexpected_internal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3: ordinary lock/platform exceptions never escape lifecycle admission."""

    workspace = _make_workspace(tmp_path)

    @contextmanager
    def broken_lock(_path: Path) -> Iterator[None]:
        raise RuntimeError("platform lock unavailable")
        yield

    monkeypatch.setattr(bootstrap, "_exclusive_lock", broken_lock)

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_INTERNAL
    assert state.reason_code == "unexpected_internal_error"
    assert state.log_path == (workspace / ".fa" / "bootstrap.log").resolve()


def test_marker_removal_io_failure_is_state_io_with_fingerprint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3: stale-marker removal failure is observable before repair mutation."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    monkeypatch.setattr(
        bootstrap,
        "_remove_marker",
        lambda _workspace: (_ for _ in ()).throw(OSError("cannot remove marker")),
    )

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_INTERNAL
    assert state.reason_code == "state_io_failed"
    assert state.fingerprint is not None
    assert state.fingerprint.startswith("sha256:")
    row = json.loads(state.log_path.read_text(encoding="utf-8").splitlines()[-1])
    assert row["reason_code"] == "state_io_failed"


def test_locked_check_failure_does_not_rewrite_uv_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C3 P10: locked verification degrades without changing source authority."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    lock_before = (workspace / "uv.lock").read_bytes()
    monkeypatch.setenv("FA_TEST_UV_CHECK_RC", "6")

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert state.reason_code == "locked_check_failed"
    assert (workspace / "uv.lock").read_bytes() == lock_before
    assert not (workspace / ".fa" / "ready-state.json").exists()


def test_uv_check_forwards_exact_command_and_strict_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0: locked check command is exact and strictness controls repair versus degradation."""

    seen: list[tuple[list[str], dict[str, Any]]] = []

    def success(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(bootstrap, "_run_process", success)
    assert bootstrap._uv_check("/tools/uv", tmp_path, fingerprint="sha256:check", strict=True) is True
    command, kwargs = seen[0]
    assert command == ["/tools/uv", "sync", "--locked", "--extra", "dev", "--check"]
    assert kwargs == {
        "cwd": tmp_path,
        "timeout": 120.0,
        "failure_reason": "locked_check_failed",
        "fingerprint": "sha256:check",
    }

    def fail(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise bootstrap._ReadinessError("locked_check_failed", fingerprint="sha256:check")

    monkeypatch.setattr(bootstrap, "_run_process", fail)
    assert bootstrap._uv_check("/tools/uv", tmp_path, fingerprint="sha256:check", strict=False) is False
    with pytest.raises(bootstrap._ReadinessError):
        bootstrap._uv_check("/tools/uv", tmp_path, fingerprint="sha256:check", strict=True)


def test_hook_installer_receives_exact_workspace_source_and_maps_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0/C3: readiness delegates one exact force-install contract."""

    workspace = tmp_path / "workspace"
    source = workspace / "src" / "fa" / "hygiene" / "hooks"
    calls: list[tuple[Path, bool, Path | None]] = []

    def install(
        repo_root: Path | None = None,
        *,
        force: bool = False,
        hook_source_dir: Path | None = None,
    ) -> list[Path]:
        assert repo_root is not None
        calls.append((repo_root, force, hook_source_dir))
        return []

    ownership_calls: list[tuple[Path, Path, str | None]] = []
    monkeypatch.setattr(
        bootstrap,
        "_assert_managed_hook_ownership",
        lambda path, hook_source, *, fingerprint=None: ownership_calls.append((path, hook_source, fingerprint)),
    )
    monkeypatch.setattr(bootstrap, "install_hooks", install)
    bootstrap._install_workspace_hooks(workspace, source)
    assert ownership_calls == [(workspace, source, None)]
    assert calls == [(workspace, True, source)]

    monkeypatch.setattr(
        bootstrap,
        "install_hooks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("install failed")),
    )
    with pytest.raises(bootstrap._ReadinessError) as caught:
        bootstrap._install_workspace_hooks(workspace, source)
    assert caught.value.reason_code == "hook_status_failed"


def test_atomic_text_replaces_content_privately_and_cleans_temp(tmp_path: Path) -> None:
    """C0/C3: CT4 writes expose no partial file or permissive mode."""

    target = tmp_path / "nested" / "state.json"
    bootstrap._write_atomic_text(target, "first\n")
    bootstrap._write_atomic_text(target, "second\n")

    assert target.read_text(encoding="utf-8") == "second\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(target.parent.stat().st_mode) == 0o700
    assert list(target.parent.glob(".*.tmp-*")) == []


def test_atomic_and_log_writers_use_explicit_utf8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0: persisted CT4/CT8 text never depends on process locale."""

    original_fdopen = os.fdopen
    encodings: list[str | None] = []

    def fdopen(
        fd: int, mode: str = "r", buffering: int = -1, encoding: str | None = None, *args: Any, **kwargs: Any
    ) -> Any:
        encodings.append(encoding)
        return original_fdopen(fd, mode, buffering, encoding, *args, **kwargs)

    monkeypatch.setattr("fa.workspace_bootstrap.os.fdopen", fdopen)
    target = tmp_path / "state" / "marker"
    bootstrap._write_atomic_text(target, "state\n")
    workspace = tmp_path / "workspace"
    (workspace / ".fa").mkdir(parents=True)
    state = ReadyState(
        status=ReadyStatus.READY,
        fingerprint="sha256:utf8",
        reason_code="ready_fast_path",
        log_path=workspace / ".fa" / "bootstrap.log",
        repaired=False,
        elapsed_ms=1,
    )
    bootstrap._append_log(state, workspace=workspace, return_code=0)

    assert encodings == ["utf-8", "utf-8"]


def test_degraded_recheck_removes_previous_ready_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1/C3: a prior marker never survives a current degraded result."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    assert ensure_workspace_ready(workspace).reason_code == "ready_repaired"
    assert (workspace / ".fa" / "ready-state.json").is_file()
    empty_path = tmp_path / "empty-path"
    empty_path.mkdir()
    monkeypatch.setenv("PATH", str(empty_path))

    state = ensure_workspace_ready(workspace)

    assert state.reason_code == "tool_missing"
    assert not (workspace / ".fa" / "ready-state.json").exists()


def test_log_append_failure_returns_state_io_and_removes_ready_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3: unobservable readiness is not published as READY."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    assert ensure_workspace_ready(workspace).reason_code == "ready_repaired"
    monkeypatch.setattr(
        bootstrap,
        "_append_log",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("log unavailable")),
    )

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_INTERNAL
    assert state.reason_code == "state_io_failed"
    assert not (workspace / ".fa" / "ready-state.json").exists()


def test_pyproject_drift_cli_warns_without_rewriting_lock_or_ready_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C2/C3 P10: drift is failure-observable and never rewrites lock authority."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    assert ensure_workspace_ready(workspace).reason_code == "ready_repaired"
    lock_before = (workspace / "uv.lock").read_bytes()
    (workspace / "pyproject.toml").write_text("[project]\nname='drifted'\n", encoding="utf-8")
    monkeypatch.setenv("FA_TEST_UV_CHECK_RC", "6")

    rc = bootstrap._main(["ensure", "--workspace", str(workspace)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert rc == 75
    assert payload["status"] == "degraded_environment"
    assert payload["reason_code"] == "locked_check_failed"
    assert captured.err == (
        f"[WORKSPACE_BOOTSTRAP] degraded_environment: locked_check_failed; log={workspace / '.fa' / 'bootstrap.log'}\n"
    )
    assert (workspace / "uv.lock").read_bytes() == lock_before
    assert not (workspace / ".fa" / "ready-state.json").exists()


def test_lock_serializes_concurrent_callers_to_one_repair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C1/C3 E: concurrent admission cannot duplicate or corrupt readiness state."""

    workspace = _make_workspace(tmp_path)
    calls_path = _install_fake_uv(tmp_path, monkeypatch)
    monkeypatch.setenv("FA_TEST_UV_SYNC_SLEEP", "0.15")
    barrier = threading.Barrier(3)
    states: list[ReadyState] = []

    def run() -> None:
        barrier.wait()
        states.append(ensure_workspace_ready(workspace))

    threads = [threading.Thread(target=run), threading.Thread(target=run)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=10)

    assert not any(thread.is_alive() for thread in threads)
    assert sorted(state.reason_code for state in states) == ["ready_fast_path", "ready_repaired"]
    assert sum(call == ["uv", "sync", "--locked", "--extra", "dev"] for call in _calls(calls_path)) == 1
    marker = _marker(workspace)
    assert marker["state"] == "ready"
    assert _sentinel(tmp_path, marker["fingerprint"]).is_file()


@pytest.mark.parametrize("argv", [[], ["ensure"]])
def test_cli_requires_subcommand_and_workspace_with_stable_program_name(
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C0: parser rejects partial invocation before readiness side effects."""

    with pytest.raises(SystemExit) as caught:
        bootstrap._main(argv)

    assert caught.value.code == 2
    assert capsys.readouterr().err.startswith("usage: python -m fa.workspace_bootstrap")


@pytest.mark.parametrize(
    ("status", "expected_rc", "stderr_expected"),
    [
        (ReadyStatus.READY, 0, False),
        (ReadyStatus.DEGRADED_ENVIRONMENT, 75, True),
        (ReadyStatus.DEGRADED_INTERNAL, 70, True),
    ],
)
def test_cli_emits_stable_json_exit_and_degraded_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    status: ReadyStatus,
    expected_rc: int,
    stderr_expected: bool,
) -> None:
    """C0/C2 F: adapter serialization and exit codes are closed."""

    workspace = tmp_path / "relative-workspace"
    state = ReadyState(
        status=status,
        fingerprint="sha256:abc" if status is ReadyStatus.READY else None,
        reason_code="ready_fast_path" if status is ReadyStatus.READY else "tool_missing",
        log_path=(workspace / ".fa" / "bootstrap.log").resolve(),
        repaired=False,
        elapsed_ms=12,
    )
    seen_paths: list[Path] = []

    def ensure(path: Path) -> ReadyState:
        seen_paths.append(path)
        return state

    monkeypatch.setattr(bootstrap, "ensure_workspace_ready", ensure)

    rc = bootstrap._main(["ensure", "--workspace", str(workspace)])

    captured = capsys.readouterr()
    assert seen_paths == [workspace]
    assert rc == expected_rc
    assert (
        captured.out
        == json.dumps(
            {
                "elapsed_ms": 12,
                "fingerprint": state.fingerprint,
                "log_path": str(state.log_path),
                "reason_code": state.reason_code,
                "repaired": False,
                "status": status.value,
            },
            sort_keys=True,
        )
        + "\n"
    )
    assert (captured.err != "") is stderr_expected
    if stderr_expected:
        assert captured.err == (f"[WORKSPACE_BOOTSTRAP] {status.value}: {state.reason_code}; log={state.log_path}\n")


@pytest.mark.parametrize(
    "missing",
    [
        "knowledge/llms.txt",
        "pyproject.toml",
        "uv.lock",
        ".pre-commit-config.yaml",
        f"src/fa/hygiene/hooks/{HOOK_NAMES[0]}",
        "src/fa/hygiene/hooks/install.py",
        "src/fa/hygiene/hooks/status.py",
    ],
)
def test_missing_workspace_authority_is_invalid_before_state_mutation(tmp_path: Path, missing: str) -> None:
    """C3: every required project/hook input participates in admission."""

    workspace = _make_workspace(tmp_path)
    (workspace / missing).unlink()

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_INTERNAL
    assert state.reason_code == "invalid_workspace"
    assert not (workspace / ".fa").exists()


def test_non_git_directory_is_invalid_even_with_project_files(tmp_path: Path) -> None:
    """C3: project-shaped files without Git authority are not managed readiness."""

    workspace = _make_workspace(tmp_path)
    shutil.rmtree(workspace / ".git")

    state = ensure_workspace_ready(workspace)

    assert state.reason_code == "invalid_workspace"
    assert not (workspace / ".fa").exists()


@requires_symlinks
def test_escaping_hook_source_symlink_is_invalid_without_external_readiness_writes(
    tmp_path: Path,
) -> None:
    """C3: explicit source authority is file-contained, not directory theater."""

    workspace = _make_workspace(tmp_path)
    external = tmp_path / "external-hook"
    external.write_text("#!/bin/sh\necho external\n", encoding="utf-8")
    source = workspace / "src" / "fa" / "hygiene" / "hooks" / HOOK_NAMES[0]
    source.unlink()
    source.symlink_to(external)

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_INTERNAL
    assert state.reason_code == "invalid_workspace"
    assert external.read_text(encoding="utf-8") == "#!/bin/sh\necho external\n"
    assert not (workspace / ".fa").exists()


@requires_symlinks
def test_contained_hook_source_symlink_is_still_invalid(tmp_path: Path) -> None:
    """C3: tracked hook authorities must be regular files, even when contained."""

    workspace = _make_workspace(tmp_path)
    hook_dir = workspace / "src" / "fa" / "hygiene" / "hooks"
    source = hook_dir / HOOK_NAMES[0]
    target = hook_dir / "contained-target"
    source.replace(target)
    source.symlink_to(target.name)

    state = ensure_workspace_ready(workspace)

    assert state.reason_code == "invalid_workspace"
    assert not (workspace / ".fa").exists()


@requires_symlinks
def test_symlinked_private_state_directory_is_rejected_without_external_write(tmp_path: Path) -> None:
    """C3: readiness cannot follow agent-controlled .fa state outside workspace."""

    workspace = _make_workspace(tmp_path)
    external = tmp_path / "external-state"
    external.mkdir()
    (workspace / ".fa").symlink_to(external, target_is_directory=True)

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_INTERNAL
    assert state.reason_code == "state_io_failed"
    assert list(external.iterdir()) == []


@requires_symlinks
@pytest.mark.parametrize("name", ["bootstrap.log", "bootstrap.lock"])
def test_symlinked_private_state_file_is_rejected_without_external_write(tmp_path: Path, name: str) -> None:
    """C3: no-follow applies to both append log and lock file producers."""

    workspace = _make_workspace(tmp_path)
    state_dir = workspace / ".fa"
    state_dir.mkdir()
    external = tmp_path / f"external-{name}"
    external.write_text("preserve\n", encoding="utf-8")
    (state_dir / name).symlink_to(external)

    state = ensure_workspace_ready(workspace)

    assert state.status is ReadyStatus.DEGRADED_INTERNAL
    assert state.reason_code == "state_io_failed"
    assert external.read_text(encoding="utf-8") == "preserve\n"


@requires_posix_modes
@pytest.mark.parametrize("artifact", ["marker", "sentinel"])
def test_permissive_ready_artifact_mode_forces_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
) -> None:
    """C1/C3: active readiness requires private marker and cache authority."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    first = ensure_workspace_ready(workspace)
    assert first.fingerprint is not None
    path = workspace / ".fa" / "ready-state.json" if artifact == "marker" else _sentinel(tmp_path, first.fingerprint)
    path.chmod(0o644)

    state = ensure_workspace_ready(workspace)

    assert state.reason_code == "ready_repaired"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


@pytest.mark.parametrize("corruption", ["invalid-json", "wrong-fingerprint", "missing-checked-at"])
def test_corrupt_marker_never_authorizes_fast_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    """C1/C3: marker parsing/equality cannot override active readiness checks."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    first = ensure_workspace_ready(workspace)
    marker_path = workspace / ".fa" / "ready-state.json"
    if corruption == "invalid-json":
        marker_path.write_text("{invalid", encoding="utf-8")
    else:
        payload = _marker(workspace)
        if corruption == "wrong-fingerprint":
            payload["fingerprint"] = "sha256:wrong"
        else:
            payload.pop("checked_at")
        marker_path.write_text(json.dumps(payload), encoding="utf-8")
    marker_path.chmod(0o600)

    state = ensure_workspace_ready(workspace)

    assert first.fingerprint == state.fingerprint
    assert state.reason_code == "ready_repaired"


@pytest.mark.parametrize(
    ("corruption", "expected_reason"),
    [
        ("missing", "ready_repaired"),
        ("stale", "hook_seat_collision"),
        ("non-executable", "ready_repaired"),
        pytest.param("wrong-symlink", "hook_seat_collision", marks=requires_symlinks),
    ],
)
def test_hook_seat_repair_requires_absent_or_verifiably_fa_owned_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
    expected_reason: str,
) -> None:
    """C1/C3: repair changes only absent or exact-copy/source-link FA seats."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    assert ensure_workspace_ready(workspace).reason_code == "ready_repaired"
    seat = workspace / ".git" / "hooks" / HOOK_NAMES[0]
    if corruption == "missing":
        seat.unlink()
    elif corruption == "stale":
        seat.unlink()
        _write_executable(seat, "#!/bin/sh\necho stale\n")
    elif corruption == "non-executable":
        content = seat.read_text(encoding="utf-8")
        seat.unlink()
        seat.write_text(content, encoding="utf-8")
        seat.chmod(0o600)
    else:
        external = tmp_path / "wrong-hook"
        source = workspace / "src" / "fa" / "hygiene" / "hooks" / HOOK_NAMES[0]
        _write_executable(external, source.read_text(encoding="utf-8"))
        seat.unlink()
        seat.symlink_to(external)

    seat_before = (
        seat.read_bytes() if seat.exists() else None,
        stat.S_IMODE(seat.lstat().st_mode) if seat.exists() or seat.is_symlink() else None,
        os.readlink(seat) if seat.is_symlink() else None,
    )

    state = ensure_workspace_ready(workspace)

    assert state.reason_code == expected_reason
    if expected_reason == "ready_repaired":
        source = workspace / "src" / "fa" / "hygiene" / "hooks" / HOOK_NAMES[0]
        assert seat.read_bytes() == source.read_bytes()
        assert os.access(seat, os.X_OK)
    else:
        assert state.status is ReadyStatus.DEGRADED_ENVIRONMENT
        assert (
            seat.read_bytes(),
            stat.S_IMODE(seat.lstat().st_mode),
            os.readlink(seat) if seat.is_symlink() else None,
        ) == seat_before
        assert not (workspace / ".fa" / "ready-state.json").exists()


def test_marker_and_sentinel_reads_use_explicit_utf8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0: active-state reads never depend on process locale."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    state = ensure_workspace_ready(workspace)
    assert state.fingerprint is not None
    marker = workspace / ".fa" / "ready-state.json"
    sentinel = _sentinel(tmp_path, state.fingerprint)
    original_read_text = Path.read_text
    seen: list[tuple[Path, str | None]] = []

    def read_text(path: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if path in (marker, sentinel):
            seen.append((path, encoding))
        return original_read_text(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert (
        bootstrap._marker_matches(
            workspace,
            fingerprint=state.fingerprint,
            python_minor=f"{sys.version_info.major}.{sys.version_info.minor}",
            uv_version="uv 0.test",
        )
        is True
    )
    monkeypatch.setattr(bootstrap, "_hooks_current", lambda *_args: True)
    monkeypatch.setattr(bootstrap, "_uv_check", lambda *_args, **_kwargs: True)
    assert (
        bootstrap._fast_ready(
            workspace,
            workspace / "src" / "fa" / "hygiene" / "hooks",
            uv="/tools/uv",
            uv_version="uv 0.test",
            python_minor=f"{sys.version_info.major}.{sys.version_info.minor}",
            fingerprint=state.fingerprint,
        )
        is True
    )
    assert (marker, "utf-8") in seen
    assert (sentinel, "utf-8") in seen


def test_hook_status_resolution_and_read_errors_are_unhealthy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0/C3: status resolution/read failure cannot authorize readiness."""

    workspace = _make_workspace(tmp_path)
    source = workspace / "src" / "fa" / "hygiene" / "hooks"
    monkeypatch.setattr(
        bootstrap,
        "resolve_hooks_dir",
        lambda _workspace: (_ for _ in ()).throw(SystemExit("unavailable")),
    )
    assert bootstrap._hooks_current(workspace, source) is False

    hooks_dir = workspace / ".git" / "hooks"
    monkeypatch.setattr(bootstrap, "resolve_hooks_dir", lambda _workspace: hooks_dir)
    for name in HOOK_NAMES:
        target = hooks_dir / name
        target.write_bytes((source / name).read_bytes())
        target.chmod(0o755)
    original_read_bytes = Path.read_bytes

    def fail_target_read(path: Path) -> bytes:
        if path.parent == hooks_dir:
            raise OSError("unreadable")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_target_read)
    assert bootstrap._hooks_current(workspace, source) is False


def test_fast_ready_sentinel_error_is_false_and_forwards_active_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0/C3: unreadable cache authority never becomes fast READY."""

    workspace = _make_workspace(tmp_path)
    fingerprint = "sha256:sentinel"
    sentinel = tmp_path / "sentinel"
    sentinel.write_text(fingerprint + "\n", encoding="utf-8")
    sentinel.chmod(0o600)
    monkeypatch.setattr(bootstrap, "_sentinel_path", lambda _fingerprint: sentinel)
    monkeypatch.setattr(bootstrap, "_marker_matches", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(bootstrap, "_hooks_current", lambda *_args: True)
    uv_calls: list[tuple[str, Path, str, bool]] = []

    def uv_check(uv: str, path: Path, *, fingerprint: str, strict: bool) -> bool:
        uv_calls.append((uv, path, fingerprint, strict))
        return True

    monkeypatch.setattr(bootstrap, "_uv_check", uv_check)
    original_read_text = Path.read_text

    def fail_sentinel_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == sentinel:
            raise OSError("cache unreadable")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_sentinel_read)

    assert (
        bootstrap._fast_ready(
            workspace,
            workspace / "src" / "fa" / "hygiene" / "hooks",
            uv="/tools/uv",
            uv_version="uv test",
            python_minor="3.13",
            fingerprint=fingerprint,
        )
        is False
    )
    assert uv_calls == []

    monkeypatch.setattr(Path, "read_text", original_read_text)
    assert (
        bootstrap._fast_ready(
            workspace,
            workspace / "src" / "fa" / "hygiene" / "hooks",
            uv="/tools/uv",
            uv_version="uv test",
            python_minor="3.13",
            fingerprint=fingerprint,
        )
        is True
    )
    assert uv_calls == [("/tools/uv", workspace, fingerprint, False)]


def test_repair_pipeline_forwards_exact_order_paths_and_strictness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C0/C1: CT3 transaction order and authority arguments are closed."""

    workspace = tmp_path / "workspace"
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    sentinel = tmp_path / "cache" / "sentinel"
    events: list[tuple[Any, ...]] = []
    fingerprints = iter(["sha256:initial", "sha256:final"])
    python_reads = 0

    def uv_executable(path: Path) -> tuple[str, str]:
        events.append(("uv-version", path))
        return "/tools/uv", "uv test"

    def read_python(path: Path, *, strict: bool, fingerprint: str | None = None) -> str | None:
        nonlocal python_reads
        python_reads += 1
        events.append(("python", path, strict, fingerprint))
        return None if python_reads == 1 else "3.13"

    def fingerprint_fn(
        path: Path,
        source: Path,
        *,
        python_minor: str,
        uv_version: str,
    ) -> str:
        events.append(("fingerprint", path, source, python_minor, uv_version))
        return next(fingerprints)

    def assert_ownership(
        path: Path,
        source: Path,
        *,
        fingerprint: str | None = None,
    ) -> None:
        events.append(("ownership", path, source, fingerprint))

    def install(path: Path, source: Path, *, fingerprint: str | None = None) -> None:
        events.append(("install", path, source, fingerprint))

    def run_process(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        events.append(("process", command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    def uv_check(uv: str, path: Path, *, fingerprint: str, strict: bool) -> bool:
        events.append(("uv-check", uv, path, fingerprint, strict))
        return True

    def hooks_current(path: Path, source: Path) -> bool:
        events.append(("hooks", path, source))
        return True

    writes: list[tuple[Path, str]] = []
    monkeypatch.setattr(bootstrap, "_uv_executable", uv_executable)
    monkeypatch.setattr(bootstrap, "_read_python_minor", read_python)
    monkeypatch.setattr(bootstrap, "_fingerprint", fingerprint_fn)
    monkeypatch.setattr(bootstrap, "_remove_marker", lambda path: events.append(("remove-marker", path)))
    monkeypatch.setattr(bootstrap, "_assert_managed_hook_ownership", assert_ownership)
    monkeypatch.setattr(bootstrap, "_install_workspace_hooks", install)
    monkeypatch.setattr(bootstrap, "_run_process", run_process)
    monkeypatch.setattr(bootstrap, "_uv_check", uv_check)
    monkeypatch.setattr(bootstrap, "_hooks_current", hooks_current)
    monkeypatch.setattr(bootstrap, "_sentinel_path", lambda fingerprint: sentinel)
    monkeypatch.setattr(bootstrap, "_write_atomic_text", lambda path, content: writes.append((path, content)))

    state = bootstrap._ensure_locked(workspace, hook_source, started=0.0)

    assert state.reason_code == "ready_repaired"
    assert state.fingerprint == "sha256:final"
    assert events[:7] == [
        ("uv-version", workspace),
        ("python", workspace, False, None),
        ("fingerprint", workspace, hook_source, f"{sys.version_info.major}.{sys.version_info.minor}", "uv test"),
        ("ownership", workspace, hook_source, "sha256:initial"),
        ("remove-marker", workspace),
        ("install", workspace, hook_source, "sha256:initial"),
        (
            "process",
            ["/tools/uv", "sync", "--locked", "--extra", "dev"],
            {
                "cwd": workspace,
                "timeout": 900.0,
                "failure_reason": "sync_failed",
                "timeout_reason": "sync_timeout",
                "fingerprint": "sha256:initial",
            },
        ),
    ]
    assert events[7] == (
        "process",
        [str(workspace / ".venv" / "bin" / "pre-commit"), "install-hooks"],
        {
            "cwd": workspace,
            "timeout": 900.0,
            "failure_reason": "precommit_prewarm_failed",
            "timeout_reason": "precommit_prewarm_timeout",
            "fingerprint": "sha256:initial",
        },
    )
    assert events[8:] == [
        ("install", workspace, hook_source, "sha256:initial"),
        ("python", workspace, True, "sha256:initial"),
        ("fingerprint", workspace, hook_source, "3.13", "uv test"),
        ("uv-check", "/tools/uv", workspace, "sha256:final", True),
        ("hooks", workspace, hook_source),
    ]
    assert writes[0] == (sentinel, "sha256:final\n")
    assert writes[1][0] == workspace / ".fa" / "ready-state.json"
    marker = json.loads(writes[1][1])
    assert marker["fingerprint"] == "sha256:final"
    assert marker["project_python"] == "3.13"
    assert marker["uv_version"] == "uv test"
    assert marker["checked_at"].endswith("Z")


def test_log_is_private_structured_and_does_not_capture_environment_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 F: observability is structured without environment/task disclosure."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    monkeypatch.setenv("FA_TASK", "must-not-appear")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret-must-not-appear")
    monkeypatch.setenv("FA_TEST_UV_SYNC_RC", "8")

    state = ensure_workspace_ready(workspace)

    assert state.reason_code == "sync_failed"
    rows = [json.loads(line) for line in state.log_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["status"] == "degraded_environment"
    assert rows[0]["reason_code"] == "sync_failed"
    assert rows[0]["workspace"] == str(workspace.resolve())
    assert rows[0]["stage"] == "uv_sync"
    assert rows[0]["argv"] == ["uv", "sync", "--locked", "--extra", "dev"]
    assert rows[0]["return_code"] == 8
    serialized = json.dumps(rows)
    assert "must-not-appear" not in serialized
    assert "sk-secret" not in serialized
    assert stat.S_IMODE(state.log_path.stat().st_mode) == 0o600


def _artifact_snapshot(paths: tuple[Path, ...]) -> dict[Path, tuple[bytes, int, int]]:
    return {path: (path.read_bytes(), path.stat().st_mtime_ns, stat.S_IMODE(path.stat().st_mode)) for path in paths}


def test_read_only_check_proves_current_state_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 S4: check reuses full fast-readiness authority without state writes."""

    workspace = _make_workspace(tmp_path)
    calls = _install_fake_uv(tmp_path, monkeypatch)
    first = ensure_workspace_ready(workspace)
    assert first.status is ReadyStatus.READY
    assert first.fingerprint is not None
    artifacts = (
        workspace / ".fa" / "ready-state.json",
        workspace / ".fa" / "bootstrap.log",
        workspace / ".fa" / "bootstrap.lock",
        _sentinel(tmp_path, first.fingerprint),
    )
    before = _artifact_snapshot(artifacts)
    calls_before = len(_calls(calls))

    checked = bootstrap.check_workspace_ready(workspace)

    assert checked.status is ReadyStatus.READY
    assert checked.reason_code == "ready_fast_path"
    assert checked.repaired is False
    assert checked.fingerprint == first.fingerprint
    assert _artifact_snapshot(artifacts) == before
    assert _calls(calls)[calls_before:] == [
        ["uv", "--version"],
        ["uv", "sync", "--locked", "--extra", "dev", "--check"],
    ]


def test_read_only_check_on_cold_workspace_creates_no_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 S4: missing readiness is observable but check cannot repair it."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)

    checked = bootstrap.check_workspace_ready(workspace)

    assert checked.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert checked.reason_code == "locked_check_failed"
    assert checked.repaired is False
    assert not (workspace / ".fa").exists()
    assert not (workspace / ".venv").exists()


def test_read_only_check_rejects_symlinked_state_without_external_read_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 S4: read-only status cannot trust or follow redirected private state."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    external = tmp_path / "external-state"
    external.mkdir()
    external_marker = external / "ready-state.json"
    external_marker.write_text('{"state":"ready"}\n', encoding="utf-8")
    before = external_marker.read_bytes()
    (workspace / ".fa").symlink_to(external, target_is_directory=True)

    checked = bootstrap.check_workspace_ready(workspace)

    assert checked.status is ReadyStatus.DEGRADED_INTERNAL
    assert checked.reason_code == "state_io_failed"
    assert external_marker.read_bytes() == before
    assert not (external / "bootstrap.log").exists()
    assert not (external / "bootstrap.lock").exists()


def test_read_only_check_distrusts_permissive_state_mode_without_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C3 S4: check detects private-mode drift but cannot chmod it."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    first = ensure_workspace_ready(workspace)
    assert first.status is ReadyStatus.READY
    state_dir = workspace / ".fa"
    state_dir.chmod(0o755)

    checked = bootstrap.check_workspace_ready(workspace)

    assert checked.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert checked.reason_code == "locked_check_failed"
    assert stat.S_IMODE(state_dir.stat().st_mode) == 0o755


@pytest.mark.parametrize("artifact", ["bootstrap.log", "bootstrap.lock"])
def test_read_only_check_reports_missing_private_artifact_without_repair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact: str,
) -> None:
    """C3 S4: log/lock absence invalidates readiness and check cannot recreate it."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    first = ensure_workspace_ready(workspace)
    assert first.status is ReadyStatus.READY
    path = workspace / ".fa" / artifact
    path.unlink()

    checked = bootstrap.check_workspace_ready(workspace)

    assert checked.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert checked.reason_code == "locked_check_failed"
    assert not path.exists()


def test_read_only_check_preserves_computed_fingerprint_for_active_state_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 S4: stale active-state diagnostics retain the fingerprint authority."""

    workspace = _make_workspace(tmp_path)
    _install_fake_uv(tmp_path, monkeypatch)
    first = ensure_workspace_ready(workspace)
    assert first.status is ReadyStatus.READY
    assert first.fingerprint is not None
    marker = workspace / ".fa" / "ready-state.json"
    marker.unlink()

    checked = bootstrap.check_workspace_ready(workspace)

    assert checked.status is ReadyStatus.DEGRADED_ENVIRONMENT
    assert checked.reason_code == "locked_check_failed"
    assert checked.fingerprint == first.fingerprint
    assert not marker.exists()


def test_check_cli_dispatches_read_only_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C1 S4: CLI check has a real producer distinct from ensure."""

    workspace = tmp_path / "workspace"
    expected = ReadyState(
        status=ReadyStatus.READY,
        fingerprint="sha256:check",
        reason_code="ready_fast_path",
        log_path=workspace / ".fa" / "bootstrap.log",
        repaired=False,
        elapsed_ms=4,
    )
    seen: list[Path] = []

    def check(path: Path) -> ReadyState:
        seen.append(path)
        return expected

    monkeypatch.setattr(bootstrap, "check_workspace_ready", check)
    rc = bootstrap._main(["check", "--workspace", str(workspace)])

    assert rc == 0
    assert seen == [workspace]
    assert json.loads(capsys.readouterr().out)["fingerprint"] == "sha256:check"


# ---------------------------------------------------------------------------
# Mutation-killing suite for 34 survivors (2026-08-25 targeted run)
# Groups A-G per PLAN-workspace-bootstrap-mutation-34-survivors-subplan.md
# ---------------------------------------------------------------------------


def test_command_environment_hermetic_pop_and_pin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Group A: kills 12 pop mutants + 2 key-set mutants + 3 value mutants (17 total).

    Asserts that 5 leak keys are removed even when present, that
    UV_PROJECT_ENVIRONMENT leak is popped then re-pinned to workspace/.venv,
    and that original os.environ is not mutated.
    """

    leak_keys = [
        "VIRTUAL_ENV",
        "VIRTUAL_ENV_PROMPT",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
        "PYTHONHOME",
    ]
    pop_only_keys = [
        "VIRTUAL_ENV",
        "VIRTUAL_ENV_PROMPT",
        "CONDA_PREFIX",
        "UV_PYTHON",
        "PYTHONHOME",
    ]
    for key in leak_keys:
        monkeypatch.setenv(key, f"/leak/{key}")

    # Snapshot original to ensure copy semantics
    original_snapshot = {k: os.environ.get(k) for k in leak_keys}

    env = bootstrap._command_environment(tmp_path)

    # Pop must have removed 5 leak-only keys
    for key in pop_only_keys:
        assert key not in env, f"{key} leak not popped — kills mutmut_2..7,10..13"

    # UV_PROJECT_ENVIRONMENT leak is popped then re-pinned — must be present but not leak value
    assert "UV_PROJECT_ENVIRONMENT" in env
    assert env["UV_PROJECT_ENVIRONMENT"] != "/leak/UV_PROJECT_ENVIRONMENT"

    # Pin must be exact resolved path, not "None", not "XX.venvXX", not ".VENV"
    expected_pin = str((tmp_path / ".venv").resolve())
    assert env["UV_PROJECT_ENVIRONMENT"] == expected_pin
    assert env["UV_PROJECT_ENVIRONMENT"] != "None"  # kills mutmut_28 str(None)
    assert env["UV_PROJECT_ENVIRONMENT"].endswith(".venv")  # kills XX.venvXX and .VENV
    assert ".venv" in env["UV_PROJECT_ENVIRONMENT"]
    assert "XX.venvXX" not in env["UV_PROJECT_ENVIRONMENT"]
    assert ".VENV" not in env["UV_PROJECT_ENVIRONMENT"]

    # Safe vars must be present
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["UV_LINK_MODE"] == "copy"

    # Original environ must still have leaks (copy, not mutate)
    for key in leak_keys:
        assert os.environ.get(key) == original_snapshot[key]

    # None workspace must NOT set pin (kills mutmut_26,27 when they set wrong key)
    env_none = bootstrap._command_environment(None)
    for key in leak_keys:
        assert key not in env_none, f"{key} not popped in None case"
    assert "UV_PROJECT_ENVIRONMENT" not in env_none


def test_command_environment_value_exactness(tmp_path: Path) -> None:
    """Group A extra: exactness of .venv path."""

    env = bootstrap._command_environment(tmp_path / "my-workspace")
    pin = env["UV_PROJECT_ENVIRONMENT"]
    # Must be absolute and resolved
    assert Path(pin).is_absolute()
    assert pin == str((tmp_path / "my-workspace" / ".venv").resolve())
    # Must contain .venv exactly, case-sensitive
    assert pin.endswith(".venv")
    assert ".VENV" not in pin


def test_open_private_calls_os_open_with_private_mode_and_nofollow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Group B: kills mutmut_7 (mode removed → default 0o777).

    Spy records mode and flags without asserting inside wrapper (spy isolation).
    """

    seen: dict[str, Any] = {}
    orig_open = os.open

    def spy_open(path: str | os.PathLike[str], flags: int, *args: Any, **kwargs: Any) -> int:
        # Record flags and mode
        seen["flags"] = flags
        if args:
            seen["mode"] = args[0]
        else:
            seen["mode"] = kwargs.get("mode", 0o777)
        return orig_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", spy_open)

    target = tmp_path / "secret"
    fd = bootstrap._open_private(target, os.O_WRONLY | os.O_CREAT)
    try:
        assert seen["mode"] == 0o600, f"mode {oct(seen.get('mode', 0))} != 0o600 — kills mutmut_7"
        assert seen["flags"] & getattr(os, "O_NOFOLLOW", 0) != 0, "O_NOFOLLOW not set"
        # Final mode must be private
        assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
    finally:
        os.close(fd)


def test_process_runner_pins_workspace_venv_in_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Group C: kills mutmut_21 env=_command_environment(cwd) → None."""

    captured: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["env"] = kwargs.get("env")
        captured["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr("fa.workspace_bootstrap.subprocess.run", fake_run)

    result = bootstrap._run_process(
        ["tool"],
        cwd=tmp_path,
        timeout=1,
        failure_reason="sync_failed",
    )

    assert result.stdout == "ok\n"
    env = captured["env"]
    assert isinstance(env, dict)
    # Must be pinned to cwd/.venv, not None
    assert "UV_PROJECT_ENVIRONMENT" in env, "pin missing — kills mutmut_21"
    assert env["UV_PROJECT_ENVIRONMENT"] == str((tmp_path / ".venv").resolve())
    assert env["UV_PROJECT_ENVIRONMENT"] != "None"


def test_read_python_minor_skips_executable_check_on_nt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Group D: kills mutmut_7,8 for _read_python_minor (nt → XXntXX / NT)."""

    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
    python.chmod(0o644)  # not executable

    monkeypatch.setattr(os, "name", "nt")

    def fake_run_process(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, "3.13\n", "")

    monkeypatch.setattr(bootstrap, "_run_process", fake_run_process)

    # On nt, non-executable should still be considered valid
    result = bootstrap._read_python_minor(tmp_path, strict=False)
    assert result == "3.13"

    result_strict = bootstrap._read_python_minor(tmp_path, strict=True)
    assert result_strict == "3.13"


def test_read_python_minor_requires_executable_on_posix(tmp_path: Path) -> None:
    """Group D: posix side — non-executable must be rejected."""

    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("not exec", encoding="utf-8")
    python.chmod(0o644)

    # Ensure posix
    assert os.name != "nt"
    assert bootstrap._read_python_minor(tmp_path, strict=False) is None


def test_hooks_current_skips_executable_check_on_nt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Group D: kills mutmut_12,13 for _hooks_current."""

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    hooks_dir = workspace / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        src = hook_source / name
        tgt = hooks_dir / name
        tgt.write_bytes(src.read_bytes())
        tgt.chmod(0o644)  # not executable

    monkeypatch.setattr(os, "name", "nt")
    assert bootstrap._hooks_current(workspace, hook_source) is True


def test_hooks_current_requires_executable_on_posix(tmp_path: Path) -> None:
    """Group D: posix requires X bit."""

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    hooks_dir = workspace / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        src = hook_source / name
        tgt = hooks_dir / name
        tgt.write_bytes(src.read_bytes())
        tgt.chmod(0o644)

    assert os.name != "nt"
    assert bootstrap._hooks_current(workspace, hook_source) is False


def test_hooks_current_false_on_content_mismatch(tmp_path: Path) -> None:
    """Group E: kills mutmut_21 return False → True on content mismatch."""

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    hooks_dir = workspace / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        src = hook_source / name
        tgt = hooks_dir / name
        tgt.write_bytes(src.read_bytes())
        tgt.chmod(0o755)

    # Corrupt one
    (hooks_dir / HOOK_NAMES[0]).write_bytes(b"different content")
    (hooks_dir / HOOK_NAMES[0]).chmod(0o755)

    assert bootstrap._hooks_current(workspace, hook_source) is False


@requires_symlinks
def test_hooks_current_false_on_symlink_mismatch(tmp_path: Path) -> None:
    """Group E: kills mutmut_24 symlink resolve mismatch False → True.

    Fix: external must be executable, otherwise X_OK check fails before symlink check,
    causing both original and mutant to return False (survivor).
    """

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    hooks_dir = workspace / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        src = hook_source / name
        tgt = hooks_dir / name
        tgt.write_bytes(src.read_bytes())
        tgt.chmod(0o755)

    external = tmp_path / "external-hook"
    external.write_bytes((hook_source / HOOK_NAMES[0]).read_bytes())
    external.chmod(0o755)
    target = hooks_dir / HOOK_NAMES[0]
    target.unlink()
    target.symlink_to(external)

    assert bootstrap._hooks_current(workspace, hook_source) is False


@requires_symlinks
def test_hook_seat_is_manageable_broken_symlink(tmp_path: Path) -> None:
    """Group F: kills strict=True → False mutants (broken symlink not manageable)."""

    source = tmp_path / "source"
    source.write_text("hook content", encoding="utf-8")

    broken = tmp_path / "broken"
    broken.symlink_to(tmp_path / "nonexistent-target")

    # Broken symlink should NOT be manageable
    assert bootstrap._hook_seat_is_manageable(source, broken) is False


def test_hook_seat_is_manageable_oserror_on_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Group F: kills except OSError False → True (mutmut_12)."""

    source = tmp_path / "source"
    source.write_text("hook content", encoding="utf-8")
    target = tmp_path / "target"
    target.write_text("different", encoding="utf-8")

    orig_read_bytes = Path.read_bytes
    calls: list[Path] = []

    def fake_read_bytes(self: Path) -> bytes:
        calls.append(self)
        if self == target:
            raise OSError("unreadable")
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)

    assert bootstrap._hook_seat_is_manageable(source, target) is False
    assert target in calls


def test_assert_managed_hook_ownership_preserves_fingerprint_on_resolve_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Group G: kills mutmut_6,8 fingerprint=None/omitted in hook_status_failed."""

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"

    def raise_oserror(_: Path) -> Path:
        raise OSError("resolve failed")

    monkeypatch.setattr(bootstrap, "resolve_hooks_dir", raise_oserror)

    with pytest.raises(bootstrap._ReadinessError) as caught:
        bootstrap._assert_managed_hook_ownership(workspace, hook_source, fingerprint="sha256:abc123")

    assert caught.value.reason_code == "hook_status_failed"
    assert caught.value.fingerprint == "sha256:abc123"


def test_assert_managed_hook_ownership_preserves_fingerprint_on_default_resolve_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Group G: same for default hooks dir."""

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"

    def ok_hooks_dir(_: Path) -> Path:
        return workspace / ".git" / "hooks"

    def raise_oserror(_: Path) -> Path:
        raise OSError("default resolve failed")

    monkeypatch.setattr(bootstrap, "resolve_hooks_dir", ok_hooks_dir)
    monkeypatch.setattr(bootstrap, "resolve_default_hooks_dir", raise_oserror)

    with pytest.raises(bootstrap._ReadinessError) as caught:
        bootstrap._assert_managed_hook_ownership(workspace, hook_source, fingerprint="sha256:def456")

    assert caught.value.reason_code == "hook_status_failed"
    assert caught.value.fingerprint == "sha256:def456"


def test_install_workspace_hooks_preserves_fingerprint_on_ownership_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Group G: kills mutmut_3,6 in _install_workspace_hooks ownership check.

    Real failure path: custom hooksPath set → _assert_managed_hook_ownership
    raises with fingerprint from argument, not None. This kills mutants that
    change fingerprint=fingerprint → None / omitted.
    """

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    custom = tmp_path / "custom-hooks"
    custom.mkdir()
    subprocess.run(
        ["git", "config", "core.hooksPath", str(custom)],
        cwd=workspace,
        check=True,
    )

    with pytest.raises(bootstrap._ReadinessError) as caught:
        bootstrap._install_workspace_hooks(workspace, hook_source, fingerprint="sha256:install123")

    assert caught.value.reason_code == "custom_hooks_unmanaged"
    assert caught.value.fingerprint == "sha256:install123"

    # Also test propagation when ownership check itself raises with its own fingerprint
    # (ensures wrapper doesn't swallow)
    def raise_readiness(*_args: Any, **_kwargs: Any) -> None:
        raise bootstrap._ReadinessError("custom_hooks_unmanaged", fingerprint="sha256:owner")

    monkeypatch.setattr(bootstrap, "_assert_managed_hook_ownership", raise_readiness)

    with pytest.raises(bootstrap._ReadinessError) as caught2:
        bootstrap._install_workspace_hooks(workspace, hook_source, fingerprint="sha256:install123")

    assert caught2.value.fingerprint == "sha256:owner"


def test_install_workspace_hooks_preserves_fingerprint_on_install_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Group G: kills mutmut_15,17 fingerprint=None/omitted on install failure."""

    workspace = tmp_path / "workspace"
    source = workspace / "src" / "fa" / "hygiene" / "hooks"

    monkeypatch.setattr(bootstrap, "_assert_managed_hook_ownership", lambda *a, **k: None)

    def raise_oserror(*_args: Any, **_kwargs: Any) -> list[Path]:
        raise OSError("install failed")

    monkeypatch.setattr(bootstrap, "install_hooks", raise_oserror)

    with pytest.raises(bootstrap._ReadinessError) as caught:
        bootstrap._install_workspace_hooks(workspace, source, fingerprint="sha256:install-fail")

    assert caught.value.reason_code == "hook_status_failed"
    assert caught.value.fingerprint == "sha256:install-fail"


# ---------------------------------------------------------------------------
# Hardening per tests-writing best practices (black-box, no spy)
# ---------------------------------------------------------------------------


@requires_posix_modes
def test_open_private_creates_private_file_even_with_umask_zero(tmp_path: Path) -> None:
    """Hardening: black-box proof that mode 0o600 is enforced even with umask 0.

    Catches mutmut_7 without spying on os.open — if mode arg removed, file would be
    created 0o777 with umask 0, then fchmod would fix it, but fstat on fd should still
    be 0o600. This is the observable security property, not just spy.
    """

    old_umask = os.umask(0)
    try:
        target = tmp_path / "secret-umask"
        fd = bootstrap._open_private(target, os.O_WRONLY | os.O_CREAT)
        try:
            # fd mode via fstat must be private immediately
            assert stat.S_IMODE(os.fstat(fd).st_mode) == 0o600
            # file on disk must also be private
            assert stat.S_IMODE(os.stat(target).st_mode) == 0o600
        finally:
            os.close(fd)
    finally:
        os.umask(old_umask)


def test_command_environment_does_not_mutate_original_environ(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Hardening: copy semantics — original os.environ unchanged."""

    monkeypatch.setenv("VIRTUAL_ENV", "/original")
    before = os.environ["VIRTUAL_ENV"]
    env = bootstrap._command_environment(tmp_path)
    # Returned env must not have leak, but original must still have it
    assert "VIRTUAL_ENV" not in env or env["VIRTUAL_ENV"] != "/original"
    assert os.environ["VIRTUAL_ENV"] == before


def test_command_environment_pin_is_absolute_and_resolved(tmp_path: Path) -> None:
    """Hardening: pin must be absolute resolved path, not relative or None."""

    # Symlink workspace to test resolve()
    real = tmp_path / "real-ws"
    real.mkdir()
    link = tmp_path / "link-ws"
    link.symlink_to(real)

    env = bootstrap._command_environment(link)
    pin = env["UV_PROJECT_ENVIRONMENT"]
    assert Path(pin).is_absolute()
    # resolve() should have resolved symlink
    assert str(real.resolve()) in pin
    assert pin.endswith(".venv")


def test_hooks_current_true_when_exact_copy_and_executable(tmp_path: Path) -> None:
    """Hardening: positive case — exact copy + executable = True."""

    workspace = _make_workspace(tmp_path)
    hook_source = workspace / "src" / "fa" / "hygiene" / "hooks"
    hooks_dir = workspace / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    for name in HOOK_NAMES:
        src = hook_source / name
        tgt = hooks_dir / name
        tgt.write_bytes(src.read_bytes())
        tgt.chmod(0o755)

    assert bootstrap._hooks_current(workspace, hook_source) is True


@requires_symlinks
def test_hook_seat_is_manageable_when_absent_or_exact_copy(tmp_path: Path) -> None:
    """Hardening: absent seat is manageable, exact copy is manageable."""

    source = tmp_path / "source"
    source.write_text("hook", encoding="utf-8")

    # Absent
    absent = tmp_path / "absent"
    assert bootstrap._hook_seat_is_manageable(source, absent) is True

    # Exact copy
    copy = tmp_path / "copy"
    copy.write_text("hook", encoding="utf-8")
    assert bootstrap._hook_seat_is_manageable(source, copy) is True

    # Different content not manageable
    diff = tmp_path / "diff"
    diff.write_text("different", encoding="utf-8")
    assert bootstrap._hook_seat_is_manageable(source, diff) is False


def test_open_private_rejects_symlink(tmp_path: Path) -> None:
    """Hardening: symlink attack rejected."""

    target = tmp_path / "real"
    target.write_text("real", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(target)

    with pytest.raises(OSError):
        bootstrap._open_private(link, os.O_WRONLY | os.O_CREAT)
