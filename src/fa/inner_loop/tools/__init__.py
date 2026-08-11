"""Tool registry builders — Stage 0 + Phase 1 with PROFILES wiring.

Fixes Gap 2: bare except pass → WARNING logging (failure-observable §1.2.5)
Phase 1: PROFILES dynamic toolset wired — researcher 600 tokens vs full 3000
- build_registry_for_role now used for baseline/planner/eval
S14b.1: fs_search replaces fs_glob + fs_grep + fs_instant_grep (unified).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from fa.inner_loop.registry import ToolRegistry, ToolSpec
from fa.inner_loop.runtime_limits import DEFAULT_BASH_TIMEOUT_SECONDS
from fa.inner_loop.tools.prepare_pr import build_prepare_pr_tool
from fa.inner_loop.tools.read_file import build_read_file_tool
from fa.inner_loop.tools.run_bash import build_run_bash_tool
from fa.inner_loop.tools.write_file import build_write_file_tool

logger = logging.getLogger(__name__)

# fs_search (S14b.1) replaces fs_glob, fs_grep, fs_instant_grep.
build_fs_search_tool: Callable[[Path, Path], ToolSpec] | None
try:
    from fa.inner_loop.tools.fs_search import build_fs_search_tool
except ImportError as exc:
    logger.warning(f"Failed to import fs_search tool: {exc}")
    build_fs_search_tool = None

build_chronicle_search_tool: Callable[[], ToolSpec] | None
build_usage_tool: Callable[[], ToolSpec] | None
build_list_tasks_tool: Callable[[], ToolSpec] | None
try:
    from fa.inner_loop.tools.observability import (
        build_chronicle_search_tool,
        build_list_tasks_tool,
        build_usage_tool,
    )
except ImportError as exc:
    logger.warning(f"Failed to import observability tools: {exc}")
    build_chronicle_search_tool = None
    build_usage_tool = None
    build_list_tasks_tool = None

build_checkpoint_tool: Callable[[Path], ToolSpec] | None
build_diff_tool: Callable[[Path], ToolSpec] | None
build_send_ctrl_c_tool: Callable[[], ToolSpec] | None
build_undo_tool: Callable[[Path], ToolSpec] | None
try:
    from fa.inner_loop.tools.pair_tools import (
        build_checkpoint_tool,
        build_diff_tool,
        build_send_ctrl_c_tool,
        build_undo_tool,
    )
except ImportError as exc:
    logger.warning(f"Failed to import pair tools: {exc}")
    build_checkpoint_tool = None
    build_undo_tool = None
    build_diff_tool = None
    build_send_ctrl_c_tool = None

build_spawn_subagent_tool: Callable[[Path], ToolSpec] | None
try:
    from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool
except ImportError as exc:
    logger.warning(f"Failed to import spawn_subagent tool: {exc}")
    build_spawn_subagent_tool = None


def _resolve_fts_path(workspace_root: Path) -> Path:
    """Resolve the FTS DB path from feature flags, falling back to .fa/fts.db."""
    try:
        from fa.feature_flags import load_feature_flags_from_path

        ff = load_feature_flags_from_path().flags
        fts_path = getattr(ff, "fts_db_path", ".fa/fts.db")
    except Exception:  # noqa: BLE001
        fts_path = ".fa/fts.db"
    return workspace_root / fts_path


def _register_extra_tools(  # noqa: C901 -- complexity from fallback chain graceful degradation, documented, will split Phase 3 per Paper 2 §4.4
    registry: ToolRegistry,
    workspace_root: Path,
    *,
    include_pair: bool = True,
    include_observability: bool = True,
) -> None:
    """Register extra Stage 0/Phase 1 tools beyond profile base.

    Failure-observable: logs WARNING on failure, not silent pass.
    fs_search is always registered here (single discovery tool for every
    role except verifier, which uses build_registry_for_role directly and
    gets only fs_run_bash).
    """
    # --- fs_search (unified search, S14b.1) ---
    if build_fs_search_tool is not None:
        try:
            if "fs_search" not in registry.names():
                registry.register(build_fs_search_tool(_resolve_fts_path(workspace_root), workspace_root))
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning(f"Failed to register fs_search: {exc}")

    if include_observability:
        if build_chronicle_search_tool:
            try:
                if "fs_chronicle_search" not in registry.names():
                    registry.register(build_chronicle_search_tool())
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to register fs_chronicle_search: {exc}")

        if build_usage_tool:
            try:
                if "fs_usage" not in registry.names():
                    registry.register(build_usage_tool())
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to register fs_usage: {exc}")

        if build_list_tasks_tool and include_pair:
            try:
                if "fs_list_tasks" not in registry.names():
                    registry.register(build_list_tasks_tool())
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to register fs_list_tasks: {exc}")

    if include_pair:
        if build_checkpoint_tool:
            try:
                if "fs_checkpoint" not in registry.names():
                    registry.register(build_checkpoint_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to register fs_checkpoint: {exc}")
        if build_undo_tool:
            try:
                if "fs_undo" not in registry.names():
                    registry.register(build_undo_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to register fs_undo: {exc}")
        if build_diff_tool:
            try:
                if "fs_diff" not in registry.names():
                    registry.register(build_diff_tool(workspace_root))
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to register fs_diff: {exc}")
        if build_send_ctrl_c_tool:
            try:
                if "fs_send_ctrl_c" not in registry.names():
                    registry.register(build_send_ctrl_c_tool())
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to register fs_send_ctrl_c: {exc}")

    if build_spawn_subagent_tool:
        try:
            if "fs_spawn_subagent" not in registry.names():
                registry.register(build_spawn_subagent_tool(workspace_root))
        except Exception as exc:  # noqa: BLE001 # graceful degradation
            logger.warning(f"Failed to register fs_spawn_subagent: {exc}")


def build_baseline_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Baseline = implementer profile (read,write,edit,bash,fs_search,blackboard_query) + observability + pair.

    Phase 1 wiring: uses build_registry_for_role for token efficiency.
    """
    try:
        from fa.inner_loop.profiles import build_registry_for_role

        registry = build_registry_for_role("implementer", workspace_root, bash_timeout=bash_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"Failed to build implementer registry via profiles, fallback baseline: {exc}")
        registry = ToolRegistry()
        registry.register(build_read_file_tool(workspace_root))
        registry.register(build_write_file_tool(workspace_root))
        registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))

    _register_extra_tools(
        registry,
        workspace_root,
        include_pair=True,
        include_observability=True,
    )
    return registry


