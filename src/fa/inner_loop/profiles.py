"""
Profiles — dynamic toolset per role (Gap 4 + Gap 8)
ADR-14, ADR-15, Prior art: Copilot CustomAgents tool restriction, Cursor skills

Researcher read-only 600 tokens vs full 3000 → -60% tokens
Cache-key = role_id + hash(tool_defs) solves internal contradiction
Phase 1: build_registry_for_role + estimate_tokens implemented, glob/grep added
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from fa.inner_loop.registry import ToolRegistry, ToolResult, ToolSchemaPortabilityError, ToolSpec, ToolWireNameError
from fa.inner_loop.tool_names import is_valid_wire_name

logger = logging.getLogger(__name__)


def is_path_within_allowlist(path: str, allowed_prefixes: Sequence[str]) -> bool:
    """Return ``True`` when *path* lies under one of *allowed_prefixes*.

    Comparison is **component-wise**, not textual. The previous implementation
    normalised with ``path.lstrip("./")``, which strips a character *set*
    rather than a prefix: ``".fa/notes.md"`` became ``"fa/notes.md"`` and no
    longer matched the ``".fa/"`` entry, so the planner profile advertised a
    write target it could never reach. ``"..foo"`` and ``"./.fa/x"`` were
    mangled the same way.

    Component-wise matching also closes the traversal hole that a
    ``str.startswith`` check leaves open: ``"knowledge/research/../../etc"``
    has the right textual prefix but escapes the allowlisted subtree, and
    ``"knowledge/researcher/x"`` textually starts with ``"knowledge/research"``
    while being a different directory.

    Absolute paths are rejected outright — every allowlist entry is a
    workspace-relative subtree, so an absolute path can never be *within* one,
    and letting it through would depend on the caller's cwd.
    """
    if not path:
        return False
    candidate = PurePosixPath(path)
    if candidate.is_absolute():
        return False
    # Resolve "." / ".." textually; PurePosixPath keeps ".." parts, so a path
    # that climbs above the workspace root is rejected rather than normalised
    # into something that accidentally matches.
    parts: list[str] = []
    for part in candidate.parts:
        if part == ".":
            continue
        if part == "..":
            if not parts:
                return False  # escapes the workspace root
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        return False
    resolved = PurePosixPath(*parts)
    for prefix in allowed_prefixes:
        prefix_path = PurePosixPath(prefix)
        if prefix_path.is_absolute():
            continue
        prefix_parts = [p for p in prefix_path.parts if p not in (".", "")]
        if not prefix_parts:
            continue
        # Strictly *within*: the target must have at least one component below
        # the prefix. Every allowlist entry names a directory, and a path equal
        # to the directory itself is not a writable file target.
        if len(resolved.parts) > len(prefix_parts) and resolved.parts[: len(prefix_parts)] == tuple(prefix_parts):
            return True
    return False


@dataclass(frozen=True)
class RoleProfile:
    description: str
    tools: list[str]
    stateless: bool
    globs: list[str] = field(default_factory=list)
    alwaysApply: bool = False  # noqa: N815 - config surface preserves external key casing
    system_prompt_key: str | None = None
    bash_impl: str | None = None


# Raw dict for backward compat + typed profiles
# v0.1 pair work: planner gets limited write_file to knowledge/research/** + .fa/** per Q3 decision
PROFILES_RAW: dict[str, dict[str, Any]] = {
    "researcher": {
        "description": "Read-only researcher, finds files, no writes",
        "tools": ["fs_search", "fs_read_file", "fs_exploration_metrics", "fs_reach"],
        "max_context_bytes": 4096,
        "stateless": True,
        "system_prompt_key": "researcher",
        "globs": ["**/*.md", "src/**/*.py"],
        "alwaysApply": False,
    },
    "verifier": {
        "description": "Run single verification command, return PASS/FAIL JSON",
        "tools": ["fs_run_bash"],
        "max_context_bytes": 2048,
        "stateless": True,
        "bash_impl": "stateless",
        "output_schema": "verifier",
    },
    "code-reviewer": {
        "description": "Review diff, return issues list",
        "tools": ["fs_read_file", "fs_search", "fs_exploration_metrics", "fs_reach"],
        "stateless": True,
    },
    "implementer": {
        "description": "Main coder, needs stateful PTY for cd/venv persistence",
        "tools": [
            "fs_read_file",
            "fs_write_file",
            "fs_edit_file",
            "fs_run_bash",
            "fs_search",
            "fs_blackboard_query",
            "fs_exploration_metrics",
            "fs_reach",
        ],
        "stateless": False,
        "bash_impl": "stateful",
    },
    "planner": {
        "description": (
            "Architect/Planner, read-only analysis + limited write to research docs for filesystem-canon plans"
        ),
        "tools": [
            "fs_search",
            "fs_read_file",
            "fs_write_file",
            "fs_blackboard_query",
            "fs_exploration_metrics",
            "fs_reach",
        ],
        "stateless": True,
        "write_allowlist": ["knowledge/research/", ".fa/"],
    },
    # Chat is a generalist pair-programming partner, not a read-only viewer.
    # It writes notes, research and scratch files directly, and makes small
    # edits anywhere in the workspace. Scope discipline comes from the
    # deterministic scope estimator (which routes large work to
    # ``invoke_workflow``), not from withholding write tools: an allowlist here
    # would only block the small edits chat is meant to handle in-line.
    "chat": {
        "description": (
            "Pair-programming partner with scope-aware execution: direct read/write tools "
            "for small changes, workflow escalation for large ones"
        ),
        "tools": [
            "fs_read_file",
            "fs_write_file",
            "fs_edit_file",
            "fs_search",
            "fs_blackboard_query",
            "fs_run_bash",
            "fs_exploration_metrics",
            "fs_reach",
            "fs_spawn_subagent",
        ],
        "stateless": False,
        "bash_impl": "stateful",
    },
}

PROFILES: dict[str, dict[str, Any]] = PROFILES_RAW

# Typed version for new code
TYPED_PROFILES: dict[str, RoleProfile] = {
    name: RoleProfile(
        description=data.get("description", ""),
        tools=data.get("tools", []),
        stateless=data.get("stateless", True),
        globs=data.get("globs", []),
        alwaysApply=data.get("alwaysApply", False),
        system_prompt_key=data.get("system_prompt_key"),
        bash_impl=data.get("bash_impl"),
    )
    for name, data in PROFILES_RAW.items()
}


def _add_optional_tool_builders(builders: dict[str, Callable[[], ToolSpec]], root: Path) -> None:
    # edit_file may not exist yet, placeholder
    try:
        # Try to import if exists in future
        from fa.inner_loop.tools.edit_file import build_edit_file_tool

        builders["fs_edit_file"] = lambda: build_edit_file_tool(root)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable, edit_file optional
        logger.warning(f"edit_file builder not available: {exc}")

    # spawn_subagent is declared by profiles (chat, baseline) but had no builder
    # here, so a profile that asked for it silently lost the tool. The tool
    # itself is feature-flagged off by default and fails with ``disabled`` when
    # invoked; registering it keeps the profile declaration and the built
    # registry in agreement instead of diverging silently.
    try:
        from fa.inner_loop.tools.spawn_subagent import build_spawn_subagent_tool

        builders["fs_spawn_subagent"] = lambda: build_spawn_subagent_tool(root)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable
        logger.warning(f"spawn_subagent builder not available: {exc}")

    # Observability + pair tools (from Stage 0)
    try:
        from fa.inner_loop.tools.observability import (
            build_chronicle_search_tool,
            build_list_tasks_tool,
            build_usage_tool,
        )

        builders["fs_chronicle_search"] = lambda: build_chronicle_search_tool()
        builders["fs_usage"] = lambda: build_usage_tool()
        builders["fs_list_tasks"] = lambda: build_list_tasks_tool()
    except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
        pass

    try:
        from fa.inner_loop.tools.pair_tools import (
            build_checkpoint_tool,
            build_diff_tool,
            build_send_ctrl_c_tool,
            build_undo_tool,
        )

        builders["fs_checkpoint"] = lambda: build_checkpoint_tool(root)
        builders["fs_undo"] = lambda: build_undo_tool(root)
        builders["fs_diff"] = lambda: build_diff_tool(root)
        builders["fs_send_ctrl_c"] = lambda: build_send_ctrl_c_tool()
    except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
        pass


def _build_tool_builders(workspace_root: Path, bash_timeout: int = 30) -> dict[str, Callable[[], ToolSpec]]:
    """Map tool name -> builder lambda, uses existing builders, graceful degradation.

    For Phase 1, we have: read_file, write_file, run_bash, glob, grep, instant_grep,
    chronicle_search, usage, list_tasks, checkpoint, undo, diff, send_ctrl_c.
    Glob/grep are new in Phase 1 (user decision add_glob_grep_now).
    """
    builders: dict[str, Callable[[], ToolSpec]] = {}
    root = Path(workspace_root).resolve()

    # Lazy imports to avoid circular and missing deps
    try:
        from fa.inner_loop.tools.read_file import build_read_file_tool

        builders["fs_read_file"] = lambda: build_read_file_tool(root)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to setup builder fs_read_file: {exc}")

    try:
        from fa.inner_loop.tools.fs_exploration_metrics import build_fs_exploration_metrics_tool

        builders["fs_exploration_metrics"] = lambda: build_fs_exploration_metrics_tool()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to setup builder fs_exploration_metrics: {exc}")

    try:
        from fa.inner_loop.tools.fs_reach import build_fs_reach_tool

        builders["fs_reach"] = lambda: build_fs_reach_tool(root)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to setup builder fs_reach: {exc}")

    try:
        from fa.inner_loop.tools.write_file import build_write_file_tool

        builders["fs_write_file"] = lambda: build_write_file_tool(root)

        # Limited write for planner. The prefixes are read from the profile's
        # ``write_allowlist`` rather than duplicated here: the key was
        # previously decorative while the real list lived in this closure, so
        # editing the profile silently changed nothing.
        def _build_limited_write() -> ToolSpec:
            base_spec = build_write_file_tool(root)
            profile_allowlist = PROFILES_RAW.get("planner", {}).get("write_allowlist", [])
            allowed_prefixes: list[str] = [str(p) for p in profile_allowlist]

            orig_handler = base_spec.handler

            def limited_handler(params: Mapping[str, object]) -> ToolResult:
                # Compliance-by-construction: deny before the write is attempted.
                # A malformed ``path`` param is left to the base handler, which
                # owns the schema error; this guard only decides allow/deny for
                # well-formed string paths.
                p = params.get("path", "")
                if not isinstance(p, str):
                    return orig_handler(params)
                if not is_path_within_allowlist(p, allowed_prefixes):
                    return ToolResult.fail(
                        "path_denied",
                        (
                            f"Planner write_file limited to {allowed_prefixes}, got '{p}' — "
                            "use implementer role for src/ writes"
                        ),
                        retryable=False,
                    )
                return orig_handler(params)

            # Return new spec with same schema but limited handler and description
            from fa.inner_loop.registry import ToolSpec

            return ToolSpec(
                name=base_spec.name,
                description=base_spec.description + " [planner limited to knowledge/research/** + .fa/**]",
                input_schema=base_spec.input_schema,
                permission=base_spec.permission,
                handler=limited_handler,
                tags=base_spec.tags,
                max_context_bytes=base_spec.max_context_bytes,
                elide=base_spec.elide,
            )

        builders["fs_write_file_limited"] = _build_limited_write

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to setup builder fs_write_file: {exc}")

    try:
        from fa.inner_loop.tools.run_bash import build_run_bash_tool

        builders["fs_run_bash"] = lambda: build_run_bash_tool(root, timeout_seconds=bash_timeout)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to setup builder fs_run_bash: {exc}")

    # fs_search replaces fs_glob, fs_grep, fs_instant_grep (S14b.1).
    # Resolve fts_db_path from feature flags (same wiring the old
    # instant_grep used), falling back to .fa/fts.db if flags unavailable.
    try:
        from fa.inner_loop.tools.fs_search import build_fs_search_tool

        try:
            from fa.feature_flags import load_feature_flags_from_path

            ff = load_feature_flags_from_path().flags
            fts_path = getattr(ff, "fts_db_path", ".fa/fts.db")
        except Exception as exc:  # noqa: BLE001 — missing optional FTS config uses deterministic default
            logger.warning("Feature-flag FTS path unavailable: %s; using .fa/fts.db", exc)
            fts_path = ".fa/fts.db"

        def _build_fs_search(bp: str = fts_path) -> Any:
            return build_fs_search_tool(root / bp, root)

        builders["fs_search"] = _build_fs_search
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to setup builder fs_search: {exc}")

    try:
        from fa.inner_loop.tools.blackboard_query import build_blackboard_query_tool

        builders["fs_blackboard_query"] = lambda: build_blackboard_query_tool()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Failed to setup builder fs_blackboard_query: {exc}")

    _add_optional_tool_builders(builders, root)

    return builders


def build_registry_for_role(
    role: str,
    workspace_root: Path,
    *,
    bash_timeout: int = 30,
) -> ToolRegistry:
    """Build ToolRegistry with only tools for given role, token efficient.

    Researcher: 4 tools ~600 tokens vs full 11 tools ~3000 tokens (-60%).
    Uses TOOL_BUILDERS mapping, failure-observable WARNING if tool missing, not crash.
    """
    if role not in PROFILES_RAW:
        raise ValueError(f"Unknown role {role}, known: {list(PROFILES_RAW.keys())}")

    profile = PROFILES_RAW[role]
    wanted = profile.get("tools", [])
    builders = _build_tool_builders(workspace_root, bash_timeout=bash_timeout)

    registry = ToolRegistry()
    for tool_name in wanted:
        # For planner, use limited write_file if requested
        if role == "planner" and tool_name == "fs_write_file":
            builder = builders.get("fs_write_file_limited") or builders.get(tool_name)
        else:
            builder = builders.get(tool_name)
        if builder is None:
            logger.warning(f"Tool {tool_name} requested for role {role} but no builder found, skipping")
            continue
        try:
            spec = builder()
            # D10: fail closed on a non-portable wire name.
            #
            # Placed here rather than in ``ToolSpec.__post_init__``,
            # ``ToolRegistry.register`` or ``render_tool_specs``: all three are
            # shared with test fixtures that deliberately use dotted names
            # (``test.echo``, ``t.ok``, ``demo.crash``) to exercise dispatch,
            # validation and stop-paths independently of naming policy —
            # measured at 16 register sites and 11 tests reaching the renderer.
            # Enforcing there would edit tests whose intent is unrelated to
            # naming, which buys no signal.
            #
            # ``build_registry_for_role`` is the production composition root:
            # it can only ever emit tools from the builder table above, so a
            # name reaching this line is one a real role will ship to a real
            # provider. It is prefix-agnostic by construction — a tool named
            # ``invoke_workflow`` is checked exactly like ``fs_read_file``,
            # which the previous ``(?:fs|pr)_`` source scrape could not do.
            if not is_valid_wire_name(spec.name):
                raise ToolWireNameError(spec.name)
            registry.register(spec)
        except ToolSchemaPortabilityError:
            raise
        except ToolWireNameError:
            raise
        except Exception as exc:  # noqa: BLE001 - failure-observable
            logger.warning(f"Failed to build/register tool {tool_name} for role {role}: {exc}")

    return registry


def estimate_tokens(registry: ToolRegistry) -> int:
    """Estimate tokens via chars/4 heuristic (Pi agent, Kon).

    Sum of description + input_schema JSON chars // 4.
    Good enough for relative comparison 600 vs 3000, no external dep.
    """
    total_chars = 0
    try:
        # ToolRegistry has names() and lookup()
        for name in registry.names():
            try:
                spec = registry.lookup(name)
                if spec is None:
                    continue
                total_chars += len(spec.description)
                total_chars += len(json.dumps(spec.input_schema, ensure_ascii=False))
            except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                continue
    except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        # Fallback if registry API different
        try:
            specs: list[ToolSpec] = getattr(registry, "all_specs", lambda: [])()
            for spec in specs:
                total_chars += len(spec.description)
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
            pass

    return total_chars // 4


def get_profile(role: str) -> RoleProfile:
    return TYPED_PROFILES[role]


__all__ = [
    "PROFILES",
    "PROFILES_RAW",
    "TYPED_PROFILES",
    "RoleProfile",
    "build_registry_for_role",
    "estimate_tokens",
    "get_profile",
    "is_path_within_allowlist",
]
