"""Unified FTS5 search index (BM25 + trigram) for ``fs_search`` tool.

Replaces the three-tool grep/instant_grep/glob surface with a single
on-disk index at ``.fa/fts.db``. Two virtual tables:

* ``files_fts`` (trigram) — populated with RAW file content, used for
  substring fallback queries (partial identifiers, typos, fragments).
* ``files_fts_bm25`` (unicode61) — populated with BM25-normalized content
  (snake_case / CamelCase tokenized), used for ranked primary search.
* ``fts_meta(path PRIMARY KEY, mtime REAL, size INTEGER)`` — reused
  from the existing InstantGrepIndex schema for incremental mtime/size
  checks.
* ``search_meta(key PRIMARY KEY, value)`` — holds ``schema_version``.

Fail-degraded (INV-S14b-2): if sqlite3 FTS5 is missing, or the DB can't
be opened, or indexing throws, ``search()`` falls back to a streaming
Python walk and returns results with ``method='literal_fallback'``.
The tool never crashes the loop.

§R-1 tokenizer normalization (critical for identifier search):
see ``_bm25_tokenize``.
"""

from __future__ import annotations

import fnmatch as _fnmatch
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from dataclasses import replace as dataclasses_replace
from pathlib import Path
from typing import Any, Self

from fa.memory._safe_walk import DEFAULT_PATTERNS, iter_searchable_files

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema version — bump when tables/columns change to force rebuild.
# ---------------------------------------------------------------------------
SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Content size caps (bytes). Matches InstantGrepIndex's 100KB cap per file.
# ---------------------------------------------------------------------------
MAX_CONTENT_BYTES_INDEXED = 100_000
SNIPPET_MAX_BYTES = 400

# ---------------------------------------------------------------------------
# Production refresh/robustness tuning (S14b.1-hardening).
# ---------------------------------------------------------------------------

#: Minimum wall-clock gap between quick-refresh walks for the same
#: (db_path, root). Canary O(1) stat checks still run every call; the
#: throttled gate limits how often we perform a full os.walk when the
#: canary reports "something may have changed". 5 seconds is a balance
#: between freshness for an interactive agent loop and stat pressure on
#: large repositories. Correctness is never sacrificed: the python-walk
#: fallback at search-time always reads the live filesystem.
REFRESH_THROTTLE_SECONDS: float = 5.0

#: Number of leading bytes to sniff for a NUL byte when detecting binary
#: files (mirrors ripgrep/git/... convention).
BINARY_SNIFF_BYTES: int = 8192

#: Canary files (relative to workspace root) whose mtimes we stat to
#: short-circuit refresh. ``.git/index`` changes on checkout/add/reset;
#: ``.git/FETCH_HEAD`` changes on pull/fetch. Missing canaries contribute
#: ``0.0`` to the canary tuple and never trigger a false "changed" signal.
_INDEX_CANARY_FILES: tuple[str, ...] = (".git/index", ".git/FETCH_HEAD")

#: Per-process refresh state keyed by f"{db_path}::{root}". Maps to a
#: dict with keys ``last_mono`` (time.monotonic of last completed refresh)
#: and ``last_canary`` (tuple[mtime, ...] observed at that refresh).
#: Module-level so ephemeral SearchIndex instances (e.g. subagent_prompts)
#: share the canary cache and do not re-walk on every call.
_refresh_state: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# BM25 tokenizer normalization (R-1)
# ---------------------------------------------------------------------------

_CAMEL_RE1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_RE2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_UNDERSCORE_RE = re.compile(r"_")
_MULTISPACE_RE = re.compile(r"\s+")


def _bm25_tokenize(text: str) -> str:
    """Normalize text for the BM25 unicode61 FTS table.

    * Replaces ``_`` with space so ``build_instant_grep_tool`` becomes
      "build instant grep tool" and each subtoken is indexed separately.
    * Inserts spaces at camelCase / PascalCase boundaries.
    * Collapses runs of whitespace.
    * Does NOT lowercase — FTS5 unicode61 is case-insensitive by default.

    Trigram table (substring fallback) gets the RAW text, not this
    normalized version, so partial fragments still match.
    """
    if not text:
        return ""
    s = _UNDERSCORE_RE.sub(" ", text)
    s = _CAMEL_RE1.sub(r"\1 \2", s)
    s = _CAMEL_RE2.sub(r"\1 \2", s)
    s = _MULTISPACE_RE.sub(" ", s)
    return s


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _rel_in_tests_dir(rel: str) -> bool:
    """Return True if relpath points into a tests/ directory."""
    parts = rel.replace("\\", "/").split("/")
    return "tests" in parts


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SearchStats:
    """Output of :meth:`SearchIndex.ensure_indexed`."""

    indexed: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    total_candidates: int = 0


@dataclass(frozen=True, slots=True)
class SearchParams:
    """Single carrier for search knobs that flow from the fs_search
    tool through the index/walk/formatting pipeline.

    Replaces an 11-argument keyword forward (which triggered
    ``pylint R0801 duplicate-code`` between ``fs_search.py`` and
    ``search_index.py``) with one typed, immutable object. Collecting
    parameters here also:

    * prevents argument-order bugs when a new flag is added,
    * keeps public ``SearchIndex.search`` and the internal
      ``_search_python_walk``/``_format_hits``/... signatures short,
    * makes it trivial to log or snapshot a query's full configuration
      for debugging.

    Attributes correspond to the user-facing parameters of the
    ``fs_search`` tool, plus derived ``subdir_rel``.
    """

    query: str
    output_mode: str = "files"
    glob_pat: str | None = None
    subdir_rel: str = ""
    include_tests: bool = True
    exclude_set: frozenset[str] = field(default_factory=frozenset)
    max_file_size: int = 200_000
    context_lines: int = 1
    limit: int = 20
    regex: bool = False
    case_sensitive: bool = False
    order: str = "bm25"


