---
title: "CI and quality guardrails closure"
compiled: 2026-07-22
goal_lens: "Make agent-authored Python arrive typed, tested, observable, and reviewable before CI rather than repaired after failures."
status: prepared
---

# PR note — CI and quality guardrails closure

INTENT: ADR-RULE
INVARIANT: Strict typing, live-path tests, observable failures, and CI are enforced by construction rather than by agent memory.

This change set closes the main quality-control gaps discovered while auditing
the First-Agent branch. It keeps the 86% coverage threshold blocking, adds
meaningful coverage for high-risk runtime paths, closes production Ruff and
strict-mypy findings, corrects the push-trigger behavior of the blocking CI
workflows, and prepares a Russian live-server execution plan for the remaining
S9 checks.

## Scope

The work is based on:

```text
db6fd884e38092e44254a1f33f6c259aa1297d2b
```

The principal implementation surfaces are:

- [`pyproject.toml`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/pyproject.toml)
- [`justfile`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/justfile)
- [`scripts/check_dead_flags.py`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/scripts/check_dead_flags.py)
- [`src/fa/inner_loop/subagent_runner.py`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/src/fa/inner_loop/subagent_runner.py)
- [`src/fa/runtime/pty_pool.py`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/src/fa/runtime/pty_pool.py)
- [`src/fa/blackboard/blackboard.py`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/src/fa/blackboard/blackboard.py)
- [`src/fa/stats.py`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/src/fa/stats.py)
- [`knowledge/instructions/03-live-server-ci-governance-plan-ru.md`](https://github.com/first-agent-dev/First-Agent-dev/blob/guardrails%2Bmistral-support/knowledge/instructions/03-live-server-ci-governance-plan-ru.md)

## What changed

Strict mypy is clean across the source and test tree. The fixes use runtime
boundary validation, typed mappings, explicit optional-dependency policies,
Protocols, narrowed exception handling, and typed helper contracts. No global
mypy suppression, `ignore_errors`, test exclusion, or blanket `Any` policy was
introduced.

Production Ruff is clean. The remaining complexity finding in
`check_dead_flags.py` was decomposed into regex detection, AST detection,
target-object classification, and deduplication. Safe unused-import cleanup
removed 106 F401 findings, followed by focused review and full-suite
verification. The operator audit script was renamed from the legacy hyphenated
name to `scripts/fa_host_layout_audit.py`; documentation and operator references
were updated.

Coverage was expanded with live and adversarial tests for PTY lifecycle and
cleanup, optional tool registration, subagent limits/history/artifacts,
blackboard authority and conflicts, session database failures, and analytics
edge cases. The following production defects were exposed and fixed during the
coverage work:

- session-context lookup was incorrectly treated as a spawn-limit failure;
- worklog aggregation could erase a valid subagent result;
- empty analytics aggregates had an unstable schema;
- workspace containment errors escaped file-tool structured result boundaries.

The blocking workflows now run on every `push` and `pull_request`, without path
filters. `Advisory CI/sanity-check` remains the authoritative `uv run just check`
path. Semgrep and mutation remain schedule/manual advisory jobs pending a
separate governance decision.

## Verification

```text
full pytest: 1826 passed, 13 skipped
full mypy: PASS — 274 files
source Ruff: PASS
producer/consumer contract: PASS
dependency contract: PASS
authoring TCB: PASS
no-mocked-dataclasses: PASS
Markdown links: PASS — 162 files
workflow path-filter check: PASS
git diff --check: PASS
```

The current aggregate coverage is approximately 80.25%, below the unchanged
86% blocking threshold. This is intentional: the gate was not lowered. The
next coverage work should continue on meaningful uncovered paths or be handled
by a separately documented coverage-policy decision.

## CI and live-server follow-up

The Russian operator plan is the live execution companion:

[`knowledge/instructions/03-live-server-ci-governance-plan-ru.md`](../instructions/03-live-server-ci-governance-plan-ru.md)

It covers Docker/read-only-rootfs smoke tests, pip-audit, gitleaks, Semgrep,
mutation, shipped-harness/session-path verification, GitHub governance, final
worktree review, and patch application.

The requested patch artifact is:

```text
first-agent-quality-closure.patch
base: db6fd884e38092e44254a1f33f6c259aa1297d2b
sha256: d6ac597fc30038e5da7fc742d8ef4fffe0e383f8fc99f816d2a71f76d0709ad5
```

The patch was checked with `git apply --check` on a clean worktree at the
requested base. No commit or push was performed by the agent.

## Human review checklist

- Confirm the intended branch and base SHA.
- Review workflow push behavior and required-check names in GitHub.
- Review the script rename as an operator-interface change.
- Confirm coverage remains blocking at 86%.
- Run the live-server plan and preserve command output/artifact URLs.
- Review staged changes before committing from VS Code or the harness.
- Confirm the agent identity has no merge, approval, or bypass permission.

## TEST-EDITS

tests/** — existing tests were modified only to align typed fixtures, strengthen
live-path oracles, preserve structured failure proofs, and remove unused
imports/locals after inspection; tests were not deleted to make a gate pass.
