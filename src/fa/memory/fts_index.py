"""
Instant Grep — SQLite FTS5 trigram index, Cursor-like instant grep
ADR-14, Gap 4 skill globs + Gap instant grep

Prior art: Cursor instant grep 3 months prod N-gram DB, Mechanical Wiki ADR-3/4 FTS5
SQLite FTS5 tokenize='trigram' → substring search "auth" finds "authentication", "AuthMiddleware"
0 external deps, sqlite3 stdlib, Python 3.13 has fts5 built-in
Progressive disclosure: llms.txt map always injected (short summaries), full file on demand via read
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
import warnings
from pathlib import Path

logger = logging.getLogger(__name__)

# Single source of truth for excluded dirs — used by glob, grep, instant_grep fallback,
# fts_index, and search_index/_safe_walk.py. Extend via EXTRA_EXCLUDE_DIRS in _safe_walk,
# not here (keep this set stable for backward compatibility).
# §I-S14b-4: canonical exclude set — single source of truth for walker pruning in _safe_walk.
EXCLUDE_DIRS = {
    ".git",
    ".fa",
    "node_modules",
    ".venv",
    "__pycache__",
    ".gremlins_cache",
    "sessions",
    "dist",
    "build",
    ".mypy_cache",
    ".tox",
    ".pytest_cache",
    ".ruff_cache",
    ".nox",
    "htmlcov",
}


class InstantGrepIndex:
    """
    N-gram trigram index for instant grep.
    Index: path, content (first 10k chars)
    Search: MATCH query → list paths <50ms, substring search
    """

    def __init__(self, db_path: Path):
        warnings.warn(
            "InstantGrepIndex is deprecated; use fa.memory.search_index.SearchIndex instead. "
            "InstantGrepIndex will be removed in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        try:
            self.conn.execute(
                """
              CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
              USING fts5(path, content, tokenize='trigram')
            """
            )
        except sqlite3.OperationalError:
            self.conn.execute(
                """
              CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
              USING fts5(path, content, tokenize='porter')
            """
            )
        try:
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS fts_meta(
                path TEXT PRIMARY KEY,
                mtime REAL,
                size INTEGER
            )"""
            )
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
            pass
        self.conn.commit()

    def _should_full_reindex(self) -> bool:
        """Check if DB older than 24h or empty — needs full reindex (precaution)."""
        try:
            if not self.db_path.exists():
                return True
            mtime = self.db_path.stat().st_mtime
            if time.time() - mtime > 86400:
                logger.warning(f"FTS DB older than 24h (mtime {mtime}), full reindex")
                return True
            # Empty DB -> full reindex precaution (stale meta may cause skip)
            count = self.conn.execute("SELECT COUNT(*) FROM files_fts").fetchone()[0]
            if count == 0:
                logger.warning("FTS DB empty, full reindex as precaution")
                return True
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            logger.warning(f"Failed to check DB staleness: {exc}, full reindex as precaution")
            return True
        return False

    def index_repo(  # noqa: C901 -- complexity from 24h check + pattern matching + mtime + stale cleanup, split into helpers
        self,
        root: Path,
        patterns: tuple[str, ...] = ("*.md", "*.py", "*.ts", "*.js", "*.json", "*.yaml", "*.toml"),
        max_file_size: int = 100_000,
    ) -> None:
        root = Path(root).resolve()

        # 24h reindex check — DELETE both tables if stale
        if self._should_full_reindex():
            try:
                # Only full delete if older than 24h, not if just empty
                # Check again mtime for 24h case
                mtime = self.db_path.stat().st_mtime if self.db_path.exists() else 0
                if time.time() - mtime > 86400:
                    self.conn.execute("DELETE FROM files_fts")
                    self.conn.execute("DELETE FROM fts_meta")
                    self.conn.commit()
                    logger.warning("FTS DB older than 24h, cleared for full reindex")
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                logger.warning(f"Failed to clear stale DB: {exc}")

        indexed_paths: set[str] = set()

        # Single walk, not per-pattern rglob, to avoid double scanning
        for dirpath, dirnames, filenames in os.walk(root):
            # Prune excluded dirs in-place
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                # Quick pattern check: does fname match any of patterns? Use fnmatch
                # For simplicity, check if file ends with pattern suffix or fnmatch
                import fnmatch

                matched_pattern = False
                for pat in patterns:
                    # pat like "*.md" or "*.py"
                    if fnmatch.fnmatch(fname, pat) or fnmatch.fnmatch(str(fpath.relative_to(root)), pat):
                        matched_pattern = True
                        break
                if not matched_pattern:
                    continue

                if not fpath.is_file():
                    continue
                try:
                    st = fpath.stat()
                except OSError:
                    continue
                if st.st_size > max_file_size:
                    continue
                # Extra safety: check parts still not in exclude (for nested)
                if any(part in EXCLUDE_DIRS for part in fpath.parts):
                    continue

                rel = str(fpath.relative_to(root))
                indexed_paths.add(rel)

                try:
                    cur = self.conn.execute("SELECT mtime FROM fts_meta WHERE path=?", (rel,)).fetchone()
                    if cur and cur[0] == st.st_mtime:
                        continue
                except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                    pass

                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")[:10000]
                    self.conn.execute("DELETE FROM files_fts WHERE path=?", (rel,))
                    self.conn.execute(
                        "INSERT INTO files_fts(path, content) VALUES (?, ?)",
                        (rel, content),
                    )
                    self.conn.execute(
                        "INSERT OR REPLACE INTO fts_meta(path, mtime, size) VALUES (?, ?, ?)",
                        (rel, st.st_mtime, st.st_size),
                    )
                except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                    continue

        # Stale cleanup: delete entries where file not exists
        try:
            rows = self.conn.execute("SELECT path FROM fts_meta").fetchall()
            for (p,) in rows:
                if p not in indexed_paths:
                    full = root / p
                    if not full.exists():
                        self.conn.execute("DELETE FROM files_fts WHERE path=?", (p,))
                        self.conn.execute("DELETE FROM fts_meta WHERE path=?", (p,))
        except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
            pass
        self.conn.commit()

    def instant_grep(self, query: str, limit: int = 10) -> list[str]:
        escaped = query.replace('"', '""')
        try:
            cursor = self.conn.execute(
                "SELECT path, rank FROM files_fts WHERE files_fts MATCH ? ORDER BY rank LIMIT ?",
                (escaped, limit),
            )
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            cursor = self.conn.execute(
                "SELECT path FROM files_fts WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            )
            return [row[0] for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()


__all__ = ["EXCLUDE_DIRS", "InstantGrepIndex"]
