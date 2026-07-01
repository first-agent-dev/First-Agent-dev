"""Tests for ``fa.sandbox.bash_gate.evaluate_bash``.

End-to-end pipeline tests — each test composes one input command and
inspects the exact :class:`BashGateDecision` (allow + category + reason
+ validator_result).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fa.sandbox.bash_gate import BashGateDecision, evaluate_bash
from fa.sandbox.classifier import BashCategory
from fa.sandbox.validators import ValidationResult


def test_read_only_command_is_allowed(tmp_path: Path) -> None:
    decision = evaluate_bash("ls -la", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=True,
        category=BashCategory.READ_ONLY,
        reason="read-only command",
    )


def test_evaluate_bash_denies_secret_path_read(tmp_path: Path) -> None:
    decision = evaluate_bash("cat /run/secrets/fa.env", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.READ_ONLY,
        reason="read of secret path blocked (ADR-12 secret isolation)",
    )


def test_evaluate_bash_honors_secret_path_extra(tmp_path: Path) -> None:
    decision = evaluate_bash(
        "cat /custom/secret/key",
        workspace_root=tmp_path,
        secret_path_extra=("/custom/secret",),
    )
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.READ_ONLY,
        reason="read of secret path blocked (ADR-12 secret isolation)",
    )


def test_dangerous_unvalidated_is_denied(tmp_path: Path) -> None:
    decision = evaluate_bash("sudo rm -rf /", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.DANGEROUS,
        reason="dangerous command with no per-command validator",
    )


def test_rm_recursive_dispatched_to_validator_and_denied(tmp_path: Path) -> None:
    decision = evaluate_bash("rm -rf /etc", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.DANGEROUS,
        reason="validator_rm: target '/etc' is a system directory (always denied)",
        validator_result=ValidationResult(
            allow=False,
            reason="validator_rm: target '/etc' is a system directory (always denied)",
        ),
    )


def test_chmod_recursive_dispatched_to_validator(tmp_path: Path) -> None:
    decision = evaluate_bash("chmod -R 777 .", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.DANGEROUS,
        reason="validator_chmod: mode '777' grants world-write (denied)",
        validator_result=ValidationResult(
            allow=False,
            reason="validator_chmod: mode '777' grants world-write (denied)",
        ),
    )


def test_git_write_allowed_for_safe_commit(tmp_path: Path) -> None:
    decision = evaluate_bash("git commit -m foo", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=True,
        category=BashCategory.GIT_WRITE,
        reason="validator_git: ok",
        validator_result=ValidationResult(allow=True, reason="validator_git: ok"),
    )


def test_git_write_denied_for_identity_rewrite(tmp_path: Path) -> None:
    decision = evaluate_bash("git config user.email evil@example.com", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.GIT_WRITE,
        reason="validator_git: writing `git config user.email` rewrites git identity (denied)",
        validator_result=ValidationResult(
            allow=False,
            reason="validator_git: writing `git config user.email` rewrites git identity (denied)",
        ),
    )


def test_git_write_denied_for_force_push_main(tmp_path: Path) -> None:
    decision = evaluate_bash("git push --force origin main", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.GIT_WRITE,
        reason="validator_git: force-push to `main`/`master` is denied",
        validator_result=ValidationResult(
            allow=False,
            reason="validator_git: force-push to `main`/`master` is denied",
        ),
    )


def test_package_install_denied_by_default(tmp_path: Path) -> None:
    decision = evaluate_bash("pip install requests", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.PACKAGE_INSTALL,
        reason="package-install denied: caller did not pass allow_package_install=True",
    )


def test_package_install_allowed_with_explicit_flag(tmp_path: Path) -> None:
    decision = evaluate_bash(
        "pip install requests",
        workspace_root=tmp_path,
        allow_package_install=True,
    )
    assert decision == BashGateDecision(
        allow=True,
        category=BashCategory.PACKAGE_INSTALL,
        reason="package-install explicitly allowed by caller",
    )


def test_general_write_default_allowed(tmp_path: Path) -> None:
    decision = evaluate_bash("mkdir foo", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=True,
        category=BashCategory.GENERAL_WRITE,
        reason="general-write allowed by caller",
    )


def test_general_write_denied_when_flag_false(tmp_path: Path) -> None:
    decision = evaluate_bash(
        "mkdir foo",
        workspace_root=tmp_path,
        allow_general_write=False,
    )
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.GENERAL_WRITE,
        reason="general-write denied: caller did not pass allow_general_write=True",
    )


def test_general_write_rm_dispatched_to_validator(tmp_path: Path) -> None:
    (tmp_path / "victim").write_text("x")
    decision = evaluate_bash("rm victim", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=True,
        category=BashCategory.GENERAL_WRITE,
        reason="validator_rm: ok",
        validator_result=ValidationResult(allow=True, reason="validator_rm: ok"),
    )


def test_general_write_rm_outside_workspace_denied(tmp_path: Path) -> None:
    decision = evaluate_bash("rm /opt/foo", workspace_root=tmp_path)
    base_str = str(tmp_path.resolve())
    expected_msg = (
        "validator_rm: target '/opt/foo' not contained in workspace "
        f"(resolved path /opt/foo is outside base {base_str})"
    )
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.GENERAL_WRITE,
        reason=expected_msg,
        validator_result=ValidationResult(
            allow=False,
            reason=expected_msg,
        ),
    )


def test_chmod_777_non_recursive_dispatched_to_validator(tmp_path: Path) -> None:
    decision = evaluate_bash("chmod 777 file", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.GENERAL_WRITE,
        reason="validator_chmod: mode '777' grants world-write (denied)",
        validator_result=ValidationResult(
            allow=False,
            reason="validator_chmod: mode '777' grants world-write (denied)",
        ),
    )


def test_bash_gate_decision_is_frozen() -> None:
    decision = BashGateDecision(
        allow=True,
        category=BashCategory.READ_ONLY,
        reason="ok",
    )
    with pytest.raises(FrozenInstanceError):
        decision.allow = False  # type: ignore[misc]


def test_empty_command_treated_as_general_write_denied(tmp_path: Path) -> None:
    decision = evaluate_bash("", workspace_root=tmp_path)
    assert decision == BashGateDecision(
        allow=False,
        category=BashCategory.GENERAL_WRITE,
        reason="validator: command is empty or unparseable",
        validator_result=ValidationResult(
            allow=False,
            reason="validator: command is empty or unparseable",
        ),
    )
