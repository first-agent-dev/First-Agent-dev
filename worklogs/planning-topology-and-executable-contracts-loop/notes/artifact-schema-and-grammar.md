# Artifact schema & grammar (canonical)

The contract for every planning artifact in this project. `plan_ids.py` parses this;
the planning skills emit it; humans and agents read it. **If the grammar changes, this
file, the skills, and the extractor change together** (that coupling is enforced by
I01's conformance test, CT12).

## 1. The four artifacts

```
worklogs/<slug>/
  roadmap.md        one per project — the index and the far-term map
  ledger.md         one per project — append-only EVIDENCE, provenance-tagged
  increments/
    increment-NN-<slug>.md   one per increment; SLICE#s are SECTIONS inside
  notes/            supporting specs, reviews, research (this file lives here)
```

Rules:
- **Folder** = a pure, stable kebab **slug** (no date in the path). `created:` lives in
  `roadmap.md` frontmatter.
- **Increments** are zero-padded (`increment-01-…`) so lexical order is correct.
- **Slices are sections, never files.** The coder is scoped to one `## SLICE#` section
  via `plan_ids.section(...)`.
- **Ephemeral run records** (`eval_report.json`, `events.jsonl`, telemetry) do **not**
  live here — they stay in the session-log root. This folder is the durable, readable
  planning layer.
- **Skill artifacts** live at `knowledge/skills/<name>/SKILL.md`.
- **Write agent-executable text as exact imperatives.** Name file:line targets and runnable
  exit checks; omit citations, history, and rationale from the instruction itself. Rationale
  lives in `notes/`, never inline in a `STEP#`/`CT#`.

**Who writes what (ownership):**

| Artifact | Written by | Never by |
|---|---|---|
| `roadmap.md` | planner (chat may prompt) | coder, eval |
| `increment-*.md` plan body (`SLICE#`/`CT#`/`STEP#`) | planner | coder, eval |
| `increment-*.md` status ticks (`STEP#` boxes, `CT#` status) | **harness (code) only** | any model |
| `ledger.md` | eval (EVIDENCE per slice) + harness (FACT entries) | edit-in-place by anyone |
| `notes/` | planner / reviewer | coder |
| repo code + tests | coder | planner, eval |

The increment file is mutated only by the harness for tracking; coder and eval are
read-only against it. Roles run under harness control and touch only what their scoped
task names — a role that edits an un-named file is out of contract.

## 2. Roadmap frontmatter & body

```markdown
---
Roadmap-ID: RM-<name>
slug: <folder-slug>
created: YYYY-MM-DD
status: IN PROGRESS | DONE
active-increment: I01
supersedes: <path, if any>
---
```

Body: **Intent** · **Artifact schema** (pointer to this file) · **Increments** (table:
ID, name, status, one-line intent — later increments are outlines) · **Standing
decisions** (`decided:` / `assumed:` tagged) · **Sources**.

## 3. Increment file

```markdown
---
Increment-ID: RM-<name>-I01
Roadmap-ID: RM-<name>
status: OUTLINED | READY | IN PROGRESS | SHIPPED
slices: <n>
---
```

Then one `## SLICE#:` section per slice.

## 4. Slice section grammar

```markdown
## SLICE<n>: <title>
STEPS: prescriptive | outcome          # the step-detail dial; default prescriptive
DEPS: SLICE<a>, SLICE<b> | —           # slice DAG; — = none
INTENT: <what + why, one to three lines>
CONTRACTS:
  CT<n> [FUNCTIONAL|CONSTRAINT|PRESERVATION]: <acceptance criterion>
  ...
TESTS: <path/to/test_file.py>          # planner-authored; the verify block points at it
```verify
<runnable command, e.g. uv run pytest tests/test_x.py -q>
```
- [ ] STEP<n>: <atomic action> (exit: <observable criterion>)
- [ ] STEP<n>: ...
```

Token rules — the harness parses exactly this; write exactly this:
- Use `SLICE#` and `STEP#`. Never `S#`.
- Every `CT#` carries one class:
  - `FUNCTIONAL` — a new behavior; its test is NEW and must fail before the change and pass
    after.
  - `CONSTRAINT` — a rule the change must not violate: backward compatibility, identical
    error shape, no new dependencies, existing conventions. Write a test that fails when the
    rule is violated.
  - `PRESERVATION` — existing behavior that must stay working; an existing test stays green.
- `TESTS:` names the test file the planner authors; the ```verify block runs it. Every `CT#`
  is covered by a test in its slice's `TESTS:` (pre-check CT8).
- `STEPS: prescriptive` — the planner writes atomic steps; every `STEP#` carries an
  `(exit: …)` (pre-check CT9). `STEPS: outcome` — contract checkpoints only; the coder owns
  the path. A step tagged `(auto)` is executed by the harness directly.
- `DEPS:` lists upstream slices; the pre-check rejects cycles and undefined references.
- `CT#` IDs match `\bCT(\d+[a-z]?)\b` and are unique per increment (letter suffixes
  allowed, hyphens not).
- `STEPS:` appears only as the mode line; steps are `- [ ] STEP<n>:` items. There is no
  separate list header.
- Sub-steps are prose: indented continuations and `- (a)` lists under a `STEP#` are not
  parsed; the harness ticks only `- [ ] STEP<n>:` lines.
- To show the grammar in a document, wrap the example fence in ````text, or it is extracted
  as a real command.

## 5. Ledger grammar (append-only)

```
E<n>  <TYPE>  <statement>  [<provenance>]
```

Worked example:

```
E7  FACT  extract_plan_ids parses ## SLICE2: and yields slices=("SLICE2",)
    [verified: tests/test_plan_ids.py:63 @ 0e08ece]
E8  DECIDED  SLICE#-only grammar; pre-rename S# plans archived  supersedes: E3
```

- **Types:** `FACT` (must carry a verification ref) · `DERIVED` · `LOOKUP` · `GUESS`
  (an `ASK#` candidate — an assumption a contract depends on) · `FAILED` · `GAP` ·
  `PRESERVE` · `DECIDED`.
- **Supersession is a field, never an edit:** a new entry carries `supersedes: E<n>`;
  the old entry stays as a tombstone. (A long-lived roadmap is a memory system; it needs
  tombstones, not deletions.)
- **Ownership:** the eval appends an EVIDENCE entry per slice it judges; the harness
  appends FACT entries carrying a verification ref; the planner reads the ledger at
  increment start. Append-only — no entry is ever edited or deleted.

## 6. Status vocabularies

- **Increment:** `OUTLINED → READY → IN PROGRESS → SHIPPED`.
- **Contract (`CT#`):** `PLANNED → IMPLEMENTED → VERIFIED`. `VERIFIED` means the slice's
  `verify` exited 0 **and** (from I02) the test was proven non-vacuous **and** (from I03)
  the eval's L2 contract verdict passed. For stochastic gates `VERIFIED` means pass^k.
- **Step (`STEP#`):** checkbox `- [ ]` → `- [x]`, ticked by the **harness**, not the model.

## 7. What the extractor must expose (I01 surface)

`PlanIds` is a frozen dataclass. The **existing flat tuple fields are retained unchanged**
(`.slices`, `.gaps`, `.contracts`, `.tests`, `.commands`) — `workflow_controller.py:332,461`
and the migrated `tests/test_plan_ids.py` depend on them. Per-slice data is **added** as a
new field, not substituted:

```python
@dataclass(frozen=True)
class SliceRecord:
    slice_id:   str
    intent:     str
    contracts:  tuple[tuple[str, str, str], ...]   # (ct_id, cls, text)
    test_paths: tuple[str, ...]
    steps_mode: str                                 # "prescriptive" | "outcome"
    commands:   tuple[str, ...]                     # this slice's ```verify commands
    section:    str                                 # raw text block (heading → next heading)

@dataclass(frozen=True)
class PlanIds:
    slices: tuple[str, ...] = ()        # retained (flat IDs)
    gaps:   tuple[str, ...] = ()        # retained
    contracts: tuple[str, ...] = ()     # retained (flat CT# IDs)
    tests:  tuple[str, ...] = ()        # retained
    commands: tuple[str, ...] = ()      # retained (flat = concat of all slices')
    slice_records: tuple[SliceRecord, ...] = ()   # NEW — backs the accessors below
```

Read API (over `slice_records`):

```python
plan = extract_plan_ids(increment_text)
plan.commands_for("SLICE2")  # that slice's verify commands only (per-slice, not flat)
plan.section("SLICE2")  # the slice's text block → the coder's scoped brief
plan.contract_class("CT3")  # "FUNCTIONAL" | "CONSTRAINT" | "PRESERVATION"
plan.tests_for("SLICE2")  # the slice's TESTS: path(s)
# NOTE: SliceRecord.test_paths holds PATHS; the retained
# flat PlanIds.tests holds T# IDs. Same word, different
# meaning — do not conflate them.
plan.steps_mode("SLICE2")  # "prescriptive" | "outcome"
precheck(increment_text)  # -> failures[], warnings[]  (pure code, pre-coder)
```

`parse_ledger(ledger_text)` is specified here but **implemented in I04**, beside its
consumers. All functions pure, total (never raise on malformed input), stdlib-only — the
existing `plan_ids.py` contract, extended.

**Open grammar decision (deferred to I02):** whether each `CT#` names the specific test
that proves it (`CT3 [CONSTRAINT] (test: test_identical_401): …`). I01 enforces only the
slice-level rule (a slice with contracts has a `TESTS:` line); per-contract attribution
becomes worth it when I02's non-vacuity gate can run each named test.
