"""Heading-aware chunker for Markdown / plain-text prose.

Implements ADR-5 §Decision step 1 (markdown-it-py AST → split on H1/H2,
configurable depth) plus the ADR-5 amendment 2026-04-29 provenance
fields (parent_title, breadcrumb, byte_start/byte_end, topic).

Files with no split-level heading or fewer than ``max_single_chunk_lines``
lines are emitted as a single chunk; otherwise the file is tiled with
one chunk per split-level heading, gap-free, so concatenating chunk
bodies reconstructs the source file (sample-test 4 in
``knowledge/research/chunker-design.md §8``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

from fa.chunker._slug import slugify
from fa.chunker.types import Chunk

# Per ADR-5 §Decision: "Files under ~500 lines stay as one chunk."
DEFAULT_MAX_SINGLE_CHUNK_LINES = 500
# Default split depth = H1 + H2.
DEFAULT_SPLIT_DEPTH = 2


@dataclass(frozen=True)
class _Heading:
    level: int
    text: str
    line_start: int  # 1-based


class MarkdownChunker:
    """Heading-aware Markdown chunker.

    Parameters mirror ADR-5 §Decision step 1's "configurable depth"
    knob plus the §Consequences "single chunk for short files"
    threshold. Defaults are deterministic so two runs over the same
    file always produce identical chunks.
    """

    def __init__(
        self,
        *,
        split_depth: int = DEFAULT_SPLIT_DEPTH,
        max_single_chunk_lines: int = DEFAULT_MAX_SINGLE_CHUNK_LINES,
        lang: str = "markdown",
    ) -> None:
        if not 1 <= split_depth <= 6:
            raise ValueError("split_depth must be in 1..6")
        if max_single_chunk_lines < 1:
            raise ValueError("max_single_chunk_lines must be >= 1")
        self._split_depth = split_depth
        self._max_single_chunk_lines = max_single_chunk_lines
        self._lang = lang
        self._md = MarkdownIt("commonmark")

    def chunk_file(self, path: Path) -> list[Chunk]:
        text = path.read_text(encoding="utf-8")
        return self._chunk_text(path, text)

    def _chunk_text(self, path: Path, text: str) -> list[Chunk]:
        lines = text.splitlines(keepends=True)
        line_byte_offsets = _line_byte_offsets(lines)
        total_lines = len(lines)
        path_str = str(path)
        encoded = text.encode("utf-8")

        frontmatter_meta, frontmatter_end_line = _parse_frontmatter(lines)
        headings = _collect_headings(self._md, text)
        # markdown-it parses the closing ``---`` of YAML frontmatter as a
        # setext-H2 underlining the previous frontmatter line, which would
        # otherwise leak as a phantom split-point with the last frontmatter
        # key as its anchor. Drop everything inside (and on) the frontmatter
        # fence range.
        if frontmatter_end_line:
            headings = [h for h in headings if h.line_start > frontmatter_end_line]
        parent_title = _resolve_parent_title(frontmatter_meta, headings, path)
        topic = frontmatter_meta.get("topic")

        split_points = [h for h in headings if h.level <= self._split_depth]

        if not split_points or total_lines < self._max_single_chunk_lines:
            anchor_source = headings[0].text if headings else path.stem
            anchor = slugify(anchor_source) or slugify(path.stem) or "chunk"
            return [
                Chunk(
                    path=path_str,
                    anchor=anchor,
                    parent_title=parent_title,
                    breadcrumb=(),
                    lang=self._lang,
                    body=text,
                    line_start=1,
                    line_end=max(total_lines, 1),
                    byte_start=0,
                    byte_end=len(encoded),
                    topic=topic,
                ),
            ]

        return _split_by_headings(
            path_str=path_str,
            encoded=encoded,
            lang=self._lang,
            parent_title=parent_title,
            topic=topic,
            headings=headings,
            split_points=split_points,
            line_byte_offsets=line_byte_offsets,
            total_lines=total_lines,
        )


def _line_byte_offsets(lines_keepends: list[str]) -> list[int]:
    """Byte offset of the start of each 1-based line, with a sentinel
    at index ``len(lines_keepends)`` pointing just past EOF.
    """

    offsets = [0]
    cum = 0
    for line in lines_keepends:
        cum += len(line.encode("utf-8"))
        offsets.append(cum)
    return offsets


def _parse_frontmatter(lines_keepends: list[str]) -> tuple[dict[str, str], int]:
    """Detect a ``---``-delimited YAML frontmatter at the top of the file
    and return single-line ``key: value`` string pairs plus the 1-based
    line number of the closing ``---`` (``0`` when there is no
    frontmatter).

    v0.1 deliberately does NOT pull in a YAML runtime dependency: only
    flat scalar keys are recognised. Multi-line values (block scalars,
    nested mappings, lists) are silently ignored, which is sufficient
    for the two keys the chunker actually needs (``title``, ``topic``).
    Returns ``({}, 0)`` when there is no frontmatter or the closing
    ``---`` is missing.
    """

    if not lines_keepends:
        return {}, 0
    if lines_keepends[0].strip() != "---":
        return {}, 0
    meta: dict[str, str] = {}
    for idx, raw in enumerate(lines_keepends[1:], start=2):
        stripped = raw.rstrip("\r\n")
        if stripped.strip() == "---":
            return meta, idx
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if ":" not in stripped:
            continue
        # Skip nested keys (any leading whitespace) — only top-level scalars.
        if stripped[0] in (" ", "\t"):
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = _strip_paired_quotes(value.strip())
        if key and value:
            meta[key] = value
    # Closing --- not found: be conservative, treat as no frontmatter.
    return {}, 0


def _strip_paired_quotes(value: str) -> str:
    """Strip exactly one matching pair of surrounding ``"`` or ``'``.

    Unpaired or mismatched quotes are kept verbatim — silently dropping
    a single leading quote from malformed YAML loses information that
    callers may legitimately need to see.
    """

    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _collect_headings(md: MarkdownIt, text: str) -> list[_Heading]:
    headings: list[_Heading] = []
    tokens = md.parse(text)
    for i, tok in enumerate(tokens):
        if tok.type != "heading_open" or tok.map is None:
            continue
        # ``tok.markup`` is the raw heading-marker run for ATX headings (``#``,
        # ``##``, ...) but a single ``=``/``-`` for setext headings, so we read
        # the level from ``tok.tag`` (``"h1"``..``"h6"``) which both flavours
        # share.
        level = int(tok.tag[1:])
        text_value = ""
        if i + 1 < len(tokens):
            text_value = _flatten_inline_text(tokens[i + 1])
        headings.append(_Heading(level=level, text=text_value, line_start=tok.map[0] + 1))
    return headings


def _flatten_inline_text(token: Token) -> str:
    if token.type != "inline":
        return (token.content or "").strip()
    if token.children is None:
        return (token.content or "").strip()
    pieces: list[str] = []
    for child in token.children:
        if child.type in ("text", "code_inline"):
            pieces.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            pieces.append(" ")
    return "".join(pieces).strip()


def _resolve_parent_title(meta: dict[str, str], headings: list[_Heading], path: Path) -> str:
    title = meta.get("title")
    if title:
        return title
    for heading in headings:
        if heading.level == 1 and heading.text:
            return heading.text
    return path.stem


def _split_by_headings(
    *,
    path_str: str,
    encoded: bytes,
    lang: str,
    parent_title: str,
    topic: str | None,
    headings: list[_Heading],
    split_points: list[_Heading],
    line_byte_offsets: list[int],
    total_lines: int,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    breadcrumb_stack = _BreadcrumbStack()
    next_heading_idx = 0
    seen_anchors: set[str] = set()

    for sp_idx, sp in enumerate(split_points):
        # Advance the breadcrumb stack across all (non-split-level too)
        # headings up to and including this split point so ancestor
        # tracking is correct even if intermediate H3..H6 are present.
        while (
            next_heading_idx < len(headings)
            and headings[next_heading_idx].line_start <= sp.line_start
        ):
            breadcrumb_stack.observe(headings[next_heading_idx])
            next_heading_idx += 1

        breadcrumb = breadcrumb_stack.ancestors_for(sp)

        line_start = 1 if sp_idx == 0 else sp.line_start
        line_end = (
            split_points[sp_idx + 1].line_start - 1
            if sp_idx + 1 < len(split_points)
            else total_lines
        )
        line_end = max(line_end, line_start)

        byte_start = line_byte_offsets[line_start - 1]
        byte_end = line_byte_offsets[line_end]
        body = encoded[byte_start:byte_end].decode("utf-8")
        base_anchor = slugify(sp.text) or f"section-{sp_idx + 1}"
        anchor = _disambiguate_anchor(base_anchor, seen_anchors)

        chunks.append(
            Chunk(
                path=path_str,
                anchor=anchor,
                parent_title=parent_title,
                breadcrumb=breadcrumb,
                lang=lang,
                body=body,
                line_start=line_start,
                line_end=line_end,
                byte_start=byte_start,
                byte_end=byte_end,
                topic=topic,
            )
        )

    return chunks


def _disambiguate_anchor(base: str, seen: set[str]) -> str:
    """GitHub-style anchor disambiguation.

    Repeated headings (``## Repeat``, ``## Repeat``, ``## Repeat``) would
    otherwise collide on ``repeat``/``repeat``/``repeat`` and break the
    ``(path, anchor)`` tuple as a stable lookup key for the SQLite index
    layer (ADR-1, ADR-3) and the future Mechanical-Wiki search surface.
    Returns ``base`` for the first occurrence and ``base-2``, ``base-3``,
    ... for subsequent ones, skipping any candidate that collides with
    an already-emitted anchor (so an explicit ``## Repeat 2`` heading
    does not get clobbered).
    """

    if base not in seen:
        seen.add(base)
        return base
    n = 2
    while f"{base}-{n}" in seen:
        n += 1
    candidate = f"{base}-{n}"
    seen.add(candidate)
    return candidate


class _BreadcrumbStack:
    """Tracks the heading hierarchy and computes ancestor-only crumbs.

    ``observe`` pops entries with level >= the new heading's level
    before pushing the new heading; ``ancestors_for`` returns every
    entry strictly above the given heading's level (which excludes
    the heading itself once it has been observed).
    """

    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def observe(self, heading: _Heading) -> None:
        while self._stack and self._stack[-1][0] >= heading.level:
            self._stack.pop()
        self._stack.append((heading.level, heading.text))

    def ancestors_for(self, heading: _Heading) -> tuple[str, ...]:
        return tuple(text for level, text in self._stack if level < heading.level)


__all__ = ["DEFAULT_MAX_SINGLE_CHUNK_LINES", "DEFAULT_SPLIT_DEPTH", "MarkdownChunker"]
