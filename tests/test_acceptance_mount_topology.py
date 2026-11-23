"""Kernel topology experiment, NOT a production Docker or STEP9A custody witness.

A child mount namespace and a capability-free process model the relevant mount
layout. The process still has access to the host filesystem, unlike the real
container, so these tests establish only the named path-topology properties.
"""

from __future__ import annotations

import errno
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ATTACK = r"""
import json, os, subprocess, sys
from pathlib import Path
w = Path(sys.argv[1]); kind = sys.argv[2]
worklogs = w / "worklogs"; project = worklogs / "demo"
accepted = project / "acceptance" / "test.py"
status = Path("/proc/self/status").read_text().splitlines()
cap_eff = next(line.split()[1] for line in status if line.startswith("CapEff:"))
result = {"before": accepted.read_text(), "effective_caps": int(cap_eff, 16)}
(w / "src" / "code.py").write_text("changed")
result["code"] = (w / "src" / "code.py").read_text()
def attempt(name, action):
    try:
        action()
    except OSError as exc:
        result[name] = exc.errno
    else:
        result[name] = 0
if kind == "nested":
    attempt("rename_project", lambda: project.rename(worklogs / "moved"))
    (project / "acceptance").mkdir(parents=True)
    accepted.write_text("forged")
    result["visible"] = accepted.read_text()
    result["original"] = (worklogs / "moved" / "acceptance" / "test.py").read_text()
else:
    attempt("write", lambda: accepted.write_text("forged"))
    attempt("unlink", accepted.unlink)
    attempt("rename_project", lambda: project.rename(worklogs / "moved"))
    attempt("rename_worklogs", lambda: worklogs.rename(w / "moved"))
    attempt("chmod", lambda: accepted.chmod(0o777))
    attempt("hardlink", lambda: os.link(accepted, w / "src" / "linked.py"))
    result["remount_rc"] = subprocess.run(["mount", "-o", "remount,rw", str(worklogs)], capture_output=True).returncode
    result["visible"] = accepted.read_text()
print(json.dumps(result))
"""

_SETUP = r"""
import os, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1]); kind = sys.argv[2]; python = sys.argv[3]
source = root / "source"; workspace = root / "workspace"
(source / "worklogs/demo/acceptance").mkdir(parents=True)
(source / "src").mkdir(); workspace.mkdir()
(source / "worklogs/demo/acceptance/test.py").write_text("original")
(source / "src/code.py").write_text("code")
subprocess.run(["mount", "--make-rprivate", "/"], check=True)
subprocess.run(["mount", "--bind", str(source), str(workspace)], check=True)
relative = "worklogs" if kind == "top" else "worklogs/demo/acceptance"
target = workspace / relative
subprocess.run(["mount", "--bind", str(source / relative), str(target)], check=True)
subprocess.run(["mount", "-o", "remount,bind,ro", str(target)], check=True)
subprocess.run(["setpriv", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs",
                python, "-c", os.environ["FA_MOUNT_ATTACK"], str(workspace), kind], check=True)
"""


def _run_topology(tmp_path: Path, kind: str) -> dict[str, object]:
    for executable in ("unshare", "mount", "setpriv"):
        if shutil.which(executable) is None:
            pytest.skip(f"kernel topology experiment requires {executable}")
    probe = subprocess.run(["unshare", "-Urnm", "true"], capture_output=True, text=True, check=False, timeout=10)
    if probe.returncode:
        pytest.skip(f"user/mount namespace unavailable: {probe.stderr.strip()}")
    run = subprocess.run(
        ["unshare", "-Urnm", sys.executable, "-c", _SETUP, str(tmp_path), kind, sys.executable],
        env={**os.environ, "FA_MOUNT_ATTACK": _ATTACK},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert isinstance(result, dict)
    return result


def test_nested_acceptance_bind_can_be_hidden_by_ancestor_rename(tmp_path: Path) -> None:
    result = _run_topology(tmp_path, "nested")
    assert result == {
        "before": "original",
        "effective_caps": 0,
        "code": "changed",
        "rename_project": 0,
        "visible": "forged",
        "original": "original",
    }


def test_top_level_readonly_bind_blocks_ancestor_and_file_changes(tmp_path: Path) -> None:
    result = _run_topology(tmp_path, "top")
    remount_rc = result.pop("remount_rc")
    assert isinstance(remount_rc, int) and remount_rc != 0
    assert result == {
        "before": "original",
        "effective_caps": 0,
        "code": "changed",
        "visible": "original",
        "write": errno.EROFS,
        "unlink": errno.EROFS,
        "rename_project": errno.EROFS,
        "rename_worklogs": errno.EBUSY,
        "chmod": errno.EROFS,
        "hardlink": errno.EXDEV,
    }
