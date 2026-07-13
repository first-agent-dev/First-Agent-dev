"""
Instant Grep — SQLite FTS5 trigram index, Cursor-like instant grep
ADR-14, Gap 4 skill globs + Gap instant grep

Prior art: Cursor instant grep 3 months prod N-gram DB, Mechanical Wiki ADR-3/4 FTS5
SQLite FTS5 tokenize='trigram' → substring search "auth" finds "authentication", "AuthMiddleware"
0 external deps, sqlite3 stdlib, Python 3.13 has fts5 built-in
Progressive disclosure: llms.txt map always injected (short summaries), full file on demand via read

Design invariant: Must stay below 100k tokens per call (AGENTS.md context-budget discipline)
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import List
# List deprecated, use list, but keep for backward compat


class InstantGrepIndex:
    """
    N-gram trigram index for instant grep.
    Index: path, content (first 10k chars)
    Search: MATCH query → list paths <50ms, substring search
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        # FTS5 trigram for substring search, same as Cursor
        # Note: SQLite must be compiled with FTS5 + trigram tokenizer
        # Python 3.13 default includes FTS5, trigram may need compile option; fallback to porter if not
        try:
            self.conn.execute(
                """
              CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
              USING fts5(path, content, tokenize='trigram')
            """
            )
        except sqlite3.OperationalError:
            # Fallback if trigram not available: use porter
            self.conn.execute(
                """
              CREATE VIRTUAL TABLE IF NOT EXISTS files_fts
              USING fts5(path, content, tokenize='porter')
            """
            )
        # Meta table for mtime tracking + stale cleanup
        try:
            self.conn.execute(
                """CREATE TABLE IF NOT EXISTS fts_meta(
                path TEXT PRIMARY KEY,
                mtime REAL,
                size INTEGER
            )"""
            )
        except Exception:
            pass
        self.conn.commit()

    def index_repo(
        self,
        root: Path,
        patterns: tuple[str, ...] = ("*.md", "*.py", "*.ts", "*.js", "*.json", "*.yaml"),
        max_file_size: int = 100_000,
    ) -> None:
        root = Path(root).resolve()
        indexed_paths: set[str] = set()
        for pattern in patterns:
            for file in root.rglob(pattern):
                if not file.is_file():
                    continue
                try:
                    st = file.stat()
                except OSError:
                    continue
                if st.st_size > max_file_size:
                    continue
                # Skip .git, .fa, node_modules, .venv, __pycache__, sessions
                if any(
                    part
                    in {
                        ".git",
                        ".fa",
                        "node_modules",
                        ".venv",
                        "__pycache__",
                        ".gremlins_cache",
                        "sessions",
                    }
                    for part in file.parts
                ):
                    continue
                rel = str(file.relative_to(root))
                indexed_paths.add(rel)
                # mtime check: skip if unchanged
                try:
                    cur = self.conn.execute(
                        "SELECT mtime FROM fts_meta WHERE path=?", (rel,)
                    ).fetchone()
                    if cur and cur[0] == st.st_mtime:
                        continue
                except Exception:
                    pass
                try:
                    content = file.read_text(encoding="utf-8", errors="ignore")[:10000]
                    # Fix Gap: DELETE then INSERT for FTS5, not INSERT OR REPLACE
                    self.conn.execute("DELETE FROM files_fts WHERE path=?", (rel,))
                    self.conn.execute(
                        "INSERT INTO files_fts(path, content) VALUES (?, ?)",
                        (rel, content),
                    )
                    self.conn.execute(
                        "INSERT OR REPLACE INTO fts_meta(path, mtime, size) VALUES (?, ?, ?)",
                        (rel, st.st_mtime, st.st_size),
                    )
                except Exception:
                    continue
        # Stale cleanup: delete entries where file no longer exists
        try:
            rows = self.conn.execute("SELECT path FROM fts_meta").fetchall()
            for (p,) in rows:
                if p not in indexed_paths:
                    full = root / p
                    if not full.exists():
                        self.conn.execute("DELETE FROM files_fts WHERE path=?", (p,))
                        self.conn.execute("DELETE FROM fts_meta WHERE path=?", (p,))
        except Exception:
            pass
        self.conn.commit()

    def instant_grep(self, query: str, limit: int = 10) -> list[str]:
        """
        Instant substring search: "auth" → finds "authentication", "AuthMiddleware"
        Returns list of paths, not content → token efficient (like OpenAI progressive disclosure)
        <50ms even for 100k files, vs ripgrep scan each time
        """
        escaped = query.replace('"', '""')
        try:
            cursor = self.conn.execute(
                "SELECT path, rank FROM files_fts WHERE files_fts MATCH ? ORDER BY rank LIMIT ?",
                (escaped, limit),
            )
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # Fallback to LIKE if FTS fails
            cursor = self.conn.execute(
                "SELECT path FROM files_fts WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            )
            return [row[0] for row in cursor.fetchall()]

    def close(self) -> None:
        self.conn.close()
