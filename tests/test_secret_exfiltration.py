"""Red-team acceptance test (ADR-12): no agent tool can read an API key.

Executable encoding of the success criterion "no LLM can sniff out my keys".
Runs the REAL fs.run_bash tool with a fake key present in os.environ (the worst
case — even if Phase-2 isolation regressed and a key leaked back into the env,
Phase-3 bash-scrubbing must still block every exfil path).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.tools.run_bash import build_run_bash_tool

_FAKE_KEY = "sk-REDTEAM-fireworks-0xDEADBEEF-1234567890"
_VAR = "FIREWORKS_API_KEY"

# Every exfil command an agent might try. None may surface the key value.
_EXFIL_COMMANDS = [
    f"printenv {_VAR} || true",
    "env || true",
    "set || true",
    "declare -p 2>/dev/null || true",
    "export -p || true",
    "cat /proc/self/environ 2>/dev/null | tr '\\0' '\\n' || true",
    "cat /proc/1/environ 2>/dev/null | tr '\\0' '\\n' || true",
    f"python3 -c \"import os,sys;sys.stdout.write(os.environ.get('{_VAR}',''))\" || true",
    f"printenv {_VAR} | base64 || true",
    f"printenv {_VAR} | xxd || true",
    f"echo ${_VAR} || true",
    f'echo "${{{_VAR}}}" || true',
]


@pytest.mark.parametrize("command", _EXFIL_COMMANDS, ids=lambda c: c[:32])
def test_bash_cannot_exfiltrate_key(command: str, tmp_path: Path, monkeypatch) -> None:
    # Worst case: the key IS in the parent process env. The scrubbed child env
    # must still keep it out of the agent shell.
    monkeypatch.setenv(_VAR, _FAKE_KEY)
    tool = build_run_bash_tool(tmp_path)
    res = tool.handler({"command": command})
    blob = (res.result or {}).get("stdout", "") + (res.result or {}).get("stderr", "")
    # raw key
    assert _FAKE_KEY not in blob, f"key leaked via: {command}"
    # base64 of key
    import base64

    assert base64.b64encode(_FAKE_KEY.encode()).decode() not in blob
    # hex of key
    assert _FAKE_KEY.encode().hex() not in blob


def test_bash_env_has_no_credential_named_vars(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-x")
    monkeypatch.setenv("GITHUB_TOKEN", "gh-x")
    monkeypatch.setenv("DB_PASSWORD", "pw-x")
    tool = build_run_bash_tool(tmp_path)
    res = tool.handler({"command": "env"})
    out = res.result["stdout"]
    for leaked in ("or-x", "gh-x", "pw-x"):
        assert leaked not in out


def test_workspace_env_files_are_not_present(tmp_path: Path) -> None:
    """`.env.fa` must not be a readable file inside the workspace anymore.

    (Structural: the agent's sandbox root is the workspace; keys live in
    /run/secrets outside it. Here we assert the tool's cwd has no key file the
    way the old layout did.)
    """
    tool = build_run_bash_tool(tmp_path)
    res = tool.handler({"command": "cat .env.fa 2>/dev/null; echo DONE"})
    assert "DONE" in res.result["stdout"]
    # nothing key-shaped leaked
    assert "sk-" not in res.result["stdout"]
