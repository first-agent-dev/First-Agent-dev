"""IntentGuard (Wave-2 R-PR-C — M-7): harness-time enforcement of §Reference.

A :class:`GuardMiddleware` that re-runs the M-6 PR-intent classifier
over the staged-diff snapshot a tool call is about to mutate, then
re-uses the M-6 commit-message validator against the session's
working PR-description draft. Both seats — the
``prepare-commit-msg`` / ``commit-msg`` git hook (M-6, PR #20) and
this middleware — share the SAME
:func:`fa.hygiene.pr_intent.classify_intent` +
:func:`fa.hygiene.pr_intent.validate_commit_msg` functions, satisfying
ADR-10 I-1 single-source-of-truth: one classifier + one validator,
two consumers.

The middleware:

- Attaches to :attr:`LifecyclePoint.BEFORE_TOOL_EXEC` only (per the
  M-7 row in ``knowledge/BACKLOG.md``); ``BEFORE_LLM_CALL``
  pre-injection is deferred to a Q-N amendment.
- Fires only on tool calls that can mutate the workspace or staged tree:

  * ``fs.write_file`` / ``fs.edit_file`` / ``fs.apply_patch`` —
    projects the touched path into the staged set (status ``A``
    if the file does not yet exist on disk, otherwise ``M``) so
    :func:`classify_intent` sees the about-to-be-produced snapshot;
  * ``fs.run_bash`` — analysed by :mod:`fa.inner_loop.bash_intent` into
    ``READ_ONLY`` / ``VERIFY_ONLY`` / ``INDEX_WRITE`` / ``REPO_WRITE`` /
    ``OPAQUE_EXEC``. Only the first two stay outside the draft-first
    gate. ``INDEX_WRITE`` reuses the current staged snapshot;
    ``REPO_WRITE`` projects high-confidence literal paths;
    ``OPAQUE_EXEC`` requires a trusted draft but makes no fake
    touched-path claims.

- Trusts the session's working PR-description draft only when it was
  produced by ``pr.prepare`` in the current process. The stable file
  path remains ``~/.fa/state/runs/<run_id>/pr_draft.md``, but the
  shared :class:`fa.inner_loop.pr_draft.PrDraftStore` rejects stale or
  externally fabricated files.
- Respects skill §D-5: a user-typed ``INTENT:`` value in the draft
  overrides the classifier output for shape-validation when the
  typed value parses as a closed-enum :class:`Intent` member.
  (The git hook does the same in :func:`_cli_validate`; both seats
  therefore reach the same verdict on the same draft.)
- On any violation, emits :class:`Decision.deny` with a message
  that echoes the git hook's wording so agent error-recovery is
  identical whether the rule fires at hook time or harness time.

References:

- ``knowledge/BACKLOG.md`` §M-7 — contract source, scope estimate,
  Q-N amendment items, blocked-on graph.
- ``knowledge/adr/ADR-7-inner-loop-tool-registry.md`` §8 — hook
  pipeline; before-tool-exec lifecycle point.
- ``knowledge/adr/ADR-8-hook-registry.md`` §3 —
  :class:`GuardMiddleware` contract; first-deny short-circuit; one
  mutation per dispatch.
- ``knowledge/skills/pr-creation/SKILL.md`` §Reference +
  §Output format + §What the hook validates — the same contract
  M-6 pinned; the middleware is the harness-side seat of that
  rule.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import override

from fa.hygiene.pr_intent import (
    HEADER_INTENT,
    INTENT_VALUES,
    Intent,
    StagedPath,
    classify_intent,
    parse_field,
    parse_name_status,
    validate_commit_msg,
)
from fa.inner_loop.bash_intent import BashIntentAnalysis, BashIntentEffect, analyze_bash_for_intent
from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
)
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolCall

# Public surface — also serves as the explicit re-export for the
# shared classifier / validator so mypy ``--strict`` treats them as
# observable on this module. Tests assert by import identity that
# the same callables power both the M-6 git hook and this middleware
# (ADR-10 I-1 single-source-of-truth).
__all__ = [
    "GitRunner",
    "Intent",
    "IntentGuard",
    "StagedPath",
    "classify_intent",
    "parse_field",
    "parse_name_status",
    "validate_commit_msg",
]

# A pluggable ``git diff --cached --name-status`` runner. Production
# uses the subprocess fallback wired into :meth:`IntentGuard._default_git_runner`;
# tests pass a closure over a pre-canned stdout string so no real git
# invocation is needed (the BACKLOG row mandates the test suite stays
# offline / pure-Python).
GitRunner = Callable[[], str]

# Tool names that directly mutate the workspace / staged tree.
_MUTATING_TOOL_NAMES: frozenset[str] = frozenset(
    {"fs.write_file", "fs.edit_file", "fs.apply_patch"}
)

_DRAFT_REQUIRED_BASH_EFFECTS: frozenset[BashIntentEffect] = frozenset(
    {
        BashIntentEffect.INDEX_WRITE,
        BashIntentEffect.REPO_WRITE,
        BashIntentEffect.OPAQUE_EXEC,
    }
)


_MISSING_DRAFT_REASON = (
    "IntentGuard: missing or untrusted current-session PR draft; call "
    "`pr.prepare` before mutating the workspace or staged tree"
)


def _parse_typed_intent(draft_text: str) -> Intent | None:
    """Return the user-typed ``INTENT:`` value if it parses as a closed-enum member.

    Returns ``None`` when:

    - no ``INTENT:`` line is present (the draft is mid-composition;
      classifier intent applies);
    - the typed value is not in :data:`INTENT_VALUES` (the validator
      will fire ``intent_value_invalid`` anyway; we fall back to the
      classifier intent so shape checks still happen against a real
      enum member).
    """

    raw = parse_field(draft_text, HEADER_INTENT)
    if raw is None:
        return None
    value = raw.strip()
    if value in INTENT_VALUES:
        return Intent(value)
    return None


def _project_call(call: ToolCall, staged: list[StagedPath], repo_root: Path) -> list[StagedPath]:
    """Project a direct filesystem mutation into the staged-diff set.

    Used for ``fs.write_file`` / ``fs.edit_file`` / ``fs.apply_patch``.
    Appends the touched path as a staged entry so :func:`classify_intent`
    sees the about-to-be-produced snapshot. Status letter is ``A``
    (new file) when the path does not yet exist on disk, otherwise ``M``
    (modified) — this keeps the middleware's verdict aligned with the
    git hook's post-stage snapshot. Existing staged rows are left
    untouched (the classifier only looks at the path / status enum, not
    at content).
    """

    if call.name not in _MUTATING_TOOL_NAMES:
        return list(staged)
    raw_path = call.params.get("path", "")
    path = str(raw_path).strip() if raw_path is not None else ""
    if not path:
        return list(staged)

    # Normalise to a repo-relative forward-slash path so classifier
    # prefix checks (``src/fa/…``) line up regardless of whether the
    # raw param is absolute, contains ``./``, or uses backslashes.
    repo_root_resolved = repo_root.resolve()
    candidate = repo_root_resolved / Path(path)
    try:
        resolved = candidate.resolve()
        rel = resolved.relative_to(repo_root_resolved)
        path = str(rel).replace("\\", "/")
    except ValueError:
        pass  # path escapes repo — leave as-is (classifier won't match)

    existing = {entry.path for entry in staged}
    if path in existing:
        return list(staged)

    status = "M" if (repo_root / path).is_file() else "A"
    return [*staged, StagedPath(status=status, path=path)]


def _merge_projected_paths(
    staged: list[StagedPath], projected: tuple[StagedPath, ...]
) -> list[StagedPath]:
    merged = list(staged)
    existing = {entry.path for entry in merged}
    for entry in projected:
        if entry.path in existing:
            continue
        merged.append(entry)
        existing.add(entry.path)
    return merged


def _bash_analysis_for_call(call: ToolCall, repo_root: Path) -> BashIntentAnalysis | None:
    if call.name != "fs.run_bash":
        return None
    command = call.params.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    return analyze_bash_for_intent(command, repo_root=repo_root)


def _requires_draft(call: ToolCall, repo_root: Path) -> tuple[bool, BashIntentAnalysis | None]:
    if call.name in _MUTATING_TOOL_NAMES:
        return True, None
    analysis = _bash_analysis_for_call(call, repo_root)
    if analysis is None:
        return False, None
    return analysis.effect in _DRAFT_REQUIRED_BASH_EFFECTS, analysis


class IntentGuard(GuardMiddleware):
    """Harness-time PR-intent enforcement on ``BEFORE_TOOL_EXEC``.

    Construction:

    - ``repo_root`` — the First-Agent workspace root (used for
      :func:`resolve_citation` and the subprocess fallback ``cwd``).
    - ``draft_store`` — session-local trust wrapper around the stable
      ``~/.fa/state/runs/<run_id>/pr_draft.md`` path. Only text written
      via ``pr.prepare`` in the current process is trusted.
    - ``git_runner`` — optional injection point for the
      ``git diff --cached --name-status`` invocation. Defaults to
      the subprocess fallback. Tests inject a closure over a
      pre-canned stdout string so the suite stays offline.
    """

    name = "IntentGuard"
    attaches_to = (LifecyclePoint.BEFORE_TOOL_EXEC,)

    def __init__(
        self,
        *,
        repo_root: Path,
        draft_store: PrDraftStore,
        git_runner: GitRunner | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._draft_store = draft_store
        self._git_runner: GitRunner = git_runner or self._default_git_runner

    def _default_git_runner(self) -> str:
        result = subprocess.run(
            # Waiver: bare "git" resolved via PATH is the portable convention.
            ["git", "diff", "--cached", "--name-status"],  # noqa: S607
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    @override
    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        if point is not LifecyclePoint.BEFORE_TOOL_EXEC:
            return Decision.allow()
        if payload.tool_call is None:
            return Decision.allow()

        requires_draft, bash_analysis = _requires_draft(payload.tool_call, self._repo_root)
        if not requires_draft:
            return Decision.allow()

        draft_text = self._draft_store.read_current_text()
        if draft_text is None:
            return Decision.deny(_MISSING_DRAFT_REASON)
        try:
            stdout = self._git_runner()
        except (subprocess.CalledProcessError, OSError):
            # Don't gate when git is unreachable — the git hook is
            # the cheaper / surer seat in that environment.
            return Decision.allow()
        staged = parse_name_status(stdout)
        if payload.tool_call.name in _MUTATING_TOOL_NAMES:
            projected = _project_call(payload.tool_call, staged, self._repo_root)
        elif bash_analysis is not None and bash_analysis.effect is BashIntentEffect.REPO_WRITE:
            projected = _merge_projected_paths(staged, bash_analysis.projected)
        else:
            # INDEX_WRITE and OPAQUE_EXEC both validate against the current
            # staged snapshot only. The former is authoritative for `git add`
            # / `git commit`; the latter intentionally makes no fake
            # touched-path claims for opaque execution.
            projected = list(staged)
        classifier_intent = classify_intent(projected)
        typed = _parse_typed_intent(draft_text)
        effective = typed if typed is not None else classifier_intent
        violations = validate_commit_msg(
            draft_text,
            effective,
            projected,
            self._repo_root,
        )
        if not violations:
            return Decision.allow()
        # Echo the git hook's wording so agent error-recovery sees the
        # same shape whether the rule fires at hook time or harness time.
        reason = "IntentGuard: " + "; ".join(v.message for v in violations)
        return Decision.deny(reason)
