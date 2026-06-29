"""``pr.prepare`` — write the per-session PR-description draft (M-7 §Q-N).

Producer side of the
:class:`fa.inner_loop.hooks.intent_guard.IntentGuard` read seam landed in
PR #22. The middleware reads the draft from
``~/.fa/session-log/<run_id>/pr_draft.md``; without a producer the
``allow-on-no-draft`` branch fired on every mutating tool call and the
guard never actually denied. This tool is the producer: the LLM
composes the header fields per
:doc:`knowledge/skills/pr-creation/SKILL.md` §Output format and the
handler renders them into the exact byte shape M-6's
``validate_commit_msg`` accepts.

Single-source-of-truth (ADR-10 I-1): this module imports the same
``HEADER_*`` constants, the ``_INVARIANT_REQUIRED_PREFIXES`` table, and
runs the same :func:`fa.hygiene.pr_intent.validate_commit_msg` as the
git hook (M-6) and the harness middleware (M-7). One validator powers
three consumers; any drift would surface in M-6's dual-located-rule
snapshot test (``tests/test_pr_intent_snapshot.py``).

Design notes:

* The draft target is closure-captured at construction time; the LLM
  does not get a ``path`` parameter. This removes the «LLM writes to
  the wrong location» failure mode.
* The shared :class:`fa.inner_loop.pr_draft.PrDraftStore` adds
  current-session provenance on top of the stable on-disk file so
  ``IntentGuard`` trusts only drafts produced by this tool in the
  current run, not stale or externally fabricated files.
* Permission tier is ``"workspace"`` because the tool writes to disk.
  The ``read`` / ``workspace`` enum is the only choice the registry
  exposes today; the actual write target is under ``~/.fa/session-log/``,
  but the LLM-observable invariant is «this tool mutates persistent
  state», which is what the ``workspace`` tier signals.
* Validation runs in two layers: (1) explicit per-field checks for
  the FIX-only clauses + invariant prefix, mirroring
  :func:`validate_commit_msg`'s Check 2 / Check 3; (2) a final
  ``validate_commit_msg`` pass on the rendered text as a defensive
  belt-and-braces so any contract drift in this renderer surfaces as
  a tool-level failure rather than a silent corrupt-draft leak into
  ``IntentGuard``.
"""

from __future__ import annotations

from collections.abc import Mapping

from fa.hygiene.pr_intent import (
    CLASS_VALUES,
    HEADER_CLASS,
    HEADER_DET_MECHANISM,
    HEADER_DOF_CLOSED,
    HEADER_INTENT,
    HEADER_INVARIANT,
    INTENT_VALUES,
    INVARIANT_REQUIRED_PREFIXES,
    Intent,
    validate_commit_msg,
)
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import optional_string, require_string

__all__ = ["build_prepare_pr_tool"]


_INPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["intent", "invariant"],
    "properties": {
        "intent": {
            "type": "string",
            "enum": sorted(INTENT_VALUES),
        },
        "invariant": {"type": "string", "minLength": 1},
        "fix_class": {
            "type": "string",
            "enum": sorted(CLASS_VALUES),
        },
        "degree_of_freedom_closed": {"type": "string", "minLength": 1},
        "deterministic_mechanism": {"type": "string", "minLength": 1},
        "body": {"type": "string", "maxLength": 64000},
    },
    "additionalProperties": False,
}


def _render_draft(
    *,
    intent: Intent,
    invariant: str,
    fix_class: str | None,
    dof: str | None,
    mechanism: str | None,
    body: str | None,
) -> str:
    """Compose canonical draft text per skill §Output format.

    Always emits ``INTENT:`` first, ``CLASS:`` second when present,
    ``INVARIANT:`` third, then the FIX-only DOF / MECHANISM clauses,
    then a blank line and the optional free-form body. Byte-identical
    output is required for the M-6 ``validate_commit_msg`` regex to
    parse the draft back the same way the git hook does.
    """

    lines: list[str] = [f"{HEADER_INTENT} {intent.value}"]
    if fix_class is not None:
        lines.append(f"{HEADER_CLASS} {fix_class}")
    lines.append(f"{HEADER_INVARIANT} {invariant}")
    if intent == Intent.FIX:
        # Required-presence enforced by ``_validate_fix_fields`` upstream;
        # we still guard against ``None`` here so the renderer cannot
        # produce a partial FIX header if the caller skipped the checks.
        if dof is not None:
            lines.append(f"{HEADER_DOF_CLOSED} {dof}")
        if mechanism is not None:
            lines.append(f"{HEADER_DET_MECHANISM} {mechanism}")
    if body is not None and body.strip():
        lines.append("")
        lines.append(body.rstrip())
    return "\n".join(lines) + "\n"


