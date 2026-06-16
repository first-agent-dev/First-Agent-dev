"""Phase-3 tests: fs.run_bash child env is allowlist-scrubbed (ADR-12)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.bash_env import SECRET_NAME_RE, build_scrubbed_env
from fa.inner_loop.tools.run_bash import build_run_bash_tool


def _run(tool: ToolSpec, command: str) -> ToolResult:
    return tool.handler({"command": command})


def _stdout(res: ToolResult) -> str:
    assert res.result is not None
    return str(res.result.get("stdout", ""))


def _stderr(res: ToolResult) -> str:
    assert res.result is not None
    return str(res.result.get("stderr") or "")


def test_secret_name_re_matches_common_credential_names() -> None:
    for name in (
        "FIREWORKS_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "GITHUB_TOKEN",
        "DB_PASSWORD",
        "MY_PRIVATE_THING",
    ):
        assert SECRET_NAME_RE.search(name), name


def test_build_scrubbed_env_drops_secrets_keeps_allowlisted() -> None:
    source = {
        "PATH": "/usr/bin",
        "PYTHONPATH": "/workspace/src",
        "LC_ALL": "C",
        "GIT_SSH_COMMAND": "ssh -i /run/secrets/git_key",
        "FIREWORKS_API_KEY": "fw-secret",
        "RANDOM_OTHER_VAR": "should-be-dropped-not-allowlisted",
    }
    scrubbed = build_scrubbed_env(source)
    assert scrubbed["PATH"] == "/usr/bin"
    assert scrubbed["PYTHONPATH"] == "/workspace/src"
    assert scrubbed["LC_ALL"] == "C"
    assert scrubbed["GIT_SSH_COMMAND"].startswith("ssh")
    assert "FIREWORKS_API_KEY" not in scrubbed
    assert "RANDOM_OTHER_VAR" not in scrubbed  # not allowlisted


def test_extra_allow_cannot_re_expose_a_secret_name() -> None:
    """Fail-closed: an operator override of a credential name is still dropped."""
    source = {"FIREWORKS_API_KEY": "fw-secret", "MY_TOOL_HOME": "/x"}
    scrubbed = build_scrubbed_env(
        source, extra_allow={"FIREWORKS_API_KEY", "MY_TOOL_HOME"}
    )
    assert "FIREWORKS_API_KEY" not in scrubbed  # secret filter wins over allowlist
    assert scrubbed["MY_TOOL_HOME"] == "/x"  # non-secret extra is allowed


def test_run_bash_printenv_returns_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIREWORKS_API_KEY", "fw-LEAK-12345")
    tool = build_run_bash_tool(tmp_path)
    res = _run(tool, "printenv FIREWORKS_API_KEY || true")
    assert "fw-LEAK-12345" not in _stdout(res)
    assert "fw-LEAK-12345" not in _stderr(res)


def test_run_bash_env_dump_returns_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-LEAK-99")
    tool = build_run_bash_tool(tmp_path)
    res = _run(tool, "env")
    assert "or-LEAK-99" not in _stdout(res)


def test_run_bash_proc_self_environ_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ak-LEAK-77")
    tool = build_run_bash_tool(tmp_path)
    res = _run(tool, "cat /proc/self/environ | tr '\\0' '\\n' || true")
    assert "ak-LEAK-77" not in _stdout(res)


def test_run_bash_python_environ_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FIREWORKS_API_KEY", "fw-LEAK-py")
    tool = build_run_bash_tool(tmp_path)
    res = _run(
        tool,
        "python3 -c \"import os;print(os.environ.get('FIREWORKS_API_KEY',''))\" || true",
    )
    assert "fw-LEAK-py" not in _stdout(res)


def test_run_bash_still_has_path(tmp_path: Path) -> None:
    """Sanity: the tool still works (PATH present, commands run)."""
    tool = build_run_bash_tool(tmp_path)
    res = _run(tool, "echo OK && test -n \"$PATH\" && echo HASPATH")
    assert res.ok
    assert "OK" in _stdout(res)
    assert "HASPATH" in _stdout(res)
