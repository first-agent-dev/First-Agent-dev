"""Private, in-memory secret store for API keys (secret-isolation invariant).

Security contract (see ``knowledge/adr/ADR-12-secret-isolation.md``):

* API-key VALUES are loaded from a file (``/run/secrets/fa.env`` in the AIO
  container, ``~/.fa/.env`` in WSL dev) into THIS object only.
* The store NEVER writes into ``os.environ``. Keeping keys out of the process
  environment means child processes (notably ``fs.run_bash`` and any interpreter
  it spawns) inherit nothing to exfiltrate.
* ``__repr__`` / ``__str__`` never render values, so an accidental log/traceback
  of the object cannot leak a key.
* The store is a read-only :class:`collections.abc.Mapping` so it drops into the
  existing injectable seams unchanged: ``ProviderChain(env=...)``,
  ``load_models_config(env=...)``, ``SecretRedactor(env=...)``.

Strict, file-only by design (no ``os.environ`` fallback): an operator
``docker run -e KEY=...`` does NOT feed provider auth. This maximises the
"no LLM can read the key" property and is the documented behaviour.
"""

from __future__ import annotations

import warnings
from collections.abc import Iterator, Mapping
from pathlib import Path

__all__ = ["SecretStore", "parse_env_file"]


def parse_env_file(text: str) -> dict[str, str]:
    """Parse ``KEY=value`` lines into a dict.

    Mirrors the historical ``_load_fa_dotenv`` semantics: ignore blank lines and
    ``#`` comments, split on the FIRST ``=`` (so ``KEY=a=b`` yields ``a=b``),
    and strip surrounding whitespace from key and value. Never logs content.
    """
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key:
            out[key] = value
    return out


class SecretStore(Mapping[str, str]):
    """Read-only mapping of secret names → values, never exposed to the env.

    Construct from a file (:meth:`from_file`) or directly from a mapping (tests).
    """

    __slots__ = ("_data",)

    def __init__(self, data: Mapping[str, str] | None = None) -> None:
        # Copy into a private dict; do not retain a reference to a caller mapping.
        self._data: dict[str, str] = dict(data) if data is not None else {}

    @classmethod
    def from_file(cls, path: Path) -> SecretStore:
        """Load secrets from ``path``.

        Fails gracefully (returns an empty/partial store with a warning) on a
        missing file, permission error, or malformed encoding — matching the
        prior loader's resilience. NEVER logs key names or values.
        """
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return cls({})
        except PermissionError as exc:
            warnings.warn(f"Permission denied reading {path}: {exc}", stacklevel=2)
            return cls({})
        except UnicodeDecodeError as exc:
            warnings.warn(
                f"Malformed encoding in {path} ({exc.encoding}): {exc}",
                stacklevel=2,
            )
            return cls({})
        except OSError as exc:
            warnings.warn(f"Could not load {path}: {exc}", stacklevel=2)
            return cls({})
        return cls(parse_env_file(text))

    # --- Mapping protocol --------------------------------------------------
    def __getitem__(self, key: str) -> str:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    # --- leak-proof representation ----------------------------------------
    def __repr__(self) -> str:  # pragma: no cover - exercised via test
        return f"SecretStore({len(self._data)} keys)"

    __str__ = __repr__
