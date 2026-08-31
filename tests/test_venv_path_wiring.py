"""S12.1 (CT1/GAP1): the readiness-provisioned workspace venv wins the PATH.

Live defect (2026-08-31 l2 row, RID cae-l2-1788164790-782783): the session
workspace had a working ``.venv/bin/pytest`` (bootstrap provisions it via
``uv sync --locked --extra dev``), but the agent's shell PATH was the
container runtime venv (``/opt/fa-venv/bin``, built ``--no-dev`` — no
pytest), so the model burned 12 of 20 turns on environment archaeology.

Contract (plan PLAN-s12-pre-live-reliability CT1): all THREE fs_run_bash
backends prepend ``<workspace>/.venv/bin`` to PATH iff it exists:

- tmux pane: clause appended to the init setup_cmd (pty_pool.py),
- pexpect fallback: PATH built into the child env dict (pty_pool.py),
- subprocess fallback: post-scrub prepend (tools/run_bash.py) — this one
  site covers the main-agent fallback AND subagents (executor=None).

Kill-checks: removing any prepend fails the corresponding test below;
the "absent venv" tests pin the other direction (raw clones unchanged).
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from fa.inner_loop.tools.run_bash import build_run_bash_tool
from fa.runtime.pty_pool import PtySession

# ── minimal fake tmux server (mirrors tests/test_pty_tmux_fake.py wire shape) ──


class _Pane:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.ready = ""

    def send_keys(self, command: str, **_: object) -> None:
        import re

        self.sent.append(command)
        ready = re.search(r"FA_READY_[^' ]+", command)
        if ready:
            self.ready = ready.group(0)

    def cmd(self, *_: str) -> SimpleNamespace:
        return SimpleNamespace(stdout=[self.ready])


class _TmuxSession:
    def __init__(self, pane: _Pane) -> None:
        self.active_window = SimpleNamespace(active_pane=pane)

    def kill(self) -> None:  # pragma: no cover - not exercised here
        pass


class _Server:
    socket_name = "fa_s12_test"

    def __init__(self) -> None:
        self.pane = _Pane()
        self.session = _TmuxSession(self.pane)

    def new_session(self, **_: object) -> _TmuxSession:
        return self.session

    def find_where(self, _: dict[str, str]) -> _TmuxSession:
        return self.session


def _make_workspace(tmp_path: Path, *, venv: bool) -> Path:
    if venv:
        (tmp_path / ".venv" / "bin").mkdir(parents=True)
    return tmp_path


# ── backend 1: tmux setup_cmd ────────────────────────────────────────────────


def test_tmux_setup_prepends_venv_when_present(tmp_path: Path) -> None:
    """Kill-check target: the setup_cmd clause in PtySession.__init__."""
    ws = _make_workspace(tmp_path, venv=True)
    server = _Server()
    session = PtySession("s12-tmux", ws, server=cast(Any, server))
    setup = server.pane.sent[0]
    expected = f'export PATH="{session.cwd / ".venv" / "bin"}:$PATH"'
    assert expected in setup, f"venv prepend missing from setup_cmd: {setup!r}"
    # Prepend must be part of the init chain (runs before any model command).
    assert "export PS1" in setup
    session.close()


def test_tmux_setup_unchanged_without_venv(tmp_path: Path) -> None:
    """Negative direction: raw clones get byte-identical init (no prepend)."""
    ws = _make_workspace(tmp_path, venv=False)
    server = _Server()
    session = PtySession("s12-tmux-novenv", ws, server=cast(Any, server))
    setup = server.pane.sent[0]
    assert "export PATH=" not in setup, f"unexpected PATH mutation: {setup!r}"
    session.close()


# ── backend 2: pexpect fallback env ──────────────────────────────────────────


def _capture_pexpect_env(tmp_path: Path, monkeypatch: Any) -> dict[str, str]:
    import pexpect  # type: ignore[import-untyped]  # same waiver as pty_pool.py

    captured: dict[str, str] = {}

    class _FakeSpawn:
        encoding = "utf-8"

        def expect(self, *_a: object, **_k: object) -> int:
            return 0

        def sendline(self, *_a: object) -> None:  # pragma: no cover
            pass

    def fake_spawn(_cmd: str, _args: list[str], *, env: dict[str, str], **_k: object) -> _FakeSpawn:
        captured.update(env)
        return _FakeSpawn()

    monkeypatch.setattr(pexpect, "spawn", fake_spawn)
    session = PtySession("s12-pexpect", tmp_path, server=None)
    assert session._is_fallback is True  # test inspects backend selection
    return captured


def test_pexpect_env_prepends_venv(tmp_path: Path, monkeypatch: Any) -> None:
    """Kill-check target: the venv_env dict in the pexpect branch."""
    ws = _make_workspace(tmp_path, venv=True)
    env = _capture_pexpect_env(ws, monkeypatch)
    venv_bin = str(ws / ".venv" / "bin")
    assert env["PATH"].split(os.pathsep)[0] == venv_bin, f"venv bin must be first on PATH: {env['PATH']!r}"


def test_pexpect_env_unchanged_without_venv(tmp_path: Path, monkeypatch: Any) -> None:
    """--norc --noprofile children historically get NO PATH key; keep it that way."""
    ws = _make_workspace(tmp_path, venv=False)
    env = _capture_pexpect_env(ws, monkeypatch)
    assert "PATH" not in env, f"raw-clone pexpect env must not gain PATH: {env!r}"


# ── backend 3: subprocess fallback (main-agent fallback AND subagents) ───────


def test_subprocess_fallback_resolves_venv_tools_live(tmp_path: Path, monkeypatch: Any) -> None:
    """Live-path: the REAL tool handler must resolve a venv-only executable.

    This is the exact failure the 2026-08-31 l2 row hit (`pytest: command not
    found` while .venv/bin/pytest existed). Kill-check: remove the post-scrub
    prepend in _run_subprocess_fallback and `command -v` no longer finds the
    stub — the assertions below fail.
    """
    ws = _make_workspace(tmp_path, venv=True)
    stub = ws / ".venv" / "bin" / "fa-s12-probe"
    stub.write_text("#!/bin/sh\necho s12-venv-stub\n", encoding="utf-8")
    stub.chmod(0o755)
    # C3 flavor: the prepend must NOT bypass the secret scrubber.
    monkeypatch.setenv("S12_FAKE_SECRET_TOKEN", "leak-me")

    tool = build_run_bash_tool(ws)
    probe = "command -v fa-s12-probe && fa-s12-probe"
    result = tool.handler({"command": f'{probe} && echo "tok=${{S12_FAKE_SECRET_TOKEN:-scrubbed}}"'})

    assert result.error is None, f"venv tool not resolvable: {result.error}"
    stdout = str((result.result or {}).get("stdout", ""))
    assert str(stub) in stdout, f"resolved outside the venv: {stdout!r}"
    assert "s12-venv-stub" in stdout
    assert "tok=scrubbed" in stdout, "secret env leaked through the prepend path"
    assert "leak-me" not in stdout


def test_subprocess_fallback_unchanged_without_venv(tmp_path: Path) -> None:
    """Negative direction: no .venv → PATH untouched by the tool."""
    ws = _make_workspace(tmp_path, venv=False)
    tool = build_run_bash_tool(ws)
    result = tool.handler({"command": 'echo "$PATH"'})
    assert result.error is None, f"PATH probe failed: {result.error}"
    stdout = str((result.result or {}).get("stdout", ""))
    assert str(ws) not in stdout, f"PATH mutated without a venv: {stdout!r}"
