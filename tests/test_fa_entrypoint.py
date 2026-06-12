from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

_ENTRYPOINT = Path(__file__).resolve().parents[1] / "scripts" / "fa-entrypoint.sh"


def _base_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    status = tmp_path / "entrypoint-status.txt"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "FA_WORKSPACE": str(workspace),
            "FA_STATUS_FILE": str(status),
            "PATH": f"{bin_dir}:{env.get('PATH', '')}",
            "PYTHONPATH": "",
        }
    )
    return env, status, bin_dir


def _write_fa_stub(bin_dir: Path, exit_code: int = 0) -> Path:
    calls = bin_dir / "fa-calls.txt"
    stub = bin_dir / "fa"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'%q \' "$@" >> "$FA_STUB_CALLS"\n'
        "printf '\\n' >> \"$FA_STUB_CALLS\"\n"
        f"exit {exit_code}\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return calls


def _wait_for_status(status: Path, expected: str, proc: subprocess.Popen[str]) -> str:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if status.exists():
            text = status.read_text(encoding="utf-8")
            if expected in text:
                return text
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    if status.exists():
        pytest.fail(f"status file never contained {expected!r}: {status.read_text()}")
    pytest.fail(f"status file was not written; proc exit={proc.poll()}")


def _terminate(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


def test_entrypoint_standby_does_not_autorun_when_only_task_is_set(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir)
    env.update({"FA_TASK": "do work", "FA_STUB_CALLS": str(calls)})

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=STANDBY", proc)
    finally:
        _terminate(proc)

    assert "FA_AUTO_RUN is not enabled" in text
    assert not calls.exists()


def test_entrypoint_autorun_runs_child_once_and_writes_success(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, exit_code=0)
    env.update(
        {
            "FA_AUTO_RUN": "1",
            "FA_TASK": "implement the plan",
            "FA_ROLE": "planner",
            "FA_MAX_TURNS": "7",
            "FA_RUN_ID": "docker-test-run",
            "FA_RESUME": "1",
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=SUCCESS", proc)
    finally:
        _terminate(proc)

    assert "exit_code=0" in text
    assert "role=planner" in text
    assert "run_id=docker-test-run" in text
    call_text = calls.read_text(encoding="utf-8")
    assert "run" in call_text
    assert "--task" in call_text
    assert "--workspace" in call_text
    assert "--role" in call_text
    assert "--max-turns" in call_text
    assert "--resume" in call_text


def test_entrypoint_invalid_blank_task_writes_status_without_child(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir)
    env.update({"FA_AUTO_RUN": "1", "FA_TASK": " \n\t", "FA_STUB_CALLS": str(calls)})

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "Task is empty" in text
    assert not calls.exists()


def test_entrypoint_autorun_accepts_task_file_inside_workspace(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir, exit_code=0)
    task_file = tmp_path / "workspace" / "tasks" / "plan.md"
    task_file.parent.mkdir()
    task_file.write_text("S1. inspect\nS2. implement\n", encoding="utf-8")
    env.update(
        {
            "FA_AUTO_RUN": "1",
            "FA_TASK_FILE": "tasks/plan.md",
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=SUCCESS", proc)
    finally:
        _terminate(proc)

    assert "task_source=file:" in text
    assert "task_sha256=" in text
    assert "S1. inspect" in text
    assert calls.exists()


def test_entrypoint_task_file_must_stay_inside_workspace(tmp_path: Path) -> None:
    env, status, bin_dir = _base_env(tmp_path)
    calls = _write_fa_stub(bin_dir)
    outside = tmp_path / "outside-task.md"
    outside.write_text("do work\n", encoding="utf-8")
    env.update(
        {
            "FA_AUTO_RUN": "1",
            "FA_TASK_FILE": str(outside),
            "FA_STUB_CALLS": str(calls),
        }
    )

    proc = subprocess.Popen(["bash", str(_ENTRYPOINT)], env=env, text=True)
    try:
        text = _wait_for_status(status, "status=INVALID_CONFIG", proc)
    finally:
        _terminate(proc)

    assert "inside workspace" in text
    assert not calls.exists()
