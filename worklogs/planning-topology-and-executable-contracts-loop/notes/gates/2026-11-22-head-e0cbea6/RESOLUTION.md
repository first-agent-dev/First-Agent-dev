# Resolution of the one new finding in `compare.md`

`compare` base `1acb56b` -> head `e0cbea6` reported **NEW TOTAL: 1**:

```
+ FAILED tests/test_console_encoding.py::test_scripts_with_non_ascii_output_force_utf8
```

Cause: the new `scripts/gate_tracker.py` draws box characters in its compare table and never called
`force_utf8_stdio()`, so on a cp1251 console it would have crashed *while reporting a gate verdict*.
The repository's own scan caught it — the gate working as designed.

Fixed in `ddb5c8f` (same shim as `scripts/check_dead_flags.py`: repo root on `sys.path`, call
`force_utf8_stdio()` first in `main`). Verified at that commit:

```
$ python -m pytest tests/test_console_encoding.py tests/test_c901_diff_guard.py -q
26 passed in 17.93s          # pytest-ddb5c8f-delta.log in this directory
```

The other difference in that run is a **measurement artifact, not a fix**: `- FAILED
tests/test_c901_diff_guard.py::test_no_new_c901_noqa_in_python_diff`. That guard scans
`merge-base(HEAD, main|origin/main|HEAD^)…HEAD`. In the baseline worktree at `1acb56b` **no candidate
resolves**: `origin/main` and `main` share no ancestor with this branch line, and the checkout does not
carry `1acb56b`'s parent object, so `HEAD^` is "not a valid object name". The guard therefore errors in
the worktree and passes in the branch checkout. It is a property of the checkout's history, not of the
commit, and it does not affect the merge decision at HEAD.

Full log of the worktree failure: `pytest-ddb5c8f-delta.log` (the run above includes the guard, which
passes at HEAD).
