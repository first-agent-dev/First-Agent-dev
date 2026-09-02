"""Durable artifact storage for payloads elided from model context."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from fa.inner_loop.state import EventLog

logger = logging.getLogger(__name__)

# S12.7 (CT7): the artifact id shape minted by ``put`` — and the ONLY shape
# ``get`` will ever touch. Matching this regex already rejects path-traversal
# and absolute "ids" by construction (no ``/``, no ``.``, fixed hex run).
_ARTIFACT_ID_PATTERN = re.compile(r"^tool-result-[0-9a-f]{16}$")


def _stable_json(value: Any) -> str:
    """Serialize arbitrary payloads deterministically enough for artifacts."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=repr)


class ArtifactStore:
    """Content-addressed artifact store scoped to one run.

    Tool results remain audit-visible through ``events.jsonl``. This store
    holds the same full payload when ``project_for_model`` has to elide it
    from the provider-visible message stream.
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def from_event_log(cls, log: EventLog) -> ArtifactStore:
        return cls(log.path.parent / "artifacts")

    def put(self, payload: Any) -> str:
        rendered = _stable_json(payload)
        digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        artifact_id = f"tool-result-{digest[:16]}"
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{artifact_id}.json"
        if not path.exists():
            path.write_text(rendered + "\n", encoding="utf-8")
        return artifact_id

    def get(self, artifact_id: str) -> Any | None:
        """Return the parsed payload for ``artifact_id``, or ``None``.

        S12.7 (CT7) guard complex, in order:

        1. **Id shape gate** — anything not matching
           ``^tool-result-[0-9a-f]{16}$`` returns ``None`` WITHOUT touching
           disk. Path-traversal (``../x``) and absolute (``/etc/…``) ids are
           rejected here by construction: the shape admits no separators.
        2. **Containment** — even for shape-valid ids the resolved path must
           stay under this store's root (defense in depth; symlinked roots
           included via ``resolve()``).
        3. **Fail-closed reads** — missing files return ``None``; unreadable
           or corrupt payloads return ``None`` with a WARNING (never a raise,
           never partial content).

        No existence oracle: every failure class looks identical to the
        caller, which surfaces one structured error (``artifact_not_found``)
        with steering.
        """
        if not isinstance(artifact_id, str) or not _ARTIFACT_ID_PATTERN.fullmatch(artifact_id):
            return None
        path = (self.root / f"{artifact_id}.json").resolve()
        if not path.is_relative_to(self.root.resolve()):
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            return json.loads(raw)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as exc:  # corrupt/unreadable -> fail closed
            logger.warning(f"artifact {artifact_id} unreadable or corrupt: {exc}")
            return None


__all__ = ["ArtifactStore"]
