import pytest

from fa.observability.redaction import SecretRedactor


class FakeModelsConfig:
    """Minimal stand-in for ModelsConfig with .roles[role].chain entries."""
    def __init__(self, env_vars: list[str]) -> None:
        self.roles = {
            "coder": type("Role", (), {"chain": [type("Entry", (), {"api_key_env": v}) for v in env_vars]})
        }


def test_exact_match():
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345"}
    redactor = SecretRedactor(env, ["OPENROUTER_API_KEY"])
    assert redactor.redact("The key is sk-or-v1-real-key-12345.") == "The key is ***REDACTED***."


def test_substring_replacement():
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345"}
    redactor = SecretRedactor(env, ["OPENROUTER_API_KEY"])
    assert (
        redactor.redact("prefix sk-or-v1-real-key-12345 suffix")
        == "prefix ***REDACTED*** suffix"
    )


def test_no_false_positive():
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345"}
    redactor = SecretRedactor(env, ["OPENROUTER_API_KEY"])
    text = "This is not the key: sk-or-v1-fake-key."
    assert redactor.redact(text) == text


def test_multiline_secret():
    env = {"KEY": "line1\nline2"}
    redactor = SecretRedactor(env, ["KEY"])
    assert redactor.redact("start\nline1\nline2\nend") == "start\n***REDACTED***\nend"


def test_nested_dict_redaction():
    """Simulate tool_call["params"] values being redacted."""
    env = {"KEY": "secret-token"}
    redactor = SecretRedactor(env, ["KEY"])
    params = {"cmd": "curl -H 'Authorization: secret-token'"}
    redacted = {k: redactor.redact(v) for k, v in params.items()}
    assert redacted["cmd"] == "curl -H 'Authorization: ***REDACTED***'"


def test_from_models_config():
    env = {"OPENROUTER_API_KEY": "sk-or-v1-real-key-12345", "FIREWORKS_API_KEY": "fw-fake-key-67890"}
    config = FakeModelsConfig(["OPENROUTER_API_KEY", "FIREWORKS_API_KEY"])
    redactor = SecretRedactor.from_models_config(env, config)
    assert "sk-or-v1-real-key-12345" not in redactor.redact("key: sk-or-v1-real-key-12345")
    assert "fw-fake-key-67890" not in redactor.redact("key: fw-fake-key-67890")


def test_empty_env_var_skipped():
    env = {"EMPTY_KEY": ""}
    redactor = SecretRedactor(env, ["EMPTY_KEY"])
    # Should not crash; .redact should be a no-op
    assert redactor.redact("nothing to see here") == "nothing to see here"
