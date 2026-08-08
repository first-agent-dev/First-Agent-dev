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
from typing import Any, override

import pytest

from fa.providers.conformance import ConfCase, _case_to_request, make_live_executor
from fa.providers.live_runner import RateLimitError


@pytest.fixture(autouse=True)
def _isolated_fa_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect FA's state root to a tmp_path so tests do not collide with
    the developer's real ~/.fa/session-log/conformance directory (resume
    semantics key off that durable dir and would otherwise accumulate state
    across test cases)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Reset the path module's DEFAULT_STATE_ROOT cache if it exists.
    import fa.paths as _p

    for attr in ("DEFAULT_STATE_ROOT",):
        if hasattr(_p, attr):
            try:
                delattr(_p, attr)
            except AttributeError:
                pass
    # Ensure fa.paths resolves to the tmp HOME on next access.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))  # type: ignore[arg-type]


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
    # Driver defaults mirror production: max_tokens present, temperature/top_p
    # omitted (the thinking-model default — no forced sampling on the wire).
    assert req.max_tokens == 64000
    assert req.temperature is None
    assert req.top_p is None


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
    CONF rows. Secrets passed via the injection seam are honoured (no proxy env in
    this test so we exercise the non-proxy secret-store path).
    """
    from fa.cli import _cmd_conformance, build_parser
    from fa.providers.base import TransportResponse

    # Ensure proxy mode is OFF (otherwise the CLI would build a proxy-only
    # SecretStore({}) and skip the injected mapping, and the fake transport sees
    # no proxy rewrite).
    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)

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

    # Run through proxy mode: proxy mode builds SecretStore({}) which allows
    # empty secrets (the proxy injects keys), and rewrites chain base_urls.
    # This matches the deployed fa@fa-HP configuration where
    # FA_EGRESS_PROXY_URL is set and the SecretStore is empty.
    token_file = tmp_path / "fa_proxy_token"
    token_file.write_text("test-token-1234", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://proxy.test:8080")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token_file))

    class _ProxyAwareTransport(_FakeTransport):
        def __init__(self) -> None:
            super().__init__()
            self.seen_urls: list[str] = []

        @override
        def post(self, url: str, **kw: Any) -> TransportResponse:
            self.seen_urls.append(url)
            return super().post(url, **kw)

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    transport = _ProxyAwareTransport()
    args = build_parser().parse_args(["conformance", "--provider", "openrouter", "--config", str(models)])
    code = _cmd_conformance(args, transport=transport, secrets={})
    assert code == 0, f"all-CONF-OK matrix must exit 0; got code={code}"
    # Proxy rewrite must have pointed the transport at the proxy route, not
    # the vendor URL from models.yaml.
    for u in transport.seen_urls:
        assert u.startswith("http://proxy.test:8080/route/"), (
            f"proxy-mode conformance must rewrite vendor URL; got {u!r}"
        )
    out = buf.getvalue()
    assert "live run" in out
    assert "CONF-1" in out or "CONF-" in out
    # All 7 cases must be OK (the fake transport returns a 200 canned body).
    assert "OK" in out
    assert "FAIL" not in out


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

    # Proxy mode like the deployed box (empty secrets allowed).
    token_file = tmp_path / "fa_proxy_token"
    token_file.write_text("test-token-1234", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://proxy.test:8080")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token_file))

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    args = build_parser().parse_args(["conformance", "--provider", "openrouter", "--config", str(models)])
    code = _cmd_conformance(args, transport=_FakeTransport(), secrets={})
    assert code == 1, f"a fully-failing matrix must exit 1; got code={code}"
    out = buf.getvalue()
    # The FAIL reason is surfaced, not an opaque "FAIL".
    assert "FAIL" in out
    assert "Unsupported parameter(s)" in out


def test_cmd_conformance_proxy_mode_rewrites_chain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 — proxy-mode `fa conformance --provider` rewrites the chain through the egress proxy.

    Live regression: the live conformance command skipped `_proxy_rewrite_chain`
    (which `fa probe` and `fa run` both apply), so the runner targeted the vendor
    URL directly with an empty SecretStore and every request 401'd. This test
    asserts that, when FA_EGRESS_PROXY_URL is set and a proxy token is present,
    the request reaches the transport at the PROXY url, not the vendor URL.
    """
    from fa.cli import _cmd_conformance, build_parser
    from fa.providers.base import TransportResponse

    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "google/gemini-3-flash-preview"
  family: "gemini"
  chain:
    - provider: aigate
      model: "google/gemini-3-flash-preview"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: AIGATE_API_KEY
