"""Operator prewarm for immutable managed project environments.

The session execution path never builds an environment. This tool runs the
approved, digest-pinned image against a disposable copy of one locked source,
then atomically publishes its `.venv` under the service's approved cache. The
source checkout is never mounted into the build container or modified.

Run with `python -m fa.execution.environment_artifact --source /path/to/repo`.
The service config supplies both the cache root and the approved execution
profile; callers cannot provide an arbitrary image or cache destination.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from fa.config import DEFAULT_CONFIG_PATH
from fa.execution import workspace as workspace_authority
from fa.execution.composition import _service_config
from fa.execution.profiles import ExecutionProfile
from fa.execution.service import ServiceConfig
from fa.execution.supervisor import SupervisorError
from fa.execution.types import ExecutionContractError
from fa.execution.view_io import _DIRECTORY, _rename_directory

_BUILD_TIMEOUT_SECONDS = 900
_IMAGE_UV = "/usr/local/bin/uv"
_IMAGE_PROJECT = "/workspace"
_BUILD_INPUT_FILES = ("pyproject.toml", "uv.lock", "README.md")


class EnvironmentArtifactError(RuntimeError):
    """Closed operator-facing failure while producing one approved artifact."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _identity(source: Path, profile: ExecutionProfile) -> tuple[dict[str, Any], str]:
    try:
        fd = workspace_authority._open_absolute(source)
    except (OSError, ExecutionContractError):
        raise EnvironmentArtifactError("source path could not be safely opened") from None
    try:
        try:
            pyproject = workspace_authority._read_environment_input(fd, "pyproject.toml")
            identity = workspace_authority._environment_identity(fd, profile)
        except SupervisorError:
            raise EnvironmentArtifactError("source lock inputs are unsafe or unreadable") from None
    finally:
        os.close(fd)
    if identity["pyproject_sha256"] is None or identity["uv_lock_sha256"] is None or pyproject is None:
        raise EnvironmentArtifactError("source must contain regular pyproject.toml and uv.lock files")
    try:
        project = tomllib.loads(pyproject.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        raise EnvironmentArtifactError("source pyproject.toml is invalid") from None
    if project.get("project", {}).get("name") != "first-agent":
        raise EnvironmentArtifactError("this prewarmer currently accepts only the First-Agent source")
    return identity, hashlib.sha256(workspace_authority._canonical(identity)).hexdigest()


def _check_cache(cache: Path) -> int:
    try:
        fd = workspace_authority._open_absolute(cache)
    except (OSError, ExecutionContractError):
        raise EnvironmentArtifactError("approved_cache must exist and contain no symlink components") from None
    try:
        info = os.fstat(fd)
    except OSError:
        os.close(fd)
        raise EnvironmentArtifactError("approved_cache could not be inspected") from None
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        os.close(fd)
        raise EnvironmentArtifactError("approved_cache ownership or permissions are unsafe")
    return fd


def _copy_build_inputs(source: Path, destination: Path) -> None:
    """Copy only package build inputs; reject symlinks in copied project code."""
    for name in _BUILD_INPUT_FILES:
        path = source / name
        try:
            info = path.lstat()
        except OSError:
            raise EnvironmentArtifactError(f"locked build input is missing: {name}") from None
        if not stat.S_ISREG(info.st_mode):
            raise EnvironmentArtifactError(f"locked build input is not a regular file: {name}")
        shutil.copyfile(path, destination / name)
    source_code = source / "src"
    if source_code.is_symlink() or not source_code.is_dir() or not (source_code / "fa").is_dir():
        raise EnvironmentArtifactError("source/src/fa must be the First-Agent package directory")
    for root, directories, files in os.walk(source_code, followlinks=False):
        for name in (*directories, *files):
            if (Path(root) / name).is_symlink():
                raise EnvironmentArtifactError("symlinks are not accepted in prewarm source code")
    shutil.copytree(source_code, destination / "src", symlinks=False)


def _docker_argv(source: Path, profile: ExecutionProfile) -> list[str]:
    mount = f"type=bind,source={source},target={_IMAGE_PROJECT}"
    if "," in str(source):
        raise EnvironmentArtifactError("temporary build path cannot be represented as a Docker mount")
    return [
        "docker",
        "run",
        "--rm",
        "--network=bridge",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--pids-limit",
        str(profile.pids_limit),
        "--memory",
        str(profile.memory_bytes),
        "--memory-swap",
        str(profile.memory_bytes),
        "--cpus",
        f"{profile.nano_cpus / 1_000_000_000:g}",
        "--user",
        f"{profile.uid}:{profile.gid}",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,exec,size=2g,mode=1777",  # noqa: S108 - isolated disposable build tmpfs
        "--env",
        "HOME=/tmp/home",
        "--env",
        "UV_CACHE_DIR=/tmp/uv-cache",
        "--env",
        "UV_LINK_MODE=copy",
        "--mount",
        mount,
        "--workdir",
        _IMAGE_PROJECT,
        "--entrypoint",
        _IMAGE_UV,
        profile.image,
        "sync",
        "--locked",
        "--extra",
        "dev",
    ]


def _run_build(argv: Sequence[str], runner: Runner) -> None:
    try:
        result = runner(
            list(argv),
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=_BUILD_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise EnvironmentArtifactError("Docker executable is unavailable") from None
    except subprocess.TimeoutExpired:
        raise EnvironmentArtifactError("locked environment build timed out") from None
    except OSError:
        raise EnvironmentArtifactError("locked environment build could not start") from None
    if result.returncode != 0:
        raise EnvironmentArtifactError(f"locked environment build failed (exit {result.returncode})")


def _check_built_venv(venv: Path) -> None:
    if venv.is_symlink() or not venv.is_dir():
        raise EnvironmentArtifactError("build did not produce a project .venv directory")
    binary_dir = venv / "bin"
    if binary_dir.is_symlink() or not binary_dir.is_dir():
        raise EnvironmentArtifactError("build did not produce .venv/bin")
    bin_fd = os.open(binary_dir, _DIRECTORY)
    try:
        for executable in ("python", "pytest", "mutmut"):
            if not workspace_authority._environment_executable(bin_fd, executable):
                raise EnvironmentArtifactError(f"build is missing executable .venv/bin/{executable}")
    finally:
        os.close(bin_fd)


def _sync_tree(root: Path) -> None:
    for directory, _subdirectories, files in os.walk(root, topdown=False, followlinks=False):
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        fd = os.open(directory, _DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _seal_tree(root: Path) -> None:
    """Remove all write bits from the artifact before its no-replace install."""
    for directory, subdirectories, files in os.walk(root, topdown=False, followlinks=False):
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
        for name in subdirectories:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(stat.S_IMODE(path.stat().st_mode) & ~0o222)
    root.chmod(stat.S_IMODE(root.stat().st_mode) & ~0o222)


def _make_writable_for_cleanup(root: Path) -> None:
    if not root.exists() or root.is_symlink():
        return
    for directory, subdirectories, _files in os.walk(root, topdown=False, followlinks=False):
        for name in subdirectories:
            path = Path(directory) / name
            if not path.is_symlink():
                path.chmod(stat.S_IMODE(path.stat().st_mode) | 0o700)
    root.chmod(stat.S_IMODE(root.stat().st_mode) | 0o700)


def _prepare_store(cache: Path, cache_fd: int) -> tuple[Path, int]:
    store = cache / workspace_authority._ENVIRONMENT_STORE
    try:
        os.mkdir(workspace_authority._ENVIRONMENT_STORE, 0o755, dir_fd=cache_fd)
    except FileExistsError:
        pass
    except OSError:
        raise EnvironmentArtifactError("environment cache directory could not be created") from None
    try:
        store_fd = os.open(workspace_authority._ENVIRONMENT_STORE, _DIRECTORY, dir_fd=cache_fd)
    except OSError:
        raise EnvironmentArtifactError("environment cache directory is not a safe directory") from None
    try:
        info = os.fstat(store_fd)
    except OSError:
        os.close(store_fd)
        raise EnvironmentArtifactError("environment cache directory could not be inspected") from None
    if info.st_uid != os.getuid() or info.st_mode & 0o022:
        os.close(store_fd)
        raise EnvironmentArtifactError("environment cache directory ownership or permissions are unsafe")
    try:
        os.fchmod(store_fd, 0o755)
    except BaseException:
        os.close(store_fd)
        raise
    return store, store_fd


def _existing_artifact(source: Path, cache: Path, profile: ExecutionProfile) -> Path | None:
    source_fd = workspace_authority._open_absolute(source)
    try:
        cache_fd = _check_cache(cache)
    except BaseException:
        os.close(source_fd)
        raise
    try:
        resolved = workspace_authority._environment_artifact(source_fd, cache_fd, cache, profile)
        if resolved is None:
            return None
        path, descriptor = resolved
        os.close(descriptor)
        return path
    except SupervisorError as error:
        raise EnvironmentArtifactError(f"existing environment artifact is invalid: {error.code}") from None
    finally:
        os.close(source_fd)
        os.close(cache_fd)


def _validated_inputs(source: Path, cache: Path, profile: ExecutionProfile) -> tuple[Path, Path, dict[str, Any], str]:
    source = Path(source).expanduser()
    cache = Path(cache).expanduser()
    if not source.is_absolute() or not cache.is_absolute():
        raise EnvironmentArtifactError("source and approved_cache must be absolute paths")
    try:
        source_fd = workspace_authority._open_absolute(source)
    except (OSError, ExecutionContractError):
        raise EnvironmentArtifactError("source must exist and contain no symlink path components") from None
    try:
        if not stat.S_ISDIR(os.fstat(source_fd).st_mode):
            raise EnvironmentArtifactError("source must be a directory")
    finally:
        os.close(source_fd)
    identity, fingerprint = _identity(source, profile)
    cache_fd = _check_cache(cache)
    try:
        if not stat.S_ISDIR(os.fstat(cache_fd).st_mode):
            raise EnvironmentArtifactError("approved_cache must be a directory")
    finally:
        os.close(cache_fd)
    return source, cache, identity, fingerprint


def prewarm_environment_artifact(
    source: Path,
    cache: Path,
    profile: ExecutionProfile,
    *,
    runner: Runner = subprocess.run,
) -> Path:
    """Build one locked dev environment inside `profile.image`, then publish it.

    Existing valid content-addressed entries are returned without invoking
    Docker. Invalid entries are never replaced; a build failure leaves the
    usable cache unchanged. The final directory is installed with RENAME_NOREPLACE.
    """
    if not isinstance(profile, ExecutionProfile):
        raise ExecutionContractError
    if profile.uid != os.getuid() or profile.gid != os.getgid():
        raise EnvironmentArtifactError("prewarm must run as the approved profile uid/gid")
    source, cache, identity, fingerprint = _validated_inputs(source, cache, profile)
    final = cache / workspace_authority._ENVIRONMENT_STORE / fingerprint
    existing = _existing_artifact(source, cache, profile)
    if existing is not None:
        return existing

    cache_fd = _check_cache(cache)
    try:
        store, store_fd = _prepare_store(cache, cache_fd)
    except OSError:
        os.close(cache_fd)
        raise EnvironmentArtifactError("environment cache directory could not be prepared") from None
    except BaseException:
        os.close(cache_fd)
        raise
    try:
        stage = store / f".{fingerprint}.{uuid4().hex}.stage"
        try:
            with tempfile.TemporaryDirectory(prefix="fa-env-prewarm-", dir="/tmp") as temporary:
                build_workspace = Path(temporary) / "workspace"
                build_workspace.mkdir(mode=0o700)
                _copy_build_inputs(source, build_workspace)
                staged_identity, _ = _identity(build_workspace, profile)
                if staged_identity != identity:
                    raise EnvironmentArtifactError("source lock inputs changed during prewarm copy")
                _run_build(_docker_argv(build_workspace, profile), runner)
                built_venv = build_workspace / ".venv"
                _check_built_venv(built_venv)
                stage.mkdir(mode=0o700)
                shutil.copytree(built_venv, stage / ".venv", symlinks=True)
                manifest = {**identity, "fingerprint": fingerprint}
                manifest_path = stage / "manifest.json"
                manifest_path.write_bytes(workspace_authority._canonical(manifest))
                manifest_path.chmod(0o444)
                _sync_tree(stage)
                _seal_tree(stage)
                _sync_tree(stage)
            stage_fd = os.open(stage.name, _DIRECTORY, dir_fd=store_fd)
            os.close(stage_fd)
            try:
                _rename_directory(store_fd, stage.name, store_fd, fingerprint)
            except OSError as error:
                if error.errno in {errno.EEXIST, errno.ENOTEMPTY} and final.exists():
                    _make_writable_for_cleanup(stage)
                    shutil.rmtree(stage)
                    existing = _existing_artifact(source, cache, profile)
                    if existing is not None:
                        return existing
                raise EnvironmentArtifactError("could not atomically publish environment artifact") from None
            os.fsync(store_fd)
        except EnvironmentArtifactError:
            _make_writable_for_cleanup(stage)
            if stage.exists():
                shutil.rmtree(stage)
            raise
        except OSError:
            _make_writable_for_cleanup(stage)
            if stage.exists():
                shutil.rmtree(stage)
            raise EnvironmentArtifactError("environment artifact staging failed") from None
        verified = _existing_artifact(source, cache, profile)
        if verified is None or verified != final / ".venv":
            raise EnvironmentArtifactError("published environment artifact did not verify")
        return verified
    finally:
        os.close(store_fd)
        os.close(cache_fd)


def _select_profile(config: ServiceConfig, profile_id: str | None) -> ExecutionProfile:
    selected_id = config.view_profile_id if profile_id is None else profile_id
    profile = next((item for item in config.profiles if item.profile_id == selected_id), None)
    if profile is None:
        raise EnvironmentArtifactError("selected execution profile is not approved")
    if config.approved_cache is None:
        raise EnvironmentArtifactError("execution config has no approved_cache")
    return profile


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m fa.execution.environment_artifact")
    parser.add_argument("--source", type=Path, required=True, help="locked project source directory")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="operator config.yaml path")
    parser.add_argument("--profile-id", help="approved cell profile (defaults to view_profile_id)")
    args = parser.parse_args(argv)
    config = _service_config(args.config)
    if config is None:
        print("environment prewarm: managed execution config is unavailable", file=sys.stderr)
        return 2
    try:
        profile = _select_profile(config, args.profile_id)
        cache = config.approved_cache
        if cache is None:
            raise EnvironmentArtifactError("execution config has no approved_cache")
        artifact = prewarm_environment_artifact(args.source, cache, profile)
    except (EnvironmentArtifactError, ExecutionContractError) as error:
        print(f"environment prewarm: {error}", file=sys.stderr)
        return 2
    print(artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
