# Increment 99 — one contract id, two owners

Observed when a slice is split in two and the contracts are copied rather than
partitioned. "CT1 is green" then means whichever of the two the harness
happened to tick.

## SLICE1: the first owner
STEPS: outcome
DEPS: —
CONTRACTS:
  CT1 [FUNCTIONAL]: the extractor returns slice ids.
TESTS: tests/test_first.py

## SLICE2: the second owner
STEPS: outcome
DEPS: SLICE1
CONTRACTS:
  CT1 [CONSTRAINT]: the extractor never raises.
TESTS: tests/test_second.py
