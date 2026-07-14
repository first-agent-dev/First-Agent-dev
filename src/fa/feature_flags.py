"""FeatureFlags loader from ~/.fa/config.yaml — Phase 0.5/1

Parses feature_flags: block for blackboard, telemetry, runtime, worktree, etc.
Uses same hand-rolled YAML subset pattern as fa.config and runtime_limits.

Principles:
- Defaults anchored, never magic constants in code
- Failure-observable: warnings for unknown keys, not silent
- Graceful degradation: missing file -> defaults
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fa._yaml_subset import strip_inline_comment
from fa.config import DEFAULT_CONFIG_PATH

_TRUE_LITERALS = frozenset({"true", "yes", "on", "1"})
_FALSE_LITERALS = frozenset({"false", "no", "off", "0"})


@dataclass(frozen=True)
class FeatureFlags:
    """Frozen snapshot of feature flags for Stage 0.5+."""

    blackboard_enabled: bool = True
    telemetry_enabled: bool = True
    tool_batching_enabled: bool = True
    subagent_spawning_enabled: bool = False
    context_budget_enabled: bool = True
    context_compaction_enabled: bool = False
    runtime_mode: str = "in_process"
    pty_pool_max_size: int = 2
    worktree_mode: str = "shared"
    fts_db_path: str = ".fa/fts.db"
    prompt_caching: bool = True
    prompt_cache_key_per_role: bool = True
    offload_threshold: int = 8000
    max_subagent_spawns_per_session: int = 3

    def as_dict(self) -> dict[str, Any]:
        return {
            "blackboard.enabled": self.blackboard_enabled,
            "telemetry.enabled": self.telemetry_enabled,
            "tool_batching.enabled": self.tool_batching_enabled,
            "subagent_spawning_enabled": self.subagent_spawning_enabled,
            "context_budget_enabled": self.context_budget_enabled,
            "context_compaction_enabled": self.context_compaction_enabled,
            "runtime.mode": self.runtime_mode,
            "pty_pool.max_size": self.pty_pool_max_size,
            "worktree.mode": self.worktree_mode,
            "memory.fts_db_path": self.fts_db_path,
            "prompt.caching": self.prompt_caching,
            "prompt.cache_key_per_role": self.prompt_cache_key_per_role,
            "offload_threshold": self.offload_threshold,
            "max_subagent_spawns_per_session": self.max_subagent_spawns_per_session,
        }


@dataclass(frozen=True)
class FeatureFlagWarning:
    line_no: int
    key: str
    detail: str


@dataclass(frozen=True)
class FeatureFlagsLoadResult:
    flags: FeatureFlags
    warnings: tuple[FeatureFlagWarning, ...] = field(default_factory=tuple)


_KNOWN_FLAGS: dict[str, str] = {
    "blackboard.enabled": "bool",
    "telemetry.enabled": "bool",
    "tool_batching.enabled": "bool",
    "subagent_spawning_enabled": "bool",
    "context_budget_enabled": "bool",
    "context_compaction_enabled": "bool",
    "runtime.mode": "str",
    "pty_pool.max_size": "int",
    "pty_pool_max_size": "int",
    "worktree.mode": "str",
    "worktree_mode": "str",
    "memory.fts_db_path": "str",
    "fts_db_path": "str",
    "prompt.caching": "bool",
    "prompt.cache_key_per_role": "bool",
    "offload_threshold": "int",
    "max_subagent_spawns_per_session": "int",
}


def _parse_bool(val: str) -> bool | None:
    low = val.lower()
    if low in _TRUE_LITERALS:
        return True
    if low in _FALSE_LITERALS:
        return False
    return None


def _build_dotted(prefixes: list[tuple[int, str]], cur_indent: int, key: str) -> str:
    active = [p for (i, p) in prefixes if i < cur_indent]
    if not active:
        return key
    if "." in key:
        return key
    return ".".join([*active, key])


def _normalize_key(dotted: str) -> str:
    if dotted in _KNOWN_FLAGS:
        return dotted
    norm = dotted.replace("_", ".")
    if norm in _KNOWN_FLAGS:
        return norm
    return dotted


def _get_bool(found: dict[str, Any], primary: str, aliases: list[str], default: bool) -> bool:
    for k in [primary, *aliases]:
        if k in found:
            return bool(found[k])
    return default


def _get_int(found: dict[str, Any], primary: str, aliases: list[str], default: int) -> int:
    for k in [primary, *aliases]:
        if k in found:
            try:
                return int(found[k])
            except (ValueError, TypeError):
                continue
    return default


def _get_str(found: dict[str, Any], primary: str, aliases: list[str], default: str) -> str:
    for k in [primary, *aliases]:
        if k in found:
            return str(found[k])
    return default


def load_feature_flags(text: str) -> FeatureFlagsLoadResult:
    """Parse feature_flags: block from YAML text.

    Supports flat dotted and nested forms.
    """
    found: dict[str, Any] = {}
    warnings: list[FeatureFlagWarning] = []
    in_block = False
    prefix_stack: list[tuple[int, str]] = []

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if indent == 0:
            is_flag_block = stripped.startswith("feature_flags:")
            in_block = is_flag_block
            prefix_stack.clear()
            continue

        if not in_block:
            continue

        if stripped.startswith("- "):
            warnings.append(
                FeatureFlagWarning(
                    line_no=line_no,
                    key=stripped,
                    detail="list not expected",
                )
            )
            continue

        if ":" not in stripped:
            continue

        key_raw, _, rest = stripped.partition(":")
        key = key_raw.strip()
        rest_stripped = strip_inline_comment(rest).strip()

        # Parent node (e.g., "blackboard:" with no value)
        if rest_stripped == "":
            prefix_stack = [(i, p) for (i, p) in prefix_stack if i < indent]
            prefix_stack.append((indent, key))
            continue

        dotted = _build_dotted(prefix_stack, indent, key)
        dotted = _normalize_key(dotted)

        if dotted not in _KNOWN_FLAGS:
            warnings.append(FeatureFlagWarning(line_no=line_no, key=dotted, detail="unknown flag"))
            continue

        val_str = rest_stripped.strip().strip('"').strip("'")
        expected = _KNOWN_FLAGS.get(dotted, "str")

        try:
            if expected == "bool":
                b = _parse_bool(val_str)
                if b is None:
                    warnings.append(
                        FeatureFlagWarning(
                            line_no=line_no,
                            key=dotted,
                            detail=f"not bool: {val_str!r}",
                        )
                    )
                    continue
                found[dotted] = b
            elif expected == "int":
                found[dotted] = int(val_str)
            else:
                found[dotted] = val_str
        except Exception as exc:  # noqa: BLE001 - parse error -> warning
            warnings.append(FeatureFlagWarning(line_no=line_no, key=dotted, detail=f"parse error: {exc}"))
            continue

    flags = FeatureFlags(
        blackboard_enabled=_get_bool(found, "blackboard.enabled", [], True),
        telemetry_enabled=_get_bool(found, "telemetry.enabled", [], True),
        tool_batching_enabled=_get_bool(found, "tool_batching.enabled", [], True),
        subagent_spawning_enabled=_get_bool(found, "subagent_spawning_enabled", [], False),
        context_budget_enabled=_get_bool(found, "context_budget_enabled", [], True),
        context_compaction_enabled=_get_bool(found, "context_compaction_enabled", [], False),
        runtime_mode=_get_str(found, "runtime.mode", [], "in_process"),
        pty_pool_max_size=_get_int(found, "pty_pool.max_size", ["pty_pool_max_size"], 2),
        worktree_mode=_get_str(found, "worktree.mode", ["worktree_mode"], "shared"),
        fts_db_path=_get_str(found, "memory.fts_db_path", ["fts_db_path"], ".fa/fts.db"),
        prompt_caching=_get_bool(found, "prompt.caching", [], True),
        prompt_cache_key_per_role=_get_bool(found, "prompt.cache_key_per_role", [], True),
        offload_threshold=_get_int(found, "offload_threshold", [], 8000),
        max_subagent_spawns_per_session=_get_int(found, "max_subagent_spawns_per_session", [], 3),
    )

    return FeatureFlagsLoadResult(flags=flags, warnings=tuple(warnings))


def load_feature_flags_from_path(
    path: Path = DEFAULT_CONFIG_PATH,
) -> FeatureFlagsLoadResult:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return FeatureFlagsLoadResult(flags=FeatureFlags())
    return load_feature_flags(text)


__all__ = [
    "FeatureFlagWarning",
    "FeatureFlags",
    "FeatureFlagsLoadResult",
    "load_feature_flags",
    "load_feature_flags_from_path",
]
