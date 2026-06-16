"""Phase-2 tests: keys flow through the private SecretStore, not os.environ."""

from __future__ import annotations

import os
from pathlib import Path

from fa.cli import _load_secret_store, _resolve_secrets_path
from fa.providers import SecretStore


def test_resolve_secrets_path_env_override(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "custom.env"
    monkeypatch.setenv("FA_SECRETS_FILE", str(target))
    assert _resolve_secrets_path() == target


def test_resolve_secrets_path_wsl_default(monkeypatch) -> None:
    monkeypatch.delenv("FA_SECRETS_FILE", raising=False)
    # No /run/secrets/fa.env on a dev box → falls back to ~/.fa/.env
    if Path("/run/secrets/fa.env").exists():  # pragma: no cover - env-specific
        return
    assert _resolve_secrets_path() == Path.home() / ".fa" / ".env"


def test_load_secret_store_reads_file_not_environ(monkeypatch, tmp_path: Path) -> None:
    f = tmp_path / "fa.env"
    f.write_text("FIREWORKS_API_KEY=fw-secret-123\n", encoding="utf-8")
    monkeypatch.setenv("FA_SECRETS_FILE", str(f))

    before = dict(os.environ)
    store = _load_secret_store()

    assert isinstance(store, SecretStore)
    assert store["FIREWORKS_API_KEY"] == "fw-secret-123"
    # The key must NOT have leaked into the process environment.
    assert "FIREWORKS_API_KEY" not in os.environ
    assert os.environ == before


def test_strict_file_only_ignores_environ(monkeypatch, tmp_path: Path) -> None:
    """A key present ONLY in os.environ (operator `-e`) must NOT be picked up."""
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setenv("FA_SECRETS_FILE", str(empty))
    monkeypatch.setenv("SHOULD_BE_IGNORED_API_KEY", "leaked")

    store = _load_secret_store()
    assert "SHOULD_BE_IGNORED_API_KEY" not in store
