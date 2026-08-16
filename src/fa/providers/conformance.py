"""S13.5/S13.11 — offline matrix plus live exact-request qualification.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.5 / D4 / D5a.

**Why this lives in ``src/`` (not only ``tests/``).** The ``fa conformance`` CLI
command must run the offline matrix without importing test infrastructure, and
the matrix drives the REAL composer + REAL production validator. A capability
matrix that only the test-suite can build would be the S11 "instrument that
cannot run offline" trap inverted. The scenario definitions and matrix logic
therefore live here (production, importable by both the CLI and the test
package); ``tests/conformance/`` exercises them as the CI ratchet.

**What this is.** Drives FA's REAL composer (``build_prompt_parts_v2``) through
the REAL production validator (``fa.providers.message_rules.validate_message_order``)
and records a **capability matrix** — one row per CONF case — with a ``ran``
positive control so a green cell can never come from "never ran" (D5a rule 1).

**Matrix shape.** A JSON-serialisable list of rows:
``{case, name, ran, final_role, violations, ok, sizes}``. ``ok`` is
``ran and not violations``. CONF-7 rows carry ``sizes`` (cacheable/non_cacheable
byte counts) and are *recorded*, never pass/fail (D4).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from fa.inner_loop.prompt_composer import build_prompt_parts_v2, to_openai_request_v2
from fa.providers.base import RequestInfo
from fa.providers.live_runner import RateLimitError
from fa.providers.message_rules import validate_message_order


@dataclass
class ConfCase:
    """One conformance scenario: a request the composer must produce validly."""

    case: int  # stable CONF number (1..N) — used by the live runner's done_ids
    name: str
    role: str
    task: str
    observations: list[dict[str, Any]] = field(default_factory=list)
    # S13.11: canonical rendered tools for live-only CONF-8. The outer tuple
    # matches RequestInfo; default offline CONF-1..7 remain tool-free.
    tools: tuple[Mapping[str, Any], ...] = ()
    # CONF-5/6/7 are capability observations, not hard qualification rows.
    record_only: bool = False
    # CONF-7: whether to record per-component composition sizes.
    record_sizes: bool = False
    # CONF-5: allow the composed request to end on a trailing assistant (a
    # provider *tolerance* capability — recorded, not required).
    allow_trailing: bool = False


@dataclass
class ConfRow:
    """One matrix row."""

    case: int
    name: str
    ran: bool
    final_role: str
    violations: list[str] = field(default_factory=list)
    ok: bool = False
    sizes: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _compose(case: ConfCase) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Compose the request via the REAL composer; return (messages, sizes)."""
    parts, _key = build_prompt_parts_v2(
        base_system=f"base system for {case.role}",
        agents_md_map="agents map placeholder",
        tool_defs=[dict(tool) for tool in case.tools],
        role_id=case.role,
        task=case.task,
        observations=case.observations,
    )
    messages = list(parts.cacheable) + list(parts.non_cacheable)
    sizes = {
        "cacheable_bytes": _byte_len(parts.cacheable),
        "non_cacheable_bytes": _byte_len(parts.non_cacheable),
        "n_messages": len(messages),
    }
    return messages, sizes


def _byte_len(messages: list[dict[str, Any]]) -> int:
    return len(json.dumps(messages, ensure_ascii=False).encode("utf-8"))


def _run_case(case: ConfCase) -> ConfRow:
    try:
        messages, sizes = _compose(case)
    except Exception as exc:  # noqa: BLE001 — a composition failure is a recorded row
        return ConfRow(
            case=case.case,
            name=case.name,
            ran=True,
            final_role="<compose-error>",
            violations=[str(exc)],
            ok=False,
        )
    final_role = messages[-1].get("role", "") if messages else ""
    violations = validate_message_order(
        messages,
        allows_trailing_assistant=case.allow_trailing,
    )
    return ConfRow(
        case=case.case,
        name=case.name,
        ran=True,
        final_role=final_role,
        violations=violations,
        ok=not violations,
        sizes=sizes if case.record_sizes else {},
    )


