"""
Subagent cheap deterministic minimal system prompts <500 tokens, not full BASE+map
Phase 2 and Phase 3: researcher websearch agent, verifier simple function
Pair over Autonomy: clean slate ~1k, restricted tools, JSON envelope, stateless scrubbed env
Senior refactor v4: split build_filtered_history into pure helpers, C901 <15 each, BLE001 narrowed,
S110/S112 with WARNING, E501 wrapped  # noqa: E501
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RESEARCHER_MINIMAL_PROMPT = (
    "You are websearch agent, tools=[web_search, fs_glob, fs_grep, fs_read_file, "
    "fs_instant_grep], input query, output JSON {urls, snippets, summary}. "
    "Clean slate ~1k, never inherit full parent history, task solvable with "
    "<600 tokens tool defs and <8000 output, structured JSON, stateless scrubbed env, isolated."
)

VERIFIER_MINIMAL_PROMPT = (
    "You are verifier agent, tools=[fs_run_bash], input spec, output JSON "
    "{file_path, test_result PASS/FAIL, summary, risks}. Clean slate ~1k, "
    "restricted tools, JSON envelope, stateless."
)


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


def _get_transaction_files(session_state: Any | None, limit: int) -> list[str]:
    """Get files from transaction.read_set/write_set, deterministic, no LLM."""
    if session_state is None:
        return []
    try:
        transaction = session_state.transaction if session_state is not None else None
        if transaction is None:
            return []
        read_set = list(getattr(transaction, "read_set", []))[:limit]
        write_set = list(getattr(transaction, "write_set", []))[:limit]
        return read_set + write_set
    except (AttributeError, TypeError, ValueError) as exc:
        logger.warning(f"transaction files failed: {exc}")
        return []


def _get_fts_files(workspace_root: Path, task: str, limit: int) -> list[str]:
    """Get relevant files via FTS5 trigram <50ms, graceful degradation."""
    try:
        db_path = workspace_root / ".fa" / "fts.db"
        if not db_path.exists():
            return []
        # Import locally to avoid circular and allow fallback if not available
        try:
            from fa.memory.fts_index import InstantGrepIndex
        except ImportError as exc:
            logger.warning(f"InstantGrepIndex import failed: {exc}")
            return []

        index = InstantGrepIndex(db_path)
        try:
            paths = index.instant_grep(task, limit=limit)
            return paths
        finally:
            try:
                index.close()
            except (OSError, AttributeError) as exc:
                logger.warning(f"FTS index close failed: {exc}")
    except (OSError, ValueError, RuntimeError) as exc:
        logger.warning(f"FTS files failed: {exc}")
        return []
    except Exception as exc:  # noqa: BLE001 # best-effort for unexpected
        logger.warning(f"FTS files unexpected failed: {exc}")
        return []


def _deduplicate_files(files: list[str], limit: int) -> list[str]:
    """Deduped order-preserving, limit-aware."""
    seen: set[str] = set()
    deduped: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            deduped.append(f)
        if len(deduped) >= limit:
            break
    return deduped


def _ensure_fallback_files(workspace_root: Path, deduped: list[str], limit: int) -> list[str]:
    """Fallback if <3 results: glob llms.txt, AGENTS.md, README.md, HANDOFF.md."""
    if len(deduped) >= 3:
        return deduped
    fallbacks = [
        "knowledge/llms.txt",
        "llms.txt",
        "AGENTS.md",
        "README.md",
        "HANDOFF.md",
    ]
    for fb in fallbacks:
        if fb not in deduped and (workspace_root / fb).exists():
            deduped.append(fb)
        if len(deduped) >= limit:
            break
    return deduped


def _build_messages(workspace_root: Path, task: str, files: list[str], limit: int) -> list[dict[str, str]]:
    """Build messages with 500-char preview each, total <8000."""
    messages: list[dict[str, str]] = [{"role": "user", "content": f"Task: {task}"}]
    total_chars = len(task)
    for rel in files[:limit]:
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
        except (OSError, ValueError, UnicodeError) as exc:
            logger.warning(f"preview for {rel} failed: {exc}")
            continue
    return messages


def build_filtered_history(
    task: str, session_state: Any | None, workspace_root: Path, limit: int = 5
) -> list[dict[str, str]]:
    """Filtered history: task + relevant files, not full parent 124 steps.

    Returns list of messages with total <8000 chars.
    Fallback chain: transaction read/write sets first, then instant_grep,
    then glob llms.txt, AGENTS.md, README.md if instant_grep <3 results.
    File-based minimal surface for v0.1 per Q2, optional blackboard plans
    behind flag blackboard.filtered_history_include_plans for v0.2.
    """
    workspace_root = Path(workspace_root).resolve()

    # 1) Transaction + FTS
    files: list[str] = []
    files.extend(_get_transaction_files(session_state, limit))
    files.extend(_get_fts_files(workspace_root, task, limit))

    # 2) Deduplicate + fallback
    deduped = _deduplicate_files(files, limit)
    deduped = _ensure_fallback_files(workspace_root, deduped, limit)

    # 3) Build messages
    return _build_messages(workspace_root, task, deduped, limit)


__all__ = [
    "RESEARCHER_MINIMAL_PROMPT",
    "VERIFIER_MINIMAL_PROMPT",
    "build_filtered_history",
    "estimate_prompt_tokens",
    "get_minimal_prompt",
]
