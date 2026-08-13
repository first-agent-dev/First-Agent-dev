"""CT1/CT2 tests for managed Git workspace provisioning.

Pyramid A path inventory:
  A: pure GitHub push-URL normalization and structured/redacted failures (C0/C3)
  B: direct provisioner checkout, branch, remotes, identity, and rollback (C1/C3)
  C: real SessionManager Git-source dispatch and public error mapping (C1)
  D: command-local publication rewrite to an offline bare remote (C1)

External Git is real and local. No provider, model, GitHub, or other network I/O
is used. Product tests assert filesystem/Git state rather than mere completion.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from typing import Any, cast

import pytest

import fa.session.workspace as workspace_module
from fa.session.manager import SessionManager, SessionManagerError
from fa.session.workspace import (
    ExistingWorkspaceState,
    GitWorkspaceState,
    WorkspaceProvisionError,
    configure_existing_workspace,
    normalize_push_url,
    provision_git_workspace,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "git@github.com:first-agent-dev/First-Agent-dev.git",
            "git@github.com:first-agent-dev/First-Agent-dev.git",
        ),
        (
            "git@github.com:first-agent-dev/First-Agent-dev",
            "git@github.com:first-agent-dev/First-Agent-dev.git",
        ),
        (
            "ssh://git@github.com/first-agent-dev/First-Agent-dev.git",
            "git@github.com:first-agent-dev/First-Agent-dev.git",
        ),
        (
            "https://github.com/fork_owner/repo.name",
            "git@github.com:fork_owner/repo.name.git",
        ),
    ],
)
def test_https_ssh_and_override_urls_canonicalize_exactly(raw: str, expected: str) -> None:
    """class=C0 claim=CT2 kill-check=remove closed URL-shape canonicalizer."""

    assert normalize_push_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " git@github.com:owner/repo.git",
        " https://github.com/owner/repo.git",
        "git@github.com:owner/repo.git\n",
        "https://github.com/owner/repo\t.git",
        "https://token@github.com/owner/repo.git",
        "https://user:secret@github.com/owner/repo.git",
        "https://github.com/owner/repo/extra",
        "https://github.com/owner/repo.git?token=secret",
        "https://github.com/owner/repo.git#fragment",
        "https://[github.com/owner/repo.git",
        "http://github.com/owner/repo.git",
        "ssh://root@github.com/owner/repo.git",
        "ssh://git@github.example/owner/repo.git",
        "file:///repo",
        "/repo",
        "git@github.com:../repo.git",
        "git@github.com:owner/...git",
        "git@github.com:owner/repo name.git",
    ],
)
def test_invalid_or_credentialed_push_urls_are_redacted_and_rejected(raw: str) -> None:
    """class=C3 claim=CT2 kill-check=remove credential/control/path deny gate."""

    with pytest.raises(WorkspaceProvisionError) as caught:
        normalize_push_url(raw)

    error = caught.value
    assert error.code == "push_url_invalid"
    assert error.stage == "resolve_push_url"
    assert error.detail == "push URL must be a credential-free GitHub HTTPS or SSH repository URL"
    assert not raw or raw not in str(error)
    assert "token" not in str(error)
    assert "secret" not in str(error)


@pytest.mark.parametrize("raw", [None, 42])
def test_non_string_push_urls_are_structured_failures(raw: object) -> None:
    """class=C3 claim=CT2 kill-check=remove runtime type gate."""

    with pytest.raises(WorkspaceProvisionError) as caught:
        normalize_push_url(cast(Any, raw))

    assert caught.value.code == "push_url_invalid"
    assert caught.value.stage == "resolve_push_url"


def test_workspace_state_is_frozen_and_error_public_fields_are_read_only() -> None:
    """class=C0 claim=CT1 oracle=immutable result/error schema."""

    state = GitWorkspaceState(
        "a",
        "a",
        "agent/s",
        "file:///repo",
        "git@github.com:o/r.git",
        "Agent",
        "a@b",
    )

    def mutate_state() -> None:
        state.branch = "main"  # type: ignore[misc]  # intentional frozen-state mutation probe

    with pytest.raises(FrozenInstanceError):
        mutate_state()

    error = WorkspaceProvisionError("target_exists", "validate_source", "target exists")
    assert str(error) == "target_exists [validate_source]: target exists"

    def mutate_error() -> None:
        error.code = "git_timeout"  # type: ignore[misc]  # intentional read-only-property mutation probe

    with pytest.raises(AttributeError):
        mutate_error()


_CANONICAL_PUSH_URL = "git@github.com:first-agent-dev/First-Agent-dev.git"


def _git(
    cwd: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        check=check,
        capture_output=True,
        text=True,
        timeout=30,
        env=environment,
    )


def _make_git_source(tmp_path: Path, *, push_url: str = _CANONICAL_PUSH_URL) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(source)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _git(source, "config", "user.name", "Source Fixture")
    _git(source, "config", "user.email", "source@example.invalid")
    (source / ".gitignore").write_text(".env.fa\n.venv/\n", encoding="utf-8")
    (source / "tracked.txt").write_text("captured\n", encoding="utf-8")
    _git(source, "add", ".gitignore", "tracked.txt")
    _git(source, "commit", "-m", "source fixture")
    _git(source, "remote", "add", "origin", push_url)

    (source / ".env.fa").write_text("ignored-secret-shaped-control\n", encoding="utf-8")
    (source / ".venv").mkdir()
    (source / ".venv" / "copied.txt").write_text("must not copy\n", encoding="utf-8")
    (source / "untracked.txt").write_text("must not copy\n", encoding="utf-8")
    source_hook = source / ".git" / "hooks" / "source-only"
    source_hook.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    source_hook.chmod(0o755)
    return source


def _target_state(target: Path) -> tuple[str, str, str, str, str, str]:
    return (
        _git(target, "rev-parse", "HEAD").stdout.strip(),
        _git(target, "branch", "--show-current").stdout.strip(),
        _git(target, "remote", "get-url", "origin").stdout.strip(),
        _git(target, "remote", "get-url", "--push", "origin").stdout.strip(),
        _git(target, "config", "--local", "--get", "user.name").stdout.strip(),
        _git(target, "config", "--local", "--get", "user.email").stdout.strip(),
    )


def test_git_runner_forces_noninteractive_bounded_argument_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """class=C3 claim=CT1 kill-check=remove subprocess safety kwargs/env."""

    seen_command: list[str] = []
    seen_kwargs: dict[str, Any] = {}

    def successful_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen_command.extend(command)
        seen_kwargs.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "value\n", "")

    monkeypatch.setattr("fa.session.workspace.subprocess.run", successful_run)

    assert workspace_module._run_git(("status", "--short"), stage="verify_postconditions") == "value"
    assert seen_command == ["git", "status", "--short"]
    assert seen_kwargs["check"] is False
    assert seen_kwargs["capture_output"] is True
    assert seen_kwargs["text"] is True
    assert seen_kwargs["timeout"] == 120
    environment = seen_kwargs["env"]
    assert isinstance(environment, dict)
    assert environment["GIT_TERMINAL_PROMPT"] == "0"


def test_git_runner_redacts_and_structures_command_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C3 claim=CT1 kill-check=remove diagnostic redaction/result fields."""

    def failed_run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            9,
            "",
            "fatal: https://user:secret@example.invalid/repo?token=hidden#fragment token=loose bad\x1b",
        )

    monkeypatch.setattr("fa.session.workspace.subprocess.run", failed_run)
    with pytest.raises(WorkspaceProvisionError) as caught:
        workspace_module._run_git(("fetch",), stage="clone")

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == (
        "git_command_failed",
        "clone",
        "git command failed with exit code 9: fatal: "
        "https://<redacted>@example.invalid/repo?<redacted> token=<redacted> bad\\x1b",
    )
    assert "secret" not in caught.value.detail
    assert "hidden" not in caught.value.detail
    assert "fragment" not in caught.value.detail
    assert "loose" not in caught.value.detail


