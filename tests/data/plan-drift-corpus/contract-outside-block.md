# Increment 99 — a contract declared outside its CONTRACTS: block

Observed when a contract is added in a hurry next to the step that motivated
it. It reads as a declaration and is only ever a reference.

## SLICE1: add a contract in the wrong place
STEPS: prescriptive
DEPS: —
INTENT: CT2 is never declared, only mentioned.
CONTRACTS:
  CT1 [FUNCTIONAL]: the declared one.
TESTS: tests/test_outside.py
- [ ] STEP1: also satisfy CT2, which lives nowhere (exit: tests pass.)
