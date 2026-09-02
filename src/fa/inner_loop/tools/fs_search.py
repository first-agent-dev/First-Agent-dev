"""Unified content/path search tool (replaces fs_grep, fs_instant_grep, fs_glob).

S14b.1: single discovery tool ``fs_search`` combining FTS5 BM25, trigram
substring index, and a streaming Python-walk fallback. S12.7 §A6 v7: three
output modes (regions folded into matches; counts removed):

* files    (default) - {path, lines, bytes} rows + skipped_large_files.
* outline  - structural map of ONE py/md file (symbols/sections, exact ranges).
* matches  - merged grep regions (N:/N- marked, 1 ctx line, byte-bounded).

Indexing is lazy (first call), mtime/size-incremental thereafter.
Fail-degraded: any DB/index/search error is caught, logged, and falls
back to streaming walk (INV-S14b-2).
"""

from __future__ import annotations

import atexit
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fa.inner_loop.registry import DEFAULT_TOOL_CONTEXT_BYTES, ToolResult, ToolSpec
from fa.inner_loop.tools.outline import (
    OUTLINE_DEFAULT_LIMIT,
    OUTLINE_MAX_READ_BYTES,
    OutlineRow,
    fold_markdown,
    fold_python_source,
)

if TYPE_CHECKING:
    from fa.memory.search_index import SearchIndex, SearchParams

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (CT-1, R-14)
# ---------------------------------------------------------------------------

DEFAULT_LIMIT = 20
HARD_MAX_LIMIT = 50
# S12.7 (§A6 v7 / CT2): aligned with the 32_768-byte read budget (S2/S4).
MAX_RESPONSE_BYTES = 32_768

_OUTPUT_KEYS = ("files", "matches")  # S12.7 S7b: regions/counts folded into matches (§A6)

# S12.7 (§A6 v7): 3 modes. regions folded into matches; counts removed.
VALID_OUTPUT_MODES = frozenset({"files", "matches", "outline"})

# S12.7 (§A6 v7 / CT11): removed params stay SCHEMA-ACCEPTED (deprecated) but are
# ignored at runtime — every use gets an observable warning naming the replacement.
_REMOVED_PARAMS: tuple[tuple[str, str], ...] = (
    ("order", "files rows are path-ordered; matches follow relevance"),
    ("include_tests", "to exclude tests, pass exclude_dirs=['tests']"),
    ("glob", "put the pattern in 'path' instead ('**' crosses directories, e.g. path='src/**/*.py')"),
    ("case_sensitive", "search is case-insensitive always; for regex, control casing in the pattern (e.g. '(?i)')"),
    ("max_file_size", "files over the fixed 200_000-byte cap are skipped and reported in skipped_large_files"),
    ("context_lines", "context is fixed at 1 line each side; for more, read the region with fs_read_file"),
)


def _warn_removed_params(data: Mapping[str, object], warnings_list: list[str]) -> None:
    for name, steer in _REMOVED_PARAMS:
        if data.get(name) is not None:
            warnings_list.append(f"param '{name}' is accepted but ignored (S12.7): {steer}")


