.PHONY: install lint format typecheck authoring-check test check run audit deadcode

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

authoring-check:
	fa authoring-check

test:
	pytest

check: lint typecheck authoring-check test

run:
	fa --help

audit:
	pip-audit

deadcode:
	vulture src/ --min-confidence 90 || true
