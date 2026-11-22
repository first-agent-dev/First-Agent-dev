# Gate recordings

One directory per recording: `<date>-<label>-<commit>`. Each holds, per gate:

| File | What it is |
|---|---|
| `<gate>.log` | the raw output, unedited (ANSI stripped only when parsing) |
| `<gate>.findings.txt` | the normalised finding list — **this is the unit of comparison** |
| `summary.json` | label, tree, exit code and finding count per gate |

`compare.md` / `compare.json` land in the **head** directory and hold the new/gone
sets per gate.

## Why lists and not counts

E608. Mid-S1 the mypy count went 83 → 65 → 62 and three of those errors were mine:
four disappeared and three appeared in the same step. A count says "how bad"; the
merge question is "did I add any". Only a set difference answers it.

## How a recording is made

```bash
# the tree under test, recorded honestly: a worktree of another commit needs
# --pythonpath, or the editable install imports the *working* tree's package
python scripts/gate_tracker.py record \
    --label base-1acb56b --out notes/gates/2026-11-22-base-1acb56b \
    --cwd /tmp/base-wt --pythonpath /tmp/base-wt/src

# the working tree
python scripts/gate_tracker.py record \
    --label head-e0cbea6 --out notes/gates/2026-11-22-head-e0cbea6

# a 25-minute suite is run once: ingest its log instead of running it again
python scripts/gate_tracker.py record --label head-e0cbea6 --out ... \
    --reuse pytest=/tmp/head-suite.log

# the gate: exits 1 when anything is new
python scripts/gate_tracker.py compare <base-dir> <head-dir>
```

## Normalisation, and why it is this coarse

Line and column numbers are dropped: they drift with every unrelated edit, and a
finding that moves is not a new finding. So a finding is

* pytest — the nodeid (`FAILED tests/x.py::test_y`), with the message dropped
  (it embeds tmp paths and digests);
* mypy — `file: message`, dotted line and column stripped;
* ruff — `file: CODE message`;
* `fa authoring-check` — the diagnostic count, since it reports no per-item lines.

## Reading a recording

`0 new` is the only passing verdict. `N gone` is welcome but never the point: a
disappearing finding can be a coincidence of two edits, which is exactly how the
three new mypy errors hid. Known red stays listed with a reason (environment,
host prerequisite, deferred fix) — never silently re-run until green.
