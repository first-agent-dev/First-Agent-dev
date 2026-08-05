"""S13.6 — live conformance executor (C1) + `fa conformance --provider` (C2).

The live executor composes each CONF case into a real RequestInfo and drives it
through a ProviderChain. This is tested offline with a fake chain (no real HTTP /
keys), proving:
- the executor maps a composed ConfCase to a RequestInfo with the right messages;
- a 429 on the chain surfaces as RateLimitError (so the runner resumes);
- the `fa conformance --provider` CLI path runs the live matrix via an injected
  transport/secrets (C2).

**Tests labelled per tests-writing skill:** C1 (live executor with a fake chain) +
C2 (CLI wiring with injected transport/secrets).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from fa.providers.conformance import ConfCase, _case_to_request, make_live_executor
from fa.providers.live_runner import RateLimitError


class _FakeChain:
    """Minimal ProviderChain stand-in: records requests, returns a canned response."""

    def __init__(
        self,
        *,
        raise_429: bool = False,
        raise_exhausted: bool = False,
        text: str = "ok",
    ) -> None:
        self.requests: list[Any] = []
        self._raise_429 = raise_429
        self._raise_exhausted = raise_exhausted
        self._text = text
        self.config = SimpleNamespace(name="test-model")

    def request(self, request: Any) -> tuple[Any, str, list[Any]]:
        self.requests.append(request)
        if self._raise_429:
            from fa.providers.errors import ProviderTransientError

            raise ProviderTransientError("429 rate limited", status=429, kind="rate_limited")
        if self._raise_exhausted:
            from fa.providers.errors import ProviderChainExhaustedError

            raise ProviderChainExhaustedError("all chain entries failed", attempts=[], logical_call_id="x")
        return SimpleNamespace(text=self._text, in_tokens=10, out_tokens=5), "logical-1", []


def _mk_case(case: int) -> ConfCase:
    return ConfCase(case=case, name=f"CONF-{case}", role="coder", task="a task")


def test_case_to_request_uses_composer() -> None:
    """C1 — a ConfCase becomes a RequestInfo that mirrors the real production request.

    CONF-8 discipline: a live run must exercise the EXACT request FA sends, so the
    composer's prompt-cache extras and the driver's temperature/max_tokens defaults
    are present — not a bare RequestInfo.
    """
    case = _mk_case(1)
    req = _case_to_request(case, model_slug="test-model")
    assert req.model_slug == "test-model"
    assert req.messages[-1]["role"] == "user"
    # The composer's prompt-cache extras are present (so a live run exercises
    # whether the provider accepts them — this is how NVIDIA's 400 surfaced).
    assert "prompt_cache_key" in req.extras
    assert "prompt_cache_retention" in req.extras
    # Driver defaults mirror production (coder role => 0.2, matching the CLI).
    assert req.max_tokens == 64000
    assert req.temperature == 0.2


def test_live_executor_drives_chain_and_reports_tokens() -> None:
    """C1 — the live executor calls the chain and returns a row with tokens."""
    chain = _FakeChain(text="hello")
    execute = make_live_executor(chain)
    row = execute(_mk_case(1), "run-1")
    assert row["case"] == 1
    assert row["ok"] is True
    assert row["model"] == "test-model"
    assert row["in_tokens"] == 10
    assert row["out_tokens"] == 5
    assert len(chain.requests) == 1


def test_live_executor_maps_429_to_rate_limit_error() -> None:
    """C1 — a 429 on the chain surfaces as RateLimitError (so the runner resumes)."""
    chain = _FakeChain(raise_429=True)
    execute = make_live_executor(chain)
    with pytest.raises(RateLimitError):
        execute(_mk_case(1), "run-1")


def test_cmd_conformance_live_provider_with_injected_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 — `fa conformance --provider X` runs the live matrix with injected secrets.

    Uses a fake transport that returns a canned 200 so no real HTTP fires, and a
    temp models.yaml with a coder role. The CLI must run the live matrix and print
    CONF rows.
    """
    from fa.cli import _cmd_conformance, build_parser
    from fa.providers.base import TransportResponse

    # Minimal models.yaml with a coder role.
    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "mistral"
  chain:
    - provider: openrouter
      model: "test-model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_KEY
""",
        encoding="utf-8",
    )

    class _FakeTransport:
        def post(self, url: str, **kw: Any) -> TransportResponse:
            del url, kw
            return TransportResponse(
                status=200,
                body={"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    args = build_parser().parse_args(["conformance", "--provider", "openrouter", "--config", str(models)])
    code = _cmd_conformance(args, transport=_FakeTransport(), secrets={"TEST_KEY": "k"})
    assert code == 0
    out = buf.getvalue()
    assert "live run" in out
    assert "CONF-1" in out or "CONF-" in out


def test_live_executor_records_chain_exhaustion_as_case_failure() -> None:
    """C1 — a chain-exhausted case is recorded, not a matrix crash.

    This is the user's `fa conformance --provider` failure mode: all chain entries
    failed for a case, and the executor used to re-raise ProviderChainExhaustedError,
    aborting the whole matrix with a traceback. It must instead record a per-case
    ok=False row so the matrix completes and shows WHICH case failed.
    """
    chain = _FakeChain(raise_exhausted=True)
    execute = make_live_executor(chain)
    row = execute(_mk_case(1), "run-1")
    assert row["ok"] is False
    assert "chain_exhausted" in row["error"]
    assert row["case"] == 1


def test_live_executor_re_raises_unknown_infra_error() -> None:
    """C1 — a non-request-shape, non-exhaustion error still propagates (not swallowed)."""
    from fa.providers.errors import ProviderAuthError

    chain = _FakeChain()

    def boom(request: Any) -> tuple[Any, str, list[Any]]:
        del request
        raise ProviderAuthError("401", status=401)

    chain.request = boom  # type: ignore[method-assign]
    execute = make_live_executor(chain)
    with pytest.raises(ProviderAuthError):
        execute(_mk_case(1), "run-1")


def test_cmd_conformance_live_renders_fail_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2 — a live FAIL row is rendered with its reason, so it is diagnosable.

    Regression for the user's run: all 7 CONF cases FAILed against nvidia_build
    but the CLI printed only "FAIL model=..." with no reason. The reason must be
    surfaced so an operator can see WHY a case failed (e.g. a provider 400).
    """
    from fa.cli import _cmd_conformance, build_parser
    from fa.providers.base import TransportResponse
    from fa.providers.errors import ProviderRequestShapeError

    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "mistral"
  chain:
    - provider: openrouter
      model: "test-model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_KEY
""",
        encoding="utf-8",
    )

    class _FakeTransport:
        def post(self, url: str, **kw: Any) -> TransportResponse:
            del url, kw
            # A 400 that the chain maps to ProviderRequestShapeError.
            raise ProviderRequestShapeError(
                "request_shape_error: status=400 body={'error': {'message': 'Unsupported parameter(s)'}}",
                status=400,
            )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    args = build_parser().parse_args(["conformance", "--provider", "openrouter", "--config", str(models)])
    code = _cmd_conformance(args, transport=_FakeTransport(), secrets={"TEST_KEY": "k"})
    assert code == 0
    out = buf.getvalue()
    # The FAIL reason is surfaced, not an opaque "FAIL".
    assert "FAIL" in out
    assert "Unsupported parameter(s)" in out
