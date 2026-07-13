"""fs.grep — token-efficient content grep, returns paths with matches.

Phase 1 Foundation: researcher needs grep, complement to instant_grep FTS5.
Uses git grep if available, fallback to python search via git ls-files.

Prior art: ripgrep, git grep, Cursor instant grep fallback.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string


def _git_grep(root: Path, query: str, limit: int) -> list[str] | None:
    # Try git grep -l for files containing query, respects .gitignore, fast
    try:
        res = subprocess.run(
            ["git", "grep", "-l", "--", query],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        # git grep returns 0 if matches found, 1 if no matches
        if res.returncode in (0, 1):
            files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            return files[:limit]
    except Exception as exc:  # noqa: BLE001 - fallback
        print(f"WARNING: git grep failed: {exc}")
    return None


def _rg_grep(root: Path, query: str, limit: int) -> list[str] | None:
    # Try ripgrep if installed
    try:
        res = subprocess.run(
            ["rg", "-l", query],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode in (0, 1):
            files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
            return files[:limit]
    except FileNotFoundError:
        # rg not installed, ok
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: rg failed: {exc}")
    return None


def build_grep_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            query = require_string(dict(params), "query")
            limit = int(params.get("limit", 20)) if "limit" in params else 20
            glob_filter = params.get("glob")
            if glob_filter is not None and not isinstance(glob_filter, str):
                glob_filter = None
        except ValueError as exc:
            return ToolResult.fail("invalid_params", str(exc), retryable=True)

        try:
            # Try fast paths: rg, git grep, then fallback python
            for method in (_rg_grep, _git_grep):
                result = method(root, query, limit)
                if result is not None:
                    # Apply glob filter if provided
                    if glob_filter:
                        import fnmatch

                        filtered = [p for p in result if fnmatch.fnmatch(p, glob_filter)]
                        result = filtered[:limit]
                    summary = f"Grep found {len(result)} files containing '{query}' via {method.__name__} (limit {limit})"
                    return ToolResult.ok(
                        summary,
                        result={"paths": result, "query": query, "limit": limit, "method": method.__name__},
                    )

            # Fallback: python search via git ls-files
            try:
                ls_res = subprocess.run(
                    ["git", "ls-files"],  # noqa: S607
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                tracked = ls_res.stdout.splitlines() if ls_res.returncode == 0 else []
            except Exception:
                tracked = []

            if not tracked:
                # Last fallback: walk filesystem
                import os

                tracked = []
                exclude_dirs = {".git", ".fa", "node_modules", ".venv", "__pycache__", "sessions"}
                for dirpath, dirnames, filenames in os.walk(root):
                    dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
                    for fname in filenames:
                        if fname.endswith((".py", ".md", ".ts", ".js", ".json", ".yaml", ".toml")):
                            rel = str((Path(dirpath) / fname).relative_to(root))
                            tracked.append(rel)

            matched: list[str] = []
            q_lower = query.lower()
            for rel in tracked:
                if glob_filter:
                    import fnmatch

                    if not fnmatch.fnmatch(rel, glob_filter):
                        continue
                fp = root / rel
                try:
                    if not fp.is_file():
                        continue
                    if fp.stat().st_size > 200_000:
                        continue
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                    if q_lower in text.lower():
                        matched.append(rel)
                        if len(matched) >= limit:
                            break
                except Exception:
                    continue

            summary = f"Grep found {len(matched)} files containing '{query}' via python fallback (limit {limit})"
            return ToolResult.ok(
                summary, result={"paths": matched, "query": query, "limit": limit, "method": "python_fallback"}
            )

        except Exception as exc:
            return ToolResult.fail("grep_failed", f"Grep failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.grep",
        description="Grep files containing query (e.g., 'auth'), respects .gitignore via git grep, returns paths not content, token efficient. Optional glob filter like '*.py'. Limit default 20.",
        input_schema={
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string", "description": "Substring to search"},
                "glob": {"type": "string", "description": "Optional glob filter e.g., '*.py'"},
                "limit": {"type": "integer", "description": "Max paths, default 20", "default": 20},
            },
        },
        permission="read",
        handler=handler,
        tags=("fs", "grep", "search"),
        max_context_bytes=2000,
    )


__all__ = ["build_grep_tool"]
