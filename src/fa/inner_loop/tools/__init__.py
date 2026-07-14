"""Tool registry builders — Stage 0 + Phase 1 with PROFILES wiring.

Fixes Gap 2: bare except pass → WARNING logging (failure-observable §1.2.5)
Phase 1: PROFILES dynamic toolset wired — researcher 600 tokens vs full 3000
- build_registry_for_role now used for baseline/planner/eval
- glob/grep added for researcher role
"""

from __future__ import annotations

import logging
from pathlib import Path

from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools.prepare_pr import build_prepare_pr_tool
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from fa.inner_loop.tools.write_file import build_write_file_tool

logger = logging.getLogger(__name__)

try:
    from fa.inner_loop.tools.glob import build_glob_tool
except ImportError as exc:
    print(f"WARNING: Failed to import glob tool: {exc}")
    build_glob_tool = None

try:
    from fa.inner_loop.tools.grep import build_grep_tool
except ImportError as exc:
    logger.warning("Failed to import grep tool: %s", exc)
    build_grep_tool = None

try:
    from fa.inner_loop.tools.observability import (
        build_chronicle_search_tool,
        build_list_tasks_tool,
        build_usage_tool,
    )
except ImportError as exc:
    print(f"WARNING: Failed to import observability tools: {exc}")
    build_chronicle_search_tool = None
    build_usage_tool = None
    build_list_tasks_tool = None

try:
    from fa.inner_loop.tools.pair_tools import (
        build_checkpoint_tool,
        build_diff_tool,
        build_send_ctrl_c_tool,
        build_undo_tool,
    )
except ImportError as exc:
    print(f"WARNING: Failed to import pair tools: {exc}")
    build_checkpoint_tool = None
    build_undo_tool = None
    build_diff_tool = None
    build_send_ctrl_c_tool = None

try:
    from fa.inner_loop.tools.instant_grep import build_instant_grep_tool
except ImportError as exc:
    print(f"WARNING: Failed to import instant_grep tool: {exc}")
    build_instant_grep_tool = None


def _register_extra_tools(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
    registry: ToolRegistry,
    workspace_root: Path,
    event_log_path: Path,
    *,
    include_pair: bool = True,
    include_observability: bool = True,
    include_instant_grep: bool = False,
    include_glob_grep: bool = False,
) -> None:
    """Register extra Stage 0/Phase 1 tools beyond profile base.

    Failure-observable: logs WARNING on failure, not silent pass.
    """
    if include_glob_grep:
        if build_glob_tool:
            try:
                # Avoid duplicate if already in registry
                if "fs.glob" not in registry.names():
                    registry.register(build_glob_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.glob: {exc}")
        if build_grep_tool:
            try:
                if "fs.grep" not in registry.names():
                    registry.register(build_grep_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.grep: {exc}")

    if include_observability:
        if build_chronicle_search_tool:
            try:
                if "fs.chronicle_search" not in registry.names():
                    registry.register(build_chronicle_search_tool(event_log_path))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.chronicle_search: {exc}")

        if build_usage_tool:
            try:
                if "fs.usage" not in registry.names():
                    registry.register(build_usage_tool(event_log_path))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.usage: {exc}")

        if build_list_tasks_tool and include_pair:
            try:
                if "fs.list_tasks" not in registry.names():
                    registry.register(build_list_tasks_tool())
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.list_tasks: {exc}")

    if include_pair:
        if build_checkpoint_tool:
            try:
                if "fs.checkpoint" not in registry.names():
                    registry.register(build_checkpoint_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.checkpoint: {exc}")
        if build_undo_tool:
            try:
                if "fs.undo" not in registry.names():
                    registry.register(build_undo_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.undo: {exc}")
        if build_diff_tool:
            try:
                if "fs.diff" not in registry.names():
                    registry.register(build_diff_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.diff: {exc}")
        if build_send_ctrl_c_tool:
            try:
                if "fs.send_ctrl_c" not in registry.names():
                    registry.register(build_send_ctrl_c_tool())
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                print(f"WARNING: Failed to register fs.send_ctrl_c: {exc}")

    if include_instant_grep and build_instant_grep_tool:
        try:
            if "fs.instant_grep" not in registry.names():
                db_path = workspace_root / ".fa" / "fts.db"
                registry.register(build_instant_grep_tool(db_path, workspace_root))
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            print(f"WARNING: Failed to register fs.instant_grep: {exc}")


def _event_log_path_for_root(workspace_root: Path) -> Path:
    candidates = [
        workspace_root / ".fa" / "events.jsonl",
        workspace_root / "events.jsonl",
        Path.home() / ".fa" / "events.jsonl",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return workspace_root / ".fa" / "events.jsonl"


def build_baseline_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Baseline = implementer profile (read,write,edit,bash,glob,grep,instant_grep) + observability + pair.

    Phase 1 wiring: uses build_registry_for_role for token efficiency.
    """
    try:
        from fa.inner_loop.profiles import build_registry_for_role

        registry = build_registry_for_role("implementer", workspace_root, bash_timeout=bash_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: Failed to build implementer registry via profiles, fallback baseline: {exc}")
        registry = ToolRegistry()
        registry.register(build_read_file_tool(workspace_root))
        registry.register(build_write_file_tool(workspace_root))
        registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))

    event_log_path = _event_log_path_for_root(workspace_root)

    _register_extra_tools(
        registry,
        workspace_root,
        event_log_path,
        include_pair=True,
        include_observability=True,
        include_instant_grep=False,  # already in implementer profile
        include_glob_grep=False,  # already in implementer profile
    )
    return registry


def build_planner_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Planner = planner profile (glob,grep,read,instant_grep) + observability.

    No bash for read-only analysis per PROFILES, but we add chronicle_search/usage for observability.
    """
    try:
        from fa.inner_loop.profiles import build_registry_for_role

        registry = build_registry_for_role("planner", workspace_root, bash_timeout=bash_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: Failed to build planner registry via profiles, fallback: {exc}")
        registry = ToolRegistry()
        registry.register(build_read_file_tool(workspace_root))
        registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))

    event_log_path = workspace_root / ".fa" / "events.jsonl"

    _register_extra_tools(
        registry,
        workspace_root,
        event_log_path,
        include_pair=False,
        include_observability=True,
        include_instant_grep=False,
        include_glob_grep=False,
    )
    return registry


def build_eval_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Eval = verifier profile (bash only) + usage for observability."""
    try:
        from fa.inner_loop.profiles import build_registry_for_role

        registry = build_registry_for_role("verifier", workspace_root, bash_timeout=bash_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: Failed to build verifier registry via profiles, fallback: {exc}")
        registry = ToolRegistry()
        registry.register(build_read_file_tool(workspace_root))
        registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))

    event_log_path = workspace_root / ".fa" / "events.jsonl"

    _register_extra_tools(
        registry,
        workspace_root,
        event_log_path,
        include_pair=False,
        include_observability=True,
        include_instant_grep=False,
        include_glob_grep=False,
    )
    return registry


__all__ = [
    "build_baseline_registry",
    "build_eval_registry",
    "build_planner_registry",
    "build_prepare_pr_tool",
    "build_read_file_tool",
    "build_run_bash_tool",
    "build_write_file_tool",
]
