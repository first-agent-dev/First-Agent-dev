"""CLI diagnostics for the ADR-12 egress-proxy route seam."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from fa.cli import _selfcheck_parse_routes_payload, build_parser
from fa.egress_proxy.routing import build_route_table
from fa.egress_proxy.server import build_handler_class

_TOKEN = "fa-proxy-selfcheck-token"
_KEY = "sk-selfcheck-real-key-must-not-print"


@contextmanager
def _proxy_server(
    chain_entries: list[tuple[str, str, str, str]],
    *,
    secrets: dict[str, str],
) -> Iterator[ThreadingHTTPServer]:
    handler = build_handler_class(
        route_table=build_route_table(chain_entries),
        secrets=secrets,
        proxy_token=_TOKEN,
        forward=None,
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


def _write_models(path: Path, slug: str = "meta-llama/llama-3.1-8b") -> None:
    path.write_text(
        f"""
coder:
  model: llama
  family: llama
  chain:
    - provider: openrouter
      slug: "{slug}"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
""".lstrip(),
        encoding="utf-8",
    )


def _run_selfcheck(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    config_path: Path,
    port: int,
) -> int:
    token_file = tmp_path / "fa_proxy_token"
    token_file.write_text(_TOKEN, encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token_file))
    parser = build_parser()
    args = parser.parse_args(["selfcheck", "--config", str(config_path), "--role", "coder"])
    return args.func(args)


def test_selfcheck_ok_when_routes_match_and_keys_present(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    with _proxy_server(
        [("openrouter", "meta-llama/llama-3.1-8b", "https://up.example/v1", "OPENROUTER_API_KEY")],
        secrets={"OPENROUTER_API_KEY": _KEY},
    ) as httpd:
        exit_code = _run_selfcheck(tmp_path, monkeypatch, config_path, httpd.server_address[1])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "fa selfcheck: OK" in out
    assert _KEY not in out


def test_selfcheck_reports_route_desync(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path, slug="meta-llama/llama-3.1-8b")
    with _proxy_server(
        [("openrouter", "different-slug", "https://up.example/v1", "OPENROUTER_API_KEY")],
        secrets={"OPENROUTER_API_KEY": _KEY},
    ) as httpd:
        exit_code = _run_selfcheck(tmp_path, monkeypatch, config_path, httpd.server_address[1])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "fa selfcheck: ERROR" in out
    assert "openrouter-meta-llama-llama-3-1-8b" in out
    assert "absent from proxy /routes" in out
    assert "scripts/fa-update.sh" in out
    assert "/srv/first-agent/routing/models.yaml" in out
    assert "restart/recreate" in out
    assert _KEY not in out


def test_selfcheck_reports_missing_proxy_key(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    with _proxy_server(
        [("openrouter", "meta-llama/llama-3.1-8b", "https://up.example/v1", "OPENROUTER_API_KEY")],
        secrets={"OPENROUTER_API_KEY": ""},
    ) as httpd:
        exit_code = _run_selfcheck(tmp_path, monkeypatch, config_path, httpd.server_address[1])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "fa selfcheck: ERROR" in out
    assert "key for OPENROUTER_API_KEY is absent" in out
    assert "/srv/first-agent/secrets/fa.env" in out

def test_selfcheck_rejects_non_http_proxy_url(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "file:///run/secrets/fa.env")
    parser = build_parser()
    args = parser.parse_args(["selfcheck", "--config", str(tmp_path / "models.yaml")])

    exit_code = args.func(args)

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "invalid FA_EGRESS_PROXY_URL" in out
    assert "expected http:// or https:// URL" in out


def test_selfcheck_rejects_routes_payload_extra_fields() -> None:
    routes, error = _selfcheck_parse_routes_payload(
        [{"name": "openrouter-s", "has_key": True, "upstream_base_url": "https://up.example"}]
    )

    assert routes == {}
    assert "must contain only name and has_key" in error

def test_selfcheck_reports_unreachable_proxy(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    token_file = tmp_path / "fa_proxy_token"
    token_file.write_text(_TOKEN, encoding="utf-8")
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token_file))
    parser = build_parser()
    args = parser.parse_args(["selfcheck", "--config", str(tmp_path / "models.yaml")])

    exit_code = args.func(args)

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "proxy is not reachable" in out
    assert "docker compose logs fa-egress-proxy" in out


def test_selfcheck_reports_missing_proxy_token(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(tmp_path / "missing-token"))
    parser = build_parser()
    args = parser.parse_args(["selfcheck", "--config", str(tmp_path / "models.yaml")])

    exit_code = args.func(args)

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "proxy token is missing" in out


def test_selfcheck_reports_unknown_role_after_proxy_checks(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    config_path = tmp_path / "models.yaml"
    _write_models(config_path)
    with _proxy_server(
        [("openrouter", "meta-llama/llama-3.1-8b", "https://up.example/v1", "OPENROUTER_API_KEY")],
        secrets={"OPENROUTER_API_KEY": _KEY},
    ) as httpd:
        token_file = tmp_path / "fa_proxy_token"
        token_file.write_text(_TOKEN, encoding="utf-8")
        monkeypatch.setenv("FA_EGRESS_PROXY_URL", f"http://127.0.0.1:{httpd.server_address[1]}")
        monkeypatch.setenv("FA_PROXY_TOKEN_FILE", str(token_file))
        parser = build_parser()
        args = parser.parse_args(["selfcheck", "--config", str(config_path), "--role", "unknown"])
        exit_code = args.func(args)

    out = capsys.readouterr().out
    assert exit_code == 2
    assert "OK: proxy /healthz reachable" in out
    assert "role 'unknown' not found" in out


def test_selfcheck_rejects_non_list_routes_payload(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
) -> None:
    import fa.cli as cli_mod

    def fake_get(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 5.0,
    ) -> tuple[int, bytes]:
        if url.endswith("/healthz"):
            return 200, b'{"status":"ok"}'
        return 200, b'{"not":"a-list"}'

    monkeypatch.setenv("FA_EGRESS_PROXY_URL", "http://127.0.0.1:8080")
    monkeypatch.setattr(cli_mod, "_resolve_proxy_token", lambda: _TOKEN)
    monkeypatch.setattr(cli_mod, "_selfcheck_http_get", fake_get)
    parser = build_parser()
    args = parser.parse_args(["selfcheck"])

    exit_code = args.func(args)

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "unsafe or malformed proxy /routes payload" in out
    assert "expected a JSON list" in out

