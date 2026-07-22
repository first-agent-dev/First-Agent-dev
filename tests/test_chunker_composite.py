"""Tests for :class:`fa.chunker.CompositeChunker` extension routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.chunker import CompositeChunker, default_chunker


def _write(tmp_path: Path, name: str, body: str) -> Path:
    target = tmp_path / name
    target.write_text(body, encoding="utf-8")
    return target


@pytest.mark.parametrize(
    ("name", "expected_lang"),
    [
        ("plain.txt", "text"),
        ("script.py", "python"),
        ("module.go", "go"),
        ("profile.ps1", "powershell"),
        ("module.psm1", "powershell"),
        ("ui.ts", "typescript"),
        ("ui.tsx", "tsx"),
        ("ui.js", "javascript"),
        ("ui.jsx", "jsx"),
        ("config.yaml", "yaml"),
        ("config.yml", "yaml"),
        ("config.toml", "toml"),
        ("config.json", "json"),
        ("unknown.xyz", "text"),
    ],
)
def test_extension_routes_to_one_chunk_with_expected_lang(tmp_path: Path, name: str, expected_lang: str) -> None:
    path = _write(tmp_path, name, "content\nmore content\n")

    chunks = CompositeChunker().chunk_file(path)

    assert len(chunks) == 1
    assert chunks[0].lang == expected_lang


def test_markdown_extension_routes_to_markdown_chunker(tmp_path: Path) -> None:
    path = _write(tmp_path, "note.md", "# Title\n\nbody\n")

    chunks = CompositeChunker().chunk_file(path)

    assert chunks[0].lang == "markdown"
    assert chunks[0].parent_title == "Title"


def test_long_txt_with_headings_splits_via_markdown_chunker(tmp_path: Path) -> None:
    """ADR-5 Decision step 1 groups ``*.md`` and ``*.txt`` under the
    heading-aware Markdown pipeline. Long heading-bearing ``.txt`` notes
    must therefore split into one chunk per H1/H2, exactly like ``.md``,
    while the chunk's ``lang`` stays ``"text"`` (not ``"markdown"``).
    """

    sections: list[str] = ["# Top\n", "\n", "Intro paragraph.\n"]
    for i in range(4):
        sections.append(f"\n## Section {i + 1}\n\n")
        sections.append("filler line\n" * 200)
    body = "".join(sections)
    path = _write(tmp_path, "long.txt", body)

    chunks = CompositeChunker().chunk_file(path)

    anchors = [c.anchor for c in chunks]
    assert anchors == ["top", "section-1", "section-2", "section-3", "section-4"]
    assert {c.lang for c in chunks} == {"text"}
    # And the gap-free tiling property still holds, like for .md:
    total_bytes = len(body.encode("utf-8"))
    assert chunks[0].byte_start == 0
    assert chunks[-1].byte_end == total_bytes


def test_short_txt_without_headings_stays_single_chunk(tmp_path: Path) -> None:
    """Heading-less ``.txt`` files use the no-headings fallback inside
    MarkdownChunker and stay a single chunk; ``lang`` remains ``text``.
    """

    body = "alpha\nbeta\ngamma\n"
    path = _write(tmp_path, "notes.txt", body)

    chunks = CompositeChunker().chunk_file(path)

    assert len(chunks) == 1
    assert chunks[0].lang == "text"
    assert chunks[0].body == body


def test_default_chunker_is_a_composite() -> None:
    assert isinstance(default_chunker(), CompositeChunker)
