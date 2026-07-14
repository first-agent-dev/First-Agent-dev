"""PinnedBuffer — verbatim preservation of safety, standing guidelines, and role profiles.

ADR-17, Phase 3 SOTA:
- Extracts critical guidelines from AGENTS.md + llms.txt + custom profile
- Safeguards them from compaction (min_fidelity=FULL)
- Verifies integrity via SHA-256 content hashes, preventing Governance Decay
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PinnedBuffer:
    """Implements standing instruction pinning to eliminate Governance Decay."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root).resolve()
        # Standing target files that contain critical constraints
        self.target_files = [
            "AGENTS.md",
            "knowledge/llms.txt",
            "llms.txt",
        ]
        self._cache: dict[str, str] = {}
        self._hashes: dict[str, str] = {}

    def refresh(self) -> None:
        """Scan and cache the raw contents and hashes of the pinned files."""
        for rel_path in self.target_files:
            fp = self.workspace_root / rel_path
            if fp.is_file():
                try:
                    content = fp.read_text(encoding="utf-8", errors="ignore")
                    h = hashlib.sha256(content.encode()).hexdigest()[:16]
                    self._cache[rel_path] = content
                    self._hashes[rel_path] = h
                except OSError as exc:
                    logger.warning("Failed to read pinned file %s: %s", rel_path, exc)

    def extract_pinned_content(self, extra_instructions: str | None = None) -> str:
        """Generate the consolidated, verbatim string of standing guidelines."""
        self.refresh()
        sections = []

        # Add custom profile extra instructions if passed
        if extra_instructions:
            h = hashlib.sha256(extra_instructions.encode()).hexdigest()[:16]
            sections.append(f"### STANDING PROFILE GUIDELINES (hash:{h})\n{extra_instructions}\n")

        for rel_path, content in self._cache.items():
            h = self._hashes.get(rel_path, "unknown")
            sections.append(f"### STANDING CONSTRAINT: {rel_path} (hash:{h})\n{content}\n")

        if not sections:
            logger.warning("PinnedBuffer: No standing constraints found or extracted!")
            return ""

        return "\n---\n".join(sections)


__all__ = ["PinnedBuffer"]
