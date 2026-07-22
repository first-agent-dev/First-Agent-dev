"""Compaction foundation — threshold selection and tool-output offload policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar


@dataclass
class CompactionAction:
    stage: str
    threshold: float
    message: str


class CompactionManager:
    """Select the highest compaction stage exceeded by current token pressure."""

    stages: ClassVar[list[tuple[float, str, str]]] = [
        (0.70, "warning", "Context pressure 70%: consider pruning"),
        (
            0.80,
            "observation_masking",
            "Mask older tool results with reference pointers to offloaded scratch files, "
            "keep 6 recent full-fidelity",
        ),
        (
            0.85,
            "fast_pruning",
            "Prune tool outputs beyond recent window, replace with [pruned] markers",
        ),
        (0.90, "aggressive_masking", "Shrink preservation window to 3 recent full-fidelity"),
        (
            0.99,
            "full_compaction",
            "Serialize entire history to scratch file + LLM summarizer compress middle, "
            "preserve recent verbatim",
        ),
    ]

    def check(self, token_usage: int, context_limit: int) -> CompactionAction | None:
        """Return the highest configured stage at or below the usage ratio."""
        if context_limit == 0:
            return None
        ratio = token_usage / context_limit
        for threshold, stage, message in reversed(self.stages):
            if ratio >= threshold:
                return CompactionAction(stage=stage, threshold=threshold, message=message)
        return None

    def should_offload(self, output: str, limit: int = 8000) -> bool:
        """Whether output exceeds the configured scratch-file offload limit."""
        return len(output) > limit
