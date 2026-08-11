# Thin backward-compat shim — delegates every target to `just`.
#
# History note (2026-08-11): the previous Makefile shipped its OWN copies of
# each recipe (lint / test / check / install-hooks / ...). Those copies
# drifted from the justfile: they missed dependency-contract-check,
# log-kind-check, cli-coverage-floor, targeted-mutmut/semgrep; they ran
# `git config core.hooksPath .git/hooks` (documented upstream as harmful —
# `pre-commit install` refuses to work when core.hooksPath is set); and
# `make audit` was pip-audit only while `just audit` also ran semgrep.
# The result was that CI/local parity was silently broken whenever an
# operator typed `make` out of muscle memory.
#
# This shim forwards all targets to just, so the justfile is the single
# source of truth. `make check` continues to work for any existing docs,
# CI scripts, or muscle memory.

# List every target that anything is known to call so tab-completion and
# `make <target>` work. Unknown targets fall through to the % match-anything
# rule which also forwards to just.
.PHONY: install install-hooks hooks-status doctor lint fix format typecheck \
        typecheck-advisory authoring-check dependency-contract-check \
        contract-check log-kind-check no-mocked-dataclasses test check-fast \
        check check-all audit deadcode mutation lock-check cli-coverage-floor \
        targeted-mutmut targeted-semgrep agent-bootstrap run help

# Default goal (what you get when you type bare `make`): show just's help.
.DEFAULT_GOAL := help

help:
	@just --list

# Match-anything rule: forward to just. GNU make will try built-in implicit
# rules (%.o, etc.) first; those will fail because there is no source file
# to compile, so it falls through here. `@` silences the command echo so
# the output matches what just would print directly.
%:
	@just $@
