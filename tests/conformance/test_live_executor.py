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
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))


class _FakeChain:
    """Minimal ProviderChain stand-in: records requests, returns a canned response."""

    def __init__(
        self,
        *,
        raise_429: bool = False,
        raise_exhausted: bool = False,
        text: str = "ok",
        tool_calls: tuple[dict[str, Any], ...] = (),
    ) -> None:
        self.requests: list[Any] = []
        self._raise_429 = raise_429
        self._raise_exhausted = raise_exhausted
        self._text = text
        self._tool_calls = tool_calls
        self.config = SimpleNamespace(name="test-model")

    def request(self, request: Any) -> tuple[Any, str, list[Any]]:
        self.requests.append(request)
        if self._raise_429:
            from fa.providers.errors import ProviderTransientError

            raise ProviderTransientError("429 rate limited", status=429, kind="rate_limited")
        if self._raise_exhausted:
            from fa.providers.errors import ProviderChainExhaustedError

            raise ProviderChainExhaustedError("all chain entries failed", attempts=[], logical_call_id="x")
        return (
            SimpleNamespace(text=self._text, tool_calls=self._tool_calls, in_tokens=10, out_tokens=5),
            "logical-1",
            [],
        )


def _mk_case(case: int) -> ConfCase:
    return ConfCase(case=case, name=f"CONF-{case}", role="coder", task="a task")


def _function_tool(name: str, *, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"{name} description",
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "additionalProperties": False,
            },
        },
    }


class _RecordingSuccessTransport:
    """Record exact provider request bodies and return a successful completion."""

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.bodies: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> Any:
        from fa.providers.base import TransportResponse

        self.urls.append(url)
        self.bodies.append(dict(kwargs.get("json_body", {})))
        return TransportResponse(
            status=200,
            body={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )


def _enable_proxy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    token_file = tmp_path / "fa_proxy_token"
    token_file.write_text("test-token-1234", encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://proxy.test:8080")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token_file))


def _write_coder_models(path: Path, chain_rows: str) -> Path:
    path.write_text(
        f'coder:\n  name: "gemini-test"\n  family: "gemini"\n  chain:\n{chain_rows}',
        encoding="utf-8",
    )
    return path


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


def test_production_request_profile_case_rejects_empty_or_missing_required_tools() -> None:
    """C0p T6: runtime positive controls reject an incomplete CONF-8 corpus."""

    from fa.providers import conformance as conformance_module

    invalid_corpora = (
        (),
        (_function_tool("fs_search"),),
        (_function_tool("pr_prepare"),),
    )
    for tools in invalid_corpora:
        with pytest.raises(ValueError, match="CONF-8"):
            conformance_module.production_request_profile_case(tools)


def test_case_to_request_carries_conf8_tools_into_composer_and_request() -> None:
    """C1 T6: one canonical tuple reaches prompt composition and RequestInfo."""

    from fa.providers import conformance as conformance_module

    tools = (
        _function_tool("fs_search", properties={"query": {"type": "string"}}),
        _function_tool("pr_prepare"),
    )
    case = conformance_module.production_request_profile_case(tools)
    request = _case_to_request(case, model_slug="test-model")

    assert request.tools == tools
    tool_block = next(
        str(message["content"])
        for message in request.messages
        if str(message.get("content", "")).startswith("Tools for role coder:\n")
    )
    assert json.loads(tool_block.split("\n", 1)[1]) == list(tools)
    assert request.max_tokens == 64000
    assert request.temperature is None
    assert request.top_p is None


@pytest.mark.parametrize(
    ("text", "tool_calls", "expected_ok"),
    [
        ("answer", (), True),
        ("", ({"id": "call-1", "function": {"name": "fs_search", "arguments": "{}"}},), True),
        ("", (), False),
    ],
    ids=("text", "tool-call-only", "empty"),
)
def test_live_executor_accepts_tool_call_only_response(
    text: str,
    tool_calls: tuple[dict[str, Any], ...],
    expected_ok: bool,
) -> None:
    """C1 T6: canonical text or tool calls indicate provider acceptance."""

    row = make_live_executor(_FakeChain(text=text, tool_calls=tool_calls))(_mk_case(1), "run-1")
    assert row["ok"] is expected_ok


def test_live_executor_drives_chain_and_reports_tokens() -> None:
    """C1 — the live executor calls the chain and returns a row with tokens."""
    chain = _FakeChain(text="hello")
    execute = make_live_executor(chain)
    row = execute(_mk_case(1), "run-1")
    assert row["case"] == 1
    assert row["name"] == "CONF-1"
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
    """C2: direct mode uses the injected selected-provider secret for all cases."""

    from fa.cli import _cmd_conformance, build_parser

    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
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

    transport = _RecordingSuccessTransport()
    args = build_parser().parse_args(["conformance", "--provider", "openrouter", "--config", str(models)])
    code = _cmd_conformance(args, transport=transport, secrets={"TEST_KEY": "selected-test-key"})

    assert code == 0
    assert len(transport.bodies) == 8
    assert all(url.startswith("https://example.invalid/v1") for url in transport.urls)


def test_cmd_conformance_selects_requested_provider_before_proxy_rewrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 S13.11: ``--provider`` selects actual chain entries, not a label.

    Current production builds the whole coder chain, so the successful first
    OpenRouter entry serves every row even when the command says Aigate.
    """

    from fa.cli import _cmd_conformance, build_parser

    models = tmp_path / "models-two-providers.yaml"
    models.write_text(
        """coder:
  name: "gemini-test"
  family: "gemini"
  chain:
    - provider: openrouter
      model: "first/gemini-3-flash-preview"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: FIRST_KEY
    - provider: aigate
      model: "target/gemini-3-flash-preview"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_KEY
""",
        encoding="utf-8",
    )
    _enable_proxy(tmp_path, monkeypatch)
    transport = _RecordingSuccessTransport()
    args = build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])

    assert _cmd_conformance(args, transport=transport, secrets={}) == 0
    assert transport.bodies
    assert {body["model"] for body in transport.bodies} == {"target/gemini-3-flash-preview"}
    assert all("/route/aigate-" in url for url in transport.urls)


def test_cmd_conformance_unknown_provider_exits_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C2 T8: unknown provider fails before secrets, artifacts, or transport."""

    from fa.cli import _cmd_conformance, build_parser

    models = _write_coder_models(
        tmp_path / "models.yaml",
        """    - provider: openrouter
      model: "first/gemini"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: FIRST_KEY
""",
    )
    _enable_proxy(tmp_path, monkeypatch)
    transport = _RecordingSuccessTransport()
    args = build_parser().parse_args(["conformance", "--provider", "missing", "--config", str(models)])

    assert _cmd_conformance(args, transport=transport, secrets={}) == 2
    err = capsys.readouterr().err
    assert "missing" in err
    assert "openrouter" in err
    assert transport.urls == []
    assert not (tmp_path / ".fa" / "session-log").exists()


def test_cmd_conformance_direct_mode_ignores_unselected_missing_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 T8: only selected entries participate in direct key validation."""

    from fa.cli import _cmd_conformance, build_parser

    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    models = _write_coder_models(
        tmp_path / "models.yaml",
        """    - provider: openrouter
      model: "first/gemini"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: FIRST_KEY
    - provider: aigate
      model: "target/gemini"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_KEY
""",
    )
    transport = _RecordingSuccessTransport()
    args = build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])

    assert _cmd_conformance(args, transport=transport, secrets={"TARGET_KEY": "selected-target-key"}) == 0
    assert len(transport.bodies) == 8
    assert {body["model"] for body in transport.bodies} == {"target/gemini"}


def test_cmd_conformance_direct_mode_rejects_missing_selected_key_without_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C3 T8: missing selected key is pre-network and never leaks a value."""

    from fa.cli import _cmd_conformance, build_parser

    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    models = _write_coder_models(
        tmp_path / "models.yaml",
        """    - provider: openrouter
      model: "first/gemini"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: FIRST_KEY
    - provider: aigate
      model: "target/gemini"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_KEY
""",
    )
    secret_sentinel = "unselected-secret-must-not-leak"
    transport = _RecordingSuccessTransport()
    args = build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])

    assert _cmd_conformance(args, transport=transport, secrets={"FIRST_KEY": secret_sentinel}) == 2
    err = capsys.readouterr().err
    assert "fa conformance: configuration error:" in err
    assert "secret redactor configuration error" not in err
    assert "TARGET_KEY" in err
    assert secret_sentinel not in err
    assert transport.urls == []
    assert not (tmp_path / ".fa" / "session-log").exists()


