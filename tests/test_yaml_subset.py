"""Tests for the shared YAML-subset helper (``fa._yaml_subset``).

Coverage is deliberately tight — the helper is a single function used
by two ad-hoc parsers (``fa.config`` and ``fa.verifier.verify_action``)
and will be deleted when the full YAML loader lands with R-1
HookRegistry runtime (BACKLOG M-1). These tests pin the YAML 1.2
§6.6.1 reading: an inline comment requires whitespace before ``#``.
"""

from __future__ import annotations

import pytest

from fa._yaml_subset import strip_inline_comment


@pytest.mark.parametrize(
    "raw, expected",
    [
        # find(" #") points at the space immediately before `#`, so
        # the returned slice ends with whatever whitespace preceded that
        # last " #". Callers .strip() afterwards, so this is fine.
        ("true  # enable", "true "),
        ("true # enable", "true"),
        ("foo bar # note", "foo bar"),
        ("foo\t# tab-comment", "foo"),
        ("foo\t# inline\twith\ttabs", "foo"),
        # No preceding whitespace — `#` is a literal value char per YAML 1.2.
        ("#literal", "#literal"),
        ("foo#bar", "foo#bar"),
        ("true#literal", "true#literal"),
        # No comment at all — value returned unchanged.
        ("true", "true"),
        ("", ""),
        ("  leading-space-only", "  leading-space-only"),
        # Multiple whitespace + `#` only counts the first occurrence,
        # which is the correct behaviour for a YAML comment cut.
        ("foo  # first # second", "foo "),
        # Devin Review finding 2026-05-20 on PR #19 — when BOTH a tab-
        # then-`#` AND a space-then-`#` are present, the earlier one
        # wins. Without min() the helper used to pick the later space
        # candidate and leak the tab-comment into the returned value.
        ("true\t# enable # more", "true"),
        ("foo\t# t-comment plus space # later", "foo"),
        # Same idea with the space-comment first — already worked, but
        # pinned here so the symmetric case stays locked in.
        ("foo #space-first \t# tab-later", "foo"),
    ],
)
def test_strip_inline_comment(raw: str, expected: str) -> None:
    assert strip_inline_comment(raw) == expected
