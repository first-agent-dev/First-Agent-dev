"""
Telemetry — Minimal Structured Telemetry + Governed Mutation Foundation
Phase 0.5 — Not 100k raw logs, but structured summaries + artifact_id, offload full outputs to ArtifactStore
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class TelemetryEvent:
    run_id: str
    turn: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    model_id: str
    tool_name: str
    tool_args: dict[str, Any]
    permission_tier: str
    edited_files: list[str]
    test_result: str
    cache_hit: bool
    latency_ms: int
    branch_decision: str
    rejected_alternatives: list[str]
    human_approval: str | None
    artifact_id: str | None


class TelemetryLogger:
    """
    Structured telemetry logger, append-only, thread-safe, graceful degradation
    Store: .fa/telemetry/telemetry.jsonl, one line per tool call
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "telemetry.jsonl"
        self.lock = threading.Lock()
        self.path.touch(exist_ok=True)

    @staticmethod
    def _is_secret_key(k: str) -> bool:
        try:
            from fa.inner_loop.tools.bash_env import SECRET_NAME_RE

            return bool(SECRET_NAME_RE.search(k))
        except Exception:
            lk = k.lower()
            secret_suffixes = ("_key", "_token", "_secret", "_password", "_passwd")
            secret_exact = {"key", "token", "secret", "password", "api_key", "access_key"}
            if lk in secret_exact:
                return True
            if any(lk.endswith(suf) for suf in secret_suffixes):
                return True
            if lk in {"authorization", "cookie", "credential"}:
                return True
            return False

    def log(self, event: TelemetryEvent) -> None:
        try:
            sanitized_args: dict[str, Any] = {}
            for k, v in event.tool_args.items():
                if self._is_secret_key(k):
                    sanitized_args[k] = "***REDACTED***"
                else:
                    if isinstance(v, str) and len(v) > 500:
                        sanitized_args[k] = v[:500] + "...[truncated]"
                    else:
                        sanitized_args[k] = v
            event.tool_args = sanitized_args

            line = json.dumps(asdict(event), ensure_ascii=False)
            if len(line) > 1000:
                if len(event.tool_args.get("command", "")) > 200:
                    event.tool_args["command"] = event.tool_args["command"][:200] + "...[truncated]"
                line = json.dumps(asdict(event), ensure_ascii=False)
                if len(line) > 1000:
                    line = line[:997] + "..."
                    if not line.endswith("}"):
                        line = line.rsplit(",", 1)[0] + "}"

            with self.lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            print(f"WARNING: Telemetry log failed {e}, continuing")

    def query(
        self, tool_name: str | None = None, test_result: str | None = None
    ) -> list[TelemetryEvent]:
        results: list[TelemetryEvent] = []
        with self.lock:
            if not self.path.exists():
                return results
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if tool_name is not None and data.get("tool_name") != tool_name:
                            continue
                        if test_result is not None and data.get("test_result") != test_result:
                            continue
                        results.append(TelemetryEvent(**data))
                    except Exception:
                        continue
        return results


CHANGE_CONTRACT_TEMPLATE = """
# Change Contract for Harness Mutation

## Which component modified
- e.g., src/fa/inner_loop/tools/run_bash.py, src/fa/memory/fts_index.py

## Which failure mode it targets
- e.g., missing dependencies, weak tests, hallucinated APIs, flaky sandboxes

## What improvement it predicts
- e.g., median tokens ↓20%, tool-calls ↓30%, cache hit ratio ↑15%

## Which invariants it must preserve
- e.g., ADR-10 I-1, ADR-11 Level-0 TCB stdlib-only, ADR-12 secret isolation

## Which evaluation can falsify it
- e.g., mini eval-harness 5 tasks before/after

## How it can be rolled back
- e.g., git revert commit abc

## HITL required?
- Yes if alters permission boundaries, network access, credential handling
- No if only retrieval policy, context packing

## Evidence
- telemetry.jsonl run_ids: [...]
- blackboard entries: [...]
- artifact_ids: [...]
"""
