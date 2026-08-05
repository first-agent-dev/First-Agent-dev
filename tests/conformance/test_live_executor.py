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

    def __init__(self, *, raise_429: bool = False, text: str = "ok") -> None:
        self.requests: list[Any] = []
        self._raise_429 = raise_429
        self._text = text
        self.config = SimpleNamespace(name="test-model")

    def request(self, request: Any) -> tuple[Any, str, list[Any]]:
        self.requests.append(request)
        if self._raise_429:
            from fa.providers.errors import ProviderTransientError

            raise ProviderTransientError("429 rate limited", status=429, kind="rate_limited")
        return SimpleNamespace(text=self._text, in_tokens=10, out_tokens=5), "logical-1", []


def _mk_case(case: int) -> ConfCase:
    return ConfCase(case=case, name=f"CONF-{case}", role="coder", task="a task")


def test_case_to_request_uses_composer() -> None:
    """C1 — a ConfCase becomes a RequestInfo with the composed messages."""
    case = _mk_case(1)
    req = _case_to_request(case, model_slug="test-model")
    assert req.model_slug == "test-model"
    # ends on a user message (valid for a strict provider)
    assert req.messages[-1]["role"] == "user"


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
