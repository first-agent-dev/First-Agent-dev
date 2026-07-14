"""ContextBudget — progressive context gating and loop circuit breaking.

ADR-17, Phase 3 SOTA:
- Thresholds: Warn at 70%, Compaction Required at 90%
- Model-aware & Dynamic fallback: min(80% limit, 150k)
- 3-strike circuit breaker to prevent infinite compaction loops/thrashing
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def estimate_tokens(
    messages: list[dict[str, Any]] | None,
    tools_schema: Any | None = None,
    pinned_text: str | None = None,
) -> int:
    """Estimated token count using chars // 4 heuristic.

    Handles string, block list, or dict-like content safely.
    Pure and injectable.
    """
    total_chars = 0
    if messages:
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        text = block.get("text") or block.get("content") or ""
                        total_chars += len(str(text))
            elif content is not None:
                total_chars += len(str(content))

            # Include tool_calls if present
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                try:
                    total_chars += len(json.dumps(tool_calls, ensure_ascii=False))
                except Exception:  # noqa: BLE001, S110
                    pass

    if tools_schema:
        try:
            total_chars += len(json.dumps(tools_schema, ensure_ascii=False))
        except Exception:  # noqa: BLE001, S110
            pass

    if pinned_text:
        total_chars += len(pinned_text)

    return total_chars // 4


class ContextBudget:
    """Progressive context gating and thrashing prevention."""

    def __init__(
        self,
        limit_tokens: int = 150000,
        configured_threshold: int | None = None,
    ):
        self.limit_tokens = limit_tokens
        # Dynamic fallback per ADR-17: min(80% limit, 150k)
        if configured_threshold is not None:
            self.threshold = configured_threshold
        else:
            self.threshold = min(int(limit_tokens * 0.80), 150000)

        self.consecutive_compactions = 0
        self.last_reclaimed_ratio = 1.0

    def check(self, current_tokens: int) -> dict[str, Any]:
        """Check current tokens against budget.

        Returns diagnostics on whether to warn (70%) or require compaction (80%).
        """
        ratio = current_tokens / self.limit_tokens if self.limit_tokens > 0 else 0.0
        warn_threshold = 0.70
        hard_threshold = 0.80

        action = "allow"
        message = "Context budget is healthy."

        if ratio >= hard_threshold:
            action = "require_compaction"
            message = (
                f"Context budget CRITICAL: {current_tokens} tokens ({ratio:.0%}) "
                f"exceeds hard threshold {hard_threshold:.0%}. Compaction required!"
            )
        elif ratio >= warn_threshold:
            action = "warn"
            message = (
                f"Context budget warning: {current_tokens} tokens ({ratio:.0%}) "
                f"exceeds warning threshold {warn_threshold:.0%}. Consider pruning."
            )

        return {
            "action": action,
            "ratio": ratio,
            "message": message,
            "current_tokens": current_tokens,
            "limit_tokens": self.limit_tokens,
            "threshold": self.threshold,
        }

    def record_compaction_attempt(self, tokens_before: int, tokens_after: int) -> bool:
        """Record a compaction attempt and check for endless loops.

        Returns True if ok, False if circuit breaker triggered (anti-thrashing).
        """
        reclaimed = tokens_before - tokens_after
        reclaimed_ratio = reclaimed / tokens_before if tokens_before > 0 else 0.0
        self.last_reclaimed_ratio = reclaimed_ratio

        if reclaimed_ratio < 0.10:  # Less than 10% space reclaimed
            self.consecutive_compactions += 1
        else:
            self.consecutive_compactions = 0

        if self.consecutive_compactions >= 3:
            logger.error(
                "Circuit breaker: Compaction triggered 3 consecutive times "
                "with less than 10% space reclaimed (anti-thrashing). Locking loop."
            )
            return False
        return True


__all__ = ["ContextBudget", "estimate_tokens"]
