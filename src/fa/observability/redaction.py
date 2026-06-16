from __future__ import annotations

import base64
import binascii
import re
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
    # Candidate encoded windows for the decoded-scan backstop. Min length keeps
    # false positives down (short tokens rarely decode to a real secret).
    _B64_WINDOW_RE = re.compile(r"[A-Za-z0-9+/]{16,}={0,2}")
    _HEX_WINDOW_RE = re.compile(r"(?:[0-9a-fA-F]{2}){8,}")

    def __init__(
        self,
        env: Mapping[str, str],
        api_key_env_vars: Sequence[str],
        *,
        extra_values: Sequence[str] = (),
        allow_empty: bool = False,
    ) -> None:
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

        # Extra non-env secret values (e.g. proxy bootstrap token, deploy-key
        # material in egress-proxy mode where provider keys are absent here).
        for value in extra_values:
            if value and len(value) >= self._MIN_LEN:
                self._secrets.add(value)

        if api_key_env_vars and not self._secrets and not allow_empty:
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
            if secret[::-1] in text:
                return True
        return False

    def redact(self, text: str) -> str:
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, self._MASK)
            # Also redact encoded forms of this secret
            text = text.replace(base64.b64encode(secret.encode()).decode(), self._MASK)
            text = text.replace(secret.encode().hex(), self._MASK)
            text = text.replace(urllib.parse.quote(secret), self._MASK)
            # Reversed-string form (cheap, deterministic; covers the common
            # "print the key backwards" redaction bypass — Hermes-CVE class).
            text = text.replace(secret[::-1], self._MASK)
        # Final pass: unquote the whole text in case the secret was
        # URL-encoded as part of a larger string not matched above.
        if self._normalize_and_check(text):
            unquoted = urllib.parse.unquote(text)
            for secret in sorted(self._secrets, key=len, reverse=True):
                unquoted = unquoted.replace(secret, self._MASK)
            text = unquoted
        # Defense-in-depth backstop (ADR-12 / Hermes-CVE class): scan base64/hex
        # *windows* and, if a decoded window contains a known secret, mask the
        # whole window. Catches an agent that runtime-encodes a value it somehow
        # obtained (the primary boundary is keys-not-reachable; this is a net).
        text = self._redact_encoded_windows(text)
        return text

    def _redact_encoded_windows(self, text: str) -> str:
        if not self._secrets:
            return text

        def _b64(match: re.Match[str]) -> str:
            token = match.group(0)
            try:
                decoded = base64.b64decode(token, validate=True).decode(
                    "utf-8", errors="replace"
                )
            except (ValueError, binascii.Error):
                return token
            return self._MASK if any(s in decoded for s in self._secrets) else token

        def _hex(match: re.Match[str]) -> str:
            token = match.group(0)
            try:
                decoded = bytes.fromhex(token).decode("utf-8", errors="replace")
            except ValueError:
                return token
            return self._MASK if any(s in decoded for s in self._secrets) else token

        text = self._B64_WINDOW_RE.sub(_b64, text)
        text = self._HEX_WINDOW_RE.sub(_hex, text)
        return text

    @classmethod
    def from_models_config(
        cls,
        env: Mapping[str, str],
        config: ModelsConfig,
        *,
        extra_values: Sequence[str] = (),
        allow_empty: bool = False,
    ) -> SecretRedactor:
        """Derive api_key_env list from a ModelsConfig.

        In egress-proxy mode the provider keys are absent from ``env`` (they
        live in the proxy), so pass ``allow_empty=True`` and seed ``extra_values``
        with the deploy key / proxy token that DO live in this process.
        """
        env_vars = [entry.api_key_env for role in config.roles.values() for entry in role.chain]
        return cls(env, env_vars, extra_values=extra_values, allow_empty=allow_empty)


__all__ = ["SecretRedactor", "SecretRedactorError"]
