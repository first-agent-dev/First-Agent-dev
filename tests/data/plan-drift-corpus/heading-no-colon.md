# Increment 99 — a slice heading with no colon

Observed when a slice is renamed and the title is deleted along with its
separator. The id survives; the declaration does not.

#### SLICE1
STEPS: outcome
DEPS: —
INTENT: the colon is what makes this a slice declaration.
CONTRACTS:
  CT1 [FUNCTIONAL]: a rule nobody will ever check.
TESTS: tests/test_colon.py
