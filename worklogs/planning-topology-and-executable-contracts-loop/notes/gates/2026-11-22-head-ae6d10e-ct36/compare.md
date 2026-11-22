## pytest: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-head-ae6d10e-ct36 — skipped, not counted

## mypy: 30 known -> 29 now, 0 new, 1 gone
- tests/test_ai_native_plan_v2.py: Argument 1 to "_cmd_invoke_workflow" has incompatible type "SimpleNamespace"; expected "Namespace"  [arg-type]

## ruff: 0 known -> 0 now, 0 new, 0 gone

## ruff-format: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-base-1acb56b — skipped, not counted

## authoring-check: 0 known -> 0 now, 0 new, 0 gone

NEW TOTAL: 0

## What this recording is, and what it is not (read before quoting it)

**Partial, by choice and by rule.** `pytest` was not recorded this round: the full suite is ~24 minutes on this
2-core sandbox and the operator asked for targeted runs. The targeted bucket that *was* run (10 modules —
acceptance bundle/collection/defect, slice verification runner, the S0 probe, authoring rules, plan v2, execution
client port, execution purposes, execution composition) gave **497 passed, 1 xfailed in 34.33 s**. The xfail is
`tests/test_ai_native_managed_substrate_probe.py`, whose prerequisite is the W4 Docker host.

**`ruff-format` has no baseline.** The base recording (`2026-11-22-base-1acb56b`) predates the gate, so its 8
findings are skipped rather than counted (E610's rule). Those 8 were separately proven pre-existing by checking
each file's base revision with the same ruff (E613). This is the first recording where the formatter is a gate at
all — the gap E613 found.

**Toolchain.** Recorded with the environment `scripts/arena-env-build.sh` publishes: CPython 3.13.16, mypy 2.1.0,
ruff 0.16.0 (pinned by `uv.lock`, and the version E613 was corrected against). The base recording was made before
that rebuild, so a mypy finding could in principle differ for toolchain reasons rather than code reasons; the one
difference here is a *gone* finding in `tests/test_ai_native_plan_v2.py`, which is not a claim of improvement —
nothing was done to it in this change set.