def test_provisioner_captures_revision_before_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C1 path=B claim=CT1 kill-check=replace captured commit with live HEAD."""

    source = _make_git_source(tmp_path)
    captured = _git(source, "rev-parse", "HEAD").stdout.strip()
    original_run_git = workspace_module._run_git
    advanced = False

    def advance_then_run(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        nonlocal advanced
        if stage == "clone" and not advanced:
            advanced = True
            (source / "after-capture.txt").write_text("newer\n", encoding="utf-8")
            _git(source, "add", "after-capture.txt")
            _git(source, "commit", "-m", "advance source")
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", advance_then_run)
    target = tmp_path / "target"
    state = provision_git_workspace(source, target, "capture-race")

    assert advanced is True
    assert _git(source, "rev-parse", "HEAD").stdout.strip() != captured
    assert state.source_revision == state.target_revision == captured
    assert not (target / "after-capture.txt").exists()


def test_provisioner_sets_local_identity_and_real_commit_needs_no_test_identity(tmp_path: Path) -> None:
    """class=C1 path=B claim=G2/GAP13 kill-check=remove local identity writes."""

    source = _make_git_source(tmp_path)
    source_revision = _git(source, "rev-parse", "HEAD").stdout.strip()
    target = tmp_path / "target"
    state = provision_git_workspace(source, target, "identity")

    assert _target_state(target) == (
        source_revision,
        "agent/identity",
        source.resolve().as_uri(),
        _CANONICAL_PUSH_URL,
        "First Agent",
        "agent@first-agent.local",
    )
    assert state == GitWorkspaceState(
        source_revision=source_revision,
        target_revision=source_revision,
        branch="agent/identity",
        fetch_url=source.resolve().as_uri(),
        push_url=_CANONICAL_PUSH_URL,
        author_name="First Agent",
        author_email="agent@first-agent.local",
    )
    assert _git(target, "status", "--porcelain=v1", "--untracked-files=all").stdout == ""
    assert not (target / ".env.fa").exists()
    assert not (target / ".venv").exists()
    assert not (target / "untracked.txt").exists()
    assert not (target / ".git" / "hooks" / "source-only").exists()

    clean_environment = os.environ.copy()
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        clean_environment.pop(name, None)
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    clean_environment["HOME"] = str(empty_home)
    (target / "agent-change.txt").write_text("commit me\n", encoding="utf-8")
    _git(target, "add", "agent-change.txt", environment=clean_environment)
    _git(target, "commit", "-m", "agent commit", environment=clean_environment)
    assert _git(target, "show", "-s", "--format=%an <%ae>").stdout.strip() == ("First Agent <agent@first-agent.local>")


def test_explicit_push_override_wins_over_source_authority(tmp_path: Path) -> None:
    """class=C1 path=B matrix=M8 claim=CT2 kill-check=remove override branch."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"

    state = provision_git_workspace(
        source,
        target,
        "override",
        "https://github.com/fork-owner/fork-repo",
    )

    assert state.push_url == "git@github.com:fork-owner/fork-repo.git"
    assert _git(target, "remote", "get-url", "--push", "origin").stdout.strip() == state.push_url


