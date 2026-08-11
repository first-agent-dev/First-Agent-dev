"""Cross-platform host development bootstrap for VS Code and terminal use."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

JUST_PACKAGE = "rust-just==1.57.0"
MARKER_PATH = Path(".fa") / "host-bootstrap.json"


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(command), flush=True)
    # Command is assembled from repository constants and the resolved uv path.
    return subprocess.run(command, check=check, text=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    digest.update(f"python={sys.version_info.major}.{sys.version_info.minor}".encode())
    digest.update(f"platform={sys.platform}".encode())
    for name in ("pyproject.toml", "uv.lock"):
        path = root / name
        digest.update(name.encode())
        digest.update(path.read_bytes())
    digest.update(JUST_PACKAGE.encode())
    return digest.hexdigest()


def _ready_marker(root: Path, fingerprint: str) -> dict[str, Any]:
    return {
        "schema": 1,
        "ready": True,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": sys.platform,
        "just_package": JUST_PACKAGE,
        "fingerprint": fingerprint,
    }


def _marker_matches(root: Path, fingerprint: str) -> bool:
    marker = root / MARKER_PATH
    if not marker.is_file() or not (root / ".venv").is_dir():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("ready") is True and data.get("fingerprint") == fingerprint


def _write_marker(root: Path, data: dict[str, Any]) -> None:
    marker = root / MARKER_PATH
    marker.parent.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(marker)


def main() -> int:
    root = _repo_root()
    os.chdir(root)
    uv = shutil.which("uv")
    if uv is None:
        print(
            "ERROR: uv is required for host bootstrap. Install uv once, then reopen VS Code.",
            file=sys.stderr,
        )
        return 2

    fingerprint = _fingerprint(root)
    if _marker_matches(root, fingerprint):
        status = _run([uv, "run", "python", "-m", "fa.hygiene.hooks.status"], check=False)
        if status.returncode == 0:
            print("FA_AGENT_READY=1")
            return 0

    _run([uv, "tool", "install", "--force", JUST_PACKAGE])
    # This updates the user's shell startup file where supported. The VS Code
    # task itself uses uvx, so readiness does not depend on the current shell
    # inheriting the updated PATH.
    _run([uv, "tool", "update-shell"], check=False)
    _run([uv, "sync", "--frozen", "--extra", "dev"])
    _run([uv, "run", "python", "-m", "fa.hygiene.hooks.install", "--force"])
    _run([uv, "run", "python", "-m", "fa.hygiene.hooks.status"])
    _write_marker(root, _ready_marker(root, fingerprint))
    print("FA_AGENT_READY=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
