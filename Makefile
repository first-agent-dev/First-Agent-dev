.PHONY: install lint format typecheck authoring-check test check run

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]"
	pre-commit install

lint:
	ruff check .
	ruff format --check .

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
