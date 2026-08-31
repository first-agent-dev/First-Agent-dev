"""S12.4 (CT4) — IntentGuard 3-state mode toggle (enforce|observe|off).

Covers the three seams of the flag chain, each pinned at its own level:

1. **Loader** (:mod:`fa.feature_flags`) — dual spelling
   ``intent_guard.mode`` / ``intent_guard_mode``, default ``enforce``,
   FAIL_CLOSED membership.
2. **Resolver** (``fa.cli._resolve_intent_guard_mode``) — override wins,
   every degradation path lands on ``enforce``.
3. **Guard + registration** — observe converts both denial sites to
   allows carrying ``would-deny(observe):`` reasons; ``off`` skips
   registration entirely; unknown values fall back to enforce.

Note on the default-config seam: ``DEFAULT_CONFIG_PATH`` is frozen at
import time (config.py:40), so a test cannot redirect it via ``$HOME``.
The no-config and loader-failure branches of the resolver are pinned
directly instead; the loader seam itself is covered by
:func:`fa.feature_flags.load_feature_flags` tests below.

Kill-checks (mutation targets):

- Flip ``_decide``'s observe branch → ``test_observe_*`` fail.
- Route only ONE deny site through ``_decide`` → the other site's
  observe test fails.
- Remove the ``off`` skip in ``_build_run_hook_registry`` → the
  registration test fails.
- Change the unknown-mode fallback to ``observe`` → the fallback test
  fails.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from fa.cli import _build_run_hook_registry, _resolve_intent_guard_mode
from fa.feature_flags import (
    FAIL_CLOSED_FLAGS,
    load_feature_flags,
)
from fa.inner_loop import EventLog, load_runtime_limits_from_path
from fa.inner_loop.hooks.base import HookPayload, LifecyclePoint
from fa.inner_loop.hooks.intent_guard import INTENT_GUARD_MODES, IntentGuard
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolCall

# Reused from the M-7 suite's vocabulary.
_MISSING_DRAFT_SNIPPET = "missing or untrusted current-session PR draft"
_OBSERVE_PREFIX = "would-deny(observe): "
_BAD_FIX_DRAFT = "INTENT: FIX\nCLASS: REPAIR\nINVARIANT: Affects: src/fa/x.py\n"


# ---------------------------------------------------------------------------
# Seam 1 — loader (C0: pure parse, no I/O)
# ---------------------------------------------------------------------------


def test_default_is_enforce() -> None:
    """Absent key → 'enforce' (FAIL_CLOSED default)."""
    flags = load_feature_flags("feature_flags:\n  telemetry.enabled: true\n").flags
    assert flags.intent_guard_mode == "enforce"


def test_dotted_spelling_parses() -> None:
    flags = load_feature_flags("feature_flags:\n  intent_guard.mode: observe\n").flags
    assert flags.intent_guard_mode == "observe"


def test_flat_alias_spelling_parses() -> None:
    flags = load_feature_flags("feature_flags:\n  intent_guard_mode: observe\n").flags
    assert flags.intent_guard_mode == "observe"


def test_nested_form_parses() -> None:
    text = "feature_flags:\n  intent_guard:\n    mode: observe\n"
    assert load_feature_flags(text).flags.intent_guard_mode == "observe"


def test_unknown_value_is_preserved_verbatim() -> None:
    """The loader does not police the enum — the guard fails closed instead.

    Pinning verbatim preservation is what makes the guard-level fallback
    (below) the single choke point for garbage values.
    """
    flags = load_feature_flags("feature_flags:\n  intent_guard.mode: banana\n").flags
    assert flags.intent_guard_mode == "banana"


def test_yaml_off_stays_string_not_bool() -> None:
    """The custom loader stores str-typed flags as raw strings — `off` must
    not become boolean False (which would stringify to 'False' and fail the
    enum check, silently re-enabling enforcement for `mode: off`)."""
    flags = load_feature_flags("feature_flags:\n  intent_guard.mode: off\n").flags
    assert flags.intent_guard_mode == "off"


def test_as_dict_exposes_dotted_key() -> None:
    from fa.feature_flags import FeatureFlags

    assert FeatureFlags().as_dict()["intent_guard.mode"] == "enforce"


def test_fail_closed_membership() -> None:
    """S12.4 contract: the flag is FAIL_CLOSED — missing flags mean the
    guard is active."""
    assert "intent_guard_mode" in FAIL_CLOSED_FLAGS


def test_mode_enum_pinned() -> None:
    assert INTENT_GUARD_MODES == frozenset({"enforce", "observe", "off"})


# ---------------------------------------------------------------------------
# Seam 2 — resolver (C0/C1 boundary: cli helper, loader monkeypatched)
# ---------------------------------------------------------------------------


def test_resolver_override_wins_without_touching_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override short-circuits: a raising loader proves no config read."""

    def _boom() -> object:
        raise AssertionError("loader must not be called when override is set")

    import fa.feature_flags as ff_mod

    monkeypatch.setattr(ff_mod, "load_feature_flags_from_path", _boom)
    assert _resolve_intent_guard_mode("observe") == "observe"