@dataclass
class SearchResult:
    """Output of :meth:`SearchIndex.search` (raw, pre-ToolSpec shaping)."""

    query: str
    method: str
    files: list[dict[str, Any]] = field(default_factory=list)
    matches: list[dict[str, Any]] = field(default_factory=list)
    regions: list[dict[str, Any]] = field(default_factory=list)
    counts: list[dict[str, Any]] = field(default_factory=list)
    returned: int = 0
    truncated: bool = False
    total_bytes: int = 0
    index_stats: SearchStats | None = None
    warnings: list[str] = field(default_factory=list)
    note: str | None = None


# ---------------------------------------------------------------------------
# SearchIndex
# ---------------------------------------------------------------------------


class SearchIndex:
    """Unified BM25+trigram FTS5 index over a workspace."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._indexed_for_session: bool = False
        self._available: bool = True
        self._connect()

    # ------------------------------------------------------------------
    # Connection / schema
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        try:
            self._conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.Error as exc:
            logger.warning("FTS open failed (%s); index unavailable", exc)
            self._available = False
            self._conn = None
            return

        if self._conn is None:
            self._available = False
            return

        try:
            self._conn.execute("CREATE TABLE IF NOT EXISTS fts_meta(path TEXT PRIMARY KEY, mtime REAL, size INTEGER)")
            self._conn.execute("CREATE TABLE IF NOT EXISTS search_meta(key TEXT PRIMARY KEY, value TEXT)")
            cur = self._conn.execute("SELECT value FROM search_meta WHERE key='schema_version'")
            row = cur.fetchone()
            version = int(row[0]) if row else 0
            if version < SCHEMA_VERSION:
                self._migrate(version)
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("FTS schema init failed (%s); falling back to walk", exc)
            self._available = False

    def _migrate(self, from_version: int) -> None:
        if self._conn is None:
            raise RuntimeError("FTS connection is unavailable during _migrate")
        logger.info(
            "FTS schema migration v%d -> v%d; rebuilding FTS tables",
            from_version,
            SCHEMA_VERSION,
        )
        self._conn.execute("DROP TABLE IF EXISTS files_fts_bm25")
        self._conn.execute("DROP TABLE IF EXISTS files_fts")
        self._conn.execute("DELETE FROM fts_meta")
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS files_fts USING fts5(path UNINDEXED, content, tokenize='trigram')"
        )
        self._conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS files_fts_bm25 USING fts5("
            "path UNINDEXED, content, tokenize='unicode61 remove_diacritics 2')"
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO search_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def _state_key(self, root: Path) -> str:
        """Key into ``_refresh_state`` for this (db, root) pair."""
        return f"{self.db_path}::{root}"

    @staticmethod
    def _stat_canaries(root: Path) -> tuple[float, ...]:
        """Return a tuple of mtimes used as an inexpensive "did the
        filesystem change?" signal. Root directory mtime changes when
        files are created or deleted at the top level. ``.git/index``
        changes on git operations (checkout, add, reset, commit).
        ``.git/FETCH_HEAD`` changes on pull/fetch. Missing files
        contribute 0.0 so a missing canary never flags as "changed".
        Any OSError is swallowed and contributes 0.0.
        """
        canary_paths: list[Path] = [root]
        canary_paths.extend(root / cf for cf in _INDEX_CANARY_FILES)
        mtimes: list[float] = []
        for p in canary_paths:
            try:
                mtimes.append(p.stat().st_mtime)
            except OSError:
                mtimes.append(0.0)
        return tuple(mtimes)

    def _should_refresh(self, key: str, canary: tuple[float, ...]) -> bool:
        """Decide whether a refresh walk should run.

        Returns False only in the steady-state fast path: (a) a full
        build has been done in this process for ``key``, (b) fewer than
        ``REFRESH_THROTTLE_SECONDS`` seconds have elapsed since the
        last refresh, and (c) the canary mtimes are byte-identical to
        the last observation. Any deviation (first call, forced
        refresh, throttle elapsed, canary changed) returns True.
        """
        state: dict[str, Any] | None = _refresh_state.get(key)
        if state is None:
            return True  # never indexed → full build
        if state.get("full_done") is not True:
            return True
        last_mono: float = state.get("last_mono", 0.0)
        if time.monotonic() - last_mono < REFRESH_THROTTLE_SECONDS:
            return False
        return state.get("last_canary") != canary

    def _index_one_file(
        self,
        fp: Path,
        rel: str,
        mtime: float,
        size: int,
        stats: SearchStats,
    ) -> None:
        """Index a single file. Updates stats.indexed/updated/errors
        in place. Safe to call on any file: binary, unreadable, or
        undecodable files are skipped with an error count.

        Caller must ensure ``self._conn`` is not None.
        """
        conn: sqlite3.Connection = self._conn  # type: ignore[assignment]
        try:
            cur = conn.execute("SELECT mtime, size FROM fts_meta WHERE path=?", (rel,)).fetchone()
            if cur and abs(cur[0] - mtime) < 1e-6 and cur[1] == size:
                stats.skipped += 1
                return
            text: str | None = self._read_text_for_index(fp)
            if text is None:
                # Binary or unreadable — skip without flagging error
                # (binary detection is intentional, not failure).
                stats.skipped += 1
                return
            conn.execute("DELETE FROM files_fts WHERE path=?", (rel,))
            conn.execute("DELETE FROM files_fts_bm25 WHERE path=?", (rel,))
            conn.execute(
                "INSERT INTO files_fts(path, content) VALUES(?, ?)",
                (rel, text[:MAX_CONTENT_BYTES_INDEXED]),
            )
            conn.execute(
                "INSERT INTO files_fts_bm25(path, content) VALUES(?, ?)",
                (rel, _bm25_tokenize(text)[:MAX_CONTENT_BYTES_INDEXED]),
            )
            conn.execute(
                "INSERT OR REPLACE INTO fts_meta(path, mtime, size) VALUES(?, ?, ?)",
                (rel, mtime, size),
            )
            if cur:
                stats.updated += 1
            else:
                stats.indexed += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("failed to index %s: %s", rel, exc)
            stats.errors += 1

    def _cleanup_stale_files(self, root: Path, seen: set[str]) -> None:
        """Delete fts_meta and FTS rows for files that no longer
        exist. Only deletes a row if the file is provably absent
        (``is_file()`` returns False) to avoid pruning files that
        transiently disappeared due to races or permission errors.
        """
        if self._conn is None:
            return
        try:
            for (rel,) in self._conn.execute("SELECT path FROM fts_meta").fetchall():
                if rel in seen:
                    continue
                if (root / rel).is_file():
                    continue
                self._conn.execute("DELETE FROM files_fts WHERE path=?", (rel,))
                self._conn.execute("DELETE FROM files_fts_bm25 WHERE path=?", (rel,))
                self._conn.execute("DELETE FROM fts_meta WHERE path=?", (rel,))
        except Exception as exc:  # noqa: BLE001
            logger.warning("stale cleanup failed: %s", exc)

    def _walk_and_index(
        self,
        root: Path,
        patterns: tuple[str, ...],
        extra_exclude_dirs: frozenset[str] | None,
        include_tests: bool,
        max_file_size: int,
        stats: SearchStats,
    ) -> set[str]:
        """Walk files and upsert FTS rows for new/changed files.
        Returns the set of ``rel`` paths observed (used for stale
        cleanup).
        """
        seen: set[str] = set()
        for fp, rel, mtime, size in iter_searchable_files(
            root,
            patterns,
            extra_exclude_dirs=extra_exclude_dirs,
            include_tests=include_tests,
            max_file_size=max_file_size,
        ):
            stats.total_candidates += 1
            # Defense-in-depth: ensure the rel is still inside root
            # (iter_searchable_files already does this, but re-check
            # after resolve to guard against TOCTOU symlink swaps).
            try:
                resolved: Path = fp.resolve()
                if not resolved.is_relative_to(root):
                    logger.warning("skipping path outside root during indexing: %s", rel)
                    stats.errors += 1
                    continue
                rel = str(resolved.relative_to(root)).replace("\\", "/")
            except (OSError, ValueError) as exc:
                logger.debug("skipping %s during indexing: %s", fp, exc)
                stats.errors += 1
                continue
            seen.add(rel)
            self._index_one_file(fp, rel, mtime, size, stats)
        return seen

    def ensure_indexed(
        self,
        root: Path,
        *,
        patterns: tuple[str, ...] = DEFAULT_PATTERNS,
        extra_exclude_dirs: frozenset[str] | None = None,
        include_tests: bool = True,
        max_file_size: int = MAX_CONTENT_BYTES_INDEXED,
        force: bool = False,
    ) -> SearchStats:
        """Build or incrementally refresh both FTS tables.

        Three modes:
        1. **Full build** (first call for this (db, root), or
           ``force=True``): walks every file, populates tables, then
           prunes stale rows.
        2. **Quick refresh** (subsequent calls when canary changed or
           throttle expired): walks every file but skips content reads
           for files whose (mtime, size) match ``fts_meta``, then prunes
           rows for files that no longer exist.
        3. **Fast-path noop** (canary unchanged and within throttle
           window): returns an empty ``SearchStats`` immediately —
           only a few ``stat()`` calls performed.

        Idempotent and fail-degraded: any exception during indexing
        sets ``self._available = False`` (caller falls back to walk).
        """
        stats = SearchStats()
        if not self._available or self._conn is None:
            return stats
        root = root.resolve()
        if not root.is_dir():
            return stats

        key: str = self._state_key(root)
        state: dict[str, Any] = _refresh_state.setdefault(
            key, {"full_done": False, "last_mono": 0.0, "last_canary": None}
        )

        # Check fast path first (canary + throttle).
        canary: tuple[float, ...] = self._stat_canaries(root)
        need_walk: bool = force or self._should_refresh(key, canary)

        if not need_walk:
            # Fast path: nothing changed.
            self._indexed_for_session = True
            return stats

        try:
            seen: set[str] = self._walk_and_index(
                root, patterns, extra_exclude_dirs, include_tests, max_file_size, stats
            )
            self._cleanup_stale_files(root, seen)
            self._conn.commit()
            self._indexed_for_session = True
            state["full_done"] = True
            state["last_mono"] = time.monotonic()
            state["last_canary"] = canary
        except Exception as exc:  # noqa: BLE001
            logger.warning("ensure_indexed failed (%s); falling back for queries", exc)
            self._available = False
            try:
                self._conn.rollback()
            except sqlite3.Error:
                pass
        return stats

    # ------------------------------------------------------------------
    # Query helpers (PURE — no FS / DB IO)
    # ------------------------------------------------------------------

    @staticmethod
    def _escape_like(text: str, esc: str = "\\") -> str:
        """Escape meta-characters for a SQL LIKE clause that uses ``esc``
        as its ESCAPE character. Returns a string that, when used as the
        right-hand side of ``LIKE ? ESCAPE '<esc>'``, matches ``text``
        literally (``%``, ``_`` and the escape character itself lose their
        wildcard meaning).

        The escape character MUST be escaped FIRST, otherwise the escapes
        we insert for ``%`` / ``_`` would themselves get escaped.
        """
        return text.replace(esc, esc + esc).replace("%", esc + "%").replace("_", esc + "_")

    @staticmethod
    def _escape_fts_query(query: str) -> str:
        """Construct a safe FTS5 MATCH right-hand side from a raw user
        query that implements implicit-AND semantics.

        Grammar:
        - At a token boundary (start of input or after whitespace), a
          ``"`` opens a phrase; the phrase runs until the next matching
          ``"``; a pair of ``""`` inside a phrase encodes a literal
          quote; an unmatched opening quote is auto-closed at EOS.
        - Outside phrases, runs of non-whitespace characters are bare
          tokens; any ``"`` inside a bare token is treated as a literal
          quote character (doubled in the output) rather than opening a
          phrase — this avoids splitting ``he"llo`` into two tokens.
        - A trailing ``*`` on a bare token is kept OUTSIDE the wrapping
          quotes (FTS5 prefix operator: ``"auth"*``). Inside a phrase,
          ``*`` is a literal.
        - Every bare token is wrapped in ``"..."`` to escape FTS5
          operators/punctuation (``AND``/``OR``/``NOT``/``NEAR``/``:``/
          ``^``/``(``/``)``/``[``/``]``/``{``/``}`` are all treated as
          literals).

        Examples (output):
            auth middleware           -> "auth" "middleware"
            "auth middleware"         -> "auth middleware"
            auth*                     -> "auth"*
            hello "world peace" now   -> "hello" "world peace" "now"
            he"llo                    -> "he""llo"
            foo (bar) baz             -> "foo" "(" "bar" ")" "baz"
        """
        out_parts: list[str] = []
        i: int = 0
        n: int = len(query)
        while i < n:
            c: str = query[i]
            if c.isspace():
                i += 1
                continue
            if c == '"':
                # Phrase (only recognized at a token boundary).
                i += 1  # consume opening quote
                buf: list[str] = ['"']
                closed: bool = False
                while i < n:
                    ch: str = query[i]
                    if ch == '"':
                        if i + 1 < n and query[i + 1] == '"':
                            # Escaped "" inside phrase -> one literal ".
                            buf.append('""')
                            i += 2
                            continue
                        buf.append('"')
                        i += 1
                        closed = True
                        break
                    buf.append(ch)
                    i += 1
                if not closed:
                    buf.append('"')
                out_parts.append("".join(buf))
                continue
            # Bare token: run until whitespace (quotes inside are
            # treated as literal characters, not phrase openers).
            j: int = i
            while j < n and not query[j].isspace():
                j += 1
            tok: str = query[i:j]
            i = j
            if not tok:
                continue
            prefix_star: bool = tok.endswith("*") and len(tok) > 1
            if prefix_star:
                tok = tok[:-1]
            # Double any embedded quote so it is a literal inside the
            # quoted token.
            tok_safe: str = tok.replace('"', '""')
            wrapped: str = f'"{tok_safe}"'
            if prefix_star:
                wrapped += "*"
            out_parts.append(wrapped)
        return " ".join(out_parts)

    @staticmethod
    def _is_binary(sample: bytes) -> bool:
        """Return True if the byte sample looks like a binary file (NUL
        byte heuristic, same convention as ripgrep/git)."""
        return b"\x00" in sample

    @staticmethod
    def _read_bytes(fp: Path, max_bytes: int) -> bytes | None:
        """Read up to ``max_bytes`` from ``fp``. Returns None on IO error."""
        try:
            with fp.open("rb") as f:
                return f.read(max_bytes)
        except OSError:
            return None

    @classmethod
    def _read_text_for_index(cls, fp: Path) -> str | None:
        """Read up to ``MAX_CONTENT_BYTES_INDEXED`` bytes from ``fp`` and
        decode to text for FTS indexing. Returns None if the file is
        binary (NUL in the first ``BINARY_SNIFF_BYTES`` bytes) or cannot
        be read. Decoding uses UTF-8 strict with Latin-1 fallback so any
        byte sequence is representable (no silent replacement)."""
        raw: bytes | None = cls._read_bytes(fp, MAX_CONTENT_BYTES_INDEXED)
        if raw is None:
            return None
        sniff: bytes = raw[:BINARY_SNIFF_BYTES] if BINARY_SNIFF_BYTES < len(raw) else raw
        if cls._is_binary(sniff):
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw.decode("latin-1")
            except Exception:  # noqa: BLE001 — Latin-1 maps every byte; this is defensive.
                return None

    @classmethod
    def _read_text_for_match(cls, fp: Path, max_bytes: int) -> str:
        """Read up to ``max_bytes`` for snippet/context display. Does NOT
        apply binary detection (if we are here the file already passed
        indexing filters). Returns "" on IO error."""
        raw: bytes | None = cls._read_bytes(fp, max_bytes)
        if raw is None:
            return ""
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return raw.decode("latin-1")
            except Exception:  # noqa: BLE001
                return ""

    @staticmethod
    def _compute_total_bytes(root: Path, rels: list[str]) -> int:
        total: int = 0
        for rel in rels:
            try:
                total += (root / rel).stat().st_size
            except OSError:
                continue
        return total

    @staticmethod
    def _path_like(subdir_rel: str) -> str:
        """Conservative SQL LIKE pattern for subdir prefix pushdown on
        the ``path`` column. Returns a LIKE pattern that matches all
        paths under ``subdir_rel`` (including subdir_rel itself when it
        is ""). All literal characters (including any that happen to look
        like LIKE wildcards) are escaped; the only wildcard is the
        trailing ``%`` we append. Glob filtering is applied post-fetch
        via ``_path_matches`` (Python-authoritative)."""
        if not subdir_rel:
            return "%"
        return SearchIndex._escape_like(subdir_rel) + "%"

    @staticmethod
    def _passes_filters(
        rel: str,
        *,
        subdir_rel: str,
        glob_pat: str | None,
        include_tests: bool,
        exclude_set: frozenset[str],
    ) -> bool:
        """Single authority for query-time path filters.

        Returns True iff ALL of:
        1. ``subdir_rel`` is empty OR ``rel`` lives under ``subdir_rel``
           (either as a direct child or deeper; also accepts an exact
           match against ``subdir_rel.rstrip("/")``).
        2. ``include_tests`` is True OR no path component equals
           ``"tests"``.
        3. No path component is in ``exclude_set``.
        4. ``glob_pat`` is None OR ``_path_matches(rel, glob_pat)`` holds.

        This is called from every search path (BM25 post-fetch, trigram
        post-fetch, python-walk pre-yield, and _collect_matches as
        defense-in-depth against stale symlinks/index drift) so that
        filters cannot be accidentally bypassed on any code path.
        """
        if subdir_rel:
            if not (rel + "/").startswith(subdir_rel) and rel != subdir_rel.rstrip("/"):
                return False
        parts: list[str] = rel.replace("\\", "/").split("/")
        if not include_tests and "tests" in parts:
            return False
        if not exclude_set.isdisjoint(parts):
            return False
        if glob_pat is not None and not SearchIndex._path_matches(rel, glob_pat):
            return False
        return True

    @staticmethod
    def _path_matches(rel: str, glob_pat: str | None) -> bool:
        """Return True if POSIX relative path ``rel`` matches
        ``glob_pat`` with proper recursive-glob semantics.

        Rules:
        - ``**`` matches zero or more path segments (e.g. ``src/**/*.py``
          matches ``src/a.py``, ``src/sub/a.py`` and ``src/sub/deep/a.py``;
          ``**/*.py`` matches any ``.py`` file at any depth).
        - ``*`` matches any sequence of characters within ONE path
          segment (does not cross ``/``).
        - ``?`` matches a single character within a segment.
        - A pattern without ``/`` is treated as a basename pattern that
          matches at any depth (ripgrep/IDE convention, so ``*.py``
          matches both ``a.py`` and ``src/deep/a.py``).
        - Otherwise the pattern must match the full relative path.

        ``PurePath.match`` is NOT used because stdlib implements ``**``
        in the middle of a pattern as single-segment (a long-standing
        documented quirk).
        """
        if not glob_pat:
            return True
        # Basename-only pattern: match against the filename component.
        if "/" not in glob_pat:
            from os.path import basename as _basename

            return _fnmatch.fnmatch(_basename(rel), glob_pat)
        # Normalize: strip leading "./" from rel if present.
        if rel.startswith("./"):
            rel = rel[2:]
        path_parts: list[str] = rel.split("/")
        # Normalize pattern: split on "/"; treat consecutive slashes as one.
        pat_parts: list[str] = [p for p in glob_pat.split("/") if p != ""]
        return SearchIndex._glob_parts_match(path_parts, pat_parts)

    @staticmethod
    def _glob_parts_match(path_parts: list[str], pat_parts: list[str]) -> bool:
        """Recursive matcher: True iff ``path_parts`` match ``pat_parts``
        where ``"**"`` in the pattern matches zero or more segments.
        ``*`` and ``?`` use ``fnmatch`` semantics per segment.
        """
        # Tail-recursive implementation using an explicit stack to
        # avoid Python recursion limits on deep directories.
        stack: list[tuple[int, int]] = [(0, 0)]
        while stack:
            pi, gi = stack.pop()
            # Both consumed: match.
            if pi == len(path_parts) and gi == len(pat_parts):
                return True
            # Pattern consumed but path has segments left: no match
            # along this branch (** backtracking handles other arities).
            if gi == len(pat_parts):
                continue
            pat: str = pat_parts[gi]
            if pat == "**":
                # "**" matches zero segments (skip the pattern) or one
                # segment (stay on "**", advance path). Push both
                # continuations; either succeeding means match.
                stack.append((pi, gi + 1))
                if pi < len(path_parts):
                    stack.append((pi + 1, gi))
                continue
            if pi < len(path_parts) and _fnmatch.fnmatchcase(path_parts[pi], pat):
                stack.append((pi + 1, gi + 1))
        return False

    @staticmethod
    def _first_match(text: str, needle: str, case_sensitive: bool) -> tuple[int, str] | None:
        hay = text if case_sensitive else text.lower()
        n = needle if case_sensitive else needle.lower()
        idx = hay.find(n)
        if idx < 0:
            return None
        line_no = text.count("\n", 0, idx) + 1
        line_start = text.rfind("\n", 0, idx) + 1
        line_end = text.find("\n", idx)
        if line_end < 0:
            line_end = len(text)
        snippet = text[line_start:line_end].rstrip()
        if len(snippet) > SNIPPET_MAX_BYTES:
            snippet = snippet[:SNIPPET_MAX_BYTES] + "..."
        return (line_no, snippet)

    # ------------------------------------------------------------------
    # Search: BM25 → trigram → literal walk
    # ------------------------------------------------------------------

    def search(
        self,
        params: SearchParams,
        *,
        root: Path,
        subpath: str = ".",
    ) -> SearchResult:
        """Run search, falling back through strategies as needed.

        All search knobs are carried on ``params`` (see :class:`SearchParams`);
        ``root`` and ``subpath`` are kept as explicit positional/keyword
        arguments because they describe *where* to search in the filesystem,
        not *how* to search.
        """
        # params.order is reserved for future use; only "bm25" is honored in v1.
        # The parameter is accepted on SearchParams for forward-compat but is not
        # consulted in this implementation.
        _ = params.order
        root = root.resolve()
        subdir = (root / subpath).resolve() if subpath else root
        try:
            subdir.relative_to(root)
        except ValueError:
            return SearchResult(
                query=params.query,
                method="literal_fallback",
                warnings=[f"path escapes workspace root: {subpath}"],
            )

        if subdir == root:
            subdir_rel = ""
        else:
            subdir_rel = subdir.relative_to(root).as_posix() + "/"

        # Freeze the resolved subdir into an effective-params object so
        # downstream helpers read everything off one carrier.
        effective: SearchParams = params  # alias if subdir_rel already matches
        if subdir_rel != params.subdir_rel:
            effective = dataclasses_replace(
                params,
                subdir_rel=subdir_rel,
                exclude_set=(params.exclude_set if params.exclude_set else frozenset()),
            )

        result = SearchResult(query=params.query, method="literal_fallback")

        # Regex and case-sensitive searches force the python-walk path:
        # FTS5 MATCH/LIKE cannot honor Python regex or case-sensitive
        # semantics against a case-folded tokenizer.
        if effective.regex or effective.case_sensitive:
            return self._search_python_walk(
                params=effective,
                root=root,
                _subdir=subdir,
                result=result,
                as_regex=bool(effective.regex),
            )

        # F2: ephemeral instances (e.g. subagent_prompts creates one per
        # call) must inherit the "index built" flag from module-level
        # state so they actually use the on-disk FTS index instead of
        # always falling back to a python walk.
        if not self._indexed_for_session:
            key_for_root: str = self._state_key(root)
            prior_state: dict[str, Any] | None = _refresh_state.get(key_for_root)
            if prior_state and prior_state.get("full_done") is True:
                self._indexed_for_session = True

        if self._available and self._conn is not None and self._indexed_for_session:
            # Hybrid: fetch BM25-ranked hits, then union with trigram
            # substring hits to catch partial-identifier matches the
            # unicode61 tokenizer would miss (e.g. "auth" inside
            # "AuthenticationMiddleware"). Merge by score: BM25 hits
            # come first (negative bm25 score = better), then trigram
            # hits at score 0.0 preserve their FTS-insertion order.
            # All candidate rels go through _passes_filters so subdir,
            # glob, include_tests, and exclude_dirs apply uniformly.
            bm25_hits = self._search_bm25(effective.query, limit=effective.limit * 2, subdir_rel=effective.subdir_rel)
            tri_hits = self._search_trigram(effective.query, limit=effective.limit * 2, subdir_rel=effective.subdir_rel)
            seen: set[str] = set()
            merged: list[tuple[str, float]] = []
            for rel, score in bm25_hits:
                if rel in seen:
                    continue
                if not self._passes_filters(
                    rel,
                    subdir_rel=effective.subdir_rel,
                    glob_pat=effective.glob_pat,
                    include_tests=effective.include_tests,
                    exclude_set=effective.exclude_set,
                ):
                    continue
                seen.add(rel)
                merged.append((rel, score))
            for rel, score in tri_hits:
                if rel in seen:
                    continue
                if not self._passes_filters(
                    rel,
                    subdir_rel=effective.subdir_rel,
                    glob_pat=effective.glob_pat,
                    include_tests=effective.include_tests,
                    exclude_set=effective.exclude_set,
                ):
                    continue
                seen.add(rel)
                merged.append((rel, score))
            if merged:
                method = "fts5_bm25" if bm25_hits else "fts5_trigram_fallback"
                return self._format_hits(
                    merged,
                    params=effective,
                    root=root,
                    method=method,
                    result=result,
                )

        return self._search_python_walk(
            params=effective,
            root=root,
            _subdir=subdir,
            result=result,
            as_regex=False,
        )

    def _search_bm25(
        self,
        query: str,
        *,
        limit: int,
        subdir_rel: str,
    ) -> list[tuple[str, float]]:
        """BM25-ranked search on the unicode61 table. Returns (rel, score).

        Path/glob/test/exclude filtering is applied by the caller via
        ``_passes_filters`` so results are always authoritative regardless
        of which search strategy produced them.
        """
        if self._conn is None:
            return []
        q_escaped = self._escape_fts_query(query)
        sql = "SELECT path, bm25(files_fts_bm25) AS score FROM files_fts_bm25 WHERE files_fts_bm25 MATCH ? "
        params: list[Any] = [q_escaped]
        if subdir_rel:
            sql += "AND path LIKE ? ESCAPE '\\' "
            params.append(self._path_like(subdir_rel))
        sql += "ORDER BY score ASC LIMIT ?"
        params.append(limit * 2)
        try:
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            logger.debug("BM25 query failed (%s); falling back", exc)
            return []
        return [(rel, float(score)) for rel, score in rows][:limit]

    def _search_trigram(
        self,
        query: str,
        *,
        limit: int,
        subdir_rel: str,
    ) -> list[tuple[str, float]]:
        """Substring LIKE on the trigram FTS table (literal fallback for
        partial identifiers that the unicode61 tokenizer would miss).
        All LIKE meta-characters in ``query`` are escaped so they match
        literally. Path/glob/test/exclude filtering is applied by the
        caller via ``_passes_filters``."""
        if self._conn is None:
            return []
        try:
            like = f"%{self._escape_like(query)}%"
            sql = "SELECT path FROM files_fts WHERE content LIKE ? ESCAPE '\\' "
            params: list[Any] = [like]
            if subdir_rel:
                sql += "AND path LIKE ? ESCAPE '\\' "
                params.append(self._path_like(subdir_rel))
            sql += "LIMIT ?"
            params.append(limit * 2)
            rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            logger.debug("trigram query failed (%s); falling back", exc)
            return []
        return [(rel, 0.0) for (rel,) in rows][:limit]

    def _search_python_walk(
        self,
        *,
        params: SearchParams,
        root: Path,
        _subdir: Path,  # kept for API symmetry; filtering via params.subdir_rel.
        result: SearchResult,
        as_regex: bool,
    ) -> SearchResult:
        """Streaming fallback: read files off disk, match line-by-line.

        All filtering (subdir/glob/include_tests/exclude_dirs) goes
        through ``_passes_filters`` so semantics match the BM25/trigram
        paths. Walk-time ``extra_exclude_dirs`` is passed to
        ``iter_searchable_files`` as an early-prune optimization, but
        the semantic authority is ``_passes_filters``.
        """
        del _subdir  # filtering via params.subdir_rel keeps semantics consistent.
        query: str = params.query
        subdir_rel: str = params.subdir_rel
        output_mode: str = params.output_mode
        glob_pat: str | None = params.glob_pat
        include_tests: bool = params.include_tests
        exclude_set: frozenset[str] = params.exclude_set
        max_file_size: int = params.max_file_size
        limit: int = params.limit
        case_sensitive: bool = params.case_sensitive

        # For literal substring search we lowercase both sides when case-insensitive.
        # For regex search, compile with re.IGNORECASE so that uppercase atoms in
        # the pattern (e.g. ``\w+Middleware``) still match against original-cased
        # text — do NOT lowercase the haystack or character-class semantics shift
        # (R-fix from S14b.1 pre-deploy smoke test).
        pat: re.Pattern[str] | None
        if as_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            pat = re.compile(query, flags)
            needle = ""  # unused
        else:
            needle = query if case_sensitive else query.lower()
            pat = None

        hits: list[tuple[str, float]] = []
        matched_paths: list[str] = []
        match_counts: dict[str, int] = {}
        # For regex matches we compute per-file matches ourselves here (scanning
        # with the compiled pattern) and pass them to _format_hits via an
        # override, because _format_hits's default scanning uses literal
        # substring matching and cannot honour regex semantics.
        per_file_matches: dict[str, list[tuple[int, str]]] = {}

        read_cap: int = max(max_file_size, MAX_CONTENT_BYTES_INDEXED)
        try:
            for fp, rel, _mt, _sz in iter_searchable_files(
                root,
                DEFAULT_PATTERNS,
                extra_exclude_dirs=exclude_set,
                include_tests=include_tests,
                max_file_size=max_file_size,
                use_git_ls_files=self._available,
            ):
                # Defense-in-depth: resolve the path we are about to read and
                # confirm it stayed inside root and passes all filters. The
                # iterator already enforces containment, but re-checking here
                # protects against TOCTOU symlink swaps mid-iteration.
                try:
                    resolved: Path = fp.resolve()
                    if not resolved.is_relative_to(root):
                        logger.warning("skipping path outside root during walk: %s", rel)
                        continue
                    rel = str(resolved.relative_to(root)).replace("\\", "/")
                except (OSError, ValueError) as exc:
                    logger.debug("skipping %s during walk: %s", fp, exc)
                    continue
                if not self._passes_filters(
                    rel,
                    subdir_rel=subdir_rel,
                    glob_pat=glob_pat,
                    include_tests=include_tests,
                    exclude_set=exclude_set,
                ):
                    continue
                text = self._read_text_for_match(fp, read_cap)
                if as_regex:
                    if pat is None:
                        continue  # defensive; pat is always compiled above.
                    file_matches: list[tuple[int, str]] = []
                    for i, line in enumerate(text.splitlines(), start=1):
                        if pat.search(line):
                            file_matches.append((i, line.rstrip()))
                    cnt = len(file_matches)
                    found = cnt > 0
                    if found:
                        per_file_matches[rel] = file_matches
                else:
                    hay = text if case_sensitive else text.lower()
                    found = needle in hay
                    cnt = hay.count(needle)
                if not found:
                    continue
                if rel not in match_counts:
                    matched_paths.append(rel)
                    match_counts[rel] = cnt
                    hits.append((rel, 0.0))
                else:
                    match_counts[rel] = cnt
                if output_mode in ("files", "counts") and len(matched_paths) >= limit:
                    result.truncated = True
                    break
        except Exception as exc:  # noqa: BLE001
            logger.warning("python walk fallback failed: %s", exc)
            result.warnings.append(f"walk fallback error: {exc}")

        result.method = "regex_fallback" if as_regex else "literal_fallback"
        return self._format_hits(
            hits,
            params=params,
            root=root,
            method=result.method,
            result=result,
            # Always supply match_counts for walk-fallback results so we don't
            # re-scan with a possibly-incompatible matcher (literal vs regex).
            match_counts_override=match_counts,
            per_file_matches_override=per_file_matches if as_regex else None,
        )

    # ------------------------------------------------------------------
    # Hit formatting helpers (extracted from _format_hits for C901).
    # ------------------------------------------------------------------

    @staticmethod
    def _scan_file_matches(
        text: str,
        needle: str,
        *,
        case_sensitive: bool,
        output_mode: str,
    ) -> tuple[list[tuple[int, str]], int]:
        """Scan ``text`` for ``needle``; return (line_matches, total_count).

        * For ``files`` mode returns only the first match (for snippet).
        * For ``matches``/``regions`` returns every line with a hit.
        * For ``counts`` returns (empty_list, occurrence_count).
        """
        if output_mode == "counts":
            hay = text if case_sensitive else text.lower()
            return [], hay.count(needle)

        matches: list[tuple[int, str]] = []
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            hay = line if case_sensitive else line.lower()
            if needle in hay:
                matches.append((i, line.rstrip()))
                if output_mode == "files":
                    # files mode: only first hit needed for snippet (R-10)
                    return matches, text.count(needle) if case_sensitive else text.lower().count(needle)
        count = len(matches)
        return matches, count

    @staticmethod
    def _build_files_output(
        matched_files: list[str],
        per_file_matches: dict[str, list[tuple[int, str]]],
        match_counts: dict[str, int],
        limit: int,
    ) -> list[dict[str, Any]]:
        files_out: list[dict[str, Any]] = []
        for rel in matched_files[:limit]:
            first_line: int | None = None
            first_snippet: str | None = None
            fms = per_file_matches.get(rel)
            if fms:
                first_line, raw_snip = fms[0]
                first_snippet = raw_snip[:SNIPPET_MAX_BYTES]
                if len(raw_snip) > SNIPPET_MAX_BYTES:
                    first_snippet += "..."
            files_out.append(
                {
                    "path": rel,
                    "match_count": match_counts.get(rel, 0),
                    "first_match_line": first_line,
                    "first_match_snippet": first_snippet,
                }
            )
        return files_out

    def _build_matches_output(
        self,
        root: Path,
        matched_files: list[str],
        per_file_matches: dict[str, list[tuple[int, str]]],
        *,
        context_lines: int,
        limit: int,
        max_file_size: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        matches_out: list[dict[str, Any]] = []
        truncated = False
        for rel in matched_files:
            fp: Path = root / rel
            # De-duplicate: the same rel can be repeated from multiple
            # hits; re-read only once per rel (matches/regions are read
            # in the same order, and we already have per_file_matches).
            full_text: str = self._read_text_for_match(fp, max_file_size)
            full_lines: list[str] = full_text.splitlines()
            for ln, content in per_file_matches.get(rel, []):
                start_ctx = max(0, ln - 1 - context_lines)
                end_ctx = min(len(full_lines), ln + context_lines)
                before = [line.rstrip() for line in full_lines[start_ctx : ln - 1]]
                after = [line.rstrip() for line in full_lines[ln:end_ctx]]
                matches_out.append(
                    {
                        "path": rel,
                        "line": ln,
                        "content": content[:SNIPPET_MAX_BYTES],
                        "before": before,
                        "after": after,
                    }
                )
                if len(matches_out) >= limit:
                    truncated = True
                    break
            if len(matches_out) >= limit:
                break
        return matches_out, truncated

    @staticmethod
    def _group_adjacent(fms: list[tuple[int, str]], context_lines: int) -> list[list[tuple[int, str]]]:
        if not fms:
            return []
        grouped: list[list[tuple[int, str]]] = [[fms[0]]]
        for ln, content in fms[1:]:
            prev_ln = grouped[-1][-1][0]
            if ln - prev_ln <= context_lines * 2 + 1:
                grouped[-1].append((ln, content))
            else:
                grouped.append([(ln, content)])
        return grouped

    def _build_regions_output(
        self,
        root: Path,
        matched_files: list[str],
        per_file_matches: dict[str, list[tuple[int, str]]],
        *,
        context_lines: int,
        limit: int,
        max_file_size: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        regions_out: list[dict[str, Any]] = []
        truncated = False
        for rel in matched_files:
            fms = per_file_matches.get(rel, [])
            if not fms:
                continue
            fp: Path = root / rel
            full_text: str = self._read_text_for_match(fp, max_file_size)
            full_lines: list[str] = full_text.splitlines()
            for grp in SearchIndex._group_adjacent(fms, context_lines):
                start = max(1, grp[0][0] - context_lines)
                end = min(len(full_lines), grp[-1][0] + context_lines)
                snippet = [full_lines[i - 1].rstrip() for i in range(start, end + 1) if 0 <= i - 1 < len(full_lines)]
                regions_out.append(
                    {
                        "path": rel,
                        "start_line": start,
                        "end_line": end,
                        "match_count": len(grp),
                        "snippet": snippet,
                    }
                )
                if len(regions_out) >= limit:
                    truncated = True
                    break
            if len(regions_out) >= limit:
                break
        return regions_out, truncated

    @staticmethod
    def _build_counts_output(
        matched_files: list[str], match_counts: dict[str, int], limit: int
    ) -> list[dict[str, Any]]:
        return [{"path": rel, "count": match_counts.get(rel, 0)} for rel in matched_files[:limit]]

    def _collect_matches(
        self,
        hits: list[tuple[str, float]],
        params: SearchParams,
        root: Path,
        needle: str,
        precomputed: dict[str, list[tuple[int, str]]],
    ) -> tuple[list[str], dict[str, int], dict[str, list[tuple[int, str]]], bool]:
        """Walk hits, scan file contents, return (matched_files, counts, per_file, truncated).

        Defense-in-depth: each rel is re-checked against ``_passes_filters``
        and its resolved path is verified to stay under ``root``. This
        guards against stale symlinks created after indexing or against
        any index path that evaded the iterator-time checks.
        """
        truncated = False
        matched_files: list[str] = []
        match_counts: dict[str, int] = {}
        per_file_matches: dict[str, list[tuple[int, str]]] = {}
        need_content = params.output_mode in ("matches", "regions", "files", "counts")
        read_cap: int = max(params.max_file_size, MAX_CONTENT_BYTES_INDEXED)
        for rel, _score in hits:
            if len(matched_files) >= params.limit and params.output_mode in ("files", "counts"):
                truncated = True
                break
            # D-in-D: re-run filter on rel from the index (catches stale
            # entries whose exclude/include status changed across calls).
            if not self._passes_filters(
                rel,
                subdir_rel=params.subdir_rel,
                glob_pat=params.glob_pat,
                include_tests=params.include_tests,
                exclude_set=params.exclude_set,
            ):
                continue
            fp: Path = root / rel
            try:
                resolved: Path = fp.resolve()
                if not resolved.is_relative_to(root):
                    logger.warning("skipping indexed path outside root: %s", rel)
                    continue
                if not resolved.is_file():
                    continue
            except OSError as exc:
                logger.warning("stat failed for %s: %s", rel, exc)
                continue
            # Re-normalize rel against the resolved path (defense against
            # symlink swap during iteration).
            rel = str(resolved.relative_to(root)).replace("\\", "/")
            matched_files.append(rel)
            if rel in precomputed:
                fm_list = precomputed[rel]
                if fm_list:
                    per_file_matches[rel] = fm_list
                    match_counts[rel] = len(fm_list)
                continue
            if need_content:
                text = self._read_text_for_match(fp, read_cap)
                fms, cnt = self._scan_file_matches(
                    text,
                    needle,
                    case_sensitive=params.case_sensitive,
                    output_mode=params.output_mode,
                )
                if fms:
                    per_file_matches[rel] = fms
                if cnt:
                    match_counts[rel] = cnt
            if len(matched_files) >= params.limit and params.output_mode in ("files", "counts"):
                truncated = True
                break
        return matched_files, match_counts, per_file_matches, truncated

    def _format_hits(
        self,
        hits: list[tuple[str, float]],
        *,
        params: SearchParams,
        root: Path,
        method: str,
        result: SearchResult,
        match_counts_override: dict[str, int] | None = None,
        per_file_matches_override: dict[str, list[tuple[int, str]]] | None = None,
    ) -> SearchResult:
        result.method = method
        needle = params.query if params.case_sensitive else params.query.lower()
        precomputed = per_file_matches_override or {}

        matched_files, match_counts, per_file_matches, truncated = self._collect_matches(
            hits,
            params,
            root,
            needle,
            precomputed,
        )

        if match_counts_override:
            for k, v in match_counts_override.items():
                match_counts[k] = v
            for rel in match_counts_override:
                if rel not in matched_files:
                    matched_files.append(rel)

        result.total_bytes = self._compute_total_bytes(root, matched_files)

        if params.output_mode == "files":
            result.files = self._build_files_output(matched_files, per_file_matches, match_counts, params.limit)
            result.returned = len(result.files)
        elif params.output_mode == "matches":
            result.matches, extra_trunc = self._build_matches_output(
                root,
                matched_files,
                per_file_matches,
                context_lines=params.context_lines,
                limit=params.limit,
                max_file_size=params.max_file_size,
            )
            result.returned = len(result.matches)
            truncated = truncated or extra_trunc
        elif params.output_mode == "regions":
            result.regions, extra_trunc = self._build_regions_output(
                root,
                matched_files,
                per_file_matches,
                context_lines=params.context_lines,
                limit=params.limit,
                max_file_size=params.max_file_size,
            )
            result.returned = len(result.regions)
            truncated = truncated or extra_trunc
        elif params.output_mode == "counts":
            result.counts = self._build_counts_output(matched_files, match_counts, params.limit)
            result.returned = len(result.counts)
        else:
            raise ValueError(f"unknown output_mode: {params.output_mode}")

        result.truncated = result.truncated or truncated
        return result


__all__ = [
    "BINARY_SNIFF_BYTES",
    "MAX_CONTENT_BYTES_INDEXED",
    "REFRESH_THROTTLE_SECONDS",
    "SCHEMA_VERSION",
    "SNIPPET_MAX_BYTES",
    "SearchIndex",
    "SearchParams",
    "SearchResult",
    "SearchStats",
    "_bm25_tokenize",
]
