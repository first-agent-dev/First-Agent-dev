"""C0 fixtures for the Q97 managed-discovery inventory primitive only."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from fa.memory.managed_discovery import (
    ManagedDiscoveryError,
    ManagedDiscoveryLimits,
    inventory_managed_files,
)
from tests._capabilities import requires_symlinks


def _file(root: Path, relative: str, data: bytes = b"x") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_inventory_keeps_exact_bounds_and_sorts_complete_candidates(tmp_path: Path) -> None:
    _file(tmp_path, "z.py", b"123")
    _file(tmp_path, "a.py", b"12")
    limits = ManagedDiscoveryLimits(walk_entries=2, candidates=2, source_bytes=5)
    inventory = inventory_managed_files(
        tmp_path,
        patterns=("*.py",),
        deadline=time.monotonic() + 2,
        limits=limits,
    )
    assert inventory.entries == 2
    assert [item.relative_path for item in inventory.candidates] == ["a.py", "z.py"]
    assert inventory.eligible_source_bytes == 5
    assert inventory.oversized_files == 0


def test_walk_candidate_and_source_cap_plus_one_refuse_without_partial_inventory(tmp_path: Path) -> None:
    for name in ("a.py", "b.py", "c.py"):
        _file(tmp_path, name, b"12")
    with pytest.raises(ManagedDiscoveryError) as caught:
        inventory_managed_files(
            tmp_path,
            patterns=("*.py",),
            deadline=time.monotonic() + 2,
            limits=ManagedDiscoveryLimits(walk_entries=2, candidates=3, source_bytes=100),
        )
    assert caught.value.reason == "walk_budget"

    with pytest.raises(ManagedDiscoveryError) as caught:
        inventory_managed_files(
            tmp_path,
            patterns=("*.py",),
            deadline=time.monotonic() + 2,
            limits=ManagedDiscoveryLimits(walk_entries=3, candidates=2, source_bytes=100),
        )
    assert caught.value.reason == "candidate_budget"

    with pytest.raises(ManagedDiscoveryError) as caught:
        inventory_managed_files(
            tmp_path,
            patterns=("*.py",),
            deadline=time.monotonic() + 2,
            limits=ManagedDiscoveryLimits(walk_entries=3, candidates=3, source_bytes=5),
        )
    assert caught.value.reason == "source_budget"


def test_oversized_per_file_is_counted_but_not_charged_to_aggregate_source(tmp_path: Path) -> None:
    _file(tmp_path, "small.py", b"123")
    _file(tmp_path, "large.py", b"123456")
    inventory = inventory_managed_files(
        tmp_path,
        patterns=("*.py",),
        deadline=time.monotonic() + 2,
        limits=ManagedDiscoveryLimits(walk_entries=2, candidates=2, source_bytes=3, per_file_bytes=5),
    )
    assert inventory.eligible_source_bytes == 3
    assert inventory.oversized_files == 1
    assert [(item.relative_path, item.oversized) for item in inventory.candidates] == [
        ("large.py", True),
        ("small.py", False),
    ]


def test_depth_path_and_expired_deadline_are_explicit_refusals(tmp_path: Path) -> None:
    _file(tmp_path, "nested/deep.py")
    with pytest.raises(ManagedDiscoveryError) as caught:
        inventory_managed_files(
            tmp_path,
            patterns=("*.py",),
            deadline=time.monotonic() + 2,
            limits=ManagedDiscoveryLimits(depth=1),
        )
    assert caught.value.reason == "depth_budget"

    long_name = "/".join(("a" * 90, "b" * 90, "c" * 90 + ".py"))
    _file(tmp_path, long_name)
    with pytest.raises(ManagedDiscoveryError) as caught:
        inventory_managed_files(
            tmp_path,
            patterns=("*.py",),
            deadline=time.monotonic() + 2,
            limits=ManagedDiscoveryLimits(relative_path_bytes=255),
        )
    assert caught.value.reason == "path_budget"

    with pytest.raises(ManagedDiscoveryError) as caught:
        inventory_managed_files(tmp_path, patterns=("*.py",), deadline=time.monotonic() - 1)
    assert caught.value.reason == "deadline"


@requires_symlinks
def test_inventory_prunes_excluded_directories_and_never_follows_symlinks(tmp_path: Path) -> None:
    _file(tmp_path, "src/ok.py")
    _file(tmp_path, "vendor/hidden.py")
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    (outside / "secret.py").write_text("def secret(): pass\n", encoding="utf-8")
    (tmp_path / "escape.py").symlink_to(outside / "secret.py")
    (tmp_path / "linked-dir").symlink_to(outside, target_is_directory=True)
    inventory = inventory_managed_files(
        tmp_path,
        patterns=("*.py",),
        extra_exclude_dirs=frozenset({"vendor"}),
        deadline=time.monotonic() + 2,
    )
    assert [item.relative_path for item in inventory.candidates] == ["src/ok.py"]
    assert not any("secret" in item.relative_path for item in inventory.candidates)


def test_invalid_or_missing_root_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    with pytest.raises(ManagedDiscoveryError) as caught:
        inventory_managed_files(missing, patterns=("*.py",), deadline=time.monotonic() + 2)
    assert caught.value.reason == "unsafe_path"
    with pytest.raises(ValueError):
        ManagedDiscoveryLimits(candidates=True)
    assert os.path.isdir(tmp_path)
