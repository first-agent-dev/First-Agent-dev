"""Phase A (ADR-12): fs.run_bash must not read known secret paths.

These prove the bash gate denies the V1-relocated vector — reading the secrets
file / deploy key out of /run/secrets (or the dev ~/.fa/.env) via any read
command — while still allowing legitimate out-of-workspace reads the agent
relies on (e.g. /etc/hostname).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.sandbox.bash_gate import evaluate_bash
from fa.sandbox.secret_paths import command_reads_secret_path

_WS = Path("/workspace")

_DENY = [
    "cat /run/secrets/fa.env",
    "cat /run/secrets/git_key",
    "grep KEY /srv/first-agent/secrets/fa.env",
    "head -c 10 /run/secrets/fa.env",
    "dd if=/run/secrets/fa.env",
    "od -c /run/secrets/git_key",
    "sed -n 1p /run/secrets/fa.env",
    "awk '{print}' /run/secrets/fa.env",
    "xxd /run/secrets/git_key",
    "cat /proc/self/root/run/secrets/fa.env",
    "cat /run/secrets/../secrets/fa.env",
    "cd /run/secrets && cat fa.env",
]

_ALLOW = [
    "cat /workspace/notes.md",
    "cat /etc/hostname",
    "ls /run",
    "grep TODO /workspace/src/app.py",
    "echo hello",
    "cat README.md",
]


@pytest.mark.parametrize("command", _DENY, ids=lambda c: c[:32])
def test_secret_reads_denied(command: str) -> None:
    d = evaluate_bash(command, workspace_root=_WS)
    assert not d.allow, f"should deny: {command}"
    assert "secret path" in d.reason


@pytest.mark.parametrize("command", _ALLOW, ids=lambda c: c[:32])
def test_legitimate_reads_allowed(command: str) -> None:
    d = evaluate_bash(command, workspace_root=_WS)
    assert d.allow, f"should allow: {command} (got: {d.reason})"


def test_unparseable_command_with_secret_prefix_fails_closed() -> None:
    # Unterminated quote → shlex fails; raw text references a secret dir → deny.
    assert command_reads_secret_path('cat "/run/secrets/fa.env')


def test_home_fa_env_denied() -> None:
    home_env = str(Path.home() / ".fa" / ".env")
    assert command_reads_secret_path(f"cat {home_env}")


def test_extra_prefix_is_honored() -> None:
    assert command_reads_secret_path(
        "cat /custom/secret/place/x", extra_prefixes=("/custom/secret/place",)
    )
    assert not command_reads_secret_path("cat /custom/secret/place/x")
