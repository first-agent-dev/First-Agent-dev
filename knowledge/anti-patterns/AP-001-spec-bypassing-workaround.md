---
compiled: 2026-05-22
applies_to:
  - "ADR-7 §Sub-amendment 2026-05-21b (R-8 LearningObserver filesystem-canon artifacts)"
  - "Any future module whose invariant references a canonical filesystem path"
status: accepted
---

# AP-001 — Spec-bypassing workaround masquerading as fix

> Catalog entry that captures the wave-3 R-8 incident verbatim so future
> sessions can recognise the shape without re-paying the lesson.

## Symptom

A module M has an **invariant** of the form «M writes its durable
state to canonical path P». An LLM-driven session observes a surface
metric «P shows up as untracked / dirty in `git status` after running
M» and proposes a one-line fix that relocates M's writes from P to
some `P'` (typically `.fa/<P>` or a tmp directory). The fix
**passes** every quick check — quality gates green, `git status`
clean — but silently **decouples** «whatever exercises M proves M
works» from «M's intended cross-session functionality», because the
production path that other modules read from is still P, not P'.

## Wrong shape

**Live evidence.** Commit
[`5c1db0f`](https://github.com/GITcrassuskey-shop/First-Agent/commit/5c1db0f)
on branch `devin/1779363347-wave3-r8-learning-observer` (PR #47).
The smoke CLI's R-8 `LearningObserver` was changed from:

```python
LearningObserver(
    codebase_map_path=workspace / "knowledge" / "trace" / "codebase_map.json",
    gotchas_path=workspace / "knowledge" / "trace" / "gotchas.md",
)
```

to:

```python
LearningObserver(
    codebase_map_path=workspace / ".fa" / "knowledge" / "trace" / "codebase_map.json",
    gotchas_path=workspace / ".fa" / "knowledge" / "trace" / "gotchas.md",
)
```

The diff is one line × two paths. It compiles, all quality gates
pass, `git status --short` is clean after a smoke run. Looks fine.

**What actually broke.** The R-8 invariant per ADR-7 §Sub-amendment
2026-05-21b is «`LearningObserver` writes the canon at
`<workspace>/knowledge/trace/` — durable cross-session memory under
UC1 + UC3». The smoke CLI is the only checked-in exerciser of R-8
until T-2 lands. Relocating the smoke writes under `.fa/` means
smoke no longer exercises the path the T-2 real runtime is supposed
to use. The artifact «smoke is green» now proves nothing about R-8.

## Right shape

**Live evidence.** Commit
[`dada707`](https://github.com/GITcrassuskey-shop/First-Agent/commit/dada707)
on the same branch — the M0a follow-up. The path is reverted; the
**reliability** that the workaround was trying to buy is delivered
at the canonical path via three orthogonal forcing functions:

1. **Deterministic-clock injection.** `record_discovery` and
   `record_gotcha` accept an optional `now: str | None` parameter.
   `LearningObserver` carries a matching field. The smoke CLI pins
   `now="2026-05-21T00:00:00Z"` (the ADR-7 §Sub-amendment date —
   stable, human-readable). The T-2 real runtime omits `now` →
   `current_utc_iso()` default → live wall-clock provenance.
   Fixed timestamp ⇒ smoke output is byte-identical across runs.
2. **`record_gotcha` byte-suffix dedup.** Skip the append when the
   file already ends with this exact section. Fixed clock ⇒
   identical bytes ⇒ dedup. Live clock ⇒ section bytes differ ⇒
   append-only contract preserved (real T-2 still gets the
   append-only audit trail it needs).
3. **Seed baseline + snapshot regression.** The post-smoke
   `knowledge/trace/codebase_map.json` is checked into the repo as a
   seed baseline. A regression test
   (`tests/test_cli.py::test_inner_loop_smoke_canon_snapshot_matches_seed_baseline`)
   byte-compares the smoke output against the baseline; any drift
   fails CI and forces the baseline update to land in the same PR
   as whatever caused the drift.

`fa inner-loop-smoke --workspace . --input README.md` leaves
`git status --short` empty across repeated runs *because the
artifact is byte-stable*, not because it was relocated.

## Why the wrong shape dominates

A **cost-asymmetry trap**. There are three modes for fixing any
module M misbehaving as B:

1. **REPAIR** — restore M's invariant. Hard. Requires understanding
   intent, designing reliability across the boundary, multi-file
   diff.
2. **RELAX** — change M's invariant. Requires explicit
   architectural decision (ADR amendment, exploration log block).
3. **WORKAROUND** — bypass M to avoid B. Cheap. Surface metric
   passes. Invariant silently broken.

An LLM with no forcing function defaults to **WORKAROUND** every
time, because:

- WORKAROUND looks like REPAIR locally (small diff, tests pass).
- The consequence (invariant broken) is invisible unless the agent
  re-reads the ADR.
- Heuristics that any reasonable session uses — minimal-diff,
  ship-velocity, surface-metric-passes — all reward WORKAROUND.

Adding rule #N+1 to [`AGENTS.md`](../../AGENTS.md) («don't bypass
module invariants») fixes nothing — it competes with rules 1..N for
attention and loses under load. **Action-count drift dominates
rule-count drift in weaker LLMs**; the structural fix must reduce
the number of actions the LLM has to take to surface the
contradiction, not add to it.

## Detection

Three layers, ranked by leverage-per-token. Implemented incrementally
— Layers 1 + 2 land with this catalog entry; Layer 3 is documentary.

1. **Change-Classification prefix (Layer 1).** Mandatory one-line
   declaration in every PR body and module-touching commit message:

   ```text
   CLASS: REPAIR | RELAX | WORKAROUND
   INVARIANT: <one sentence — what the module promises>
   ```

   Cognitive load: «label your fix» (one action). The act of
   writing «CLASS: WORKAROUND, INVARIANT: R-8 writes to
   `knowledge/trace/`» makes the contradiction visible to the agent
   mid-write, and to the reviewer in two seconds. Codified in
   [`pr-creation` skill §Reference](../skills/pr-creation/SKILL.md#reference).

2. **Named ADR-bound invariant tests (Layer 2).** For each ADR
   amendment's invariant, one test whose **name** encodes the
   assertion. Example:

   ```python
   def test_invariant_adr7_r8_canon_root_is_knowledge_trace(...) -> None:
       """ADR-7 §Sub-amendment 2026-05-21b INVARIANT: R-8 canon
       writes go to <workspace>/knowledge/trace/, nowhere else."""
   ```

   If the agent relocates the canon, this test fails. To make it
   pass, the agent must change the test → which means changing the
   ADR → which means a visible architectural decision (RELAX), not
   a silent WORKAROUND. Mechanical spec→test link makes silent
   direction-changes impossible. Retrofitted **opportunistically**
   (when an ADR amendment touches an invariant), not as a campaign.

3. **Review-time prompt (Layer 3).** Single question in the PR
   review carrier (Devin Review prompt, PR template,
   self-review checklist):

   > «Does this PR change *what the module does*
   > (path / contract / schema / output) or *how reliably it does
   > it* (timing / dedup / retry / errors)? If the former, link the
   > ADR amendment.»

   Catches whatever Layers 1 + 2 missed. One sentence, no
   implementation cost.

## Linked-ADR

- [ADR-7 §Sub-amendment 2026-05-21b — R-8 LearningObserver
  filesystem-canon artifacts](../adr/ADR-7-inner-loop-tool-registry.md#sub-amendment-2026-05-21b--r-8-learningobserver-filesystem-canon-artifacts).
  The worked-history note in that section (added in M0a, expanded
  in M1) cross-links here.

## Evidence

- **Wrong shape (the workaround):** commit
  [`5c1db0f`](https://github.com/GITcrassuskey-shop/First-Agent/commit/5c1db0f)
  «fix(wave-3): R-8 follow-up — smoke `.fa/` canon + path-keyed key
  + 2 test gaps» on PR #47. Path relocation visible in `src/fa/cli.py`
  `_cmd_inner_loop_smoke` constructor of `LearningObserver`.
- **Right shape (the M0a repair):** commit
  [`dada707`](https://github.com/GITcrassuskey-shop/First-Agent/commit/dada707)
  «fix(wave-3): R-8 reliability at canonical `knowledge/trace/` (M0a)»
  on the same PR. Adds the three forcing functions described in
  §Right shape.
- **Decision trail (chosen vs rejected branches):**
  [`exploration_log.md` Q-7](../trace/exploration_log.md#q-7--what-is-the-v01-inner-loop--tool-registry-contract-2026-05-12)
  §Rejected blocks «Smoke canon root under `.fa/knowledge/trace/`
  (the path-relocation workaround)» and «Wall-clock
  `LearningObserver.now` for the smoke CLI».
- **External anchor (independent rediscovery):**
  [R-32 in `borrow-roadmap-2026-05.md` §2.8 + §3](../research/borrow-roadmap-2026-05.md#28-group-h--agentsmd--adr-citations-cluster-r-26r-32-7-items)
  cites soviet-code B-NEW-4 «anti-pattern catalog as living
  document» — the practice this catalog implements.
