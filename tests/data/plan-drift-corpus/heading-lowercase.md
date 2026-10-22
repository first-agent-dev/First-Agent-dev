# Increment 99 — a lower-case slice id

Observed when a plan is drafted in an editor with sentence-case heading
autocorrect, and when a model echoes the heading back in prose casing.

## slice1: lowercase and therefore absent
STEPS: outcome
DEPS: —
INTENT: parses as an ordinary Markdown heading, not as a slice.
CONTRACTS:
  CT1 [CONSTRAINT]: a rule nobody will ever check.
TESTS: tests/test_lower.py
