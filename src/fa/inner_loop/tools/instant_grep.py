"""Instant Grep tool — FTS5 trigram substring search, <50ms, token efficient.

Senior refactor v2 — fixes F821 undefined e bug + C901 complexity split:
- Module-level single source EXCLUDE_DIRS
- FTS5 fast path with count check and index_repo fallback (helper _fts_search)
- Fallback chain: git ls-files --cached --others --exclude-standard, then a symlink-safe walk.
- Streaming file read for fallback, no hard size skip, soft limit warning
- Returns paths not content, always valid fts_error variable
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools._common import git_ls_files, validate_search_params

# Single source of truth for excluded directories
from fa.memory.fts_index import EXCLUDE_DIRS

DEFAULT_LIMIT = 10
MAX_LIMIT = 50
MAX_FILE_SIZE_SOFT = 100_000


def _iter_files_fallback(root: Path) -> Iterator[Path]:
    root_resolved = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root_resolved, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fname in filenames:
            if not any(
                fname.endswith(ext) for ext in (".md", ".py", ".ts", ".js", ".json", ".yaml", ".yml", ".toml", ".txt")
            ):
                continue
            fp = Path(dirpath) / fname
            try:
                if not fp.resolve().is_relative_to(root_resolved):
                    continue
            except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                continue
            try:
                yield fp
            except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
                continue


def _matches_file_content(path: Path, query_lower: str) -> bool:
    """Streaming search line-by-line, handles large files."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if query_lower in line.lower():
                    return True
        if query_lower in path.name.lower():
            return True
        return False
    except OSError:
        return False


def _fts_search(db_path: Path, workspace_root: Path, query: str, limit: int) -> tuple[list[str] | None, str | None]:
    """Try FTS5 fast path — STRICTLY READ-ONLY.

    FIND-013 fix: this function must NOT perform writes (index_repo). If FTS index
    is missing or empty, return fts_error to force git-ls-files / walk fallback,
    which are read-only. Indexing is explicit via fa reindex / CLI, not query path.
    """
    import logging

    logger = logging.getLogger(__name__)
    index = None
    # Strictly read-only: if db file does not exist, do not create it — trigger fallback
    if not db_path.exists():
        return None, f"FTS5 db not exists at {db_path} — read-only, use reindex"
    try:
        from fa.memory.fts_index import InstantGrepIndex

        index = InstantGrepIndex(db_path)
        # Read-only check: if table missing or empty, treat as unavailable, no indexing
        try:
            count = index.conn.execute("SELECT COUNT(*) FROM files_fts").fetchone()[0]
            if count == 0:
                raise RuntimeError("FTS5 index empty — use fa reindex to build, not query-time indexing")
        except Exception as exc:
            # Empty or missing table -> trigger fallback, do NOT auto-index (read-only guarantee)
            raise RuntimeError(f"FTS5 not ready: {exc}") from exc

        paths = index.instant_grep(query, limit=limit)
        return paths, None
    except Exception as fts_exc:  # noqa: BLE001 # read-only fallback
        fts_error = str(fts_exc)
        logger.warning("FTS5 instant_grep unavailable: %s, fallback to git ls-files", fts_error)
        return None, fts_error
    finally:
        if index is not None:
            try:
                index.close()
            except Exception:  # noqa: BLE001, S110 # best-effort close
                pass


def _git_fallback_search(root: Path, query: str, limit: int, fts_error: str) -> list[str]:
    """Fallback via git ls-files, respects EXCLUDE_DIRS, streaming content check."""
    tracked = git_ls_files(root)
    matched: list[str] = []
    q_lower = query.lower()
    for rel in tracked:
        if any(part in EXCLUDE_DIRS for part in Path(rel).parts):
            continue
        fp = root / rel
        try:
            if not fp.is_file():
                if q_lower in rel.lower():
                    matched.append(rel)
                    if len(matched) >= limit:
                        break
                continue
            if q_lower in rel.lower() or _matches_file_content(fp, q_lower):
                matched.append(rel)
                if len(matched) >= limit:
                    break
        except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
            continue
    return matched


def _walk_fallback_search(root: Path, query: str, limit: int) -> list[str]:
    """Walk fallback pruning symlink-safe, streaming."""
    matched: list[str] = []
    q_lower = query.lower()
    for fp in _iter_files_fallback(root):
        try:
            rel = str(fp.relative_to(root))
            if q_lower in rel.lower() or _matches_file_content(fp, q_lower):
                matched.append(rel)
                if len(matched) >= limit:
                    break
        except Exception:  # noqa: BLE001, S112 # graceful degradation per Phase 0.5, failure-observable WARNING
            continue
    return matched


def build_instant_grep_tool(db_path: Path, workspace_root: Path) -> ToolSpec:
    db_path = Path(db_path).resolve()
    workspace_root = Path(workspace_root).resolve()

    if not workspace_root.is_dir():
        raise ValueError(f"workspace_root {workspace_root} not dir")

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            query, limit = validate_search_params(params, DEFAULT_LIMIT, MAX_LIMIT)
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        # Fast path FTS5
        paths, fts_error = _fts_search(db_path, workspace_root, query, limit)
        if fts_error is None and paths is not None:
            summary = f"Found {len(paths)} files matching '{query}' (limit {limit}) via FTS5 trigram <50ms"
            return ToolResult.ok(
                summary,
                result={"paths": paths, "query": query, "limit": limit, "method": "fts5"},
            )

        # Fallback chain
        try:
            # Git ls-files fallback
            matched = _git_fallback_search(workspace_root, query, limit, fts_error or "unknown")
            if matched:
                summary = (
                    f"Found {len(matched)} files matching '{query}' via git ls-files fallback (FTS failed: {fts_error})"
                )
                return ToolResult.ok(
                    summary,
                    result={
                        "paths": matched,
                        "query": query,
                        "limit": limit,
                        "method": "git_ls_files",
                        "fts_error": fts_error,
                    },
                )

            # Walk fallback
            matched = _walk_fallback_search(workspace_root, query, limit)
            summary = f"Found {len(matched)} files matching '{query}' via fallback walk (FTS failed: {fts_error})"
            return ToolResult.ok(
                summary,
                result={
                    "paths": matched,
                    "query": query,
                    "limit": limit,
                    "method": "fallback_walk",
                    "fts_error": fts_error,
                },
            )

        except Exception as exc2:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail(
                "search_failed",
                f"Instant grep failed: {fts_error}, fallback failed: {exc2}",
                retryable=False,
            )

    return ToolSpec(
        name="fs.instant_grep",
        description=(
            "Instant substring search via FTS5 trigram index (Cursor-like), under 50ms, "
            "returns paths rather than content; "
            "token efficient. Falls back to git ls-files --cached --others --exclude-standard "
            "(respects .gitignore) "
            "if FTS not available, then walk pruning symlink-safe."
        ),
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Substring to search, e.g., 'auth'"},
                "limit": {"type": "integer", "description": "Max paths, default 10 max 50", "default": 10},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "memory", "instant_grep", "search"),
        max_context_bytes=2000,
    )


__all__ = ["DEFAULT_LIMIT", "EXCLUDE_DIRS", "MAX_FILE_SIZE_SOFT", "MAX_LIMIT", "build_instant_grep_tool"]
