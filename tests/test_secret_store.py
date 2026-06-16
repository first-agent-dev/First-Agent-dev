"""Unit tests for the private SecretStore (secret-isolation invariant)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fa.providers.secret_store import SecretStore, parse_env_file


def test_parse_env_file_basic() -> None:
    parsed = parse_env_file("A=1\nB=two\n")
    assert parsed == {"A": "1", "B": "two"}


def test_parse_env_file_ignores_comments_and_blanks() -> None:
    parsed = parse_env_file("\n# comment\n  \nKEY=val  \n")
    assert parsed == {"KEY": "val"}


def test_parse_env_file_splits_on_first_equals() -> None:
    parsed = parse_env_file("TOKEN=a=b=c\n")
    assert parsed == {"TOKEN": "a=b=c"}


def test_mapping_protocol() -> None:
    store = SecretStore({"FIREWORKS_API_KEY": "sk-test"})
    assert store["FIREWORKS_API_KEY"] == "sk-test"
    assert "FIREWORKS_API_KEY" in store
    assert store.get("MISSING", "") == ""
    assert len(store) == 1
    assert list(store) == ["FIREWORKS_API_KEY"]


def test_repr_never_renders_values() -> None:
    store = SecretStore({"FIREWORKS_API_KEY": "sk-secret-value"})
    assert "sk-secret-value" not in repr(store)
    assert "sk-secret-value" not in str(store)
    assert repr(store) == "SecretStore(1 keys)"


def test_from_file_loads(tmp_path: Path) -> None:
    f = tmp_path / "fa.env"
    f.write_text("OPENROUTER_API_KEY=sk-or-1\n# c\nFIREWORKS_API_KEY=fw-2\n", encoding="utf-8")
    store = SecretStore.from_file(f)
    assert store["OPENROUTER_API_KEY"] == "sk-or-1"
    assert store["FIREWORKS_API_KEY"] == "fw-2"


def test_from_file_missing_is_empty(tmp_path: Path) -> None:
    store = SecretStore.from_file(tmp_path / "does-not-exist.env")
    assert len(store) == 0


def test_from_file_does_not_touch_os_environ(tmp_path: Path) -> None:
    """The store must never leak keys into the process environment."""
    f = tmp_path / "fa.env"
    f.write_text("FA_TEST_SECRET_XYZ=should-not-leak\n", encoding="utf-8")
    before = dict(os.environ)
    SecretStore.from_file(f)
    assert "FA_TEST_SECRET_XYZ" not in os.environ
    assert os.environ == before


def test_constructor_copies_input() -> None:
    src = {"A": "1"}
    store = SecretStore(src)
    src["A"] = "mutated"
    assert store["A"] == "1"  # store holds its own copy


def test_from_file_malformed_encoding_warns(tmp_path: Path) -> None:
    f = tmp_path / "bad.env"
    f.write_bytes(b"\xff\xfe\x00bad")
    with pytest.warns(UserWarning):
        store = SecretStore.from_file(f)
    assert len(store) == 0
