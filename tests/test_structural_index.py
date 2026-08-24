"""S16 (CT-5): structural index — C0 unit tests.

Fixture modules are written into tmp_path (not a git repo → the safe walker's
os.walk fallback path, same behavior as production for non-git workspaces).
All oracles are structural (row presence, exact qualname/kind/line, edge
presence), never "no exception".
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from fa.memory.structural_index import StructIndexStats, StructuralIndex, SymbolRow, _is_test_path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FIXTURE_MODULE = '''\
"""Fixture: a → b → c → d chain + class + unresolved calls."""
import os


def d() -> str:
    return "d"


def c() -> str:
    return d()


def b() -> str:
    return c()


def a() -> str:
    """Root caller of the chain."""
    return b()


def uses_unresolved() -> str:
    # os.path.join is a module attribute — must stay unresolved in v1.
    return os.path.join("x", "y")


class Greeter:
    """Says hello."""

    def greet(self, name: str) -> str:
        return self._format(name)

    def _format(self, name: str) -> str:
        return f"hello {name}"


async def async_fn() -> str:
    return await d_async()  # noqa: F821  (deliberately unresolved)


def d_async() -> str:  # defined after use — resolution is order-independent
    return "async"
'''


@pytest.fixture
def indexed(tmp_path: Path) -> StructuralIndex:
    _write(tmp_path / "mod.py", FIXTURE_MODULE)
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    stats = index.ensure_indexed(tmp_path)
    assert stats.available is True
    return index


def _find(index: StructuralIndex, name: str, kind: str | None = None) -> list[SymbolRow]:
    return index.find_symbols(name, kind=kind)


# ── schema + extraction ──────────────────────────────────────────────────────


def test_schema_tables_exist(tmp_path: Path) -> None:
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    _write(tmp_path / "mod.py", "def x():\n    return 1\n")
    index.ensure_indexed(tmp_path)
    import sqlite3

    conn = sqlite3.connect(str(tmp_path / ".fa" / "structural.db"))
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()
    assert {"symbols", "calls", "struct_meta"} <= tables


def test_symbol_extraction_qualnames_kinds_lines(indexed: StructuralIndex) -> None:
    rows = _find(indexed, "a")
    assert len(rows) == 1
    a = rows[0]
    assert a.qualname == "a"
    assert a.kind == "function"
    assert a.path == "mod.py"
    # FIXTURE_MODULE literal has a leading newline: line 1 is blank, so the
    # docstring is line 2 and `def a` lands at 17. Pin the offset, not a guess.
    assert a.start_line == 17
    assert a.end_line == 19
    assert a.docstring == "Root caller of the chain."
    # method
    greet = _find(indexed, "greet")[0]
    assert greet.qualname == "Greeter.greet"
    assert greet.kind == "method"
    # the class docstring belongs to the CLASS (not indexed in v1 — Q-AST
    # narrow); the method itself carries no docstring.
    assert greet.docstring is None
    # nested-class method present
    fmt = _find(indexed, "_format")[0]
    assert fmt.qualname == "Greeter._format"
    assert fmt.kind == "method"
    # async fn
    async_row = _find(indexed, "async_fn")[0]
    assert async_row.kind == "function"
    # all four chain functions present
    for name in ("a", "b", "c", "d", "d_async", "uses_unresolved"):
        assert _find(indexed, name), name


# ── callee-resolution heuristics ────────────────────────────────────────────


def test_in_file_name_edge_resolves(indexed: StructuralIndex) -> None:
    import sqlite3

    a = _find(indexed, "a")[0]
    b = _find(indexed, "b")[0]
    conn = sqlite3.connect(str(indexed.db_path))
    try:
        rows = conn.execute("SELECT callee_sym_id FROM calls WHERE caller_sym_id = ?", (a.sym_id,)).fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == {b.sym_id}


def test_self_method_edge_resolves(indexed: StructuralIndex) -> None:
    import sqlite3

    greet = _find(indexed, "Greeter.greet")[0]
    fmt = _find(indexed, "Greeter._format")[0]
    conn = sqlite3.connect(str(indexed.db_path))
    try:
        rows = conn.execute("SELECT callee_sym_id FROM calls WHERE caller_sym_id = ?", (greet.sym_id,)).fetchall()
    finally:
        conn.close()
    assert {row[0] for row in rows} == {fmt.sym_id}


def test_module_attribute_and_unknown_stay_unresolved(indexed: StructuralIndex) -> None:
    import sqlite3

    fn = _find(indexed, "uses_unresolved")[0]
    conn = sqlite3.connect(str(indexed.db_path))
    try:
        rows = conn.execute("SELECT callee_sym_id FROM calls WHERE caller_sym_id = ?", (fn.sym_id,)).fetchall()
    finally:
        conn.close()
    callees = {row[0] for row in rows}
    assert callees == {"<unresolved:os.path.join>"}
    # the unresolved value inserts without error (no FK) AND is NOT a symbols row:
    conn2 = sqlite3.connect(str(indexed.db_path))
    try:
        n = conn2.execute("SELECT COUNT(*) FROM symbols WHERE sym_id = '<unresolved:os.path.join>'").fetchone()[0]
    finally:
        conn2.close()
    assert n == 0


# ── incremental + ghost sweep ───────────────────────────────────────────────


def test_incremental_reindex_zero_changes(tmp_path: Path) -> None:
    _write(tmp_path / "mod.py", "def x():\n    return 1\n")
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    first = index.ensure_indexed(tmp_path)
    second = index.ensure_indexed(tmp_path, force=True)
    assert first.files_indexed == 1
    assert second.files_indexed == 0  # fresh hashes → skipped
    assert second.files_skipped == 1
    assert second.symbols == 0
    assert second.edges == 0


def test_modify_one_file_reindexes_only_that_path(tmp_path: Path) -> None:
    _write(tmp_path / "a.py", "def a():\n    return 1\n")
    _write(tmp_path / "b.py", "def b():\n    return 2\n")
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    index.ensure_indexed(tmp_path)
    # change a.py only
    _write(tmp_path / "a.py", "def a():\n    return 11\n")
    stats = index.ensure_indexed(tmp_path, force=True)
    assert stats.files_indexed == 1
    assert stats.files_skipped == 1
    assert _find(index, "b")  # b untouched and still present


def test_syntax_error_skips_file_only(tmp_path: Path) -> None:
    _write(tmp_path / "broken.py", "def broken(:\n    return\n")
    _write(tmp_path / "ok.py", "def ok():\n    return 1\n")
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    stats = index.ensure_indexed(tmp_path)
    assert stats.available is True
    assert _find(index, "ok")
    assert _find(index, "broken") == []
    assert any("syntax error" in err for _, err in stats.errors)


def test_ghost_sweep_removes_deleted_file_symbols(tmp_path: Path) -> None:
    # Same-file edge (cross-file calls are unresolved by design in v1, so a
    # cross-file fixture could not produce a symbol-linked edge to sweep).
    _write(tmp_path / "gone.py", "def gone():\n    return 1\n\n\ndef caller():\n    return gone()\n")
    _write(tmp_path / "stay.py", "def stay():\n    return 1\n")
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    index.ensure_indexed(tmp_path)
    gone = _find(index, "gone")[0]
    caller = _find(index, "caller")[0]
    assert gone and caller
    (tmp_path / "gone.py").unlink()
    index.ensure_indexed(tmp_path, force=True)
    assert _find(index, "gone") == []
    assert _find(index, "caller") == []
    assert _find(index, "stay")
    # no calls rows may reference the ghost symbol ids
    import sqlite3

    conn = sqlite3.connect(str(index.db_path))
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM calls WHERE caller_sym_id IN (?, ?) OR callee_sym_id IN (?, ?)",
            (gone.sym_id, caller.sym_id, gone.sym_id, caller.sym_id),
        ).fetchone()[0]
    finally:
        conn.close()
    assert n == 0


# ── anchors ─────────────────────────────────────────────────────────────────


def test_anchor_extracted_as_doc_anchor(tmp_path: Path) -> None:
    _write(tmp_path / "mod.py", "# §I-FOO: does the thing\ndef f():\n    return 1\n")
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    index.ensure_indexed(tmp_path)
    rows = _find(index, "§I-FOO")
    assert len(rows) == 1
    assert rows[0].kind == "doc_anchor"
    assert rows[0].docstring == "does the thing"
    assert rows[0].start_line == 1
    assert rows[0].end_line == 1


# ── find_symbols semantics ──────────────────────────────────────────────────


def test_find_symbols_exact_suffix_literals(tmp_path: Path) -> None:
    # A function name containing % and _ must match literally, not as LIKE.
    _write(tmp_path / "mod.py", "def pct_100():\n    return 1\n")
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    index.ensure_indexed(tmp_path)
    assert _find(index, "pct_100")
    assert _find(index, "pct_1%") == []  # % is a literal, not a wildcard
    assert _find(index, "pct_1__") == []  # _ is literal too


# ── reachable BFS ───────────────────────────────────────────────────────────


def test_reachable_down_depth_and_limit(indexed: StructuralIndex) -> None:
    a = _find(indexed, "a")[0]
    rows, truncated, _unresolved = indexed.reachable(a.sym_id, "down", depth=2, limit=20)
    qualnames = [r.qualname for r, _d in rows]
    assert qualnames == ["b", "c"]  # distance 1 then 2; d is distance 3
    assert [d for _r, d in rows] == [1, 2]  # true BFS distances, not positions
    assert truncated is False
    rows_limited, truncated_limited, _ = indexed.reachable(a.sym_id, "down", depth=5, limit=2)
    assert [r.qualname for r, _d in rows_limited] == ["b", "c"]
    assert truncated_limited is True


def test_reachable_up(indexed: StructuralIndex) -> None:
    c = _find(indexed, "c")[0]
    rows, truncated, _ = indexed.reachable(c.sym_id, "up", depth=3, limit=20)
    assert [r.qualname for r, _d in rows] == ["b", "a"]
    assert [d for _r, d in rows] == [1, 2]
    assert truncated is False


def test_reachable_unresolved_count(indexed: StructuralIndex) -> None:
    fn = _find(indexed, "uses_unresolved")[0]
    _rows, _trunc, unresolved = indexed.reachable(fn.sym_id, "down", depth=2, limit=20)
    assert unresolved == 1  # os.path.join


def test_reachable_include_tests_query_filter(tmp_path: Path) -> None:
    # Real in-file edges inside a test-path file (v1 resolution is in-file only,
    # so the filter is exercised on same-file callers of a test-path callee).
    _write(
        tmp_path / "tests" / "test_m.py",
        "def callee():\n    return 1\n\n\ndef caller():\n    return callee()\n",
    )
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    index.ensure_indexed(tmp_path)
    callee = _find(index, "callee")[0]
    rows_default, _, _ = index.reachable(callee.sym_id, "up", depth=2, limit=20)
    rows_with_tests, _, _ = index.reachable(callee.sym_id, "up", depth=2, limit=20, include_tests=True)
    assert rows_default == []  # test-path caller filtered by default
    assert [r.qualname for r, _d in rows_with_tests] == ["caller"]
    assert [d for _r, d in rows_with_tests] == [1]


def test_is_test_path_helper() -> None:
    assert _is_test_path("tests/test_x.py")
    assert _is_test_path("src/pkg/tests/test_x.py")
    assert _is_test_path("pkg/test_helper.py")
    assert _is_test_path("pkg/helper_test.py")
    assert not _is_test_path("src/pkg/mod.py")
    assert not _is_test_path("contest.py")


# ── thread safety ───────────────────────────────────────────────────────────


def test_concurrent_build_runs_once(tmp_path: Path) -> None:
    _write(tmp_path / "mod.py", FIXTURE_MODULE)
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    results: list[StructIndexStats] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(index.ensure_indexed(tmp_path))
        except BaseException as exc:  # noqa: BLE001 - collect any thread failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors
    assert len(results) == 4
    # One build; concurrent callers share the SAME cached stats object.
    assert all(r is results[0] for r in results)
    assert results[0].files_indexed == 1
    assert all(r.available for r in results)


# ── language probe ──────────────────────────────────────────────────────────


def test_non_python_repo_unavailable(tmp_path: Path) -> None:
    _write(tmp_path / "app.js", "console.log(1)\n")
    _write(tmp_path / "README.md", "# hi\n")
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    stats = index.ensure_indexed(tmp_path)
    assert stats.available is False
    assert stats.files_indexed == 0
    assert set(stats.detected_languages) == {".js", ".md"}


def test_reachable_distances_are_true_on_fanout(tmp_path: Path) -> None:
    """Kill-test for the post-ship distance fix: one level with THREE callees
    must report distance 1 for all three (enumerate-fabricated labeling gave
    1,2,3 — chain-only fixtures masked it because every level had one node)."""
    _write(
        tmp_path / "fan.py",
        "def h1():\n    return 1\n\n\ndef h2():\n    return 2\n\n\ndef h3():\n    return 3\n\n"
        "\ndef root():\n    return h1() + h2() + h3()\n",
    )
    index = StructuralIndex(tmp_path / ".fa" / "structural.db")
    index.ensure_indexed(tmp_path)
    root = _find(index, "root")[0]
    rows, truncated, _ = index.reachable(root.sym_id, "down", depth=1, limit=20)
    by_name = {r.qualname: d for r, d in rows}
    assert set(by_name) == {"h1", "h2", "h3"}
    assert all(d == 1 for d in by_name.values()), by_name
    assert truncated is False
