"""Operator cache prewarm contract; fake Docker runner, no daemon or network."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from fa.execution import workspace
from fa.execution.environment_artifact import EnvironmentArtifactError, prewarm_environment_artifact
from tests.test_execution_client import profile


def current_profile() -> Any:
    return replace(profile(), uid=os.getuid(), gid=os.getgid())


def source_tree(root: Path) -> Path:
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'first-agent'\n")
    (root / "uv.lock").write_text("version = 1\n")
    (root / "README.md").write_text("artifact fixture\n")
    (root / "src" / "fa").mkdir(parents=True)
    (root / "src" / "fa" / "__init__.py").write_text("VALUE = 1\n")
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("must not be mounted\n")
    (root / ".venv" / "bin").mkdir(parents=True)
    (root / ".venv" / "bin" / "pytest").write_text("host environment must not be reused\n")
    return root


def expected_identity(source: Path) -> dict[str, Any]:
    selected = current_profile()
    return {
        "schema_version": 1,
        "profile_id": selected.profile_id,
        "image": selected.image,
        "image_digest": selected.image_digest,
        "pyproject_sha256": hashlib.sha256((source / "pyproject.toml").read_bytes()).hexdigest(),
        "uv_lock_sha256": hashlib.sha256((source / "uv.lock").read_bytes()).hexdigest(),
        "extra": "dev",
    }


def fake_docker(source: Path, calls: list[list[str]]) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        assert kwargs["check"] is False
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["timeout"] == 900
        assert "--network=bridge" in argv
        assert "--read-only" in argv and "--cap-drop=ALL" in argv
        assert argv[-4:] == ["sync", "--locked", "--extra", "dev"]
        assert profile().image in argv
        mount = argv[argv.index("--mount") + 1]
        assert mount.startswith("type=bind,source=") and mount.endswith(",target=/workspace")
        mounted = Path(mount.removeprefix("type=bind,source=").removesuffix(",target=/workspace"))
        assert mounted != source and mounted.is_relative_to(Path("/tmp"))
        assert (mounted / "pyproject.toml").read_bytes() == (source / "pyproject.toml").read_bytes()
        assert (mounted / "uv.lock").read_bytes() == (source / "uv.lock").read_bytes()
        assert not (mounted / ".git").exists() and not (mounted / ".venv").exists()
        binaries = mounted / ".venv" / "bin"
        binaries.mkdir(parents=True)
        os.symlink("/usr/local/bin/python3.13", binaries / "python")
        for name in ("pytest", "mutmut"):
            executable = binaries / name
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o555)
        return subprocess.CompletedProcess(argv, 0, "", "")

    return run


def test_prewarm_builds_from_locked_copy_and_atomically_seals_cache(tmp_path: Path) -> None:
    source = source_tree(tmp_path / "source")
    cache = tmp_path / "approved-cache"
    cache.mkdir(mode=0o755)
    before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    calls: list[list[str]] = []

    artifact = prewarm_environment_artifact(source, cache, current_profile(), runner=fake_docker(source, calls))
    expected = expected_identity(source)
    fingerprint = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    entry = cache / workspace._ENVIRONMENT_STORE / fingerprint

    assert artifact == entry / ".venv"
    assert len(calls) == 1
    manifest = json.loads((entry / "manifest.json").read_text())
    assert manifest == {**expected, "fingerprint": fingerprint}
    assert stat.S_IMODE(entry.stat().st_mode) & 0o222 == 0
    assert stat.S_IMODE(artifact.stat().st_mode) & 0o222 == 0
    assert stat.S_IMODE((entry / "manifest.json").stat().st_mode) == 0o444
    source_fd = workspace._open_absolute(source)
    cache_fd = workspace._open_absolute(cache)
    try:
        resolved = workspace._environment_artifact(source_fd, cache_fd, cache, profile())
        assert resolved is not None and resolved[0] == artifact
        os.close(resolved[1])
    finally:
        os.close(source_fd)
        os.close(cache_fd)
    after = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    assert after == before

    def unexpected_build(_argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError("a valid immutable cache hit must not rebuild")

    assert prewarm_environment_artifact(source, cache, current_profile(), runner=unexpected_build) == artifact


def test_prewarm_failure_publishes_no_artifact_and_does_not_touch_source(tmp_path: Path) -> None:
    source = source_tree(tmp_path / "source")
    cache = tmp_path / "approved-cache"
    cache.mkdir(mode=0o755)
    original = (source / "uv.lock").read_bytes()

    def failed_build(argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 17, "", "private build output is not surfaced")

    with pytest.raises(EnvironmentArtifactError, match="exit 17"):
        prewarm_environment_artifact(source, cache, current_profile(), runner=failed_build)
    assert (source / "uv.lock").read_bytes() == original
    store = cache / workspace._ENVIRONMENT_STORE
    assert store.is_dir() and list(store.iterdir()) == []


def test_existing_corrupt_entry_is_not_overwritten_or_rebuilt(tmp_path: Path) -> None:
    source = source_tree(tmp_path / "source")
    cache = tmp_path / "approved-cache"
    cache.mkdir(mode=0o755)
    selected = current_profile()
    source_fd = workspace._open_absolute(source)
    try:
        identity = workspace._environment_identity(source_fd, selected)
    finally:
        os.close(source_fd)
    fingerprint = hashlib.sha256(workspace._canonical(identity)).hexdigest()
    entry = cache / workspace._ENVIRONMENT_STORE / fingerprint
    venv = entry / ".venv" / "bin"
    venv.mkdir(parents=True)
    (entry / "manifest.json").write_text("{}")
    (entry / "manifest.json").chmod(0o444)
    (entry / "manifest.json").parent.chmod(0o555)
    (entry / ".venv" / "bin").chmod(0o555)
    (entry / ".venv").chmod(0o555)
    entry.chmod(0o555)

    def unexpected_build(_argv: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError("an invalid existing entry must fail closed, not be replaced")

    with pytest.raises(EnvironmentArtifactError, match="existing environment artifact is invalid"):
        prewarm_environment_artifact(source, cache, selected, runner=unexpected_build)
    assert (entry / "manifest.json").read_text() == "{}"
