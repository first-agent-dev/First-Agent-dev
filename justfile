# Cross-platform task runner for First-Agent-dev
# Install: cargo install just  (or download binary from GitHub releases)

set dotenv-load := false
set windows-shell := ["powershell.exe", "-Command"]

_default:
    just --list

install:
    uv sync
    pre-commit install

lint:
    ruff check .
    ruff format --check .
    deptry src/

format:
    ruff check --fix .
    ruff format .

typecheck:
    mypy

typecheck-advisory:
    -pyrefly check

authoring-check:
    fa authoring-check

test:
    pytest

audit:
    pip-audit

deadcode:
    -vulture src/ --min-confidence 90

check: lint typecheck authoring-check test
