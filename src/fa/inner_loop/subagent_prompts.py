"""
Subagent cheap deterministic minimal system prompts <500 tokens, not full BASE+map
Phase 2 and Phase 3: researcher websearch agent, verifier simple function
Pair over Autonomy: clean slate ~1k, restricted tools, JSON envelope, stateless scrubbed env
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


RESEARCHER_MINIMAL_PROMPT = """You are websearch agent, tools=[web_search, fs.glob, fs.grep, fs.read_file,
fs.instant_grep], input query, output JSON {urls, snippets, summary}. Clean slate ~1k,
never inherit full parent history, task solvable with <600 tokens tool defs and <8000 output, structured JSON,
stateless scrubbed env, isolated."""

VERIFIER_MINIMAL_PROMPT = """You are verifier agent, tools=[fs.run_bash], input spec, output JSON {file_path,
test_result PASS/FAIL, summary, risks}. Clean slate ~1k, restricted tools, JSON envelope, stateless."""


def estimate_prompt_tokens(prompt: str) -> int:
    """Chars/4 heuristic per Pi agent, for token budgeting."""
    return len(prompt) // 4


def get_minimal_prompt(role: str) -> str:
    role = role.lower()
    if role in ("researcher", "websearch", "search"):
        return RESEARCHER_MINIMAL_PROMPT
    if role in ("verifier", "test", "bash"):
        return VERIFIER_MINIMAL_PROMPT
    return RESEARCHER_MINIMAL_PROMPT


def build_filtered_history(
    task: str, session_state: Any | None, workspace_root: Path, limit: int = 5
) -> list[dict[str, str]]:
    """Filtered history: task + relevant files from transaction.read_set/write_set + instant_grep(task), not full parent 124 steps.

    Returns list of messages with total <8000 chars.
    Fallback chain: transaction read/write sets first, then instant_grep, then glob llms.txt, AGENTS.md, README.md if instant_grep <3 results.
    """
    from fa.memory.fts_index import InstantGrepIndex

    workspace_root = Path(workspace_root).resolve()
    relevant_files: list[str] = []

    # 1) Transaction read_set/write_set
    try:
        if session_state is not None:
            transaction = getattr(session_state, "transaction", None)
            if transaction is not None:
                read_set = list(getattr(transaction, "read_set", []))[:limit]
                write_set = list(getattr(transaction, "write_set", []))[:limit]
                relevant_files.extend(read_set)
                relevant_files.extend(write_set)
    except Exception:
        pass

    # 2) instant_grep(task) via FTS5 trigram <50ms
    try:
        db_path = workspace_root / ".fa" / "fts.db"
        if db_path.exists():
            index = InstantGrepIndex(db_path)
            try:
                paths = index.instant_grep(task, limit=limit)
                relevant_files.extend(paths)
            finally:
                try:
                    index.close()
                except Exception:
                    pass
    except Exception:
        pass

    # Deduplicate and limit
    seen: set[str] = set()
    deduped: list[str] = []
    for f in relevant_files:
        if f not in seen:
            seen.add(f)
            deduped.append(f)
        if len(deduped) >= limit:
            break

    # 3) Fallback if <3 results: glob llms.txt, AGENTS.md, README.md
    if len(deduped) < 3:
        for fallback in ["knowledge/llms.txt", "llms.txt", "AGENTS.md", "README.md", "HANDOFF.md"]:
            if fallback not in deduped:
                # Check exists
                if (workspace_root / fallback).exists():
                    deduped.append(fallback)
            if len(deduped) >= limit:
                break

    # Build messages with 500-char preview each, total <8000
    messages: list[dict[str, str]] = [{"role": "user", "content": f"Task: {task}"}]
    total_chars = len(task)
    for rel in deduped[:limit]:
        try:
            fp = workspace_root / rel
            if not fp.is_file():
                continue
            content = fp.read_text(encoding="utf-8", errors="ignore")[:500]
            msg = f"Relevant file {rel} (500-char preview):\n{content}"
            if total_chars + len(msg) > 8000:
                break
            messages.append({"role": "system", "content": msg})
            total_chars += len(msg)
        except Exception:
            continue

    return messages


__all__ = [
    "RESEARCHER_MINIMAL_PROMPT",
    "VERIFIER_MINIMAL_PROMPT",
    "estimate_prompt_tokens",
    "get_minimal_prompt",
    "build_filtered_history",
]
