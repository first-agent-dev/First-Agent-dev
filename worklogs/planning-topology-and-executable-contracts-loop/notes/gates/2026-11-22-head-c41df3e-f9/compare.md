## pytest: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-head-c41df3e-f9 — skipped, not counted

## mypy: 30 known -> 29 now, 0 new, 1 gone
- tests/test_ai_native_plan_v2.py: Argument 1 to "_cmd_invoke_workflow" has incompatible type "SimpleNamespace"; expected "Namespace"  [arg-type]

## ruff: 0 known -> 0 now, 0 new, 0 gone

## ruff-format: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-base-1acb56b — skipped, not counted

## authoring-check: 0 known -> 0 now, 0 new, 0 gone

NEW TOTAL: 0

## Scope of this recording (partial, stated as partial)

Recorded after E616 (the attempt entity + the F9 refusal), commit `c41df3e`. `pytest` was not recorded: the full
suite is ~24 minutes here and SLICE3 is not closed yet. The targeted bucket run for this change was 225 passed +
1 xfailed in 9.25 s (attempt entity, acceptance bundle, acceptance collection, slice verification runner, S0 probe).
`ruff-format`'s 8 findings are the known pre-existing list with no baseline to compare against (E613).
mypy: 0 new, the one "gone" is pre-existing drift in `tests/test_ai_native_plan_v2.py` — nothing in this change set
touched it, so it is not a claim of improvement.
