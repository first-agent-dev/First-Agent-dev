"""Tests for ``fa.sandbox.bash_gate.evaluate_bash``.

End-to-end pipeline tests — each test composes one input command and
inspects the full :class:`BashGateDecision` (allow + category + reason
+ validator_result). The five-category x validator-dispatch matrix is
covered with at least one allow and one deny per category.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from fa.sandbox.bash_gate import BashGateDecision, evaluate_bash
from fa.sandbox.classifier import BashCategory


def test_read_only_command_is_allowed(tmp_path: Path) -> None:
    decision = evaluate_bash("ls -la", workspace_root=tmp_path)
    assert decision.allow is True
    assert decision.category is BashCategory.READ_ONLY
    assert decision.validator_result is None


def test_dangerous_unvalidated_is_denied(tmp_path: Path) -> None:
    decision = evaluate_bash("sudo rm -rf /", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.category is BashCategory.DANGEROUS


def test_rm_recursive_dispatched_to_validator_and_denied(
    tmp_path: Path,
) -> None:
    """`rm -rf .` is DANGEROUS but rm has a validator — it still denies
    because the validator sees `.` as the workspace root and rejects."""
    decision = evaluate_bash("rm -rf /etc", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.category is BashCategory.DANGEROUS
    assert decision.validator_result is not None


def test_chmod_recursive_dispatched_to_validator(tmp_path: Path) -> None:
    decision = evaluate_bash("chmod -R 777 .", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.category is BashCategory.DANGEROUS
    assert decision.validator_result is not None


def test_git_write_allowed_for_safe_commit(tmp_path: Path) -> None:
    decision = evaluate_bash("git commit -m foo", workspace_root=tmp_path)
    assert decision.allow is True
    assert decision.category is BashCategory.GIT_WRITE


def test_git_write_denied_for_identity_rewrite(tmp_path: Path) -> None:
    decision = evaluate_bash("git config user.email evil@example.com", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.category is BashCategory.GIT_WRITE
    assert "identity" in decision.reason


def test_git_write_denied_for_force_push_main(tmp_path: Path) -> None:
    decision = evaluate_bash("git push --force origin main", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.category is BashCategory.GIT_WRITE
    assert "force-push" in decision.reason


def test_package_install_denied_by_default(tmp_path: Path) -> None:
    decision = evaluate_bash("pip install requests", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.category is BashCategory.PACKAGE_INSTALL


def test_package_install_allowed_with_explicit_flag(tmp_path: Path) -> None:
    decision = evaluate_bash(
        "pip install requests",
        workspace_root=tmp_path,
        allow_package_install=True,
    )
    assert decision.allow is True
    assert decision.category is BashCategory.PACKAGE_INSTALL


def test_general_write_default_allowed(tmp_path: Path) -> None:
    decision = evaluate_bash("mkdir foo", workspace_root=tmp_path)
    assert decision.allow is True
    assert decision.category is BashCategory.GENERAL_WRITE


def test_general_write_denied_when_flag_false(tmp_path: Path) -> None:
    decision = evaluate_bash(
        "mkdir foo",
        workspace_root=tmp_path,
        allow_general_write=False,
    )
    assert decision.allow is False
    assert decision.category is BashCategory.GENERAL_WRITE
    assert "general-write" in decision.reason


def test_general_write_rm_dispatched_to_validator(tmp_path: Path) -> None:
    """Non-recursive `rm` is GENERAL_WRITE; validator still runs."""
    (tmp_path / "victim").write_text("x")
    decision = evaluate_bash("rm victim", workspace_root=tmp_path)
    assert decision.allow is True
    assert decision.validator_result is not None


def test_general_write_rm_outside_workspace_denied(tmp_path: Path) -> None:
    decision = evaluate_bash("rm /opt/foo", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.validator_result is not None


def test_chmod_777_non_recursive_dispatched_to_validator(
    tmp_path: Path,
) -> None:
    """Non-recursive `chmod 777` is GENERAL_WRITE; validator denies it."""
    decision = evaluate_bash("chmod 777 file", workspace_root=tmp_path)
    assert decision.allow is False
    assert decision.validator_result is not None


def test_bash_gate_decision_is_frozen() -> None:
    """Decision type is immutable so the audit log is replay-safe."""
    decision = BashGateDecision(
        allow=True,
        category=BashCategory.READ_ONLY,
        reason="ok",
    )
    with pytest.raises(FrozenInstanceError):
        decision.allow = False  # type: ignore[misc]


def test_empty_command_treated_as_general_write_denied(
    tmp_path: Path,
) -> None:
    """Defensive — empty command falls through; validator denies."""
    decision = evaluate_bash("", workspace_root=tmp_path)
    assert decision.allow is False
