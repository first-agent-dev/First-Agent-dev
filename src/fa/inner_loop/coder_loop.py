"""LLM-driven coder loop (M-8) — the missing LLM ↔ tools bridge.

This is the v0.1 acceptance surface for ``fa run``. It bridges the
:class:`fa.providers.chain.ProviderChain` (which makes the LLM call
and handles per-provider fallback) and
:func:`fa.inner_loop.loop.run_session` (which dispatches tool calls
through the HookRegistry). Without this bridge ``run_session``
consumes only pre-built ``ToolCall`` sequences and the substrate is
undrivable by a real model — see ``release-roadmap-post-m2.md`` §M4.

Per-turn loop (one iteration === one LLM round-trip):

1. Dispatch ``BEFORE_LLM_CALL`` middleware (ObserverMiddleware in
   v0.1; LLM-using GuardMiddleware would require family-disjoint
   plumbing through the chain, deferred to M5+).
2. Build a :class:`fa.providers.base.RequestInfo` from the running
   message list plus the mechanically-projected tool spec list.
3. Call ``provider_chain.request(req)`` — the chain handles
   per-attempt fallback and cooldown bookkeeping internally,
   returning a :class:`fa.providers.base.ResponseInfo` plus per-
   attempt trace records.
4. Dispatch ``AFTER_LLM_CALL`` middleware.
5. Append the assistant turn (text + tool_calls) to the message
   list AND to events.jsonl as a ``model_msg`` row.
6. If the response carries tool_calls: parse each (closed-set JSON
   decode, no LLM judgement), build a :class:`ToolCall` per entry,
   pass the whole batch through ``run_session`` so the existing
   BEFORE/AFTER_TOOL_EXEC hooks fire. Append each tool result as
   a ``tool``-role observation message for the next LLM turn.
7. If no tool_calls AND ``finish_reason`` is terminal → exit the
   loop with ``stopped_by_llm``.
8. If turn count reaches ``max_turns`` → exit with
   ``iteration_cap``.

Provider-agnostic by design: every adapter normalises ``tool_calls``
to the canonical OpenAI ``{id, type:"function", function:{name,
arguments:str}}`` shape (see
:func:`fa.providers.openai_compat._normalize_success` +
:func:`fa.providers.anthropic._normalize_success`). The driver's
:func:`fa.inner_loop.conversation_history.record_model_response` records the
response and parses that one shape only. After terminal-stop handling,
:mod:`fa.inner_loop.tool_turn` owns padding and model-facing tool-result
handoff; :mod:`fa.inner_loop.scope_turn` evaluates chat scope at turn
boundaries. :func:`fa.inner_loop.prompt_composer.compose_turn_request` builds
provider payloads, including compaction rebuilds. This driver retains turn
ordering, execution and session outcome.

Determinism guards (deep-dive §3 I-5 — deterministic post-LLM
filter): malformed ``arguments`` JSON, missing ``name`` field, or
non-mapping params collapse to a synthetic ``ToolCall`` whose
registry validation produces the canonical ``invalid_params``
error row rather than the driver itself raising. The LLM sees the
error on the next turn and can correct.

References:
- knowledge/adr/ADR-9-llm-provider-client.md §2 (chain runtime),
  §4 (Tier-1 / Tier-2 observability), §5 (canonical request /
  response shapes).
- knowledge/adr/ADR-8-hook-registry.md §1 (lifecycle order),
  §3 (first-deny short-circuit + GuardMiddleware contract).
- knowledge/adr/ADR-7-inner-loop-tool-registry.md §2 (ToolSpec /
  ToolCall / ToolResult contract), §7 (events.jsonl kinds),
  §Amendment 2026-05-20 rule 2 (max_iterations from
  ~/.fa/config.yaml, never code constants).
- knowledge/research/fa-abc-synthesis-deep-dive-2026-05.md §3
  I-2 (A-bucket residue), I-4 (typed loop-state ownership),
  I-5 (deterministic post-LLM filter).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final

from fa.inner_loop.artifacts import ArtifactStore
from fa.inner_loop.budget_effects import (
    emit_context_warn as _emit_context_warn,
)
from fa.inner_loop.budget_effects import (
    record_budget_pressure as _record_budget_pressure,
)
from fa.inner_loop.budget_effects import (
    record_compaction_pressure as _record_compaction_pressure,
)
from fa.inner_loop.budget_turn import classify_budget as classify_budget
from fa.inner_loop.compaction.compaction_turn import run_stage2_masking, run_stage3_compaction
from fa.inner_loop.conversation_history import (
    _assert_tool_pairing_invariant as _assert_tool_pairing_invariant,
)
from fa.inner_loop.conversation_history import (
    record_model_response,
    restore_conversation_history,
)
from fa.inner_loop.expansion import (
    ExpansionState,
    difficulty_to_level,
)
from fa.inner_loop.hooks.base import HookPayload, HookRegistry, LifecyclePoint
from fa.inner_loop.hooks.loop_guard import (
    LOOP_GUARD_REASON_PREFIX as LOOP_GUARD_REASON_PREFIX,
)
from fa.inner_loop.injections import (
    CODER_SLICE_CEREMONY,
    InjectionModes,
    is_active,
    is_observed,
    mode_for,
)
from fa.inner_loop.loop import StopInfo, run_session
from fa.inner_loop.path_risk import (
    default_scope_risk_config,
    load_scope_risk_config,
)
from fa.inner_loop.prompt import (
    render_tool_specs,
)
from fa.inner_loop.registry import ToolCall, ToolRegistry, ToolResult
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.scope_turn import evaluate_scope_turn
from fa.inner_loop.state import EventLog, SessionState, _now_iso_z
from fa.inner_loop.tool_turn import (
    _failed_tool_names,
    append_tool_turn_messages,
    prepare_continuing_tool_results,
)
from fa.inner_loop.tool_turn import (
    _handle_terminal_tool_stop as _handle_terminal_tool_stop,
)
from fa.inner_loop.tool_turn import (
    _pad_unexecuted_tool_results as _pad_unexecuted_tool_results,
)
from fa.inner_loop.tool_turn import (
    _redact as _redact,
)
from fa.observability.redaction import SecretRedactor
from fa.output import EventBus, OutputEvent
from fa.providers.base import RequestInfo, ResponseInfo
from fa.providers.chain import ProviderChain
from fa.providers.errors import (
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
)
from fa.providers.types import ChainAttemptRecord

logger = logging.getLogger(__name__)

_DEFAULT_PINNED_BUFFER = object()

# Default LLM-turn cap. Distinct from :attr:`RuntimeLimits.max_iterations`
# which counts *tool calls* across one ``run_session`` invocation; one
# LLM turn may emit multiple tool calls so the two caps are
# independent. Anchored at 16 — small enough to bound runaway loops on
# a confused model, large enough that a multi-step UC1 demo
# (read → write → verify → run) completes without truncation.
DEFAULT_MAX_TURNS = 16

# ``finish_reason`` values that signal the LLM intends to end its turn
# cleanly (not via iteration cap, not via content_filter / length cap).
# Both adapters normalise into one of these per
# :data:`fa.providers.anthropic._STOP_REASON_MAP`.
_TERMINAL_FINISH_REASONS: frozenset[str] = frozenset({"stop", "end_turn"})

# No default sampling temperature is forced. Modern reasoning/thinking models
# lock temperature/top_p (they are rejected or silently ignored), so FA omits
# them from the wire by default. A role that wants explicit sampling opts in via
# `sampling: {temperature, top_p}` in models.yaml (ADR-9 §Amendment 2026-07-23);
# the chain resolves those per-role defaults and the adapter omits the fields
# when they are None (see openai_compat.py). Retry-time T=1.0 is a *retry*
# policy owned by the FailureClassifierObserver (ADR-7 rule 3), not a first-attempt
# default.

# Default max output tokens per turn. Sized for modern long-context reasoning
# models (e.g. the Fireworks lineup in models.yaml.example) so multi-tool-call
# turns and long reasoning are not truncated; a runaway emission still surfaces
# via the ``abnormal_stop:length`` outcome.
DEFAULT_MAX_TOKENS = 64000


def _usage_event_content(response: ResponseInfo) -> dict[str, int]:
    return {
        "input_tokens": response.in_tokens,
        "cache_read_input_tokens": response.cache_read_input_tokens,
        "cache_creation_input_tokens": response.cache_creation_input_tokens,
        "output_tokens": response.out_tokens,
    }


def _session_summary_content(
    totals: Mapping[str, int],
    n_turns: int,
    *,
    role: str,
    exit_code: int,
    stop_reason: str,
) -> dict[str, object]:
    """The durable end-of-run row: usage totals **and** the run's own decision.

    Q98 (operator, 2026-11-01) asked for one thing above all: "we must see
    success/error codes for every workflow stage in sequence, so the work can be
    traced back by status". Before this, the stage's decision existed only as a
    console line (``OK: stopped_by_llm``) and a ``global_history`` row that the
    workflow collapses into a single aggregate — a finished run left no per-stage
    code anywhere in its own artifacts. ``run_started`` already records the role,
    so one summary row per stage now carries the whole stage verdict, and
    ``fa stats`` reads it instead of inferring a clean stop.
    """
    cache_read = totals["cache_read_input_tokens"]
    cache_creation = totals["cache_creation_input_tokens"]
    input_tokens = totals["input_tokens"]
    uncached = max(input_tokens - cache_read - cache_creation, 0)
    denominator = cache_read + cache_creation + uncached
    cache_hit_ratio = (cache_read / denominator) if denominator else 0.0
    return {
        "n_turns": n_turns,
        "input_tokens": input_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
        "uncached_input_tokens": uncached,
        "output_tokens": totals["output_tokens"],
        "cache_hit_ratio": cache_hit_ratio,
        "role": role,
        "exit_code": exit_code,
        "stop_reason": stop_reason,
    }


#: Condensates injected by the coder-stage slice ceremony, in prompt order.
#: Purpose-built ``INJECT.md`` files (~70 lines each) rather than the full
#: ``SKILL.md`` bodies (734 + 867 lines), which would dominate the context
#: window. PLAN S5 / CT1.
CEREMONY_SKILLS: Final[tuple[str, ...]] = ("feature-planning", "tests-writing")


def should_inject_ceremony(role: str, turn: int, injection_modes: InjectionModes | None) -> bool:
    """True when THIS turn must carry the slice-ceremony payload.

    Extracted from the call site so the decision is testable directly. A test
    that re-implements the condition instead would keep passing while the
    production guard rotted -- the mutation run that motivated this extraction
    showed exactly that (mutants flipping `is_active` to `is_observed` and
    detaching the blocks both survived against a mirrored predicate).

    Three conditions, each load-bearing:

    * ``role == "coder"`` -- the ceremony is the coder's implementation
      protocol; injections.py role-gating already forces `off` elsewhere, but
      the site states it too so the payload branch is self-contained.
    * ``turn == 1`` -- the workflow dispatches one coder stage per slice, so
      the stage's first turn IS slice entry. Later turns must not resend a
      ~5 KB body every request.
    * mode is ``enforce`` -- ``observe`` deliberately does NOT inject; it only
      records that the trigger fired (ADR-10-I6 clause 4).
    """
    return role == "coder" and turn == 1 and is_active(injection_modes, CODER_SLICE_CEREMONY.name)


def _ceremony_blocks(workspace_root: Path) -> list[dict[str, Any]]:
    """Read the slice-ceremony condensates as composer-ready skill blocks.

    Advisory by contract: a missing or unreadable condensate is logged and
    skipped, never raised. The ceremony tells the model how to work; failing
    a real implementation run because a markdown file moved would be a far
    worse outcome than running without the reminder (plan G8: no new
    rejection surface).

    Returns the blocks that could be read, in :data:`CEREMONY_SKILLS` order,
    which may be empty.
    """
    blocks: list[dict[str, Any]] = []
    try:
        from fa.skills._inject import default_skills_root, read_skill_for_injection

        skills_root = default_skills_root(workspace_root)
        for skill_name in CEREMONY_SKILLS:
            result = read_skill_for_injection(skill_name, skills_root, file_name="INJECT.md")
            if result.warning is not None:
                logger.warning("slice ceremony: %s", result.warning)
            if result.block is not None:
                blocks.append(dict(result.block))
    except Exception as exc:  # noqa: BLE001 - advisory must never crash a run
        logger.warning("slice ceremony injection failed: %s", exc)
    return blocks


@dataclass(frozen=True)
class SessionOutcome:
    """Terminal state of a :func:`drive_session` invocation.

    Returned (never raised) so the CLI can render the outcome in the
    canonical OK/ERROR shape across every termination path:

    - ``exit_code == 0`` + ``stop_reason == "stopped_by_llm"``: LLM
      emitted a final message with no tool calls and a terminal
      ``finish_reason`` (the happy path).
    - ``exit_code == 1`` + ``stop_reason == "iteration_cap"``: the
      ``max_turns`` cap fired before the LLM signalled completion. Only
      this path — never a guard denial — carries this code.
    - ``exit_code == 1`` + ``stop_reason == "abnormal_stop:<reason>"``:
      the LLM stopped on ``length`` / ``content_filter`` without a
      tool call — terminal but abnormal.
    - ``exit_code == 1`` + ``stop_reason == "hook_deny:<point>"``: a guard
      denied at ``AFTER_TOOL_EXEC`` (or at a terminal ``BETWEEN_ROUNDS``
      gate). The results that turn executed stay in ``tool_results``; the
      point names which lifecycle gate stopped the run.
    - ``exit_code == 1`` + ``stop_reason == "loop_guard"``: ``LoopGuard``
      tripped (repeat / ping-pong breaker) and ended the session in-band.
      Distinct from ``hook_deny`` because it means "the model was looping",
      not "a policy said no".
    - ``exit_code == 2`` + ``stop_reason == "chain_exhausted"``: every
      provider in the chain failed; the chain raised
      :class:`fa.providers.errors.ProviderChainExhaustedError`.
    - ``exit_code == 2`` + ``stop_reason == "request_shape"``: a
      provider returned 400/422 (FA's request construction is wrong);
      the chain raised :class:`fa.providers.errors.ProviderRequestShapeError`.
    - ``exit_code == 130`` + ``stop_reason == "abnormal_stop:interrupt"``:
      the user sent ``KeyboardInterrupt`` (Ctrl+C) during a turn.
    """

    exit_code: int
    stop_reason: str
    turns: int
    final_text: str
    tool_results: tuple[ToolResult, ...] = field(default_factory=tuple)
    failed_tools: tuple[str, ...] = ()


# C901-baseline waiver (25>15): top-level session driver; decompose per
# loop-improvement-workplan BEFORE adding more branches.
def drive_session(
    task: str,
    *,
    provider_chain: ProviderChain,
    compactor_chain: ProviderChain | None = None,
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str = "coder",
    acting_family: str = "",
    limits: RuntimeLimits | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    system_prompt_extra: str = "",
    turn_context: str = "",
    scope_mode: str = "",
    # PLAN S5a: per-injection mode RESOLVERS for this stage, keyed by
    # injection name (fa.inner_loop.injections). Resolvers rather than strings
    # so the mode is read when it is needed, letting a config edit -- e.g. a
    # WebUI toggle -- take effect on the next turn without restarting the
    # agent. Deliberately separate from ``scope_mode``: reusing that would
    # switch on chat-only scope machinery (observed_tiers, next_level,
    # escalation events) as a side effect. ``None`` means "no injections",
    # which is what every existing caller gets.
    injection_modes: InjectionModes | None = None,
    initial_memory_summary: str = "",
    temperature: float | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    redactor: SecretRedactor | None = None,
    output: EventBus | None = None,
    pinned_buffer: Any = _DEFAULT_PINNED_BUFFER,
) -> SessionOutcome:
    """Drive an LLM-driven coder session to terminal state.

    Args:
        task: The user-supplied task description; injected as the
            first ``user`` message in the conversation.
        provider_chain: Configured chain for the acting role; the
            driver calls :meth:`ProviderChain.request` once per
            turn. The chain handles per-provider fallback and
            cooldown internally — the driver only sees the final
            outcome.
        registry: Tool registry; spec list rendered into the system
            prompt's tool-list slot once at the start of the
            session.
        hooks: Hook registry; dispatched at ``BEFORE_LLM_CALL`` /
            ``AFTER_LLM_CALL`` per turn AND at ``BETWEEN_ROUNDS`` /
            ``BEFORE_TOOL_EXEC`` / ``AFTER_TOOL_EXEC`` inside
            ``run_session`` per tool call.
        state: Session state; the driver writes ``user_msg`` /
            ``model_msg`` rows for LLM I/O, and ``run_session``
            writes ``tool_call`` / ``tool_result`` / ``hook_decision``
            rows for tool dispatch.
        role: Acting role label (``coder`` / ``planner`` / ``eval``);
            passed through to every HookPayload.
        acting_family: Acting-role model family for the
            family-disjoint LLM-using-middleware check; pass the
            ``family`` field from :attr:`ProviderChain.config` to
            keep the chain and the hook registry in sync.
        limits: Per-call runtime limits; defaults to
            :meth:`RuntimeLimits.anchored_defaults` (max_iterations=6).
            One ``run_session`` invocation per LLM turn means the
            tool-call cap applies per-turn, not per-session.
        max_turns: LLM-turn cap; defaults to :data:`DEFAULT_MAX_TURNS`.
        turn_context: Optional per-request advisory text (the chat role's
            scope estimate is the first consumer). Routed to the prompt's
            NON-cacheable block so it never enters the cache key. Content
            that varies per task must use this rather than
            ``system_prompt_extra``, which is hashed into the cacheable
            prefix via the AGENTS.md map.
        system_prompt_extra: Optional standing profile guidance added to the
            pinned governance block. Not for mutable resume/session context.
        initial_memory_summary: Optional mutable summary/history injected into
            the memory-summary plane before provider calls.
        temperature: Sampling temperature; ``None`` (default) means "omit" —
            the adapter sends no temperature/top_p, matching the thinking-model
            default. Pass an explicit value (or set role ``sampling:``) to opt in.
        max_tokens: Per-turn output token cap.

    Returns:
        :class:`SessionOutcome` describing the terminal state.

    Raises:
        ValueError: when ``state.log`` is None (the run-wide audit
            sink is the durable replay surface; silently None-ing
            it would lose audit rows — same fence as
            :func:`fa.inner_loop.loop.run_session`).
    """
    if state.log is None:
        raise ValueError(
            "SessionState.log must be set before drive_session. "
            "Fix: pass log=EventLog(path) when constructing SessionState, "
            "or let __post_init__ create one from the default path."
        )

    from fa.inner_loop.context import reset_current_session, set_current_session

    token = set_current_session(state)
    try:
        return _drive_session_inner(
            task,
            provider_chain=provider_chain,
            compactor_chain=compactor_chain,
            registry=registry,
            hooks=hooks,
            state=state,
            role=role,
            acting_family=acting_family,
            limits=limits,
            max_turns=max_turns,
            system_prompt_extra=system_prompt_extra,
            turn_context=turn_context,
            scope_mode=scope_mode,
            injection_modes=injection_modes,
            initial_memory_summary=initial_memory_summary,
            temperature=temperature,
            max_tokens=max_tokens,
            redactor=redactor,
            output=output,
            pinned_buffer=pinned_buffer,
        )
    finally:
        reset_current_session(token)


def _request_with_cooldown_retries(
    provider_chain: ProviderChain,
    request: RequestInfo,
    *,
    log: EventLog,
    output: EventBus | None,
    turn: int,
    max_turns: int,
) -> tuple[ResponseInfo, str, list[ChainAttemptRecord]]:
    """Retry one turn's exhausted provider chain while honoring cooldowns."""
    # --- Internal Retry Loop for Chain Exhaustion ---
    # S22: renamed from max_chain_retries to avoid collision with
    # the FeatureFlags field that controls session-level retry.
    # This is the per-turn retry: wait for cooldowns and retry the
    # same request. The session-level retry (FeatureFlags.max_chain_retries)
    # is in the outer ProviderChainExhaustedError handler.
    _per_turn_chain_retries = 3
    attempt_count = 0
    while True:
        try:
            return provider_chain.request(request)
        except ProviderChainExhaustedError as exc:
            attempt_count += 1
            if log is not None:
                for attempt in exc.attempts:
                    log.append(
                        actor="provider",
                        kind="provider_attempt",
                        content={
                            "provider": attempt.provider,
                            "slug": attempt.slug,
                            "status": attempt.status,
                            "ms": attempt.ms,
                            "error": attempt.error,
                            "logical_call_id": exc.logical_call_id,
                        },
                    )
            if attempt_count >= _per_turn_chain_retries:
                raise  # Break the while loop, letting the outer try/except catch it as norm

            now = time.time()
            active_cooldowns = [
                row.expires_at - now for key, row in provider_chain.cooldowns.items() if row.expires_at > now
            ]

            wait_s = max(1.0, min(active_cooldowns)) if active_cooldowns else 5.0

            # Protect tests from hanging without changing production
            # cooldown semantics. The runtime must honor the provider
            # chain's cooldown ledger on the AIO host; only pytest gets
            # the near-zero sleep shim so unit tests stay fast.
            import os

            if "PYTEST_CURRENT_TEST" in os.environ:
                wait_s = 0.01

            if output is not None:
                for _att in exc.attempts:
                    output.emit(
                        OutputEvent(
                            type="api_retry",
                            turn=turn,
                            max_turns=max_turns,
                            data={
                                "provider": _att.provider,
                                "status": _att.status,
                                "retry_after_s": int(wait_s),
                                "reason": _att.error or "unknown",
                            },
                        )
                    )
            time.sleep(wait_s)


def _stop_reason_for(stop: StopInfo) -> str:
    """Short, stable code for a terminal tool stop (the detail stays in the row).

    The durable ``run_stopped`` row written by ``run_session`` already carries the
    full reason; ``stop_reason`` is the code the CLI banner and the session
    summary need. ``iteration_cap`` is deliberately *not* an option here: that
    code means "the turn budget ran out", and reporting it for a guard denial is
    the misleading banner S12.7 recorded.
    """
    if stop.reason.startswith(LOOP_GUARD_REASON_PREFIX):
        return "loop_guard"
    return f"hook_deny:{stop.point}"


def _finish_no_tool_response(
    response: ResponseInfo,
    *,
    turn: int,
    max_turns: int,
    results: Sequence[ToolResult],
    log: EventLog,
    output: EventBus | None,
) -> SessionOutcome:
    """Classify a response with no tool calls, recording abnormal stops."""
    if response.finish_reason in _TERMINAL_FINISH_REASONS or not response.finish_reason:
        return SessionOutcome(
            exit_code=0,
            stop_reason="stopped_by_llm",
            turns=turn,
            final_text=response.text,
            tool_results=tuple(results),
        )

    # S17 LOGIC-10: abnormal finish reasons have actionable console guidance.
    if response.finish_reason == "length":
        hint = "Output truncated (finish_reason=length). Consider increasing max_tokens or simplifying the task."
    elif response.finish_reason == "content_filter":
        hint = (
            "Output blocked by content filter (finish_reason=content_filter). Review the prompt for policy violations."
        )
    else:
        hint = f"Unexpected finish_reason: {response.finish_reason}"
    if output is not None:
        output.emit(
            OutputEvent(
                type="loop_warn",
                turn=turn,
                max_turns=max_turns,
                data={"detector": "abnormal_stop", "message": hint},
            )
        )
    log.append(
        actor="runtime",
        kind="run_stopped",
        content={"reason": f"abnormal_stop:{response.finish_reason}"},
    )
    return SessionOutcome(
        exit_code=1,
        stop_reason=f"abnormal_stop:{response.finish_reason}",
        turns=turn,
        final_text=response.text,
        tool_results=tuple(results),
    )


def _drive_session_inner(  # noqa: C901 -- complexity from top-level loop, documented
    task: str,
    *,
    provider_chain: ProviderChain,
    compactor_chain: ProviderChain | None = None,
    registry: ToolRegistry,
    hooks: HookRegistry,
    state: SessionState,
    role: str = "coder",
    acting_family: str = "",
    limits: RuntimeLimits | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    system_prompt_extra: str = "",
    turn_context: str = "",
    scope_mode: str = "",
    injection_modes: InjectionModes | None = None,
    initial_memory_summary: str = "",
    temperature: float | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    redactor: SecretRedactor | None = None,
    output: EventBus | None = None,
    pinned_buffer: Any = _DEFAULT_PINNED_BUFFER,
) -> SessionOutcome:
    effective_limits = limits if limits is not None else RuntimeLimits.anchored_defaults()
    log = state.require_log()
    tool_payload = render_tool_specs(registry.specs())
    tool_defs_for_prompt = [dict(tool) for tool in tool_payload]
    artifact_store = ArtifactStore.from_event_log(log)

    from fa.memory.context_budget import ContextBudget, estimate_tokens
    from fa.memory.pinned_buffer import PinnedBuffer

    # G1 fix: direct access — ChainConfig always has both fields.
    # The old getattr+or pattern had a logic trap: `or 150000` silently
    # converted context_limit=0 to 150000. ChainConfig.validate() already
    # rejects context_limit <= 0 (chain.py:63), but the floor below is
    # defense-in-depth for misconfigured-but-positive values.
    context_limit = provider_chain.config.context_limit
    compaction_threshold = provider_chain.config.compaction_threshold

    # MIN_CONTEXT_LIMIT: below this, context budget is meaningless.
    # Catches typos like context_limit=100 (meant 100000).
    min_context_limit = 32_000
    if context_limit < min_context_limit:
        log.append(
            actor="runtime",
            kind="telemetry",
            content={"message": f"context_limit={context_limit} below floor {min_context_limit}, clamped"},
        )
        context_limit = min_context_limit

    # TODO: Adaptive context sizing — eventually derive context_limit from API response
    # metadata (model's actual context_window). ADR-17 §Option B point 5 describes the
    # target architecture. Current implementation uses static config from models.yaml.
    # See: knowledge/adr/ADR-17-context-management-and-compaction.md
    budget = ContextBudget(limit_tokens=context_limit, configured_threshold=compaction_threshold)
    active_pinned_buffer = (
        PinnedBuffer(state.workspace_root) if pinned_buffer is _DEFAULT_PINNED_BUFFER else pinned_buffer
    )

    usage_totals = {
        "input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "output_tokens": 0,
    }
    usage_turns = 0
    summary_written = False
    memory_summary, conversation_history = restore_conversation_history(log, initial_memory_summary)

    log.append(actor="user", kind="user_msg", content={"text": task})
    log.append(
        actor="runtime",
        kind="run_started",
        content={"role": role, "max_turns": max_turns, "temperature": temperature},
    )

    _session_start_mono = time.monotonic()
    # LOGIC-5: track the last budget ratio so finish() can compute
    # context_used_pct instead of hardcoding None.
    last_budget_ratio: float = 0.0

    # ── Output: session_start ──────────────────────────────────────────────
    if output is not None:
        output.emit(
            OutputEvent(
                type="session_start",
                max_turns=max_turns,
                data={"model": provider_chain.config.name, "role": role, "family": acting_family},
            )
        )

    collected_results: list[ToolResult] = []
    failed_tools: set[str] = set()
    turn = 0
    # S10 / CT2: expansion state for the chat role. Seeded from the
    # estimator's recommended_mode (difficulty -> level); rebuilt per turn
    # at the boundary. Path sets are the transaction read/write snapshots
    # carried forward for the H-reuse observation. Non-chat roles (no scope
    # mode) keep level 1 with no expansion advice — observations are only
    # wired for the chat path (CT2 scope note).
    _is_chat_role = role == "chat" and bool(scope_mode)
    _scope_tiers = load_scope_risk_config() if _is_chat_role else default_scope_risk_config()
    try:
        _seed_level = difficulty_to_level(scope_mode) if scope_mode else 1
    except ValueError:
        _seed_level = 1
    _expansion = ExpansionState(level=_seed_level)
    _active_skill_name: str = ""
    _exhausted_flag = False
    # Per-turn observation block. REBUILT (not appended) at every boundary so a
    # stale L2 line never survives L3. It is composed ON TOP of the caller's
    # turn_context (the S3 scope hint), which is session-constant and must be
    # preserved (RK-H) — the two strings only meet at the composer binding.
    observation_context = ""
    # Pairs produced during the previous turn's tool batch, evaluated at the
    # next boundary (F6: observations land in the NEXT request).
    _prev_calls: tuple[ToolCall, ...] = ()
    _prev_results: tuple[ToolResult, ...] = ()
    # S10.9 / CT-H3: delta gate for the durable near-miss telemetry
    # (expansion_observed) — one event per distinct policy-relevant evidence
    # tuple per run, never on a transition turn.
    _last_observed_evidence: tuple[tuple[str, object], ...] | None = None
    # S22: Session-level chain exhaustion counter for max_chain_retries guard.
    # Distinct from the inner per-turn retry loop (_per_turn_chain_retries):
    #   - Inner loop retries provider_chain.request() with cooldown waits
    #   - This counter retries the entire turn (continue back to while loop)
    #   - max_chain_retries (FeatureFlags, default=0) controls this counter
    #   - transport_retries (ChainEntry, models.yaml) controls per-provider HTTP retries
    chain_exhaustion_count = 0

    def record_usage(response: ResponseInfo) -> None:
        nonlocal usage_turns
        # Waiver: internal invariant (log attached before loop starts).
        assert log is not None  # noqa: S101
        row = _usage_event_content(response)
        log.append(actor="runtime", kind="usage", content=row)
        for key, value in row.items():
            usage_totals[key] += value
        usage_turns += 1

    def finish(outcome: SessionOutcome) -> SessionOutcome:
        nonlocal summary_written
        # Waiver: internal invariant (log attached before loop starts).
        assert log is not None  # noqa: S101
        if not summary_written:
            summary = _session_summary_content(
                usage_totals,
                usage_turns,
                role=role,
                exit_code=outcome.exit_code,
                stop_reason=outcome.stop_reason,
            )
            log.append(
                actor="runtime",
                kind="session_summary",
                content=summary,
            )
            summary_written = True
            # ── Output: session_end ────────────────────────────────────────
            if output is not None:
                output.emit(
                    OutputEvent(
                        type="session_end",
                        turn=outcome.turns,
                        max_turns=max_turns,
                        data={
                            "stop_reason": outcome.stop_reason,
                            "ok": outcome.exit_code == 0,
                            "turns": outcome.turns,
                            "wall_s": time.monotonic() - _session_start_mono,
                            "total_in": usage_totals.get("input_tokens", 0),
                            "total_out": usage_totals.get("output_tokens", 0),
                            "cache_hit_ratio": summary.get("cache_hit_ratio", 0.0),
                            "context_used_pct": round(last_budget_ratio * 100, 1),
                        },
                    )
                )

            # S9: Guardrail metrics for data-driven improvement (G9).
            # Incremental counting from EventLog.kind_counts, written at
            # session end via session_db.set_meta(). Never crash the session
            # for metrics — try/except with logging on failure.
            if state.session_db is not None and log is not None:
                try:
                    kind_counts = dict(log.kind_counts)
                    state.session_db.set_meta("kind_counts", kind_counts, _now_iso_z())
                    budget_breaches = kind_counts.get("context_budget_warn", 0) + kind_counts.get(
                        "context_budget_hard_stop", 0
                    )
                    state.session_db.set_meta("budget_threshold_breaches", budget_breaches, _now_iso_z())
                    state.session_db.set_meta("chain_exhaustion_events", log.chain_exhaustion_count, _now_iso_z())
                except Exception as exc:  # noqa: BLE001 # never crash at session end
                    logger.warning("session_meta write failed: %s", exc)

        return replace(outcome, failed_tools=tuple(sorted(failed_tools)))

    def finish_at(
        exit_code: int,
        stop_reason: str,
        *,
        final_text: str = "",
        extra_results: Sequence[ToolResult] = (),
    ) -> SessionOutcome:
        """The single way this driver ends a session.

        Every terminal branch used to spell out the same eight-line
        ``finish(SessionOutcome(...))`` with five fields, so the ONE thing that
        had to differ — the reason — was buried in boilerplate identical to its
        neighbours. That is not hypothetical: the terminal-stop branch reported
        ``iteration_cap`` for a guard denial and dropped the results it had
        executed, and it survived review because the block looked like all the
        others (S6-F5). Naming the call makes the difference visible and gives
        new exits no way to forget a field or bypass the summary guard.

        ``turns`` is always the current ``turn``; ``tool_results`` is everything
        collected so far plus whatever this turn executed (``extra_results``).
        """
        return finish(
            SessionOutcome(
                exit_code=exit_code,
                stop_reason=stop_reason,
                turns=turn,
                final_text=final_text,
                tool_results=(*collected_results, *extra_results),
            )
        )

    def _request_shape_failure(exc: ProviderRequestShapeError) -> SessionOutcome:
        """Log + emit + finish a request-shape failure (CT5 / I-50 / I-51).

        Shared by both the composition-time path (a dangling-tool or invalid
        message order raised locally before HTTP) and the provider-returned
        400/422 path, so an operator sees the same graceful `request_shape`
        exit-2 and the real provider/reason either way. Previously a
        composition-time failure (e.g. dangling tool_calls on resume) escaped as
        an uncaught ValueError traceback because it happened outside the
        provider-request try block.
        """
        log.append(
            actor="runtime",
            kind="run_stopped",
            content={"reason": "request_shape", "detail": str(exc)},
        )
        if output is not None:
            output.emit(
                OutputEvent(
                    type="api_retry",
                    turn=turn,
                    max_turns=max_turns,
                    data={
                        "provider": getattr(exc, "provider", None) or "unknown",
                        "status": exc.status,
                        "retry_after_s": 0,
                        "reason": f"request_shape_error: {exc}",
                    },
                )
            )
        return finish_at(2, "request_shape")

    while turn < max_turns:
        turn += 1
        # S10 / CT2: per-turn scope expansion boundary. Runs EVERY turn for
        # the chat role, BEFORE the compose call. Evidence is read from the
        # transaction read/write sets (git-truth via tools) plus the previous
        # turn's bash results; the observation is rebuilt by ASSIGNMENT (the
        # old S7 append is gone), so a stale L2 line never survives an L3
        # escalation. Effects land in the NEXT LLM request after this turn's
        # tool batch (F6) — there is no mid-turn injection.
        skill_block_for_request: list[dict[str, Any]] | None = None

        # PLAN S5 (G1/G2, CT3, P1-P3): coder-stage slice ceremony.
        #
        # Deliberately OUTSIDE the `_is_chat_role` branch below: that
        # predicate is about a different feature (chat scope expansion) and is
        # false for a workflow coder stage, so anything placed inside it is
        # dead code for this role (plan D1).
        #
        # Entry turn only. The workflow dispatches one coder stage per slice,
        # so turn 1 of the stage IS slice entry; later turns must not resend
        # the bodies, which is why this assigns rather than accumulates and
        # sits inside the turn loop, above the `_compose_request_payload`
        # re-definition that binds it as a default arg (plan F-3).
        if role == "coder" and turn == 1 and is_observed(injection_modes, CODER_SLICE_CEREMONY.name):
            enforcing = should_inject_ceremony(role, turn, injection_modes)
            ceremony_blocks = _ceremony_blocks(state.workspace_root) if enforcing else []
            if ceremony_blocks:
                skill_block_for_request = list(ceremony_blocks)
            # CT3 dual-write: telemetry in the SAME branch that injects, so
            # "the harness said it injected" and "the payload changed" cannot
            # drift apart. `observe` records the counterfactual and alters
            # nothing, which is what makes it a safe default (ADR-10-I6).
            log.append(
                actor="harness",
                kind="ceremony_injected",
                content={
                    "turn": turn,
                    "role": role,
                    "mode": mode_for(injection_modes, CODER_SLICE_CEREMONY.name),
                    "skills": list(CEREMONY_SKILLS) if enforcing else [],
                    "blocks": len(ceremony_blocks),
                },
            )

        if _is_chat_role:
            scope_turn = evaluate_scope_turn(
                state=state,
                scope_tiers=_scope_tiers,
                scope_mode=scope_mode,
                expansion=_expansion,
                active_skill_name=_active_skill_name,
                exhausted_flag=_exhausted_flag,
                previous_calls=_prev_calls,
                previous_results=_prev_results,
                last_observed_evidence=_last_observed_evidence,
                log=log,
                output=output,
                turn=turn,
                max_turns=max_turns,
            )
            _expansion = scope_turn.expansion
            _active_skill_name = scope_turn.active_skill_name
            _last_observed_evidence = scope_turn.last_observed_evidence
            render = scope_turn.render
            observation_context = render.turn_context
            # Append, never replace: ceremony may already have populated this.
            if render.skill_block is not None:
                skill_block_for_request = [*(skill_block_for_request or []), render.skill_block]
        # ── Output: turn_start ─────────────────────────────────────────────
        if output is not None:
            output.emit(
                OutputEvent(
                    type="turn_start",
                    turn=turn,
                    max_turns=max_turns,
                )
            )
        try:
            hooks.dispatch(
                LifecyclePoint.BEFORE_LLM_CALL,
                HookPayload(role=role, acting_family=acting_family),
            )
        except PermissionError as exc:
            log.append(
                actor="runtime",
                kind="run_stopped",
                content={
                    "reason": f"hook_deny:{LifecyclePoint.BEFORE_LLM_CALL.value}",
                    "detail": str(exc),
                },
            )
            # ── Output: hook_deny ──────────────────────────────────────────
            if output is not None:
                output.emit(
                    OutputEvent(
                        type="hook_deny",
                        turn=turn,
                        max_turns=max_turns,
                        data={"hook": "BEFORE_LLM_CALL", "reason": str(exc)},
                    )
                )
            return finish_at(1, f"hook_deny:{LifecyclePoint.BEFORE_LLM_CALL.value}")
        if __debug__:
            try:
                _assert_tool_pairing_invariant(conversation_history)
            except AssertionError:
                # A malformed *data* state (e.g. an interrupted prior stage whose
                # tool_call has no persisted tool_result) is a request-shape error,
                # not a code bug: fail gracefully as `request_shape` instead of
                # letting a dev-only assertion crash the CLI with a traceback. The
                # chain conformance (S13.4) is the authoritative pairing gate; this
                # catch keeps the dev assertion loud but non-fatal on bad data.
                return _request_shape_failure(
                    ProviderRequestShapeError(
                        "history pairing invariant violated: orphaned/duplicate tool calls in conversation history",
                        status=400,
                    )
                )

        # ── PinnedBuffer Every Turn (Phase 2 / PR 2) ────────────────────────
        try:
            if active_pinned_buffer is None:
                pinned_text = system_prompt_extra
            else:
                pinned_text = active_pinned_buffer.extract_pinned_content(extra_instructions=system_prompt_extra)
        except Exception as exc:  # noqa: BLE001 # graceful degradation
            logger.warning("PinnedBuffer update failed on turn %d: %s", turn, exc)
            pinned_text = system_prompt_extra

        # ── PromptComposer Sole Assembly Path (Phase 3 / PR 3) ──────────────
        from fa.inner_loop.prompt import _ROLE_PROMPTS, CODER_SYSTEM_PROMPT
        from fa.inner_loop.prompt_composer import compose_turn_request

        base_system = _ROLE_PROMPTS.get(role, CODER_SYSTEM_PROMPT)
        pinned_text_for_turn = pinned_text

        def _compose_request_payload(
            *,
            active_summary: str,
            observations: list[dict[str, Any]],
            base_system_value: str = base_system,
            pinned_text_value: str = pinned_text_for_turn,
            # S7 / CT10 -> S10 / CT2: bound as default args (B023 late-binding
            # pattern). The observation context is reassigned each turn by the
            # scope expansion boundary above, so a bare closure read would
            # capture the value at the LAST turn, not this one. The caller's
            # turn_context (S3 scope hint) is session-constant and preserved.
            turn_context_value: str = (
                f"{turn_context}\n\n{observation_context}".strip() if observation_context else turn_context
            ),
            # S10 / CT5 F3: the L2 skill block from this turn's boundary;
            # None on every non-entry turn. Bound as a default arg for the
            # same late-binding reason as turn_context_value.
            skills_conditional_value: list[dict[str, Any]] | None = skill_block_for_request,
        ) -> tuple[dict[str, Any], list[dict[str, Any]], Mapping[str, Any]]:
            return compose_turn_request(
                family=provider_chain.config.family,
                base_system=base_system_value,
                pinned_text=pinned_text_value,
                tool_defs=tool_defs_for_prompt,
                role=role,
                task=task,
                active_summary=active_summary,
                observations=observations,
                turn_context=turn_context_value,
                skills_conditional=skills_conditional_value,
            )

        try:
            _request_body, messages_payload, request_extras = _compose_request_payload(
                active_summary=memory_summary,
                observations=conversation_history,
            )
        except ProviderRequestShapeError as exc:
            # S13.4: a local conformance/composition failure (e.g. a dangling-tool
            # assistant-final history on resume, which used to escape as an uncaught
            # traceback) is a request-shape error: fail locally, before HTTP, as the
            # same graceful exit-2 the provider-returned 400 path produces.
            return _request_shape_failure(exc)

        # ── ContextBudget Gating (Phase 1 / PR 1) ───────────────────────────
        # S13: FAIL-CLOSED — context_budget_enabled defaults to True when flags unavailable
        budget_enabled = state.feature_flags.context_budget_enabled if state.feature_flags is not None else True

        if budget_enabled:
            usage = estimate_tokens(messages_payload, tool_payload)
            decision = budget.check(usage)
            # The decision, named. Effects below are unchanged and still read
            # `decision` / `last_budget_ratio`, so this hop adds no behaviour —
            # it gives the next slice a value to check the effects against, and
            # turns an unrecognised budget action into a loud error instead of a
            # silent fall-through.
            verdict = classify_budget(
                decision,
                stage2_threshold=budget.stage2_threshold,
                stage3_threshold=budget.stage3_threshold,
            )
            last_budget_ratio = verdict.ratio
            if verdict.action == "warn":
                logger.warning("ContextBudget Gating Warning: %s", verdict.message)
                # Durable row + console mirror live in budget_effects: this
                # verdict has no consequence for the session's fate, so it does
                # not need to sit inside the block that can end the run.
                _record_budget_pressure(
                    verdict,
                    turn=turn,
                    max_turns=max_turns,
                    log=log,
                    output=output,
                    compaction_enabled=False,
                )
            elif decision["action"] in {"stage2", "stage3"}:
                # S6: compaction_warning — single observation point for
                # compaction-level pressure. Fires in BOTH enabled and
                # disabled cases so the operator can always see when the
                # system detected pressure at compaction threshold,
                # regardless of whether compaction is actually enabled.
                # SSoT: threshold presence is the explicit compaction toggle;
                # its numeric value tunes the Stage 2 threshold. No second
                # boolean flag is consulted.
                compaction_enabled = compaction_threshold is not None

                _record_compaction_pressure(
                    verdict,
                    turn=turn,
                    max_turns=max_turns,
                    log=log,
                    output=output,
                    compaction_enabled=compaction_enabled,
                )

                logger.warning("compaction_enabled: %s, flags: %s", compaction_enabled, state.feature_flags)

                if not compaction_enabled:
                    if verdict.action == "stage2":
                        logger.warning(
                            "ContextBudget Stage 2 reached but compaction is disabled: %s",
                            verdict.message,
                        )
                        _record_budget_pressure(
                            verdict,
                            turn=turn,
                            max_turns=max_turns,
                            log=log,
                            output=output,
                            compaction_enabled=False,
                        )
                    else:
                        logger.warning("ContextBudget Gate Breach: Stage 3 reached! %s", decision["message"])
                        log.append(
                            actor="runtime",
                            kind="context_budget_hard_stop",
                            content=budget.hard_stop_row(usage, message=decision["message"]),
                        )
                        # context_budget_hard_stop → console context_warn (critical)
                        _emit_context_warn(
                            verdict,
                            output=output,
                            turn=turn,
                            max_turns=max_turns,
                            action="stage3",
                        )
                        log.append(
                            actor="runtime",
                            kind="run_stopped",
                            content={"reason": "context_budget_hard_stop", "turns": turn},
                        )
                        return finish_at(1, "context_budget_hard_stop", final_text=decision["message"])
                else:
                    # Stage-2 masking lives in compaction_turn: it owns its own rows,
                    # events and the one deliberate except that keeps the run alive.
                    stage2 = run_stage2_masking(
                        turn=turn,
                        max_turns=max_turns,
                        history=conversation_history,
                        memory_summary=memory_summary,
                        usage=usage,
                        budget=budget,
                        log=log,
                        output=output,
                        tool_payload=tool_payload,
                        compose_request=_compose_request_payload,
                        artifact_store=artifact_store,
                        recent_turns_to_keep=4,
                    )
                    if stage2.applied:
                        conversation_history = stage2.history
                        messages_payload = stage2.messages_payload
                        request_extras = stage2.request_extras
                        usage = stage2.usage
                        # Re-classify: after masking the decision is a different one, and
                        # every later read goes through the verdict. Q#4 lives here.
                        verdict = stage2.verdict
                        last_budget_ratio = verdict.ratio
                    # Guard on the verdict, not on the pre-masking decision: after
                    # stage-2 the decision has been re-derived, so reading the older
                    # name here would act on a stale value (Q#4's shape, one level up).
                    if verdict.action == "stage3":
                        # Stage-3 compaction, the anti-thrashing breaker and the exit
                        # decision live in compaction_turn: they own rows and events, but
                        # not how a session ends — they report it, and the driver performs it.
                        stage3 = run_stage3_compaction(
                            turn=turn,
                            max_turns=max_turns,
                            history=conversation_history,
                            memory_summary=memory_summary,
                            usage=usage,
                            budget=budget,
                            log=log,
                            output=output,
                            tool_payload=tool_payload,
                            compose_request=_compose_request_payload,
                            compactor_chain=compactor_chain,
                        )
                        if stage3.stopped:
                            # Q#4, applied to the exit itself: the percentage the
                            # session reports must describe the state the stop was
                            # decided on, not the one before compaction. Without
                            # this the summary printed the pre-compaction ratio
                            # (measured: 99% where the run died at 92%).
                            last_budget_ratio = stage3.verdict.ratio
                            return finish_at(1, "context_budget_hard_stop", final_text=stage3.stop_message)
                        if stage3.applied:
                            conversation_history = stage3.history
                            memory_summary = stage3.memory_summary
                            messages_payload = stage3.messages_payload
                            request_extras = stage3.request_extras
                            usage = stage3.usage
                            verdict = stage3.verdict
                            last_budget_ratio = verdict.ratio

        # Prompt-composer extras (``prompt_cache_key``, ``prompt_cache_retention``)
        # come from the request body builder. Per-provider fields (Mistral's
        # ``prediction``, ``reasoning_effort``, etc.) are no longer merged here —
        # ProviderChain.request() now merges each chain entry's OWN
        # ``provider_params`` per-entry (ADR-9 §Amendment 2026-07-23), so a
        # sibling entry for a different provider never sees another entry's
        # provider-specific fields.
        request = RequestInfo(
            model_slug=provider_chain.config.name,
            messages=tuple(messages_payload),
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tool_payload,
            extras=dict(request_extras),
        )

        try:
            response, _logical_id, _attempts = _request_with_cooldown_retries(
                provider_chain, request, log=log, output=output, turn=turn, max_turns=max_turns
            )

            if log is not None:
                for attempt in _attempts:
                    log.append(
                        actor="provider",
                        kind="provider_attempt",
                        content={
                            "provider": attempt.provider,
                            "slug": attempt.slug,
                            "status": attempt.status,
                            "ms": attempt.ms,
                            "error": attempt.error,
                            "logical_call_id": _logical_id,
                        },
                    )
                # Tier-1 observability rollup (ADR-9 Sec4): one row per
                # logical call, embedding the attempts list this loop just
                # wrote individually above. cost_usd is intentionally
                # OMITTED per BACKLOG I-33 -- no wired cost source exists
                # yet; a fake/None placeholder here would be worse than
                # absence (a consumer could mistake it for "free").
                log.append(
                    actor="provider",
                    kind="llm_call",
                    content={
                        "logical_call_id": _logical_id,
                        "role": role,
                        "model": provider_chain.config.name,
                        "family": acting_family,
                        "chain": [
                            {
                                "provider": attempt.provider,
                                "slug": attempt.slug,
                                "status": attempt.status,
                                "ms": attempt.ms,
                                "error": attempt.error,
                            }
                            for attempt in _attempts
                        ],
                        "in_tokens": response.in_tokens,
                        "out_tokens": response.out_tokens,
                        "wallclock_ms": sum(attempt.ms for attempt in _attempts),
                    },
                )
            record_usage(response)
            # ── Output: llm_response ───────────────────────────────────────
            if output is not None:
                _elapsed = int(_attempts[-1].ms if _attempts else 0)
                output.emit(
                    OutputEvent(
                        type="llm_response",
                        turn=turn,
                        max_turns=max_turns,
                        data={
                            "ms": _elapsed,
                            "in_tokens": response.in_tokens,
                            "out_tokens": response.out_tokens,
                            "cache_read": response.cache_read_input_tokens,
                            "cache_creation": response.cache_creation_input_tokens,
                            "tool_call_count": len(response.tool_calls),
                            "text": response.text if response.text else None,
                        },
                    )
                )
        except KeyboardInterrupt:
            log.append(
                actor="runtime",
                kind="run_stopped",
                content={"reason": "abnormal_stop:interrupt"},
            )
            return finish_at(130, "abnormal_stop:interrupt")
        except ProviderChainExhaustedError as exc:
            # The per-turn retry seam already persisted this exception's attempts.
            # Re-emitting them here would count the final attempt twice in stats.

            # S22: Session-level chain retry logic (CT13).
            # max_chain_retries (FeatureFlags, default=0 → fail-fast)
            # controls how many times to retry the ENTIRE turn after chain
            # exhaustion. This is DISTINCT from:
            #   - transport_retries (ChainEntry, models.yaml) — HTTP-level per-provider
            #   - _per_turn_chain_retries (inner while loop) — per-turn cooldown-wait retries
            # The session-level retry fires only after ALL entries are exhausted
            # AND the inner per-turn retries are spent.
            chain_exhaustion_count += 1
            if log is not None:
                log.chain_exhaustion_count += 1

            max_chain_retries = state.feature_flags.max_chain_retries if state.feature_flags is not None else 0
            if chain_exhaustion_count <= max_chain_retries:
                # Retry the entire provider chain — continue to next turn
                logger.info(
                    "Provider chain exhausted, session-level retry (%d/%d)",
                    chain_exhaustion_count,
                    max_chain_retries,
                )
                if output is not None:
                    for _att in exc.attempts:
                        output.emit(
                            OutputEvent(
                                type="api_retry",
                                turn=turn,
                                max_turns=max_turns,
                                data={
                                    "provider": _att.provider,
                                    "status": _att.status,
                                    "retry_after_s": 0,
                                    "reason": _att.error or "unknown",
                                },
                            )
                        )
                continue  # back to the top of while turn < max_turns

            # Max retries reached — session exits with chain_exhausted
            log.append(
                actor="runtime",
                kind="run_stopped",
                content={"reason": "chain_exhausted", "detail": str(exc)},
            )
            # ── Output: api_retry (all entries failed, no more retries) ────
            if output is not None:
                for _att in exc.attempts:
                    output.emit(
                        OutputEvent(
                            type="api_retry",
                            turn=turn,
                            max_turns=max_turns,
                            data={
                                "provider": _att.provider,
                                "status": _att.status,
                                "retry_after_s": 0,
                                "reason": _att.error or "unknown",
                            },
                        )
                    )
            return finish_at(2, "chain_exhausted")
        except ProviderRequestShapeError as exc:
            return _request_shape_failure(exc)
        try:
            hooks.dispatch(
                LifecyclePoint.AFTER_LLM_CALL,
                HookPayload(role=role, acting_family=acting_family),
            )
        except PermissionError as exc:
            log.append(
                actor="runtime",
                kind="run_stopped",
                content={
                    "reason": f"hook_deny:{LifecyclePoint.AFTER_LLM_CALL.value}",
                    "detail": str(exc),
                },
            )
            # Dual-write: emit hook_deny OutputEvent for AFTER_LLM_CALL path
            # (mirrors the BEFORE_LLM_CALL path at L559)
            if output is not None:
                output.emit(
                    OutputEvent(
                        type="hook_deny",
                        turn=turn,
                        max_turns=max_turns,
                        data={"hook": "AFTER_LLM_CALL", "reason": str(exc)},
                    )
                )
            return finish_at(1, f"hook_deny:{LifecyclePoint.AFTER_LLM_CALL.value}")

        tool_calls = record_model_response(response, conversation_history, log)

        if not tool_calls:
            return finish(
                _finish_no_tool_response(
                    response, turn=turn, max_turns=max_turns, results=collected_results, log=log, output=output
                )
            )

        # Capture log length BEFORE run_session so we only inspect
        # rows appended during this invocation, not stale rows from
        # earlier turns (cross-turn contamination guard).
        log_len_before = len(log.read_all()) if log is not None else 0
        turn_results = run_session(
            tool_calls,
            registry=registry,
            hooks=hooks,
            state=state,
            role=role,
            acting_family=acting_family,
            limits=effective_limits,
        )
        # S6-F4 / S12.7: only AFTER_TOOL_EXEC or a LoopGuard trip are
        # terminal; other BETWEEN_ROUNDS denials continue through padding.
        # Checked BEFORE the early `failed_tools` update below, because a
        # terminal stop must not run the padding/projection path — and because
        # this branch now owns the whole exit (see `_finish_terminal_tool_stop`).
        if _handle_terminal_tool_stop(turn_results.stop, state=state, output=output):
            # S6-F5: the results this turn really produced are part of the
            # outcome, and the stop carries the guard's own reason. Falling
            # through to the shared `iteration_cap` tail used to report a cap
            # that never fired and drop executed results from `tool_results`.
            assert turn_results.stop is not None  # noqa: S101 — _handle_* returned True
            return finish_at(1, _stop_reason_for(turn_results.stop), extra_results=turn_results.results)
        failed_tools.update(_failed_tool_names(tool_calls, turn_results.results))

        turn_results = prepare_continuing_tool_results(
            tool_calls,
            turn_results,
            state=state,
            log=log,
            log_len_before=log_len_before,
            limits=effective_limits,
            role=role,
            output=output,
        )
        failed_tools.update(_failed_tool_names(tool_calls, turn_results.results))
        collected_results.extend(turn_results)
        # S10 / CT2: remember THIS turn's (call, result) pairs; the next
        # turn's boundary evaluates them for the verify_failed trigger (F6 —
        # effects are visible at the next request, not mid-turn).
        _prev_calls = tuple(tool_calls)
        _prev_results = tuple(turn_results)
        _exhausted_flag = append_tool_turn_messages(
            tool_calls,
            turn_results,
            exhausted_flag=_exhausted_flag,
            log=log,
            output=output,
            turn=turn,
            max_turns=max_turns,
            registry=registry,
            conversation_history=conversation_history,
            redactor=redactor,
            artifact_store=artifact_store,
        )

    log.append(
        actor="runtime",
        kind="run_stopped",
        content={"reason": "iteration_cap", "turns": turn},
    )
    return finish_at(1, "iteration_cap")


__all__ = [
    "CEREMONY_SKILLS",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MAX_TURNS",
    "LOOP_GUARD_REASON_PREFIX",
    "SessionOutcome",
    "classify_budget",
    "drive_session",
    "should_inject_ceremony",
]
