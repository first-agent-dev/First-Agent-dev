"""Standalone audit hygiene module (R-13).

Port of three Gortex audit primitives that work without the full
audit subsystem (deferred per `borrow-roadmap-2026-05.md` §R-15
in ``knowledge/research/``):

- :func:`classify_tokens` — conservative classifier for backticked
  tokens; ports Gortex ``internal/audit/tokens.go`` (156 LOC).
- :func:`build_suggestions` — turns a raw :class:`AuditReport`
  into 1-3 human-readable hints; ports Gortex
  ``internal/audit/audit.go:185-199``.
- :func:`default_config_paths` — canonical probe list for AI-agent
  config files (CLAUDE.md, AGENTS.md, …); ports Gortex
  ``internal/audit/discover.go`` (83 LOC).
"""

from __future__ import annotations

from fa.hygiene.discover import default_config_paths
from fa.hygiene.suggestions import AuditReport, build_suggestions
from fa.hygiene.tokens import TokenKind, classify_token, classify_tokens

__all__ = [
    "AuditReport",
    "TokenKind",
    "build_suggestions",
    "classify_token",
    "classify_tokens",
    "default_config_paths",
]
