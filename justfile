# Cross-platform task runner for First-Agent-dev
# Install: cargo install just  (or download binary from GitHub releases)

set dotenv-load := false
set windows-shell := ["powershell.exe", "-Command"]

_default:
    just --list

install:
    uv sync
    pre-commit install
    just install-hooks

# Symlink the M-6 commit-message hooks (prepare-commit-msg / commit-msg)
# into .git/hooks. Without this the git-hook seat of pr_intent +
# validate_test_edits is INERT — pre-commit does not manage the
# commit-msg stage in this repo. Idempotent (force-overwrites).
install-hooks:
    git config core.hooksPath .git/hooks
    cp -f src/fa/hygiene/hooks/prepare-commit-msg .git/hooks/prepare-commit-msg
    cp -f src/fa/hygiene/hooks/commit-msg .git/hooks/commit-msg
    chmod +x .git/hooks/prepare-commit-msg .git/hooks/commit-msg

lint:
    ruff check .
    ruff format --check .
    deptry src/
    pylint src/fa

# Agents: run `just fix` after editing; it auto-resolves every mechanical
# lint/format finding (incl. RUF022 __all__ sorting) so none of it needs
# to be done by hand or held in context. Sequencing matters: `--fix-only`
# exits 0 even when judgment findings (S/BLE/C901/...) remain, so the
# format pass ALWAYS runs; the final `ruff check` then reports what needs
# an actual design decision (fix the code or add `# noqa: <code>` + a
# rationale comment — see AGENTS.md §Judgment rules).
fix:
    ruff check --fix-only .
    ruff format .
    ruff check .

# Back-compat alias for `just fix`.
format: fix

typecheck:
    mypy

typecheck-advisory:
    -pyrefly check

authoring-check:
    fa authoring-check

# Full suite with the coverage gate (fail_under in pyproject). For a quick
# single-file iteration loop use plain `pytest tests/test_x.py` — no gate.
test:
    pytest --cov=fa --cov-report=term-missing --cov-report=xml

audit:
    pip-audit

deadcode:
    -vulture src/ --min-confidence 90

# Mutation testing on the high-risk sandbox scope ([tool.mutmut] in
# pyproject). Slow (~1 min): runs the sandbox test files per mutant.
# Survivor-clearing tracker: knowledge/mutation-survivors-workplan.md
mutation:
    mutmut run
    mutmut results
    mutmut export-cicd-stats

lock-check:
    uv lock --locked

check: lock-check lint typecheck authoring-check test