def default_cases() -> list[ConfCase]:
    """The CONF-1..7 scenario definitions (add provider N+1 by extending here)."""
    return [
        # CONF-1 minimal completion: fresh history, ends on user.
        ConfCase(case=1, name="CONF-1 minimal completion", role="coder", task="add a docstring"),
        # CONF-2 single tool call round-trip: user -> assistant(tool) -> tool result.
        ConfCase(
            case=2,
            name="CONF-2 single tool call round-trip",
            role="coder",
            task="call a tool once",
            observations=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "c1", "function": {"name": "fs_read", "arguments": "{}"}}],
                },
                {"role": "tool", "tool_call_id": "c1", "content": "file contents"},
            ],
        ),
        # CONF-3 resumed transcript (the I-50 shape): history then new task.
        ConfCase(
            case=3,
            name="CONF-3 resumed transcript (I-50 shape)",
            role="coder",
            task="continue the work",
            observations=[
                {"role": "user", "content": "prior stage task"},
                {"role": "assistant", "content": "# Prior plan"},
            ],
        ),
        # CONF-4 multi-turn tool chain: two sequential calls, ends on tool.
        ConfCase(
            case=4,
            name="CONF-4 multi-turn tool chain",
            role="coder",
            task="do two things",
            observations=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "a", "function": {"name": "f", "arguments": "{}"}}],
                },
                {"role": "tool", "tool_call_id": "a", "content": "r1"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "b", "function": {"name": "g", "arguments": "{}"}}],
                },
                {"role": "tool", "tool_call_id": "b", "content": "r2"},
            ],
        ),
        # CONF-5 trailing-assistant tolerance (recorded, not required).
        ConfCase(
            case=5,
            name="CONF-5 trailing-assistant tolerance (recorded)",
            role="coder",
            task="",
            observations=[
                {"role": "user", "content": "t"},
                {"role": "assistant", "content": "final"},
            ],
            allow_trailing=True,
            record_only=True,
        ),
        # CONF-6 user-after-tool tolerance (recorded, not required).
        #
        # S13 live-fix: observations must not themselves contain a `user`
        # immediately after a `tool`. The composer's terminal-role rule
        # (S13.3) only reorders the TASK relative to observations; it does
        # not rewrite the caller-supplied observation sequence. CONF-6 is
        # intended to record whether the PROVIDER tolerates a `user` message
        # placed directly after a `tool` result; the composer's task-first
        # branch does exactly that when the last observation is a `tool`
        # (it inserts the task user-message FIRST in non_cacheable then
        # appends observations, which ends the list on `tool` — NOT on
        # `user`). So we instead build a tool round-trip followed by an
        # assistant turn, so the composer's terminal-role rule (assistant
        # plain-text final → task last) appends the new user task AFTER the
        # tool/assistant history, producing the exact user-after-tool
        # shape this case exists to exercise: [system…, assistant(tool_call),
        # tool, assistant, user(new task)].
        ConfCase(
            case=6,
            name="CONF-6 user-after-tool tolerance (recorded)",
            role="coder",
            task="another instruction",
            observations=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "x", "function": {"name": "f", "arguments": "{}"}}],
                },
                {"role": "tool", "tool_call_id": "x", "content": "r"},
                {"role": "assistant", "content": "intermediate reply"},
            ],
            record_only=True,
        ),
        # CONF-7 prompt-cache + composition: record sizes, never pass/fail.
        ConfCase(
            case=7,
            name="CONF-7 prompt-cache + composition (recorded sizes)",
            role="coder",
            task="a task with a moderately long instruction",
            observations=[{"role": "assistant", "content": "# Plan"}],
            record_only=True,
            record_sizes=True,
        ),
    ]


def production_request_profile_case(
    tools: tuple[Mapping[str, Any], ...],
) -> ConfCase:
    """Build live-only CONF-8 from the exact rendered production tool corpus."""

    names: set[str] = set()
    for tool in tools:
        function = tool.get("function")
        if not isinstance(function, Mapping):
            continue
        name = function.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    missing = sorted({"fs_search", "pr_prepare"} - names)
    if not tools or missing:
        detail = f"; missing required tools: {missing}" if missing else ""
        raise ValueError(f"CONF-8 exact production request profile requires non-empty tools{detail}")

    return ConfCase(
        case=8,
        name="CONF-8 exact production request profile",
        role="coder",
        task="Reply with exactly OK. Do not call a tool.",
        tools=tools,
    )


def run_conformance_matrix() -> list[dict[str, Any]]:
    """Run all CONF-1..7 scenarios and return the capability matrix as dicts."""
    rows: list[dict[str, Any]] = []
    for case in default_cases():
        row = _run_case(case)
        # CONF-7 is recorded, never pass/fail: force ok to a neutral "recorded".
        if case.record_sizes:
            row.ok = True
            row.violations = []
        rows.append(row.to_dict())
    return rows


def matrix_to_text(rows: list[dict[str, Any]]) -> str:
    """Render the matrix as a no-truncation text table."""
    lines = [f"{'case':<5} {'name':<40} {'ran':<4} {'final_role':<12} {'ok':<5} violations"]
    for row in rows:
        v = "; ".join(row["violations"]) if row["violations"] else "-"
        lines.append(
            f"{row['case']:<5} {row['name']:<40} {row['ran']!s:<4} {row['final_role']:<12} {row['ok']!s:<5} {v}"
        )
    return "\n".join(lines)


