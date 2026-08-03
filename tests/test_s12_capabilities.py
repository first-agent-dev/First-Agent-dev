"""C1 (S12.2) — the capability probes report the capability they name.

Two obligations, and the second is the one that matters.

**Positive:** every probe is ``True`` on this POSIX host. If one is ``False``
here, the probe is wrong — not the host — and it would silently skip live tests
on Linux and in CI. That is plan contract **CT2**, the slice's primary negative
proof: markers must never fire on Linux.

**Negative (kill-check):** each probe returns ``False`` when its underlying
capability is removed. A probe that cannot report absence is not a probe; it is
a constant that happens to be ``True``, and it would leave the Windows gate red
while looking healthy. Board lesson: *a check that cannot fail is not a check.*

The probes are ``functools.cache``d, so every negative test clears the cache
first and restores it afterwards — otherwise the first call in the session
fixes the answer for all later ones and these tests pass vacuously.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pexpect  # type: ignore[import-untyped]
import pytest

from tests import _capabilities as cap
from tests._capabilities import requires_posix_paths

_PROBES: tuple[tuple[str, Callable[[], bool]], ...] = (
    ("has_posix_shell", cap.has_posix_shell),
    ("has_posix_modes", cap.has_posix_modes),
    ("has_posix_paths", cap.has_posix_paths),
    ("has_symlinks", cap.has_symlinks),
    ("has_pty_backend", cap.has_pty_backend),
    ("has_stable_tmpdir", cap.has_stable_tmpdir),
)


@pytest.fixture(autouse=True)
def _clear_probe_caches() -> Iterator[None]:
    """Drop every probe's cache around each test.

    Without this a negative test would be scored against a value computed
    before the monkeypatch landed, and would pass no matter what the probe did.
    """
    for _, probe in _PROBES:
        cache_clear = getattr(probe, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()
    yield
    for _, probe in _PROBES:
        cache_clear = getattr(probe, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()


# --- Positive: this host is POSIX and every probe must say so ---------------


@requires_posix_paths
@pytest.mark.parametrize(("name", "probe"), _PROBES, ids=[n for n, _ in _PROBES])
def test_every_probe_is_true_on_this_posix_host(name: str, probe: Callable[[], bool]) -> None:
    """CT2: no marker may fire on a POSIX host.

    A ``False`` here means the corresponding ``requires_*`` marker would skip
    its tests in CI, silently deleting coverage. ``has_pty_backend`` is the
    cautionary case: an earlier draft probed ``shutil.which("tmux")``, which is
    absent on the Linux sandbox even though all 13 PTY tests pass via the
    ``pexpect`` fallback. That version would have skipped 26 live tests.

    **Gated on ``requires_posix_paths``** (S12 review finding RS4). Without the
    gate this test asserts "every capability is present" *unconditionally*, so
    on Windows — where five of six are legitimately absent — it fails six times
    and reports the platform difference as a defect. That is the same
    "a gate that fails when the thing it guards is healthy" error this whole
    slice exists to remove, reintroduced inside the slice's own test file.

    ``requires_posix_paths`` is the right discriminator because ``os.sep == "/"``
    is true on every host where the other five are expected to hold (Linux,
    macOS, WSL, the container) and false exactly on native Windows.
    """
    assert probe() is True, (
        f"{name}() is False on a POSIX host — the probe is wrong, not the host. "
        f"Shipping it would skip its tests in CI and delete coverage (CT2)."
    )


@requires_posix_paths
def test_all_marker_constants_are_present_and_do_not_skip_here() -> None:
    """The exported markers exist and are inactive on a POSIX host.

    Gated for the same reason as the probe sweep above: on Windows these
    markers are *supposed* to be active.
    """
    markers = {
        "requires_posix_shell": cap.requires_posix_shell,
        "requires_posix_modes": cap.requires_posix_modes,
        "requires_posix_paths": cap.requires_posix_paths,
        "requires_symlinks": cap.requires_symlinks,
        "requires_pty_backend": cap.requires_pty_backend,
        "requires_stable_tmpdir": cap.requires_stable_tmpdir,
    }
    for name, marker in markers.items():
        assert marker.args[0] is False, f"{name} would skip on this POSIX host"


def test_marker_constants_exist_on_every_platform() -> None:
    """All six markers are importable and well-formed regardless of host.

    Replaces the coverage the gate above gives up on Windows: the *existence*
    and *shape* of every marker is platform-independent, so that much must
    still be checked there. Only the "is it inactive" claim is POSIX-specific.
    """
    for name in (
        "requires_posix_shell",
        "requires_posix_modes",
        "requires_posix_paths",
        "requires_symlinks",
        "requires_pty_backend",
        "requires_stable_tmpdir",
    ):
        marker = getattr(cap, name)
        assert isinstance(marker.args[0], bool), f"{name} condition must be a bool"
        assert marker.kwargs.get("reason"), f"{name} must carry a reason"


def test_every_reason_names_a_capability_not_a_platform() -> None:
    """CT3 in miniature: reasons must be actionable.

    ``pytest -rs`` output is the operator's only signal about what is not being
    verified locally, so "windows" is not an acceptable reason.
    """
    reasons = [
        cap.posix_shell_reason,
        cap.posix_modes_reason,
        cap.posix_paths_reason,
        cap.symlinks_reason,
        cap.pty_backend_reason,
        cap.stable_tmpdir_reason,
    ]
    for reason in reasons:
        assert reason.startswith("needs "), f"reason must state a requirement: {reason!r}"
        lowered = reason.lower()
        assert "win32" not in lowered
        assert not lowered.startswith("windows")


# --- Negative: each probe reports absence (the kill-checks) -----------------


def test_posix_shell_false_when_bash_is_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert cap.has_posix_shell() is False


def test_posix_shell_false_under_msys_path_translation(monkeypatch: pytest.MonkeyPatch) -> None:
    """The defect this slice exists for.

    Git Bash *is* installed, so ``shutil.which`` succeeds and the old
    ``which("bash") is None`` guard passes — then the shell answers ``/c/...``
    for a ``C:\\...`` request and the test fails on a string compare. The probe
    must catch that where the old guard could not.
    """
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/bash")

    def _msys_pwd(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["bash"], returncode=0, stdout="/c/Users/x\n", stderr="")

    monkeypatch.setattr(subprocess, "run", _msys_pwd)
    assert cap.has_posix_shell() is False


def test_posix_shell_false_when_shell_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/bash")

    def _broken(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["bash"], returncode=127, stdout="", stderr="boom")

    monkeypatch.setattr(subprocess, "run", _broken)
    assert cap.has_posix_shell() is False


def test_posix_modes_false_when_chmod_does_not_stick(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates NTFS: ``chmod`` is accepted and ignored."""
    monkeypatch.setattr(os, "chmod", lambda *_a, **_k: None)
    assert cap.has_posix_modes() is False


