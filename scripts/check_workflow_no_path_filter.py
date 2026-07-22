#!/usr/bin/env python3
"""Verify GitHub Actions workflow files have no `paths:` / `paths-ignore:` filters.

ADR-11-I6: CI is the authority, not pre-commit; a guardrail that only runs
when its own files change is trivially bypassed.  Every workflow in the
authoring-guardrails surface MUST run on *all* PRs and pushes to main.

Why this script exists (instead of naïve grep):
    # BAD oracle (false FAIL): matches comments that mention "paths: filter"
    grep -q "paths:" .github/workflows/authoring-guardrails.yml && echo FAIL

    This script parses YAML properly — comments are naturally ignored by the
    parser — so it only flags actual YAML keys, not prose in comments.

Exit codes:
    0 — no path filters found in any checked workflow
    1 — one or more workflows contain path filters
    2 — usage / file-not-found error

stdlib-only (yaml is a project dependency already; uses yaml.safe_load).
This file IS a protected TCB path (scripts/).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

# Keys that constitute path filtering at the trigger level.
_PATH_FILTER_KEYS = frozenset({"paths", "paths-ignore"})


def _collect_on_triggers(on_section: Any) -> list[tuple[str, dict[str, Any]]]:
    """Walk the ``on:`` section and return (trigger_name, config) pairs.

    Handles both shorthand and longhand forms::

        on:
          pull_request:           # shorthand → config is None
          push:                   # shorthand → config is None
            branches: [main]      # longhand → config = {"branches": [...]}

    Also handles the list form::

        on: [pull_request, push]
    """
    if on_section is None:
        return []
    # List form: on: [pull_request, push]
    if isinstance(on_section, list):
        return [(str(item), {}) for item in on_section]
    # Dict form: on: {pull_request: ..., push: ...}
    if isinstance(on_section, dict):
        pairs: list[tuple[str, dict[str, Any]]] = []
        for name, config in on_section.items():
            pairs.append((str(name), config if isinstance(config, dict) else {}))
        return pairs
    return []


def check_workflow(path: Path) -> dict[str, Any]:
    """Check a single workflow file for path filters.

    Returns a dict with keys:
        path: str
        has_path_filter: bool
        triggers_with_filter: list[str]  — trigger names that contain a path key
        filter_keys_found: list[str]     — the actual keys (paths, paths-ignore)
        error: str | None                — parse error, if any
    """
    result: dict[str, Any] = {
        "path": str(path),
        "has_path_filter": False,
        "triggers_with_filter": [],
        "filter_keys_found": [],
        "error": None,
    }
    if not path.exists():
        result["error"] = f"file not found: {path}"
        return result

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        result["error"] = f"YAML parse error: {exc}"
        return result

    if not isinstance(data, dict):
        result["error"] = "workflow is not a YAML mapping"
        return result

    # YAML parses the key ``on`` as boolean ``True`` — a well-known gotcha.
    # GitHub Actions uses ``on`` as a key, but PyYAML (and all YAML 1.1
    # parsers) interpret bare ``on``/``off``/``yes``/``no`` as booleans.
    on_section = data.get("on") or data.get(True)
    triggers = _collect_on_triggers(on_section)

    filter_keys_found: set[str] = set()
    triggers_with_filter: list[str] = []

    for trigger_name, config in triggers:
        for key in _PATH_FILTER_KEYS:
            if key in config:
                filter_keys_found.add(key)
                if trigger_name not in triggers_with_filter:
                    triggers_with_filter.append(trigger_name)

    result["has_path_filter"] = bool(filter_keys_found)
    result["triggers_with_filter"] = triggers_with_filter
    result["filter_keys_found"] = sorted(filter_keys_found)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_workflow_no_path_filter",
        description="Verify GitHub Actions workflows have no paths:/paths-ignore: filters.",
    )
    parser.add_argument(
        "workflows",
        nargs="*",
        type=Path,
        help="Workflow YAML files to check (default: .github/workflows/*.yml)",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root (default: current directory).",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text).",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()

    # Default: all workflow files
    if args.workflows:
        workflow_paths = [p if p.is_absolute() else repo_root / p for p in args.workflows]
    else:
        workflow_dir = repo_root / ".github" / "workflows"
        if not workflow_dir.is_dir():
            print(f"error: no .github/workflows/ directory found in {repo_root}", file=sys.stderr)
            return 2
        workflow_paths = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))

    if not workflow_paths:
        print("error: no workflow files found", file=sys.stderr)
        return 2

    results = [check_workflow(p) for p in workflow_paths]
    any_filter = any(r["has_path_filter"] for r in results)

    if args.output == "json":
        json.dump(
            {
                "has_path_filter": any_filter,
                "workflows": results,
            },
            sys.stdout,
            indent=2,
        )
        print()
    else:
        for r in results:
            if r["error"]:
                print(f"ERROR {r['path']}: {r['error']}")
            elif r["has_path_filter"]:
                keys = ", ".join(r["filter_keys_found"])
                triggers = ", ".join(r["triggers_with_filter"])
                print(f"FAIL {r['path']}: has {keys} in trigger(s): {triggers}")
            else:
                print(f"PASS {r['path']}: no path filters")

    return 1 if any_filter else 0


if __name__ == "__main__":
    raise SystemExit(main())
