"""Kernel topology experiment, NOT a production Docker or STEP9A custody witness.

A child mount namespace and a capability-free process model the relevant mount
layout. The process still has access to the host filesystem, unlike the real
container, so these tests establish only the named path-topology properties.
"""

from __future__ import annotations

import errno
import json
import os
import select
import shutil
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from fa.execution.view_io import RootedViewIO

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
elif kind in {"selective", "anchored"}:
    ledger = project / "ledger.md"
    with ledger.open("a") as stream:
        stream.write("shell append\n")
    (project / "notes" / "new.md").write_text("old note")
    (project / "notes" / "replacement.tmp").write_text("note")
    os.replace(project / "notes" / "replacement.tmp", project / "notes" / "new.md")
    (project / "e2e" / "new.md").write_text("e2e")
    attempt("ledger_tempfile", lambda: (project / "ledger.tmp").write_text("replacement"))
    attempt("write_accepted", lambda: accepted.write_text("forged"))
    attempt("rename_project", lambda: project.rename(worklogs / "moved"))
    if kind == "anchored":
        attempt("rename_worklogs", lambda: worklogs.rename(w / "moved"))
        attempt("rename_acceptance", lambda: (project / "acceptance").rename(project / "moved"))
        attempt("link_accepted", lambda: os.link(accepted, project / "linked.py"))
        attempt("write_plan", lambda: (project / "increments/plan.md").write_text("forged"))
        attempt("rename_increments", lambda: (project / "increments").rename(project / "other"))
        attempt("write_roadmap", lambda: (project / "roadmap.md").write_text("forged"))
        attempt("rename_roadmap", lambda: (project / "roadmap.md").rename(project / "moved.md"))
        attempt("outside_scope", lambda: (project / "other.md").write_text("outside scope"))
        attempt("write_questions", lambda: (project / "open-questions.md").write_text("changed"))
    # The parent outside this namespace runs the real rooted atomic writer.
    print("ready", flush=True)
    if sys.stdin.readline().strip() != "continue":
        raise RuntimeError("parent did not complete replacement")
    result.update(visible=accepted.read_text(), shell_ledger=ledger.read_text())
    if kind == "anchored":
        (project / "ledger.tmp").write_text("shell replacement\n")
        attempt("shell_atomic_replace", lambda: os.replace(project / "ledger.tmp", ledger))
    else:
        attempt("shell_atomic_replace", lambda: os.replace(project / "notes" / "new.md", ledger))
    def append_again():
        with ledger.open("a") as stream:
            stream.write("second append\n")
    attempt("second_append", append_again)
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
if kind in {"selective", "anchored"}:
    (source / "worklogs/demo/notes").mkdir()
    (source / "worklogs/demo/e2e").mkdir()
    (source / "worklogs/demo/ledger.md").write_text("initial\n")
if kind == "anchored":
    (source / "worklogs/demo/increments").mkdir()
    (source / "worklogs/demo/increments/plan.md").write_text("plan")
    (source / "worklogs/demo/roadmap.md").write_text("roadmap")
    (source / "worklogs/demo/open-questions.md").write_text("questions")
subprocess.run(["mount", "--make-rprivate", "/"], check=True)
subprocess.run(["mount", "--bind", str(source), str(workspace)], check=True)
relative = "worklogs" if kind in {"top", "selective", "anchored"} else "worklogs/demo/acceptance"
target = workspace / relative
subprocess.run(["mount", "--bind", str(source / relative), str(target)], check=True)
subprocess.run(["mount", "-o", "remount,bind,ro", str(target)], check=True)
if kind == "selective":
    for name in ("notes", "e2e", "ledger.md"):
        relative = f"worklogs/demo/{name}"
        subprocess.run(["mount", "--bind", str(source / relative), str(workspace / relative)], check=True)
