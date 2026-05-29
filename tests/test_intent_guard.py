"""Behaviour tests for :class:`IntentGuard` (PR C — M-7).

Offline / pure-Python: every test injects a closure ``git_runner``
returning canned ``git diff --cached --name-status`` stdout, so no
real git invocation happens. The middleware imports
:func:`classify_intent` / :func:`validate_commit_msg` directly from
:mod:`fa.hygiene.pr_intent`, so the «single source of truth» property
(ADR-10 I-1: one classifier + one validator, two consumers — the
M-6 git hook and this middleware) is enforced by import identity
(see :func:`test_intent_guard_uses_skill_classifier_directly`).

References:

- ``knowledge/BACKLOG.md`` §M-7 — scope; offline-test mandate.
- ``knowledge/skills/pr-creation/SKILL.md`` §Reference + §Output
  format + §What the hook validates — the shared contract.
"""

from __future__ import annotations

from pathlib import Path

from fa.hygiene import pr_intent
from fa.inner_loop.hooks import intent_guard as intent_guard_mod
from fa.inner_loop.hooks.base import (
    Decision,
    HookPayload,
    LifecyclePoint,
)
from fa.inner_loop.hooks.intent_guard import IntentGuard
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolCall

# A draft that matches the IMPLEMENT shape per skill §Reference
# (`Implements:` prefix). Reused across positive-path tests.
_VALID_IMPLEMENT_DRAFT = (
    "INTENT: IMPLEMENT\nINVARIANT: Implements: knowledge/adr/ADR-7-inner-loop-tool-registry.md §8\n"
)

# A draft missing the FIX anti-shallow-fix clauses (DOF CLOSED +
# DETERMINISTIC MECHANISM). Triggers checks 4-5 from skill §What
# the hook validates.
_BAD_FIX_DRAFT = "INTENT: FIX\nCLASS: REPAIR\nINVARIANT: Affects: src/fa/x.py\n"


_MISSING_DRAFT_SNIPPET = "missing or untrusted current-session PR draft"


def _make_repo(tmp_path: Path) -> Path:
    """Materialise an FA-workspace marker file inside ``tmp_path``.

    :func:`fa.hygiene.pr_intent.resolve_citation` only ever walks the
    staged tree we pass it (no real filesystem reads outside ``tmp_path``),
    so the marker is mostly for parallel structure with production
    repos. Tests stay hermetic.
    """

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "knowledge").mkdir()
    (repo_root / "knowledge" / "llms.txt").write_text("placeholder\n")
    return repo_root


def _make_guard(
    tmp_path: Path,
    *,
    draft_text: str | None,
    git_output: str,
    trusted_draft: bool = True,
) -> tuple[IntentGuard, PrDraftStore]:
    """Construct an :class:`IntentGuard` with the injected fixture state."""

    repo_root = _make_repo(tmp_path)
    draft_store = PrDraftStore(tmp_path / "pr_draft.md")
    if draft_text is not None:
        if trusted_draft:
            draft_store.write_text(draft_text)
        else:
            draft_store.path.parent.mkdir(parents=True, exist_ok=True)
            draft_store.path.write_text(draft_text, encoding="utf-8")
    guard = IntentGuard(
        repo_root=repo_root,
        draft_store=draft_store,
        git_runner=lambda: git_output,
    )
    return guard, draft_store


# ---------------------------------------------------------------------------
# Single-source-of-truth (ADR-10 I-1) sanity
# ---------------------------------------------------------------------------


def test_intent_guard_uses_skill_classifier_directly() -> None:
    """The middleware uses the same ``classify_intent`` + ``validate_commit_msg``
    the git hook uses — proven by import identity, not by string match.

    Any future change to either function in ``fa.hygiene.pr_intent``
    affects both seats automatically, satisfying ADR-10 I-1.
    ``getattr`` (rather than direct attribute access) is used because
    the names are private re-exports inside ``intent_guard.py``; mypy
    ``--strict`` refuses to treat plain ``from ... import ...`` as
    explicit re-exports.
    """

    assert intent_guard_mod.classify_intent is pr_intent.classify_intent
    assert intent_guard_mod.validate_commit_msg is pr_intent.validate_commit_msg


