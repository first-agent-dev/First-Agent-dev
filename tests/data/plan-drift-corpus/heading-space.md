# Increment 99 — a space inside the slice id

Observed when a plan is reformatted by a tool that "tidies" headings, or when
an author copies a title out of prose. Renders identically; declares nothing.

## SLICE 1: tidy the extractor
STEPS: prescriptive
DEPS: —
INTENT: everything in this section is invisible to the harness.
CONTRACTS:
  CT1 [FUNCTIONAL]: a rule nobody will ever check.
TESTS: tests/test_tidy.py
- [ ] STEP1: do the work (exit: the test passes.)
