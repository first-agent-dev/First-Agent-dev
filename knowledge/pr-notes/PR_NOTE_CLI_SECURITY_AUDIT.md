# PR Note: CLI Consolidation, Transparent Stdin, and Security Audit
**Date:** 2026-07-02
**Type:** Refactor & Security Fixes

## Problem Statement
The codebase suffered from three distinct issues identified during routine audits and testing:
1. **CLI Help Fragmentation:** The `argparse` configuration in `src/fa/cli.py` and the bilingual help registry in `src/fa/cli_help.py` had drifted. `fa run --help` and `fa help run` produced different, conflicting outputs. 
2. **Bash Piping Inflexibility:** Piping data into `fa run` required explicitly using the `-` flag (`cat file | fa run -`), making it impossible to easily combine piped context with a distinct instruction prompt.
3. **Security Technical Debt:** The CI lacked a local SAST execution layer. When `semgrep` was introduced, it revealed 21 findings—mostly mutable Action tags (`@v4`) vulnerable to supply-chain attacks, and unsafe "curl | bash" installation patterns in GitHub workflows.

## Decisions & Mechanics

### 1. Single Source of Truth (SSOT) for CLI Help
- **Consolidation:** `src/fa/cli_help.py` is now the strict SSOT. We wrote an AST-based script (during the session) to dynamically bind `help=` arguments in `cli.py` directly to the `COMMANDS` dictionary from `cli_help.py`.
- **UI Clean-up:** `fa run --help` now prints the standard `argparse` block in English, followed by a clearly separated `--- Справка на русском языке ---` quick-reference block.
- **Drift Prevention:** `test_help_registry_covers_real_commands` now asserts that every subcommand registered in `argparse` exists in the `cli_help` registry.

### 2. Transparent Stdin Processing
- **Mechanic:** `_resolve_task()` in `cli.py` now checks `sys.stdin.isatty()`. If piped data exists AND an explicit task string is provided, it seamlessly concatenates them (`[Task]\n\n<stdin>\n[Piped Data]\n</stdin>`).
- **Compatibility:** The legacy `-` flag behavior is preserved, but no longer strictly required for standard piping. Pytest mock environments are safely handled via `try/except` fallbacks.

### 3. Local SAST & Zero-Trust CI Hardening
- **Local Audit:** Added `uvx semgrep` to the `just audit` target and documented its advisory usage in `AGENTS.md` and `ci-guardrails-reference.md`.
- **Zero-Trust GitHub Actions:** 
  - Replaced all mutable action tags (`@v4`, `@v3`) with strict 40-character SHA-256 commit hashes (e.g., `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4`).
  - **Eliminated `curl | bash`:** Replaced the unsafe `just.systems` installer pipe with the official, securely pinned `extractions/setup-just@<sha>` action.
- **TCB Bash Waiver:** Retained `shell=True` in `run_bash.py` as it is a core contract of the Agent's sandbox (ADR-6). Added `# nosemgrep` to explicitly document the waiver.

### 4. Test Environment Resilience
- Addressed `noexec` tmpfs mount failures in CI environments by ensuring `test_executable_script_modes_are_pinned` and `install_hooks` gracefully `pytest.skip()` when the filesystem natively blocks `+x` execution, rather than failing the suite.
