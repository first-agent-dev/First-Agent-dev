"""Smoke tests for the hygiene token classifier (R-13)."""

from __future__ import annotations

from fa.hygiene import TokenKind, classify_token, classify_tokens


def test_identifier_uppercase_qualifies() -> None:
    assert classify_token("MyClass") == TokenKind.IDENTIFIER
    assert classify_token("ADR-7") == TokenKind.IDENTIFIER


def test_identifier_double_colon_qualifies() -> None:
    assert classify_token("ns::func") == TokenKind.IDENTIFIER


def test_identifier_call_suffix_qualifies() -> None:
    assert classify_token("do_thing()") == TokenKind.IDENTIFIER
    # Spaces inside the call suffix disqualify the token (prose).
    assert classify_token("foo ( )") == TokenKind.PROSE


def test_shell_verb_hard_skip() -> None:
    for verb in ("grep", "git", "ls", "cat"):
        assert classify_token(verb) == TokenKind.SHELL_VERB


def test_shell_verb_hard_skip_is_case_insensitive() -> None:
    """Capitalised shell verbs MUST also be skipped.

    Devin Review finding 2026-05-20 on PR #18 — module docstring says
    "Never treated as identifiers even when uppercased" but the lookup
    was case-sensitive, so `Git` / `GREP` / `Ls` fell through to the
    uppercase-letter heuristic and were misclassified as IDENTIFIER.
    """
    for verb in ("Git", "GIT", "Grep", "GREP", "Ls", "LS", "Cat"):
        assert classify_token(verb) == TokenKind.SHELL_VERB, verb


def test_prose_lowercase_word_is_not_identifier() -> None:
    assert classify_token("older_than") == TokenKind.PROSE
    assert classify_token("search_symbols") == TokenKind.PROSE


def test_prose_for_empty_and_invalid_chars() -> None:
    assert classify_token("") == TokenKind.PROSE
    assert classify_token("   ") == TokenKind.PROSE
    assert classify_token("hello world") == TokenKind.PROSE
    assert classify_token("smile :)") == TokenKind.PROSE


def test_classify_tokens_extracts_in_source_order_and_buckets() -> None:
    text = "Use `grep` not `MyClass`, and run `ns::func` plus `do_it()`; `older_than` stays prose."
    buckets = classify_tokens(text)
    assert buckets[TokenKind.SHELL_VERB] == ["grep"]
    assert buckets[TokenKind.IDENTIFIER] == ["MyClass", "ns::func", "do_it()"]
    assert buckets[TokenKind.PROSE] == ["older_than"]


def test_classify_tokens_preserves_duplicates() -> None:
    text = "first `Foo` second `Foo` third `Foo`"
    buckets = classify_tokens(text)
    assert buckets[TokenKind.IDENTIFIER] == ["Foo", "Foo", "Foo"]


def test_classify_tokens_skips_multiline_spans() -> None:
    # The proper `Mid` pair is captured; the second opening backtick
    # never finds a same-line closing partner because the candidate
    # body would cross a newline, so it is dropped silently.
    text = "start `Mid` ` foo\nbar ` extra"
    buckets = classify_tokens(text)
    assert buckets[TokenKind.IDENTIFIER] == ["Mid"]
