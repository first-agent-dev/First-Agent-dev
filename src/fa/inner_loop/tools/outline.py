"""S12.7 (CT9/GAP10) — outline folding: structural maps of py/md files.

Produced for ``fs_search output_mode='outline'``: symbol/section rows with
EXACT line ranges designed to paste straight into ``fs_read_file``'s
``start_line``/``end_line`` (the S12.7 discovery chain:
files -> outline -> read).

Design notes (CT9, R20-corrected): ``structural_index``'s stored SymbolRow
carries only sym_id/path/qualname/kind/start_line/end_line/docstring —
decorator_line/depth/signature do NOT exist there. This module computes
them itself from ``ast`` and only keeps the ROW SHAPE compatible.

Pure functions: no I/O, no workspace knowledge — the caller (fs_search)
owns path routing, size caps, and failure steering. ``SyntaxError`` from
``fold_python_source`` propagates on purpose: the tool layer turns it into
a structured fail steering to matches/read (this module never guesses).
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import override

# Read cap enforced by the CALLER (fs_search) before reading a file for
# outlining — 2MB keeps the fold bounded on pathological inputs.
OUTLINE_MAX_READ_BYTES = 2_000_000
# Default symbol/section row count (CT9); the byte cap governs the real
# ceiling — there is deliberately no separate hard row max.
OUTLINE_DEFAULT_LIMIT = 60
# Signatures are navigation aids, not source dumps.
_SIGNATURE_MAX_CHARS = 160

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_MD_SECTION = re.compile(r"^\s*§\s*(.+?)\s*$")
# Banner = inline-name divider: the NAME must start/end with a non-divider
# char, so a BARE divider line ("# ----...----") never matches (negative-pinned).
_PY_BANNER = re.compile(r"^#\s*[=\-─]{2,}\s*([^\s=\-─].*?[^\s=\-─])\s*[=\-─]{2,}\s*$")
_PY_SECTION = re.compile(r"^#\s*§\s*(.+?)\s*$")

SYMBOL_KINDS = frozenset({"function", "class", "async_function"})


@dataclass(frozen=True)
class OutlineRow:
    """One outline row — symbol or section, in document order."""

    kind: str  # "function" | "class" | "async_function" | "section"
    name: str
    start_line: int
    end_line: int
    depth: int  # symbols: enclosing def/class count (top level = 0); sections: heading level
    signature: str | None = None  # symbols only


def _render_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Compact ``name(args) -> ret`` rendering; bounded length."""
    a = node.args
    parts: list[str] = []
    pos = [ast.unparse(x) for x in (*a.posonlyargs, *a.args)]
    defaults = [ast.unparse(d) for d in a.defaults]
    pad = len(pos) - len(defaults)
    for i, p in enumerate(pos):
        if i >= pad and defaults[i - pad] is not None:
            parts.append(f"{p}={defaults[i - pad]}")
        else:
            parts.append(p)
    if a.vararg is not None:
        parts.append(f"*{ast.unparse(a.vararg)}")
    for k, d in zip(a.kwonlyargs, a.kw_defaults, strict=True):
        rendered = ast.unparse(k)
        parts.append(f"{rendered}={ast.unparse(d)}" if d is not None else rendered)
    if a.kwarg is not None:
        parts.append(f"**{ast.unparse(a.kwarg)}")
    ret = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    sig = f"{node.name}({', '.join(parts)}){ret}"
    if len(sig) > _SIGNATURE_MAX_CHARS:
        sig = sig[: _SIGNATURE_MAX_CHARS - 1] + "…"
    return sig


class _FoldVisitor(ast.NodeVisitor):
    """Collect def/class rows in DOCUMENT order with nesting depth."""

    def __init__(self) -> None:
        self.rows: list[OutlineRow] = []
        self._depth = 0

    def _symbol_start(self, node: ast.AST) -> int:
        decorators = getattr(node, "decorator_list", [])
        return int(min([d.lineno for d in decorators] + [node.lineno]))  # type: ignore[attr-defined]

    def _visit_def(self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        self.rows.append(
            OutlineRow(
                kind=kind,
                name=node.name,
                start_line=self._symbol_start(node),
                end_line=node.end_lineno or node.lineno,
                depth=self._depth,
                signature=_render_signature(node),
            )
        )
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_def(node, "function")

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_def(node, "async_function")

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.rows.append(
            OutlineRow(
                "class",
                node.name,
                self._symbol_start(node),
                node.end_lineno or node.lineno,
                self._depth,
                None,
            )
        )
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1


def _py_section_rows(source_lines: list[str]) -> list[OutlineRow]:
    """Section rows from banner-sandwich comments + ``# §`` ONLY.

    A plain ``# comment`` is NEVER a section (negative-pinned): banners
    require delimiter runs (``# ─── NAME ───`` / ``# --- NAME ---``), and
    explicit sections require the ``§`` marker.
    """
    rows: list[OutlineRow] = []
    starts: list[tuple[int, str]] = []
    for idx, line in enumerate(source_lines, start=1):
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        m = _PY_BANNER.match(stripped) or _PY_SECTION.match(stripped)
        if m and m.group(1).strip():
            starts.append((idx, m.group(1).strip()))
    for i, (line_no, name) in enumerate(starts):
        end = starts[i + 1][0] - 1 if i + 1 < len(starts) else len(source_lines)
        rows.append(OutlineRow("section", name, line_no, end, 0, None))
    return rows


def fold_python_source(source: str) -> list[OutlineRow]:
    """Fold Python source into symbol + section rows (document order).

    Raises ``SyntaxError`` for unparseable source — the caller steers.
    """
    tree = ast.parse(source)
    visitor = _FoldVisitor()
    visitor.visit(tree)
    rows = visitor.rows + _py_section_rows(source.splitlines())
    rows.sort(key=lambda r: (r.start_line, r.end_line))
    return rows


def fold_markdown(source: str) -> list[OutlineRow]:
    """Fold Markdown into ATX-heading + standalone-``§`` section rows.

    Fenced code blocks (``` / ~~~) are skipped — a ``#`` line inside a
    fence is code, not a heading (negative-pinned).
    """
    lines = source.splitlines()
    fence = re.compile(r"^\s*(```|~~~)")
    in_fence = False
    marks: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines, start=1):
        if fence.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _MD_HEADING.match(line)
        if m:
            marks.append((idx, len(m.group(1)), m.group(2).strip()))
            continue
        m = _MD_SECTION.match(line)
        if m and m.group(1):
            marks.append((idx, 1, m.group(1).strip()))
    rows: list[OutlineRow] = []
    for i, (line_no, level, name) in enumerate(marks):
        end = marks[i + 1][0] - 1 if i + 1 < len(marks) else len(lines)
        rows.append(OutlineRow("section", name, line_no, end, level, None))
    return rows


__all__ = [
    "OUTLINE_DEFAULT_LIMIT",
    "OUTLINE_MAX_READ_BYTES",
    "SYMBOL_KINDS",
    "OutlineRow",
    "fold_markdown",
    "fold_python_source",
]