_TOOL_DESCRIPTION = """\
Search workspace files by content or path. Single unified discovery tool.

Output modes (exactly one; default "files"):
  * "files"   - DISCOVERY. Rows {path, lines, bytes}, ordered by path, plus a
              skipped_large_files count (files over the fixed 200_000-byte cap).
              With a query: files whose content matches. WITHOUT a query: pure
              scope listing (path/exclude_dirs filters apply). Most
              token-efficient — always start here.
              Example: {"output_mode": "files", "path": "src/fa"}.
  * "outline" - STRUCTURE of ONE .py/.md file (path must be a file). Python:
              symbols (kind, name, start_line/end_line incl. decorators,
              depth, signature); Markdown: headings + sections. Rows'
              start_line/end_line paste straight into fs_read_file windows.
              query = optional case-insensitive symbol-name filter.
              Example: {"path": "src/fa/cli.py", "output_mode": "outline",
                        "query": "stats"}.
  * "matches" - GREP. Hits merge into regions when within 2 lines of each
              other; 1 context line per side; hit lines are "N:"-prefixed,
              context lines "N-"-prefixed. Dense regions carry a
              "[...N more hits in lines A-B]" trailer instead of ballooning.
              Rows: {path, start_line, end_line, match_lines, match_count,
              snippet} — read the exact region with fs_read_file.
              Example: {"query": "budget", "output_mode": "matches",
                        "path": "src/**/*.py"}.

Parameters:
  query           (string, optional) - literal substring, CASE-INSENSITIVE
                  always; multiple bare words are implicit-AND (ranked BM25);
                  a trailing "*" is the prefix operator; quoted phrases match
                  exactly. Omit for output_mode="files" (full listing) or
                  "outline" (full table). Required for "matches".
  regex           (bool, default false) - query is a Python regex. Casing is
                  controlled IN THE PATTERN (e.g. "(?i)"); bypasses the FTS
                  index, so prefer literal queries for speed.
  path            (string, default ".") - search root: a literal directory, a
                  literal file (single-file scope), or a glob pattern —
                  "src/**/*.py" matches at any depth under src/; a bare "*.py"
                  (no "/") matches that basename at any depth (ripgrep
                  convention). Must not escape the workspace root.
  exclude_dirs    (list of strings, optional) - extra directory basenames to
                  skip beyond the built-in set (".git", "node_modules",
                  ".venv", "__pycache__", ".fa", ...). This is also how you
                  exclude tests: exclude_dirs=["tests"].
  output_mode     ("files"|"outline"|"matches", default "files").
  limit           (int, default 20, clamped 1..50) - caps rows (files) /
                  regions (matches) / symbols (outline; default 60 there).

Removed knobs (S12.7): order, include_tests, glob, case_sensitive,
max_file_size, context_lines are ACCEPTED BUT IGNORED with a warning — use
path (absorbs glob), exclude_dirs, or fs_read_file for context instead.

Hard rules:
  * Never invoke raw grep/rg/find/ag via fs_run_bash for discovery - use
    fs_search; it respects .gitignore, enforces token caps and provenance.
  * Discovery ladder: files (find candidates) -> outline (map a file; rows
    carry "lines" — a file over ~500 lines pays an outline FIRST) -> matches
    (grep it) -> fs_read_file (read the exact lines). Each step is cheap;
    skipping straight to reading whole files is not.
  * Who references/calls a symbol -> fs_reach (symbol reachability); fs_reach
    and outline are companions: outline shows a file's structure, fs_reach
    traces a symbol's callers/callees.
  * If fs_search returns no results but you believe the content exists,
    try a shorter query (substring matching works on any fragment).
"""

_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        # --- §A6 v7: the locked 6-param surface -------------------------
        "query": {
            "type": "string",
            "minLength": 1,
            "description": (
                "Search terms (literal substring, case-insensitive; or a Python "
                "regex when regex=true). Optional: omit for output_mode='files' "
                "(pure scope listing) or 'outline' (full structural table)."
            ),
        },
        "regex": {
            "type": "boolean",
            "default": False,
            "description": "query is a Python regex; control casing in the pattern, e.g. (?i).",
        },
        "path": {
            "type": "string",
            "default": ".",
            "description": (
                "Search root: literal dir, literal file, or glob pattern "
                "(basename-only patterns match at any depth; '/' anchors)."
            ),
        },
        "exclude_dirs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Extra dir names to skip beyond the built-in set (e.g. ['tests']).",
        },
        "output_mode": {
            "type": "string",
            "enum": sorted(VALID_OUTPUT_MODES),
            "default": "files",
        },
        "limit": {"type": "integer", "default": DEFAULT_LIMIT, "minimum": 1},
        # --- removed (§A6 v7): schema-ACCEPTED for leniency, runtime-IGNORED
        #     with an observable warning (CT11). additionalProperties is False,
        #     so dropping these properties would hard-reject old callers; the
        #     portable profile has no `deprecated` keyword, so removal is
        #     marked via description. -----------------------------------------
        "case_sensitive": {
            "type": "boolean",
            "default": False,
            "description": "Removed (S12.7): search is case-insensitive always; ignored.",
        },
        "glob": {
            "type": "string",
            "description": "Removed (S12.7): put the pattern in 'path' instead; ignored.",
        },
        "include_tests": {
            "type": "boolean",
            "default": True,
            "description": "Removed (S12.7): use exclude_dirs=['tests'] instead; ignored.",
        },
        "max_file_size": {
            "type": "integer",
            "default": 200_000,
            "minimum": 1,
            "description": "Removed (S12.7): fixed 200_000 cap; skips are reported; ignored.",
        },
        "context_lines": {
            "type": "integer",
            "default": 1,
            "minimum": 0,
            "description": "Removed (S12.7): context fixed at 1 line each side; ignored.",
        },
        "order": {
            "type": "string",
            "enum": ["bm25", "path", "match_count"],
            "default": "bm25",
            "description": "Removed (S12.7): ignored.",
        },
    },
    # S12.7 (§A6 v7/CT11): query optional (files listing / outline);
    # matches enforces it in-handler.
    "required": [],
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