def test_exact_empty_push_override_falls_back_to_source_authority(tmp_path: Path) -> None:
    """class=C1 path=B matrix=M8 claim=CT2 kill-check=mutate exact-empty fallback."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"

    state = provision_git_workspace(source, target, "empty-override", "")

    assert state.push_url == _CANONICAL_PUSH_URL


def test_push_origin_reaches_rewritten_local_bare_remote(tmp_path: Path) -> None:
    """class=C1 path=D claim=CT2 kill-check=remove origin.pushurl producer."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    state = provision_git_workspace(source, target, "publish")
    source_head_before = _git(source, "rev-parse", "HEAD").stdout.strip()
    source_status_before = _git(source, "status", "--porcelain=v1", "--untracked-files=all").stdout
    bare = tmp_path / "fake-github.git"
    subprocess.run(
        ["git", "init", "--bare", str(bare)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    rewrite_key = f"url.{bare.resolve().as_uri()}.insteadOf={_CANONICAL_PUSH_URL}"
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "-c",
            rewrite_key,
            "-C",
            str(target),
            "push",
            "origin",
            f"HEAD:refs/heads/{state.branch}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert _git(bare, "rev-parse", f"refs/heads/{state.branch}").stdout.strip() == state.target_revision
    assert _git(target, "remote", "get-url", "--push", "origin").stdout.strip() == _CANONICAL_PUSH_URL
    assert _git(source, "rev-parse", "HEAD").stdout.strip() == source_head_before
    assert _git(source, "status", "--porcelain=v1", "--untracked-files=all").stdout == source_status_before


def test_git_invalid_branch_id_fails_before_target_creation(tmp_path: Path) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove git check-ref-format gate."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"

    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "a..b")

    assert caught.value.code == "invalid_branch"
    assert caught.value.stage == "validate_branch"
    assert not target.exists()


def test_invalid_git_repository_has_source_revision_failure_code(tmp_path: Path) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove source-revision error mapping."""

    source = tmp_path / "not-a-repository"
    (source / ".git").mkdir(parents=True)
    target = tmp_path / "target"

    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "invalid-source")

    assert caught.value.code == "source_revision_unavailable"
    assert caught.value.stage == "capture_source_revision"
    assert not target.exists()


def test_missing_source_push_authority_is_structured_before_clone(tmp_path: Path) -> None:
    """class=C3 path=B claim=CT2 kill-check=remove push-authority error mapping."""

    source = _make_git_source(tmp_path)
    _git(source, "remote", "remove", "origin")
    target = tmp_path / "target"

    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "missing-origin")

    assert caught.value.code == "push_url_unavailable"
    assert caught.value.stage == "resolve_push_url"
    assert not target.exists()


def test_clone_failure_removes_only_helper_created_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove failed-clone cleanup."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    real_run = subprocess.run

    def fail_clone(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = args[0]
        if isinstance(command, list) and command[1:3] == ["clone", "--no-checkout"]:
            target.mkdir()
            (target / "partial").write_text("partial\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 128, "", "\x1b[31m" + ("x" * 5000))
        return cast(subprocess.CompletedProcess[str], real_run(*args, **kwargs))

    monkeypatch.setattr("fa.session.workspace.subprocess.run", fail_clone)
    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "clone-failure")

    assert caught.value.code == "git_command_failed"
    assert caught.value.stage == "clone"
    assert len(caught.value.detail) == 4096
    assert "\x1b" not in caught.value.detail
    assert "\\x1b" in caught.value.detail
    assert not target.exists()
    assert source.is_dir()


def test_preexisting_target_is_never_removed(tmp_path: Path) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove target-exists ownership gate."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "caller-owned"
    sentinel.write_text("keep\n", encoding="utf-8")

    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "existing")

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == ("target_exists", "validate_source", "target already exists")
    assert sentinel.read_text(encoding="utf-8") == "keep\n"

    broken_target = tmp_path / "broken-target-link"
    broken_target.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    with pytest.raises(WorkspaceProvisionError) as symlink_caught:
        provision_git_workspace(source, broken_target, "existing-link")
    assert symlink_caught.value.code == "target_exists"
    assert broken_target.is_symlink()


def test_symlinked_git_administration_directory_is_not_a_normal_source(tmp_path: Path) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove normal-checkout shape gate."""

    source = _make_git_source(tmp_path)
    git_directory = source / ".git"
    moved_git_directory = tmp_path / "source-git-admin"
    git_directory.rename(moved_git_directory)
    git_directory.symlink_to(moved_git_directory, target_is_directory=True)
    target = tmp_path / "target"

    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "symlinked-git")

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == (
        "source_not_git",
        "validate_source",
        "source is not a normal Git checkout",
    )
    assert not target.exists()
    assert git_directory.is_symlink()


def test_missing_git_is_structured_before_target_creation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C3 path=B claim=CT1 oracle=typed missing-binary failure."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"

    def missing_git(*_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr("fa.session.workspace.subprocess.run", missing_git)
    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "missing-git")

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == (
        "git_unavailable",
        "capture_source_revision",
        "git executable is not available",
    )
    assert not target.exists()