def test_posix_paths_false_when_separator_is_backslash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(os, "sep", "\\")
    assert cap.has_posix_paths() is False


def test_symlinks_false_when_symlink_is_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows without Developer Mode raises ``OSError`` here."""

    def _denied(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(1314, "A required privilege is not held by the client")

    monkeypatch.setattr(os, "symlink", _denied)
    assert cap.has_symlinks() is False


def test_pty_backend_false_without_tmux_and_without_pexpect_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """The operator's exact Windows condition.

    ``tmux`` has no Windows build and ``pexpect`` imports but exposes no
    ``spawn``, which the log shows verbatim as
    ``pexpect fallback failed: module 'pexpect' has no attribute 'spawn'``.
    """
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.delattr(pexpect, "spawn", raising=False)
    assert cap.has_pty_backend() is False


def test_pty_backend_true_from_tmux_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """tmux present is sufficient even if pexpect cannot spawn."""
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/tmux" if name == "tmux" else None)
    monkeypatch.delattr(pexpect, "spawn", raising=False)
    assert cap.has_pty_backend() is True


def test_stable_tmpdir_false_for_8_3_short_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tempfile, "gettempdir", lambda: r"C:\Users\836D~1\AppData\Local\Temp")
    assert cap.has_stable_tmpdir() is False


# --- A raising probe must not break collection (plan K7) --------------------


def test_probe_returns_false_instead_of_propagating(monkeypatch: pytest.MonkeyPatch) -> None:
    """K7: probes run at import time, so an escaping exception aborts the suite.

    Degrading to ``False`` ("don't run") is always safe; raising is not.
    """

    def _explode(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("disk on fire")

    monkeypatch.setattr(Path, "write_text", _explode)
    assert cap.has_posix_modes() is False


def test_unexpected_exception_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The converse: ``_PROBE_ERRORS`` is a named tuple, not a blanket catch.

    A probe that swallowed *everything* could hide a real bug in itself and
    report a capability as absent forever. ``KeyboardInterrupt`` must escape.
    """

    def _interrupt(*_args: Any, **_kwargs: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(Path, "write_text", _interrupt)
    with pytest.raises(KeyboardInterrupt):
        cap.has_posix_modes()
