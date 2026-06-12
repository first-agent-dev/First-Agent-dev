.PHONY: install lint fix format typecheck authoring-check test lock-check check run audit deadcode

install:
	uv sync
	pre-commit install

lint:
	ruff check .
	ruff format --check .
	deptry src/
	pylint src/fa

fix:
	ruff check --fix-only .
	ruff format .
	ruff check .

format: fix

typecheck:
	mypy

authoring-check:
	fa authoring-check

test:
	pytest --cov=fa --cov-report=term-missing --cov-report=xml

lock-check:
	uv lock --locked

check: lock-check lint typecheck authoring-check test

run:
	fa --help

audit:
	pip-audit

deadcode:
	vulture src/ --min-confidence 90 || true