def test_git_timeout_is_structured_and_cleans_partial_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove timeout mapping/cleanup."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    real_run = subprocess.run

    def timeout_clone(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = args[0]
        if isinstance(command, list) and command[1:3] == ["clone", "--no-checkout"]:
            target.mkdir()
            (target / "partial").write_text("partial\n", encoding="utf-8")
            raise subprocess.TimeoutExpired(command, 120, stderr="hung")
        return cast(subprocess.CompletedProcess[str], real_run(*args, **kwargs))

    monkeypatch.setattr("fa.session.workspace.subprocess.run", timeout_clone)
    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "timeout")

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == (
        "git_timeout",
        "clone",
        "git command exceeded 120 seconds",
    )
    assert not target.exists()


def test_interrupt_cleans_created_target_and_reraises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove BaseException cleanup finally."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    real_run = subprocess.run

    def interrupt_clone(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = args[0]
        if isinstance(command, list) and command[1:3] == ["clone", "--no-checkout"]:
            target.mkdir()
            (target / "partial").write_text("partial\n", encoding="utf-8")
            raise KeyboardInterrupt
        return cast(subprocess.CompletedProcess[str], real_run(*args, **kwargs))

    monkeypatch.setattr("fa.session.workspace.subprocess.run", interrupt_clone)
    with pytest.raises(KeyboardInterrupt):
        provision_git_workspace(source, target, "interrupt")

    assert not target.exists()


@pytest.mark.parametrize("failed_stage", ["checkout_branch", "set_push_url", "set_identity"])
def test_configuration_command_failure_preserves_exact_stage_and_cleans_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_stage: workspace_module.WorkspaceProvisionStage,
) -> None:
    """class=C3 path=B claim=CT1 kill-check=mutate command-stage telemetry."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    original_run_git = workspace_module._run_git

    def fail_stage(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        if stage == failed_stage:
            raise WorkspaceProvisionError("git_command_failed", stage, "forced failure")
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", fail_stage)
    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, f"fail-{failed_stage}")

    assert caught.value.code == "git_command_failed"
    assert caught.value.stage == failed_stage
    assert not target.exists()


@pytest.mark.parametrize("identity_key", ["user.name", "user.email"])
def test_each_identity_command_failure_has_set_identity_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_key: str,
) -> None:
    """class=C3 path=B claim=CT1 kill-check=mutate either identity-command stage."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    original_run_git = workspace_module._run_git

    def fail_identity_key(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        if identity_key in arguments:
            raise WorkspaceProvisionError("git_command_failed", stage, "forced identity failure")
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", fail_identity_key)
    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, f"fail-{identity_key}")

    assert caught.value.code == "git_command_failed"
    assert caught.value.stage == "set_identity"
    assert not target.exists()


