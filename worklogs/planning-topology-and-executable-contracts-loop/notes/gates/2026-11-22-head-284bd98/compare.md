## pytest: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-head-284bd98 — skipped, not counted

## mypy: 30 known -> 29 now, 0 new, 1 gone
- tests/test_ai_native_plan_v2.py: Argument 1 to "_cmd_invoke_workflow" has incompatible type "SimpleNamespace"; expected "Namespace"  [arg-type]

## ruff: 0 known -> 0 now, 0 new, 0 gone

## ruff-format: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-base-1acb56b — skipped, not counted

## authoring-check: 0 known -> 0 now, 0 new, 0 gone

NEW TOTAL: 0

## Scope of this recording (partial, stated as partial)

Recorded after E619 (F5: the substrate names the revision), commit `284bd98`. `pytest` was **not** recorded: the
full suite is ~24 minutes here and SLICE3 is not closed yet. The targeted bucket for this change was **523 passed
+ 1 xfailed in 19.96 s** over the acceptance bundle/collection/closure/defect files, the two V2 attempt files,
`tests/test_slice_verification_runner.py`, `tests/test_ai_native_managed_substrate_probe.py` and
`tests/test_execution_client.py` (the xfail is the S0 probe's W4-host prerequisite, unchanged).

`ruff-format`'s 8 findings are the known pre-existing list with no baseline to compare against (E613). mypy:
62 raw / 29 unique vs 30 at base -> 0 new, 1 gone; the one "gone" is pre-existing drift in
`tests/test_ai_native_plan_v2.py`, not a claim of improvement. Six hand-built mutants of the F5 seam were each
killed by their intended oracle (recorded in `notes/verification-entities-2026-11-22.md`).
