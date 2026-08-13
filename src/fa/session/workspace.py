"""Deterministic Git workspace provisioning for managed sessions.

The module owns the Git-specific half of session workspace creation.  It keeps
remote routing and local checkout invariants out of the generic session manager,
which still owns plain-directory fallback provisioning for embedders and tests.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

WorkspaceProvisionCode = Literal[
    "source_not_git",
    "source_revision_unavailable",
    "target_exists",
    "invalid_branch",
    "push_url_unavailable",
    "push_url_invalid",
    "git_unavailable",
    "git_timeout",
    "git_command_failed",
    "postcondition_failed",
]
WorkspaceProvisionStage = Literal[
    "validate_source",
    "capture_source_revision",
    "validate_branch",
    "resolve_push_url",
    "clone",
    "checkout_branch",
    "set_push_url",
    "set_identity",
    "verify_postconditions",
]
ExistingRemoteAction = Literal["verified", "repaired", "preserved_custom"]

_INVALID_PUSH_URL_DETAIL = "push URL must be a credential-free GitHub HTTPS or SSH repository URL"
_REPOSITORY_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")
_SCP_GITHUB_URL = re.compile(r"git@github\.com:([^/]+)/([^/]+)")
_URL_USERINFO = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")
_URL_SECRET_SUFFIX = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*://[^\s?#]*)[?#][^\s]*")
_SENSITIVE_ASSIGNMENT = re.compile(r"(?i)\b(password|passwd|token|secret|api[_-]?key)=[^\s&]+")

_GIT_COMMAND_TIMEOUT_SECONDS = 120
_MAX_ERROR_DETAIL_CHARS = 4096
_AGENT_AUTHOR_NAME = "First Agent"
_AGENT_AUTHOR_EMAIL = "agent@first-agent.local"
_PRESERVED_CUSTOM_REDACTED = "<preserved-custom-redacted>"
_PRESERVED_CUSTOM_WARNING = "[WORKSPACE_BOOTSTRAP] preserving operator-customized origin.pushurl"


@dataclass(frozen=True, slots=True)
class GitWorkspaceState:
    """Verified Git state returned after a managed workspace is provisioned."""

    source_revision: str
    target_revision: str
    branch: str
    fetch_url: str
    push_url: str
    author_name: str
    author_email: str


@dataclass(frozen=True, slots=True)
class ExistingWorkspaceState:
    """Verified configuration of an entrypoint-created managed workspace."""

    branch: str
    fetch_url: str
    push_url: str
    author_name: str
    author_email: str
    remote_action: ExistingRemoteAction


class WorkspaceProvisionError(RuntimeError):
    """Structured private failure translated at the session-manager boundary."""

    __slots__ = ("_code", "_detail", "_stage")

    def __init__(
        self,
        code: WorkspaceProvisionCode,
        stage: WorkspaceProvisionStage,
        detail: str,
    ) -> None:
        self._code = code
        self._stage = stage
        self._detail = detail
        super().__init__(f"{code} [{stage}]: {detail}")

    @property
    def code(self) -> WorkspaceProvisionCode:
        return self._code

    @property
    def stage(self) -> WorkspaceProvisionStage:
        return self._stage

    @property
    def detail(self) -> str:
        return self._detail


def _invalid_push_url() -> WorkspaceProvisionError:
    return WorkspaceProvisionError(
        "push_url_invalid",
        "resolve_push_url",
        _INVALID_PUSH_URL_DETAIL,
    )


def _canonical_repository(owner: str, repository: str) -> str:
    if repository.endswith(".git"):
        repository = repository[:-4]
    segments = (owner, repository)
    if any(
        not segment or _REPOSITORY_SEGMENT.fullmatch(segment) is None or set(segment) == {"."} for segment in segments
    ):
        raise _invalid_push_url()
    return f"git@github.com:{owner}/{repository}.git"


def normalize_push_url(raw: str) -> str:
    """Return one canonical GitHub SSH URL or raise a redacted typed error."""

    if not isinstance(raw, str) or raw != raw.strip() or any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise _invalid_push_url()

    scp_match = _SCP_GITHUB_URL.fullmatch(raw)
    if scp_match is not None:
        return _canonical_repository(*scp_match.groups())

    try:
        parsed = urlsplit(raw)
    except ValueError as exc:
        raise _invalid_push_url() from exc
    if parsed.query or parsed.fragment or parsed.path.count("/") != 2:
        raise _invalid_push_url()
    empty, owner, repository = parsed.path.split("/")
    if empty:
        raise _invalid_push_url()

    valid_https = parsed.scheme == "https" and parsed.netloc == "github.com"
    valid_ssh = parsed.scheme == "ssh" and parsed.netloc == "git@github.com"
    if not (valid_https or valid_ssh):
        raise _invalid_push_url()
    return _canonical_repository(owner, repository)


def _safe_detail(value: str) -> str:
    redacted = _URL_USERINFO.sub(r"\1<redacted>@", value)
    redacted = _URL_SECRET_SUFFIX.sub(r"\1?<redacted>", redacted)
    redacted = _SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<redacted>", redacted)
    control_safe = "".join(char if char.isprintable() else f"\\x{ord(char):02x}" for char in redacted)
    return control_safe[:_MAX_ERROR_DETAIL_CHARS]


def _run_git(
    arguments: tuple[str, ...],
    *,
    stage: WorkspaceProvisionStage,
    failure_code: WorkspaceProvisionCode = "git_command_failed",
) -> str:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    command = ["git", *arguments]
    try:
        # Argument-vector execution only; branch/remote values are validated and
        # source/target paths are caller-contained by SessionManager.
        completed = subprocess.run(  # noqa: S603
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_COMMAND_TIMEOUT_SECONDS,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise WorkspaceProvisionError("git_unavailable", stage, "git executable is not available") from exc
    except subprocess.TimeoutExpired as exc:
        raise WorkspaceProvisionError(
            "git_timeout",
            stage,
            f"git command exceeded {_GIT_COMMAND_TIMEOUT_SECONDS} seconds",
        ) from exc
    if completed.returncode != 0:
        detail = f"git command failed with exit code {completed.returncode}"
        stderr = completed.stderr.strip()
        if stderr:
            detail = f"{detail}: {stderr}"
        raise WorkspaceProvisionError(failure_code, stage, _safe_detail(detail))
    return completed.stdout.strip()


def _remove_created_target(target: Path) -> None:
    try:
        if target.is_symlink():
            target.unlink()
        elif target.exists():
            shutil.rmtree(target)
    except OSError:
        # SessionManager has a second best-effort rollback boundary. Preserve the
        # original provisioning failure rather than replacing it with cleanup I/O.
        pass


def _read_verified_workspace_state(
    target: Path,
    *,
    source_revision: str,
    branch: str,
    fetch_url: str,
    push_url: str,
) -> GitWorkspaceState:
    target_revision = _run_git(
        ("-C", str(target), "rev-parse", "--verify", "HEAD^{commit}"),
        stage="verify_postconditions",
    )
    actual_branch = _run_git(
        ("-C", str(target), "symbolic-ref", "--quiet", "--short", "HEAD"),
        stage="verify_postconditions",
    )
    actual_fetch_url = _run_git(
        ("-C", str(target), "remote", "get-url", "origin"),
        stage="verify_postconditions",
    )
    actual_push_url = _run_git(
        ("-C", str(target), "remote", "get-url", "--push", "origin"),
        stage="verify_postconditions",
    )
    author_name = _run_git(
        ("-C", str(target), "config", "--local", "--get", "user.name"),
        stage="verify_postconditions",
    )
    author_email = _run_git(
        ("-C", str(target), "config", "--local", "--get", "user.email"),
        stage="verify_postconditions",
    )
    status = _run_git(
        ("-C", str(target), "status", "--porcelain=v1", "--untracked-files=all"),
        stage="verify_postconditions",
    )
    expected = (
        source_revision,
        branch,
        fetch_url,
        push_url,
        _AGENT_AUTHOR_NAME,
        _AGENT_AUTHOR_EMAIL,
        "",
    )
    actual = (
        target_revision,
        actual_branch,
        actual_fetch_url,
        actual_push_url,
        author_name,
        author_email,
        status,
    )
    if actual != expected:
        raise WorkspaceProvisionError(
            "postcondition_failed",
            "verify_postconditions",
            "workspace read-back did not match provisioned state",
        )
    return GitWorkspaceState(
        source_revision=source_revision,
        target_revision=target_revision,
        branch=actual_branch,
        fetch_url=actual_fetch_url,
        push_url=actual_push_url,
        author_name=author_name,
        author_email=author_email,
    )


def provision_git_workspace(
    source: Path,
    target: Path,
    session_id: str,
    push_url_override: str | None = None,
) -> GitWorkspaceState:
    """Create and verify one clean managed Git checkout at a captured commit."""

    source = Path(source).expanduser().resolve()
    raw_target = Path(target).expanduser()
    if raw_target.exists() or raw_target.is_symlink():
        raise WorkspaceProvisionError("target_exists", "validate_source", "target already exists")
    target = raw_target.resolve()
    git_directory = source / ".git"
    if not git_directory.is_dir() or git_directory.is_symlink():
        raise WorkspaceProvisionError("source_not_git", "validate_source", "source is not a normal Git checkout")

    source_revision = _run_git(
        ("-C", str(source), "rev-parse", "--verify", "HEAD^{commit}"),
        stage="capture_source_revision",
        failure_code="source_revision_unavailable",
    )
    branch = f"agent/{session_id}"
    _run_git(
        ("check-ref-format", "--branch", branch),
        stage="validate_branch",
        failure_code="invalid_branch",
    )

    if push_url_override is not None and push_url_override != "":
        push_url = normalize_push_url(push_url_override)
    else:
        source_push_url = _run_git(
            ("-C", str(source), "remote", "get-url", "--push", "origin"),
            stage="resolve_push_url",
            failure_code="push_url_unavailable",
        )
        push_url = normalize_push_url(source_push_url)

    fetch_url = source.as_uri()
    try:
        _run_git(
            ("clone", "--no-checkout", "--", fetch_url, str(target)),
            stage="clone",
        )
        _run_git(
            ("-C", str(target), "switch", "-c", branch, source_revision),
            stage="checkout_branch",
        )
        _run_git(
            ("-C", str(target), "remote", "set-url", "--push", "origin", push_url),
            stage="set_push_url",
        )
        _run_git(
            ("-C", str(target), "config", "--local", "user.name", _AGENT_AUTHOR_NAME),
            stage="set_identity",
        )
        _run_git(
            ("-C", str(target), "config", "--local", "user.email", _AGENT_AUTHOR_EMAIL),
            stage="set_identity",
        )
        return _read_verified_workspace_state(
            target,
            source_revision=source_revision,
            branch=branch,
            fetch_url=fetch_url,
            push_url=push_url,
        )
    except BaseException:
        _remove_created_target(target)
        raise


def _require_normal_checkout(path: Path, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    git_directory = resolved / ".git"
    if not git_directory.is_dir() or git_directory.is_symlink():
        raise WorkspaceProvisionError(
            "source_not_git",
            "validate_source",
            f"{label} is not a normal Git checkout",
        )
    return resolved


def _desired_push_url(source: Path, push_url_override: str | None) -> str:
    if push_url_override is not None and push_url_override != "":
        return normalize_push_url(push_url_override)
    source_push_url = _run_git(
        ("-C", str(source), "remote", "get-url", "--push", "origin"),
        stage="resolve_push_url",
        failure_code="push_url_unavailable",
    )
    return normalize_push_url(source_push_url)


def _preserved_push_url_for_output(push_url: str) -> str:
    try:
        normalize_push_url(push_url)
    except WorkspaceProvisionError:
        return _PRESERVED_CUSTOM_REDACTED
    return push_url


def configure_existing_workspace(
    source: Path,
    workspace: Path,
    session_id: str,
    push_url_override: str | None = None,
) -> ExistingWorkspaceState:
    """Validate and configure an existing managed workspace without checkout/reset."""

    source = _require_normal_checkout(source, label="source")
    workspace = _require_normal_checkout(workspace, label="workspace")
    expected_branch = f"agent/{session_id}"
    _run_git(
        ("check-ref-format", "--branch", expected_branch),
        stage="validate_branch",
        failure_code="invalid_branch",
    )
    actual_branch = _run_git(
        ("-C", str(workspace), "symbolic-ref", "--quiet", "--short", "HEAD"),
        stage="verify_postconditions",
        failure_code="postcondition_failed",
    )
    if actual_branch != expected_branch:
        raise WorkspaceProvisionError(
            "postcondition_failed",
            "verify_postconditions",
            "workspace branch does not match managed session branch",
        )

    expected_fetch_url = source.as_uri()
    actual_fetch_url = _run_git(
        ("-C", str(workspace), "remote", "get-url", "origin"),
        stage="verify_postconditions",
        failure_code="postcondition_failed",
    )
    if actual_fetch_url != expected_fetch_url:
        raise WorkspaceProvisionError(
            "postcondition_failed",
            "verify_postconditions",
            "workspace fetch URL does not match managed source",
        )

    explicit_override = push_url_override is not None and push_url_override != ""
    current_push_url = _run_git(
        ("-C", str(workspace), "remote", "get-url", "--push", "origin"),
        stage="verify_postconditions",
        failure_code="postcondition_failed",
    )
    local_push_url = current_push_url == actual_fetch_url and urlsplit(actual_fetch_url).scheme == "file"
    desired_push_url: str | None
    if explicit_override or local_push_url:
        desired_push_url = _desired_push_url(source, push_url_override)
    else:
        try:
            desired_push_url = _desired_push_url(source, None)
        except WorkspaceProvisionError as exc:
            if exc.code not in ("push_url_unavailable", "push_url_invalid"):
                raise
            desired_push_url = None

    if desired_push_url is not None and current_push_url == desired_push_url:
        remote_action: ExistingRemoteAction = "verified"
        expected_push_url = desired_push_url
        output_push_url = desired_push_url
    elif desired_push_url is not None and (explicit_override or local_push_url):
        _run_git(
            ("-C", str(workspace), "remote", "set-url", "--push", "origin", desired_push_url),
            stage="set_push_url",
        )
        remote_action = "repaired"
        expected_push_url = desired_push_url
        output_push_url = desired_push_url
    else:
        remote_action = "preserved_custom"
        expected_push_url = current_push_url
        output_push_url = _preserved_push_url_for_output(current_push_url)

    _run_git(
        ("-C", str(workspace), "config", "--local", "user.name", _AGENT_AUTHOR_NAME),
        stage="set_identity",
    )
    _run_git(
        ("-C", str(workspace), "config", "--local", "user.email", _AGENT_AUTHOR_EMAIL),
        stage="set_identity",
    )

    verified_branch = _run_git(
        ("-C", str(workspace), "symbolic-ref", "--quiet", "--short", "HEAD"),
        stage="verify_postconditions",
    )
    verified_fetch_url = _run_git(
        ("-C", str(workspace), "remote", "get-url", "origin"),
        stage="verify_postconditions",
    )
    verified_push_url = _run_git(
        ("-C", str(workspace), "remote", "get-url", "--push", "origin"),
        stage="verify_postconditions",
    )
    author_name = _run_git(
        ("-C", str(workspace), "config", "--local", "--get", "user.name"),
        stage="verify_postconditions",
    )
    author_email = _run_git(
        ("-C", str(workspace), "config", "--local", "--get", "user.email"),
        stage="verify_postconditions",
    )
    if (
        verified_branch,
        verified_fetch_url,
        verified_push_url,
        author_name,
        author_email,
    ) != (
        expected_branch,
        expected_fetch_url,
        expected_push_url,
        _AGENT_AUTHOR_NAME,
        _AGENT_AUTHOR_EMAIL,
    ):
        raise WorkspaceProvisionError(
            "postcondition_failed",
            "verify_postconditions",
            "existing workspace read-back did not match configured state",
        )
    return ExistingWorkspaceState(
        branch=verified_branch,
        fetch_url=verified_fetch_url,
        push_url=output_push_url,
        author_name=author_name,
        author_email=author_email,
        remote_action=remote_action,
    )


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m fa.session.workspace")
    subparsers = parser.add_subparsers(required=True)
    configure = subparsers.add_parser("configure-existing")
    configure.add_argument("--source", required=True)
    configure.add_argument("--workspace", required=True)
    configure.add_argument("--session-id", required=True)
    args = parser.parse_args(argv)

    push_url_override = os.environ.get("FA_REPO_PUSH_URL")
    try:
        state = configure_existing_workspace(
            source=Path(args.source),
            workspace=Path(args.workspace),
            session_id=args.session_id,
            push_url_override=push_url_override,
        )
    except WorkspaceProvisionError as exc:
        print(
            f"fa.session.workspace: {exc.code} [{exc.stage}]: {exc.detail}",
            file=sys.stderr,
        )
        return 2
    if state.remote_action == "preserved_custom":
        print(_PRESERVED_CUSTOM_WARNING, file=sys.stderr)
    print(json.dumps(asdict(state), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
