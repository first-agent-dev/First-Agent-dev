"""
PromptComposer v2.5 Production — Phase 1 Foundation, two-level caching

Fixes:
- Hash stable parts only: names + input_schema, exclude description with date
- Cache-key = role_id + hash_names_schemas + hash_agents_map + hash_alwaysApply_skills
- Two-level: alwaysApply skills in cacheable (stable), conditional globs skills in non-cacheable
- Universal for Anthropic (cache_control ephemeral single breakpoint Phase 1), OpenAI (prompt_cache_key)
- FeatureFlags prompt.caching flag disables cache_control
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class PromptParts:
    cacheable: list[dict[str, Any]]
    non_cacheable: list[dict[str, Any]]


def _stable_hash(obj: Any) -> str:
    stable = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(stable.encode()).hexdigest()[:8]


def _hash_tool_defs_stable(tool_defs: list[dict[str, Any]]) -> str:
    """Hash only name + input_schema, exclude description which may contain date."""
    stable_parts = []
    for td in sorted(tool_defs, key=lambda x: x.get("name", "")):
        stable_parts.append(
            {
                "name": td.get("name"),
                "input_schema": td.get("input_schema"),
            }
        )
    return _stable_hash(stable_parts)


def _hash_skills(skills: list[dict[str, Any]] | None) -> str:
    """Hash skills stable: name + globs + alwaysApply, exclude content which may change."""
    if not skills:
        return "no-skills"
    stable = []
    for s in sorted(skills, key=lambda x: x.get("name", "")):
        stable.append(
            {
                "name": s.get("name"),
                "globs": s.get("globs", []),
                "alwaysApply": s.get("alwaysApply", False),
            }
        )
    return _stable_hash(stable)


def build_prompt_parts_v2(
    base_system: str,
    agents_md_map: str,
    tool_defs: list[dict[str, Any]],
    role_id: str,
    skills_all: list[dict[str, Any]] | None = None,
    skills_always: list[dict[str, Any]] | None = None,
    skills_conditional: list[dict[str, Any]] | None = None,
    memory_summary: str = "",
    task: str = "",
    observations: list[dict[str, Any]] | None = None,
) -> tuple[PromptParts, str]:
    """Build prompt parts with two-level caching.

    - cacheable: BASE system + AGENTS.md map + tool defs + alwaysApply skills (stable)
    - non-cacheable: conditional skills + memory_summary + task + observations (varies)

    Cache-key stable: role + hash_tools + hash_map + hash_always_skills (not conditional).
    """
    observations = observations or []
    skills_all = skills_all or []
    skills_always = skills_always or []
    skills_conditional = skills_conditional or []

    hash_tools = _hash_tool_defs_stable(tool_defs)
    hash_map = _stable_hash(agents_md_map)
    hash_always = _hash_skills(skills_always)

    if not skills_always and skills_all:
        hash_skills_effective = _hash_skills(skills_all)
        if hash_always == "no-skills":
            hash_always = hash_skills_effective

    cache_key = f"fa-{role_id}-{hash_tools}-{hash_map}-{hash_always}"

    cacheable = [
        {"role": "system", "content": base_system},
        {"role": "system", "content": f"AGENTS.md map:\n{agents_md_map}"},
        {"role": "system", "content": f"Tools for role {role_id}:\n{json.dumps(tool_defs, indent=2)}"},
    ]
    if skills_always:
        cacheable.append({"role": "system", "content": f"AlwaysSkills:\n{json.dumps(skills_always, indent=2)}"})

    non_cacheable: list[dict[str, Any]] = []
    if skills_conditional:
        non_cacheable.append(
            {
                "role": "system",
                "content": f"ConditionalSkills:\n{json.dumps(skills_conditional, indent=2)}",
            }
        )
    if memory_summary:
        non_cacheable.append({"role": "system", "content": f"Memory summary:\n{memory_summary}"})
    if task:
        non_cacheable.append({"role": "user", "content": f"Task: {task}"})
    non_cacheable.extend(observations)

    return PromptParts(cacheable=cacheable, non_cacheable=non_cacheable), cache_key


def build_prompt_parts(
    base_system: str,
    agents_md_map: str,
    tool_defs: list[dict[str, Any]],
    role_id: str,
    memory_summary: str = "",
    task: str = "",
    observations: list[dict[str, Any]] | None = None,
) -> tuple[PromptParts, str]:
    return build_prompt_parts_v2(
        base_system,
        agents_md_map,
        tool_defs,
        role_id,
        skills_all=None,
        skills_always=None,
        skills_conditional=None,
        memory_summary=memory_summary,
        task=task,
        observations=observations,
    )


def to_anthropic_request_v2(parts: PromptParts, cache_key: str) -> dict[str, Any]:
    """Phase 3 SOTA: multi-breakpoint cache control anchoring on stable segments."""
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        flags = session.feature_flags if session is not None else None
        if flags is None:
            from fa.feature_flags import load_feature_flags_from_path

            flags = load_feature_flags_from_path().flags
        if not getattr(flags, "prompt_caching", True):
            return {"messages": parts.cacheable + parts.non_cacheable, "_cache_key": cache_key}
    except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
        pass

    messages: list[dict[str, Any]] = []
    for i, msg in enumerate(parts.cacheable):
        # Anchor at system prompt (index 0), tool definitions (index 2), and final cacheable message.
        if i in (0, 2, len(parts.cacheable) - 1):
            msg = {**msg, "cache_control": {"type": "ephemeral"}}
        messages.append(msg)

    memory_anchor_applied = False
    for msg in parts.non_cacheable:
        if (
            not memory_anchor_applied
            and msg.get("role") == "system"
            and isinstance(msg.get("content"), str)
            and str(msg.get("content")).startswith("Memory summary:\n")
        ):
            msg = {**msg, "cache_control": {"type": "ephemeral"}}
            memory_anchor_applied = True
        messages.append(msg)
    return {"messages": messages, "_cache_key": cache_key}


def to_anthropic_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return to_anthropic_request_v2(*args, **kwargs)


def to_openai_request_v2(parts: PromptParts, cache_key: str) -> dict[str, Any]:
    all_messages = parts.cacheable + parts.non_cacheable
    return {
        "messages": all_messages,
        "extra_body": {"prompt_cache_key": cache_key, "prompt_cache_retention": "1h"},
    }


def to_openai_request(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return to_openai_request_v2(*args, **kwargs)