_GLOB_META_CHARS = ("*", "?", "[")


def _parse_path(data: Mapping[str, object]) -> tuple[str, str | None, str | None]:
    """§A6 v7 (CT10): ``path`` absorbs the old ``glob`` param.

    A value with glob metacharacters (* ? [) is a PATTERN (basename-only
    patterns match at any depth, ``/`` anchors — same rules the old glob
    knob used); otherwise it is a literal dir/file as before. Returns
    (subpath, glob_pat, error).
    """
    subpath = data.get("path", ".") or "."
    if not isinstance(subpath, str):
        return ".", None, f"path must be a string, got {type(subpath).__name__}"
    if subpath != "." and any(ch in subpath for ch in _GLOB_META_CHARS):
        return ".", subpath, None
    return subpath, None, None


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
        result["skipped_large_files"] = sr.skipped_large_files  # §A6 v7 skip report
    elif mode == "matches":
        result["matches"] = sr.matches


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
        "matches": "regions",  # S12.7: matches rows ARE merged regions (concept, not the removed mode)
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
    exclude_dirs: list[str] | None,
    limit: int,
    regex: bool,
) -> SearchParams:
    """Construct a :class:`SearchParams` from parsed user input.

    Centralized in one place so the two code paths (indexed and
    fallback) receive an identical parameter object. S12.7 §A6 v7: the
    carrier is the locked 6-param surface minus path/exclude wiring —
    size/context/merge/casing knobs are fixed constants in
    ``search_index`` now.
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
        exclude_set=exclude_set,
        limit=limit,
        regex=regex,
    )


def _register_search_result_paths(result: dict[str, Any]) -> None:
    """S15 (CT-3): register returned paths as PENDING search results.

    They are not attributable yet — ``run_session`` promotes them to
    ``last_search_paths`` at batch end (``commit_search_paths``), which keeps
    ``surfaced_by`` attribution deterministic under the parallel executor.
    Best-effort: a telemetry failure must never fail the search itself.
    """
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is None:
            return
        surfaced_paths: list[str] = []
        for key in _OUTPUT_KEYS:
            rows = result.get(key)
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, Mapping) and isinstance(row.get("path"), str):
                        surfaced_paths.append(row["path"])
        if surfaced_paths:
            session.add_search_result_paths(surfaced_paths)
    except Exception as exc:  # noqa: BLE001 - telemetry best-effort, failure-observable
        logger.warning(f"fs_search telemetry failed: {exc}")


def _load_outline_rows(subdir: Path, rel: Path) -> ToolResult | list[OutlineRow]:
    """Validate + read + fold ONE file for outline mode; every failure steers."""
    if subdir.is_dir():
        return ToolResult.fail(
            "invalid_params",
            "outline takes ONE file; for a directory use output_mode='files' first, then outline the file you need",
            retryable=True,
        )
    suffix = subdir.suffix.lower()
    if suffix not in (".py", ".md"):
        return ToolResult.fail(
            "invalid_params",
            f"outline supports .py and .md (got {suffix!r}); use output_mode='matches' to grep other files",
            retryable=True,
        )
    try:
        size = subdir.stat().st_size
    except OSError as exc:
        return ToolResult.fail("read_failed", str(exc), retryable=True)
    if size > OUTLINE_MAX_READ_BYTES:
        return ToolResult.fail(
            "invalid_params",
            f"file too large to outline ({size} > {OUTLINE_MAX_READ_BYTES} bytes); "
            "use output_mode='matches' with a query",
            retryable=True,
        )
    try:
        text = subdir.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return ToolResult.fail("read_failed", str(exc), retryable=True)

    if suffix == ".py":
        try:
            return fold_python_source(text)
        except SyntaxError as exc:
            return ToolResult.fail(
                "invalid_params",
                f"Python syntax error in {rel}: {exc.msg} (line {exc.lineno or '?'}) — "
                "use output_mode='matches' to grep it or fs_read_file windows",
                retryable=True,
            )
    return fold_markdown(text)


def _do_outline(
    root: Path,
    subdir: Path,
    query: str | None,
    data: Mapping[str, object],
    warnings_list: list[str],
) -> ToolResult:
    """S12.7 (CT9): structural outline of ONE py/md file (plan §A6).

    Routing/steering contract (every failure names the better tool):
    dir -> files mode; non-py/md -> matches/read; too large -> matches;
    SyntaxError -> matches/read. Rows' start_line/end_line paste straight
    into fs_read_file windows (the discovery chain).
    """
    rel = subdir.relative_to(root)
    loaded = _load_outline_rows(subdir, rel)
    if isinstance(loaded, ToolResult):
        return loaded
    rows = loaded

    if data.get("regex") is True:
        warnings_list.append(
            "param 'regex' is accepted but ignored in outline mode (S12.7): "
            "query is a literal case-insensitive symbol-name filter"
        )
    if data.get("exclude_dirs") is not None:
        warnings_list.append(
            "param 'exclude_dirs' is accepted but ignored in outline mode (S12.7): "
            "outline reads ONE file — scope filters apply to files/matches"
        )

    # R21 consistency: name filtering is case-insensitive, always.
    if query is not None:
        filtered = [r for r in rows if query.lower() in r.name.lower()]
        if not filtered:
            rows_all = rows
            warnings_list.append(f"no symbol matched {query!r}; showing full outline")
        else:
            rows_all = filtered
    else:
        rows_all = rows

    total = len(rows_all)
    limit = _clamp_int(
        data.get("limit"), lo=1, hi=500, default=OUTLINE_DEFAULT_LIMIT, warnings=warnings_list, label="limit"
    )
    shown = rows_all[:limit]

    def _row_dict(r: Any) -> dict[str, Any]:
        d: dict[str, Any] = {
            "kind": r.kind,
            "name": r.name,
            "start_line": r.start_line,
            "end_line": r.end_line,
            "depth": r.depth,
        }
        if r.signature is not None:
            d["signature"] = r.signature
        return d

    row_dicts = [_row_dict(r) for r in shown]
    truncated = len(shown) < total
    if truncated:
        warnings_list.append(f"showing {len(shown)} of {total} rows — raise limit or filter with query")
    while _estimate_size({"rows": row_dicts}) > MAX_RESPONSE_BYTES and len(row_dicts) > 1:
        row_dicts.pop()
        truncated = True
    if truncated and len(row_dicts) < len(shown):
        warnings_list.append(f"byte cap {MAX_RESPONSE_BYTES} reached — {total} rows total, narrow with query")
    shown = shown[: len(row_dicts)]

    result: dict[str, Any] = {
        "query": query or "",
        "mode": "outline",
        "path": str(rel),
        "returned": len(row_dicts),
        "total": total,
        "truncated": truncated,
        "rows": row_dicts,
    }
    if warnings_list:
        result["warnings"] = warnings_list

    _register_outline_path(str(rel))
    summary = f"fs_search[outline] {len(row_dicts)}/{total} rows for {str(rel)!r}"
    if truncated:
        summary += " (truncated)"
    return ToolResult.ok(summary, result=result)


def _register_outline_path(rel: str) -> None:
    """S15 attribution: the outlined file becomes a surfaced search result."""
    try:
        from fa.inner_loop.context import get_current_session

        session = get_current_session()
        if session is not None:
            session.add_search_result_paths([rel])
    except Exception as exc:  # noqa: BLE001 - telemetry best-effort
        logger.warning(f"outline telemetry failed: {exc}")


def _do_files_listing(
    root: Path,
    subdir: Path,
    glob_pat: str | None,
    exclude_set: frozenset[str],
    limit: int,
    warnings_list: list[str],
) -> ToolResult:
    """S12.7 (§A6 v7 / CT11): absent query + files mode = pure listing.

    A discovery primitive: everything under the (path/glob/exclude)
    scope, path-ordered, with ``{path, lines, bytes}`` rows, the
    ``skipped_large_files`` count, and steering when truncated. Never
    touches the search index.
    """
    from fa.memory.search_index import files_stat_rows, walk_scope_listing

    if not subdir.exists():
        rel = subdir.relative_to(root)
        return ToolResult.fail(
            "invalid_params",
            f"path does not exist: {rel} — list '.' first or check the spelling",
            retryable=True,
        )
    subdir_rel = _subdir_rel(root, subdir)
    rels, skipped = walk_scope_listing(
        root,
        subdir_rel=subdir_rel,
        glob_pat=glob_pat,
        exclude_set=exclude_set,
    )
    total = len(rels)
    rows = files_stat_rows(root, rels, limit)
    truncated = len(rows) < total
    if truncated:
        warnings_list.append(f"showing {len(rows)} of {total} files — raise limit or narrow path")

    result: dict[str, Any] = {
        "query": "",
        "method": "walk_listing",
        "returned": len(rows),
        "truncated": truncated,
        "total": total,
        "total_bytes": int(sum(r.get("bytes") or 0 for r in rows)),
        "index_stats": None,
        "files": rows,
        "skipped_large_files": skipped,
    }
    if warnings_list:
        result["warnings"] = warnings_list

    _enforce_response_cap(result)

    # S15 (CT-3): listed paths are surfaced search results too.
    _register_search_result_paths(result)

    summary = _build_summary("", "files", "walk_listing", result)
    return ToolResult.ok(summary, result=result)


def _parse_output_mode(data: Mapping[str, object]) -> tuple[str, ToolResult | None]:
    """§A6 v7: 3 modes; removed modes (P19) steer with fold guidance."""
    output_mode, err = _parse_str_enum(data, "output_mode", "files", VALID_OUTPUT_MODES, "output_mode")
    if err:
        raw_mode = data.get("output_mode")
        if raw_mode in ("regions", "counts"):  # S12.7 removed modes -> steering below (P19)
            return "files", ToolResult.fail(
                "invalid_params",
                f"output_mode {raw_mode!r} no longer exists (S12.7 §A6): 'regions' is "
                "folded into 'matches' (merged, grep-marked regions) and 'counts' was "
                "removed — use output_mode='files'/'matches' with limit. "
                f"Valid modes: {sorted(VALID_OUTPUT_MODES)}",
                retryable=True,
            )
        return "files", ToolResult.fail("invalid_params", err, retryable=True)
    return output_mode, None


def _handle(
    params: Mapping[str, object],
    holder: _IndexHolder,
    root: Path,
    db: Path,
) -> ToolResult:
    warnings_list: list[str] = []

    data = dict(params)

    # enums (output_mode first: query optionality depends on it — S12.7 S7a)
    output_mode, mode_err = _parse_output_mode(data)
    if mode_err is not None:
        return mode_err

    # query — OPTIONAL for files (pure listing) and outline (full table);
    # required for matches (S12.7 §A6 v7 / CT11 leniency).
    query_raw = data.get("query")
    optional_query = output_mode in ("files", "outline") and (
        query_raw is None or (isinstance(query_raw, str) and not query_raw.strip())
    )
    if optional_query:
        query = None
    else:
        if not isinstance(query_raw, str) or not query_raw.strip():
            if output_mode == "matches":
                return ToolResult.fail(
                    "invalid_params",
                    "query is required for output_mode='matches' (a grep needs a pattern); "
                    "use output_mode='files' to list the scope first",
                    retryable=True,
                )
            return ToolResult.fail(
                "invalid_params",
                "query must be a non-empty string (optional for output_mode='files' listing and 'outline')",
                retryable=True,
            )
        query = query_raw.strip()

    # CT11 leniency: removed params warn (kept for outline/listing results too).
    leniency: list[str] = []
    _warn_removed_params(data, leniency)
    warnings_list.extend(leniency)

    # bools
    regex = _parse_bool(data, "regex", False)

    # ints (R-14 clamping) — §A6 v7: limit is the only int knob left.
    limit = _clamp_int(
        data.get("limit"),
        lo=1,
        hi=HARD_MAX_LIMIT,
        default=DEFAULT_LIMIT,
        warnings=warnings_list,
        label="limit",
    )

    # path (absorbs the old glob param — CT10)
    subpath, glob_pat, err = _parse_path(data)
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)
    try:
        subdir = _resolve_subdir(root, subpath)
    except PermissionError as exc:
        return ToolResult.fail("path_escape", str(exc), retryable=True)

    # exclude_dirs — §A6 v7: the only dir-exclusion knob (parsed before the
    # dispatches because the listing is scoped by it too).
    exclude_dirs, err = _parse_exclude_dirs(data)
    if err:
        return ToolResult.fail("invalid_params", err, retryable=True)
    exclude_set = frozenset(exclude_dirs) if exclude_dirs else frozenset()

    # S12.7 (CT9): outline mode — structural fold of ONE file; never
    # touches the search index. Leniency warnings survive; generic limit
    # clamp noise does not (outline has its own limit semantics).
    if output_mode == "outline":
        return _do_outline(root, subdir, query, data, leniency)

    # S12.7 (§A6 v7 / CT11): absent query + files = pure scope listing.
    if query is None and output_mode == "files":
        return _do_files_listing(root, subdir, glob_pat, exclude_set, limit, warnings_list)

    if query is None:  # unreachable: files+None listed and matches+None failed above
        return ToolResult.fail("invalid_params", "query must be a non-empty string", retryable=True)

    # Build one immutable carrier; both search paths consume the same object.
    search_params = _build_search_params(
        query=query,
        output_mode=output_mode,
        glob_pat=glob_pat,
        exclude_dirs=exclude_dirs,
        limit=limit,
        regex=regex,
    )

    # lazy index + search (fixed internal size cap — §A6 v7)
    from fa.memory.search_index import MAX_SEARCH_FILE_BYTES

    index_stats_dict = _ensure_index(holder, root, MAX_SEARCH_FILE_BYTES, warnings_list)

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
    if warnings_list:
        result["warnings"] = warnings_list
    elif sr.warnings:
        result["warnings"] = list(sr.warnings)

    _enforce_response_cap(result)

    # S15 (CT-3): surface this search's returned paths to the attribution
    # pipeline (pending set — run_session promotes at batch end).
    _register_search_result_paths(result)

    summary = _build_summary(query, output_mode, sr.method, result)
    return ToolResult.ok(summary, result=result)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_fs_search_tool(db_path: Path, workspace_root: Path) -> ToolSpec:
    """Build the fs_search ToolSpec bound to a workspace and FTS DB path.

    Registers an ``atexit`` handler that closes the held
    :class:`SearchIndex` connection deterministically at interpreter
    shutdown. Without this, the lazy ``_IndexHolder`` singleton keeps a
    ``sqlite3.Connection`` open until GC finalizes it, which emits a
    ``ResourceWarning: unclosed database`` from the CPython finalizer.
    Those warnings are treated as errors in ``tests/test_fs_search.py``
    to prevent resource-leak regressions.
    """
    root = Path(workspace_root).resolve()
    db = Path(db_path)
    holder = _IndexHolder(db)
    atexit.register(holder.close)

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
        # S12.7 (CT2/GAP4): projection ceiling (was 30_000). MAX_RESPONSE_BYTES
        # remains the INTERNAL response cap until the S7 mode restructure.
        max_context_bytes=DEFAULT_TOOL_CONTEXT_BYTES,
    )


__all__ = [
    "DEFAULT_LIMIT",
    "HARD_MAX_LIMIT",
    "MAX_RESPONSE_BYTES",
    "VALID_OUTPUT_MODES",
    "build_fs_search_tool",
]