@pytest.mark.parametrize("failed_call", range(7))
def test_each_readback_command_failure_has_verify_postconditions_stage(
    monkeypatch: pytest.MonkeyPatch,
    failed_call: int,
) -> None:
    """class=C3 claim=CT1 kill-check=mutate any read-back stage field."""

    outputs = [
        "revision",
        "agent/session",
        "file:///repo",
        _CANONICAL_PUSH_URL,
        "First Agent",
        "agent@first-agent.local",
        "",
    ]
    calls = 0

    def fail_selected_readback(
        _arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        nonlocal calls
        del failure_code
        current = calls
        calls += 1
        if current == failed_call:
            raise WorkspaceProvisionError("git_command_failed", stage, "forced read-back failure")
        return outputs[current]

    monkeypatch.setattr(workspace_module, "_run_git", fail_selected_readback)
    with pytest.raises(WorkspaceProvisionError) as caught:
        workspace_module._read_verified_workspace_state(
            Path("/unused-target"),
            source_revision="revision",
            branch="agent/session",
            fetch_url="file:///repo",
            push_url=_CANONICAL_PUSH_URL,
        )

    assert caught.value.code == "git_command_failed"
    assert caught.value.stage == "verify_postconditions"


def test_final_readback_rejects_new_untracked_file(tmp_path: Path) -> None:
    """class=C3 claim=CT1 kill-check=remove all-untracked status verification."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    state = provision_git_workspace(source, target, "dirty-readback")
    (target / "unexpected.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(WorkspaceProvisionError) as caught:
        workspace_module._read_verified_workspace_state(
            target,
            source_revision=state.source_revision,
            branch=state.branch,
            fetch_url=state.fetch_url,
            push_url=state.push_url,
        )

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == (
        "postcondition_failed",
        "verify_postconditions",
        "workspace read-back did not match provisioned state",
    )


def test_readback_mismatch_is_structured_and_cleans_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C3 path=B claim=CT1 kill-check=remove final read-back equality gate."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "target"
    original_run_git = workspace_module._run_git

    def wrong_branch(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        result = original_run_git(arguments, stage=stage, failure_code=failure_code)
        if stage == "verify_postconditions" and "symbolic-ref" in arguments:
            return "main"
        return result

    monkeypatch.setattr(workspace_module, "_run_git", wrong_branch)
    with pytest.raises(WorkspaceProvisionError) as caught:
        provision_git_workspace(source, target, "mismatch")

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == (
        "postcondition_failed",
        "verify_postconditions",
        "workspace read-back did not match provisioned state",
    )
    assert not target.exists()


def test_manager_git_source_provisions_clean_b2_workspace(tmp_path: Path) -> None:
    """class=C1 root=SessionManager path=C claim=G1/G2 producer-kill-check=remove Git dispatch."""

    source = _make_git_source(tmp_path)
    source_revision = _git(source, "rev-parse", "HEAD").stdout.strip()
    manager = SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=source,
        repo_push_url="https://github.com/fork-owner/fork-repo",
    )

    session = manager.create_or_attach_session(session_id=None, workspace_override=None)
    expected_branch = f"agent/{session.session_id}"

    assert session.workspace_path.is_dir()
    assert session.manifest_path.is_file()
    assert session.session_db_path.is_file()
    assert _target_state(session.workspace_path) == (
        source_revision,
        expected_branch,
        source.resolve().as_uri(),
        "git@github.com:fork-owner/fork-repo.git",
        "First Agent",
        "agent@first-agent.local",
    )
    assert _git(session.workspace_path, "status", "--porcelain=v1", "--untracked-files=all").stdout == ""
    assert not (session.workspace_path / ".env.fa").exists()
    assert not (session.workspace_path / ".venv").exists()
    assert not (session.workspace_path / "untracked.txt").exists()
    assert not (session.workspace_path / ".git" / "hooks" / "source-only").exists()


def test_manager_maps_private_failure_to_workspace_provision_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """class=C3 root=SessionManager path=C claim=CT1 kill-check=remove public error translation."""

    source = _make_git_source(tmp_path)
    manager = SessionManager(
        state_root=tmp_path / "state",
        workspace_root=tmp_path / "workspaces",
        source_workspace=source,
    )

    def fail_provision(*_args: object, **_kwargs: object) -> GitWorkspaceState:
        raise WorkspaceProvisionError("git_timeout", "clone", "timed out")

    monkeypatch.setattr("fa.session.manager.provision_git_workspace", fail_provision)
    with pytest.raises(SessionManagerError) as caught:
        manager.create_or_attach_session(session_id=None, workspace_override=None)

    assert caught.value.code == "workspace_provision_failed"
    assert "git_timeout: timed out" in str(caught.value)
    assert isinstance(caught.value.__cause__, WorkspaceProvisionError)
    assert caught.value.__cause__.code == "git_timeout"
    assert not list(manager.sessions_root.iterdir())
    assert not list(manager.workspace_root.iterdir())


def _make_existing_workspace(source: Path, target: Path, session_id: str) -> Path:
    subprocess.run(
        ["git", "clone", source.resolve().as_uri(), str(target)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    _git(target, "switch", "-c", f"agent/{session_id}")
    return target


def test_existing_workspace_verified_state_and_identity(tmp_path: Path) -> None:
    """class=C1 path=P2 claim=CT2 kill-check=remove verified read-back/identity."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "verified")
    _git(workspace, "remote", "set-url", "--push", "origin", _CANONICAL_PUSH_URL)

    state = configure_existing_workspace(source, workspace, "verified")

    assert state == ExistingWorkspaceState(
        branch="agent/verified",
        fetch_url=source.resolve().as_uri(),
        push_url=_CANONICAL_PUSH_URL,
        author_name="First Agent",
        author_email="agent@first-agent.local",
        remote_action="verified",
    )


def test_existing_workspace_repairs_local_push_and_sets_identity(tmp_path: Path) -> None:
    """class=C1 path=P13 claim=CT2 kill-check=remove local-push repair producer."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "repair")
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == source.resolve().as_uri()

    state = configure_existing_workspace(source, workspace, "repair")

    assert state.remote_action == "repaired"
    assert state.push_url == _CANONICAL_PUSH_URL
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == _CANONICAL_PUSH_URL
    assert _git(workspace, "config", "--local", "--get", "user.name").stdout.strip() == "First Agent"
    assert _git(workspace, "config", "--local", "--get", "user.email").stdout.strip() == ("agent@first-agent.local")


def test_existing_workspace_preserves_supported_custom_push_and_worktree(tmp_path: Path) -> None:
    """class=C3 path=P14 claim=Q4 kill-check=remove custom preservation branch."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "custom")
    custom_push = "git@github.com:operator/custom-fork.git"
    _git(workspace, "remote", "set-url", "--push", "origin", custom_push)
    uncommitted = workspace / "operator-work.txt"
    uncommitted.write_text("preserve\n", encoding="utf-8")

    state = configure_existing_workspace(source, workspace, "custom")

    assert state.remote_action == "preserved_custom"
    assert state.push_url == custom_push
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == custom_push
    assert uncommitted.read_text(encoding="utf-8") == "preserve\n"
    assert _git(workspace, "branch", "--show-current").stdout.strip() == "agent/custom"


def test_existing_workspace_custom_classification_reads_supplied_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """class=C2 claim=Q4 kill-check=replace custom-classification source with None."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "custom-source-path")
    custom = "git@github.com:operator/custom.git"
    _git(workspace, "remote", "set-url", "--push", "origin", custom)
    original_run_git = workspace_module._run_git
    push_read_paths: list[str] = []

    def record_push_reads(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        if "get-url" in arguments and "--push" in arguments:
            push_read_paths.append(arguments[1])
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", record_push_reads)
    state = configure_existing_workspace(source, workspace, "custom-source-path")

    assert state.remote_action == "preserved_custom"
    assert push_read_paths == [str(workspace), str(source), str(workspace)]


def test_existing_workspace_explicit_override_replaces_custom_push(tmp_path: Path) -> None:
    """class=C1 path=P14 matrix=M8 claim=Q3 kill-check=remove override precedence."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "custom-override")
    _git(
        workspace,
        "remote",
        "set-url",
        "--push",
        "origin",
        "git@github.com:operator/old-custom.git",
    )

    state = configure_existing_workspace(
        source,
        workspace,
        "custom-override",
        "https://github.com/fork-owner/new-target",
    )

    assert state.remote_action == "repaired"
    assert state.push_url == "git@github.com:fork-owner/new-target.git"
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == state.push_url


def test_existing_workspace_preserves_unsafe_custom_push_with_redacted_state(tmp_path: Path) -> None:
    """class=C3 path=P14 claim=Q5 kill-check=remove custom-output redaction."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "unsafe-custom")
    unsafe_push = "https://user:secret@github.com/operator/custom.git?token=hidden"
    _git(workspace, "remote", "set-url", "--push", "origin", unsafe_push)

    state = configure_existing_workspace(source, workspace, "unsafe-custom")

    assert state.remote_action == "preserved_custom"
    assert state.push_url == "<preserved-custom-redacted>"
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == unsafe_push
    assert "secret" not in repr(state)
    assert "hidden" not in repr(state)


def test_existing_workspace_branch_mismatch_fails_before_config_mutation(tmp_path: Path) -> None:
    """class=C3 path=P2 claim=CT2 kill-check=remove branch equality gate."""

    source = _make_git_source(tmp_path)
    workspace = tmp_path / "workspace"
    subprocess.run(
        ["git", "clone", source.resolve().as_uri(), str(workspace)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "expected")

    assert caught.value.code == "postcondition_failed"
    assert caught.value.detail == "workspace branch does not match managed session branch"
    assert _git(workspace, "config", "--local", "--get", "user.name", check=False).returncode == 1
    assert _git(workspace, "branch", "--show-current").stdout.strip() == "main"


def test_existing_workspace_fetch_mismatch_fails_without_remote_or_identity_repair(tmp_path: Path) -> None:
    """class=C3 path=P2 claim=CT2 kill-check=remove local-fetch authority gate."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "fetch-mismatch")
    other_fetch = (tmp_path / "other-source").resolve().as_uri()
    _git(workspace, "remote", "set-url", "origin", other_fetch)

    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "fetch-mismatch")

    assert caught.value.code == "postcondition_failed"
    assert caught.value.stage == "verify_postconditions"
    assert caught.value.detail == "workspace fetch URL does not match managed source"
    assert _git(workspace, "remote", "get-url", "origin").stdout.strip() == other_fetch
    assert _git(workspace, "config", "--local", "--get", "user.name", check=False).returncode == 1