def _validate_fix_fields(
    intent: Intent,
    *,
    fix_class: str | None,
    dof: str | None,
    mechanism: str | None,
) -> str | None:
    """Mirror :func:`validate_commit_msg` Checks 2 + 4 for early refusal.

    Returns the first violation message (suitable for
    ``ToolResult.fail``), or ``None`` when all FIX-shape preconditions
    are satisfied. The full ``validate_commit_msg`` pass at the end of
    the handler is the authoritative gate; this function fails fast so
    the LLM sees a focused error message rather than a six-violation
    dump for what is conceptually one omission.
    """

    if intent == Intent.FIX:
        if fix_class is None:
            return f"`INTENT: FIX` requires `fix_class` (one of: {sorted(CLASS_VALUES)})"
        if dof is None:
            return "`INTENT: FIX` requires `degree_of_freedom_closed`"
        if mechanism is None:
            return "`INTENT: FIX` requires `deterministic_mechanism`"
        return None
    if fix_class is not None:
        return f"`fix_class` is only valid when `intent` is `FIX`; got `{intent.value}`"
    if dof is not None:
        return (
            f"`degree_of_freedom_closed` is only valid when `intent` is `FIX`; got `{intent.value}`"
        )
    if mechanism is not None:
        return (
            f"`deterministic_mechanism` is only valid when `intent` is `FIX`; got `{intent.value}`"
        )
    return None


def _validate_invariant_prefix(intent: Intent, invariant: str) -> str | None:
    required = INVARIANT_REQUIRED_PREFIXES[intent]
    if any(invariant.lower().startswith(p.lower()) for p in required):
        return None
    return (
        f"`invariant` value {invariant!r} does not match the required "
        f"shape for `INTENT: {intent.value}` "
        f"(expected to start with one of: {list(required)})"
    )


def build_prepare_pr_tool(draft_store: PrDraftStore) -> ToolSpec:
    """Return the ``pr.prepare`` :class:`ToolSpec` bound to ``draft_store``.

    ``draft_store`` carries both the stable on-disk path and the
    current-session trust marker shared with :class:`IntentGuard`.
    """

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            intent_raw = require_string(params, "intent")
            invariant = require_string(params, "invariant")
            fix_class = optional_string(params, "fix_class")
            dof = optional_string(params, "degree_of_freedom_closed")
            mechanism = optional_string(params, "deterministic_mechanism")
            body = optional_string(params, "body")
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        if intent_raw not in INTENT_VALUES:
            return ToolResult.fail(
                "invalid_params",
                f"`intent` {intent_raw!r} not in closed enum {sorted(INTENT_VALUES)}",
                retryable=True,
            )
        intent = Intent(intent_raw)

        prefix_violation = _validate_invariant_prefix(intent, invariant)
        if prefix_violation is not None:
            return ToolResult.fail("invariant_shape_mismatch", prefix_violation, retryable=True)

        fix_violation = _validate_fix_fields(
            intent, fix_class=fix_class, dof=dof, mechanism=mechanism
        )
        if fix_violation is not None:
            return ToolResult.fail("invalid_params", fix_violation, retryable=True)

        rendered = _render_draft(
            intent=intent,
            invariant=invariant,
            fix_class=fix_class,
            dof=dof,
            mechanism=mechanism,
            body=body,
        )

        # Defensive belt-and-braces: re-validate the rendered text with
        # the same validator IntentGuard / the git hook use. Any drift
        # in this renderer surfaces here rather than as a silent
        # corrupt-draft leak. Staged paths are intentionally empty —
        # citation-resolution against the staged tree is the git
        # hook's job at ``commit-msg`` time, not ours.
        downstream = validate_commit_msg(
            rendered,
            intent,
            staged=[],
            repo_root=draft_store.path.parent,
        )
        # Filter out citation-only violations: the draft is composed
        # before staging in v0.1; ``DETERMINISTIC MECHANISM`` may carry
        # a future ``path/file.ext:line`` citation that does not yet
        # resolve at draft-write time. The commit-msg git hook is the
        # authoritative seat for citation resolution.
        blocking = [v for v in downstream if v.code != "mechanism_citation_unresolved"]
        if blocking:
            # Surface only the first violation as the failure code; the
            # full set is in the message for context.
            first = blocking[0]
            joined = "; ".join(f"{v.code}: {v.message}" for v in blocking)
            return ToolResult.fail(first.code, joined, retryable=True)

        try:
            draft_store.write_text(rendered)
        except (OSError, PermissionError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        return ToolResult.ok(
            f"wrote pr draft ({intent.value})",
            result={
                "path": str(draft_store.path),
                "bytes": len(rendered.encode("utf-8")),
                "intent": intent.value,
            },
        )

    return ToolSpec(
        name="pr.prepare",
        description=(
            "Write the per-session PR-description draft to "
            "~/.fa/session-log/<run_id>/pr_draft.md so the IntentGuard "
            "middleware (M-7) can validate subsequent mutating tool "
            "calls against the declared INTENT / INVARIANT (and the "
            "FIX-only CLASS / DEGREE-OF-FREEDOM CLOSED / "
            "DETERMINISTIC MECHANISM clauses). The path is fixed at "
            "session bootstrap; the tool takes no `path` parameter."
        ),
        input_schema=_INPUT_SCHEMA,
        permission="workspace",
        handler=handler,
        tags=("pr", "draft", "hygiene"),
    )