def _case_to_request(case: ConfCase, model_slug: str) -> RequestInfo:
    """Compose a ConfCase into a provider RequestInfo for a live call.

    Mirrors the REAL production driver (CONF-8 discipline: replay the exact
    request shape FA sends in production), NOT a bare RequestInfo. That means:
    - compose via ``build_prompt_parts_v2`` (the real composer),
    - then run through ``to_openai_request_v2`` so the composer's
      ``prompt_cache_key`` / ``prompt_cache_retention`` extras are present — a
      live run must exercise whether the provider accepts them (this is exactly
      how NVIDIA's rejection surfaced),
    - carry the driver's ``max_tokens`` (64000) default and omit
      ``temperature``/``top_p`` (the thinking-model default), which every
      provider-visible request does.
    """
    parts, _key = build_prompt_parts_v2(
        base_system=f"base system for {case.role}",
        agents_md_map="agents map placeholder",
        tool_defs=[dict(tool) for tool in case.tools],
        role_id=case.role,
        task=case.task,
        observations=case.observations,
    )
    openai_request = to_openai_request_v2(parts, _key)
    messages = tuple(openai_request["messages"])
    extras = dict(openai_request.get("extra_body") or {})
    return RequestInfo(
        model_slug=model_slug,
        messages=messages,
        max_tokens=64000,
        tools=case.tools,
        extras=extras,
    )


def make_live_executor(chain: Any, *, transient_sleep: float = 2.0) -> Callable[[ConfCase, str], dict[str, Any]]:
    """Build an ``execute`` callable for :func:`live_runner.run_matrix`.

    ``chain`` is a ``ProviderChain`` (or any object with a ``request(RequestInfo)``
    returning a ``ResponseInfo``). Each ConfCase is composed to a real request and
    driven through the chain; a 429 surfaces as :class:`RateLimitError` so the
    runner resumes. Returns a row dict with ``case``/``ok`` (and observed
    in/out tokens + the model slug, for the matrix).
    """

    def execute(case: ConfCase, run_id: str) -> dict[str, Any]:
        del run_id
        model_slug = chain.config.name if hasattr(chain, "config") else "model"
        request = _case_to_request(case, model_slug)
        from fa.providers.errors import ProviderChainExhaustedError, ProviderRequestShapeError

        last_exc: Exception | None = None
        response: Any = None
        for attempt_idx in range(3):
            try:
                response, _logical, _attempts = chain.request(request)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                is_429 = (
                    getattr(exc, "status", None) == 429
                    or getattr(exc, "kind", "") == "rate_limited"
                    or (
                        isinstance(exc, ProviderChainExhaustedError)
                        and any(
                            getattr(a, "status", None) == 429 or getattr(a, "error", "") == "rate_limited"
                            for a in getattr(exc, "attempts", ())
                        )
                    )
                )
                if is_429:
                    raise RateLimitError(f"429: {exc}") from exc
                is_transient = getattr(exc, "status", 0) in {500, 502, 503, 504} or (
                    isinstance(exc, ProviderChainExhaustedError)
                    and any(getattr(a, "status", 0) in {500, 502, 503, 504} for a in getattr(exc, "attempts", ()))
                )
                if is_transient and attempt_idx < 2:
                    if transient_sleep > 0:
                        time.sleep(transient_sleep * (attempt_idx + 1))
                    continue
                # A local conformance rejection (MessageRulesError, a
                # ProviderRequestShapeError) is a RECORDED capability result, not a
                # crash: the provider's strict validator rejects this shape. Return a
                # row with ok=False + the reason so the matrix completes and documents
                # it (CONF-6/5 style).
                if isinstance(exc, ProviderRequestShapeError):
                    return {
                        "case": case.case,
                        "name": case.name,
                        "record_only": case.record_only,
                        "ok": False,
                        "model": model_slug,
                        "error": f"request_shape: {exc}",
                        "in_tokens": None,
                        "out_tokens": None,
                    }
                break

        if last_exc is not None:
            # A chain exhaustion is a per-case failure too, not a matrix crash: the
            # provider (or every fallback) failed for this case. Record it so the
            # matrix completes and the operator sees WHICH case failed and why,
            # instead of a raw traceback aborting the whole run.
            if isinstance(last_exc, ProviderChainExhaustedError):
                # The generic message is "all N entries failed" — useless alone.
                # Surface the per-attempt provider status/error so the real cause
                # (e.g. a 400 body, a 429, a timeout) is diagnosable.
                detail = "; ".join(f"{a.provider}:{a.status} {a.error or ''}".strip() for a in last_exc.attempts)
                return {
                    "case": case.case,
                    "name": case.name,
                    "record_only": case.record_only,
                    "ok": False,
                    "model": model_slug,
                    "error": f"chain_exhausted: {last_exc} [{detail}]",
                    "in_tokens": None,
                    "out_tokens": None,
                }
            # Anything else is a real infra error (network, auth, unexpected): let
            # it propagate so it is not silently swallowed as a case result.
            raise last_exc
        has_content = bool(getattr(response, "text", None) or getattr(response, "tool_calls", ()))
        return {
            "case": case.case,
            "name": case.name,
            "record_only": case.record_only,
            "ok": case.record_only or has_content,
            "model": model_slug,
            "in_tokens": getattr(response, "in_tokens", None),
            "out_tokens": getattr(response, "out_tokens", None),
        }

    return execute


__all__ = [
    "ConfCase",
    "ConfRow",
    "_case_to_request",
    "default_cases",
    "make_live_executor",
    "matrix_to_text",
    "production_request_profile_case",
    "run_conformance_matrix",
]
