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

from fa.inner_loop.registry import ToolRegistry, ToolSchemaPortabilityError, ToolSpec
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


def _register_optional_tool(
    registry: ToolRegistry,
    tool_name: str,
    builder: Callable[[], ToolSpec] | None,
) -> None:
    """Register one optional tool; source-contract failures are never degraded."""

    if builder is None or tool_name in registry.names():
        return
    try:
        registry.register(builder())
    except ToolSchemaPortabilityError:
        raise
    except Exception as exc:  # noqa: BLE001 - optional builder availability remains fail-degraded
        logger.warning("Failed to register %s: %s", tool_name, exc)


def _register_extra_tools(
    registry: ToolRegistry,
    workspace_root: Path,
    *,
    include_pair: bool = True,
    include_observability: bool = True,
) -> None:
    """Register extra tools while preserving optional availability policy."""

    fs_search_builder = (
        None
        if build_fs_search_tool is None
        else lambda: build_fs_search_tool(_resolve_fts_path(workspace_root), workspace_root)
    )
    _register_optional_tool(registry, "fs_search", fs_search_builder)

    if include_observability:
        _register_optional_tool(registry, "fs_chronicle_search", build_chronicle_search_tool)
        _register_optional_tool(registry, "fs_usage", build_usage_tool)
        if include_pair:
            _register_optional_tool(registry, "fs_list_tasks", build_list_tasks_tool)

    if include_pair:
        checkpoint_builder = None if build_checkpoint_tool is None else lambda: build_checkpoint_tool(workspace_root)
        undo_builder = None if build_undo_tool is None else lambda: build_undo_tool(workspace_root)
        diff_builder = None if build_diff_tool is None else lambda: build_diff_tool(workspace_root)
        _register_optional_tool(registry, "fs_checkpoint", checkpoint_builder)
        _register_optional_tool(registry, "fs_undo", undo_builder)
        _register_optional_tool(registry, "fs_diff", diff_builder)
        _register_optional_tool(registry, "fs_send_ctrl_c", build_send_ctrl_c_tool)

    spawn_builder = None if build_spawn_subagent_tool is None else lambda: build_spawn_subagent_tool(workspace_root)
    _register_optional_tool(registry, "fs_spawn_subagent", spawn_builder)


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
    except ToolSchemaPortabilityError:
        raise
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
    except ToolSchemaPortabilityError:
        raise
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
    except ToolSchemaPortabilityError:
        raise
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


def build_chat_registry(
    workspace_root: Path,
    *,
    bash_timeout_seconds: int = DEFAULT_BASH_TIMEOUT_SECONDS,
) -> ToolRegistry:
    """Chat = pair-programming partner (read+search+bash+blackboard+reach).

    Chat role gets read-only tools for exploration. No write/edit tools.
    The invoke_workflow tool is registered in S4 (not yet available).

    Security boundary: chat cannot mutate files directly. Complex tasks
    are escalated via invoke_workflow (S4) to the full planner→coder→eval pipeline.
    """
    try:
        from fa.inner_loop.profiles import build_registry_for_role

        registry = build_registry_for_role("chat", workspace_root, bash_timeout=bash_timeout_seconds)
    except ToolSchemaPortabilityError:
        raise
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        logger.warning(f"Failed to build chat registry via profiles, fallback: {exc}")
        registry = ToolRegistry()
        registry.register(build_read_file_tool(workspace_root))
        registry.register(build_run_bash_tool(workspace_root, timeout_seconds=bash_timeout_seconds))

    _register_extra_tools(
        registry,
        workspace_root,
        include_pair=False,
        include_observability=True,
    )
    # NOTE: invoke_workflow tool will be registered in S4
    return registry


__all__ = [
    "build_baseline_registry",
    "build_chat_registry",
    "build_eval_registry",
    "build_fs_search_tool",
    "build_planner_registry",
    "build_prepare_pr_tool",
    "build_read_file_tool",
    "build_run_bash_tool",
    "build_write_file_tool",
]
