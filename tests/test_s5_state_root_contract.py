"""S5.4.5 — one resolver decides where FA state lives (Q17).

Defect this closes (source-verified, measured)
----------------------------------------------
``scripts/fa-entrypoint.sh:214`` defines
``state_root="${FA_STATE_ROOT:-${HOME}/.fa}"`` and passes it to
``python -m fa.session.manager provision --state-root``. **No Python code read
``FA_STATE_ROOT``** — a repo-wide grep found 15 independent
``Path.home() / ".fa"`` derivations and zero readers of the variable.

Measured consequence: with ``FA_STATE_ROOT=/tmp/x`` the entrypoint provisions
``/tmp/x`` while ``cli.py:128`` computes ``~/.fa``. Provisioning and ``fa run``
then disagree about where the session authority lives — a split-brain session
where the run cannot see what was provisioned for it.

Contract
--------
``fa_state_root()`` is the single source of truth. Unset ``FA_STATE_ROOT``
yields ``~/.fa`` byte-identically to today (no migration for existing installs).
Set to an absolute path, it is honoured everywhere. A relative or empty value is
ignored in favour of the default rather than silently producing a CWD-relative
state tree — the XDG convention, and the safer failure since a state root that
moves with the working directory is a data-loss hazard.

Test classes: C0 (resolver semantics), C2 (CLI/env contract end to end).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from fa.paths import fa_state_root
from tests._capabilities import requires_posix_paths, requires_posix_shell

# ---------------------------------------------------------------------------
# C0 — resolver semantics
# ---------------------------------------------------------------------------


@requires_posix_paths
def test_defaults_to_home_dot_fa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """C0: unset behaviour is exactly today's behaviour."""
    monkeypatch.delenv("FA_STATE_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert fa_state_root() == tmp_path / ".fa"


def test_honours_absolute_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """C0: an absolute override wins over HOME."""
    override = tmp_path / "custom-state"
    # HOME first: the autouse fixture drops its FA_STATE_ROOT default as soon
    # as a test takes control of HOME, so the override must be set afterwards.
    monkeypatch.setenv("HOME", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("FA_STATE_ROOT", str(override))
    assert fa_state_root() == override


@requires_posix_paths
@pytest.mark.parametrize(
    "override",
    ["relative/state", ".", "..", "", "   "],
    ids=["relative-path", "dot", "dotdot", "empty", "whitespace"],
)
def test_ignores_non_absolute_override(tmp_path: Path, override: str) -> None:
    """C0: a non-absolute value must not produce a CWD-relative state tree.

    Honouring it would make the state root move with the working directory —
    the same class of hazard as the V10 import-time binding, and a quiet way to
    lose a session.

    Run in a subprocess with an explicit CWD *different* from HOME. In-process
    this could not be tested: the autouse isolation fixture drops
    ``FA_STATE_ROOT`` the moment a test sets ``HOME``, so the assertion would
    pass against the fixture rather than the resolver — verified by a
    kill-check (``return Path(override)``) that survived the in-process form.
    """
    home = tmp_path / "home"
    home.mkdir()
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()

    env = dict(os.environ)
    env["HOME"] = str(home)
    env["FA_STATE_ROOT"] = override
    result = subprocess.run(
        [sys.executable, "-c", "from fa.paths import fa_state_root; print(fa_state_root())"],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=60,
        check=True,
    ).stdout.strip()

    assert result == str(home / ".fa"), (
        f"FA_STATE_ROOT={override!r} was honoured; a non-absolute state root "
        "follows the working directory and silently loses sessions"
    )


def test_resolution_is_call_time_not_import_time(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """C0: the V10 class must not reappear.

    A module-level constant bound at import silently ignores later changes to
    the environment. This resolver must re-read on every call.
    """
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "first"))
    assert fa_state_root() == tmp_path / "first"
    monkeypatch.setenv("FA_STATE_ROOT", str(tmp_path / "second"))
    assert fa_state_root() == tmp_path / "second", "resolver cached its answer across calls"


# ---------------------------------------------------------------------------
# C2 — the end-to-end agreement the defect broke
# ---------------------------------------------------------------------------


def _run_cli_state_root(env_override: str | None, home: Path) -> str:
    """Resolve the state root the way the CLI does, in a fresh interpreter.

    A subprocess is required, not stylistic: the defect was an *import-time*
    binding, which an in-process monkeypatch cannot detect once the module is
    already loaded.
    """
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop("FA_STATE_ROOT", None)
    if env_override is not None:
        env["FA_STATE_ROOT"] = env_override
    proc = subprocess.run(
        [sys.executable, "-c", "from fa.paths import fa_state_root; print(fa_state_root())"],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=True,
    )
    return proc.stdout.strip()


@requires_posix_shell
def test_entrypoint_and_cli_agree_on_state_root(tmp_path: Path) -> None:
    """C2 (S5-P23): the entrypoint's shell expression and Python must match.

    Recomputes the entrypoint's own expression
    (``state_root="${FA_STATE_ROOT:-${HOME}/.fa}"``) with the same environment
    and asserts Python lands on the same directory. This is the assertion whose
    absence allowed the split brain.
    """
    home = tmp_path / "home"
    home.mkdir()
    override = tmp_path / "shared-state"

    for env_override in (None, str(override)):
        env = dict(os.environ)
        env["HOME"] = str(home)
        env.pop("FA_STATE_ROOT", None)
        if env_override is not None:
            env["FA_STATE_ROOT"] = env_override
        shell = subprocess.run(
            ["bash", "-c", 'printf "%s" "${FA_STATE_ROOT:-${HOME}/.fa}"'],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=True,
        ).stdout.strip()

        python_side = _run_cli_state_root(env_override, home)
        assert python_side == shell, (
            f"entrypoint provisions {shell!r} but Python resolves {python_side!r} "
            f"(FA_STATE_ROOT={env_override!r}) — split-brain session"
        )


def test_entrypoint_expression_is_unchanged(tmp_path: Path) -> None:
    """C2: pin the entrypoint line the Python side is contracted against.

    If the shell contract moves, the agreement test above must be revisited
    rather than silently comparing against something new.
    """
    entrypoint = Path("scripts/fa-entrypoint.sh").read_text(encoding="utf-8")
    assert 'local state_root="${FA_STATE_ROOT:-${HOME}/.fa}"' in entrypoint


def test_state_root_env_override_reaches_session_manager(tmp_path: Path) -> None:
    """C2 (S5-P23): production consumers derive from the resolver.

    Kill-check target: revert ``cli.py:128`` to ``Path.home() / ".fa"`` and this
    fails, because the CLI would resolve the default while the operator asked
    for an override.
    """
    home = tmp_path / "home"
    home.mkdir()
    override = tmp_path / "explicit-state"

    env = dict(os.environ)
    env["HOME"] = str(home)
    env["FA_STATE_ROOT"] = str(override)

    # Assert on the SessionManager the CLI actually builds (cli.py:128), not on
    # the resolver in isolation: an earlier version of this test called
    # fa_state_root() directly and therefore survived the plan's own named
    # kill-check (reverting cli.py:128 to Path.home()).
    probe = (
        "import argparse\n"
        "from fa.cli import _session_manager_for_args\n"
        "mgr = _session_manager_for_args(argparse.Namespace())\n"
        "print(mgr.state_root)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        check=True,
    )
    assert proc.stdout.strip() == str(override), (
        f"SessionManager provisioned {proc.stdout.strip()!r} but the operator "
        f"asked for {str(override)!r} — provisioning and `fa run` disagree"
    )


def test_session_log_root_follows_state_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """C2: the session-log root is derived, not independently recomputed.

    ``default_state_root()`` was fixed in S5.3 for the V10 leak but still went
    straight to ``Path.home()``; it must now sit under the one resolver so an
    override moves the whole tree together.
    """
    from fa.inner_loop.state import default_state_root

    override = tmp_path / "state"
    monkeypatch.setenv("FA_STATE_ROOT", str(override))
    assert default_state_root() == override / "session-log"