def test_configure_existing_cli_redacts_custom_warning_and_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """class=C0/C3 claim=Q5 kill-check=serialize raw custom push URL."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "cli-custom")
    unsafe_push = "https://user:secret@github.com/operator/custom.git?token=hidden"
    _git(workspace, "remote", "set-url", "--push", "origin", unsafe_push)
    monkeypatch.delenv("FA_REPO_PUSH_URL", raising=False)

    assert (
        workspace_module._main(
            [
                "configure-existing",
                "--source",
                str(source),
                "--workspace",
                str(workspace),
                "--session-id",
                "cli-custom",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["push_url"] == "<preserved-custom-redacted>"
    assert payload["remote_action"] == "preserved_custom"
    assert captured.err == "[WORKSPACE_BOOTSTRAP] preserving operator-customized origin.pushurl\n"
    assert "secret" not in captured.out + captured.err
    assert "hidden" not in captured.out + captured.err


def test_existing_workspace_rejects_non_git_source_and_workspace(tmp_path: Path) -> None:
    """class=C3 claim=CT2 kill-check=remove normal-checkout aggregate gate."""

    invalid_source = tmp_path / "invalid-source"
    invalid_source.mkdir()
    invalid_workspace = tmp_path / "invalid-workspace"
    invalid_workspace.mkdir()

    with pytest.raises(WorkspaceProvisionError) as source_error:
        configure_existing_workspace(invalid_source, invalid_workspace, "invalid")
    assert (
        source_error.value.code,
        source_error.value.stage,
        source_error.value.detail,
    ) == (
        "source_not_git",
        "validate_source",
        "source is not a normal Git checkout",
    )

    valid_root = tmp_path / "valid"
    valid_root.mkdir()
    source = _make_git_source(valid_root)
    with pytest.raises(WorkspaceProvisionError) as workspace_error:
        configure_existing_workspace(source, invalid_workspace, "invalid")
    assert (
        workspace_error.value.code,
        workspace_error.value.stage,
        workspace_error.value.detail,
    ) == (
        "source_not_git",
        "validate_source",
        "workspace is not a normal Git checkout",
    )


def test_existing_workspace_exact_empty_override_uses_source_authority(tmp_path: Path) -> None:
    """class=C1 claim=CT2 kill-check=mutate exact-empty desired-URL fallback."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "empty-existing")

    state = configure_existing_workspace(source, workspace, "empty-existing", "")

    assert state.remote_action == "repaired"
    assert state.push_url == _CANONICAL_PUSH_URL


def test_existing_workspace_exact_empty_override_preserves_custom_push_url(tmp_path: Path) -> None:
    """class=C1 claim=Q3/Q5 kill-check=treat exact-empty as explicit override."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "empty-custom")
    custom = "git@github.com:owner/custom.git"
    _git(workspace, "remote", "set-url", "--push", "origin", custom)

    state = configure_existing_workspace(source, workspace, "empty-custom", "")

    assert state.remote_action == "preserved_custom"
    assert state.push_url == custom
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == custom


def test_existing_workspace_missing_source_push_authority_is_structured(tmp_path: Path) -> None:
    """class=C3 claim=CT2 kill-check=remove desired push error mapping."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "missing-source-push")
    _git(source, "remote", "remove", "origin")

    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "missing-source-push")

    assert caught.value.code == "push_url_unavailable"
    assert caught.value.stage == "resolve_push_url"


