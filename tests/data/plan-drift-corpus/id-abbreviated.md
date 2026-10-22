# Increment 99 — ids shortened to S

Observed when a model echoes a plan back. Inside a plan `S1` is ambiguous: it
could be SLICE1 or STEP1, and both namespaces are present. The pre-check
reports it rather than picking one.

## S1: a shortened slice heading
STEPS: prescriptive
DEPS: —
INTENT: neither the heading nor the step below declares what it looks like.
TESTS: tests/test_abbrev.py
- [ ] S2: a shortened step id (exit: nothing checks this.)
