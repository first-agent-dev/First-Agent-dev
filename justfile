# Cross-platform task runner for First-Agent-dev.
#
# Public interface (see AGENTS.md §Just recipes): six core recipes —
# `doctor`, `install`, `fix`, `test`, `check`, `check-deep` — plus a
# harness-facing alias `agent-bootstrap`. Underscore-prefixed recipes are
# INTERNAL; they exist for composition but are hidden from `just --list`
# and are NOT a stable surface.

set dotenv-load := false
set windows-shell := ["powershell.exe", "-Command"]

_default:
    just --list

# ---------------------------------------------------------------------------
# Public: environment / bootstrap
# ---------------------------------------------------------------------------

# Sub-second preflight: uv, just, python>=3.13, .venv, hooks, uv.lock.
#
# Read-only: never installs anything, never runs `uv sync`, never touches
# hooks. One-shot bootstrap lives in `just install` (and the harness-facing
# `just agent-bootstrap`); `doctor` is the cheap "is this shell pointed at
# a healthy clone?" probe called by humans, by the pre-push hook on skip
# paths, and by CI's doctor-preflight job.
doctor:
    #!/usr/bin/env bash
    set -euo pipefail
    fail=0
    ok()    { printf '✓ %s\n' "$*"; }
    bad()   { printf '✗ %s\n' "$*" >&2; fail=1; }
    have()  { command -v "$1" >/dev/null 2>&1; }

    if have uv;        then ok "uv ($(uv --version | awk '{print $2}'))"
    else                    bad "uv not found on PATH (install: https://docs.astral.sh/uv/getting-started/installation/)"; fi

    if have just;      then ok "just ($(just --version | awk '{print $2}'))"
    else                    bad "just not found on PATH (install: uv tool install rust-just==1.57.0)"; fi

        py=""
    if [[ "${CI:-}" == "true" ]]; then
        # In CI we trust setup-uv + uv sync; any python3 on PATH is fine
        # for the doctor preflight itself (it does not import fa).
        if have python3; then
            py_ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            ok "python ($py_ver, $(command -v python3)) [CI: version gate deferred to uv sync]"
        else
            bad "python3 not found on PATH"
        fi
    else
        for cand in python3.13 python3 python; do
            if have "$cand"; then py="$cand"; break; fi
        done
        if [[ -z "$py" ]]; then
            bad "no python3 interpreter found on PATH"
        else
            py_ver=$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            if [[ "$py_ver" == "3.13" || "$py_ver" == "3.14" ]]; then
                ok "python ($py_ver, $(command -v "$py"))"
            else
                bad "python >=3.13 required (found $py_ver at $(command -v "$py"))"
            fi
        fi
    fi

    # .venv: required locally (nothing else works without it), optional in CI
    # (each parallel CI job does its own `uv sync`; doctor is the cheap
    # preflight that runs BEFORE any sync, and uv lock --locked works without
    # a populated venv).
    if [[ -d ".venv" ]]; then
        ok ".venv present"
    elif [[ "${CI:-}" == "true" ]]; then
        ok ".venv: will be created by per-job uv sync"
    else
        bad ".venv missing — run: just install"
    fi

    if [[ -f "uv.lock" ]]; then
        if have uv && uv lock --check >/dev/null 2>&1; then ok "uv.lock in sync with pyproject.toml"
        else bad "uv.lock out of date — run: uv lock"; fi
    else
        bad "uv.lock missing"
    fi

    # Full local readiness is checked through the same read-only CT3 authority
    # used by every bootstrap alias. CI never commits/pushes from the checkout,
    # so its existing hooks/readiness exemption remains explicit.
    if [[ "${CI:-}" == "true" ]]; then
        ok "workspace readiness: not applicable (CI environment)"
    elif have uv && have python3 && [[ -x ".venv/bin/python" || -x ".venv/Scripts/python.exe" ]]; then
        if python3 scripts/bootstrap/workspace.py check --workspace . >/dev/null 2>&1; then
            ok "workspace readiness current (env, hooks, marker, cache sentinel)"
        else
            bad "workspace readiness missing/stale — run: just install"
        fi
    elif [[ -d ".venv" ]]; then
        bad "cannot verify workspace readiness (.venv present but not runnable)"
    else
        ok "workspace readiness: will be prepared by 'just install'"
    fi

    if [[ $fail -eq 0 ]]; then echo "doctor: OK (uv, just, python>=3.13, readiness, lock)"; fi
    exit $fail