@pytest.mark.parametrize("source_push_url", [None, "file:///not-a-publication-remote"])
def test_existing_workspace_preserves_custom_when_source_push_authority_is_unusable(
    tmp_path: Path,
    source_push_url: str | None,
) -> None:
    """class=C1/C3 claim=Q4/Q5 kill-check=resolve source before classifying custom push."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "custom-no-source")
    custom = "https://user:secret@github.com/operator/custom.git?token=hidden"
    _git(workspace, "remote", "set-url", "--push", "origin", custom)
    if source_push_url is None:
        _git(source, "remote", "remove", "origin")
    else:
        _git(source, "remote", "set-url", "--push", "origin", source_push_url)

    state = configure_existing_workspace(source, workspace, "custom-no-source")

    assert state.remote_action == "preserved_custom"
    assert state.push_url == "<preserved-custom-redacted>"
    assert _git(workspace, "remote", "get-url", "--push", "origin").stdout.strip() == custom
    assert _git(workspace, "config", "--local", "--get", "user.name").stdout.strip() == "First Agent"
    assert _git(workspace, "config", "--local", "--get", "user.email").stdout.strip() == "agent@first-agent.local"


def test_existing_workspace_invalid_branch_is_structured_before_mutation(tmp_path: Path) -> None:
    """class=C3 claim=CT2 kill-check=remove aggregate check-ref-format mapping."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "valid")

    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "a..b")

    assert caught.value.code == "invalid_branch"
    assert caught.value.stage == "validate_branch"
    assert _git(workspace, "config", "--local", "--get", "user.name", check=False).returncode == 1


@pytest.mark.parametrize(
    ("failed_verify_call", "expected_code"),
    [
        (0, "postcondition_failed"),
        (1, "postcondition_failed"),
        (2, "postcondition_failed"),
        (3, "git_command_failed"),
        (4, "git_command_failed"),
        (5, "git_command_failed"),
        (6, "git_command_failed"),
        (7, "git_command_failed"),
    ],
)
def test_each_existing_workspace_verify_failure_preserves_stage_and_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failed_verify_call: int,
    expected_code: workspace_module.WorkspaceProvisionCode,
) -> None:
    """class=C3 claim=CT2 kill-check=mutate verify command telemetry."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "verify-failure")
    _git(workspace, "remote", "set-url", "--push", "origin", _CANONICAL_PUSH_URL)
    original_run_git = workspace_module._run_git
    verify_calls = 0

    def fail_selected_verify(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        nonlocal verify_calls
        if stage == "verify_postconditions":
            current = verify_calls
            verify_calls += 1
            if current == failed_verify_call:
                raise WorkspaceProvisionError(failure_code, stage, "forced verify failure")
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", fail_selected_verify)
    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "verify-failure")

    assert caught.value.code == expected_code
    assert caught.value.stage == "verify_postconditions"


@pytest.mark.parametrize("identity_key", ["user.name", "user.email"])
def test_each_existing_workspace_identity_failure_has_set_identity_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_key: str,
) -> None:
    """class=C3 claim=CT2 kill-check=mutate identity configuration telemetry."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "identity-failure")
    original_run_git = workspace_module._run_git

    def fail_identity(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        if identity_key in arguments:
            raise WorkspaceProvisionError("git_command_failed", stage, "forced identity failure")
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", fail_identity)
    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "identity-failure")

    assert caught.value.code == "git_command_failed"
    assert caught.value.stage == "set_identity"


