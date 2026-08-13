#!/usr/bin/env python3
"""Host development compatibility adapter for workspace readiness."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path

JUST_PACKAGE = "rust-just==1.57.0"
JUST_VERSION = "1.57.0"
_VERSION_TIMEOUT_SECONDS = 30
_TOOL_INSTALL_TIMEOUT_SECONDS = 900
_UPDATE_SHELL_TIMEOUT_SECONDS = 120
_READINESS_TIMEOUT_SECONDS = 2000


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run(
    command: list[str],
    *,
    cwd: Path,
    timeout: int,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("+", shlex.join(command), flush=True)
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=capture_output,
        text=True,
        timeout=timeout,
    )


def _just_is_current(just: str | None, root: Path) -> bool:
    if just is None:
        return False
    result = _run([just, "--version"], cwd=root, timeout=_VERSION_TIMEOUT_SECONDS, capture_output=True)
    return result.returncode == 0 and result.stdout.strip() == f"just {JUST_VERSION}"


def _prepare_just(uv: str, root: Path) -> int:
    try:
        if _just_is_current(shutil.which("just"), root):
            return 0
        installed = _run(
            [uv, "tool", "install", "--force", JUST_PACKAGE],
            cwd=root,
            timeout=_TOOL_INSTALL_TIMEOUT_SECONDS,
        )
        if installed.returncode != 0:
            print(
                f"[WORKSPACE_BOOTSTRAP] failed to install {JUST_PACKAGE}; rc={installed.returncode}",
                file=sys.stderr,
            )
            return 75
        updated = _run(
            [uv, "tool", "update-shell"],
            cwd=root,
            timeout=_UPDATE_SHELL_TIMEOUT_SECONDS,
        )
        if updated.returncode != 0:
            print(
                f"[WORKSPACE_BOOTSTRAP] uv tool update-shell returned {updated.returncode}; continuing",
                file=sys.stderr,
            )
        return 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[WORKSPACE_BOOTSTRAP] host tool setup failed: {exc}", file=sys.stderr)
        return 75


def _run_readiness(root: Path) -> int:
    command = [
        sys.executable,
        str(root / "scripts" / "bootstrap" / "workspace.py"),
        "ensure",
        "--workspace",
        str(root),
    ]
    try:
        return _run(command, cwd=root, timeout=_READINESS_TIMEOUT_SECONDS).returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[WORKSPACE_BOOTSTRAP] readiness wrapper failed to start or finish: {exc}", file=sys.stderr)
        return 70


def main() -> int:
    root = _repo_root()
    uv = shutil.which("uv")
    if uv is None:
        print(
            "ERROR: uv is required for host bootstrap. Install uv once, then rerun just agent-bootstrap.",
            file=sys.stderr,
        )
        return 2
    tool_rc = _prepare_just(uv, root)
    if tool_rc != 0:
        return tool_rc
    readiness_rc = _run_readiness(root)
    if readiness_rc != 0:
        return readiness_rc
    print("FA_AGENT_READY=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
