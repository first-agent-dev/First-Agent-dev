# Increment 99 — a continuation wrapped back to the margin

The defect that motivated CT35. A contract sentence runs long and the author
wraps it to column 0 like ordinary prose. That closes the CONTRACTS: block, so
CT1 is truncated and CT2 and CT3 are deleted outright. Nothing errors and the
Markdown renders exactly as intended.

## SLICE1: wrap a contract like prose
STEPS: outcome
DEPS: —
CONTRACTS:
  CT1 [FUNCTIONAL]: the extractor recovers every contract declared in the
block, including the ones whose text needed a second line to say.
  CT2 [CONSTRAINT]: gone.
  CT3 [PRESERVATION]: also gone.
TESTS: tests/test_wrap.py
