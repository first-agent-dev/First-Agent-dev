"""Host capability probes for cross-platform test gating (S12).

Why this module exists
----------------------
The suite is written for the POSIX host FA actually ships on (a Linux
container). Run natively on Windows, ~85 tests fail — not because the product
is broken, but because the *tests* assume POSIX semantics.

The pre-existing guard for this was::

    @pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")

That asks **"is bash installed?"** when it means **"can bash here speak this
host's path dialect?"**. Git Bash satisfies the former and fails the latter: it
answers ``pwd`` with ``/c/Users/...`` while Python asked about
``C:\\Users\\...``. The guard passes, the test runs, and it fails on a string
comparison. A machine with *no* bash would have skipped cleanly — so the box is
punished for being more capable.

Every probe below therefore tests an **effect**, never a precondition, and
never ``sys.platform``. A ``sys.platform == "win32"`` check would also skip on
WSL (where these tests pass) and would keep skipping forever after the
underlying issue was fixed.

Design constraints (plan S12 §3)
--------------------------------
* **Cached** — ``functools.cache``; at most one subprocess per session.
* **Never raise** — the ``skipif`` constants are evaluated at import time, i.e.
  during collection. A probe that propagated an exception would abort the whole
  suite, which is worse than the problem it guards. Every probe degrades to
  ``False`` ("don't run"), which is always the safe direction.
* **No repo state** — probes touch only ``tempfile`` locations.

Usage::

    from tests._capabilities import requires_posix_shell

    @requires_posix_shell
    def test_something_that_compares_shell_output_to_a_host_path(): ...
"""

from __future__ import annotations

import functools
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

__all__ = [
    "posix_modes_reason",
    "posix_paths_reason",
    "posix_shell_reason",
    "pty_backend_reason",
    "python3_executable_reason",
    "requires_posix_modes",
    "requires_posix_paths",
    "requires_posix_shell",
    "requires_pty_backend",
    "requires_python3_executable",
    "requires_stable_tmpdir",
    "requires_symlink_hook_installs",
    "requires_symlinks",
    "stable_tmpdir_reason",
    "symlink_hook_installs_reason",
    "symlinks_reason",
]

# Probe timeout. Generous enough for a cold shell start on a loaded CI box,
# short enough that a hung shell cannot stall collection indefinitely.
_PROBE_TIMEOUT_S = 30

# Every failure a probe may legitimately hit, enumerated rather than caught as
# a blind `except Exception`. Each entry is reachable:
#
#   OSError               — chmod/symlink/stat denied; PermissionError and
#                           NotADirectoryError are subclasses. On Windows
#                           os.symlink raises this without Developer Mode.
#   NotImplementedError   — os.symlink on platforms lacking the syscall.
#   AttributeError        — os.symlink is absent entirely on some builds.
#   ValueError            — embedded NUL / illegal characters in a temp path.
#   subprocess.SubprocessError
#                         — TimeoutExpired (hung shell) and friends.
#
# Anything outside this set is a bug in the probe itself and must surface
# loudly rather than silently disable a marker.
_PROBE_ERRORS = (
    OSError,
    NotImplementedError,
    AttributeError,
    ValueError,
    subprocess.SubprocessError,
)


@functools.cache
def has_posix_shell() -> bool:
    """True when a ``bash`` exists **and** agrees with this host's path syntax.

    The dialect check is the entire point. ``shutil.which("bash")`` is not
    sufficient: MSYS/Git Bash on Windows resolves a native ``C:\\Users\\x``
    working directory and reports it as ``/c/Users/x``. Tests that compare
    shell output against a :class:`pathlib.Path` then fail on a host that does
    have a usable shell for *other* purposes.

    Comparing via ``Path`` rather than string equality keeps the probe honest
    about separators and trailing slashes on the POSIX side.
    """
    try:
        bash = shutil.which("bash")
        if bash is None:
            return False
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [bash, "-c", "pwd"],
                capture_output=True,
                text=True,
                timeout=_PROBE_TIMEOUT_S,
                check=False,
                cwd=tmp,
            )
            if completed.returncode != 0:
                return False
            reported = completed.stdout.strip()
            if not reported:
                return False
            # os.path.realpath resolves the /tmp -> /private/tmp style symlinks
            # that macOS inserts, so a POSIX host is not failed for that alone.
            return Path(reported) == Path(os.path.realpath(tmp))
    except _PROBE_ERRORS:
        return False


