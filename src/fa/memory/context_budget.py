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
    """Progressive context gating and thrashing prevention.

    Stage semantics:
    - warn: operator signal only
    - stage2: deterministic observation masking zone
    - stage3: LLM compaction zone / hard-stop zone if compaction unavailable
    """

    def __init__(
        self,
        limit_tokens: int = 150000,
        configured_threshold: int | None = None,
    ):
        self.limit_tokens = limit_tokens
        # Dynamic fallback per ADR-17 / §9.4 for Stage 2.
        if configured_threshold is not None:
            self.stage2_threshold = configured_threshold
        else:
            self.stage2_threshold = min(int(limit_tokens * 0.80), 150000)
        self.threshold = self.stage2_threshold
        self.stage3_threshold = min(max(self.stage2_threshold + 1, int(limit_tokens * 0.90)), limit_tokens)

        self.consecutive_compactions = 0
        self.last_reclaimed_ratio = 1.0

    def check(self, current_tokens: int) -> dict[str, Any]:
        """Classify current tokens against the progressive Stage C ladder."""
        ratio = current_tokens / self.limit_tokens if self.limit_tokens > 0 else 0.0
        warn_threshold_tokens = min(int(self.limit_tokens * 0.70), int(self.stage2_threshold * 0.875))
        warn_threshold_ratio = (
            warn_threshold_tokens / self.limit_tokens if self.limit_tokens > 0 else 0.0
        )
        stage2_threshold_ratio = (
            self.stage2_threshold / self.limit_tokens if self.limit_tokens > 0 else 0.0
        )
        stage3_threshold_ratio = (
            self.stage3_threshold / self.limit_tokens if self.limit_tokens > 0 else 0.0
        )

        action = "allow"
        message = "Context budget is healthy."

        if current_tokens >= self.stage3_threshold:
            action = "stage3"
            message = (
                f"Context budget critical: {current_tokens} tokens ({ratio:.0%}) "
                f"exceeds Stage 3 threshold {self.stage3_threshold} tokens "
                f"({stage3_threshold_ratio:.0%}). LLM compaction required."
            )
        elif current_tokens >= self.stage2_threshold:
            action = "stage2"
            message = (
                f"Context budget high: {current_tokens} tokens ({ratio:.0%}) "
                f"exceeds Stage 2 threshold {self.stage2_threshold} tokens "
                f"({stage2_threshold_ratio:.0%}). Observation masking recommended."
            )
        elif current_tokens >= warn_threshold_tokens:
            action = "warn"
            message = (
                f"Context budget warning: {current_tokens} tokens ({ratio:.0%}) "
                f"exceeds warning threshold {warn_threshold_tokens} tokens ({warn_threshold_ratio:.0%}). "
                "Consider pruning."
            )

        return {
            "action": action,
            "ratio": ratio,
            "message": message,
            "current_tokens": current_tokens,
            "limit_tokens": self.limit_tokens,
            "threshold": self.threshold,
            "warning_threshold": warn_threshold_tokens,
            "stage2_threshold": self.stage2_threshold,
            "stage3_threshold": self.stage3_threshold,
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
