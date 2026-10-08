# Increment 99 — a checkbox marker nobody agreed on

STEP1 below is the *accepted* spelling and is here as a regression guard: a
capital X renders identically to a lower-case one in every Markdown viewer, so
CT36 normalises it to "done". Before CT36 it was not a step at all, which meant
its missing exit predicate was never checked and the step never appeared in the
lint.

STEP2 is the actual drift mode: a marker from some other tool's vocabulary. It
is reported rather than guessed at, because a marker outside the vocabulary
usually means the author wanted a state the schema does not have.

## SLICE1: mark steps with markers from elsewhere
STEPS: prescriptive
DEPS: —
INTENT: one marker is legal after normalisation, the other is not a state.
TESTS: tests/test_marker.py
- [X] STEP1: do the work (exit: the test passes.)
- [-] STEP2: a marker from another tool's vocabulary (exit: ditto.)
