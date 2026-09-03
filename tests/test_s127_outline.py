"""S12.7 (CT9/GAP10) — outline folding C0: py symbols, md sections, banners.

Oracle discipline: py symbol ranges are checked against an INDEPENDENTLY
assembled ast expectation (decorator-aware min-lineno / end_lineno), not
hardcoded line numbers — cli.py drifts as the repo edits it, the INVARIANT
(fold == ast truth) must not. The named anchors (_cmd_stats, main) are
asserted structurally (present, depth 0, exact-range == oracle).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.tools.outline import (
    OUTLINE_DEFAULT_LIMIT,
    OUTLINE_MAX_READ_BYTES,
    OutlineRow,
    fold_markdown,
    fold_python_source,
)

_REPO = Path(__file__).resolve().parent.parent / "src" / "fa" / "cli.py"


# ---------------------------------------------------------------------------
# py symbols — real-file oracle (74-symbol cli.py fixture)
# ---------------------------------------------------------------------------


def test_s127_fold_cli_py_matches_ast_truth() -> None:
    """Card kill-check (T-outline-cli): fold_python_source on the real
    src/fa/cli.py agrees with an independently computed ast expectation for
    EVERY top-level def/class (decorator-aware), and the symbol count
    matches the preflight measurement (74 at plan time; >=70 with drift)."""
    source = _REPO.read_text(encoding="utf-8")
    rows = fold_python_source(source)
    syms = [r for r in rows if r.kind != "section"]

    tree = ast.parse(source)
    expected: dict[str, tuple[int, int]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            deco = [d.lineno for d in node.decorator_list]
            expected[node.name] = (min([*deco, node.lineno]), node.end_lineno or node.lineno)

    got = {r.name: (r.start_line, r.end_line) for r in syms if r.depth == 0}
    assert all(got.get(k) == v for k, v in expected.items()), "top-level ranges must equal decorator-aware ast truth"
    assert len(syms) >= 70, f"cli.py symbol count drifted hard: {len(syms)}"
    assert len(syms) == 74  # preflight anchor; bump DELIBERATELY if cli.py grows symbols

    for name in ("_cmd_stats", "main"):
        row = next(r for r in syms if r.name == name)
        assert row.depth == 0
        assert (row.start_line, row.end_line) == expected[name]


def test_s127_fold_decorators_depth_nested_and_signatures() -> None:
    source = (
        "import functools\n"
        "\n"
        "@functools.cache\n"
        "def outer(a, b=1, *args, key=None, **kw) -> str:\n"
        "    class Inner:\n"
        "        def method(self):\n"
        "            return 1\n"
        "    if True:\n"
        "        def conditional(x):\n"
        "            return x\n"
        "    try:\n"
        "        def guarded():\n"
        "            pass\n"
        "    except Exception:\n"
        "        pass\n"
        "    return ''\n"
        "\n"
        "async def pump():\n"
        "    pass\n"
        "\n"
        "one = 1  # not a symbol\n"
    )
    rows = fold_python_source(source)
    by_name = {r.name: r for r in rows if r.kind != "section"}

    outer = by_name["outer"]
    assert outer.start_line == 3, "decorator line MUST be the start (agent pastes read ranges)"
    assert outer.end_line == 16
    assert outer.depth == 0
    assert outer.signature and outer.signature.startswith("outer(a, b=1, *args, key=None, **kw)")

    inner = by_name["Inner"]
    assert inner.kind == "class" and inner.depth == 1 and inner.signature is None
    assert by_name["method"].depth == 2
    assert by_name["conditional"].depth == 1, "if-nested defs are real symbols"
    assert by_name["guarded"].depth == 1, "try-nested defs are real symbols"
    assert by_name["pump"].kind == "async_function"
    assert "one" not in by_name and len([r for r in rows if r.kind != "section"]) == 6


def test_s127_fold_one_liner() -> None:
    rows = fold_python_source("def tiny(): return 1\n")
    assert rows[0].start_line == rows[0].end_line == 1


def test_s127_fold_syntax_error_propagates() -> None:
    """The folder never guesses — SyntaxError propagates; fs_search steers."""
    with pytest.raises(SyntaxError):
        fold_python_source("def broken(:\n")


# ---------------------------------------------------------------------------
# py sections — banner-sandwich + § only; plain # NEVER (negative pin)
# ---------------------------------------------------------------------------


def test_s127_fold_py_sections_banner_and_marker_only() -> None:
    source = (
        "# ─── Setup ────────────────────────────\n"
        "import os\n"
        "\n"
        "# plain comment — NOT a section\n"
        "# another plain comment\n"
        "def f():\n"
        "    pass\n"
        "\n"
        "# § Explicit Section\n"
        "X = 1\n"
    )
    rows = fold_python_source(source)
    sections = [r for r in rows if r.kind == "section"]
    names = [r.name for r in sections]
    assert names == ["Setup", "Explicit Section"], f"plain '#' comments must never be sections: {names}"
    setup = sections[0]
    assert setup.start_line == 1 and setup.end_line == 8, "section spans to the next section"
    assert sections[1].start_line == 9 and sections[1].end_line == 10


# ---------------------------------------------------------------------------
# md — ATX headings + standalone §
# ---------------------------------------------------------------------------


def test_s127_fold_markdown_atx_and_paragraph_marker() -> None:
    source = (
        "# Title\n"
        "intro text\n"
        "## §-less normal heading\n"
        "body\n"
        "\n"
        "§ Standalone Section\n"
        "content under it\n"
        "### Deep\n"
        "more\n"
    )
    rows = fold_markdown(source)
    assert [(r.name, r.depth, r.start_line, r.end_line) for r in rows] == [
        ("Title", 1, 1, 2),
        ("§-less normal heading", 2, 3, 5),
        ("Standalone Section", 1, 6, 7),
        ("Deep", 3, 8, 9),
    ]


def test_s127_fold_markdown_no_false_headings() -> None:
    rows = fold_markdown("plain text with # inline hash\n```\n# fenced code heading\n```\n")
    assert rows == [], "inline/fenced '#' lines are not headings (line-anchored regex)"


def test_s127_outline_constants() -> None:
    assert OUTLINE_MAX_READ_BYTES == 2_000_000
    assert OUTLINE_DEFAULT_LIMIT == 60
    assert isinstance(OutlineRow("function", "f", 1, 2, 0, None), OutlineRow)


# ---------------------------------------------------------------------------
# C1 — fs_search outline branch (tool-level, tmp workspace)
# ---------------------------------------------------------------------------


def _make_tool(tmp_path: Path) -> Any:
    from fa.inner_loop.tools.fs_search import build_fs_search_tool

    (tmp_path / "mod.py").write_text(
        "def alpha():\n    pass\n\n\nclass Beta:\n    def m(self):\n        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "doc.md").write_text("# Title\nbody\n## Sub\n", encoding="utf-8")
    (tmp_path / "bad.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "data.txt").write_text("x", encoding="utf-8")
    return build_fs_search_tool(tmp_path / ".fa" / "fts.db", tmp_path)


def test_s127_outline_branch_py_md_and_defaults(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    r = tool.handler({"path": "mod.py", "output_mode": "outline"})
    assert r.error is None and r.result["mode"] == "outline" and r.result["truncated"] is False
    assert [(x["name"], x["start_line"], x["end_line"], x["depth"]) for x in r.result["rows"]] == [
        ("alpha", 1, 2, 0),
        ("Beta", 5, 7, 0),
        ("m", 6, 7, 1),
    ]
    assert r.result["rows"][1].get("signature") is None  # classes carry no signature
    assert "warnings" not in r.result, "clean run must not warn"
    md = tool.handler({"path": "doc.md", "output_mode": "outline"})
    assert [(x["name"], x["depth"]) for x in md.result["rows"]] == [("Title", 1), ("Sub", 2)]


def test_s127_outline_query_filter_case_insensitive_and_miss(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    r = tool.handler({"path": "mod.py", "output_mode": "outline", "query": "ALPH"})
    assert [x["name"] for x in r.result["rows"]] == ["alpha"], "R21: filter is case-insensitive"
    miss = tool.handler({"path": "mod.py", "output_mode": "outline", "query": "zzz"})
    assert len(miss.result["rows"]) == 3 and miss.result["total"] == 3
    assert any("no symbol matched" in w for w in miss.result["warnings"])


def test_s127_outline_steering_errors(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    d = tool.handler({"path": ".", "output_mode": "outline"})
    assert d.error.code == "invalid_params" and "output_mode='files'" in d.error.message
    x = tool.handler({"path": "data.txt", "output_mode": "outline"})
    assert x.error.code == "invalid_params" and ".py and .md" in x.error.message
    syn = tool.handler({"path": "bad.py", "output_mode": "outline"})
    assert syn.error.code == "invalid_params" and "syntax error" in syn.error.message
    assert "output_mode='matches'" in syn.error.message, "every failure names the better tool"
    big = tool.handler({"path": "mod.py", "output_mode": "outline"})
    assert big.error is None  # size path covered below via monkeypatched constant


def test_s127_outline_size_cap_steers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import fa.inner_loop.tools.fs_search as fss

    tool = _make_tool(tmp_path)
    monkeypatch.setattr(fss, "OUTLINE_MAX_READ_BYTES", 4)
    r = tool.handler({"path": "mod.py", "output_mode": "outline"})
    assert r.error.code == "invalid_params" and "too large" in r.error.message
    assert "output_mode='matches'" in r.error.message


def test_s127_outline_limit_clamps_and_truncation_steering(tmp_path: Path) -> None:
    tool = _make_tool(tmp_path)
    lo = tool.handler({"path": "mod.py", "output_mode": "outline", "limit": 0})
    assert lo.result["returned"] == 1, "lo-clamp lands on limit=1, not the default"
    assert any("minimum 1" in w for w in lo.result["warnings"])
    hi = tool.handler({"path": "mod.py", "output_mode": "outline", "limit": 999})
    assert any("hard cap 500" in w for w in hi.result["warnings"]), "outline cap is 500, not the generic 50"
    one = tool.handler({"path": "mod.py", "output_mode": "outline", "limit": 1})
    assert one.result["returned"] == 1 and one.result["total"] == 3 and one.result["truncated"] is True
    assert any("raise limit" in w for w in one.result["warnings"])


def test_s127_outline_byte_cap_governs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import fa.inner_loop.tools.fs_search as fss

    tool = _make_tool(tmp_path)
    monkeypatch.setattr(fss, "MAX_RESPONSE_BYTES", 120)
    r = tool.handler({"path": "mod.py", "output_mode": "outline"})
    assert r.error is None and r.result["returned"] < 3 and r.result["truncated"] is True
    assert any("byte cap" in w for w in r.result["warnings"])


def test_s127_schema_query_optionality_final(tmp_path: Path) -> None:
    """§A6 v7 final: absent/blank query -> files lists, outline full table,
    matches errors with the grep steer."""
    tool = _make_tool(tmp_path)
    no_q = tool.handler({"path": "doc.md", "output_mode": "matches"})
    assert no_q.error.code == "invalid_params" and "matches" in no_q.error.message
    listing = tool.handler({"path": ".", "output_mode": "files"})
    assert listing.error is None and listing.result["method"] == "walk_listing" and listing.result["files"]
    both = tool.handler({"path": "doc.md", "output_mode": "outline", "query": ""})
    assert both.error is None and len(both.result["rows"]) == 2, "empty string query == absent (full outline)"


def test_s127_fold_py_bare_divider_is_not_a_section() -> None:
    """House style uses bare `# ----` dividers (fs_search.py:39) — they must
    NOT become nameless section rows (found in live output review)."""
    source = "# " + "-" * 75 + "\n# Constants (CT-1, R-14)\n# " + "-" * 75 + "\nX = 1\n\n# ── Real Banner ──\nY = 2\n"
    rows = fold_python_source(source)
    sections = [r for r in rows if r.kind == "section"]
    assert [r.name for r in sections] == ["Real Banner"]
    assert all(r.name.strip() for r in sections), "no nameless sections, ever"
