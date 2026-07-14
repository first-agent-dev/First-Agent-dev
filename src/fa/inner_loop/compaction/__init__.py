"""fa.inner_loop.compaction — foundation for ADR-17 progressive compaction

Current: Stage 1 only warning + artifact offload 8000 chars → scratch file + 500-char preview
Full progressive: warning 70%, observation masking 80%, full LLM compaction 90%
"""

from .compactor import (
    FullLLMCompactor,
    ObservationMasker,
    find_turn_boundary_backward,
    project_messages_after_mask,
)
from .foundation import CompactionAction, CompactionManager

__all__ = [
    "CompactionAction",
    "CompactionManager",
    "FullLLMCompactor",
    "ObservationMasker",
    "find_turn_boundary_backward",
    "project_messages_after_mask",
]