def build_planner_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Planner = planner profile (fs_search,read,write for research docs,blackboard_query) + observability."""
    try:
        from fa.inner_loop.profiles import build_registry_for_role

        registry = build_registry_for_role("planner", workspace_root, bash_timeout=bash_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"Failed to build planner registry via profiles, fallback: {exc}")
        registry = ToolRegistry()
        registry.register(build_read_file_tool(workspace_root))
        registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))

    _register_extra_tools(
        registry,
        workspace_root,
        include_pair=False,
        include_observability=True,
    )
    return registry


def build_eval_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Eval = verifier profile (bash only) + usage for observability.

    Verifier intentionally does NOT get fs_search (single-command PASS/FAIL contract).
    """
    try:
        from fa.inner_loop.profiles import build_registry_for_role

        registry = build_registry_for_role("verifier", workspace_root, bash_timeout=bash_timeout_seconds)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"Failed to build verifier registry via profiles, fallback: {exc}")
        registry = ToolRegistry()
        registry.register(build_read_file_tool(workspace_root))
        registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))

    _register_extra_tools(
        registry,
        workspace_root,
        include_pair=False,
        include_observability=True,
    )
    return registry


__all__ = [
    "build_baseline_registry",
    "build_eval_registry",
    "build_fs_search_tool",
    "build_planner_registry",
    "build_prepare_pr_tool",
    "build_read_file_tool",
    "build_run_bash_tool",
    "build_write_file_tool",
]