# ---------------------------------------------------------------------------
# Allow-path: non-mutating calls / valid draft
# ---------------------------------------------------------------------------


def test_intent_guard_allows_non_mutating_call(tmp_path: Path) -> None:
    """``fs.read_file`` does not touch the staged tree → middleware is silent."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_VALID_IMPLEMENT_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.read_file", params={"path": "src/fa/x.py"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_allows_when_draft_passes_validation(tmp_path: Path) -> None:
    """``fs.write_file`` to ``src/fa/`` → IMPLEMENT-bucket; matching draft passes."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_VALID_IMPLEMENT_DRAFT,
        git_output="A\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/y.py", "content": "y"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_allows_on_unrelated_bash(tmp_path: Path) -> None:
    """Non-mutating bash (``ls``) is not classified as mutating → allow."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "ls -la"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_allows_verify_only_bash_without_draft(tmp_path: Path) -> None:
    """Known verifier commands stay outside the draft-first gate."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=None,
        git_output="",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "python -m pytest --version"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_allows_non_repo_redirection_without_draft(tmp_path: Path) -> None:
    """Literal sinks outside the repo do not require a draft."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=None,
        git_output="",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "echo hello > /dev/null"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_other_lifecycle_points_allow(tmp_path: Path) -> None:
    """Middleware only attaches to BEFORE_TOOL_EXEC; other points are no-ops."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    after = guard.handle(LifecyclePoint.AFTER_TOOL_EXEC, HookPayload(tool_call=call))
    between = guard.handle(LifecyclePoint.BETWEEN_ROUNDS, HookPayload())
    assert after.action == "allow"
    assert between.action == "allow"


