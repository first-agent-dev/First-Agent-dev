"""CLI tests for `fa probe` — liveness test of the LLM provider chain."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, override

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from fa.cli import build_parser
from fa.providers.base import Transport, TransportResponse


def _write_models(path: Path, *, roles: dict[str, dict[str, str]] | None = None) -> None:
    """Write a minimal models.yaml with one or more roles."""
    if roles is None:
        roles = {
            "coder": {
                "model": "test-model",
                "family": "llama",
                "slug": "meta-llama/llama-3.1-8b",
            },
        }
    sections: list[str] = []
    for role_name, cfg in roles.items():
        sections.append(
            f"""{role_name}:
  model: "{cfg["model"]}"
  family: "{cfg["family"]}"
  chain:
    - provider: openrouter
      slug: "{cfg["slug"]}"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
"""
        )
    path.write_text("\n".join(sections), encoding="utf-8")


class _FakeTransport(Transport):
    """Deterministic transport that returns a canned response or error status."""

    def __init__(self, *, status: int = 200, body: Mapping[str, Any] | None = None) -> None:
        self._status = status
        self._body = body

    @override
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any],
        timeout_seconds: float,
    ) -> TransportResponse:
        if self._status == 200:
            default_body: dict[str, Any] = {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 8, "completion_tokens": 1},
            }
            return TransportResponse(
                status=200,
                body=self._body if self._body is not None else default_body,
                retry_after_seconds=None,
            )
        return TransportResponse(
            status=self._status,
            body=self._body or {"error": {"message": "test error"}},
            retry_after_seconds=None,
        )


def _run_probe(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    config_path: Path,
    transport: Transport,
    *,
    extra_args: list[str] | None = None,
) -> int:
    """Run `fa probe` with a fake transport (no network)."""
    from fa.providers import SecretStore

    # Disable proxy mode — probe runs with direct secret store.
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "")
    # Provide a fake secret store with the key present.
    monkeypatch.setattr(
        "fa.cli._load_secret_store",
        lambda: SecretStore({"OPENROUTER_API_KEY": "sk-test-key"}),
    )

    # Inject the fake transport by patching UrllibTransport construction.
    monkeypatch.setattr("fa.cli.UrllibTransport", lambda: transport)

    parser = build_parser()
    args_list = ["probe", "--config", str(config_path)]
    if extra_args:
        args_list.extend(extra_args)
    args = parser.parse_args(args_list)
    result: int = args.func(args)
    return result


def test_probe_ok(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    transport = _FakeTransport(status=200)

    exit_code = _run_probe(tmp_path, monkeypatch, config_path, transport)

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "fa probe: OK" in out
    assert "in=8 out=1" in out


def test_probe_chain_exhausted(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    transport = _FakeTransport(status=401)

    exit_code = _run_probe(tmp_path, monkeypatch, config_path, transport)

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "fa probe: FAIL" in out
    assert "all 1 entries failed" in out


def test_probe_unknown_role(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    transport = _FakeTransport(status=200)

    exit_code = _run_probe(
        tmp_path, monkeypatch, config_path, transport, extra_args=["--role", "nonexistent"]
    )

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "not found" in out


def test_probe_all_roles(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(
        config_path,
        roles={
            "planner": {
                "model": "glm-5p2",
                "family": "glm",
                "slug": "meta-llama/llama-3.1-8b",
            },
            "coder": {
                "model": "llama-3",
                "family": "llama",
                "slug": "meta-llama/llama-3.1-8b",
            },
        },
    )
    transport = _FakeTransport(status=200)

    exit_code = _run_probe(
        tmp_path, monkeypatch, config_path, transport, extra_args=["--all-roles"]
    )

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "role=coder" in out
    assert "role=planner" in out
    assert out.count("fa probe: OK") == 2


def test_probe_request_shape_error(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    transport = _FakeTransport(status=400)

    exit_code = _run_probe(tmp_path, monkeypatch, config_path, transport)

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "FAIL" in out


def test_probe_config_error(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    # Invalid YAML: role value is a string, not a mapping.
    config_path.write_text("planner: not-a-mapping\n", encoding="utf-8")
    transport = _FakeTransport(status=200)

    exit_code = _run_probe(
        tmp_path, monkeypatch, config_path, transport, extra_args=["--role", "planner"]
    )

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "configuration error" in err


def test_probe_empty_config(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    config_path.write_text("", encoding="utf-8")
    transport = _FakeTransport(status=200)

    exit_code = _run_probe(tmp_path, monkeypatch, config_path, transport)

    err = capsys.readouterr().err
    assert exit_code == 2
    assert "no roles found" in err


def test_probe_proxy_mode_missing_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    """In proxy mode, a missing proxy token should fail gracefully."""
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    transport = _FakeTransport(status=200)

    # Enable proxy mode but with no token file.
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(tmp_path / "nonexistent"))
    monkeypatch.setattr("fa.cli.UrllibTransport", lambda: transport)

    parser = build_parser()
    args = parser.parse_args(["probe", "--config", str(config_path), "--role", "coder"])
    result: int = args.func(args)

    output = capsys.readouterr()
    # Missing token → proxy rewrite fails → any_failure=True → exit 1.
    assert result != 0
    assert "proxy" in output.err.lower() or "token" in output.err.lower()
