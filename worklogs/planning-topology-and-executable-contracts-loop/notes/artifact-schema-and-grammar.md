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
  allowed, hyphens not). Uniqueness is enforced by pre-check CT34, not left to care.
- `STEPS:` appears only as the mode line; steps are `- [ ] STEP<n>:` items. There is no
  separate list header.
- Sub-steps are prose: indented continuations and `- (a)` lists under a `STEP#` are not
  parsed; the harness ticks only `- [ ] STEP<n>:` lines.
- To show the grammar in a document, wrap the example fence in ````text, or it is extracted
  as a real command.

**Section boundaries (normative — the parser implements these, it does not invent them):**
- A slice section runs from its `## SLICE<n>:` heading to the line before the next heading
  whose depth is **less than or equal to the depth of that slice's own heading** — not to the
  next `SLICE` heading. The last slice of an increment therefore does not absorb what follows
  it. The depth is read from the heading that matched: the slice pattern admits `##` through
  `####` (`plan_ids.py:58`), so a hardcoded `^#{1,2}` terminator is wrong for a `###` slice.
- Increment-level `##` sections (definition of done, out of scope, hand-off) **may** follow the
  last slice and are not part of any slice.
- A contract is **declared** only inside the `CONTRACTS:` block. The block runs from the
  `CONTRACTS:` line to the first later **non-blank line that begins at column 0**, or to the end
  of the section. Indentation is the only terminator. Do not enumerate the field names that may
  follow (`TESTS:`, `STEPS:`, a fence, a `- [ ]` item): an allowlist silently swallows the next
  column-0 field someone adds — `SHIPPED:` already exists — whereas the indentation rule is
  total.
- One entry declares **one** contract. An entry begins at an indented line matching
  `CT<n>[a-z]? [[CLASS]]:` and continues through every subsequent line indented more deeply.
  Its id and `[CLASS]` are read from the **entry's first line only**, but its **text is the
  whole entry**, continuation lines joined with single spaces — splitting on the first `]:` and
  keeping one line discards the rationale that `CONSTRAINT` entries are required to carry. A
  `CT#` written anywhere else is a *reference*, never a declaration.
- Every `CONSTRAINT`-class contract carries a rationale naming the wrong implementation
  it catches, on the entry's continuation lines. It is the only rationale permitted inside a plan body (§1), because it is an
  acceptance criterion in prose form, not history.

**The `## Grounding` block (prose, never parsed).** A planner-authored increment may end with a
`## Grounding` section carrying the conventions, scope-outs, assumptions and risks that have no
home in the slice grammar. The harness never reads it; it exists for the human reviewer and for
the planner's own next pass. Its **first line is mandatory** and states what the planner
understood the request to be and what it deliberately excluded — the readback that lets a
reviewer catch a misunderstood requirement in five lines instead of two hundred.

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
- **Reflection output is typed, never raw prose.** A retrospective or self-critique enters the
  ledger as a typed entry; raw reflection text is never replayed into a later prompt. Untyped
  prose fed back into context is how a loop conditions itself on its own past failures.
- **Projection target.** A ledger entry maps onto a `BlackboardEntry`
  (`src/fa/blackboard/blackboard.py`): its anchor becomes `version_dependencies`, its
  preconditions become `assumptions`, and `detect_conflict` then reports a FACT whose
  assumptions no longer hold. Staleness is therefore a property of the existing substrate, not
  a field to invent. Implemented in I04 beside the parser.

## 6. Status vocabularies

- **Increment:** `OUTLINED → READY → IN PROGRESS → SHIPPED`.
- **Contract (`CT#`):** `PLANNED → IMPLEMENTED → VERIFIED`. `VERIFIED` means the slice's
  `verify` exited 0 **and** (from I02) the test was proven non-vacuous **and** (from I03)
  the eval's L2 contract verdict passed. For stochastic gates `VERIFIED` means pass^k.
- **Step (`STEP#`):** checkbox `- [ ]` → `- [x]`, ticked by the **harness**, not the model.
  **Interim rule until the I03 harness exists:** the **operator** ticks shipped steps and sets
  `shipped:` in the increment frontmatter. The model still never ticks them. This exception
  expires when I03 ships.
