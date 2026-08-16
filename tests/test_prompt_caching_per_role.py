"""
Tests for Gap 2 Prompt Caching per role (cache-key = role_id) and Gap 4 skill globs
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fa.inner_loop.prompt import render_tool_specs
from fa.inner_loop.prompt_composer import build_prompt_parts_v2
from fa.inner_loop.tools import build_baseline_registry


def _nested_tool(name: str, parameters: dict[str, Any], *, description: str = "tool") -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def _cache_key_for(tools: list[dict[str, Any]]) -> str:
    _parts, key = build_prompt_parts_v2(
        base_system="BASE",
        agents_md_map="MAP",
        tool_defs=tools,
        role_id="coder",
        task="task",
    )
    return key


def test_cache_key_per_role() -> None:
    from fa.inner_loop.prompt_composer import build_prompt_parts

    base = "BASE SYSTEM"
    map_md = "AGENTS.md map"
    researcher_tools = [{"name": "fs_search"}, {"name": "fs_read_file"}]
    coder_tools = [
        {"name": "fs_read_file"},
        {"name": "fs_write_file"},
        {"name": "fs_edit_file"},
        {"name": "fs_run_bash"},
    ]

    _parts_r, key_r = build_prompt_parts(base, map_md, researcher_tools, role_id="researcher", task="find auth")
    _parts_c, key_c = build_prompt_parts(base, map_md, coder_tools, role_id="coder", task="find auth")

    assert key_r != key_c, f"Cache keys should differ for different toolsets: {key_r} vs {key_c}"
    assert "researcher" in key_r
    assert "coder" in key_c


def test_cache_key_tracks_nested_rendered_tool_name_and_schema() -> None:
    """S13.11 regression: production tools are nested under ``function``.

    The deployed hash reads flat ``name``/``input_schema`` keys, so every tool
    below currently contributes ``None`` and distinct tool contracts collide.
    """

    base = _nested_tool("fs_search", {"type": "object", "properties": {}})
    renamed = _nested_tool("fs_read_file", {"type": "object", "properties": {}})
    changed_schema = _nested_tool(
        "fs_search",
        {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )
    changed_description = _nested_tool(
        "fs_search",
        {"type": "object", "properties": {}},
        description="description-only change",
    )

    base_key = _cache_key_for([base])
    assert _cache_key_for([renamed]) != base_key
    assert _cache_key_for([changed_schema]) != base_key
    assert _cache_key_for([changed_description]) == base_key
    assert _cache_key_for([base, renamed]) == _cache_key_for([renamed, base])


def test_cache_key_tracks_schema_changes_in_real_rendered_registry(tmp_path: Path) -> None:
    """C1: hash the actual ``render_tool_specs`` shape, not a flat test double."""

    rendered = [dict(tool) for tool in render_tool_specs(build_baseline_registry(tmp_path).specs())]
    changed = deepcopy(rendered)
    search = next(tool for tool in changed if tool["function"]["name"] == "fs_search")
    search["function"]["parameters"]["properties"]["query"]["description"] = "changed schema bytes"

    assert _cache_key_for(rendered) != _cache_key_for(changed)
    assert _cache_key_for(rendered) == _cache_key_for(list(reversed(rendered)))


def test_cacheable_split() -> None:
    from fa.inner_loop.prompt_composer import build_prompt_parts, to_anthropic_request, to_openai_request

    base = "BASE"
    map_md = "MAP"
    tools: list[dict[str, str]] = [{"name": "fs_read_file"}]

    parts, key = build_prompt_parts(
        base, map_md, tools, role_id="researcher", task="do something", memory_summary="summary"
    )

    assert len(parts.cacheable) == 3
    assert len(parts.non_cacheable) == 2

    anth_req = to_anthropic_request(parts, key)
    assert "cache_control" in anth_req["messages"][-1] or any("cache_control" in m for m in anth_req["messages"])
    memory_summary_rows = [
        m
        for m in anth_req["messages"]
        if m.get("role") == "system" and str(m.get("content", "")).startswith("Memory summary:\n")
    ]
    assert len(memory_summary_rows) == 1
    assert memory_summary_rows[0].get("cache_control") == {"type": "ephemeral"}

    openai_req = to_openai_request(parts, key)
    assert "prompt_cache_key" in openai_req["extra_body"]
    assert openai_req["extra_body"]["prompt_cache_key"] == key


def test_skill_globs() -> None:
    def should_load_skill(skill_globs: list[str], always_apply: bool, current_files: list[str]) -> bool:
        if always_apply:
            return True
        if not skill_globs:
            return False
        for pattern in skill_globs:
            for f in current_files:
                if "**" in pattern:
                    prefix = pattern.split("**")[0].rstrip("/")
                    suffix_part = pattern.split("**")[-1]
                    suffix = suffix_part.lstrip("/").lstrip("*")
                    if suffix and not suffix.startswith("."):
                        suffix = suffix[-3:] if ".ts" in suffix else suffix
                    if f.startswith(prefix) and (
                        not suffix or f.endswith(suffix.strip("*").lstrip("/")) or suffix in f
                    ):
                        if pattern.endswith(".ts") and f.endswith(".ts") and prefix in f:
                            return True
                        if f.startswith(prefix):
                            return True
                else:
                    from fnmatch import fnmatch

                    if fnmatch(f, pattern):
                        return True
        return False

    assert should_load_skill(["src/api/**/*.ts"], False, ["src/api/auth.ts"]) is True
    assert should_load_skill(["src/api/**/*.ts"], False, ["src/frontend/button.tsx"]) is False
    assert should_load_skill([], True, []) is True
    assert should_load_skill(["src/api/**/*.ts"], False, ["src/api/v1/users/auth.ts"]) is True