# One-shot locked workspace readiness. The stdlib wrapper owns sync, hook-seat
# install, pre-commit environment prewarm, verification, and marker publication.
install:
    python3 scripts/bootstrap/workspace.py ensure --workspace .

# Harness/agent compatibility alias. Host-tool preparation remains separate;
# workspace state delegates to the same checked-out stdlib wrapper.
agent-bootstrap:
    python3 scripts/bootstrap/host_bootstrap.py

# ---------------------------------------------------------------------------
# Public: fix / test
# ---------------------------------------------------------------------------

# Auto-fix mechanical lint/format findings, then report what still needs judgment.
#
# Sequencing: `ruff check --fix-only` → `ruff format` → trailing plain
# `ruff check` so any finding fix-only couldn't resolve (BLE001 / C901 /
# S / ...) surfaces for a human decision. See AGENTS.md §Judgment rules
# for how to handle a remaining finding (fix the code; add a rationale'd
# waiver only when unavoidable).
fix:
    uv run ruff check --fix-only .
    uv run ruff format .
    uv run ruff check .

# Full pytest suite with branch coverage on src/fa, plus CLI coverage floor.
#
# Writes term/XML/JSON coverage reports (JSON feeds the CLI coverage-floor
# check). For rapid single-file iteration, call pytest directly — addopts
# stay strict-config/strict-markers, but --cov flags are intentionally
# NOT in addopts so a bare `pytest tests/test_x.py` stays green.
test:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run pytest --cov=fa --cov-report=term-missing --cov-report=xml --cov-report=json
    just _cli-cov-floor

# ---------------------------------------------------------------------------
# Public: check / check-deep
# ---------------------------------------------------------------------------

# Full blocking gate chain: run everything non-mutational; collect ALL errors.
#
# Does NOT fail-fast: every gate runs to completion so an agent sees the
# FULL error list in one pass (instead of iterating "one error per push",
# which the operator measured at ~5 minutes per cycle). Advisory vulture
# (dead-code scan) runs LAST with a leading `-` so it reports but never
# blocks. Pre-commit and CI sanity-check both converge here.
check:
    #!/usr/bin/env bash
    set -uo pipefail
    rc=0
    gate() {
        local name="$1"; shift
        printf '\n══════ %s ══════\n' "$name" >&2
        if "$@"; then
            printf '✓ %s\n' "$name" >&2
        else
            local g_rc=$?
            printf '✗ %s FAILED (rc=%s)\n' "$name" "$g_rc" >&2
            rc=$(( rc == 0 ? g_rc : rc ))
        fi
    }

    gate "lock-check"                               just _lock-check
    gate "lint (ruff+format+deptry+pylint-gap)"     just _lint
    gate "typecheck (mypy strict)"                  just _mypy
    gate "typecheck (pyrefly)"                      just _pyrefly
    gate "authoring-check"                          just _authoring
    gate "contracts (dep+pc+log-kind+no-mock-dc)"   just _contracts
    gate "shell-syntax (bash -n)"                   just _shell-syntax
    gate "test+coverage+cli-cov-floor"              just test
    printf '\n══════ deadcode (vulture, advisory — non-blocking) ══════\n' >&2
    just _deadcode || echo "  (vulture reported findings; advisory only, not failing the gate)" >&2
    printf '\n══════ summary ══════\n' >&2
    if [[ $rc -eq 0 ]]; then
        echo "check: all blocking gates passed" >&2
    else
        echo "check: ONE OR MORE GATES FAILED (first non-zero rc=$rc)" >&2
    fi
    exit $rc

