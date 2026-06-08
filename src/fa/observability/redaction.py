from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fa.providers.config import ModelsConfig


class SecretRedactor:
    """Mask exact secret strings from text. Stdlib-only.

    KNOWN LIMITATION: This redactor uses exact ``str.replace()`` of
    known env values. It will NOT catch base64-encoded, URL-encoded,
    or JSON-escaped variants of the same secret. This is an
    intentional trade-off: exact-match avoids false positives that
    would break tool outputs or code samples.
    """

    _MASK = "***REDACTED***"

    def __init__(self, env: Mapping[str, str], api_key_env_vars: Sequence[str]) -> None:
        self._secrets = {
            env[v] for v in api_key_env_vars
            if v in env and env[v] and len(env[v]) >= 8
        }

    @property
    def secrets(self) -> frozenset[str]:
        return frozenset(self._secrets)

    def redact(self, text: str) -> str:
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, self._MASK)
        return text

    @classmethod
    def from_models_config(
        cls, env: Mapping[str, str], config: ModelsConfig
    ) -> SecretRedactor:
        """Derive api_key_env list from a ModelsConfig."""
        vars = [
            entry.api_key_env
            for role in config.roles.values()
            for entry in role.chain
        ]
        return cls(env, vars)