def test_cmd_conformance_redactor_failure_exits_before_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C2 T8: selected-secret redactor rejection leaves no run artifacts."""

    from fa.cli import _cmd_conformance, build_parser

    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    models = _write_coder_models(
        tmp_path / "models.yaml",
        """    - provider: aigate
      model: "target/gemini"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_KEY
""",
    )
    transport = _RecordingSuccessTransport()
    args = build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])

    assert _cmd_conformance(args, transport=transport, secrets={"TARGET_KEY": "short"}) == 2
    assert "secret redactor configuration error" in capsys.readouterr().err
    assert transport.urls == []
    assert not (tmp_path / ".fa" / "session-log").exists()


def test_cmd_conformance_retains_selected_provider_fallback_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 T8: same-provider fallbacks retain order across an intervening entry."""

    from fa.cli import _cmd_conformance, build_parser
    from fa.providers.base import TransportResponse

    monkeypatch.delenv("FA_EGRESS_PROXY_URL", raising=False)
    monkeypatch.delenv("FA_PROXY_TOKEN_FILE", raising=False)
    models = _write_coder_models(
        tmp_path / "models.yaml",
        """    - provider: aigate
      model: "target-a/gemini"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_A_KEY
    - provider: openrouter
      model: "forbidden/gemini"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: MISSING_MIDDLE_KEY
    - provider: aigate
      model: "target-b/gemini"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_B_KEY
""",
    )
    seen_models: list[str] = []

    class _FallbackTransport:
        def post(self, url: str, **kwargs: Any) -> TransportResponse:
            del url
            body = dict(kwargs.get("json_body", {}))
            model = str(body.get("model", ""))
            seen_models.append(model)
            if model == "target-a/gemini":
                return TransportResponse(status=401, body={})
            return TransportResponse(
                status=200,
                body={"choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]},
            )

    args = build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])
    secrets = {"TARGET_A_KEY": "selected-a-key", "TARGET_B_KEY": "selected-b-key"}

    assert _cmd_conformance(args, transport=_FallbackTransport(), secrets=secrets) == 0
    assert seen_models == ["target-a/gemini", "target-b/gemini"] * 8
    assert "forbidden/gemini" not in seen_models