def test_intent_guard_silently_allows_when_git_fails(tmp_path: Path) -> None:
    """Don't gate when git is unreachable — env-fault, not a contract violation."""

    repo_root = _make_repo(tmp_path)
    draft_store = PrDraftStore(tmp_path / "draft.md")
    draft_store.write_text(_VALID_IMPLEMENT_DRAFT)

    def failing_git() -> str:
        raise OSError("git not found")

    guard = IntentGuard(
        repo_root=repo_root,
        draft_store=draft_store,
        git_runner=failing_git,
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


# ---------------------------------------------------------------------------
# Current-session trust / deny-path
# ---------------------------------------------------------------------------


def test_intent_guard_denies_when_no_pr_draft_has_been_prepared(tmp_path: Path) -> None:
    """Missing current-session draft → deny the first mutating call."""

    guard, store = _make_guard(
        tmp_path,
        draft_text=None,
        git_output="A\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert _MISSING_DRAFT_SNIPPET in decision.reason
    assert store.read_current_text() is None


def test_intent_guard_denies_repo_write_bash_without_draft(tmp_path: Path) -> None:
    """High-confidence repo writes via bash must declare intent first."""

    guard, store = _make_guard(
        tmp_path,
        draft_text=None,
        git_output="",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "printf 'x\n' > src/fa/x.py"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert _MISSING_DRAFT_SNIPPET in decision.reason
    assert store.read_current_text() is None


def test_intent_guard_denies_opaque_exec_bash_without_draft(tmp_path: Path) -> None:
    """Opaque execution forms also require a trusted draft first."""

    guard, store = _make_guard(
        tmp_path,
        draft_text=None,
        git_output="",
    )
    call = ToolCall(
        name="fs.run_bash",
        params={
            "command": (
                'python -c "import pathlib; pathlib.Path(\"src/fa/x.py\").write_text(\"x\")"'
            )
        },
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert _MISSING_DRAFT_SNIPPET in decision.reason
    assert store.read_current_text() is None


def test_intent_guard_denies_mutating_ruff_check_without_draft(tmp_path: Path) -> None:
    """`ruff check --fix` must not escape via VERIFY_ONLY."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=None,
        git_output="",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "ruff check --fix ."})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert _MISSING_DRAFT_SNIPPET in decision.reason


def test_intent_guard_allows_repo_write_bash_after_trusted_draft(tmp_path: Path) -> None:
    """After `pr.prepare`, high-confidence repo writes pass the presence gate."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text="INTENT: IMPLEMENT\nINVARIANT: Implements: src/fa/new.py\n",
        git_output="",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "printf 'x\n' > src/fa/new.py"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_denies_when_on_disk_draft_was_not_prepared_this_session(tmp_path: Path) -> None:
    """A stale or externally fabricated file must not be trusted."""

    guard, store = _make_guard(
        tmp_path,
        draft_text="INTENT: CHORE\nINVARIANT: n/a\n",
        git_output="A\tsrc/fa/x.py\n",
        trusted_draft=False,
    )
    assert store.path.is_file()
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert _MISSING_DRAFT_SNIPPET in decision.reason


def test_intent_guard_denies_when_trusted_draft_is_tampered_after_prepare(tmp_path: Path) -> None:
    """Current-session trust is revoked if the file changes after ``pr.prepare``."""

    guard, store = _make_guard(
        tmp_path,
        draft_text="INTENT: CHORE\nINVARIANT: n/a\n",
        git_output="A\tsrc/fa/x.py\n",
    )
    store.path.write_text("INTENT: CHORE\nINVARIANT: n/a\n\nmodified\n", encoding="utf-8")
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert _MISSING_DRAFT_SNIPPET in decision.reason


# ---------------------------------------------------------------------------
# Deny-path: contract violations echo hook wording
# ---------------------------------------------------------------------------


def test_intent_guard_denies_on_invariant_shape_mismatch(tmp_path: Path) -> None:
    """User declared IMPLEMENT but wrote a FIX-shaped INVARIANT prefix → deny."""

    bad_draft = "INTENT: IMPLEMENT\nINVARIANT: Affects: src/fa/x.py\n"
    guard, _ = _make_guard(
        tmp_path,
        draft_text=bad_draft,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert decision.reason.startswith("IntentGuard: ")
    assert "INVARIANT" in decision.reason


def test_intent_guard_denies_when_fix_lacks_mechanism(tmp_path: Path) -> None:
    """``INTENT: FIX`` without DOF / MECHANISM triggers the anti-shallow-fix gate."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert "DEGREE-OF-FREEDOM CLOSED" in decision.reason
    assert "DETERMINISTIC MECHANISM" in decision.reason


def test_intent_guard_denies_on_git_add_via_run_bash(tmp_path: Path) -> None:
    """``git add`` via ``fs.run_bash`` is a staged-tree mutation → middleware fires."""

    bad_draft = "INTENT: IMPLEMENT\nINVARIANT: Affects: src/fa/x.py\n"
    guard, _ = _make_guard(
        tmp_path,
        draft_text=bad_draft,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "git add ."})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert "INVARIANT" in decision.reason


def test_intent_guard_denies_on_git_commit_via_run_bash(tmp_path: Path) -> None:
    """``git commit`` via ``fs.run_bash`` is also a staged-tree mutation."""

    bad_draft = "INTENT: IMPLEMENT\nINVARIANT: Affects: src/fa/x.py\n"
    guard, _ = _make_guard(
        tmp_path,
        draft_text=bad_draft,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.run_bash", params={"command": "git commit -m 'wip'"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"


def test_intent_guard_deny_reason_echoes_validator_wording(tmp_path: Path) -> None:
    """Deny reason concatenates the same violation messages the git hook prints."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    # The same Violation.message strings the validator returns must be
    # observable inside the deny reason — that's how error-recovery
    # stays identical at the hook and middleware seats.
    direct_violations = pr_intent.validate_commit_msg(
        _BAD_FIX_DRAFT,
        pr_intent.Intent.FIX,
        pr_intent.parse_name_status("M\tsrc/fa/x.py\n"),
        Path(guard._repo_root),
    )
    assert direct_violations
    for violation in direct_violations:
        assert violation.message in decision.reason


# ---------------------------------------------------------------------------
# Skill §D-5 override + path projection
# ---------------------------------------------------------------------------


def test_intent_guard_respects_user_intent_override(tmp_path: Path) -> None:
    """User-typed ``INTENT: IMPLEMENT`` overrides classifier (skill §D-5)."""

    # Status M on src/fa/ → classifier would say FIX; user typed
    # IMPLEMENT with the matching Implements: invariant → no violation.
    draft = "INTENT: IMPLEMENT\nINVARIANT: Implements: ADR-7-inner-loop-tool-registry.md §8\n"
    guard, _ = _make_guard(
        tmp_path,
        draft_text=draft,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_invalid_typed_intent_falls_back_to_classifier(tmp_path: Path) -> None:
    """Typed value outside the closed enum → fall back to classifier intent;
    validate_commit_msg's Check 1 still surfaces the bad enum value as a violation.
    """

    bad_draft = "INTENT: NONSENSE\nINVARIANT: Affects: src/fa/x.py\n"
    guard, _ = _make_guard(
        tmp_path,
        draft_text=bad_draft,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"
    assert "NONSENSE" in decision.reason


def test_intent_guard_path_projection_for_fs_write_file(tmp_path: Path) -> None:
    """Empty staged set + new file under ``src/fa/`` → classifier sees IMPLEMENT."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_VALID_IMPLEMENT_DRAFT,
        git_output="",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/new.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_path_projection_research_only_diff(tmp_path: Path) -> None:
    """``fs.write_file`` to ``knowledge/research/`` → RESEARCH intent."""

    research_draft = "INTENT: RESEARCH\nINVARIANT: n/a\n"
    guard, _ = _make_guard(
        tmp_path,
        draft_text=research_draft,
        git_output="",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "knowledge/research/note.md", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_payload_without_tool_call_allows(tmp_path: Path) -> None:
    """Defensive: payload with no ``tool_call`` must not crash the dispatch."""

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload())
    assert decision.action == "allow"


def test_intent_guard_decision_factory_used(tmp_path: Path) -> None:
    """Sanity: returned decisions are constructed via :meth:`Decision.allow` /
    :meth:`Decision.deny` so they satisfy the registry's invariants
    (deny must have a non-empty reason).
    """

    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/x.py", "content": "x"},
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert isinstance(decision, Decision)
    assert decision.action == "deny"
    assert decision.reason  # non-empty


# ---------------------------------------------------------------------------
# Review-driven regression tests (post-M-7 bug-fix sweep)
# ---------------------------------------------------------------------------


def test_intent_guard_exported_from_hooks_package() -> None:
    """IntentGuard must be importable from the hooks package __init__.

    Every other middleware is re-exported there; omitting IntentGuard
    breaks the established convention and causes ImportError for
    consumers using ``from fa.inner_loop.hooks import IntentGuard``.
    """
    from fa.inner_loop.hooks import IntentGuard as ImportedGuard

    assert ImportedGuard is IntentGuard


def test_intent_guard_mutating_call_includes_edit_file(tmp_path: Path) -> None:
    """``fs.edit_file`` is an edit shape per ADR-7 §4 and must trigger the guard."""
    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(
        name="fs.edit_file", params={"path": "src/fa/x.py", "old_string": "a", "new_string": "b"}
    )
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    # Draft is FIX-shaped but lacks DOF/MECHANISM → deny regardless of
    # whether the classifier or the user typed the intent.
    assert decision.action == "deny"


def test_intent_guard_mutating_call_includes_apply_patch(tmp_path: Path) -> None:
    """``fs.apply_patch`` is the second edit shape per ADR-7 §4 and must trigger the guard."""
    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    call = ToolCall(name="fs.apply_patch", params={"path": "src/fa/x.py", "unified_diff": "diff"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "deny"


def test_intent_guard_git_add_prefix_exact_match(tmp_path: Path) -> None:
    """``git add`` exact/space forms stay on the INDEX_WRITE path; unknown
    `git add*` spellings fall back to the generic bash analyser.
    """
    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    exact_call = ToolCall(name="fs.run_bash", params={"command": "git add"})
    assert (
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=exact_call)).action
        == "deny"
    )
    space_call = ToolCall(name="fs.run_bash", params={"command": "git add src/fa/x.py"})
    assert (
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=space_call)).action
        == "deny"
    )

    valid_tmp = tmp_path / "valid"
    valid_tmp.mkdir()
    valid_guard, _ = _make_guard(
        valid_tmp,
        draft_text=_VALID_IMPLEMENT_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    fallback_call = ToolCall(name="fs.run_bash", params={"command": "git add--interactive"})
    assert (
        valid_guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=fallback_call)).action
        == "allow"
    )


def test_intent_guard_git_commit_prefix_exact_match(tmp_path: Path) -> None:
    """``git commit`` exact/space forms stay on the INDEX_WRITE path;
    unknown `git commit*` spellings fall back to generic bash analysis.
    """
    guard, _ = _make_guard(
        tmp_path,
        draft_text=_BAD_FIX_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    exact_call = ToolCall(name="fs.run_bash", params={"command": "git commit"})
    assert (
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=exact_call)).action
        == "deny"
    )
    space_call = ToolCall(name="fs.run_bash", params={"command": "git commit -m 'wip'"})
    assert (
        guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=space_call)).action
        == "deny"
    )

    valid_tmp = tmp_path / "valid"
    valid_tmp.mkdir()
    valid_guard, _ = _make_guard(
        valid_tmp,
        draft_text=_VALID_IMPLEMENT_DRAFT,
        git_output="M\tsrc/fa/x.py\n",
    )
    fallback_call = ToolCall(name="fs.run_bash", params={"command": "git commit-tree"})
    assert (
        valid_guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=fallback_call)).action
        == "allow"
    )


def test_intent_guard_path_projection_for_existing_file_uses_modify_status(tmp_path: Path) -> None:
    """If ``fs.write_file`` targets a file that already exists on disk,
    the projection should use status ``M`` (modified), not ``A`` (added).
    """
    from fa.inner_loop.hooks.intent_guard import _project_call

    repo_root = _make_repo(tmp_path)
    existing = repo_root / "src" / "fa" / "existing.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("old\n", encoding="utf-8")

    call = ToolCall(
        name="fs.write_file",
        params={"path": "src/fa/existing.py", "content": "new\n"},
    )
    projected = _project_call(call, [], repo_root)
    assert len(projected) == 1
    assert projected[0].status == "M"
    assert projected[0].path == "src/fa/existing.py"


def test_intent_guard_path_projection_normalizes_absolute_path(tmp_path: Path) -> None:
    """Absolute paths inside the repo must be normalised to repo-relative
    so classifier prefix checks (``src/fa/…``) still match.
    """
    repo_root = _make_repo(tmp_path)
    draft_store = PrDraftStore(tmp_path / "pr_draft.md")
    draft_store.write_text(_VALID_IMPLEMENT_DRAFT)
    guard = IntentGuard(
        repo_root=repo_root,
        draft_store=draft_store,
        git_runner=lambda: "",
    )
    abs_path = str(repo_root / "src" / "fa" / "new.py")
    call = ToolCall(name="fs.write_file", params={"path": abs_path, "content": "x"})
    decision = guard.handle(LifecyclePoint.BEFORE_TOOL_EXEC, HookPayload(tool_call=call))
    assert decision.action == "allow"


def test_intent_guard_parse_field_is_shared_from_skill_module() -> None:
    """``_parse_typed_intent`` reuses the same :func:`parse_field` parser
    that the git hook's ``_cli_validate`` uses — proven by import identity.
    Eliminates the duplicate regex that previously existed in
    ``intent_guard.py``.
    """
    assert intent_guard_mod.parse_field is pr_intent.parse_field
