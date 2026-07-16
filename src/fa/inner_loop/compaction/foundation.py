"""
Compaction foundation — Stage 1 only for ADR-13, full 5-stage for ADR-15

Prior art: ArXiv 2603.05344 Building Effective AI Coding Agents, Appendix I Implementation Constants
Table: Compaction stages 70/80/90/99% — Four graduated thresholds: warn, mask, aggressive mask, full compaction
Tool output offload 8000 chars → scratch files, 500-char preview retained
Observation masking 6/3 recent — Full-fidelity outputs at 80%/90%
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CompactionAction:
    stage: str
    threshold: float
    message: str


class CompactionManager:
    """
    Foundation for ADR-15. For ADR-13, only Stage 1 warning + artifact offload 8000.
    Wired at BETWEEN_ROUNDS hook (ADR-8).
    """

    # From ArXiv 2603.05344 v2 Appendix I
    stages = [
        (0.70, "warning", "Context pressure 70%: consider pruning"),
        (
            0.80,
            "observation_masking",
            "Mask older tool results with reference pointers to offloaded scratch files, keep 6 recent full-fidelity",
        ),
        (0.85, "fast_pruning", "Prune tool outputs beyond recent window, replace with [pruned] markers"),
        (0.90, "aggressive_masking", "Shrink preservation window to 3 recent full-fidelity"),
        (
            0.99,
            "full_compaction",
            "Serialize entire history to scratch file + LLM summarizer compress middle, preserve recent verbatim",
        ),
    ]

    def check(self, token_usage: int, context_limit: int) -> CompactionAction | None:
        if context_limit == 0:
            return None
        ratio = token_usage / context_limit
        for threshold, stage, msg in self.stages:
            if ratio > threshold:
                # Return highest exceeded stage
                # Actually we want first exceeded? No, highest
                # For foundation, return warning at 70%
                # Full logic: if ratio >0.99 return full_compaction, elif >0.90 aggressive, etc.
                pass

        # Implement correctly: check from highest to lowest
        for threshold, stage, msg in reversed(self.stages):
            if ratio >= threshold:
                return CompactionAction(stage=stage, threshold=threshold, message=msg)
        return None

    def should_offload(self, output: str, limit: int = 8000) -> bool:
        return len(output) > limit


# Example usage in loop.py BETWEEN_ROUNDS:
# manager = CompactionManager()
# action = manager.check(token_usage=85000, context_limit=100000) # 85% → fast_pruning
# if action and action.stage == "warning":
#   state.log.append(actor="runtime", kind="compaction_warning", content={"stage": action.stage, "ratio": ...})
# if manager.should_offload(tool_result.stdout):
#   artifact_id = artifact_store.put(tool_result.stdout)
#   projected = tool_result.stdout[:500] + f"\n...[offloaded to artifact {artifact_id}]"
