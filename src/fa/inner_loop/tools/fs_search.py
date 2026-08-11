"""Unified content/path search tool (replaces fs_grep, fs_instant_grep, fs_glob).

S14b.1: single discovery tool ``fs_search`` combining FTS5 BM25, trigram
substring index, and a streaming Python-walk fallback. Four output modes:

* files    (default) - paths with match_count + short first-match snippet.
* matches  - line-level matches with before/after context lines.
* regions  - adjacent matches grouped into contiguous snippets.
* counts   - per-path match counts only.

Indexing is lazy (first call), mtime/size-incremental thereafter.
Fail-degraded: any DB/index/search error is caught, logged, and falls
back to streaming walk (INV-S14b-2).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fa.inner_loop.registry import ToolResult, ToolSpec

if TYPE_CHECKING:
    from fa.memory.search_index import SearchIndex, SearchParams

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (CT-1, R-14)
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 20
HARD_MAX_LIMIT = 50
DEFAULT_CONTEXT_LINES = 1
HARD_MAX_CONTEXT_LINES = 5
DEFAULT_MAX_FILE_SIZE = 200_000
MAX_RESPONSE_BYTES = 30_000

_OUTPUT_KEYS = ("files", "matches", "regions", "counts")

VALID_OUTPUT_MODES = frozenset({"files", "matches", "regions", "counts"})
VALID_ORDERS = frozenset({"bm25", "path", "match_count"})

_TOOL_DESCRIPTION = """\
Search workspace files by content or path. Single unified discovery tool.

Output modes (pick exactly one):
  * "files"   (DEFAULT) - return paths only with match_count + a short
              first-match snippet. Most token-efficient. Use first.
  * "regions" - group nearby matches into contiguous windows with context
              lines (best for reading code without a follow-up read_file).
  * "matches" - individual matching lines with before/after context. Use
              this when you need exact line numbers (e.g. for edit_file).
  * "counts"  - per-path match counts (fast distribution overview).

Parameters:
  query           (required, string) - search terms. Multiple bare words
                  are implicit-AND (ranked BM25). A trailing "*" is the
                  prefix operator ("auth*" matches "auth", "authenticate").
                  Surround phrases with double quotes for exact-phrase
                  search ('"hello world"'). Literal substring matching is
                  used for regex/case-sensitive modes and as a final
                  trigram fallback.
  regex           (bool, default false) - interpret query as a Python
                  regular expression. Bypasses the FTS index (uses the
                  streaming walk) so prefer literal queries for speed.
  case_sensitive  (bool, default false) - case-sensitive matching. When
                  true, bypasses the FTS index and uses streaming walk.
  glob            (string, optional) - POSIX glob filter applied to
                  relative paths. "**" matches zero or more directories
                  ("src/**/*.py" matches files at any depth under src/);
                  "*" matches within one directory segment. A bare
                  "*.py" (no "/") matches that basename at any depth,
                  like ripgrep. Examples: "*.md", "src/**/*.py",
                  "tests/**/test_*.py".
  path            (string, default ".") - subdirectory to search under,
                  relative to the workspace root. Must not escape root
                  (enforced server-side).
  types           (list of strings, optional) - RESERVED for future
                  blackboard artifact-type filter; accepted and ignored
                  with a notice in v1.
  include_tests   (bool, default true) - include files under tests/.
  exclude_dirs    (list of strings, optional) - additional directory
                  basenames to exclude (union with the built-in set:
                  ".git", "node_modules", ".venv", "__pycache__",
                  ".fa", ...). Excludes apply uniformly across BM25,
                  trigram, and python-walk.
  max_file_size   (int, default 200000, max 1000000) - skip files larger
                  than this (bytes).
  output_mode     ("files"|"matches"|"regions"|"counts", default "files").
  context_lines   (int, default 1, clamped to 0..5) - lines of context
                  before/after each match (for "matches" and "regions").
  limit           (int, default 20, clamped to 1..50) - max returned
                  entries (files/matches/regions/counts).
  order           ("bm25"|"path"|"match_count", default "bm25") - result
                  ordering. Currently "bm25" (best-effort relevance) is
                  the primary path; other orders fall back to insertion
                  order in v1.

