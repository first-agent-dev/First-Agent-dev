"""S16 (CT-5): structural call-graph index — lazy, thread-safe, Python-only.

Indexes ``symbols`` (functions/methods/doc_anchors), ``calls`` (direct call
edges with best-effort in-file resolution), and ``struct_meta`` (per-file
hash for incremental rebuilds) into ``<workspace>/.fa/structural.db``.

Design decisions (plan v5, `S16-PLAN-REVIEW-2026-08-17.md`):

- **Thread-safe lazy build (D-S16-5).** A module-level lock serializes
  ``ensure_indexed`` — two parallel ``fs_reach`` calls in one batch must not
  race the first build. Every DB operation opens a SHORT-LIVED sqlite3
  connection (WAL, ``synchronous=NORMAL``, ``timeout=10.0`` — mirrors
  ``search_index.py:213-215``); there is NO shared connection object, so
  ``check_same_thread`` stays at its default and cross-thread use is safe.
- **In-file-only edge resolution (D-S16-2).** ``Name(id=foo)`` resolves
  against in-file symbols whose qualname's last component is ``foo``;
  ``self.foo`` resolves against the enclosing class's methods; everything
  else (module attributes, imports, chains) is recorded honestly as
  ``<unresolved>:...``. No cross-file edges in v1 — no hallucinated calls.
- **No FK on ``callee_sym_id`` (D-S16-3).** Unresolved callees are values,
  not symbol rows; a foreign key would be theater on default SQLite
  connections and a raise on FK-enabled ones.
- **Ghost sweep (D-S16-7).** After a build, symbols/calls of files that
  disappeared from the workspace are deleted (the same ghost-hit class the
  S14b.1 hardening fixed for SearchIndex).
- **Index-time ``include_tests`` removed (D-S16-6).** All ``.py`` files are
  indexed; ``fs_reach`` filters test paths at QUERY time via ``reachable``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fa.memory._safe_walk import RootedFileReader, iter_searchable_files

logger = logging.getLogger(__name__)

# §I-S16-1: thread-safe lazy build — module lock serializes ensure_indexed across parallel calls.
_BUILD_LOCK = threading.Lock()
_ANCHOR_RE = re.compile(r"^\s*#\s*§([A-Za-z0-9_.-]+):\s*(.+)$")
_UNRESOLVED_PREFIX = "<unresolved:"
KIND_DOC_ANCHOR = "doc_anchor"  # storage kind for §-anchors (NOT a LogKind — S4 contract)
_DOCSTRING_CAP = 400
_SYMBOL_HASH_LEN = 16
_FILE_HASH_LEN = 24
_LANGUAGE_PROBE_LIMIT = 200
_MAX_SOURCE_FILE_BYTES = 200_000  # Must match the structural walk's existing candidate cap.
MAX_MANAGED_AST_NODES = 2_000_000
MAX_MANAGED_FILE_AST_NODES = 256_000
MAX_MANAGED_SYMBOLS = 100_000
MAX_MANAGED_EDGES = 250_000
MAX_MANAGED_FILE_EDGES = 25_000
MAX_MANAGED_SQLITE_PAGE_SIZE = 4_096
MAX_MANAGED_SQLITE_PAGES = 32_768
MAX_MANAGED_SQLITE_CACHE_KIB = 16 * 1024


def _hash16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_SYMBOL_HASH_LEN]


def _is_test_path(rel: str) -> bool:
    """Query-time test filter (same convention as the safe walker).

    A path is a test path when any component is ``tests`` or the basename
    matches ``test_*.py`` / ``*_test.py``.
    """
    parts = tuple(rel.replace("\\", "/").split("/"))
    if "tests" in parts:
        return True
    basename = parts[-1] if parts else ""
    return (basename.startswith("test_") and basename.endswith(".py")) or basename.endswith("_test.py")


@dataclass(frozen=True)
class StructIndexStats:
    """Result of one build attempt (CT-5 failure surface)."""

    files_indexed: int = 0
    files_skipped: int = 0
    symbols: int = 0
    edges: int = 0
    available: bool = True
    detected_languages: tuple[str, ...] = ()
    errors: tuple[tuple[str, str], ...] = ()  # (relpath, message)


@dataclass(slots=True)
class _ManagedReachBudget:
    """Mutable per-call counters retained only while one managed index is built."""

    nodes: int = 0
    symbols: int = 0
    edges: int = 0


@dataclass(frozen=True)
class SymbolRow:
    """One symbol row, as returned by lookup/query APIs."""

    sym_id: str
    path: str
    qualname: str
    kind: str
    start_line: int
    end_line: int
    docstring: str | None


@dataclass(frozen=True)
class _FileSymbol:
    """Working representation during indexing (qualname-keyed)."""

    qualname: str
    sym_id: str
    rel: str
    kind: str
    start_line: int
    end_line: int
    docstring: str | None


def _docstring_first_line(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Module,
) -> str | None:
    raw = ast.get_docstring(node, clean=False)
    if not raw:
        return None
    first = raw.splitlines()[0].strip()
    return first[:_DOCSTRING_CAP] or None


def _iter_body_calls(node: ast.AST) -> Iterator[ast.Call]:
    """Yield ast.Call nodes under ``node``, skipping nested def/class bodies.

    A call inside a nested function/class belongs to THAT scope, not to the
    enclosing function — attributing it upward would create wrong edges.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(child, ast.Call):
            yield child
        yield from _iter_body_calls(child)


