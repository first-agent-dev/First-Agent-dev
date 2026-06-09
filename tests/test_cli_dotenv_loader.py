import os
from pathlib import Path

import pytest

from fa.cli import _load_fa_dotenv


def test_load_fa_dotenv_missing_file_silently_continues(tmp_path: Path) -> None:
    missing = tmp_path / "missing.env"
    # Should not raise and should not warn
    _load_fa_dotenv(missing)
    # No side effects on os.environ


def test_load_fa_dotenv_malformed_encoding_warns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.env"
    # Write invalid UTF-8 bytes
    bad.write_bytes(b"\xff\xfe\x00\x00")
    with pytest.warns(UserWarning, match="Malformed encoding"):
        _load_fa_dotenv(bad)


def test_load_fa_dotenv_loads_valid_pairs(tmp_path: Path) -> None:
    env_file = tmp_path / "valid.env"
    env_file.write_text("FA_TEST_KEY=hello-world\n# comment\n\nBAD_LINE\n", encoding="utf-8")
    _load_fa_dotenv(env_file)
    assert os.environ.get("FA_TEST_KEY") == "hello-world"
    # Clean up
    os.environ.pop("FA_TEST_KEY", None)


def test_load_fa_dotenv_does_not_leak_values_in_warning(tmp_path: Path) -> None:
    bad = tmp_path / "bad.env"
    bad.write_bytes(b"\xff\xfe")
    with pytest.warns(UserWarning) as warn_info:
        _load_fa_dotenv(bad)
    for record in warn_info.list:
        message = str(record.message)
        assert "secret" not in message.lower()
        assert "token" not in message.lower()
        assert "key=" not in message.lower()