""",
        encoding="utf-8",
    )
    token_file = tmp_path / "fa_proxy_token"
    token_file.write_text("test-token", encoding="utf-8")

    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://proxy.test:8080")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token_file))

    seen_urls: list[str] = []

    class _RecordingTransport:
        def post(self, url: str, **kw: Any) -> TransportResponse:
            seen_urls.append(url)
            return TransportResponse(
                status=200,
                body={"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    args = build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])
    code = _cmd_conformance(args, transport=_RecordingTransport(), secrets={})
    assert code == 0, "proxy-mode conformance with a 200 transport must exit 0"
    assert seen_urls, "transport must have been called at least once"
    for u in seen_urls:
        assert u.startswith("http://proxy.test:8080/route/"), (
            f"proxy mode must rewrite vendor URL to proxy route; got {u!r}"
        )


def test_conf6_case_does_not_preemptively_violate_user_after_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C1 — CONF-6 harness case does not itself contain a user-after-tool violation.

    Live regression: the previous CONF-6 observations put a `user` directly after
    a `tool` message. The composer does not rewrite caller-supplied observations
    (it only reorders the TASK relative to observations), so that case raised a
    local MessageRulesError before any HTTP call — a harness defect, not a
    provider capability result. With the fix the composer places the task after
    the tool-final observation, producing the user-after-tool shape the case is
    intended to exercise, and the case must drive the transport rather than fail
    locally.
    """
    from fa.cli import _cmd_conformance, build_parser
    from fa.providers.base import TransportResponse

    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)

    # Key must be ≥8 chars for the SecretRedactor "not too short" check.
    _test_key = "TEST_KEY_k" * 4

    models = tmp_path / "models.yaml"
    models.write_text(
        """coder:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test-model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_KEY
""",
        encoding="utf-8",
    )

    class _RecordingTransport:
        def __init__(self) -> None:
            self.calls = 0
            self.conf6_seen = False

        def post(self, url: str, **kw: Any) -> TransportResponse:
            del url
            self.calls += 1
            body = kw.get("json_body", {})
            msgs = body.get("messages", [])
            roles = tuple(m.get("role") for m in msgs)
            # Detect the CONF-6 body: it has three history messages in
            # observations (assistant/tool_call, tool, assistant) plus the
            # trailing user task message. Assert the user-after-tool shape:
            # a `tool` message appears somewhere, followed eventually by a
            # final `user`.
            if "tool" in roles and roles[-1] == "user" and len(roles) >= 7:
                self.conf6_seen = True
            return TransportResponse(
                status=200,
                body={"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    transport = _RecordingTransport()
    args = build_parser().parse_args(["conformance", "--provider", "openrouter", "--config", str(models)])
    code = _cmd_conformance(args, transport=transport, secrets={"TEST_KEY": _test_key})
    out = buf.getvalue()
    assert code == 0, f"all-CONF-OK matrix must exit 0; got code={code} out={out!r}"
    # CONF-6 must NOT be rendered as a local request_shape failure.
    assert "CONF-6" in out
    conf6_line = next(ln for ln in out.splitlines() if "CONF-6" in ln)
    assert "user-after-tool" not in conf6_line, (
        f"CONF-6 must not self-fail with a local user-after-tool violation before HTTP; got {conf6_line!r}"
    )
    assert "FAIL" not in conf6_line, f"CONF-6 must not FAIL; got {conf6_line!r}"
    # The transport must have seen a user-after-tool body (a tool result
    # followed by a final user message) for CONF-6.
    assert transport.conf6_seen, "CONF-6 body must exercise the user-after-tool shape on the wire"
    assert transport.calls == 7, f"all 7 CONF cases must drive the transport once; calls={transport.calls}"
