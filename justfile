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

# Back-compat alias: `just lint` is the old name for `just check-fast`.
# Kept for muscle memory and existing docs (knowledge/ references it).
lint: check-fast

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

# Convenience runner for a fast, standalone pyrefly report.
#
# The leading `-` makes THIS RECIPE non-fatal so an agent can eyeball the full
# error list without the runner aborting. It does NOT make pyrefly advisory:
# pyrefly is a BLOCKING gate (Q50), enforced inside `just test` by
# tests/test_pyrefly_import_topology.py::test_pyrefly_check_passes. The recipe
# name is kept for back-compat with existing docs and muscle memory.
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
    uv run pytest --cov=fa --cov-report=term-missing --cov-report=xml --cov-report=json

# Targeted mutation testing against files changed vs origin/main. Blocking
# gate for the LLM-agent loop: if any mutant survives in code the agent
# touched, tests are not strong enough. Runs mutmut on a scoped
# source_paths derived from `git diff origin/main...HEAD`, restores
# pyproject.toml after. Advisory in CI (full weekly) is in tests.yml.
targeted-mutmut:
    uv run python scripts/run_targeted_mutmut.py

# Targeted semgrep SAST scan against files changed vs origin/main.
# Blocking gate in pre-push/CI; full-repo scan runs weekly (semgrep.yml).
targeted-semgrep:
    uv run python scripts/run_targeted_semgrep.py

# Vulnerability scanning (Dependencies + SAST)
audit:
    uv run pip-audit
    uvx semgrep scan --config=p/python --config=p/owasp-top-ten

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

# Guard: per-function coverage floors for src/fa/cli.py (S10a). Reads the
# JSON report `just test` writes. Deliberately NOT a pytest test: coverage
# flags are excluded from addopts so a bare `pytest tests/test_x.py` works,
# which means a test reading coverage.json would fail on every bare run.
cli-coverage-floor:
    uv run python scripts/check_cli_coverage_floor.py

# Lightweight environment readiness probe — verifies uv/just are on PATH,
# the active Python satisfies requires-python (>=3.13), the venv exists,
# and the four git hooks are installed/current. This is meant to run
# in seconds (no sync, no test execution) as a preflight for `pre-push`,
# NOT as a substitute for `just install`/`just agent-bootstrap`. It does
# NOT attempt to fix anything — a nonzero exit tells the caller (human
# or agent) exactly what prerequisite is missing.
doctor:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v uv >/dev/null 2>&1; then
        echo "doctor: uv not found on PATH — install uv (https://docs.astral.sh/uv/getting-started/installation/)" >&2; exit 127
    fi
    if ! command -v just >/dev/null 2>&1; then
        echo "doctor: just not found on PATH — run 'uv tool install rust-just>=1.57' or 'just install'" >&2; exit 127
    fi
    pyv=$(uv run python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    case "$pyv" in
      3.13|3.14|3.1[3-9]|3.[2-9][0-9]) : ;;
      *) echo "doctor: Python $pyv found; project requires >=3.13" >&2; exit 2 ;;
    esac
    if [ ! -d .venv ]; then
        echo "doctor: .venv missing — run 'just install' or 'uv sync --frozen --extra dev'" >&2; exit 2
    fi
    if ! uv run python -m fa.hygiene.hooks.status; then
        echo "doctor: git hooks are not correctly installed — run 'just install-hooks'" >&2; exit 2
    fi
    echo "doctor: OK (uv, just, python>=$pyv, .venv, hooks)"

# Fast static gates (no tests, no authoring-check that walks knowledge/).
# Runs in seconds; suitable as a pre-commit full-tree check after the
# staged-only autofix pass. Anything that needs network, filesystem
# walks of knowledge/, or pytest goes into `check` instead.
check-fast:
    uv run ruff check .
    uv run ruff format --check .
    uv run deptry src/
    uv run pylint src/fa

# Full local CI parity — all BLOCKING gates, short-circuits on the first
# failure (mirrors pre-push hook behaviour for a tight iteration loop).
# For "run everything and collect all failures" use check-all.
check: doctor lock-check dependency-contract-check check-fast typecheck authoring-check contract-check log-kind-check no-mocked-dataclasses test cli-coverage-floor targeted-mutmut targeted-semgrep
    @echo "check: all blocking gates passed"

# Full gate with NO short-circuit: runs every check and reports
# ALL failures in one pass. Use this when you want the entire error
# list at once (e.g. after a large refactor, or for an agent that
# consumes all failures in one LLM turn). Exits 0 iff every sub-check
# passed.
check-all: doctor
    @( set +e; rc=0; \
       for step in lock-check dependency-contract-check check-fast typecheck \
                   authoring-check contract-check log-kind-check \
                   no-mocked-dataclasses test cli-coverage-floor \
                   targeted-mutmut targeted-semgrep; do \
         echo ""; echo "══════ just $$step ══════"; \
         just $$step; s_rc=$$?; \
         if [ $$s_rc -ne 0 ]; then rc=$$s_rc; echo "^^^ $$step FAILED (rc=$$s_rc)"; fi; \
       done; \
       echo ""; echo "══════ summary ══════"; \
       if [ $$rc -eq 0 ]; then echo "check-all: all blocking gates passed"; \
                       else echo "check-all: ONE OR MORE GATES FAILED (last rc=$$rc)"; fi; \
       exit $$rc )
