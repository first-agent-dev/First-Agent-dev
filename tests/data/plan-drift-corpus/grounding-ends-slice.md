# Increment 99 — a '##' subsection silently ends its slice

The measured S-e defect. Under CT16 a slice section ends at the first later
heading of depth less than or equal to its own, so a `## Grounding` written
*inside* a slice closes it. Everything below — here the TESTS: line — belongs
to no slice. It must be `### Grounding`.

## SLICE1: ground a slice with the wrong heading depth
STEPS: outcome
DEPS: —
INTENT: the slice ends four lines earlier than it looks like it does.
CONTRACTS:
  CT1 [FUNCTIONAL]: a rule whose test anchor is about to go missing.

## Grounding
Understood as: the parser recovers every field written under a slice.

TESTS: tests/test_grounding.py
