"""S24: Kill-check test for actionable error messages in providers/ and coder_loop.

root=C0p property matrix=C claim=every ConfigurationError/ValueError includes fix guidance
kill-check=removing 'Fix:' or config-file reference from a message → test fails
path-inventory: 17 raise sites across 4 files

Principle (user intent): "properly log all possible errors — early dev stage,
explicit error messaging to make debugging a better experience."

The test scans all raise ConfigurationError / raise ValueError sites in the
target files and verifies each message contains at least one actionable fix
reference — either 'Fix:', 'models.yaml', '~/.fa/', or '__post_init__'.
This ensures that when an operator hits a config error, the message is
self-contained: they know what file to edit, not just what went wrong.
"""

from __future__ import annotations

from pathlib import Path

# Files where ConfigurationError/ValueError messages must include fix guidance
TARGET_FILES = [
    "src/fa/providers/chain.py",
    "src/fa/providers/config.py",
    "src/fa/providers/registry.py",
    "src/fa/inner_loop/coder_loop.py",
]

# Acceptable fix-guidance keywords in error messages
FIX_KEYWORDS = ("Fix:", "models.yaml", "~/.fa/", "__post_init__")


def test_all_config_errors_include_fix_guidance() -> None:
    """C0p: every ConfigurationError/ValueError in target files includes fix guidance.

    kill-check: removing the 'Fix:' line from a ConfigurationError message
    makes this test fail for that site.
    """
    violations: list[str] = []

    for fpath in TARGET_FILES:
        source = Path(fpath).read_text(encoding="utf-8")
        lines = source.splitlines()

        for i, line in enumerate(lines):
            if "raise ConfigurationError" not in line and "raise ValueError" not in line:
                continue
            # Skip ReservedProviderError (different exception class)
            if "ReservedProviderError" in line:
                continue

            # Check surrounding 6 lines for fix-guidance keywords
            context = "\n".join(lines[max(0, i - 1) : i + 6])
            has_fix = any(kw in context for kw in FIX_KEYWORDS)

            if not has_fix:
                preview = line.strip()[:100]
                violations.append(f"{fpath}:{i + 1}: {preview}")

    assert not violations, (
        f"{len(violations)} error message(s) missing fix guidance "
        f"(expected one of {FIX_KEYWORDS}):\n"
        + "\n".join(f"  - {v}" for v in violations)
    )


def test_config_error_messages_mention_models_yaml() -> None:
    """C0p: ConfigurationError messages in providers/ mention ~/.fa/models.yaml.

    This is a tighter property than the general fix-guidance check:
    all provider config errors should tell the operator which file to edit.

    kill-check: replacing 'models.yaml' with a generic string makes this fail.
    """
    violations: list[str] = []

    provider_files = [
        "src/fa/providers/chain.py",
        "src/fa/providers/config.py",
        "src/fa/providers/registry.py",
    ]

    for fpath in provider_files:
        source = Path(fpath).read_text(encoding="utf-8")
        lines = source.splitlines()

        for i, line in enumerate(lines):
            if "raise ConfigurationError" not in line:
                continue
            if "ReservedProviderError" in line:
                continue

            context = "\n".join(lines[max(0, i - 1) : i + 6])
            if "models.yaml" not in context:
                preview = line.strip()[:100]
                violations.append(f"{fpath}:{i + 1}: {preview}")

    assert not violations, (
        f"{len(violations)} ConfigurationError(s) in providers/ missing "
        f"'models.yaml' reference:\n"
        + "\n".join(f"  - {v}" for v in violations)
    )
