# Cross-platform task runner for First-Agent-dev
# Install: cargo install just  (or download binary from GitHub releases)

set dotenv-load := false
set windows-shell := ["powershell.exe", "-Command"]

_default:
    just --list

install:
    uv sync --frozen --extra dev
    just install-hooks
    just hooks-status
    @echo ""
    @echo "Bootstrap complete:"
    @echo "  - Python env synced (with dev extras)"
    @echo "  - pre-commit / pre-push hooks installed"
    @echo "  - prepare-commit-msg / commit-msg hooks installed"
    @echo "  - Local commits are now guarded by hook chain"
    @echo "  - Run 'just hooks-status' to verify at any time"

# Canonical agent-environment bootstrap. The harness must invoke this recipe
# before declaring the workspace ready. It fails closed if dependency sync,
# hook installation, or hook status fails; the final marker is emitted only
# after all three steps succeed.
agent-bootstrap:
    uv run python scripts/bootstrap/host_bootstrap.py

# Install the M-6 commit-message hooks (prepare-commit-msg / commit-msg)
# into .git/hooks via the tested Python installer. Without this the
# git-hook seat of pr_intent + validate_test_edits is INERT —
# pre-commit does not manage the commit-msg stage in this repo.
# Idempotent (force-overwrites).  Delegates to the same installer
# that ``python -m fa.hygiene.hooks.install`` uses, so just and
# direct invocation share one code path.
#
# NOTE: do NOT set core.hooksPath here.  The default (.git/hooks)
# is already correct, and pre-commit install explicitly refuses to
# work when core.hooksPath is set (even to the default).  The old
# `git config core.hooksPath .git/hooks` line from the previous
# justfile caused "Cowardly refusing to install hooks" errors.
install-hooks:
    uv run python -m fa.hygiene.hooks.install --force

# Verify that local commit hooks are installed and active.
# Deterministic, zero-API-call status probe for all four hook seats
# (pre-commit, pre-push, prepare-commit-msg, commit-msg).  Run after
# ``just install`` or at any time to confirm the local hook chain.
hooks-status:
    uv run python -m fa.hygiene.hooks.status

lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run deptry src/
    uv run pylint src/fa

# Agents: run `just fix` after editing; it auto-resolves every mechanical
# lint/format finding (incl. RUF022 __all__ sorting) so none of it needs
# to be done by hand or held in context. Sequencing matters: `--fix-only`
# exits 0 even when judgment findings (S/BLE/C901/...) remain, so the
# format pass ALWAYS runs; the final `ruff check` then reports what needs
# an actual design decision (fix the code or add `# noqa: <code>` + a
# rationale comment — see AGENTS.md §Judgment rules).
fix:
    uv run ruff check --fix-only .
    uv run ruff format .
    uv run ruff check .

# Back-compat alias for `just fix`.
format: fix

typecheck:
    uv run mypy

typecheck-advisory:
    -uv run pyrefly check

authoring-check:
    uv run fa authoring-check

# Dependency allowlist gate: verifies every direct pyproject dependency is
# covered by the tracked TCB contract.
dependency-contract-check:
    uv run python scripts/check_dependency_contract.py

# Producer-consumer contract gate: verifies every EventType has both a
# producer (emit call in production code) and a consumer (handler in
# ConsoleRenderer). Prevents "not wired / partial implementation" gaps.
# See: knowledge/research/root-cause-analysis-not-wired-gaps-2026-07-19.md
contract-check:
    uv run python scripts/check_producer_consumer_contract.py

# LogKind contract gate (S6.1 / S6-F6): every LogKind member has a producer or
# a reasoned KNOWN_DORMANT_KINDS entry, dynamic kinds resolve, and
# CONSOLE_MIRROR_KINDS dual-write holds. Previously this script existed but was
# invoked by NOTHING, so its exit code was decorative.
log-kind-check:
    uv run python scripts/check_log_kind_contract.py

# Guard: no MagicMock(spec=<frozen_dataclass>) in tests. Frozen dataclasses
# are pure data — mock them and every new field becomes a latent regression.
# Use real instances (make_test_chain_config, etc.) instead.
no-mocked-dataclasses:
    uv run python scripts/check_no_mocked_dataclasses.py

# Full suite with the coverage gate (fail_under in pyproject). For a quick
# single-file iteration loop use plain `pytest tests/test_x.py` — no gate.
test:
    uv run pytest --cov=fa --cov-report=term-missing --cov-report=xml

# Vulnerability scanning (Dependencies + SAST)
audit:
    uv run pip-audit
    uvx semgrep --config=p/python --config=p/owasp-top-ten

deadcode:
    -uv run vulture src/ --min-confidence 90

# Mutation testing on the high-risk sandbox scope ([tool.mutmut] in
# pyproject). Slow (~1 min): runs the sandbox test files per mutant.
# Survivor-clearing tracker: knowledge/mutation-survivors-workplan.md
mutation:
    uv run mutmut run
    uv run mutmut results
    uv run mutmut export-cicd-stats

lock-check:
    uv lock --locked

check: lock-check dependency-contract-check lint typecheck authoring-check contract-check log-kind-check no-mocked-dataclasses test
