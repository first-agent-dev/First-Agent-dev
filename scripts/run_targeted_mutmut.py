#!/usr/bin/env python3
"""Targeted mutation selector for check-deep/pre-push.

Discovery is fail-open before execution for the existing emergency/tool/Git/
oversized-diff cases. Once the isolated slice executor starts, its strict
clean/actionable/infrastructure exit is returned unchanged.
"""

from __future__ import annotations

import os
import sys
import tomllib
from pathlib import Path
from typing import Any, cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts._git_diff as gd
from scripts.run_slice_mutmut import InputError, request_from_configured_scope, run_slice

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_FILES = 20
TARGETED_TIMEOUT_SECONDS = 600


def _configured_source_roots(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    try:
        data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
        raw = data["tool"]["mutmut"]["source_paths"]
    except (OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        raise InputError(f"cannot read configured mutation source paths: {exc}") from exc
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise InputError("[tool.mutmut].source_paths must be a non-empty string array")
    return tuple(cast(list[str], raw))


def _scope_to_changed(
    changed: list[Path],
    *,
    repo_root: Path = REPO_ROOT,
    source_roots: tuple[str, ...] | None = None,
) -> list[Path]:
    """Keep changed production files beneath configured mutmut source roots."""
    roots = source_roots or _configured_source_roots(repo_root)
    canonical_root = repo_root.resolve()
    scoped: set[Path] = set()
    for path in changed:
        try:
            relative = path.resolve().relative_to(canonical_root).as_posix()
        except ValueError:
            continue
        if relative.startswith("tests/"):
            continue
        if any(relative == root.rstrip("/") or relative.startswith(root.rstrip("/") + "/") for root in roots):
            scoped.add(path.resolve())
    return sorted(scoped)


def _mutmut_installed() -> bool:
    return gd.resolve_tool("mutmut", repo_root=REPO_ROOT, venv_bin_rel=".venv/bin/mutmut") is not None


def main() -> int:
    if os.environ.get("FA_SKIP_TARGETED_MUTATION") == "1":
        gd._log("skipping (FA_SKIP_TARGETED_MUTATION=1)")
        return 0
    if not _mutmut_installed():
        gd._log("mutmut not installed; skipping (fail-open)")
        return 0

    changed = gd.changed_python_files(
        REPO_ROOT,
        source_prefixes=("src/", "tests/"),
        allow_extensions=(".py",),
        max_files=MAX_FILES * 2,
        include_worktree=True,
        include_untracked=True,
    )
    if not changed:
        gd._log("no discoverable changed Python files; nothing to mutate")
        return 0
    try:
        scoped = _scope_to_changed(changed)
    except InputError as exc:
        gd._log(f"invalid mutation configuration: {exc}")
        return 2
    if not scoped:
        gd._log("changed files are outside configured production mutation scope; nothing to do")
        return 0
    if len(scoped) > MAX_FILES:
        gd._log(f"{len(scoped)} production files > MAX_FILES={MAX_FILES}; skipping (weekly full-mutmut covers it)")
        return 0

    gd._log(f"mutating {len(scoped)} production file(s):")
    relative_sources = tuple(path.relative_to(REPO_ROOT).as_posix() for path in scoped)
    for source in relative_sources:
        gd._log(f"  - {source}")
    try:
        request = request_from_configured_scope(
            REPO_ROOT,
            source_override=relative_sources,
            timeout_seconds=TARGETED_TIMEOUT_SECONDS,
        )
    except InputError as exc:
        gd._log(f"invalid targeted mutation request: {exc}")
        return 2
    result = run_slice(request)
    counts = cast(dict[str, Any] | None, result.payload.get("counts"))
    if counts is not None:
        gd._log(
            f"finished: rc={result.exit_code} total={counts['total']} killed={counts['killed']} "
            f"type_invalid={counts['type_invalid']} survived={counts['survived']}"
        )
    else:
        gd._log(f"finished: rc={result.exit_code} reason={result.payload.get('reason')}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
