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
    """Implements standing instruction pinning to eliminate Governance Decay.

    Hashes are recalculated on every refresh and embedded into the extracted
    text as deterministic integrity markers. The buffer always reflects the
    current on-disk state of pinned files: changed files reload, disappeared
    files are removed from the cache and warned about.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = Path(workspace_root).resolve()
        # Standing target files that contain critical constraints.
        self.target_files = [
            "AGENTS.md",
            "knowledge/llms.txt",
            "llms.txt",
        ]
        self._cache: dict[str, str] = {}
        self._hashes: dict[str, str] = {}

    def refresh(self) -> None:
        """Scan pinned files and replace the cache with current on-disk state."""
        previous_hashes = dict(self._hashes)
        previous_paths = set(self._cache)
        new_cache: dict[str, str] = {}
        new_hashes: dict[str, str] = {}

        for rel_path in self.target_files:
            fp = self.workspace_root / rel_path
            if not fp.is_file():
                if rel_path in previous_paths:
                    logger.warning("Pinned file disappeared mid-session and will be omitted: %s", rel_path)
                continue
            try:
                content = fp.read_text(encoding="utf-8", errors="ignore")
                content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
                if rel_path in previous_hashes and previous_hashes[rel_path] != content_hash:
                    logger.warning(
                        "Pinned file changed hash and will be reloaded: %s %s -> %s",
                        rel_path,
                        previous_hashes[rel_path],
                        content_hash,
                    )
                new_cache[rel_path] = content
                new_hashes[rel_path] = content_hash
            except OSError as exc:
                logger.warning("Failed to read pinned file %s: %s", rel_path, exc)

        self._cache = new_cache
        self._hashes = new_hashes

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
