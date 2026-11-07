"""``pr_prepare`` — write an optional per-session PR/work note.

The tool renders structured PR-intent headers and optional narrative into
``~/.fa/session-log/<run_id>/pr_draft.md``. It remains a human-readable review
surface and does not authorize or gate workspace mutation. Its contents and
same-process provenance are not runtime policy evidence.

This module imports the same ``HEADER_*`` constants, invariant-prefix table,
and pure :func:`fa.hygiene.pr_intent.validate_commit_msg` used by the commit-msg
hook. That shared validator keeps the note format aligned with commit-boundary
validation; the hook remains the authoritative staged-path/test-edit seat.

Design notes:

* The draft target is closure-captured at construction time; the LLM does not
  get a ``path`` parameter.
* ``PrDraftStore`` atomically persists the note and tracks a same-process digest
  to detect accidental artifact tampering. The digest is not mutation authority.
* Permission tier is ``"workspace"`` because the tool writes persistent
  session-log state; it does not write project source or grant project writes.
* Validation retains the existing PR-note shape and FIX-only clauses. It may
  reject an invalid note, but that tool result does not block a later workspace
  mutation or make the optional note a write permit.
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
        "invariant": {
            "type": "string",
            "minLength": 1,
            # S12.5 (CT5): document the remaining shape rules inline — the
            # model reads this schema, not the skill doc (live-trial D11:
            # agents burned turns rediscovering the old `n/a` literal).
            "description": (
                "One-line invariant statement. Required prefixes: ADR-RULE -> "
                "'Contract: ...', IMPLEMENT -> 'Implements: ...', FIX -> "
                "'Affects: ...'. RESEARCH and CHORE take free-form text "
                "(e.g. 'n/a (dependency bump)')."
            ),
        },
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
        return f"`degree_of_freedom_closed` is only valid when `intent` is `FIX`; got `{intent.value}`"
    if mechanism is not None:
        return f"`deterministic_mechanism` is only valid when `intent` is `FIX`; got `{intent.value}`"
    return None


def _validate_invariant_prefix(intent: Intent, invariant: str) -> str | None:
    required = INVARIANT_REQUIRED_PREFIXES[intent]
    # S12.5 (CT5): empty tuple = no shape check (RESEARCH/CHORE). The
    # early return must precede the any() below — any(()) is False and
    # would reject every draft for those intents (RN7 empty-tuple trap).
    if not required:
        return None
    if any(invariant.lower().startswith(p.lower()) for p in required):
        return None
    return (
        f"`invariant` value {invariant!r} does not match the required "
        f"shape for `INTENT: {intent.value}` "
        f"(expected to start with one of: {list(required)})"
    )


def build_prepare_pr_tool(draft_store: PrDraftStore) -> ToolSpec:
    """Return the ``pr_prepare`` :class:`ToolSpec` bound to ``draft_store``.

    ``draft_store`` carries the stable on-disk path and an artifact-integrity
    marker for this process; neither grants mutation authorization.
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

        fix_violation = _validate_fix_fields(intent, fix_class=fix_class, dof=dof, mechanism=mechanism)
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
        # the same validator the commit-msg hook uses. Any drift in this
        # renderer surfaces as an optional-note validation error. Staged
        # paths are intentionally empty —
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
        name="pr_prepare",
        description=(
            "Optionally write a human-readable PR/work note to "
            "~/.fa/session-log/<run_id>/pr_draft.md. The note's contents "
            "and provenance do not authorize or gate workspace mutations; "
            "call this only when a review note is useful. The path is fixed "
            "at session bootstrap; the tool takes no `path` parameter."
        ),
        input_schema=_INPUT_SCHEMA,
        permission="workspace",
        handler=handler,
        tags=("pr", "draft", "hygiene"),
    )
