"""Durable artifact storage for payloads elided from model context."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fa.inner_loop.state import EventLog


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


__all__ = ["ArtifactStore"]