Hard rules:
  * Never invoke raw grep/rg/find/ag via fs_run_bash for discovery - use
    fs_search; it respects .gitignore, enforces token caps and provenance.
  * Start with output_mode="files" and a narrow path/glob; only escalate
    to "matches"/"regions" once you know which files are relevant.
  * If fs_search returns no results but you believe the content exists,
    try a shorter query (substring matching works on any fragment).
"""

_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "minLength": 1,
            "description": ("Search terms (literal substring, or regex if regex=true)."),
        },
        "regex": {"type": "boolean", "default": False},
        "case_sensitive": {"type": "boolean", "default": False},
        "glob": {"type": ["string", "null"], "default": None},
        "path": {"type": "string", "default": "."},
        "types": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "default": None,
            "description": ("Reserved for future artifact-type filter; ignored in v1."),
        },
        "include_tests": {"type": "boolean", "default": True},
        "exclude_dirs": {
            "type": ["array", "null"],
            "items": {"type": "string"},
            "default": None,
        },
        "max_file_size": {
            "type": "integer",
            "default": DEFAULT_MAX_FILE_SIZE,
            "minimum": 1,
        },
        "output_mode": {
            "type": "string",
            "enum": sorted(VALID_OUTPUT_MODES),
            "default": "files",
        },
        "context_lines": {
            "type": "integer",
            "default": DEFAULT_CONTEXT_LINES,
            "minimum": 0,
        },
        "limit": {"type": "integer", "default": DEFAULT_LIMIT, "minimum": 1},
        "order": {
            "type": "string",
            "enum": sorted(VALID_ORDERS),
            "default": "bm25",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Parameter parsing helpers (pure functions - easy to test)
# ---------------------------------------------------------------------------


def _clamp_int(
    value: Any,
    lo: int,
    hi: int,
    default: int,
    warnings: list[str],
    label: str,
) -> int:
    """Coerce value to int within [lo, hi]; default on invalid. Appends warning."""
    if value is None:
        return default
    try:
        n = int(value)
    except (TypeError, ValueError):
        warnings.append(f"{label} invalid ({value!r}); using default {default}")
        return default
    if n < lo:
        warnings.append(f"{label} clamped from {n} to minimum {lo}")
        return lo
    if n > hi:
        warnings.append(f"{label} clamped from {n} to hard cap {hi}")
        return hi
    return n


def _parse_bool(data: Mapping[str, object], key: str, default: bool) -> bool:
    val = data.get(key, default)
    return bool(val)


def _parse_str_enum(
    data: Mapping[str, object],
    key: str,
    default: str,
    valid: frozenset[str],
    label: str,
) -> tuple[str, str | None]:
    """Return (value, error_message). error_message is None on success."""
    raw = data.get(key, default)
    if raw is None:
        raw = default
    if not isinstance(raw, str) or raw not in valid:
        return default, f"{label} must be one of {sorted(valid)}, got {raw!r}"
    return raw, None


def _parse_glob(data: Mapping[str, object]) -> tuple[str | None, str | None]:
    glob_pat = data.get("glob")
    if glob_pat is None:
        return None, None
    if not isinstance(glob_pat, str):
        return None, (f"glob must be a string or null, got {type(glob_pat).__name__}")
    if glob_pat == "":
        return None, None
    return glob_pat, None


def _parse_path(data: Mapping[str, object]) -> tuple[str, str | None]:
    subpath = data.get("path", ".") or "."
    if not isinstance(subpath, str):
        return ".", f"path must be a string, got {type(subpath).__name__}"
    return subpath, None


def _parse_exclude_dirs(
    data: Mapping[str, object],
) -> tuple[list[str] | None, str | None]:
    raw = data.get("exclude_dirs")
    if raw is None:
        return None, None
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        return None, "exclude_dirs must be a list of strings"
    return list(raw), None


def _resolve_subdir(root: Path, subpath: str | None) -> Path:
    """Resolve ``subpath`` under ``root``; raise ``PermissionError`` on escape.

    Uses :meth:`pathlib.Path.is_relative_to` on the fully-resolved paths
    (Python 3.9+, available per ``requires-python >= 3.13``). This
    correctly rejects sibling-prefix attacks (e.g. ``root="/tmp/ws"``,
    ``subpath="../ws-secret"``), case-insensitive filesystems, and
    symlinks that resolve outside the root — all of which a naive
    ``str.startswith`` check misses.

    Raises ``PermissionError`` (not ``ValueError``) so ``_handle`` can
    map it to a structured ``path_escape`` ToolResult rather than a
    generic 500. The ``from None`` suppresses a confusing exception
    chain in the user-facing error.

    Non-existent subpaths are NOT treated as escape: ``resolve()``
    returns a syntactic path, downstream ``is_file()``/``is_dir()``
    checks (via ``iter_searchable_files``) naturally yield zero hits,
    matching ripgrep semantics.
    """
    if not subpath:
        subpath = "."
    root_resolved: Path = root.resolve()
    subdir: Path = (root_resolved / subpath).resolve()
    if not subdir.is_relative_to(root_resolved):
        raise PermissionError(f"path escapes workspace root: {subpath}") from None
    return subdir


# ---------------------------------------------------------------------------
# Index lifecycle
# ---------------------------------------------------------------------------


class _IndexHolder:
    """Holds a lazily-created SearchIndex singleton for the process."""

    def __init__(self, db_path: Path) -> None:
        self._db = db_path
        self._index: SearchIndex | None = None
        self._indexed: bool = False

    def get(self) -> SearchIndex:
        if self._index is None:
            from fa.memory.search_index import SearchIndex

            self._index = SearchIndex(self._db)
        return self._index

    def close(self) -> None:
        if self._index is not None:
            try:
                self._index.close()
            except Exception:
                logger.debug("error closing SearchIndex", exc_info=True)
            self._index = None


def _ensure_index(
    holder: _IndexHolder,
    root: Path,
    max_file_size: int,
    warnings: list[str],
) -> dict[str, int] | None:
    """Lazily build/refresh the FTS index.

    Called on EVERY fs_search invocation. ``SearchIndex.ensure_indexed``
    is responsible for the fast canary-check / throttle path (steady-
    state cost is a few ``stat()`` calls), so this wrapper always
    delegates. If the index is unavailable it stays on the streaming-
    walk fallback for the lifetime of the process (matching the
    fail-degraded contract INV-HARDEN-5).

    Returns a stats dict suitable for embedding in the tool result, or
    ``None`` when the index is unavailable. ``holder._indexed`` reflects
    whether the most recent call succeeded and the index can be used
    for the upcoming search.
    """
    try:
        index = holder.get()
    except Exception as exc:  # noqa: BLE001 - INV-HARDEN-5 fail-degraded
        logger.warning("fs_search index unavailable: %s", exc)
        warnings.append(f"FTS index unavailable ({exc}); using streaming fallback")
        holder._indexed = False
        return None
    try:
        stats = index.ensure_indexed(
            root,
            # Always index the superset of indexable files (including
            # tests/ and default-excluded directories). Query-time
            # filtering is applied by _passes_filters so the index can
            # serve any future narrower query without rebuilding.
            include_tests=True,
            max_file_size=max_file_size,
        )
        holder._indexed = True
        return {
            "indexed": stats.indexed,
            "updated": stats.updated,
            "skipped": stats.skipped,
            "errors": stats.errors,
            "total_candidates": stats.total_candidates,
        }
    except Exception as exc:  # noqa: BLE001 - INV-HARDEN-5 fail-degraded
        logger.warning("fs_search indexing failed: %s", exc)
        warnings.append(f"index build/refresh failed ({exc}); using streaming fallback")
        # Mark unavailable so subsequent calls go straight to walk.
        holder._indexed = False
        return None


# ---------------------------------------------------------------------------
# Search execution
# ---------------------------------------------------------------------------


def _subdir_rel(root: Path, subdir: Path) -> str:
    if subdir == root:
        return ""
    return str(subdir.relative_to(root)).replace("\\", "/") + "/"


def _do_indexed_search(
    holder: _IndexHolder,
    params: SearchParams,
    root: Path,
    subdir: Path,
) -> Any:
    """Run search against the live index."""
    index = holder.get()
    subpath_arg = "." if subdir == root else str(subdir.relative_to(root))
    return index.search(params, root=root, subpath=subpath_arg)


def _do_fallback_search(
    db: Path,
    params: SearchParams,
    root: Path,
    subdir: Path,
    warnings: list[str],
) -> Any:
    """Streaming walk fallback when index is unavailable."""
    from fa.memory.search_index import SearchIndex, SearchResult

    sr: Any = SearchResult(query=params.query, method="literal_fallback")
    try:
        tmp_index = SearchIndex(db)
        try:
            sr = tmp_index._search_python_walk(
                params=params,
                root=root,
                _subdir=subdir,
                result=sr,
                as_regex=params.regex,
            )
        finally:
            tmp_index.close()
    except Exception as exc:  # noqa: BLE001 - INV-HARDEN-5 fail-degraded
        logger.warning("fs_search streaming fallback failed: %s", exc)
        warnings.append(f"streaming fallback error: {exc}")
    return sr


def _output_for_mode(result: dict[str, Any], sr: Any, mode: str) -> None:
    """Populate mode-specific result field from SearchResult."""
    if mode == "files":
        result["files"] = sr.files
    elif mode == "matches":
        result["matches"] = sr.matches
    elif mode == "regions":
        result["regions"] = sr.regions
    elif mode == "counts":
        result["counts"] = sr.counts


def _estimate_size(obj: Any) -> int:
    try:
        return len(json.dumps(obj, ensure_ascii=False, default=str))
    except Exception:  # noqa: BLE001 - INV-S14b-2 fail-degraded
        return len(repr(obj))


def _enforce_response_cap(result: dict[str, Any]) -> None:
    """Mutate result in-place to stay under MAX_RESPONSE_BYTES."""
    while _estimate_size(result) > MAX_RESPONSE_BYTES and result.get("returned", 0) > 1:
        popped = False
        for key in _OUTPUT_KEYS:
            lst = result.get(key)
            if lst and len(lst) > 1:
                lst.pop()
                result["returned"] = sum(len(result.get(k, []) or []) for k in _OUTPUT_KEYS)
                result["truncated"] = True
                result.setdefault("warnings", []).append(f"response truncated to {MAX_RESPONSE_BYTES}-byte cap")
                popped = True
                break
        if not popped:
            break


def _build_summary(query: str, mode: str, method: str, result: dict[str, Any]) -> str:
    n = int(result.get("returned", 0))
    truncated = " (truncated)" if result.get("truncated") else ""
    mode_noun = {
        "files": "files",
        "matches": "matches",
        "regions": "regions",
        "counts": "paths",
    }.get(mode, "results")
    return f"fs_search[{mode}] {n} {mode_noun} for {query!r} via {method}{truncated}"


# ---------------------------------------------------------------------------
# Handler (thin - delegates to helpers)
# ---------------------------------------------------------------------------


def _build_search_params(
    *,
    query: str,
    output_mode: str,
    glob_pat: str | None,
    include_tests: bool,
    exclude_dirs: list[str] | None,
    max_file_size: int,
    context_lines: int,
    limit: int,
    order: str,
    regex: bool,
    case_sensitive: bool,
) -> SearchParams:
    """Construct a :class:`SearchParams` from parsed user input.

    Centralized in one place so the two code paths (indexed and
    fallback) receive an identical parameter object — the whole point
    of the dataclass is to kill the 9-kwarg copy/paste that pylint
    R0801 was flagging.
    """
    from fa.memory.search_index import SearchParams  # local to avoid import cycle

    exclude_set: frozenset[str] = frozenset(exclude_dirs) if exclude_dirs else frozenset()
    return SearchParams(
        query=query,
        output_mode=output_mode,
        glob_pat=glob_pat,
        # subdir_rel is resolved by SearchIndex.search() after validating
        # subpath against root; we pass "" here and let that layer set it.
        subdir_rel="",
        include_tests=include_tests,
        exclude_set=exclude_set,
        max_file_size=max_file_size,
        context_lines=context_lines,
        limit=limit,
        regex=regex,
        case_sensitive=case_sensitive,
        order=order,
    )


def _handle(
    params: Mapping[str, object],
    holder: _IndexHolder,
    root: Path,
    db: Path,
) -> ToolResult:
    warnings_list: list[str] = []

    data = dict(params)

    # query
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        return ToolResult.fail(
            "invalid_params",
            "query must be a non-empty string",
            retryable=True,
        )
    query = query.strip()

    # bools
    regex = _parse_bool(data, "regex", False)
    case_sensitive = _parse_bool(data, "case_sensitive", False)
    include_tests = _parse_bool(data, "include_tests", True)

    # enums
    output_mode, err = _parse_str_enum(data, "output_mode", "files", VALID_OUTPUT_MODES, "output_mode")
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)
    order, err = _parse_str_enum(data, "order", "bm25", VALID_ORDERS, "order")
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)

    # ints (R-14 clamping)
    context_lines = _clamp_int(
        data.get("context_lines"),
        lo=0,
        hi=HARD_MAX_CONTEXT_LINES,
        default=DEFAULT_CONTEXT_LINES,
        warnings=warnings_list,
        label="context_lines",
    )
    limit = _clamp_int(
        data.get("limit"),
        lo=1,
        hi=HARD_MAX_LIMIT,
        default=DEFAULT_LIMIT,
        warnings=warnings_list,
        label="limit",
    )
    max_file_size = _clamp_int(
        data.get("max_file_size"),
        lo=1,
        hi=1_000_000,
        default=DEFAULT_MAX_FILE_SIZE,
        warnings=warnings_list,
        label="max_file_size",
    )

    # glob
    glob_pat, err = _parse_glob(data)
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)

    # path
    subpath, err = _parse_path(data)
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)
    try:
        subdir = _resolve_subdir(root, subpath)
    except PermissionError as exc:
        return ToolResult.fail("path_escape", str(exc), retryable=True)

    # exclude_dirs
    exclude_dirs, err = _parse_exclude_dirs(data)
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)

    # types (R-15: reserved, accepted+ignored)
    note: str | None = None
    if data.get("types") is not None:
        note = "types parameter is reserved for future artifact-type filtering; ignored in v1."

    # Build one immutable carrier; both search paths consume the same object.
    search_params = _build_search_params(
        query=query,
        output_mode=output_mode,
        glob_pat=glob_pat,
        include_tests=include_tests,
        exclude_dirs=exclude_dirs,
        max_file_size=max_file_size,
        context_lines=context_lines,
        limit=limit,
        order=order,
        regex=regex,
        case_sensitive=case_sensitive,
    )

    # lazy index + search
    index_stats_dict = _ensure_index(holder, root, max_file_size, warnings_list)

    try:
        if holder._indexed:
            sr = _do_indexed_search(holder, search_params, root, subdir)
        else:
            sr = _do_fallback_search(db, search_params, root, subdir, warnings_list)
    except Exception as exc:
        logger.warning("fs_search unexpected error: %s", exc, exc_info=True)
        return ToolResult.fail(
            "search_failed",
            f"internal error in fs_search: {exc}",
            retryable=False,
        )

    # assemble result dict
    result: dict[str, Any] = {
        "query": query,
        "method": sr.method,
        "returned": sr.returned,
        "truncated": bool(sr.truncated),
        "total_bytes": int(sr.total_bytes),
        "index_stats": index_stats_dict,
    }
    _output_for_mode(result, sr, output_mode)
    if note:
        result["note"] = note
    if warnings_list:
        result["warnings"] = warnings_list
    elif sr.warnings:
        result["warnings"] = list(sr.warnings)

    _enforce_response_cap(result)

    summary = _build_summary(query, output_mode, sr.method, result)
    return ToolResult.ok(summary, result=result)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_fs_search_tool(db_path: Path, workspace_root: Path) -> ToolSpec:
    """Build the fs_search ToolSpec bound to a workspace and FTS DB path."""
    root = Path(workspace_root).resolve()
    db = Path(db_path)
    holder = _IndexHolder(db)

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            return _handle(params, holder, root, db)
        except Exception as exc:
            logger.warning("fs_search top-level error: %s", exc, exc_info=True)
            return ToolResult.fail(
                "search_failed",
                f"internal error in fs_search: {exc}",
                retryable=False,
            )

    return ToolSpec(
        name="fs_search",
        description=_TOOL_DESCRIPTION,
        input_schema=_INPUT_SCHEMA,
        permission="read",
        handler=handler,
        tags=("fs", "search", "discovery"),
        max_context_bytes=MAX_RESPONSE_BYTES,
    )


__all__ = [
    "DEFAULT_CONTEXT_LINES",
    "DEFAULT_LIMIT",
    "DEFAULT_MAX_FILE_SIZE",
    "HARD_MAX_CONTEXT_LINES",
    "HARD_MAX_LIMIT",
    "MAX_RESPONSE_BYTES",
    "VALID_ORDERS",
    "VALID_OUTPUT_MODES",
    "build_fs_search_tool",
]
