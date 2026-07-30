.PHONY: install lint fix format typecheck authoring-check contract-check no-mocked-dataclasses test lock-check check run audit deadcode mutation install-hooks

install:
	uv sync
	pre-commit install
	$(MAKE) install-hooks

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

fix:
	ruff check --fix-only .
	ruff format .
	ruff check .

format: fix

typecheck:
	mypy

authoring-check:
	fa authoring-check

contract-check:
	python scripts/check_producer_consumer_contract.py

log-kind-check:
	python scripts/check_log_kind_contract.py

no-mocked-dataclasses:
	python scripts/check_no_mocked_dataclasses.py

test:
	pytest --cov=fa --cov-report=term-missing --cov-report=xml

lock-check:
	uv lock --locked

check: lock-check lint typecheck authoring-check contract-check no-mocked-dataclasses test

run:
	fa --help

audit:
	pip-audit

deadcode:
	vulture src/ --min-confidence 90 || true

mutation:
	mutmut run
	mutmut results
	mutmut export-cicd-stats