- **pass^k resettability.** A pass^k streak counts only runs over an unchanged gate input. Any
  change to the diff, the test file, the verify command or the model family **resets k to
  zero**. Without this, passes accumulate across different code states and `VERIFIED` means
  nothing.

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
    commands:   tuple[str, ...]                     # this slice's ```verify commands,
                                                    #   document order, deduped WITHIN the slice
    tests_note: str                                 # the trailing `(NEW — …)` annotation on the
                                                    #   TESTS: line, preserved verbatim; I01
                                                    #   assigns it no meaning (consumer: I02)
    section:    str                                 # raw text: this heading through the line
                                                    #   before the next heading whose depth is
                                                    #   ≤ this heading's own depth

@dataclass(frozen=True)
class PlanIds:
    slices: tuple[str, ...] = ()        # retained (flat IDs)
    gaps:   tuple[str, ...] = ()        # retained
    contracts: tuple[str, ...] = ()     # retained (flat CT# IDs)
    tests:  tuple[str, ...] = ()        # retained
    commands: tuple[str, ...] = ()      # retained: EVERY verify command in the document,
                                        #   document order, deduped GLOBALLY. A superset of —
                                        #   not equal to — the concatenation of the slices'
                                        #   commands, which dedupe per slice. Measured on
                                        #   increment-01 at 2f6b8c1: flat 10, concat 12.
    plan_commands: tuple[str, ...] = ()  # NEW — verify blocks before the first slice heading;
                                        #   returned by commands_for(None) so they belong to
                                        #   someone instead of only to the flat field
    slice_records: tuple[SliceRecord, ...] = ()   # NEW — backs the accessors below
```

Read API (over `slice_records`). **Every name carries a `consumer:` — the increment and call
site that will read it. A name with no named consumer is not added** (precedent: the flat
`.commands` field shipped with zero readers and still has none, ledger E2/E3/E5):

```python
plan = extract_plan_ids(increment_text)
plan.commands_for("SLICE2")  # consumer: I02 verify gate — that slice's verify commands only
plan.commands_for(None)  # consumer: I02 — the pre-slice prologue bucket (PlanIds.plan_commands)
plan.section("SLICE2")  # consumer: I03 coder brief — the slice's text block, scoped
plan.contract_class("CT3")  # consumer: I02 — CONSTRAINT-first ordering of verify and findings
plan.tests_for("SLICE2")  # consumer: I02 — baseline selection; TESTS:-not-in-diff assertion
# SliceRecord.tests_note  # consumer: I02 — the preserved `(NEW — …)` text its fail-before
#                         #   filter keys on. I01 preserves the string and defines no
#                         #   semantics for it; I02 decides what NEW licenses.
# NOTE: SliceRecord.test_paths holds PATHS; the retained
# flat PlanIds.tests holds T# IDs. Same word, different
# meaning — do not conflate them.
plan.steps_mode("SLICE2")  # consumer: I03 — PENDING, not built in I01 (no reader until then)
precheck(increment_text)  # consumer: I01 SLICE3 + the I03 admission step; pure code, pre-coder
```

`precheck` returns **every** violation in one pass, each naming `file:line` and a rule id; it
never stops at the first failure. `parse_ledger(ledger_text)` is specified here but
**implemented in I04**, beside its consumers. All functions pure, total (never raise on malformed input), stdlib-only — the
existing `plan_ids.py` contract, extended.

**Identifier uniqueness is enforced, not merely stated.** Every `CT#` is declared exactly once
per increment. A duplicate declaration is a pre-check FAILURE naming both `file:line`s (I01
SLICE3/CT34). `contract_class` stays total and deterministic regardless — first declaration in
document order wins — so a malformed plan degrades into a reported violation, never into an
answer that depends on parse order.

**Open grammar decision (deferred to I02):** whether each `CT#` names the specific test
that proves it (`CT3 [CONSTRAINT] (test: test_identical_401): …`). I01 enforces only the
slice-level rule (a slice with contracts has a `TESTS:` line); per-contract attribution
becomes worth it when I02's non-vacuity gate can run each named test.
