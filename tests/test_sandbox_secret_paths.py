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
    # Unterminated quote without secret prefix → allow (False).
    assert command_reads_secret_path('cat "/etc/hostname') is False


def test_home_fa_env_denied() -> None:
    home_env = str(Path.home() / ".fa" / ".env")
    assert command_reads_secret_path(f"cat {home_env}")


def test_extra_prefix_is_honored() -> None:
    assert command_reads_secret_path(
        "cat /custom/secret/place/x", extra_prefixes=("/custom/secret/place",)
    )
    assert not command_reads_secret_path("cat /custom/secret/place/x")


def test_raw_substring_fallback_prevents_interpreter_bypass() -> None:
    # A clever agent might pass a secret path as a string to another interpreter
    # where the tokenizer sees `python3 -c "import os..."` as a single token
    # that does not START with the secret path. The raw substring fallback catches it.
    command = "python3 -c \"print(open('/run/secrets/fa.env').read())\""
    assert command_reads_secret_path(command) is True


def test_safe_tokens_posix_and_error_handling() -> None:
    from fa.sandbox.secret_paths import _safe_tokens
    assert _safe_tokens("cat foo") == ["cat", "foo"]
    assert _safe_tokens('cat "foo bar"') == ["cat", "foo bar"]
    assert _safe_tokens('cat "unterminated') is None


def test_path_candidates_splitting() -> None:
    from fa.sandbox.secret_paths import _path_candidates
    assert _path_candidates("simple") == ["simple"]
    assert _path_candidates("if=/path/to/secret") == ["if=/path/to/secret", "/path/to/secret"]
    assert _path_candidates("a=b=c") == ["a=b=c", "b=c"]


def test_within_prefix_matching() -> None:
    from fa.sandbox.secret_paths import _within
    assert _within("", "/prefix") is False
    assert _within("/run/secrets", "/run/secrets/") is True
    assert _within("/run/secrets/", "/run/secrets") is True
    assert _within("/run/secrets/fa.env", "/run/secrets") is True
    assert _within("/run/secrets_other", "/run/secrets") is False
    assert _within("/run/sec", "/run/secrets") is False


def test_lexical_abs_path_collapsing() -> None:
    from pathlib import Path

    from fa.sandbox.secret_paths import _lexical_abs
    assert _lexical_abs(Path("/")) == "/"
    assert _lexical_abs(Path("/a/b/../c/./d")) == "/a/c/d"
    assert _lexical_abs(Path("/../a")) == "/a"


def test_normalize_proc_and_relative() -> None:
    from fa.sandbox.secret_paths import _normalize
    assert _normalize("") == ""
    assert _normalize("   ") == ""
    assert _normalize("/proc/self/root") == "/"
    assert _normalize("/proc/self/root/etc/passwd") == "/etc/passwd"
    assert _normalize("/proc/1/root") == "/"
    assert _normalize("/proc/1/root/etc/passwd") == "/etc/passwd"
    assert _normalize("relative/path") == "relative/path"
    assert _normalize("/abs/./path/../file") == "/abs/file"
    assert _normalize("~/secret") == str(Path("~/secret").expanduser())


def test_command_reads_secret_path_normalized_traversal() -> None:
    assert command_reads_secret_path("cat /run/secret_dir/../secrets/fa.env") is True
    assert command_reads_secret_path('cat "/run/secret_dir/../secrets/fa.env"') is True
    assert command_reads_secret_path("dd if=/run/secret_dir/../secrets/fa.env") is True
    assert command_reads_secret_path("cd /run/secret_dir/../secrets && cat fa.env") is True
    assert command_reads_secret_path("ls /run") is False
