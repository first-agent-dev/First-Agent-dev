"""Canonical tool-name map (S13.10) — single source of truth for wire tool names.

**Why this exists.** FA tool names used `namespace.name` (`fs.read_file`,
`pr.prepare`). The OpenAI-standard tool-name pattern is ``^[a-zA-Z0-9_-]{1,64}$``
— no dots, max 64 chars — enforced by OpenAI, Anthropic, NVIDIA, and Gemini. So
strict providers rejected FA's dotted tool definitions with a 400. S13.10 renamed
every tool name dot → underscore, preserving the ``fs_`` / ``pr_`` namespace
prefix. This module is the single source of truth so the rename stays auditable
and a dotted name can never be reintroduced.

**Design (tests-writing skill / CT5).** ``TOOL_NAMES`` is the canonical set of the
**new** wire names. The former ``LEGACY_TO_NEW`` migration ledger (old dotted name
→ new name) was pruned on 2026-08-06 as a completed one-time artifact — it was not
used by any production code. The canonical set is now a direct frozenset; a tool
name must be added here (and to the ``ToolSpec.name`` in ``tools/*.py``) or the
S13.10 composition test fails.

**Names covered (21):**
- 17 canonical ``ToolSpec.name`` wire names (``fs_read_file`` … ``pr_prepare``,
  incl. ``fs_blackboard_query``).
- ``fs_write_file_limited`` — a builder key in ``profiles.py`` (not a standalone
  ToolSpec, but participates in the same naming scheme).
- ``fs_apply_patch`` — referenced in ``intent_guard`` logic/docs (prose), not a
  registered tool.
- ``fs_read`` — a fixture tool name in ``conformance.py`` test scenario.
- ``invoke_workflow`` — **declared ahead of registration (D10).** The chat role's
  system prompt already instructs the model to call it for ``workflow_linear``
  scope estimates, and the escalation design depends on that instruction, but the
  tool itself lands in S4b (``tools/__init__.py``: "invoke_workflow tool will be
  registered in S4"). It is listed here so the canonical ledger matches the
  advertised contract; ``test_prompt_registry_coherence.py`` records it as a
  known-pending exemption that must be deleted once S4b registers the builder,
  at which point the coherence test converts into live enforcement.

**Note on the namespace.** ``invoke_workflow`` deliberately carries neither the
``fs_`` nor the ``pr_`` prefix: it is not a filesystem or PR operation but a
control-flow escalation. The D10 enforcement layers are prefix-agnostic precisely
so that this is expressible — see ``tests/test_s13_10_tool_names.py``.
"""

from __future__ import annotations

import re

# Canonical wire-name pattern (CT1): letters, digits, underscore, hyphen, <=64.
_WIRE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# Canonical set of wire tool names (the target). Every ToolSpec.name in tools/*.py
# must be a member (test_s13_10_tool_names.py::test_map_covers_all_tool_spec_names).
TOOL_NAMES: frozenset[str] = frozenset(
    {
        "fs_apply_patch",
        "fs_blackboard_query",
        "fs_checkpoint",
        "fs_chronicle_search",
        "fs_diff",
        "fs_edit_file",
        "fs_list_tasks",
        "fs_read",
        "fs_read_file",
        "fs_reach",
        "fs_run_bash",
        "fs_search",
        "fs_exploration_metrics",
        "fs_send_ctrl_c",
        "fs_spawn_subagent",
        "fs_undo",
        "fs_usage",
        "fs_write_file",
        "fs_write_file_limited",
        "invoke_workflow",
        "pr_prepare",
    }
)


def is_valid_wire_name(name: str) -> bool:
    """True if ``name`` matches the provider-standard tool-name pattern (CT1)."""
    return bool(_WIRE_NAME_RE.match(name))


__all__ = [
    "TOOL_NAMES",
    "is_valid_wire_name",
]