if kind == "anchored":
    relative = "worklogs/demo"
    subprocess.run(["mount", "--bind", str(source / relative), str(workspace / relative)], check=True)
    for name in ("acceptance", "increments", "roadmap.md"):
        relative = f"worklogs/demo/{name}"
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
    command = ["unshare", "-Urnm", sys.executable, "-c", _SETUP, str(tmp_path), kind, sys.executable]
    env = {**os.environ, "FA_MOUNT_ATTACK": _ATTACK}
    if kind in {"selective", "anchored"}:
        if os.getuid() == 0 or os.getgid() == 0:
            pytest.skip("RootedViewIO requires non-root view uid and gid")
        with subprocess.Popen(
            command,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        ) as run:
            try:
                assert run.stdin is not None and run.stdout is not None
                ready, _, _ = select.select([run.stdout], [], [], 20)
                if not ready:
                    raise AssertionError("selective topology did not reach the authority replacement")
                assert run.stdout.readline() == b"ready\n"
                root = tmp_path / "source"
                source = root / "worklogs" / "demo"
                staging = tmp_path / "authority-staging"
                staging.mkdir(mode=0o700)
                root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
                staging_fd = os.open(staging, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    with RootedViewIO(
                        root_fd,
                        staging_fd,
                        uid=os.getuid(),
                        gid=os.getgid(),
                        writable=True,
                        protected_paths=(),
                        excluded_paths=(),
                    ) as io:
                        before = io.read_file("worklogs/demo/ledger.md", offset_bytes=0, max_bytes=4096)
                        assert before["content"] == "initial\nshell append\n"
                        written = io.write_file(
                            "worklogs/demo/ledger.md", "file tool replacement\n", expected_sha256=before["sha256"]
                        )
                        assert written["bytes"] == len("file tool replacement\n")
                finally:
                    os.close(root_fd)
                    os.close(staging_fd)
                stdout, stderr = run.communicate(b"continue\n", timeout=20)
                assert run.returncode == 0, stderr.decode()
            finally:
                if run.poll() is None:
                    os.killpg(run.pid, signal.SIGKILL)
                    run.communicate()
        result = json.loads(stdout)
        result.update(
            authority_ledger=(source / "ledger.md").read_text(),
            authority_note=(source / "notes/new.md").read_text(),
            authority_e2e=(source / "e2e/new.md").read_text(),
        )
        if kind == "anchored":
            result["authority_questions"] = (source / "open-questions.md").read_text()
            result["authority_outside_scope"] = (source / "other.md").read_text()
    else:
        completed = subprocess.run(command, env=env, capture_output=True, text=True, check=False, timeout=20)
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
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


def test_anchored_writable_project_protects_mounts_but_exceeds_nested_scope(tmp_path: Path) -> None:
    result = _run_topology(tmp_path, "anchored")
    assert result == {
        "before": "original",
        "effective_caps": 0,
        "code": "changed",
        "ledger_tempfile": 0,
        "write_accepted": errno.EROFS,
        "rename_project": errno.EROFS,
        "rename_worklogs": errno.EBUSY,
        "rename_acceptance": errno.EBUSY,
        "link_accepted": errno.EXDEV,
        "write_plan": errno.EROFS,
        "rename_increments": errno.EBUSY,
        "write_roadmap": errno.EROFS,
        "rename_roadmap": errno.EBUSY,
        "outside_scope": 0,
        "write_questions": 0,
        "authority_questions": "changed",
        "authority_outside_scope": "outside scope",
        "visible": "original",
        "shell_ledger": "file tool replacement\n",
        "shell_atomic_replace": 0,
        "second_append": 0,
        "authority_ledger": "shell replacement\nsecond append\n",
        "authority_note": "note",
        "authority_e2e": "e2e",
    }


def test_selective_file_bind_after_external_atomic_replace(tmp_path: Path) -> None:
    result = _run_topology(tmp_path, "selective")
    assert result == {
        "before": "original",
        "effective_caps": 0,
        "code": "changed",
        "ledger_tempfile": errno.EROFS,
        "write_accepted": errno.EROFS,
        "rename_project": errno.EROFS,
        "visible": "original",
        "shell_ledger": "file tool replacement\n",
        "shell_atomic_replace": errno.EXDEV,
        "second_append": errno.EROFS,
        "authority_ledger": "file tool replacement\n",
        "authority_note": "note",
        "authority_e2e": "e2e",
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


_LANDLOCK = r"""
import ctypes, errno, json, os, sys
from pathlib import Path

libc = ctypes.CDLL(None, use_errno=True)
CREATE, ADD, RESTRICT = 444, 445, 446
WRITE, REMOVE, MAKE, REFER = 1 << 1, 1 << 5, 1 << 8, 1 << 13
handled = WRITE | REMOVE | MAKE | REFER
class Ruleset(ctypes.Structure):
    _fields_ = [("handled", ctypes.c_uint64)]
class PathRule(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed", ctypes.c_uint64), ("fd", ctypes.c_int32)]
def call(number, *args):
    value = libc.syscall(number, *args)
    if value < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    return value
project = Path(sys.argv[1]); mode = sys.argv[2]
attr = Ruleset(handled)
ruleset = call(CREATE, ctypes.byref(attr), ctypes.sizeof(attr), 0)
def allow(path, rights):
    fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
    try:
        rule = PathRule(rights, fd)
        call(ADD, ruleset, 1, ctypes.byref(rule), 0)
    finally:
        os.close(fd)
allow(project, REMOVE | MAKE | REFER | (WRITE if mode == "wide" else 0))
allow(project / "ledger.md", WRITE)
allow(project / "notes", handled)
if libc.prctl(38, 1, 0, 0, 0) != 0:
    error = ctypes.get_errno()
    raise OSError(error, os.strerror(error))
call(RESTRICT, ruleset, 0)
os.close(ruleset)
status = Path("/proc/self/status").read_text().splitlines()
cap_eff = next(line.split()[1] for line in status if line.startswith("CapEff:"))
results = {"effective_caps": int(cap_eff, 16)}
def attempt(name, action):
    try:
        action()
    except OSError as exc:
        results[name] = exc.errno
    else:
        results[name] = 0
attempt("ledger_append", lambda: (project / "ledger.md").open("a").write("append\n"))
attempt("project_temp", lambda: (project / "ledger.tmp").write_text("replacement\n"))
results["project_temp_exists"] = (project / "ledger.tmp").exists()
attempt("other_write", lambda: (project / "other.md").write_text("changed\n"))
(project / "notes" / "temp").write_text("replacement\n")
attempt("note_to_ledger", lambda: os.replace(project / "notes" / "temp", project / "ledger.md"))
attempt("ledger_append_after_replace", lambda: (project / "ledger.md").open("a").write("again\n"))
(project / "notes" / "other-temp").write_text("forged\n")
attempt("note_to_other", lambda: os.replace(project / "notes" / "other-temp", project / "other.md"))
results["ledger"] = (project / "ledger.md").read_text()
results["other"] = (project / "other.md").read_text()
print(json.dumps(results))
"""


@pytest.mark.parametrize("mode", ["narrow", "wide"])
def test_landlock_directory_rights_and_atomic_ledger_edit(tmp_path: Path, mode: str) -> None:
    import ctypes

    if shutil.which("setpriv") is None:
        pytest.skip("Landlock diagnostic requires setpriv")
    if os.uname().machine not in {"x86_64", "aarch64"}:
        pytest.skip("Landlock syscall numbers in this diagnostic are x86_64/aarch64 only")
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(444, 0, 0, 1)
    if abi < 2:
        pytest.skip(f"Landlock ABI 2 unavailable: {abi}, errno {ctypes.get_errno()}")
    project = tmp_path / mode
    (project / "notes").mkdir(parents=True)
    (project / "ledger.md").write_text("initial\n")
    (project / "other.md").write_text("other\n")
    run = subprocess.run(
        [
            "setpriv",
            "--bounding-set=-all",
            "--inh-caps=-all",
            "--ambient-caps=-all",
            "--no-new-privs",
            sys.executable,
            "-c",
            _LANDLOCK,
            str(project),
            mode,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result == {
        "effective_caps": 0,
        "ledger_append": 0,
        "project_temp": errno.EACCES if mode == "narrow" else 0,
        "project_temp_exists": True,
        "other_write": errno.EACCES if mode == "narrow" else 0,
        "note_to_ledger": 0,
        "ledger_append_after_replace": errno.EACCES if mode == "narrow" else 0,
        "note_to_other": 0,
        "ledger": "replacement\n" if mode == "narrow" else "replacement\nagain\n",
        "other": "forged\n",
    }
    assert (project / "ledger.md").read_text() == result["ledger"]
    assert (project / "other.md").read_text() == "forged\n"
