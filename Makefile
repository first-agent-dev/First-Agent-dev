# Thin shim over `just`.
#
# The canonical task surface lives in `justfile` (see AGENTS.md §Just recipes
# for the six public names). This Makefile exists for muscle memory and for
# tooling that invokes `make`; every target forwards to `just` so the two
# cannot drift. New gates are added in justfile, not here.
#
# USAGE:
#   make            -> lists the six public recipes (same as `just --list`)
#   make <target>   -> forwards to `just <target>`
#
# NOTE: do NOT set `core.hooksPath` here. The default .git/hooks is already
# correct and pre-commit refuses to install when core.hooksPath is set.

JUST ?= just

.DEFAULT_GOAL := help

# Public recipe list mirrors justfile; any target in this list or matching the
# catch-all pattern below forwards to just.
.PHONY: help doctor install fix test check check-deep agent-bootstrap

help:
	@$(JUST) --list

doctor install fix test check check-deep agent-bootstrap:
	@$(JUST) "$@"

# Catch-all: any other target (private _targeted-mutmut, _lint, etc.) forwards
# to just too, so `make _lint` works for ad-hoc use.
%:
	@$(JUST) "$@"
