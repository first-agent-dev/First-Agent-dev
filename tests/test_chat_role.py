"""Tests for the chat role (S2 of P2 plan — prompt + registry + models.yaml).

Test class: C1 (integration — exercises module boundaries, not just pure functions)
Oracle: structural assertions on prompt registration, profile config, and tool registry contents.
Kill-check: delete any of the three S2 edits and watch the corresponding group fail.

Path inventory:
  Path 1: CHAT_SYSTEM_PROMPT registered in _ROLE_PROMPTS["chat"]
  Path 2: "chat" profile in PROFILES_RAW with correct tool set and stateless config
  Path 3: build_chat_registry() returns correct tools
  Path 4: Security boundary — no write/edit/subagent tools in chat registry
  Path 5: _build_role_registry dispatches "chat" correctly
  Path 6: CHAT_SYSTEM_PROMPT content contains key identity phrases
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.inner_loop.profiles import PROFILES, PROFILES_RAW, TYPED_PROFILES

# ── Imports under test ──────────────────────────────────────────────────────
from fa.inner_loop.prompt import _ROLE_PROMPTS, CHAT_SYSTEM_PROMPT
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.tools import build_chat_registry

# ── Group 1: Prompt registration (kills Edit 1) ─────────────────────────────


class TestPromptRegistration:
    """Verify CHAT_SYSTEM_PROMPT is wired into the role prompt dispatch."""

    def test_chat_key_in_role_prompts(self) -> None:
        assert "chat" in _ROLE_PROMPTS, "chat role not registered in _ROLE_PROMPTS — Edit 1 missing"

    def test_chat_prompt_matches_constant(self) -> None:
        assert _ROLE_PROMPTS["chat"] is CHAT_SYSTEM_PROMPT

    def test_chat_prompt_is_non_empty_string(self) -> None:
        assert isinstance(CHAT_SYSTEM_PROMPT, str)
        assert len(CHAT_SYSTEM_PROMPT) > 50, "CHAT_SYSTEM_PROMPT is suspiciously short"

    def test_chat_prompt_contains_identity_phrases(self) -> None:
        """The prompt must establish the chat role's identity and boundaries."""
        lower = CHAT_SYSTEM_PROMPT.lower()
        # Must mention what chat IS
        assert "read" in lower, "chat prompt must mention read-only capability"
        # Must mention the workflow escalation path
        assert "workflow" in lower, "chat prompt must mention workflow escalation"


# ── Group 2: Profile registration (kills Edit 2) ────────────────────────────


class TestProfileRegistration:
    """Verify the chat profile exists in PROFILES_RAW with correct structure."""

    def test_chat_in_profiles_raw(self) -> None:
        assert "chat" in PROFILES_RAW, "chat profile not in PROFILES_RAW — Edit 2 missing"

    def test_chat_in_profiles_alias(self) -> None:
        """PROFILES is an alias of PROFILES_RAW; both must see chat."""
        assert "chat" in PROFILES

    def test_chat_in_typed_profiles(self) -> None:
        assert "chat" in TYPED_PROFILES

    def test_chat_profile_has_tools(self) -> None:
        profile = PROFILES_RAW["chat"]
        assert "tools" in profile
        tools = profile["tools"]
        assert isinstance(tools, list)
        assert len(tools) >= 3, "chat profile must have at least 3 tools"

    def test_chat_profile_tools_are_read_only(self) -> None:
        """Chat must NOT have write or edit tools."""
        tools = PROFILES_RAW["chat"]["tools"]
        assert "fs_write_file" not in tools, "chat must not have fs_write_file"
        assert "fs_edit_file" not in tools, "chat must not have fs_edit_file"
        assert "fs_spawn_subagent" not in tools, "chat must not have fs_spawn_subagent"

    def test_chat_profile_has_read_file(self) -> None:
        assert "fs_read_file" in PROFILES_RAW["chat"]["tools"]

    def test_chat_profile_has_search(self) -> None:
        assert "fs_search" in PROFILES_RAW["chat"]["tools"]

    def test_chat_profile_has_bash(self) -> None:
        assert "fs_run_bash" in PROFILES_RAW["chat"]["tools"]

    def test_chat_profile_stateless(self) -> None:
        profile = PROFILES_RAW["chat"]
        assert profile.get("stateless") is True, "chat profile must be stateless"

    def test_chat_profile_bash_impl(self) -> None:
        profile = PROFILES_RAW["chat"]
        assert profile.get("bash_impl") == "stateless"


# ── Group 3: Tool registry (kills Edit 3) ───────────────────────────────────


