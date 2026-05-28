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
- Fires only on tool calls that mutate the staged tree:

  * ``fs.write_file`` / ``fs.edit_file`` / ``fs.apply_patch`` —
    projects the touched path into the staged set (status ``A``
    if the file does not yet exist on disk, otherwise ``M``) so
    :func:`classify_intent` sees the about-to-be-produced snapshot;
  * ``fs.run_bash`` whose command starts with ``git add`` or
    ``git commit`` — the bash call may stage arbitrary paths we
    cannot statically inspect; the middleware uses the currently
    staged set as-is (the git hook covers the post-stage drift
    case at ``commit-msg`` time).

- Reads the session's working PR-description draft from a path
  injected at construction time (typically
  ``~/.fa/state/runs/<run_id>/pr_draft.md`` per M-7 row Q-N item).
  When the draft file does not exist, the middleware allows: the
  agent has not yet declared its intent and the
  ``prepare-commit-msg`` git hook is the earlier seat that pulls
  the placeholder buffer.
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
from fa.inner_loop.hooks.base import (
    Decision,
    GuardMiddleware,
    HookPayload,
    LifecyclePoint,
)
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

# Bash command prefixes that stage / commit changes. Matched against
# the stripped command; further arguments (paths, flags) do not
# affect the match. Exact match or space-delimited prefix prevents
# false positives such as ``git add--interactive`` or ``git commit-tree``.
_MUTATING_BASH_PREFIXES: tuple[str, ...] = ("git add", "git commit")


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
    """Project the about-to-happen mutation into the staged-diff set.

    For ``fs.write_file`` / ``fs.edit_file`` / ``fs.apply_patch``:
    append the touched path as a staged entry so :func:`classify_intent`
    includes it. Status letter is ``A`` (new file) when the path does
    not yet exist on disk, otherwise ``M`` (modified) — this keeps the
    middleware's verdict aligned with the git hook's post-stage snapshot.
    Existing staged rows are left untouched (the classifier only looks
    at the path / status enum, not at content).

    For ``fs.run_bash``: return the current staged set unchanged. The
    bash command may stage arbitrary paths via ``git add`` that we
    cannot statically inspect — the git hook is the cheaper seat for
    that drift, firing at ``commit-msg`` time over the actual
    post-stage snapshot.
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


def _is_mutating_call(call: ToolCall) -> bool:
    """Return True iff the tool call would mutate the staged tree.

    The trigger set matches the M-7 row in ``knowledge/BACKLOG.md``:
    direct workspace writes (``fs.write_file``, ``fs.edit_file``,
    ``fs.apply_patch``) plus index-mutating bash invocations
    (``git add`` / ``git commit``). Other bash commands are not
    statically classifiable as mutating, so the middleware does not
    gate them; the git hook catches anything that ultimately
    produces a commit.
    """

    if call.name in _MUTATING_TOOL_NAMES:
        return True
    if call.name == "fs.run_bash":
        command = str(call.params.get("command", "")).strip()
        return any(
            command == prefix or command.startswith(prefix + " ")
            for prefix in _MUTATING_BASH_PREFIXES
        )
    return False


class IntentGuard(GuardMiddleware):
    """Harness-time PR-intent enforcement on ``BEFORE_TOOL_EXEC``.

    Construction:

    - ``repo_root`` — the First-Agent workspace root (used for
      :func:`resolve_citation` and the subprocess fallback ``cwd``).
    - ``draft_path`` — absolute path to the session's working PR
      description draft. The session bootstrap is expected to
      resolve this to ``~/.fa/state/runs/<run_id>/pr_draft.md``
      per the M-7 row Q-N amendment; tests pass a ``tmp_path``-
      rooted file directly.
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
        draft_path: Path,
        git_runner: GitRunner | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._draft_path = draft_path
        self._git_runner: GitRunner = git_runner or self._default_git_runner

    def _default_git_runner(self) -> str:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout

    def handle(self, point: LifecyclePoint, payload: HookPayload) -> Decision:
        if point is not LifecyclePoint.BEFORE_TOOL_EXEC:
            return Decision.allow()
        if payload.tool_call is None:
            return Decision.allow()
        if not _is_mutating_call(payload.tool_call):
            return Decision.allow()
        if not self._draft_path.is_file():
            # Session has not declared its intent yet; the
            # prepare-commit-msg hook (M-6) is the earlier seat that
            # pulls the placeholder buffer.
            return Decision.allow()
        try:
            stdout = self._git_runner()
        except (subprocess.CalledProcessError, OSError):
            # Don't gate when git is unreachable — the git hook is
            # the cheaper / surer seat in that environment.
            return Decision.allow()
        draft_text = self._draft_path.read_text(encoding="utf-8")
        staged = parse_name_status(stdout)
        projected = _project_call(payload.tool_call, staged, self._repo_root)
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