@functools.cache
def has_posix_modes() -> bool:
    """True when ``chmod`` actually changes the stored permission bits.

    NTFS accepts :func:`os.chmod` and silently ignores most of it: a file
    created on Windows reports ``0o666`` and a directory ``0o777`` regardless.
    Probing with ``os.access(path, os.X_OK)`` would be wrong for the same
    reason — it answers from the ACL, not from ``st_mode``. Only a
    write-``chmod``-``stat`` round-trip proves the bits survive.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "mode_probe"
            probe.write_text("x", encoding="utf-8")
            os.chmod(probe, 0o600)
            return stat.S_IMODE(probe.stat().st_mode) == 0o600
    except _PROBE_ERRORS:
        return False


@functools.cache
def has_posix_paths() -> bool:
    """True when the path separator is ``/``.

    Guards tests that compare against ``"/"``-joined string literals, or that
    rely on :attr:`pathlib.PurePath.parts` yielding ``"/"`` for the root — on
    Windows it yields ``"\\\\"``, which silently changes lexical path
    normalisation.
    """
    return os.sep == "/"


@functools.cache
def has_symlinks() -> bool:
    """True when this process may create a symlink.

    On Windows this needs Developer Mode or elevation, so it is a *runtime*
    capability of the current process, not a property of the platform: the same
    box answers differently depending on how the shell was launched. Probed by
    attempting one.
    """
    try:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.write_text("x", encoding="utf-8")
            link = Path(tmp) / "link"
            os.symlink(target, link)
            return link.is_symlink()
    except _PROBE_ERRORS:
        return False


@functools.cache
def installs_hooks_as_symlinks() -> bool:
    """True when ``fa.hygiene.hooks.install`` links rather than copies.

    Distinct from :func:`has_symlinks`, and the distinction is load-bearing.
    ``install.py:63`` forces ``shutil.copy2`` on ``win32`` **unconditionally** —
    Git for Windows does not reliably execute a symlinked hook — so on Windows
    an installed hook is always a real file even when the OS *can* create
    symlinks (Developer Mode on).

    Consequence: ``_install_one`` raises ``FileExistsError`` on a second install
    because its idempotency path is ``target.is_symlink()``, which is false for
    a copy. Tests asserting symlink-replacement semantics therefore need *this*
    capability, not merely "symlinks work here". Gating them on
    :func:`has_symlinks` mislabels a real platform behaviour difference as an
    OS permission issue (S12 review finding RS5 → BACKLOG I-45).
    """
    try:
        return sys.platform != "win32" and has_symlinks()
    except _PROBE_ERRORS:
        return False


@functools.cache
def has_pty_backend() -> bool:
    """True when ``PtyPool`` can obtain a working PTY.

    **Not** ``shutil.which("tmux")``. Measured on the Linux sandbox: ``tmux`` is
    absent there, yet all 13 ``test_pty_persistence`` tests pass, because
    :class:`~fa.runtime.pty_pool.PtyPool` degrades to ``pexpect``
    (``pty_pool.py:125``). Gating on tmux would have skipped 26 tests that
    currently pass on Linux and in CI — deleting live coverage, exactly the
    failure this slice exists to prevent (plan CT2/K6).

    The capability is therefore "tmux **or** a usable ``pexpect.spawn``".
    ``pexpect`` imports on Windows but exposes no ``spawn`` (it is POSIX-only),
    which is precisely what the operator's log shows::

        pexpect fallback failed: module 'pexpect' has no attribute 'spawn'
    """
    try:
        if shutil.which("tmux") is not None:
            return True
        import pexpect  # type: ignore[import-untyped]

        return hasattr(pexpect, "spawn")
    except ImportError:
        return False
    except _PROBE_ERRORS:
        return False


@functools.cache
def has_python3_executable() -> bool:
    """True when a command named ``python3`` actually runs Python.

    Windows ships an **App Execution Alias** at ``python3.exe`` that is not
    Python: invoking it prints *"Python was not found; run without arguments to
    install from the Microsoft Store"* and exits ``9009``. ``shutil.which`` finds
    it, so a presence check is not enough — the operator's log shows exactly
    this text captured as a subagent's stdout (S12 review finding RS6).

    Probed by running it and requiring the interpreter to answer.
    """
    try:
        python3 = shutil.which("python3")
        if python3 is None:
            return False
        completed = subprocess.run(
            [python3, "-c", "print('ok')"],
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT_S,
            check=False,
        )
        return completed.returncode == 0 and completed.stdout.strip() == "ok"
    except _PROBE_ERRORS:
        return False


@functools.cache
def has_stable_tmpdir() -> bool:
    """True when the temp directory is not an 8.3 short path.

    Windows hands out ``C:\\Users\\836D~1\\AppData\\Local\\Temp`` for a
    username too long or non-ASCII for the legacy 8.3 form. Code that resolves
    the long form and compares it against ``tempfile.gettempdir()`` then sees
    two different strings for one directory.
    """
    try:
        return "~" not in str(Path(tempfile.gettempdir()))
    except _PROBE_ERRORS:
        return False


# --- Reason strings -------------------------------------------------------
# Exported so tests can assert on them and so `pytest -rs` output names the
# missing capability rather than a platform. "windows" is never a reason: the
# operator must be able to read the skip list and know exactly what is not
# being verified locally.

posix_shell_reason = "needs a POSIX shell whose paths match the host (Git Bash reports /c/... for C:\\...)"
posix_modes_reason = "needs POSIX permission bits that survive chmod (NTFS reports 0o666/0o777)"
posix_paths_reason = "needs POSIX path semantics (os.sep == '/')"
symlinks_reason = "needs symlink creation (Windows requires Developer Mode or elevation)"
symlink_hook_installs_reason = (
    "needs hook installs to use symlinks; install.py forces copy on win32 so the "
    "symlink-replacement path is unreachable there"
)
pty_backend_reason = "needs a PTY backend: tmux, or pexpect.spawn (POSIX-only) as fallback"
python3_executable_reason = (
    "needs a real python3 on PATH; Windows ships an App Execution Alias that "
    "prints a Microsoft Store notice and exits 9009"
)
stable_tmpdir_reason = "needs a temp dir that is not an 8.3 short path (C:\\Users\\836D~1\\...)"

# --- Marker constants -----------------------------------------------------
# Module-level constants rather than custom marks: `--strict-markers` is on and
# `pyproject.toml` has no `markers` list, so a custom mark would need config
# and would fail obscurely if misspelled. A constant is plain Python, caught by
# mypy, and matches the existing house style
# (tests/test_deploy_scripts.py:177 uses the same pattern).

requires_posix_shell = pytest.mark.skipif(not has_posix_shell(), reason=posix_shell_reason)
requires_posix_modes = pytest.mark.skipif(not has_posix_modes(), reason=posix_modes_reason)
requires_posix_paths = pytest.mark.skipif(not has_posix_paths(), reason=posix_paths_reason)
requires_symlinks = pytest.mark.skipif(not has_symlinks(), reason=symlinks_reason)
requires_symlink_hook_installs = pytest.mark.skipif(
    not installs_hooks_as_symlinks(), reason=symlink_hook_installs_reason
)
requires_pty_backend = pytest.mark.skipif(not has_pty_backend(), reason=pty_backend_reason)
requires_stable_tmpdir = pytest.mark.skipif(not has_stable_tmpdir(), reason=stable_tmpdir_reason)
requires_python3_executable = pytest.mark.skipif(not has_python3_executable(), reason=python3_executable_reason)
