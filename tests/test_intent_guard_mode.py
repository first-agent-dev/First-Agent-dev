"""Runtime IntentGuard retirement and legacy component-mode characterization.

Production ``fa run`` no longer registers IntentGuard. Historical config
spellings are still recognized so operators receive an explicit retired/ignored
warning instead of believing the mode controls runtime writes. Direct component
tests remain useful characterization; they are not production-boundary proof.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.cli import _build_run_hook_registry
from fa.feature_flags import load_feature_flags
from fa.inner_loop import EventLog, load_runtime_limits_from_path
from fa.inner_loop.hooks.base import HookPayload, LifecyclePoint
from fa.inner_loop.hooks.intent_guard import INTENT_GUARD_MODES, IntentGuard
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolCall


@pytest.mark.parametrize(
    "legacy_setting",
    [
        "intent_guard.mode: enforce",
        "intent_guard_mode: enforce",
        "intent_guard:\n    mode: enforce",
        "intent_guard.mode: off",
        "intent_guard_mode: observe",
        "intent_guard:\n    mode: observe",
        "intent_guard.mode: banana",
    ],
)
def test_legacy_runtime_mode_is_explicitly_ignored(legacy_setting: str) -> None:
    result = load_feature_flags(f"feature_flags:\n  {legacy_setting}\n")

    assert any(
        warning.key == "intent.guard.mode" and "retired and ignored" in warning.detail for warning in result.warnings
    )
    assert "intent_guard.mode" not in result.flags.as_dict()
    assert "intent_guard_mode" not in result.flags.as_dict()


def test_run_hook_registry_never_registers_intent_guard(tmp_path: Path) -> None:
    """The common production builder contains no runtime IntentGuard seat."""
    limits = load_runtime_limits_from_path().limits
    log = EventLog(
        tmp_path / "events.jsonl",
        run_id="r19-no-guard",
        redactor=None,
        session_db=None,
        session_id="",
    )
    hooks = _build_run_hook_registry(
        workspace=tmp_path,
        log=log,
        limits=limits,
        redactor=None,
        run_log_dir=tmp_path,
        output_bus_ref=[],
    )
    registered = [hook for chain in hooks._chains.values() for hook in chain]  # type: ignore[attr-defined]

    assert not any(isinstance(hook, IntentGuard) for hook in registered)


def _guard(
    tmp_path: Path,
    *,
    draft_text: str | None,
    git_output: str = "A\tsrc/fa/x.py\n",
    mode: str | None = None,
) -> IntentGuard:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    (repo / "knowledge").mkdir(exist_ok=True)
    (repo / "knowledge" / "llms.txt").write_text("placeholder\n", encoding="utf-8")
    store = PrDraftStore(tmp_path / "pr_draft.md")
    if draft_text is not None:
        store.write_text(draft_text)
    kwargs: dict[str, object] = {
        "repo_root": repo,
        "draft_store": store,
        "git_runner": lambda: git_output,
    }
    if mode is not None:
        kwargs["mode"] = mode
    return IntentGuard(**kwargs)  # type: ignore[arg-type]


def _write_call() -> HookPayload:
    return HookPayload(
        tool_call=ToolCall(name="fs_write_file", params={"path": "src/fa/x.py", "content": "x"}),
    )


def test_component_mode_enum_is_pinned() -> None:
    assert INTENT_GUARD_MODES == frozenset({"enforce", "observe", "off"})


def test_component_enforce_still_denies_missing_draft(tmp_path: Path) -> None:
    """Component characterization only; production ``fa run`` does not wire it."""
    decision = _guard(tmp_path, draft_text=None).handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "deny"
    assert "missing or untrusted current-session PR draft" in decision.reason


def test_component_observe_allows_missing_draft_with_reason(tmp_path: Path) -> None:
    decision = _guard(tmp_path, draft_text=None, mode="observe").handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "allow"
    assert decision.reason.startswith("would-deny(observe): ")


def test_component_unknown_mode_falls_back_to_enforce(tmp_path: Path) -> None:
    decision = _guard(tmp_path, draft_text=None, mode="banana").handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "deny"


def test_component_off_is_not_an_allow_all_mode(tmp_path: Path) -> None:
    decision = _guard(tmp_path, draft_text=None, mode="off").handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "deny"
