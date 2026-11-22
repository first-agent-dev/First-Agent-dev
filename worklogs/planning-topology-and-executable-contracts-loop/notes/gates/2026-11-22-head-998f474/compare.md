## pytest: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-head-998f474 — skipped, not counted

## mypy: 30 known -> 29 now, 0 new, 1 gone
- tests/test_ai_native_plan_v2.py: Argument 1 to "_cmd_invoke_workflow" has incompatible type "SimpleNamespace"; expected "Namespace"  [arg-type]

## ruff: 0 known -> 0 now, 0 new, 0 gone

## ruff-format: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-base-1acb56b — skipped, not counted

## authoring-check: 0 known -> 0 now, 0 new, 0 gone

NEW TOTAL: 0

## Scope of this recording (partial, stated as partial)

Recorded after E618 (the sealed -> attempt projection, F10 item 1), commit `998f474`. `pytest` was **not**
recorded: the full suite is ~24 minutes here and SLICE3 is not closed yet. The targeted bucket run for this change
was **314 passed in 9.70 s** over `tests/test_ai_native_acceptance_bundle.py`,
`tests/test_ai_native_acceptance_collection.py`, `tests/test_ai_native_acceptance_closure.py`,
`tests/test_ai_native_acceptance_defect.py`, `tests/test_v2_verification_attempt.py`,
`tests/test_v2_sealed_attempt.py` and `tests/test_slice_verification_runner.py`; `tests/test_authoring_rules_tests.py`
37 passed separately (V4's xfail rule).

`ruff-format`'s 8 findings are the known pre-existing list with no baseline to compare against (E613), unchanged by
this change. mypy: 62 raw / 29 unique vs 30 at base -> 0 new, 1 gone; the one "gone" is pre-existing drift in
`tests/test_ai_native_plan_v2.py`, so it is not a claim of improvement. Seven hand-built mutants of the projection
and of the corrected total rule were each killed by their intended test (recorded in
`notes/verification-entities-2026-11-22.md`).