def test_cmd_conformance_redactor_receives_selected_models_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 T8: redaction derives names from the selected config projection."""

    from fa.cli import _cmd_conformance, build_parser
    from fa.observability.redaction import SecretRedactor
    from fa.providers import ModelsConfig

    models = _write_coder_models(
        tmp_path / "models.yaml",
        """    - provider: openrouter
      model: "first/gemini"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: FIRST_KEY
    - provider: aigate
      model: "target/gemini"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_KEY
""",
    )
    _enable_proxy(tmp_path, monkeypatch)
    seen_configs: list[ModelsConfig] = []
    original = SecretRedactor.from_models_config

    def recording_redactor(
        env: Mapping[str, str],
        config: ModelsConfig,
        *,
        extra_values: Sequence[str] = (),
        allow_empty: bool = False,
    ) -> SecretRedactor:
        seen_configs.append(config)
        return original(env, config, extra_values=extra_values, allow_empty=allow_empty)

    monkeypatch.setattr(SecretRedactor, "from_models_config", recording_redactor)
    transport = _RecordingSuccessTransport()
    args = build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])

    assert _cmd_conformance(args, transport=transport, secrets={}) == 0
    assert len(seen_configs) == 1
    assert set(seen_configs[0].roles) == {"coder"}
    assert [entry.provider for entry in seen_configs[0].roles["coder"].chain] == ["aigate"]


def test_cmd_conformance_appends_exact_nonempty_production_tools_conf8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C2 T6: live CONF-8 calls the shared producer and sends exact mappings."""

    import fa.cli as cli_module
    from fa.inner_loop.pr_draft import PrDraftStore
    from fa.inner_loop.prompt import render_tool_specs
    from fa.inner_loop.registry import ToolRegistry

    models = tmp_path / "models-aigate.yaml"
    models.write_text(
        """coder:
  name: "gemini-test"
  family: "gemini"
  chain:
    - provider: aigate
      model: "target/gemini-3-flash-preview"
      base_url: "https://api.aigate.shop/v1"
      api_key_env: TARGET_KEY
""",
        encoding="utf-8",
    )
    _enable_proxy(tmp_path, monkeypatch)
    expected_tools: list[dict[str, Any]] = []
    producer_workspaces: list[Path] = []
    original_builder = cli_module._build_run_tool_registry

    def recording_builder(
        role: str,
        workspace: Path,
        *,
        bash_timeout_seconds: int,
        draft_store: PrDraftStore,
    ) -> ToolRegistry:
        registry = original_builder(
            role,
            workspace,
            bash_timeout_seconds=bash_timeout_seconds,
            draft_store=draft_store,
        )
        producer_workspaces.append(workspace)
        expected_tools[:] = [dict(tool) for tool in render_tool_specs(registry.specs())]
        return registry

    monkeypatch.setattr(cli_module, "_build_run_tool_registry", recording_builder)
    transport = _RecordingSuccessTransport()
    args = cli_module.build_parser().parse_args(["conformance", "--provider", "aigate", "--config", str(models)])

    assert cli_module._cmd_conformance(args, transport=transport, secrets={}) == 0
    assert len(transport.bodies) == 8
    assert all("tools" not in body for body in transport.bodies[:7])
    conf8_body = transport.bodies[7]
    conf8_tools = conf8_body.get("tools")
    assert conf8_tools == expected_tools
    assert len(producer_workspaces) == 1
    assert producer_workspaces[0].is_relative_to(tmp_path)
    names = [tool["function"]["name"] for tool in expected_tools]
    assert len(names) == len(set(names)) == 15
    assert {"fs_search", "pr_prepare"} <= set(names)
    assert conf8_body["max_tokens"] == 64000
    assert "temperature" not in conf8_body
    assert "top_p" not in conf8_body

    forbidden = {"anyOf", "oneOf", "allOf", "$ref", "$defs"}

    def assert_portable_schema(value: object) -> None:
        if isinstance(value, dict):
            assert forbidden.isdisjoint(value)
            assert not isinstance(value.get("type"), list)
            assert value.get("type") != "null"
            for child in value.values():
                assert_portable_schema(child)
        elif isinstance(value, list):
            for child in value:
                assert_portable_schema(child)

    for tool in expected_tools:
        assert_portable_schema(tool["function"]["parameters"])


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
    assert row["name"] == "CONF-1"


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

    Historical regression: all then-existing 7 CONF cases failed against nvidia_build
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
    assert transport.calls == 8, f"all 8 live CONF cases must drive the transport once; calls={transport.calls}"
