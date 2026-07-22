"""Tests for :class:`fa.chunker.MarkdownChunker`.

Covers ``research/chunker-design.md §8`` sample-tests 2 (Markdown
smoke-test) and 4 (round-trip reconstruction), plus the ADR-5
amendment 2026-04-29 provenance fields.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest

from fa.chunker import MarkdownChunker
from fa.chunker.markdown import DEFAULT_MAX_SINGLE_CHUNK_LINES


def _write(tmp_path: Path, name: str, body: str) -> Path:
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return target


def test_short_markdown_yields_single_chunk(tmp_path: Path) -> None:
    body = "# Title\n\nIntro paragraph.\n\n## Section\n\nSome body text.\n"
    path = _write(tmp_path, "doc.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.lang == "markdown"
    assert chunk.body == body
    assert chunk.line_start == 1
    assert chunk.line_end == body.count("\n")
    assert chunk.byte_start == 0
    assert chunk.byte_end == len(body.encode("utf-8"))
    assert chunk.parent_title == "Title"
    assert chunk.breadcrumb == ()
    assert chunk.anchor == "title"
    assert chunk.topic is None


def test_no_headings_anchors_to_filename_stem(tmp_path: Path) -> None:
    body = "Just some plain text without any heading at all.\n"
    path = _write(tmp_path, "free-form.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.anchor == "free-form"
    assert chunk.parent_title == "free-form"
    assert chunk.body == body


def test_long_markdown_splits_on_h1_h2(tmp_path: Path) -> None:
    sections: list[str] = ["# Top\n", "\n"]
    sections.append("Intro paragraph.\n")
    # Four H2 sections, each padded so the total file is well over the
    # 500-line single-chunk threshold.
    for i in range(4):
        sections.append(f"\n## Section {i + 1}\n\n")
        sections.append("filler line\n" * 200)
    body = "".join(sections)
    path = _write(tmp_path, "long.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    # Five split points: H1 'Top' + 4 H2 sections.
    assert [c.anchor for c in chunks] == [
        "top",
        "section-1",
        "section-2",
        "section-3",
        "section-4",
    ]
    # Tile the file with no gaps.
    assert chunks[0].line_start == 1
    for prev, nxt in pairwise(chunks):
        assert nxt.line_start == prev.line_end + 1
        assert nxt.byte_start == prev.byte_end
    total_bytes = len(body.encode("utf-8"))
    assert chunks[-1].byte_end == total_bytes


def test_breadcrumb_excludes_self_and_tracks_h1_ancestor(tmp_path: Path) -> None:
    body_parts = [
        "# Top\n",
        "\n## Section A\n",
        "\nfiller\n" * 250,
        "\n## Section B\n",
        "\nmore filler\n" * 250,
    ]
    body = "".join(body_parts)
    path = _write(tmp_path, "with-h1.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    by_anchor = {c.anchor: c for c in chunks}
    assert by_anchor["top"].breadcrumb == ()
    assert by_anchor["section-a"].breadcrumb == ("Top",)
    assert by_anchor["section-b"].breadcrumb == ("Top",)


def test_round_trip_reconstruction(tmp_path: Path) -> None:
    sections = ["# T\n", "\n## A\n\n", "alpha\n" * 200, "\n## B\n\n", "beta\n" * 350]
    body = "".join(sections)
    path = _write(tmp_path, "round-trip.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    reconstructed = "".join(c.body for c in chunks)
    assert reconstructed == body


def test_byte_offsets_align_with_line_offsets(tmp_path: Path) -> None:
    sections = ["# T\n", "\n## A\n\n", "x\n" * 250, "\n## B\n\n", "y\n" * 300]
    body = "".join(sections)
    encoded = body.encode("utf-8")
    path = _write(tmp_path, "offsets.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    for chunk in chunks:
        assert encoded[chunk.byte_start : chunk.byte_end].decode("utf-8") == chunk.body


def test_frontmatter_title_and_topic(tmp_path: Path) -> None:
    body = '---\ntitle: "Architecture"\ntopic: architecture\ncompiled: 2026-05-03\n---\n\n# Doc heading\n\nBody.\n'
    path = _write(tmp_path, "front.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    assert len(chunks) == 1
    chunk = chunks[0]
    # Frontmatter title takes precedence over the first H1.
    assert chunk.parent_title == "Architecture"
    assert chunk.topic == "architecture"


def test_split_depth_h1_only(tmp_path: Path) -> None:
    sections = ["# Top\n", "\n"]
    sections.append("intro\n")
    for i in range(3):
        sections.append(f"\n## H2 {i}\n\n")
        sections.append("body\n" * 220)
    sections.append("\n# Second top\n\nstuff\n")
    body = "".join(sections)
    path = _write(tmp_path, "depth.md", body)

    chunks = MarkdownChunker(split_depth=1).chunk_file(path)

    # Only H1 split points are honoured at depth=1.
    assert [c.anchor for c in chunks] == ["top", "second-top"]


def test_invalid_split_depth_rejected() -> None:
    with pytest.raises(ValueError):
        MarkdownChunker(split_depth=0)
    with pytest.raises(ValueError):
        MarkdownChunker(split_depth=7)


def test_invalid_max_lines_rejected() -> None:
    with pytest.raises(ValueError):
        MarkdownChunker(max_single_chunk_lines=0)


def test_default_threshold_is_500_lines() -> None:
    assert DEFAULT_MAX_SINGLE_CHUNK_LINES == 500


def test_frontmatter_close_is_not_a_phantom_split_point(tmp_path: Path) -> None:
    """The closing ``---`` of YAML frontmatter is parsed by markdown-it
    as a setext heading underlining the previous frontmatter line.

    Regression: the chunker used to leak this phantom heading into the
    split-point list, producing a chunk whose anchor was the slugified
    last frontmatter key (e.g. ``compiled-2026-05-03``) and whose body
    started at the frontmatter fence — not on the real document
    structure.
    """

    sections = [
        "---\n",
        'title: "Doc"\n',
        "topic: architecture\n",
        "compiled: 2026-05-03\n",
        "---\n",
        "\n",
        "# Real heading\n\n",
        "Intro.\n",
    ]
    for i in range(3):
        sections.append(f"\n## Section {i + 1}\n\n")
        sections.append("filler\n" * 200)
    body = "".join(sections)
    path = _write(tmp_path, "phantom.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    anchors = [c.anchor for c in chunks]
    # No phantom anchor synthesised from the closing ``---``.
    assert "compiled-2026-05-03" not in anchors
    assert "compiled" not in anchors
    assert anchors == ["real-heading", "section-1", "section-2", "section-3"]
    # And the parent-title still resolves through the frontmatter ``title:``,
    # not through the phantom heading text.
    assert chunks[0].parent_title == "Doc"


def test_frontmatter_preserves_unpaired_leading_quote(tmp_path: Path) -> None:
    """A bare leading ``\"`` without a matching trailing ``\"`` must be
    kept verbatim. The previous ``.strip('"').strip(\"'\")`` chain
    silently dropped one side of the pair, which is data loss for
    malformed YAML the user may want to see in the chunk's
    ``parent_title``.
    """

    body = (
        "---\n"
        'title: "missing-close\n'  # deliberately malformed
        "topic: ok\n"
        "---\n"
        "\n"
        "# Real heading\n\n"
        "Body.\n"
    )
    path = _write(tmp_path, "bad-quote.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    assert len(chunks) == 1
    chunk = chunks[0]
    # Unpaired quote is preserved on the value, not silently elided.
    assert chunk.parent_title == '"missing-close'
    # Topic with no quotes is unchanged.
    assert chunk.topic == "ok"


def test_frontmatter_strips_paired_single_and_double_quotes(tmp_path: Path) -> None:
    """Round-trip the two well-formed quoting styles."""

    body = "---\ntitle: 'Single-quoted'\ntopic: \"double-quoted\"\n---\n\n# Heading\n\nBody.\n"
    path = _write(tmp_path, "quoted.md", body)

    chunk = MarkdownChunker().chunk_file(path)[0]

    assert chunk.parent_title == "Single-quoted"
    assert chunk.topic == "double-quoted"


def test_setext_headings_levels_match_atx(tmp_path: Path) -> None:
    """Setext headings (``===`` / ``---`` underlines) must use the same
    level numbering as their ATX counterparts.

    Regression: an earlier draft computed ``level`` from
    ``len(token.markup)``, which collapsed every setext H2 to level 1
    (markup = ``"-"``, length 1) and broke split-depth filtering,
    parent-title detection, and breadcrumb ancestry.
    """

    sections = [
        "Document Title\n",
        "==============\n",
        "\nintro paragraph.\n\n",
        "Section A\n",
        "---------\n",
        "\n",
        "alpha\n" * 250,
        "\n",
        "Section B\n",
        "---------\n",
        "\n",
        "beta\n" * 250,
    ]
    body = "".join(sections)
    path = _write(tmp_path, "setext.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    anchors = [c.anchor for c in chunks]
    assert anchors == ["document-title", "section-a", "section-b"]
    by_anchor = {c.anchor: c for c in chunks}
    assert by_anchor["document-title"].parent_title == "Document Title"
    # H2 setext children carry the H1 setext ancestor as their breadcrumb,
    # exactly like ATX-style siblings would.
    assert by_anchor["section-a"].breadcrumb == ("Document Title",)
    assert by_anchor["section-b"].breadcrumb == ("Document Title",)


def test_setext_h2_not_split_at_depth_1(tmp_path: Path) -> None:
    """A setext H2 (``---`` underline) must not be a split point when
    ``split_depth=1``.
    """

    sections = [
        "Top\n",
        "===\n",
        "\nintro\n",
        "Sub\n",
        "---\n",
        "\n",
        "filler\n" * 600,
        "\nSecond top\n",
        "==========\n",
        "\nstuff\n",
    ]
    body = "".join(sections)
    path = _write(tmp_path, "setext-depth.md", body)

    chunks = MarkdownChunker(split_depth=1).chunk_file(path)

    assert [c.anchor for c in chunks] == ["top", "second-top"]


def test_unicode_heading_slug_preserves_cyrillic(tmp_path: Path) -> None:
    sections = ["# Установка\n", "\n## Настройка\n\n", "тело\n" * 600]
    body = "".join(sections)
    path = _write(tmp_path, "ru.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    anchors = [c.anchor for c in chunks]
    assert anchors == ["установка", "настройка"]
    # Round-trip with multi-byte UTF-8 still lines up.
    assert "".join(c.body for c in chunks) == body


def test_duplicate_headings_get_disambiguated_anchors(tmp_path: Path) -> None:
    """Repeated heading text used to collide on the same anchor, breaking
    ``(path, anchor)`` as a stable lookup key for the future SQLite
    index. Subsequent occurrences are now suffixed GitHub-style with
    ``-2``, ``-3``, ...; the first occurrence keeps the bare slug.
    """

    sections = ["# Top\n", "\n"]
    for _ in range(3):
        sections.append("\n## Repeat\n\n")
        sections.append("filler\n" * 200)
    body = "".join(sections)
    path = _write(tmp_path, "dups.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    anchors = [c.anchor for c in chunks]
    assert anchors == ["top", "repeat", "repeat-2", "repeat-3"]
    # All anchors must be unique now -- storage layer can rely on
    # ``(path, anchor)`` without an extra ordinal field.
    assert len(set(anchors)) == len(anchors)


def test_duplicate_anchor_disambiguation_skips_existing_explicit_suffix(
    tmp_path: Path,
) -> None:
    """If the doc already contains an explicit ``## Repeat 2`` heading,
    the disambiguation loop must skip ``repeat-2`` to avoid clobbering
    that explicit anchor when a second ``## Repeat`` appears later.
    """

    sections = ["# Top\n", "\n"]
    sections.append("\n## Repeat\n\n")
    sections.append("filler\n" * 200)
    sections.append("\n## Repeat 2\n\n")
    sections.append("filler\n" * 200)
    sections.append("\n## Repeat\n\n")
    sections.append("filler\n" * 200)
    body = "".join(sections)
    path = _write(tmp_path, "explicit-dup.md", body)

    chunks = MarkdownChunker().chunk_file(path)

    anchors = [c.anchor for c in chunks]
    # ``Repeat`` -> ``repeat``; explicit ``Repeat 2`` -> ``repeat-2``;
    # second ``Repeat`` -> ``repeat-3`` (skipping the taken ``repeat-2``).
    assert anchors == ["top", "repeat", "repeat-2", "repeat-3"]
