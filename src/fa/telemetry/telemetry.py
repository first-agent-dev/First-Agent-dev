"""
Telemetry — Minimal Structured Telemetry + Governed Mutation Foundation
Phase 0.5 — Not 100k raw logs, but structured summaries + artifact_id, offload full outputs to ArtifactStore

Prior art: Paper §3.5.1 Deep Telemetry as Optimization Substrate, Paper §3.2.6 Context Compaction and State Offloading
Active context: compact summaries + resource identifiers, not raw logs (e.g., failing test name + key frames + suspected files + link to full log)
Durable: files, DBs, trace stores
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

@dataclass
class TelemetryEvent:
    run_id: str
    turn: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    model_id: str
    tool_name: str
    tool_args: Dict[str, Any]  # sanitized, no secrets
    permission_tier: str  # read, workspace, full
    edited_files: List[str]
    test_result: str  # PASS/FAIL
    cache_hit: bool
    latency_ms: int
    branch_decision: str  # e.g., "choose fs.grep over fs.read 10 files"
    rejected_alternatives: List[str]  # e.g., ["fs.read 10 files", "fs.grep"]
    human_approval: Optional[str]  # approved, rejected, policy exception
    artifact_id: Optional[str]  # reference to full output offloaded to ArtifactStore, not raw log

class TelemetryLogger:
    """
    Structured telemetry logger, append-only, thread-safe, graceful degradation
    Store: .fa/telemetry/telemetry.jsonl, one line per tool call, structured, not raw logs, <1k chars per line
    Offload full tool outputs to ArtifactStore content-addressed, keep 500-char preview + artifact_id in active context (ArXiv table)
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "telemetry.jsonl"
        self.lock = threading.Lock()
        self.path.touch(exist_ok=True)

    @staticmethod
    def _is_secret_key(k: str) -> bool:
        """Precise secret detection, reuse allowlist from bash_env.py."""
        try:
            from fa.inner_loop.tools.bash_env import SECRET_NAME_RE

            return bool(SECRET_NAME_RE.search(k))
        except Exception:
            # Fallback precise matching: suffix or exact, not substring "key" in "keyboard"
            lk = k.lower()
            # Exact suffixes that indicate secrets, avoid broad "key" substring
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
            # Sanitize tool_args: remove secrets via precise matching (Gap fix)
            sanitized_args = {}
            for k, v in event.tool_args.items():
                if self._is_secret_key(k):
                    sanitized_args[k] = "***REDACTED***"
                else:
                    # Also truncate very long values to keep line <1k
                    if isinstance(v, str) and len(v) > 500:
                        sanitized_args[k] = v[:500] + "...[truncated]"
                    else:
                        sanitized_args[k] = v
            event.tool_args = sanitized_args

            line = json.dumps(asdict(event), ensure_ascii=False)
            # Enforce <1k chars per line: re-trim tool_args if still large
            if len(line) > 1000:
                # Truncate summary fields, not break JSON entirely
                # Best-effort: shorten branch_decision and summary in tool_args
                # Keep line valid JSON by re-dumping after trimming
                if len(event.tool_args.get("command", "")) > 200:
                    event.tool_args["command"] = event.tool_args["command"][:200] + "...[truncated]"
                line = json.dumps(asdict(event), ensure_ascii=False)
                if len(line) > 1000:
                    line = line[:997] + "..."
                    # If we truncated JSON, ensure we still write something parseable?
                    # For v0.1 we accept truncated line with WARNING marker,
                    # but attempt to keep JSON valid by closing brace if needed
                    if not line.endswith("}"):
                        line = line.rsplit(",", 1)[0] + "}"

            with self.lock:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
        except Exception as e:
            # Graceful degradation: log WARNING and continue, not crash
            print(f"WARNING: Telemetry log failed {e}, continuing")

    def query(self, tool_name: str = None, test_result: str = None) -> List[TelemetryEvent]:
        results = []
        with self.lock:
            if not self.path.exists():
                return results
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if tool_name and data.get("tool_name") != tool_name:
                            continue
                        if test_result and data.get("test_result") != test_result:
                            continue
                        results.append(TelemetryEvent(**data))
                    except Exception:
                        continue
        return results

# Change Contract Template for Evolution Agent (Pillar 4)
# From Paper §5.2.3 Self-Evolving Harnesses without Regression: every proposed edit should carry change contract
CHANGE_CONTRACT_TEMPLATE = """
# Change Contract for Harness Mutation

## Which component modified
- e.g., src/fa/inner_loop/tools/run_bash.py, src/fa/memory/fts_index.py

## Which failure mode it targets
- e.g., missing dependencies, weak tests, hallucinated APIs, flaky sandboxes, over-permissive tool calls, premature termination, token cost

## What improvement it predicts
- e.g., median tokens / completed task ↓20%, tool-calls ↓30%, cache hit ratio ↑15%

## Which invariants it must preserve
- e.g., ADR-10 I-1 single-source-of-truth classifier, ADR-11 Level-0 TCB stdlib-only, ADR-12 secret isolation, ADR-7 §10 paired rows

## Which evaluation can falsify it
- e.g., mini eval-harness 5 tasks (read repo, fix bug, add test, refactor, code-review) before/after, median tokens, tool-calls, USD cost, test pass rate

## How it can be rolled back
- e.g., git revert commit abc, restore previous prompt template, restore previous tool schema

## HITL required?
- e.g., Yes if alters permission boundaries, network access, credential handling, deployment behavior, human-review requirements (per §3.5.3 Governed Harness Mutation)
- No if only retrieval policy, context packing, retry limits

## Evidence
- telemetry.jsonl run_ids: [...]
- blackboard entries: [...]
- artifact_ids: [...]
"""

# Example usage:
# logger = TelemetryLogger(Path(".fa/telemetry"))
# event = TelemetryEvent(run_id="abc", turn=1, prompt_tokens=1000, completion_tokens=200, cost_usd=0.01, model_id="claude-opus-4", tool_name="fs.read_file", tool_args={"path":"src/auth.py"}, permission_tier="read", edited_files=[], test_result="PASS", cache_hit=True, latency_ms=100, branch_decision="choose grep over read 10 files", rejected_alternatives=["read 10 files"], human_approval=None, artifact_id="tool-result-abc123")
# logger.log(event)
# Active context for LLM: compact summary + artifact_id, not raw log
# e.g., "Tool fs.read_file read src/auth.py, cache_hit True, artifact_id abc123, preview: ..."