def test_resolver_loader_failure_falls_back_to_enforce(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    import fa.feature_flags as ff_mod

    def _boom() -> object:
        raise RuntimeError("config unreadable")

    monkeypatch.setattr(ff_mod, "load_feature_flags_from_path", _boom)
    with caplog.at_level(logging.WARNING):
        assert _resolve_intent_guard_mode(None) == "enforce"
    assert "enforcing" in caplog.text


# ---------------------------------------------------------------------------
# Seam 3a — guard mode matrix (C1: middleware behaviour)
# ---------------------------------------------------------------------------


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
    (repo / "knowledge" / "llms.txt").write_text("placeholder\n")
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


def test_guard_default_mode_is_enforce(tmp_path: Path) -> None:
    """No mode kwarg → unchanged M-7 deny behaviour (parity pin)."""
    guard = _guard(tmp_path, draft_text=None)
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "deny"
    assert _MISSING_DRAFT_SNIPPET in decision.reason


def test_observe_missing_draft_allows_with_prefixed_reason(tmp_path: Path) -> None:
    """Observe, deny site 1 (missing draft): allow, reason carries the
    original denial so the hook_decision sink keeps the telemetry."""
    guard = _guard(tmp_path, draft_text=None, mode="observe")
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "allow"
    assert decision.reason.startswith(_OBSERVE_PREFIX)
    assert _MISSING_DRAFT_SNIPPET in decision.reason


def test_observe_violation_allows_with_prefixed_reason(tmp_path: Path) -> None:
    """Observe, deny site 2 (shape violations): allow with prefix.

    Separate from the missing-draft site so routing only ONE site through
    ``_decide`` fails one of these two tests.
    """
    guard = _guard(tmp_path, draft_text=_BAD_FIX_DRAFT, mode="observe")
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "allow"
    assert decision.reason.startswith(_OBSERVE_PREFIX)
    assert "IntentGuard:" in decision.reason


def test_enforce_violation_still_denies(tmp_path: Path) -> None:
    """Control for the observe violation test: enforce keeps denying."""
    guard = _guard(tmp_path, draft_text=_BAD_FIX_DRAFT, mode="enforce")
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "deny"
    assert not decision.reason.startswith(_OBSERVE_PREFIX)


def test_unknown_mode_falls_back_to_enforce(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Garbage config value → enforce + warning (fail-closed)."""
    with caplog.at_level(logging.WARNING):
        guard = _guard(tmp_path, draft_text=None, mode="banana")
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "deny"
    assert "unknown mode" in caplog.text


def test_guard_level_off_denies_defensively(tmp_path: Path) -> None:
    """``off`` is a REGISTRATION-level concept (the guard is never built).
    Direct construction with mode='off' must not create an allow-everything
    guard — it denies like enforce. Pinned so a future ``in ("observe",
    "off")`` slip in ``_decide`` is caught."""
    guard = _guard(tmp_path, draft_text=None, mode="off")
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, _write_call())
    assert decision.action == "deny"


# ---------------------------------------------------------------------------
# Seam 3b — registration (C1: builder wiring through the real registry)
# ---------------------------------------------------------------------------


def _build(tmp_path: Path, mode: str | None) -> object:
    limits = load_runtime_limits_from_path().limits
    log = EventLog(
        tmp_path / "events.jsonl",
        run_id="s124",
        redactor=None,
        session_db=None,
        session_id="",
    )
    return _build_run_hook_registry(
        workspace=tmp_path,
        log=log,
        limits=limits,
        redactor=None,
        draft_store=PrDraftStore(tmp_path / "pr_draft.md"),
        run_log_dir=tmp_path,
        output_bus_ref=[],
        intent_guard_mode=mode,
    )


def _intent_guards(hooks: object) -> list[IntentGuard]:
    chains = hooks._chains  # type: ignore[attr-defined]
    return [h for chain in chains.values() for h in chain if isinstance(h, IntentGuard)]


def test_off_skips_registration(tmp_path: Path) -> None:
    hooks = _build(tmp_path, "off")
    assert _intent_guards(hooks) == []


def test_observe_registers_guard_in_observe_mode(tmp_path: Path) -> None:
    hooks = _build(tmp_path, "observe")
    guards = _intent_guards(hooks)
    assert len(guards) == 1
    assert guards[0]._mode == "observe"


def test_default_registers_guard_in_enforce_mode(tmp_path: Path) -> None:
    """No override + no config on the sandbox default path → enforce."""
    hooks = _build(tmp_path, None)
    guards = _intent_guards(hooks)
    assert len(guards) == 1
    assert guards[0]._mode == "enforce"
