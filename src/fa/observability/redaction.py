from __future__ import annotations

import base64
import urllib.parse
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fa.providers.config import ModelsConfig


class SecretRedactorError(Exception):
    """Raised when :class:`SecretRedactor` cannot be constructed because
    all requested API-key environment variables are missing, empty, or
    shorter than the minimum length threshold.
    """


class SecretRedactor:
    """Mask exact secret strings from text. Stdlib-only.

    Also catches base64-encoded and URL-encoded forms of known secrets
    so that encoded leakage does not bypass redaction.

    Raises :class:`SecretRedactorError` if ``api_key_env_vars`` is
    non-empty but no valid secrets are found (all missing, empty, or
    too short).
    """

    _MASK = "***REDACTED***"
    _MIN_LEN = 8

    def __init__(self, env: Mapping[str, str], api_key_env_vars: Sequence[str]) -> None:
        missing: list[str] = []
        empty: list[str] = []
        too_short: list[str] = []
        self._secrets: set[str] = set()

        for var in api_key_env_vars:
            if var not in env:
                missing.append(var)
                continue
            value = env[var]
            if not value:
                empty.append(var)
                continue
            if len(value) < self._MIN_LEN:
                too_short.append(var)
                continue
            self._secrets.add(value)

        if api_key_env_vars and not self._secrets:
            parts: list[str] = []
            if missing:
                parts.append(f"missing: {', '.join(missing)}")
            if empty:
                parts.append(f"empty: {', '.join(empty)}")
            if too_short:
                parts.append(f"too short (<{self._MIN_LEN}): {', '.join(too_short)}")
            raise SecretRedactorError(f"No valid secrets loaded. {'; '.join(parts)}")

    @property
    def secrets(self) -> frozenset[str]:
        return frozenset(self._secrets)

    def _normalize_and_check(self, text: str) -> bool:
        """Return True if ``text`` contains a known secret in any form."""
        for secret in self._secrets:
            if base64.b64encode(secret.encode()).decode() in text:
                return True
            if urllib.parse.quote(secret) in text:
                return True
            if secret in urllib.parse.unquote(text):
                return True
        return False

    def redact(self, text: str) -> str:
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, self._MASK)
            # Also redact encoded forms of this secret
            text = text.replace(base64.b64encode(secret.encode()).decode(), self._MASK)
            text = text.replace(urllib.parse.quote(secret), self._MASK)
        # Final pass: unquote the whole text in case the secret was
        # URL-encoded as part of a larger string not matched above.
        if self._normalize_and_check(text):
            unquoted = urllib.parse.unquote(text)
            for secret in sorted(self._secrets, key=len, reverse=True):
                unquoted = unquoted.replace(secret, self._MASK)
            text = unquoted
        return text

    @classmethod
    def from_models_config(cls, env: Mapping[str, str], config: ModelsConfig) -> SecretRedactor:
        """Derive api_key_env list from a ModelsConfig."""
        env_vars = [entry.api_key_env for role in config.roles.values() for entry in role.chain]
        return cls(env, env_vars)


__all__ = ["SecretRedactor", "SecretRedactorError"]
