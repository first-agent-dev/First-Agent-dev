"""Bash sandbox gate for First-Agent (ADR-6 §Amendment 2026-05-20 Wave-1).

Three-layer hybrid security model ported from two open-source agents:

- **Layer 1 — pattern classifier** (no-LLM, zero-latency):
  ``classifier.classify_command`` categorises the command into one of
  ``BashCategory`` (read-only / git-write / package-install / dangerous /
  general-write). Port of Gortex ``internal/hooks/bash_classify.go``.

- **Layer 2 — per-command validators** (function-as-step, no LLM):
  ``validators.validate_*`` apply additional rules for sensitive commands
  (``rm``, ``chmod``, ``git``, ``pkill``, ``psql``). Port of Aperant
  ``apps/desktop/src/main/ai/security/bash-validator.ts``.

- **Layer 3 — path containment** (symlink-resolved):
  ``path_containment.is_contained`` checks any path-argument resolves
  inside the workspace base. Port of Aperant
  ``apps/desktop/src/main/ai/security/path-containment.ts``.

The top-level entry point is ``bash_gate.evaluate_bash`` which composes
the three layers and returns a ``BashGateDecision``. Capabilities are
gated by ``fa.config`` flags (ADR-6 §Amendment 2026-05-20 R-21 layer
already shipped in PR-2); the gate is the *runtime* arm.
"""

from fa.sandbox.bash_gate import BashGateDecision, evaluate_bash
from fa.sandbox.classifier import BashCategory, classify_command
from fa.sandbox.path_containment import (
    ContainmentResult,
    contains_traversal,
    is_contained,
)
from fa.sandbox.validators import ValidationResult, validate_command

__all__ = [
    "BashCategory",
    "BashGateDecision",
    "ContainmentResult",
    "ValidationResult",
    "classify_command",
    "contains_traversal",
    "evaluate_bash",
    "is_contained",
    "validate_command",
]
