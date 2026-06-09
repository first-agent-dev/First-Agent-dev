import base64
import threading
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

from fa.inner_loop.state import EventLog
from fa.observability.redaction import SecretRedactor, SecretRedactorError


class FakeModelsConfig:
    """Minimal stand-in for ModelsConfig with .roles[role].chain entries."""
    def __init__(self, env_vars: list[str]) -> None:
        self.roles = {
            "coder": type(
                "Role", (), {"chain": [type("Entry", (), {"api_key_env": v}) for v in env_vars]}
            )
        }


def test_exact_match() -> None:
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345"}
    redactor = SecretRedactor(env, ["OPENROUTER_API_KEY"])
    assert redactor.redact("The key is sk-or-v1-real-key-12345.") == "The key is ***REDACTED***."


def test_substring_replacement() -> None:
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345"}
    redactor = SecretRedactor(env, ["OPENROUTER_API_KEY"])
    assert (
        redactor.redact("prefix sk-or-v1-real-key-12345 suffix")
        == "prefix ***REDACTED*** suffix"
    )


def test_no_false_positive() -> None:
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345"}
    redactor = SecretRedactor(env, ["OPENROUTER_API_KEY"])
    text = "This is not the key: sk-or-v1-fake-key."
    assert redactor.redact(text) == text


def test_multiline_secret() -> None:
    env = {"KEY": "line1\nline2"}
    redactor = SecretRedactor(env, ["KEY"])
    assert redactor.redact("start\nline1\nline2\nend") == "start\n***REDACTED***\nend"


def test_nested_dict_redaction() -> None:
    """Simulate tool_call["params"] values being redacted."""
    env = {"KEY": "secret-token"}
    redactor = SecretRedactor(env, ["KEY"])
    params = {"cmd": "curl -H 'Authorization: secret-token'"}
    redacted = {k: redactor.redact(v) for k, v in params.items()}
    assert redacted["cmd"] == "curl -H 'Authorization: ***REDACTED***'"


def test_from_models_config() -> None:
    env = {
        "OPENROUTER_API_KEY": "sk-or-v1-real-key-12345",
        "FIREWORKS_API_KEY": "fw-fake-key-67890",
    }
    config = FakeModelsConfig(["OPENROUTER_API_KEY", "FIREWORKS_API_KEY"])
    redactor = SecretRedactor.from_models_config(env, config)  # type: ignore[arg-type]
    assert "sk-or-v1-real-key-12345" not in redactor.redact("key: sk-or-v1-real-key-12345")
    assert "fw-fake-key-67890" not in redactor.redact("key: fw-fake-key-67890")


def test_empty_env_var_raises() -> None:
    env = {"EMPTY_KEY": ""}
    with pytest.raises(SecretRedactorError, match="empty: EMPTY_KEY"):
        SecretRedactor(env, ["EMPTY_KEY"])


def test_secrets_property() -> None:
    env = {"KEY": "secret-value-12345"}
    redactor = SecretRedactor(env, ["KEY"])
    assert redactor.secrets == frozenset({"secret-value-12345"})


def test_eventlog_redaction(tmp_path: Path) -> None:
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345"}
    redactor = SecretRedactor(env, ["OPENROUTER_API_KEY"])
    log_path = tmp_path / "events.jsonl"
    log = EventLog(log_path, run_id="test", redactor=redactor)

    log.append(
        actor="model",
        kind="model_msg",
        content={
            "text": "The key is sk-or-v1-real-key-12345.",
            "nested": {"cmd": "curl -H 'sk-or-v1-real-key-12345'"},
            "items": ["sk-or-v1-real-key-12345"],
            "tuple": ("sk-or-v1-real-key-12345",),
        },
    )

    events = log.read_all()
    assert len(events) == 1
    content: dict[str, Any] = events[0].content  # type: ignore[assignment]
    assert content["text"] == "The key is ***REDACTED***."
    assert content["nested"]["cmd"] == "curl -H '***REDACTED***'"
    assert content["items"] == ["***REDACTED***"]
    # JSON round-trip turns tuples into lists
    assert content["tuple"] == ["***REDACTED***"]


def test_eventlog_no_redactor_passes_through() -> None:
    log_path = Path("/dev/null")
    log = EventLog(log_path, run_id="test", redactor=None)
    assert log._redact_value("plain text") == "plain text"
    assert log._redact_value({"a": 1}) == {"a": 1}
    assert log._redact_value(("a", "b")) == ("a", "b")


def test_very_long_secret() -> None:
    secret = "x" * 2048
    env = {"KEY": secret}
    redactor = SecretRedactor(env, ["KEY"])
    assert redactor.redact(f"prefix {secret} suffix") == f"prefix {redactor._MASK} suffix"


def test_secret_contains_mask_string() -> None:
    secret = "***REDACTED***-real-value"
    env = {"KEY": secret}
    redactor = SecretRedactor(env, ["KEY"])
    result = redactor.redact(f"value: {secret}")
    assert secret not in result
    assert redactor._MASK in result


def test_concurrent_redaction() -> None:
    env = {"KEY": "secret-token-12345"}
    redactor = SecretRedactor(env, ["KEY"])
    text = "start secret-token-12345 middle secret-token-12345 end"
    expected = f"start {redactor._MASK} middle {redactor._MASK} end"
    results: list[str] = []

    def worker() -> None:
        for _ in range(100):
            results.append(redactor.redact(text))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r == expected for r in results)


def test_empty_secret_set() -> None:
    env: dict[str, str] = {}
    redactor = SecretRedactor(env, [])
    text = "nothing to see here"
    assert redactor.redact(text) == text


def test_secret_multiple_times() -> None:
    env = {"KEY": "abc12345678"}
    redactor = SecretRedactor(env, ["KEY"])
    text = "abc12345678 abc12345678 abc12345678"
    expected = f"{redactor._MASK} {redactor._MASK} {redactor._MASK}"
    assert redactor.redact(text) == expected


def test_base64_encoded_secret_redacted() -> None:
    secret = "sk-or-v1-real-key-12345"
    env = {"KEY": secret}
    redactor = SecretRedactor(env, ["KEY"])
    b64 = base64.b64encode(secret.encode()).decode()
    assert redactor.redact(f"token={b64}") == f"token={redactor._MASK}"


def test_url_encoded_secret_redacted() -> None:
    secret = "sk-or-v1-real-key=12345"
    env = {"KEY": secret}
    redactor = SecretRedactor(env, ["KEY"])
    url = urllib.parse.quote(secret)
    assert redactor.redact(f"url?key={url}") == f"url?key={redactor._MASK}"


@pytest.mark.parametrize(
    ("env", "var", "match"),
    [
        ({}, "MISSING_KEY", "missing: MISSING_KEY"),
        ({"EMPTY_KEY": ""}, "EMPTY_KEY", "empty: EMPTY_KEY"),
        ({"SHORT_KEY": "ab"}, "SHORT_KEY", "too short"),
    ],
)
def test_secret_redactor_error_cases(env: dict[str, str], var: str, match: str) -> None:
    with pytest.raises(SecretRedactorError, match=match):
        SecretRedactor(env, [var])