def _base_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        inner = _base_name(node.value)
        return f"{inner}.{node.attr}" if inner else node.attr
    return ""


class StructuralIndex:
    """Lazy, thread-safe structural call-graph index (CT-5)."""

    def __init__(
        self,
        db_path: Path,
        *,
        in_memory: bool = False,
        strict_rooted_reads: bool = False,
        managed_bounded: bool = False,
    ) -> None:
        if type(strict_rooted_reads) is not bool or type(managed_bounded) is not bool:
            raise ValueError("strict_rooted_reads and managed_bounded must be bool")
        if managed_bounded and (not in_memory or not strict_rooted_reads):
            raise ValueError("managed bounded reach requires an in-memory rooted index")
        self.db_path = Path(db_path)
        self._strict_rooted_reads = strict_rooted_reads
        self._managed_bounded = managed_bounded
        self._managed_deadline: float | None = None
        self._memory_uri = f"file:fa-struct-{uuid4().hex}?mode=memory&cache=shared" if in_memory else None
        self._anchor = (
            sqlite3.connect(self._memory_uri, uri=True, check_same_thread=False)
            if self._memory_uri is not None
            else None
        )
        self._stats: StructIndexStats | None = None

    # -- connection / schema -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        if self._memory_uri is None:
            # Ensure the parent directory exists for direct and tool callers.
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        else:
            conn = sqlite3.connect(self._memory_uri, timeout=10.0, uri=True)
            conn.execute("PRAGMA temp_store=MEMORY")
        if self._managed_bounded:
            conn.execute(f"PRAGMA page_size={MAX_MANAGED_SQLITE_PAGE_SIZE}")
            conn.execute(f"PRAGMA max_page_count={MAX_MANAGED_SQLITE_PAGES}")
            conn.execute(f"PRAGMA cache_size=-{MAX_MANAGED_SQLITE_CACHE_KIB}")
            if (
                conn.execute("PRAGMA page_size").fetchone()[0] != MAX_MANAGED_SQLITE_PAGE_SIZE
                or conn.execute("PRAGMA max_page_count").fetchone()[0] > MAX_MANAGED_SQLITE_PAGES
                or conn.execute("PRAGMA cache_size").fetchone()[0] != -MAX_MANAGED_SQLITE_CACHE_KIB
            ):
                conn.close()
                raise sqlite3.OperationalError("managed SQLite limits unavailable")
            if self._managed_deadline is not None:
                deadline = self._managed_deadline
                conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS symbols (
                sym_id     TEXT PRIMARY KEY,
                path       TEXT NOT NULL,
                qualname   TEXT NOT NULL,
                kind       TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line   INTEGER NOT NULL,
                docstring  TEXT,
                file_hash  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_symbols_qualname ON symbols(qualname);
            CREATE INDEX IF NOT EXISTS idx_symbols_path ON symbols(path);
            CREATE TABLE IF NOT EXISTS calls (
                caller_sym_id TEXT NOT NULL,
                callee_sym_id TEXT NOT NULL,
                call_line     INTEGER NOT NULL,
                PRIMARY KEY (caller_sym_id, callee_sym_id, call_line)
            );
            CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_sym_id);
            CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_sym_id);
            CREATE TABLE IF NOT EXISTS struct_meta (
                path TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                indexed_at REAL NOT NULL
            );
            """
        )
        conn.commit()

    # -- public API -----------------------------------------------------------

    @property
    def available(self) -> bool:
        """True when the last build succeeded on a Python repo (or not yet built)."""
        return self._stats.available if self._stats is not None else True

    def ensure_indexed(self, root: Path, *, force: bool = False) -> StructIndexStats:
        """Build (or return the cached build of) the index for ``root``.

        Thread-safe: the module lock serializes builds; concurrent callers
        get the cached stats with zero re-build cost (D-S16-5).
        """
        with _BUILD_LOCK:
            if not force and self._stats is not None:
                return self._stats
            self._stats = self._build(root)
            return self._stats

    def ensure_managed_indexed(
        self,
        root: Path,
        inventory: Any,
        *,
        rooted_reader: RootedFileReader | None,
        deadline: float,
    ) -> StructIndexStats:
        """Build a one-shot managed index, rolling back every aggregate refusal."""
        from fa.memory.managed_discovery import ManagedDiscoveryError

        if not self._managed_bounded or rooted_reader is None:
            raise ManagedDiscoveryError("unsafe_path")
        if type(deadline) not in {int, float} or deadline <= 0:
            raise ManagedDiscoveryError("deadline")
        with _BUILD_LOCK:
            if self._stats is not None:
                return self._stats
            self._managed_deadline = float(deadline)
            self._stats = self._build_managed(root, inventory, rooted_reader, deadline=float(deadline))
            return self._stats

    def find_symbols(self, name: str, *, kind: str | None = None) -> list[SymbolRow]:
        """Exact-suffix lookup: ``name`` matches qualnames ending in ``name``.

        Suffix semantics are EXACT (``WHERE qualname = substr(qualname, -len(name))``),
        so ``%``/``_`` in the input are literals, not LIKE wildcards (D-S16-12).
        Deterministic total order: (len(qualname), path, start_line).
        """
        conn = self._connect()
        try:
            sql = (
                "SELECT sym_id, path, qualname, kind, start_line, end_line, docstring "
                "FROM symbols WHERE substr(qualname, -?) = ?"
            )
            params: tuple[object, ...] = (len(name), name)
            if kind is not None:
                sql += " AND kind = ?"
                params = (len(name), name, kind)
            sql += " ORDER BY length(qualname), path, start_line LIMIT 50"
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [SymbolRow(*row) for row in rows]

    def reachable(
        self,
        sym_id: str,
        direction: str,
        depth: int,
        limit: int,
        *,
        include_tests: bool = False,
    ) -> tuple[list[tuple[SymbolRow, int]], bool, int]:
        """BFS over ``calls`` from ``sym_id``.

        Returns ``(rows, truncated, unresolved)``:
        - ``rows`` = ``(SymbolRow, distance)`` pairs, ordered by
          (distance, path, start_line), EXCLUDING the root. The distance is
          the TRUE BFS level — NOT a list-position fabrication (S16 post-ship
          fix: enumerate-based labeling misreported fan-out levels; the
          chain-only fixtures masked it because every level had one node).
        - ``truncated`` True when the ``limit`` cut more results;
        - ``unresolved`` = distinct ``<unresolved>`` callee identifiers
          encountered during the traversal (down/both directions).
        """
        conn = self._connect()
        try:
            visited: set[str] = {sym_id}
            frontier = {sym_id}
            result_rows: list[tuple[SymbolRow, int]] = []
            truncated = False
            unresolved: set[str] = set()
            for dist in range(1, depth + 1):
                if not frontier:
                    break
                next_frontier, unresolved_level = self._next_frontier(conn, frontier, direction, visited)
                unresolved |= unresolved_level  # merge BEFORE the empty check —
                # a terminal unresolved edge must still be counted (dist-level
                # callees that never become frontier members).
                if not next_frontier:
                    break
                rows = self._rows_for_ids(conn, next_frontier, include_tests)
                rows_sorted = sorted(rows, key=lambda r: (dist, r.path, r.start_line))
                added: set[str] = set()
                for row in rows_sorted:
                    if len(result_rows) >= limit:
                        truncated = True
                        break
                    result_rows.append((row, dist))
                    visited.add(row.sym_id)
                    added.add(row.sym_id)
                frontier = added
                if truncated:
                    break
            return result_rows, truncated, len(unresolved)
        finally:
            conn.close()

    @staticmethod
    def _next_frontier(
        conn: sqlite3.Connection,
        frontier: set[str],
        direction: str,
        visited: set[str],
    ) -> tuple[set[str], set[str]]:
        """One BFS hop: return (next ids, unresolved callee ids seen)."""
        next_frontier: set[str] = set()
        unresolved_level: set[str] = set()
        for current in frontier:
            if direction in ("down", "both"):
                for (callee_id,) in conn.execute(
                    "SELECT callee_sym_id FROM calls WHERE caller_sym_id = ?", (current,)
                ).fetchall():
                    if callee_id.startswith(_UNRESOLVED_PREFIX):
                        unresolved_level.add(callee_id)
                        continue
                    if callee_id not in visited:
                        next_frontier.add(callee_id)
            if direction in ("up", "both"):
                for (caller_id,) in conn.execute(
                    "SELECT caller_sym_id FROM calls WHERE callee_sym_id = ?", (current,)
                ).fetchall():
                    if caller_id.startswith(_UNRESOLVED_PREFIX):
                        continue  # callers are real symbol rows by construction
                    if caller_id not in visited:
                        next_frontier.add(caller_id)
        return next_frontier, unresolved_level

    def close(self) -> None:
        """Close the in-memory anchor; disk connections remain short-lived."""
        if self._anchor is not None:
            self._anchor.close()
            self._anchor = None

    # -- internals -------------------------------------------------------------

    def _rows_for_ids(self, conn: sqlite3.Connection, sym_ids: set[str], include_tests: bool) -> list[SymbolRow]:
        if not sym_ids:
            return []
        # json_each keeps the IN-list fully parametrized (no dynamic SQL).
        rows = conn.execute(
            "SELECT sym_id, path, qualname, kind, start_line, end_line, docstring "
            "FROM symbols WHERE sym_id IN (SELECT value FROM json_each(?))",
            (json.dumps(sorted(sym_ids)),),
        ).fetchall()
        out: list[SymbolRow] = []
        for row in rows:
            symbol = SymbolRow(*row)
            if not include_tests and _is_test_path(symbol.path):
                continue
            out.append(symbol)
        return out

    @staticmethod
    def _read_rooted_candidate(reader: RootedFileReader, rel: str) -> tuple[str, bytes] | None:
        try:
            return reader.read_bytes_with_path(rel, max_bytes=_MAX_SOURCE_FILE_BYTES)
        except OSError:
            return None

    def _index_candidate(
        self,
        conn: sqlite3.Connection,
        fp: Path,
        rel: str,
        reader: RootedFileReader | None,
        seen_rooted_paths: set[str],
    ) -> tuple[str, tuple[int, int, int, int, str | None]] | None:
        if reader is None:
            return rel, self._index_one_file(conn, fp, rel)
        rooted_source = self._read_rooted_candidate(reader, rel)
        if rooted_source is None:
            return None
        indexed_rel, source_bytes = rooted_source
        if indexed_rel in seen_rooted_paths:
            return indexed_rel, (0, 1, 0, 0, None)
        seen_rooted_paths.add(indexed_rel)
        result = self._index_one_file(conn, fp, indexed_rel, source_bytes=source_bytes)
        return indexed_rel, result

    def _build(self, root: Path) -> StructIndexStats:
        root_resolved = root.resolve()
        conn = self._connect()
        rooted_reader: RootedFileReader | None = None
        try:
            self._init_schema(conn)
            if self._strict_rooted_reads:
                rooted_reader = RootedFileReader(root_resolved)
            walked: list[tuple[Path, str]] = []
            extensions: set[str] = set()
            try:
                for fp, rel, _mtime, _size in iter_searchable_files(
                    root_resolved,
                    patterns=("*.py",),
                    include_tests=True,
                    max_file_size=_MAX_SOURCE_FILE_BYTES,
                    strict_paths=self._strict_rooted_reads,
                ):
                    walked.append((fp, rel))
                    if len(extensions) < _LANGUAGE_PROBE_LIMIT:
                        extensions.add(Path(rel).suffix.lower())
            except Exception as exc:  # noqa: BLE001 - walk failure = unavailable, never crash
                logger.warning("structural index walk failed: %s", exc)
                return StructIndexStats(available=False, errors=((str(root_resolved), str(exc)),))

            if not walked:
                # Language probe (D-S16-14): the .py-patterned walk saw nothing;
                # walk once more with a catch-all pattern (bounded) to report
                # WHAT is actually in the workspace.
                probe_exts: set[str] = set()
                try:
                    for fp, _rel, _m, _s in iter_searchable_files(
                        root_resolved,
                        patterns=("*",),
                        include_tests=True,
                        strict_paths=self._strict_rooted_reads,
                    ):
                        if len(probe_exts) >= _LANGUAGE_PROBE_LIMIT:
                            break
                        probe_exts.add(fp.suffix.lower())
                except Exception as exc:  # noqa: BLE001 - probe is best-effort
                    logger.debug("structural language probe failed: %s", exc)
                return StructIndexStats(
                    available=False,
                    detected_languages=tuple(sorted(probe_exts)),
                )

            files_indexed = 0
            files_skipped = 0
            total_symbols = 0
            total_edges = 0
            indexed_files: set[str] = set()
            errors: list[tuple[str, str]] = []
            seen_rooted_paths: set[str] = set()

            for fp, rel in walked:
                candidate = self._index_candidate(conn, fp, rel, rooted_reader, seen_rooted_paths)
                if candidate is None:
                    return StructIndexStats(available=False, errors=((rel, "rooted source read refused"),))
                indexed_rel, result = candidate
                files_indexed += result[0]
                files_skipped += result[1]
                total_symbols += result[2]
                total_edges += result[3]
                indexed_files.add(indexed_rel)
                if result[4] is not None:
                    errors.append((indexed_rel, result[4]))

            self._sweep_ghosts(conn, indexed_files)

            return StructIndexStats(
                files_indexed=files_indexed,
                files_skipped=files_skipped,
                symbols=total_symbols,
                edges=total_edges,
                available=True,
                detected_languages=tuple(sorted(extensions)),
                errors=tuple(errors),
            )
        except Exception as exc:  # noqa: BLE001 - DB failure → unavailable, structured
            logger.warning("structural index build failed: %s", exc)
            return StructIndexStats(available=False, errors=((str(self.db_path), str(exc)),))
        finally:
            conn.close()
            if rooted_reader is not None:
                rooted_reader.close()

    def _build_managed(
        self,
        root: Path,
        inventory: Any,
        rooted_reader: RootedFileReader,
        *,
        deadline: float,
    ) -> StructIndexStats:
        from fa.memory.managed_discovery import (
            MAX_MANAGED_CANDIDATES,
            MAX_MANAGED_SOURCE_BYTES,
            ManagedDiscoveryError,
            _read_managed_candidate,
        )

        if len(inventory.candidates) > MAX_MANAGED_CANDIDATES:
            raise ManagedDiscoveryError("candidate_budget")
        if inventory.eligible_source_bytes > MAX_MANAGED_SOURCE_BYTES:
            raise ManagedDiscoveryError("source_budget")
        if time.monotonic() >= deadline:
            raise ManagedDiscoveryError("deadline")
        if not inventory.candidates or all(candidate.oversized for candidate in inventory.candidates):
            return StructIndexStats(
                files_skipped=inventory.oversized_files,
                available=False,
                detected_languages=inventory.detected_languages,
            )

        conn = self._connect()
        stats = _ManagedReachBudget()
        files_indexed = 0
        files_skipped = inventory.oversized_files
        actual_source_bytes = 0
        errors: list[tuple[str, str]] = []
        try:
            self._init_schema(conn)
            conn.execute("BEGIN")
            self._check_managed_deadline(deadline)
            self._check_managed_page_budget(conn)
            for candidate in inventory.candidates:
                self._check_managed_deadline(deadline)
                if candidate.oversized:
                    continue
                if candidate.size_bytes > _MAX_SOURCE_FILE_BYTES:
                    raise ManagedDiscoveryError("unsafe_path")
                canonical_rel, raw = _read_managed_candidate(rooted_reader, candidate)
                if actual_source_bytes + len(raw) > MAX_MANAGED_SOURCE_BYTES:
                    raise ManagedDiscoveryError("source_budget")
                actual_source_bytes += len(raw)
                result = self._index_one_file(
                    conn,
                    root / canonical_rel,
                    canonical_rel,
                    source_bytes=raw,
                    managed_budget=stats,
                    commit=False,
                )
                files_indexed += result[0]
                files_skipped += result[1]
                if result[4] is not None:
                    errors.append((canonical_rel, result[4]))
                self._check_managed_deadline(deadline)
                self._check_managed_page_budget(conn)
            self._check_managed_deadline(deadline)
            conn.commit()
            return StructIndexStats(
                files_indexed=files_indexed,
                files_skipped=files_skipped,
                symbols=stats.symbols,
                edges=stats.edges,
                available=True,
                detected_languages=inventory.detected_languages,
                errors=tuple(errors),
            )
        except ManagedDiscoveryError:
            conn.rollback()
            raise
        except sqlite3.Error:
            conn.rollback()
            if time.monotonic() >= deadline:
                raise ManagedDiscoveryError("deadline") from None
            raise ManagedDiscoveryError("index_budget") from None
        finally:
            conn.close()

    @staticmethod
    def _check_managed_deadline(deadline: float) -> None:
        from fa.memory.managed_discovery import ManagedDiscoveryError

        if time.monotonic() >= deadline:
            raise ManagedDiscoveryError("deadline")

    @staticmethod
    def _check_managed_page_budget(conn: sqlite3.Connection) -> None:
        from fa.memory.managed_discovery import ManagedDiscoveryError

        page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
        max_pages = int(conn.execute("PRAGMA max_page_count").fetchone()[0])
        if (
            page_size != MAX_MANAGED_SQLITE_PAGE_SIZE
            or page_count > MAX_MANAGED_SQLITE_PAGES
            or max_pages > MAX_MANAGED_SQLITE_PAGES
        ):
            raise ManagedDiscoveryError("index_budget")

    def _count_managed_ast_nodes(self, tree: ast.AST, limit: int) -> int:
        from fa.memory.managed_discovery import ManagedDiscoveryError

        if limit <= 0:
            raise ManagedDiscoveryError("ast_budget")
        pending = [tree]
        count = 0
        while pending:
            if count % 512 == 0:
                self._check_managed_deadline(self._active_deadline())
            node = pending.pop()
            count += 1
            if count > limit:
                raise ManagedDiscoveryError("ast_budget")
            pending.extend(ast.iter_child_nodes(node))
        return count

    def _active_deadline(self) -> float:
        from fa.memory.managed_discovery import ManagedDiscoveryError

        if self._managed_deadline is None:
            raise ManagedDiscoveryError("deadline")
        return self._managed_deadline

    def _index_one_file(
        self,
        conn: sqlite3.Connection,
        fp: Path,
        rel: str,
        *,
        source_bytes: bytes | None = None,
        managed_budget: _ManagedReachBudget | None = None,
        commit: bool = True,
    ) -> tuple[int, int, int, int, str | None]:
        """Index one file. Returns (indexed, skipped, symbols, edges, error).

        ``skipped`` counts fresh-hash and syntax-error skips alike; ``error``
        carries a human message for the stats ledger when non-None.
        """
        try:
            data = source_bytes if source_bytes is not None else fp.read_bytes()
        except OSError as exc:
            return (0, 0, 0, 0, f"read failed: {exc}")
        file_hash = hashlib.sha256(data).hexdigest()[:_FILE_HASH_LEN]

        fresh = conn.execute("SELECT file_hash FROM struct_meta WHERE path = ?", (rel,)).fetchone()
        if fresh is not None and fresh[0] == file_hash:
            return (0, 1, 0, 0, None)

        try:
            source = data.decode("utf-8", errors="replace")
            tree = ast.parse(source)
        except SyntaxError as exc:
            return (0, 1, 0, 0, f"syntax error: {exc}")
        except Exception as exc:  # noqa: BLE001 - decode is replace-mode; defensive only
            return (0, 1, 0, 0, f"parse failed: {exc}")

        if managed_budget is not None:
            allowed_nodes = min(MAX_MANAGED_FILE_AST_NODES, MAX_MANAGED_AST_NODES - managed_budget.nodes)
            managed_budget.nodes += self._count_managed_ast_nodes(tree, allowed_nodes)

        file_symbols: dict[str, _FileSymbol] = {}
        edges: set[tuple[str, str, int]] = set()
        for anchor in self._extract_anchors(rel, source):
            file_symbols[anchor.qualname] = anchor
        edge_limit = None
        if managed_budget is not None:
            edge_limit = min(MAX_MANAGED_FILE_EDGES, MAX_MANAGED_EDGES - managed_budget.edges)
        self._walk_tree(tree, rel, file_symbols, edges, edge_limit=edge_limit)
        if managed_budget is not None:
            if managed_budget.symbols + len(file_symbols) > MAX_MANAGED_SYMBOLS:
                from fa.memory.managed_discovery import ManagedDiscoveryError

                raise ManagedDiscoveryError("symbol_budget")
            managed_budget.symbols += len(file_symbols)
            managed_budget.edges += len(edges)

        # per-file replace: DELETE then INSERT (incremental update)
        conn.execute("DELETE FROM symbols WHERE path = ?", (rel,))
        conn.execute(
            "DELETE FROM calls WHERE caller_sym_id IN (SELECT sym_id FROM symbols WHERE path = ?)",
            (rel,),
        )
        for sym in file_symbols.values():
            conn.execute(
                "INSERT OR REPLACE INTO symbols "
                "(sym_id, path, qualname, kind, start_line, end_line, docstring, file_hash) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    sym.sym_id,
                    sym.rel,
                    sym.qualname,
                    sym.kind,
                    sym.start_line,
                    sym.end_line,
                    sym.docstring,
                    file_hash,
                ),
            )
        for caller_id, callee_id, call_line in sorted(edges):
            conn.execute(
                "INSERT OR IGNORE INTO calls (caller_sym_id, callee_sym_id, call_line) VALUES (?,?,?)",
                (caller_id, callee_id, call_line),
            )
        conn.execute(
            "INSERT OR REPLACE INTO struct_meta (path, file_hash, indexed_at) VALUES (?,?,?)",
            (rel, file_hash, time.time()),
        )
        if commit:
            conn.commit()
        return (1, 0, len(file_symbols), len(edges), None)

    def _sweep_ghosts(self, conn: sqlite3.Connection, indexed_files: set[str]) -> None:
        """Delete rows for files that vanished from the walk (D-S16-7).

        Fully parametrized via ``json_each`` — no dynamic SQL (S608-clean).
        """
        meta_paths = [row[0] for row in conn.execute("SELECT path FROM struct_meta").fetchall()]
        ghosts = [p for p in meta_paths if p not in indexed_files]
        if not ghosts:
            return
        ghost_ids = [
            row[0]
            for row in conn.execute(
                "SELECT sym_id FROM symbols WHERE path IN (SELECT value FROM json_each(?))",
                (json.dumps(ghosts),),
            ).fetchall()
        ]
        if ghost_ids:
            conn.execute(
                "DELETE FROM calls WHERE caller_sym_id IN (SELECT value FROM json_each(?))",
                (json.dumps(ghost_ids),),
            )
            conn.execute(
                "DELETE FROM calls WHERE callee_sym_id IN (SELECT value FROM json_each(?))",
                (json.dumps(ghost_ids),),
            )
        conn.execute(
            "DELETE FROM symbols WHERE path IN (SELECT value FROM json_each(?))",
            (json.dumps(ghosts),),
        )
        conn.execute(
            "DELETE FROM struct_meta WHERE path IN (SELECT value FROM json_each(?))",
            (json.dumps(ghosts),),
        )
        conn.commit()

    def _extract_anchors(self, rel: str, source: str) -> list[_FileSymbol]:
        anchors: list[_FileSymbol] = []
        for line_no, line in enumerate(source.splitlines(), start=1):
            match = _ANCHOR_RE.match(line)
            if not match:
                continue
            anchor_id, description = match.group(1), match.group(2).strip()
            qualname = f"§{anchor_id}"
            anchors.append(
                _FileSymbol(
                    qualname=qualname,
                    sym_id=_hash16(f"{rel}:{qualname}"),
                    rel=rel,
                    kind=KIND_DOC_ANCHOR,
                    start_line=line_no,
                    end_line=line_no,
                    docstring=description[:_DOCSTRING_CAP],
                )
            )
        return anchors

    def _walk_tree(
        self,
        tree: ast.AST,
        rel: str,
        file_symbols: dict[str, _FileSymbol],
        edges: set[tuple[str, str, int]],
        *,
        edge_limit: int | None = None,
    ) -> None:
        """Two passes: symbols first (order-independent resolution), then edges.

        Scope stacks carry (name, is_class) pairs so "method vs function" is
        decided from structure, never reconstructed from name strings.
        """
        for item in ast.iter_child_nodes(tree):
            _collect_symbols_pass(item, [], rel, file_symbols)
        for item in ast.iter_child_nodes(tree):
            _collect_edges_pass(item, [], rel, file_symbols, edges, edge_limit=edge_limit)

    @staticmethod
    def _resolve_callee(
        call: ast.Call,
        file_symbols: dict[str, _FileSymbol],
        class_qualname: str | None,
    ) -> str:
        """Best-effort in-file callee resolution (CT-5 v5; D-S16-2).

        Unresolved values follow one canonical spelling — ``<unresolved:NAME>``
        (angle brackets delimit the whole value, so the ``startswith``
        detection in ``reachable`` and the ``unresolved`` count stay exact).
        """
        func = call.func
        if isinstance(func, ast.Name):
            name = func.id
            matches = [
                sym
                for qual, sym in file_symbols.items()
                if qual.rsplit(".", 1)[-1] == name and sym.kind != "doc_anchor"
            ]
            if matches:
                best = min(matches, key=lambda s: (len(s.qualname), s.start_line))
                return best.sym_id
            return f"{_UNRESOLVED_PREFIX}{name}>"
        if (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == "self"
            and class_qualname
        ):
            attr = func.attr
            matches = [
                sym
                for qual, sym in file_symbols.items()
                if qual.startswith(class_qualname + ".") and qual.rsplit(".", 1)[-1] == attr and sym.kind == "method"
            ]
            if matches:
                best = min(matches, key=lambda s: (len(s.qualname), s.start_line))
                return best.sym_id
            return f"{_UNRESOLVED_PREFIX}self.{attr}>"
        if isinstance(func, ast.Attribute):
            base = _base_name(func.value)
            attr = func.attr
            return f"{_UNRESOLVED_PREFIX}{base}.{attr}>" if base else f"{_UNRESOLVED_PREFIX}{attr}>"
        return f"{_UNRESOLVED_PREFIX}?>"


__all__ = [
    "KIND_DOC_ANCHOR",
    "MAX_MANAGED_AST_NODES",
    "MAX_MANAGED_EDGES",
    "MAX_MANAGED_FILE_AST_NODES",
    "MAX_MANAGED_FILE_EDGES",
    "MAX_MANAGED_SQLITE_CACHE_KIB",
    "MAX_MANAGED_SQLITE_PAGES",
    "MAX_MANAGED_SQLITE_PAGE_SIZE",
    "MAX_MANAGED_SYMBOLS",
    "StructIndexStats",
    "StructuralIndex",
    "SymbolRow",
]


def _collect_symbols_pass(
    node: ast.AST,
    scope: list[tuple[str, bool]],
    rel: str,
    file_symbols: dict[str, _FileSymbol],
) -> None:
    """Pass 1: insert every function/method symbol (no edges)."""
    if isinstance(node, ast.ClassDef):
        for child in ast.iter_child_nodes(node):
            _collect_symbols_pass(child, [*scope, (node.name, True)], rel, file_symbols)
        return
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        own_scope = [*scope, (node.name, False)]
        qualname = ".".join(name for name, _ in own_scope)
        kind = "method" if scope and scope[-1][1] else "function"
        file_symbols[qualname] = _FileSymbol(
            qualname=qualname,
            sym_id=_hash16(f"{rel}:{qualname}"),
            rel=rel,
            kind=kind,
            start_line=node.lineno,
            end_line=getattr(node, "end_lineno", None) or node.lineno,
            docstring=_docstring_first_line(node),
        )
        for child in ast.iter_child_nodes(node):
            _collect_symbols_pass(child, own_scope, rel, file_symbols)
        return
    for child in ast.iter_child_nodes(node):
        _collect_symbols_pass(child, scope, rel, file_symbols)


def _collect_edges_pass(
    node: ast.AST,
    scope: list[tuple[str, bool]],
    rel: str,
    file_symbols: dict[str, _FileSymbol],
    edges: set[tuple[str, str, int]],
    *,
    edge_limit: int | None = None,
) -> None:
    """Pass 2: resolve call edges against the COMPLETE in-file symbol set."""
    if isinstance(node, ast.ClassDef):
        for child in ast.iter_child_nodes(node):
            _collect_edges_pass(child, [*scope, (node.name, True)], rel, file_symbols, edges, edge_limit=edge_limit)
        return
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        own_scope = [*scope, (node.name, False)]
        qualname = ".".join(name for name, _ in own_scope)
        class_chain = [name for name, is_class in scope if is_class]
        class_qualname = ".".join(class_chain) if class_chain else None
        caller_id = _hash16(f"{rel}:{qualname}")
        for call in _iter_body_calls(node):
            callee = StructuralIndex._resolve_callee(call, file_symbols, class_qualname)
            edge = (caller_id, callee, call.lineno)
            if edge not in edges:
                edges.add(edge)
                if edge_limit is not None and len(edges) > edge_limit:
                    from fa.memory.managed_discovery import ManagedDiscoveryError

                    raise ManagedDiscoveryError("edge_budget")
        for child in ast.iter_child_nodes(node):
            _collect_edges_pass(child, own_scope, rel, file_symbols, edges, edge_limit=edge_limit)
        return
    for child in ast.iter_child_nodes(node):
        _collect_edges_pass(child, scope, rel, file_symbols, edges, edge_limit=edge_limit)
