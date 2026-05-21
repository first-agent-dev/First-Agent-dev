"""Tiny YAML-subset helpers shared by Wave-0/Wave-1 ad-hoc parsers.

Two consumers live in the repo today and both will be replaced when
the full YAML loader lands with R-1 HookRegistry runtime (BACKLOG M-1):

- :mod:`fa.config` — capability-flag parser (security-sensitive flags).
- :mod:`fa.verifier.verify_action` — verifier contract loader.

The helpers exist as a single source of truth so a subtle YAML-parsing
edge case fixed in one parser cannot drift away from the other. When
M-1 ships the real loader, this module is deleted.

Devin Review finding 2026-05-20 on PR #19 surfaced that the ad-hoc
parsers stripped neither inline ``# comment`` from values nor from
list items — security-sensitive capability flags silently flipped to
``False`` on a normal YAML inline comment, and verifier contracts
would not match any trace event when contracts grew inline comments.
"""

from __future__ import annotations

__all__ = ["strip_inline_comment"]


def strip_inline_comment(value: str) -> str:
    """Return ``value`` with a YAML inline comment removed.

    Per YAML 1.2 §6.6.1, an inline comment begins with ``#`` and MUST
    be preceded by whitespace. ``"#literal"`` (no preceding whitespace)
    is therefore a literal string starting with ``#``, NOT a comment;
    this function preserves that distinction.

    The function does NOT strip surrounding whitespace from the
    returned value — callers can chain ``.strip()`` / ``.lower()`` as
    they need. This keeps the helper compositional and lets each
    consumer decide on case-folding policy.

    Examples (with ``.strip()`` applied by the caller):

    - ``"true  # enable"`` → ``"true "`` → ``"true"`` after caller
      ``.strip()`` (slice ends at the first ``" #"`` match, so one of
      the two intervening spaces is retained — caller ``.strip()``
      removes it).
    - ``"#literal"`` → ``"#literal"`` (no preceding whitespace; not a
      comment).
    - ``"foo#bar"`` → ``"foo#bar"`` (no preceding whitespace; not a
      comment — treated as literal value).
    - ``"foo #bar"`` → ``"foo"`` → ``"foo"`` after caller ``.strip()``.
    - ``"true\\t# enable # more"`` → ``"true"`` → ``"true"`` after
      caller ``.strip()`` (tab-then-``#`` comes before space-then-``#``
      so the helper picks the earlier comment start).
    - ``""`` → ``""``.
    """

    # Whitespace before ``#`` is required per YAML 1.2 §6.6.1; the
    # whitespace can be a literal space or a tab. We have to inspect
    # BOTH candidate positions and pick the earlier one — otherwise a
    # tab-then-``#`` value with a later space-then-``#`` (e.g.
    # ``"true\t# enable # more"``) would silently strip from the wrong
    # comment start. Devin Review finding 2026-05-20 on PR #19.
    space_idx = value.find(" #")
    tab_idx = value.find("\t#")
    if space_idx == -1 and tab_idx == -1:
        return value
    if space_idx == -1:
        return value[:tab_idx]
    if tab_idx == -1:
        return value[:space_idx]
    return value[: min(space_idx, tab_idx)]
