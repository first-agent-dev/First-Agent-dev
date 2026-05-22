"""Smoke tests for ``record_gotcha`` (R-8).

Coverage targets:

1. Append-only — second call preserves the first section verbatim
   and adds a new section after it.
2. Atomic-rename — the .tmp sibling does not leak on success.
3. Subject normalisation — multi-line / multi-space subjects
   collapse to single-line; empty subject rejected.
4. Tags trailer — emitted only when at least one tag is non-empty.
5. Parent directory creation — missing parents created
   automatically (no FileNotFoundError).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.tools import record_gotcha


def test_record_gotcha_creates_file_with_expected_section(tmp_path: Path) -> None:
    target = tmp_path / "gotchas.md"
    record_gotcha(
        "ctags missing on Alpine",
        "Install via `apk add ctags-universal`; default repo is `ctags-minimal`.",
        tags=["ctags", "alpine"],
        path=target,
        now="2026-05-20T14:23:01Z",
    )
    body = target.read_text(encoding="utf-8")
    assert body.startswith("## 2026-05-20T14:23:01Z — ctags missing on Alpine\n")
    assert "**Tags:** ctags, alpine\n" in body


def test_record_gotcha_is_append_only(tmp_path: Path) -> None:
    target = tmp_path / "gotchas.md"
    record_gotcha(
        "first",
        "body one",
        path=target,
        now="2026-05-20T01:00:00Z",
    )
    record_gotcha(
        "second",
        "body two",
        path=target,
        now="2026-05-20T02:00:00Z",
    )
    body = target.read_text(encoding="utf-8")
    assert "## 2026-05-20T01:00:00Z — first" in body
    assert "## 2026-05-20T02:00:00Z — second" in body
    assert body.index("first") < body.index("second")


def test_record_gotcha_does_not_leak_tmp_file(tmp_path: Path) -> None:
    target = tmp_path / "gotchas.md"
    record_gotcha("k", "v", path=target, now="2026-05-20T00:00:00Z")
    assert list(tmp_path.glob("*.tmp")) == []


def test_record_gotcha_normalises_subject(tmp_path: Path) -> None:
    target = tmp_path / "gotchas.md"
    record_gotcha(
        "multi\nline   subject",
        "body",
        path=target,
        now="2026-05-20T00:00:00Z",
    )
    body = target.read_text(encoding="utf-8")
    assert "## 2026-05-20T00:00:00Z — multi line subject" in body


def test_record_gotcha_rejects_empty_subject(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-empty"):
        record_gotcha("   ", "body", path=tmp_path / "g.md")


def test_record_gotcha_omits_tags_when_none(tmp_path: Path) -> None:
    target = tmp_path / "gotchas.md"
    record_gotcha(
        "subject",
        "body",
        path=target,
        now="2026-05-20T00:00:00Z",
    )
    body = target.read_text(encoding="utf-8")
    assert "**Tags:**" not in body


def test_record_gotcha_creates_missing_parent(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "deep" / "gotchas.md"
    record_gotcha(
        "subject",
        "body",
        path=target,
        now="2026-05-20T00:00:00Z",
    )
    assert target.exists()


def test_record_gotcha_dedups_only_consecutive_identical_sections(
    tmp_path: Path,
) -> None:
    """Trailing-byte dedup: a second call producing a byte-identical
    section is skipped; a different subject/body/tags re-appends; a
    different ``now`` also re-appends (live-timestamp T-2 runtime keeps
    the append-only contract).

    Captures ADR-7 §Sub-amendment 2026-05-21b «gotchas dedup» rule.
    The smoke CLI relies on this property paired with fixed-clock
    injection to keep ``knowledge/trace/gotchas.md`` byte-stable
    across repeated runs against the same failing tool call.
    """

    target = tmp_path / "gotchas.md"
    record_gotcha("subj", "body", path=target, now="2026-05-21T00:00:00Z")
    first = target.read_text(encoding="utf-8")

    # Same args → dedup (file bytes unchanged).
    record_gotcha("subj", "body", path=target, now="2026-05-21T00:00:00Z")
    assert target.read_text(encoding="utf-8") == first

    # Different body → appends.
    record_gotcha("subj", "body 2", path=target, now="2026-05-21T00:00:00Z")
    after_distinct_body = target.read_text(encoding="utf-8")
    assert after_distinct_body != first
    assert "body 2" in after_distinct_body

    # Different timestamp (T-2 live-clock mode emulated) → appends
    # even when subject/body match the last section.
    record_gotcha("subj", "body 2", path=target, now="2026-05-21T01:00:00Z")
    after_live_clock = target.read_text(encoding="utf-8")
    assert after_live_clock != after_distinct_body
    assert "2026-05-21T01:00:00Z" in after_live_clock
