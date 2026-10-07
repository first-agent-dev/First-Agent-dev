# Plan drift corpus

One file per drift mode **actually observed** in this project, not per mode
imagined. Each file is a minimal increment that a human reads as correct and
that the extractor reads as something else. `tests/test_plan_precheck.py`
asserts that every file here produces at least one diagnostic, and that it
produces the *specific* rule the mode is about — naming a file is not covering
a mode.

Add a file here when a new way of silently losing plan content is found in the
wild. Do not add speculative ones: a corpus that is mostly hypothetical stops
being evidence of anything.

`README.md` is skipped by the tests, which glob `*.md` and look up expected
rules by filename; it is listed as having no expected rule.
