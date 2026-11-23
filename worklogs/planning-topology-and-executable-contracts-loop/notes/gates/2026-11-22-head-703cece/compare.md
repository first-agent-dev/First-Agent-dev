## pytest: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-head-703cece — skipped, not counted

## mypy: 30 known -> 29 now, 0 new, 1 gone
- tests/test_ai_native_plan_v2.py: Argument 1 to "_cmd_invoke_workflow" has incompatible type "SimpleNamespace"; expected "Namespace"  [arg-type]

## ruff: 0 known -> 0 now, 0 new, 0 gone

## ruff-format: not recorded in worklogs/planning-topology-and-executable-contracts-loop/notes/gates/2026-11-22-base-1acb56b — skipped, not counted

## authoring-check: 0 known -> 0 now, 0 new, 0 gone

NEW TOTAL: 0

## Scope of this recording (partial, stated as partial)

Recorded after E620 (the `PLAN-V2` controller branch, F10 item 3), commit `703cece`. `pytest` was **not** recorded:
the full suite is ~24 minutes here and SLICE3 is not closed yet. The targeted buckets for this change were
**576 passed in 181.16 s** (`tests/test_verify_gate_live.py`, including the live `_run_stage` → `verify_plan` /
`write_verification` kill-check oracle) and **149 passed in 37.91 s** (`test_s8_workflow_controller`,
`test_injection_threading`, `test_kill_directives`, `test_plan_candidate_retention`, `test_plan_reference`,
`test_s5p1_acquisition_seam`, `test_slice_id_validation`, `test_workflow_deadline`, `test_workflow_global_history`,
`test_workflow_no_eval_terminal`).

`ruff-format`'s 8 findings are the known pre-existing list with no baseline to compare against (E613). mypy:
62 raw / 29 unique vs 30 at base -> 0 new, 1 gone; the one "gone" is pre-existing drift in
`tests/test_ai_native_plan_v2.py`, not a claim of improvement. Five mutants of the branch were each killed by their
intended oracle (recorded in `notes/verification-entities-2026-11-22.md`).

**Recording pitfall, measured here:** an interim recording made after running `mypy tests/test_verify_gate_live.py`
on its own reported `+2 / -6` in `tests/test_ai_native_plan_v2.py` ("Module \"fa\" has no attribute \"cli\"").
That was not a code regression: the single-file invocation resolves `fa` through a different path and poisons
`.mypy_cache`. With the cache removed and the gate's own invocation used, the delta is the 0 new above. Record a
gate with `scripts/gate_tracker.py` only, and never from a cache warmed by a narrower `mypy` call.
