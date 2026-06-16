"""Phase-5 tests: encoding-aware redaction backstop (ADR-12 / Hermes-CVE class)."""

from __future__ import annotations

import base64

from fa.observability.redaction import SecretRedactor

_SECRET = "sk-fireworks-supersecret-1234567890"


def _redactor() -> SecretRedactor:
    return SecretRedactor({"FIREWORKS_API_KEY": _SECRET}, ["FIREWORKS_API_KEY"])


def test_plaintext_redacted() -> None:
    r = _redactor()
    assert _SECRET not in r.redact(f"key is {_SECRET} ok")


def test_base64_literal_of_secret_redacted() -> None:
    r = _redactor()
    encoded = base64.b64encode(_SECRET.encode()).decode()
    assert encoded not in r.redact(f"leaked: {encoded}")


def test_hex_of_secret_redacted() -> None:
    r = _redactor()
    hexed = _SECRET.encode().hex()
    assert hexed not in r.redact(f"hexleak {hexed} end")


def test_base64_window_containing_secret_redacted() -> None:
    """An arbitrary base64 blob that DECODES to text containing the secret."""
    payload = f"prefix-{_SECRET}-suffix"
    blob = base64.b64encode(payload.encode()).decode()
    out = r_out = _redactor().redact(f"exfil={blob}")
    # the blob decodes to something containing the secret -> masked
    assert blob not in out
    assert _SECRET not in r_out


def test_non_secret_base64_left_alone() -> None:
    r = _redactor()
    benign = base64.b64encode(b"just some harmless config value here").decode()
    out = r.redact(f"data={benign}")
    assert benign in out  # not masked — decodes to no secret


def test_non_secret_hex_left_alone() -> None:
    r = _redactor()
    benign_hex = b"harmless-bytes-not-a-secret".hex()
    out = r.redact(f"h={benign_hex}")
    assert benign_hex in out