class TestChatRegistry:
    """Verify build_chat_registry() produces the correct tool set."""

    @pytest.fixture()
    def chat_registry(self, tmp_path: Path) -> ToolRegistry:
        """Build a chat registry against a throwaway workspace."""
        return build_chat_registry(tmp_path)

    def test_build_chat_registry_returns_registry(self, chat_registry: ToolRegistry) -> None:
        assert isinstance(chat_registry, ToolRegistry)

    def test_chat_registry_has_read_file(self, chat_registry: ToolRegistry) -> None:
        names = {spec.name for spec in chat_registry.specs()}
        assert "fs_read_file" in names

    def test_chat_registry_has_bash(self, chat_registry: ToolRegistry) -> None:
        names = {spec.name for spec in chat_registry.specs()}
        assert "fs_run_bash" in names

    def test_chat_registry_no_write_file(self, chat_registry: ToolRegistry) -> None:
        """Security boundary: chat cannot write files."""
        names = {spec.name for spec in chat_registry.specs()}
        assert "fs_write_file" not in names, "chat must not have fs_write_file"

    def test_chat_registry_no_edit_file(self, chat_registry: ToolRegistry) -> None:
        """Security boundary: chat cannot edit files."""
        names = {spec.name for spec in chat_registry.specs()}
        assert "fs_edit_file" not in names, "chat must not have fs_edit_file"

    def test_chat_registry_no_prepare_pr(self, chat_registry: ToolRegistry) -> None:
        """Security boundary: chat cannot prepare PRs (that's a coder concern)."""
        names = {spec.name for spec in chat_registry.specs()}
        assert "fs_prepare_pr" not in names, "chat must not have fs_prepare_pr"

    def test_chat_registry_has_search(self, chat_registry: ToolRegistry) -> None:
        names = {spec.name for spec in chat_registry.specs()}
        assert "fs_search" in names


# ── Group 4: CLI dispatch (kills Edit 4) ─────────────────────────────────────


class TestCliDispatch:
    """Verify _build_role_registry dispatches 'chat' to build_chat_registry."""

    def test_build_role_registry_chat(self, tmp_path: Path) -> None:
        from fa.cli import _build_role_registry

        registry = _build_role_registry("chat", tmp_path, bash_timeout_seconds=30)
        names = {spec.name for spec in registry.specs()}
        # Must have read-only tools
        assert "fs_read_file" in names
        # Must NOT have write tools
        assert "fs_write_file" not in names
        assert "fs_edit_file" not in names

    def test_build_role_registry_planner_still_works(self, tmp_path: Path) -> None:
        """Regression: adding chat must not break planner dispatch."""
        from fa.cli import _build_role_registry

        registry = _build_role_registry("planner", tmp_path, bash_timeout_seconds=30)
        names = {spec.name for spec in registry.specs()}
        assert "fs_read_file" in names

    def test_build_role_registry_eval_still_works(self, tmp_path: Path) -> None:
        """Regression: adding chat must not break eval dispatch."""
        from fa.cli import _build_role_registry

        registry = _build_role_registry("eval", tmp_path, bash_timeout_seconds=30)
        names = {spec.name for spec in registry.specs()}
        # eval has search-based tools, not fs_read_file
        assert "fs_search" in names

    def test_build_role_registry_coder_still_works(self, tmp_path: Path) -> None:
        """Regression: coder (the default else branch) still gets write tools."""
        from fa.cli import _build_role_registry

        registry = _build_role_registry("coder", tmp_path, bash_timeout_seconds=30)
        names = {spec.name for spec in registry.specs()}
        assert "fs_write_file" in names
        assert "fs_edit_file" in names


# ── Group 5: Cross-module consistency ────────────────────────────────────────


class TestCrossModuleConsistency:
    """Verify prompt, profile, and registry agree on the chat role's identity."""

    def test_profile_tools_are_subset_of_baseline_tools(self) -> None:
        """Every tool in the chat profile must be a real tool name."""
        chat_tools = set(PROFILES_RAW["chat"]["tools"])
        # These are known-good tool names from the baseline
        known_tools = {
            "fs_read_file",
            "fs_write_file",
            "fs_edit_file",
            "fs_search",
            "fs_run_bash",
            "fs_blackboard_query",
            "fs_exploration_metrics",
            "fs_reach",
            "fs_spawn_subagent",
            "fs_pair_request",
            "fs_prepare_pr",
        }
        unknown = chat_tools - known_tools
        assert not unknown, f"chat profile references unknown tools: {unknown}"

    def test_chat_profile_system_prompt_key(self) -> None:
        """Profile's system_prompt_key must match the _ROLE_PROMPTS key."""
        profile = PROFILES_RAW["chat"]
        prompt_key = profile.get("system_prompt_key", "chat")
        assert prompt_key == "chat"
        assert prompt_key in _ROLE_PROMPTS
