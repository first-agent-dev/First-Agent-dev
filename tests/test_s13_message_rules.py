"""S13.4 — ``MessageRules`` + conformance pass at the chain chokepoint.

Plan: ``worklogs/implementation-plans/PLAN-cli-trace-S13-multi-provider-conformance.md``
§S13.4.

**Why.** FA emits a provider-neutral message list (S13.3). But a conformance pass
at the single provider chokepoint (``chain.py:368``) is the safety net and
discovery instrument: it validates ordering/pairing per-provider and minimally
normalises sampling (I-48 ``top_p``), failing **locally before HTTP** (CT5) instead
of letting a strict provider reject the request. Rules are capability flags on
``ProviderSpec`` (D2), never provider-name branches.

**Tests labelled per tests-writing skill:**
- **C0p** — ``validate_message_order`` / ``validate_and_normalize`` matrix: each
  rule's default and effect (flag on/off, temperature/top_p interaction).
- **C0p** — registry wiring: ``ProviderSpec.rules`` set per adapter; a new
  ``ProviderSpec`` with no rules gets strict defaults (K6).
- **C1** — the chain chokepoint fails a strict-rule provider **locally** on an
  assistant-last / dangling-tool request BEFORE ``provider.request`` (assert no
  HTTP via a raising transport), and the attempt record carries the violation.

**Kill-checks:** K4 (dangling tool raises locally before HTTP); K6 (new
ProviderSpec defaults apply); the C1 test fails if the chain call-site or the
local-raise path is removed.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

from fa.providers.base import Provider, RequestInfo, ResponseInfo, TransportResponse
from fa.providers.chain import ChainConfig, ChainEntry, ProviderChain
from fa.providers.errors import ProviderRequestShapeError
from fa.providers.message_rules import (
    MessageRules,
    MessageRulesError,
    validate_and_normalize,
    validate_message_order,
)
from fa.providers.registry import PROVIDERS
from tests.test_s13_strict_transport import validate_message_order as oracle_validate

_FIXTURE = Path(__file__).parent / "fixtures" / "i50_resumed_assistant_last.json"


def _load_fixture() -> list[dict[str, Any]]:
    data = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return cast(list[dict[str, Any]], data)


# --- C0p: validate_message_order matrix --------------------------------------


def _m(
    role: str,
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {"role": role, "content": ""}
    if tool_calls is not None:
        d["tool_calls"] = tool_calls
    if tool_call_id is not None:
        d["tool_call_id"] = tool_call_id
    return d


def _tc(cid: str) -> dict[str, Any]:
    return {"id": cid, "function": {"name": "f", "arguments": "{}"}}


def test_assistant_final_rejected_when_not_allowed() -> None:
    msgs = [_m("user"), _m("assistant")]
    assert validate_message_order(msgs, allows_trailing_assistant=False)  # non-empty


def test_assistant_final_allowed_when_flag_set() -> None:
    msgs = [_m("user"), _m("assistant")]
    assert validate_message_order(msgs, allows_trailing_assistant=True) == []


def test_user_after_tool_rejected() -> None:
    msgs = [_m("user"), _m("assistant", tool_calls=[_tc("a1")]), _m("tool", tool_call_id="a1"), _m("user")]
    violations = validate_message_order(msgs, allows_trailing_assistant=True)
    assert any("user-after-tool" in v for v in violations)


def test_dangling_tool_call_rejected() -> None:
    msgs = [_m("user"), _m("assistant", tool_calls=[_tc("a1")])]
    violations = validate_message_order(msgs, allows_trailing_assistant=True)
    assert any("dangling tool_calls" in v for v in violations)


def test_valid_tool_final_ok() -> None:
    msgs = [_m("user"), _m("assistant", tool_calls=[_tc("a1")]), _m("tool", tool_call_id="a1")]
    assert validate_message_order(msgs, allows_trailing_assistant=True) == []


# --- C0p: validate_and_normalize (sampling) -----------------------------------


def _req(*, temperature: float | None = None, top_p: float | None = None) -> RequestInfo:
    # A valid, ordering-clean message list (ends on user) so the sampling
    # assertions exercise only the top_p rule, not ordering validation.
    return RequestInfo(
        model_slug="m",
        messages=(_m("user"), _m("assistant"), _m("user")),
        temperature=temperature,
        top_p=top_p,
    )


def test_top_p_one_when_greedy_inserted() -> None:
    rules = MessageRules(requires_top_p_one_when_greedy=True, allows_trailing_assistant=True)
    out = validate_and_normalize(_req(temperature=0.0), rules, effective_temperature=0.0)
    assert out.top_p == 1.0


def test_top_p_one_when_greedy_not_when_temp_nonzero() -> None:
    rules = MessageRules(requires_top_p_one_when_greedy=True, allows_trailing_assistant=True)
    out = validate_and_normalize(_req(temperature=0.5), rules, effective_temperature=0.5)
    assert out.top_p is None  # untouched


def test_top_p_one_when_greedy_not_when_flag_off() -> None:
    rules = MessageRules(allows_trailing_assistant=True)  # flag off
    out = validate_and_normalize(_req(temperature=0.0), rules, effective_temperature=0.0)
    assert out.top_p is None


def test_top_p_one_when_greedy_keeps_explicit() -> None:
    rules = MessageRules(requires_top_p_one_when_greedy=True, allows_trailing_assistant=True)
    out = validate_and_normalize(_req(temperature=0.0, top_p=0.9), rules, effective_temperature=0.0)
    assert out.top_p == 0.9  # explicit caller value wins


# --- C0p: registry wiring (K6) ------------------------------------------------


def test_openai_compat_allows_trailing_assistant() -> None:
    assert PROVIDERS["openrouter"].rules.allows_trailing_assistant is True


def test_mistral_and_anthropic_strict() -> None:
    assert PROVIDERS["mistral"].rules.allows_trailing_assistant is False
    assert PROVIDERS["anthropic"].rules.allows_trailing_assistant is False


def test_default_provider_spec_strict() -> None:
    # A ProviderSpec declared without rules must default to strict-safe values.
    from fa.providers.registry import ProviderSpec

    spec = ProviderSpec(factory=lambda _t: cast(Provider, None), adapter="x")
    assert spec.rules == MessageRules()


# --- C1: chain chokepoint fails locally before HTTP ---------------------------


class _FakeProvider:
    """Provider whose .request records whether it was EVER invoked."""

    name = "fake"
    invoked = False

    def request(
        self,
        request: RequestInfo,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        transport_retries: int,
        extra_headers: Mapping[str, str],
    ) -> ResponseInfo:
        del request, base_url, api_key, timeout_seconds, transport_retries, extra_headers
        self.__class__.invoked = True
        return ResponseInfo(text="ok", in_tokens=1, out_tokens=1, finish_reason="stop", tool_calls=())


def _chain_with(provider: str, request: RequestInfo) -> ProviderChain:
    del request
    entry = ChainEntry(
        provider=provider,
        model="m",
        base_url="https://example.invalid/v1",
        api_key_env="K",
        cooldown_seconds=0,
    )
    config = ChainConfig(role="coder", name="m", family="", chain=(entry,))

    def _factory(_entry: ChainEntry) -> Provider:
        return cast(Provider, _FakeProvider())

    return ProviderChain(config, provider_factory=_factory, env={"K": "k"})


def test_chain_fails_strict_provider_locally_before_http() -> None:
    """C1 — a strict provider (mistral) rejects assistant-last BEFORE provider.request.

    Asserts no HTTP: the fake provider's ``request`` is never invoked. This is the
    CT5 local-fail guarantee — the shape never reaches the wire.
    """
    _FakeProvider.invoked = False
    assistant_last = RequestInfo(
        model_slug="m",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "final plan"},
        ),
    )
    chain = _chain_with("mistral", assistant_last)
    with pytest.raises(MessageRulesError, match="last role"):
        chain.request(assistant_last)
    assert _FakeProvider.invoked is False, "provider.request must not be reached on a local violation"


def test_chain_passes_openai_compat_trailing_assistant() -> None:
    """C1 — the same assistant-last shape is allowed for an OpenAI-compat provider.

    Proves the rule is capability-driven, not a blanket rejection: the strict
    rule is per-provider (D2), and an OpenAI-shaped endpoint tolerates it.
    """
    _FakeProvider.invoked = False
    assistant_last = RequestInfo(
        model_slug="m",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "final plan"},
        ),
    )
    chain = _chain_with("openrouter", assistant_last)
    resp, _logical, _attempts = chain.request(assistant_last)
    assert resp.finish_reason == "stop"
    assert _FakeProvider.invoked is True


def test_chain_dangling_tool_fails_locally() -> None:
    """C1 — dangling tool_call_id fails locally (CT5/K4), before HTTP."""
    _FakeProvider.invoked = False
    req = RequestInfo(
        model_slug="m",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "", "tool_calls": [_tc("a1")]},
        ),
    )
    chain = _chain_with("mistral", req)
    with pytest.raises(MessageRulesError, match="dangling"):
        chain.request(req)
    assert _FakeProvider.invoked is False


def test_message_rules_violation_is_provider_request_shape_error() -> None:
    """C0p — MessageRulesError is a ProviderRequestShapeError subclass.

    This is what lets the local gate flow through the existing fail-fast path
    (coder-loop maps it to stop_reason="request_shape", exit 2) unchanged.
    """
    assert issubclass(MessageRulesError, ProviderRequestShapeError)


# --- C1: I-48 top_p reaches the wire through the real chain + Mistral adapter --


class _RecordingTransport:
    """Transport that records the outbound json_body and returns a 200."""

    def __init__(self) -> None:
        self.bodies: list[Mapping[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
        transport_retries: int,
    ) -> TransportResponse:
        del url, headers, timeout_seconds, transport_retries
        self.bodies.append(dict(json_body))
        return TransportResponse(
            status=200,
            body={"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
        )


def test_mistral_temp_zero_sends_top_p_one_on_wire() -> None:
    """C1 (I-48) — a mistral request at temperature=0 sends top_p=1 to the wire.

    Proves the S13.4b mechanism end-to-end: the registry activates
    ``requires_top_p_one_when_greedy`` on the ``mistral`` adapter, the chain
    chokepoint applies it, and the Mistral adapter serialises ``top_p=1`` into the
    HTTP body it would send. Kill-check: clearing the flag on the registry makes
    this fail (the body would omit top_p).
    """
    from fa.providers.mistral import MistralProvider

    transport = _RecordingTransport()
    entry = ChainEntry(
        provider="mistral",
        model="mistral-medium-2604",
        base_url="https://api.mistral.ai/v1",
        api_key_env="K",
        cooldown_seconds=0,
    )
    config = ChainConfig(role="coder", name="mistral-medium-2604", family="mistral", chain=(entry,))
    chain = ProviderChain(config, provider_factory=lambda _e: MistralProvider(transport), env={"K": "k"})

    request = RequestInfo(
        model_slug="mistral-medium-2604",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "p"},
            {"role": "user", "content": "continue"},
        ),
        temperature=0.0,
    )
    chain.request(request)

    assert len(transport.bodies) == 1
    body = transport.bodies[0]
    assert body["top_p"] == 1.0, f"mistral greedy request must send top_p=1, got {body}"


def test_mistral_temp_nonzero_does_not_force_top_p() -> None:
    """C1 (I-48) — at temperature != 0 the rule does not force top_p=1."""
    from fa.providers.mistral import MistralProvider

    transport = _RecordingTransport()
    entry = ChainEntry(
        provider="mistral",
        model="mistral-medium-2604",
        base_url="https://api.mistral.ai/v1",
        api_key_env="K",
        cooldown_seconds=0,
    )
    config = ChainConfig(role="coder", name="mistral-medium-2604", family="mistral", chain=(entry,))
    chain = ProviderChain(config, provider_factory=lambda _e: MistralProvider(transport), env={"K": "k"})

    request = RequestInfo(
        model_slug="mistral-medium-2604",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "p"},
            {"role": "user", "content": "continue"},
        ),
        temperature=0.5,
    )
    chain.request(request)

    assert len(transport.bodies) == 1
    body = transport.bodies[0]
    assert "top_p" not in body, f"non-greedy mistral request should not force top_p, got {body}"


# --- S13.4d: MessageRules hard gate -------------------------------------------
#
# The S13.1 strict-transport oracle (tests/test_s13_strict_transport.py) and the
# production MessageRules validator must AGREE for the same provider — otherwise
# the CI oracle and the live finalizer can contradict each other and K2 is
# vacuous. For a strict provider (allows_trailing_assistant=False), every shape
# the oracle rejects must also be rejected by the production validator, and vice
# versa.


def _valid_tool_final() -> list[dict[str, Any]]:
    return [
        {"role": "user", "content": "t"},
        {"role": "assistant", "content": "", "tool_calls": [_tc("a1")]},
        {"role": "tool", "tool_call_id": "a1", "content": "r"},
    ]


@pytest.mark.parametrize(
    "label,messages",
    [
        ("assistant-final plain", [_m("user"), _m("assistant")]),
        ("assistant-final with tool_calls", [_m("user"), _m("assistant", tool_calls=[_tc("a1")])]),
        (
            "user-after-tool",
            [_m("user"), _m("assistant", tool_calls=[_tc("a1")]), _m("tool", tool_call_id="a1"), _m("user")],
        ),
        ("dangling tool", [_m("user"), _m("assistant", tool_calls=[_tc("a1")])]),
        ("orphan tool result", [_m("user"), _m("tool", tool_call_id="ghost")]),
        ("valid tool-final", _valid_tool_final()),
        ("valid fresh user", [_m("user")]),
    ],
)
def test_s13d_oracle_and_production_validator_agree(label: str, messages: list[dict[str, Any]]) -> None:
    """C0p (S13.4d) — the strict oracle and the production validator agree.

    The S13.1 oracle (always-strict) and the production ``validate_message_order``
    with ``allows_trailing_assistant=False`` must yield the same valid/invalid
    verdict for every shape. A drift here would let CI pass a request the live
    finalizer rejects (or vice versa).
    """
    oracle_violations = oracle_validate(messages)
    production_violations = validate_message_order(messages, allows_trailing_assistant=False)
    assert (len(oracle_violations) > 0) == (len(production_violations) > 0), (
        f"[{label}] oracle={oracle_violations} production={production_violations}"
    )


def test_s13d_live_fixture_agreement() -> None:
    """C0p (S13.4d) — the live I-50 fixture is rejected by BOTH the oracle and production.

    The exact live failing shape must be flagged by the strict oracle AND the
    production validator with strict rules, so the two can never disagree on the
    defect this slice fixes.
    """
    fixture = _load_fixture()
    oracle_violations = oracle_validate(fixture)
    production_violations = validate_message_order(fixture, allows_trailing_assistant=False)
    assert oracle_violations  # oracle rejects it
    assert production_violations  # production rejects it
    assert any("last role" in v for v in oracle_violations)
    assert any("last role" in v for v in production_violations)


def test_s13d_flipping_config_cannot_override_strict_truth() -> None:
    """C0p (S13.4d / K2) — a wrong registry config cannot silence the strict truth.

    Even if ``allows_trailing_assistant`` were set True for a provider, the strict
    S13.1 oracle (which encodes the provider's actual serving rule for
    Mistral/Anthropic) must still reject an assistant-last request. This is what
    makes K2 non-vacuous: the registry rules cannot override the provider's truth.
    """
    assistant_last = [_m("user"), _m("assistant")]
    # Production validator with the (wrong) permissive flag would accept it:
    assert validate_message_order(assistant_last, allows_trailing_assistant=True) == []
    # But the strict oracle (provider truth) rejects it regardless:
    assert oracle_validate(assistant_last)  # non-empty violations


# --- S13.4d hardening: requires_user_after_tool is a live capability (Issue 1) ---


def test_user_after_tool_rejected_when_not_required() -> None:
    """The default (requires_user_after_tool=False) rejects user-after-tool."""
    msgs = [_m("user"), _m("assistant", tool_calls=[_tc("a1")]), _m("tool", tool_call_id="a1"), _m("user")]
    violations = validate_message_order(msgs, allows_trailing_assistant=True)
    assert any("user-after-tool" in v for v in violations)


def test_user_after_tool_allowed_when_required_by_provider() -> None:
    """CONF-6 capability: a provider that requires user-after-tool is not flagged."""
    msgs = [_m("user"), _m("assistant", tool_calls=[_tc("a1")]), _m("tool", tool_call_id="a1"), _m("user")]
    violations = validate_message_order(
        msgs,
        allows_trailing_assistant=True,
        requires_user_after_tool=True,
    )
    assert not any("user-after-tool" in v for v in violations)


# --- S13.5: fa conformance CLI command ------------------------------------------


def test_cmd_conformance_runs_offline() -> None:
    """C2 — `fa conformance` runs offline and prints the capability matrix.

    Exercises the CLI handler (not just the library) so the command's wiring and
    its no-truncation matrix render are verified.
    """
    import io
    import sys

    from fa.cli import _cmd_conformance, build_parser

    buf = io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sys, "stdout", buf)
        args = build_parser().parse_args(["conformance"])
        code = _cmd_conformance(args)
    assert code == 0
    text = buf.getvalue()
    for name in ("CONF-1", "CONF-2", "CONF-3", "CONF-4", "CONF-5", "CONF-6", "CONF-7"):
        assert name in text


def test_cmd_conformance_json_output() -> None:
    """C2 — `fa conformance --json` emits a valid JSON matrix."""
    import io
    import json as _json
    import sys

    from fa.cli import _cmd_conformance, build_parser

    buf = io.StringIO()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sys, "stdout", buf)
        args = build_parser().parse_args(["conformance", "--json"])
        code = _cmd_conformance(args)
    assert code == 0
    rows = _json.loads(buf.getvalue())
    assert len(rows) == 7
    assert all("ran" in r and "final_role" in r for r in rows)


# --- S13.7: NVIDIA prompt-cache capability (measured divergence) --------------


def test_nvidia_build_does_not_support_prompt_cache() -> None:
    """C0p — NVIDIA build rejects prompt-cache keys; it must be flagged.

    The registry records `supports_prompt_cache=False` for nvidia_build (a
    measured 400: `Unsupported parameter(s): prompt_cache_retention,
    prompt_cache_key`), unlike OpenRouter which shares openai_compat but accepts
    them. Capability flag, not a provider-name branch (D2).
    """
    from fa.providers.message_rules import MessageRules

    nvidia_rules = PROVIDERS["nvidia_build"].rules
    openrouter_rules = PROVIDERS["openrouter"].rules
    assert isinstance(nvidia_rules, MessageRules)
    assert nvidia_rules.supports_prompt_cache is False
    assert openrouter_rules.supports_prompt_cache is True


def test_validate_and_normalize_strips_prompt_cache_for_nvidia() -> None:
    """C0p — the conformance pass strips prompt-cache keys for a non-supporting provider.

    The composer always injects `prompt_cache_key`/`prompt_cache_retention`; for a
    provider that rejects them (NVIDIA), they must be removed before the wire,
    while everything else (e.g. provider_params) is preserved.
    """
    from fa.providers.message_rules import MessageRules, validate_and_normalize

    rules = MessageRules(supports_prompt_cache=False)
    request = RequestInfo(
        model_slug="nvidia/nemotron-3-ultra-550b-a55b",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "p"},
            {"role": "user", "content": "c"},
        ),
        extras={
            "prompt_cache_key": "fa-coder-abc",
            "prompt_cache_retention": "1h",
            "reasoning_budget": 16384,  # a provider_param that MUST survive
        },
    )
    out = validate_and_normalize(request, rules)
    assert "prompt_cache_key" not in out.extras
    assert "prompt_cache_retention" not in out.extras
    assert out.extras["reasoning_budget"] == 16384  # provider_params preserved


def test_validate_and_normalize_keeps_prompt_cache_for_openai_compat() -> None:
    """C0p — prompt-cache keys are preserved for supporting providers (cache-hit)."""
    from fa.providers.message_rules import MessageRules, validate_and_normalize

    rules = MessageRules(supports_prompt_cache=True)
    request = RequestInfo(
        model_slug="openrouter/model",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "p"},
            {"role": "user", "content": "c"},
        ),
        extras={"prompt_cache_key": "fa-coder-abc", "prompt_cache_retention": "1h"},
    )
    out = validate_and_normalize(request, rules)
    assert out.extras["prompt_cache_key"] == "fa-coder-abc"
    assert out.extras["prompt_cache_retention"] == "1h"


def test_nvidia_wire_body_omits_prompt_cache_keys() -> None:
    """C1 — a real nvidia_build chain request reaches the wire WITHOUT prompt-cache keys.

    End-to-end through ProviderChain + OpenAICompatProvider (recording transport):
    the composer's prompt_cache_key/retention (which the chain merges into
    extras) must be stripped by the conformance pass before the body is built —
    this is the exact 400 NVIDIA returns when they are present.
    """
    from fa.providers.openai_compat import OpenAICompatProvider

    transport = _RecordingTransport()
    entry = ChainEntry(
        provider="nvidia_build",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key_env="K",
        cooldown_seconds=0,
    )
    config = ChainConfig(role="coder", name="nemotron-3-ultra-550b", family="nemotron", chain=(entry,))
    chain = ProviderChain(config, provider_factory=lambda _e: OpenAICompatProvider(transport), env={"K": "k"})

    request = RequestInfo(
        model_slug="nemotron-3-ultra-550b",
        messages=(
            {"role": "user", "content": "t"},
            {"role": "assistant", "content": "p"},
            {"role": "user", "content": "c"},
        ),
        extras={
            "prompt_cache_key": "fa-coder-abc",
            "prompt_cache_retention": "1h",
            "reasoning_budget": 16384,  # a provider_param that must survive
        },
    )
    chain.request(request)

    assert len(transport.bodies) == 1
    body = transport.bodies[0]
    assert "prompt_cache_key" not in body, body
    assert "prompt_cache_retention" not in body, body
    assert body["reasoning_budget"] == 16384  # provider_param preserved
    assert body["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
