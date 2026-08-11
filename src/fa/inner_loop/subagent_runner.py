"""
SubagentRunner — stateless subagents with filtered history, JSON envelope validation, proxy_token foundation
ADR-14, ADR-15, Phase 1 Foundation: uses extracted SubagentEnvelope, spawn limit via SessionState

Prior art:
- OpenAI Sandbox Agents as Tools custom_output_extractor JSON
- Copilot CustomAgents isolated context
- LangChain subagents pattern supervisor maintains context, subagents stateless isolated

Design: Main holds PTY stateful, sub stateless subprocess.run isolated, structured JSON via fastjsonschema
Phase 3: filtered history task + 5 relevant files via fs_search (files-mode FTS) not full parent 124 steps,
scrubbed env extra_allow X_FA_PROXY_TOKEN foundation per-subagent random, worklog aggregation
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import fastjsonschema  # type: ignore[import-untyped]

from fa.inner_loop.subagent_envelope import (
    SubagentEnvelope,
    validate_envelope,
    write_envelope_artifact,
)

if TYPE_CHECKING:
    from fa.observability.redaction import SecretRedactor

logger = logging.getLogger(__name__)


class SubagentRunner:
    """
    Stateless subagent runner with filtered history, JSON envelope, proxy_token foundation
    Phase 1: spawn limit enforced via SessionState counter (not instance counter), filtered history
    Phase 3: filtered history via build_filtered_history (transaction.read_set/write_set
    + fs_search FTS fallback)
    """

    def __init__(
        self,
        session_root: Path,
        proxy_token: str | None = None,
        timeout: int = 30,
        limits: Any | None = None,  # RuntimeLimits
        redactor: SecretRedactor | None = None,
    ):
        self.session_root = Path(session_root).resolve()
        self.proxy_token = proxy_token
        self.timeout = timeout
        self.validator = validate_envelope
        self.limits = limits
        # S6.5 / S6-F7 (Q25 option (i)). Optional: an unconfigured caller
        # degrades to "no masking", never to a crash.
        self.redactor = redactor
        self._instance_spawn_count = 0

    def _mask(self, text: str) -> str:
        """Mask configured secrets in captured subagent output.

        Applied ONCE, at the capture boundary in :meth:`run_stateless`, because
        every downstream writer derives from that single string: ``summary``,
        the ``stdout`` field, the ``.fa/subagents/<id>.json`` artifact,
        ``worklog.md``, ``.fa/worklog-detailed.md``, and the ``EventLog`` trace
        (via ``ToolResult.result = envelope.to_json()``). Masking here fixes all
        of them at once and makes it structurally hard for a new writer to
        reopen the hole; masking per-writer would leave some uncovered.

        ``worklog.md`` matters most: it is **not** gitignored (``.gitignore:14``
        is ``.fa/*``, which covers the artifact and ``worklog-detailed.md`` but
        not ``worklog.md``), so before this slice a failing subagent that
        printed a token wrote it into a committable file.

        Limit, stated plainly rather than implied away: this masks *configured*
        secrets and their base64/URL-encoded forms. It cannot mask a credential
        the subagent's command itself materialises. Masking is a safety net,
        not a containment boundary.

        Relation to ADR-12. That ADR is explicit that ``SecretRedactor`` is a
        best-effort filter and **not** the boundary — the boundary is container
        separation (egress proxy) plus the scrubbed child env
        (``bash_env.build_scrubbed_env``), which is why the subagent does not
        inherit FA's provider keys at all. The model-facing channel has its own
        chokepoint (``coder_loop._redact``, ADR-12 B2), verified still to mask
        this payload independently of the call here. This masking therefore adds
        the *persistence* layer ADR-12 left uncovered — artifact, worklogs, trace
        — and is defense-in-depth on top of both, not a replacement for either.
        """
        if self.redactor is None:
            return text
        try:
            return self.redactor.redact(text)
        except Exception as exc:  # noqa: BLE001 # never let masking break the run
            # Fail CLOSED: if masking failed we cannot prove the text is clean.
            logger.warning("Subagent output redaction failed, withholding output: %s", exc)
            return "[output withheld: redaction failed]"

    def _get_limits(self) -> Any:
        if self.limits is not None:
            return self.limits
        try:
            from fa.inner_loop.runtime_limits import RuntimeLimits

            return RuntimeLimits.anchored_defaults()
        except Exception as exc:  # noqa: BLE001 # graceful degradation
            logger.warning(f"_get_limits failed: {exc}")
            return None

    def _resolve_max_spawns(self) -> int:
        """Resolve max spawns from FeatureFlags > RuntimeLimits > default 3."""
        try:
            from fa.inner_loop.context import get_current_session

            session = get_current_session()
            if session is not None:
                ff = session.feature_flags if session is not None else None
                if ff is not None:
                    ff_max = getattr(ff, "max_subagent_spawns_per_session", None)
                    if isinstance(ff_max, int) and ff_max >= 0:
                        return ff_max
        except Exception as exc:  # noqa: BLE001 # graceful fallback to defaults
            logger.warning("Feature flag resolution for max_subagent_spawns_per_session failed: %s", exc)

        limits = self._get_limits()
        if limits is not None:
            lim_max = getattr(limits, "max_subagent_spawns_per_session", None)
            if isinstance(lim_max, int) and lim_max >= 0:
                return lim_max
        return 3

    def _check_spawn_limit(self) -> None:
        """Enforce the session limit, falling back to an instance counter if needed."""
        try:
            from fa.inner_loop.context import get_current_session

            session = get_current_session()
        except Exception as exc:  # noqa: BLE001 - context lookup is a fallback boundary
            logger.warning("Failed to check SessionState spawn counter: %s, using instance counter", exc)
            session = None

        if session is not None:
            max_spawns = self._resolve_max_spawns()
            # V21: admission must be ONE atomic operation. The previous code
            # read the counter, compared it, then incremented — three steps
            # with no lock, so concurrent callers all observed the same
            # pre-increment value and were all admitted. Measured with a
            # counter whose read is not instantaneous (any DB- or IPC-backed
            # counter): 12 of 12 racing threads admitted under a limit of 3.
            #
            # ``try_reserve_subagent_spawn`` does the compare and the increment
            # while holding the session lock, so the decision and the effect
            # cannot be separated.
            try:
                reserved = session.try_reserve_subagent_spawn(max_spawns)
            except Exception as exc:
                # A counter that cannot be updated is not permission to spawn:
                # every later caller would read a stale count and be admitted,
                # i.e. the limit silently stops existing. Deny instead (V21).
                raise RuntimeError(
                    f"spawn_admission_failed: cannot reserve a subagent slot ({exc}). "
                    "Refusing the spawn rather than proceeding with an unenforced limit."
                ) from exc
            if not reserved:
                raise RuntimeError(
                    f"Subagent spawn limit {max_spawns} reached "
                    f"(current {session.get_subagent_spawns()}), "
                    "sequential subagent limit for v0.1 pair over autonomy"
                )
            return

        max_spawns = self._resolve_max_spawns()
        if self._instance_spawn_count >= max_spawns:
            raise RuntimeError(f"Subagent spawn limit {max_spawns} reached (instance counter)")
        self._instance_spawn_count += 1

    def _build_filtered_history(self, task: str) -> list[dict[str, str]]:
        """Build filtered history for subagent: task + 5 relevant files, not full parent 124 steps.

        Uses subagent_prompts.build_filtered_history if available, else fallback to task only.
        Token efficient <8000 chars, file-based minimal surface per Q2 decision (keep only file-based for v0.1).
        Optional blackboard plans behind flag blackboard.filtered_history_include_plans (default False).
        """
        try:
            from fa.inner_loop.context import get_current_session
            from fa.inner_loop.subagent_prompts import build_filtered_history

            session = get_current_session()
            # Check feature flag for including blackboard plans (Q2)
            include_plans = False
            try:
                if session is not None and session.feature_flags is not None:
                    include_plans = session.feature_flags.blackboard_filtered_history_include_plans
            except (AttributeError, TypeError) as exc:
                logger.warning("blackboard_filtered_history_include_plans flag check failed: %s", exc)

            # For v0.1 minimal surface, keep file-based only unless flag True
            # build_filtered_history already handles fallback chain:
            # transaction.read_set/write_set -> fs_search(task) files-mode limit 5 -> static fallbacks if <3 results
            history = build_filtered_history(task, session, self.session_root, limit=5)
            # If include_plans flag True, append latest 3 plan entries from blackboard (600 tokens)
            if include_plans:
                try:
                    bb = session.blackboard if session is not None else None
                    plans = bb.query(type="plan") if bb is not None else []
                    # Latest 3
                    for plan in plans[-3:]:
                        preview = (
                            f"Plan {plan.id} hash:{plan.content_hash[:8]} "
                            f"Goal:{str(plan.payload.get('Goal', ''))[:200]} "
                            f"Assumptions:{plan.assumptions}"
                        )
                        history.append({"role": "system", "content": preview})
                except Exception as exc:  # noqa: BLE001 # blackboard plans optional
                    logger.warning(f"failed to include blackboard plans in filtered history: {exc}")

            return history
        except Exception as exc:  # noqa: BLE001 # filtered history best-effort
            logger.warning(f"build_filtered_history failed: {exc}, using task only")
            return [{"role": "user", "content": f"Task: {task}"}]

    def _append_to_worklog(self, envelope: SubagentEnvelope) -> None:
        """Worklog aggregation: Goal, Evidence, Steps, Verification from JSONs for PR body.

        Writes to root worklog.md committed summary (Goal, Evidence, Steps + artifact_id + 500-char preview)
        and .fa/worklog-detailed.md gitignored detailed (full file paths, decisions, open questions).
        """
        try:
            # Use session_root parent if session_root is .fa or workspace.
            # For simplicity, use self.session_root / "worklog.md" if exists,
            # else Path.cwd() / "worklog.md"
            # Check which exists, prefer root of workspace (parent of .fa)
            candidates = [
                self.session_root.parent / "worklog.md"
                if self.session_root.name == ".fa"
                else self.session_root / "worklog.md",
                Path.cwd() / "worklog.md",
            ]
            worklog_path = None
            for cand in candidates:
                try:
                    if cand.parent.exists():
                        worklog_path = cand
                        break
                except Exception as exc:  # noqa: BLE001 # best-effort worklog candidate check
                    logger.warning(f"worklog candidate check failed for {cand}: {exc}")
                    continue
            if worklog_path is None:
                worklog_path = self.session_root / "worklog.md"

            # Sanitized summary: no secrets, 500-char preview
            summary = envelope.summary[:500] if envelope.summary else ""
            evidence = ", ".join(envelope.files_changed[:5]) if envelope.files_changed else "none"

            section = (
                f"\n## {envelope.task_id} {envelope.type} {envelope.verification[:20]}\n"
                f"- Goal: {envelope.goal}\n"
                f"- Evidence: {evidence}\n"
                f"- Steps: {summary[:200]}\n"
                f"- Verification: {envelope.verification}\n"
                f"- Risks: {', '.join(envelope.risks)}\n"
                f"- Artifact: .fa/subagents/{envelope.task_id}.json\n"
                f"- Duration: {envelope.duration_ms}ms\n"
            )

            try:
                with open(worklog_path, "a", encoding="utf-8") as f:
                    f.write(section)
            except Exception as exc:  # noqa: BLE001 # worklog append best-effort
                logger.warning(f"Failed to append to worklog.md {worklog_path}: {exc}")

            # Detailed gitignored .fa/worklog-detailed.md
            if self.session_root.name == ".fa":
                detailed_path = self.session_root / "worklog-detailed.md"
            else:
                detailed_path = self.session_root / ".fa" / "worklog-detailed.md"
            try:
                detailed_path.parent.mkdir(parents=True, exist_ok=True)
                with open(detailed_path, "a", encoding="utf-8") as f:
                    f.write(section + f"\n- Full envelope: {envelope.to_json()[:2000]}\n")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"Failed to append to detailed worklog {detailed_path}: {exc}")

        except Exception as exc:  # noqa: BLE001 # worklog aggregation best-effort
            logger.warning(f"append_to_worklog failed: {exc}")

    def run_stateless(
        self,
        task_id: str,
        command: str,
        role: str = "verifier",
        workdir: Path | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> SubagentEnvelope:
        """
        Stateless subprocess.run isolated, scrubbed env, no PTY state.
        Returns validated SubagentEnvelope.
        workdir: from WorktreeManager.create_subagent_workspace(task_id)
        Filtered history: not full parent 124 steps, only task + relevant files
        """
        self._check_spawn_limit()

        cwd = Path(workdir) if workdir else self.session_root
        if not cwd.exists() or not cwd.is_dir():
            raise RuntimeError(f"workdir {cwd} not exists (defensive check Gap 6)")

        # Build filtered history for logging / future LLM subagent use
        # For verifier bash tool, filtered history is logged but not used for command execution
        # For researcher websearch agent, filtered history would be injected as prompt
        try:
            filtered = self._build_filtered_history(task_id)
            # For v0.1, log filtered history length for observability
            total_chars = sum(len(m.get("content", "")) for m in filtered)
            logger.info(f"Filtered history for {task_id}: {len(filtered)} messages, total chars {total_chars}")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"filtered history build failed for {task_id}: {exc}")

        from .tools.bash_env import SECRET_NAME_RE, build_scrubbed_env

        extra_keys = frozenset((env_extra or {}).keys())
        env = build_scrubbed_env(os.environ, extra_allow=extra_keys)

        if env_extra:
            for k, v in env_extra.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    continue
                if SECRET_NAME_RE.search(k):
                    continue
                env[k] = v

        if self.proxy_token:
            env["X_FA_PROXY_TOKEN"] = self.proxy_token

        start = time.time()
        try:
            # intentional sandbox boundary ADR-6, scrubbed env
            completed = subprocess.run(  # noqa: S602
                command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
            output = (stdout + "\n" + stderr) if stderr else stdout
            if len(output) > 8000:
                output = output[:8000] + "\n...[truncated 8000]"
        except subprocess.TimeoutExpired as e:
            raw_stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            stdout = raw_stdout if e.stdout else ""
            exit_code = -1
            output = f"Timeout {self.timeout}s, partial:\n{stdout[:8000]}"

        # S6.5 / S6-F7 (Q25 option (i)): mask BEFORE the string reaches the
        # envelope, so every downstream writer inherits it. Both branches above
        # feed this — the timeout branch carries partial output and can leak
        # just as easily as the normal one.
        output = self._mask(output)
        duration_ms = int((time.time() - start) * 1000)

        envelope = SubagentEnvelope.from_verifier(
            task_id=task_id,
            exit_code=exit_code,
            stdout=output,
            duration_ms=duration_ms,
            role=role,
        )

        try:
            self.validator(asdict(envelope))
        except fastjsonschema.JsonSchemaValueException as exc:
            return SubagentEnvelope(
                task_id=task_id,
                type=role,
                goal=f"Verify {task_id}",
                exit_code=-1,
                summary=f"Envelope validation failed: {exc.message}",
                verification=f"validation error at {exc.path}",
                files_changed=[],
                patch_diff="",
                risks=["envelope validation failed"],
                open_questions=[],
                token_usage={},
                duration_ms=duration_ms,
                next_action="retry",
            )

        try:
            write_envelope_artifact(envelope, self.session_root)
        except Exception as exc:  # noqa: BLE001 - artifact write best-effort
            logger.warning(f"Failed to write subagent artifact for {task_id}: {exc}")

        # Worklog aggregation is a mirror/summary boundary; it must not erase a
        # valid subagent result when the worklog sink is unavailable.
        try:
            self._append_to_worklog(envelope)
        except Exception as exc:  # noqa: BLE001 - worklog is best-effort
            logger.warning("Failed to aggregate subagent worklog for %s: %s", task_id, exc)

        return envelope