# `check` + last-resort blocking gates: targeted mutmut and targeted semgrep.
#
# Pre-push hook and CI run this; local inner loops can use plain `just check`
# for speed. Targeted scope = Python files changed vs merge-base (or vs HEAD
# for uncommitted work), not the whole repo.
check-deep:
    #!/usr/bin/env bash
    set -euo pipefail
    just check
    just _targeted-semgrep
    just _targeted-mutmut

# ---------------------------------------------------------------------------
# Private gates (_-prefixed → hidden from `just --list`)
# ---------------------------------------------------------------------------

_lock-check:
    uv lock --locked

# Fast deterministic lint: ruff check, ruff format --check, deptry (src+scripts),
# pylint-gap src/fa.
#
# scripts/ are included in the deptry scan so an agent cannot smuggle an
# unused or hallucinated dependency into a CI/dev helper without deptry
# flagging it. Both source trees are passed as ROOTs in ONE invocation
# so scripts/ (which imports `fa` from src/) don't trigger false-positive
# DEP001 "imported but missing" errors.
# (src/fa stays under pylint gap-profile; scripts/ are advisory-linted
# in the CI scripts-lint job.)
#
# pylint gap-profile = duplicate-code (R0801) + cyclic-import (R0401), disable=all.
# Measured ~20 s on operator i5-1235U; fits the ~1 minute pre-commit budget.
_lint:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run ruff check .
    uv run ruff format --check .
    uv run deptry src/ scripts/
    uv run pylint src/fa

_mypy:
    uv run mypy

_pyrefly:
    uv run pyrefly check

_authoring:
    uv run fa authoring-check

# Four contract guards bundled: dependency-allowlist + producer-consumer + LogKind + no-mock-dc.
_contracts:
    #!/usr/bin/env bash
    set -euo pipefail
    uv run python scripts/check_dependency_contract.py
    uv run python scripts/check_producer_consumer_contract.py
    uv run python scripts/check_log_kind_contract.py
    uv run python scripts/check_no_mocked_dataclasses.py

_cli-cov-floor:
    uv run python scripts/check_cli_coverage_floor.py

# Shell-syntax preflight: bash -n every *.sh and every shipped git-hook shell script.
# Delegates to scripts/check_shell_syntax.sh (also used directly by pre-commit).
_shell-syntax:
    ./scripts/check_shell_syntax.sh

# Advisory dead-code scan (vulture). Called from `just check` with `-` so never blocks.
_deadcode:
    uv run vulture src/ --min-confidence 90

# Targeted mutation testing: mutmut on Python files changed vs merge-base.
#
# Last blocking gate in check-deep / pre-push. Full-repo mutmut scope runs
# weekly in CI (tests.yml), not here. Fail-open if mutmut is missing or
# FA_SKIP_TARGETED_MUTATION=1; timeout 600s; MAX_FILES=20.
_targeted-mutmut:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${FA_SKIP_TARGETED_MUTATION:-0}" == "1" ]]; then
        echo "targeted-mutmut: skipped (FA_SKIP_TARGETED_MUTATION=1)" >&2
        exit 0
    fi
    uv run python scripts/run_targeted_mutmut.py

# Targeted semgrep: Semgrep OSS (p/python + p/owasp-top-ten) on changed Python files.
#
# Last blocking gate alongside targeted-mutmut in check-deep / pre-push.
# Full-repo semgrep runs weekly in CI (semgrep.yml). Fail-open if uvx is
# unavailable or FA_SKIP_TARGETED_SEMGREP=1; timeout 120s; MAX_FILES=50.
_targeted-semgrep:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ "${FA_SKIP_TARGETED_SEMGREP:-0}" == "1" ]]; then
        echo "targeted-semgrep: skipped (FA_SKIP_TARGETED_SEMGREP=1)" >&2
        exit 0
    fi
    uv run python scripts/run_targeted_semgrep.py
