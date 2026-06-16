"""Phase B (ADR-12 B2): the model-facing tool-result channel is redacted.

Before this work, ``SecretRedactor`` was wired only into the trace/EventLog,
NOT into the messages sent to the LLM. These tests prove the single egress
chokepoint (``coder_loop._redact`` applied to ``project_for_model`` output)
masks a known secret value in raw and common-encoded forms — so even if a tool
returns a secret, the model never sees it (and thus can never repeat it).
"""

from __future__ import annotations

import base64
import urllib.parse

from fa.inner_loop.coder_loop import _redact
from fa.observability.redaction import SecretRedactor

_KEY = "fw-SECRET-DEPLOY-VALUE-abcdef0123456789"
_REDACTOR = SecretRedactor({"FIREWORKS_API_KEY": _KEY}, ["FIREWORKS_API_KEY"])
_MASK = "***REDACTED***"


def test_raw_secret_masked() -> None:
    out = _redact(_REDACTOR, f"here is the key {_KEY} ok")
    assert _KEY not in out
    assert _MASK in out


def test_base64_secret_masked() -> None:
    enc = base64.b64encode(_KEY.encode()).decode()
    out = _redact(_REDACTOR, f"leak: {enc}")
    assert enc not in out
    assert _KEY not in out


def test_hex_secret_masked() -> None:
    enc = _KEY.encode().hex()
    out = _redact(_REDACTOR, f"leak: {enc}")
    assert enc not in out


def test_url_encoded_secret_masked() -> None:
    enc = urllib.parse.quote(_KEY)
    out = _redact(_REDACTOR, f"leak: {enc}")
    assert _KEY not in urllib.parse.unquote(out)


def test_reversed_secret_masked() -> None:
    out = _redact(_REDACTOR, f"leak: {_KEY[::-1]}")
    assert _KEY[::-1] not in out


def test_none_redactor_is_passthrough() -> None:
    assert _redact(None, "anything") == "anything"


def test_non_secret_text_unchanged() -> None:
    out = _redact(_REDACTOR, "the planner role uses chat/completions")
    assert out == "the planner role uses chat/completions"
