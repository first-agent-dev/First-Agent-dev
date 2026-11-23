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

## Baseline gotchas (both measured the hard way)

1. **A worktree needs `--pythonpath`.** `pip install -e` points at the working tree; without
   `--pythonpath <worktree>/src` the "base" recording silently measures HEAD.
2. **A worktree also needs a `.venv` inside it.** The product's T0 baseline capture shells out to a
   literal `python -m pytest … -p fa.inner_loop.junit_nodeid_plugin`, and the gate environment puts
   `<workspace>/.venv/bin` first on `PATH`. In a worktree with no `.venv`, `python` resolves to the
   system interpreter, the plugin import fails, no JUnit report appears, T0 becomes
   `baseline-unavailable`, the coder stage is refused with exit 2 — and **114 tests fail for a reason
   that has nothing to do with the commit under test**. Symlink the venv (`ln -s … /tmp/base-wt/.venv`)
   and the same tests pass. A red baseline measured in a tree that cannot run the toolchain is not a
   baseline; it is a property of the tree.
3. **The suite is ~13–19 minutes.** Record it once, `--reuse pytest=<log>` afterwards. A `--tb=no -rf`
   run is enough for the nodeid list; re-run the survivors with `--tb=line` when a reason is needed.

## A gate that read clean while the gate failed (2026-11-22)

The first S2 recording printed `ruff exit=1 findings=0`. Both halves were true: ruff failed, and the
parser found nothing — the parser only knew `path:line:col: CODE msg` (concise), while ruff's default
output puts the code on one line and `--> path:line:col` on the next. So the gate reported "no
findings" for a run that had one (an unused import), which is exactly the failure `no new red` exists to
prevent: a green reading from a red run.

Two fixes: recordings now pass `--output-format=concise`, and the parser reads both shapes, pairing a
`CODE message` line with a following `--> location` line. Lesson for the next gate added here: **record
the exit code as a finding too** — `summary.json` keeps it, and a non-zero exit with an empty list is a
parser bug, never a clean tree.

## Partial recordings are named, not compared (2026-11-22)

The full suite costs ~24 minutes on this host, so a change set that cannot touch most of it may record
only the cheap gates (`--gate mypy --gate ruff --gate authoring-check`). `compare` now reports a gate
recorded on one side only as `not recorded in <dir> — skipped, not counted` and keeps it out of
`NEW TOTAL`. Before that rule, a partial head recording made the base's two pytest failures read as
`2 gone`, i.e. a cheap run looked like a repair. A partial recording is a legitimate economy; a partial
recording *read as a full one* is the same class of error as counting instead of listing.