def test_existing_workspace_set_push_failure_has_exact_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """class=C3 claim=CT2 kill-check=mutate set-push command telemetry."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "set-push-failure")
    original_run_git = workspace_module._run_git

    def fail_set_push(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        if "set-url" in arguments:
            raise WorkspaceProvisionError(failure_code, stage, "forced set-push failure")
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", fail_set_push)
    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "set-push-failure")

    assert caught.value.code == "git_command_failed"
    assert caught.value.stage == "set_push_url"


def test_existing_workspace_identity_readback_uses_workspace_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """class=C2 claim=CT2 kill-check=replace final read-back target with None."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "readback-path")
    original_run_git = workspace_module._run_git
    identity_read_paths: list[str] = []

    def record_identity_reads(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        if "--get" in arguments and ("user.name" in arguments or "user.email" in arguments):
            identity_read_paths.append(arguments[1])
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", record_identity_reads)
    state = configure_existing_workspace(source, workspace, "readback-path")

    assert state.author_name == "First Agent"
    assert state.author_email == "agent@first-agent.local"
    assert identity_read_paths == [str(workspace), str(workspace)]


def test_fresh_workspace_identity_readback_uses_target_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """class=C2 claim=CT2 kill-check=replace fresh read-back target with None."""

    source = _make_git_source(tmp_path)
    target = tmp_path / "workspace"
    original_run_git = workspace_module._run_git
    identity_read_paths: list[str] = []

    def record_identity_reads(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        if "--get" in arguments and ("user.name" in arguments or "user.email" in arguments):
            identity_read_paths.append(arguments[1])
        return original_run_git(arguments, stage=stage, failure_code=failure_code)

    monkeypatch.setattr(workspace_module, "_run_git", record_identity_reads)
    state = provision_git_workspace(source, target, "readback-path")

    assert state.author_name == "First Agent"
    assert state.author_email == "agent@first-agent.local"
    assert identity_read_paths == [str(target), str(target)]


def test_existing_workspace_final_readback_mismatch_is_exact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """class=C3 claim=CT2 kill-check=remove final existing-state equality gate."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "final-mismatch")
    _git(workspace, "remote", "set-url", "--push", "origin", _CANONICAL_PUSH_URL)
    original_run_git = workspace_module._run_git
    branch_reads = 0

    def wrong_final_branch(
        arguments: tuple[str, ...],
        *,
        stage: workspace_module.WorkspaceProvisionStage,
        failure_code: workspace_module.WorkspaceProvisionCode = "git_command_failed",
    ) -> str:
        nonlocal branch_reads
        result = original_run_git(arguments, stage=stage, failure_code=failure_code)
        if "symbolic-ref" in arguments:
            branch_reads += 1
            if branch_reads == 2:
                return "main"
        return result

    monkeypatch.setattr(workspace_module, "_run_git", wrong_final_branch)
    with pytest.raises(WorkspaceProvisionError) as caught:
        configure_existing_workspace(source, workspace, "final-mismatch")

    assert (
        caught.value.code,
        caught.value.stage,
        caught.value.detail,
    ) == (
        "postcondition_failed",
        "verify_postconditions",
        "existing workspace read-back did not match configured state",
    )


def test_configure_existing_cli_requires_all_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    """class=C0 claim=CT2 kill-check=remove required CLI argument contract."""

    with pytest.raises(SystemExit) as caught:
        workspace_module._main(["configure-existing"])

    assert caught.value.code == 2
    assert "--source" in capsys.readouterr().err


def test_configure_existing_cli_requires_subcommand_and_stable_program_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """class=C0 claim=CT2 kill-check=remove subcommand/prog CLI contracts."""

    with pytest.raises(SystemExit) as caught:
        workspace_module._main([])

    assert caught.value.code == 2
    assert capsys.readouterr().err.startswith("usage: python -m fa.session.workspace")


@pytest.mark.parametrize("missing_option", ["--source", "--workspace", "--session-id"])
def test_configure_existing_cli_requires_each_option(
    missing_option: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """class=C0 claim=CT2 kill-check=remove one required option declaration."""

    args = [
        "configure-existing",
        "--source",
        "/source",
        "--workspace",
        "/workspace",
        "--session-id",
        "required",
    ]
    option_index = args.index(missing_option)
    del args[option_index : option_index + 2]

    with pytest.raises(SystemExit) as caught:
        workspace_module._main(args)

    assert caught.value.code == 2
    assert missing_option in capsys.readouterr().err


def test_configure_existing_cli_error_is_stderr_only_and_exit_two(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """class=C0/C3 claim=CT2 kill-check=mutate CLI error channel/code."""

    source = _make_git_source(tmp_path)
    workspace = tmp_path / "workspace"
    subprocess.run(
        ["git", "clone", source.resolve().as_uri(), str(workspace)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    rc = workspace_module._main(
        [
            "configure-existing",
            "--source",
            str(source),
            "--workspace",
            str(workspace),
            "--session-id",
            "expected",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert captured.err == (
        "fa.session.workspace: postcondition_failed [verify_postconditions]: "
        "workspace branch does not match managed session branch\n"
    )


def test_configure_existing_cli_consumes_push_override_and_emits_sorted_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """class=C0/C1 claim=Q3 kill-check=drop CLI override/JSON contract."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "cli-override")
    monkeypatch.setenv("FA_REPO_PUSH_URL", "https://github.com/fork-owner/cli-target")

    rc = workspace_module._main(
        [
            "configure-existing",
            "--source",
            str(source),
            "--workspace",
            str(workspace),
            "--session-id",
            "cli-override",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    expected = ExistingWorkspaceState(
        branch="agent/cli-override",
        fetch_url=source.resolve().as_uri(),
        push_url="git@github.com:fork-owner/cli-target.git",
        author_name="First Agent",
        author_email="agent@first-agent.local",
        remote_action="repaired",
    )
    assert captured.out == json.dumps(asdict(expected), sort_keys=True) + "\n"
    assert captured.err == ""


def test_configure_existing_cli_exact_empty_environment_preserves_custom_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """class=C0/C1 claim=CT1/Q5 kill-check=treat empty environment as override."""

    source = _make_git_source(tmp_path)
    workspace = _make_existing_workspace(source, tmp_path / "workspace", "cli-empty")
    custom = "git@github.com:owner/custom.git"
    _git(workspace, "remote", "set-url", "--push", "origin", custom)
    monkeypatch.setenv("FA_REPO_PUSH_URL", "")

    rc = workspace_module._main(
        [
            "configure-existing",
            "--source",
            str(source),
            "--workspace",
            str(workspace),
            "--session-id",
            "cli-empty",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 0
    expected = ExistingWorkspaceState(
        branch="agent/cli-empty",
        fetch_url=source.resolve().as_uri(),
        push_url=custom,
        author_name="First Agent",
        author_email="agent@first-agent.local",
        remote_action="preserved_custom",
    )
    assert captured.out == json.dumps(asdict(expected), sort_keys=True) + "\n"
    assert captured.err == "[WORKSPACE_BOOTSTRAP] preserving operator-customized origin.pushurl\n"
