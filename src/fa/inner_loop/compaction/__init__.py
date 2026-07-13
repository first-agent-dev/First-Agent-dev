"""fa.inner_loop.compaction — foundation for ADR-15 5-stage compaction

Current: Stage 1 only warning + artifact offload 8000 chars → scratch file + 500-char preview
Full 5-stage: warning 70%, observation masking 80%, fast pruning 85%, aggressive masking 90%, full LLM compaction 99%
ArXiv 2603.05344 verified
"""

from .foundation import CompactionManager, CompactionAction

__all__ = ["CompactionManager", "CompactionAction"]
