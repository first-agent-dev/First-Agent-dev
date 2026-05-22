---
compiled: 2026-05-22
applies_to:
  - "knowledge/MAINTENANCE.md §When adding a new file (row format rule)"
  - "knowledge/llms.txt BY-DEMAND-INDEX rows that carry `(~N lines)` metadata"
  - "Any cheap-read overlay surface that mirrors a value that drifts"
status: accepted
---

# AP-002 — Stale row counts in routing index drift silently

> Catalog entry that captures the **routine staleness pattern** found in
> M2 (PR after #48): 27% of `knowledge/llms.txt` rows carried `(~N lines)`
> counts that drifted by > 10 lines from the actual file length, including
> three rows that should have shifted size category entirely. The right
> shape (size buckets at semantic boundaries) is documented here so future
> «cheap-read mirror» surfaces inherit the discipline.

## Symptom

A cheap-read overlay surface (here:
[`knowledge/llms.txt`](../llms.txt) BY-DEMAND-INDEX rows) carries a
**raw mirror** of a value that lives in another file (here: the actual
file's `wc -l`). Each row pays a maintenance debt every time the
underlying file grows or shrinks by more than the rounding tolerance.
The mirror's drift is silent — no test fails, no lint catches it, and
the rule that demands the value is paged out of the agent's working
memory while it is editing the underlying file. M2 measured the drift
across 58 rows on 2026-05-22:

- 16 rows (~ 27 %) had `|actual − claimed| > 10`.
- 3 rows would have shifted bucket under any 4-bucket scheme:
  - `HANDOFF.md`: 270 → 705 (S → M, +160 % growth).
  - `knowledge/adr/DIGEST.md`: 170 → 374 (S → M, +120 %).
  - `knowledge/trace/exploration_log.md`: 220 → 952 (S → L, +330 %).

These are not pathological files — they are the durable mirrors that
the project edits every PR. The mirror drifts in lockstep with feature
velocity.

## Wrong shape

The pre-M2 row format demanded **raw line-count metadata** with no
tolerance band: `(~N lines)` rounded to the nearest ten. Every PR that
touched a mirrored file SHOULD have updated the row, but only the
explicit-archival PRs (`MAINTENANCE.md §When archiving a research note`)
remembered. Live precedent: the AGENTS.md row claimed `~390` while the
file is `533` lines, drifted across 12 PRs since the count was last
edited.

The cost asymmetry is the same shape as
[`AP-001`](./AP-001-spec-bypassing-workaround.md) §Why the wrong shape
dominates: the maintenance cost (re-read the file, count lines, round,
edit the row, re-run gates) is high; the perceived benefit (the next
agent can pre-batch better) is invisible until the agent actually
ranges over many rows; the surface metric (`pytest`, `pre-commit`,
`ruff`) is mute on it; and the rule that demands the value lives in a
file (`MAINTENANCE.md`) the editing agent is rarely re-reading.

## Right shape

Replace **raw mirror** with **bucket overlay + raw count for
additivity**: `(BUCKET, ~N lines)` where `BUCKET ∈ {S, M, L, XL}` and
the boundaries are 300 / 800 / 1500 LOC. The bucket label is the
semantic primary key; the raw count is the additivity escape hatch.

```text
- [README.md](raw-url) (S, ~210 lines): description.
- [AGENTS.md](raw-url) (M, ~530 lines): description.
- [knowledge/research/borrow-roadmap-2026-05.md](raw-url) (XL, ~1840 lines): description.
```

The bucket scheme **defeats routine drift**: a file going from
`~480` to `~510` lines stays `M` and the row needs no edit. Only
crossing a bucket boundary (which is rare for any single PR — see the
M2 measurement: 3 of 58 rows in ~5 months of project drift) triggers
a row update. The maintenance cost drops from «every edit that grows
the file by 10 lines» to «every edit that crosses a 300 / 800 / 1500
boundary».

The raw count is preserved because the project's existing token-budget
math depends on additivity:
[`research/bootstrap-cost-baseline-2026-05.md`](../research/bootstrap-cost-baseline-2026-05.md)
§3 documents the 6-file irreducible bootstrap core; an agent batching
reads still needs to sum line counts to compare against context-window
limits. Pure-bucket labels would have killed that ability.

Boundary rationale:

- **S ≤ 300** — one screenful for a human reader; mid-tier OSS LLMs
  approximate this as «single read, batch freely».
- **M 301 – 800** — fits 2-3 instances inside a 24 K usable-token
  context (DeepSeek 4 typical). Below
  [AGENTS.md PR Checklist rule #3](../../AGENTS.md#pr-checklist)
  «summaries / overviews < 1000 lines» so M is the «routine
  documentation» tier.
- **L 801 – 1500** — read alone on mid-tier; below rule #3's
  «deep-dive research < 2000» so L is the «deep-dive but still
  single-file» tier.
- **XL > 1500** — alarm bucket: read chunked / sectional. On 2026-05-22
  the only XL file is
  [`borrow-roadmap-2026-05.md`](../research/borrow-roadmap-2026-05.md)
  at 1840 LOC.

## Why the wrong shape dominates

Three mutually-reinforcing reasons the raw-mirror format silently
accumulated 27 % drift:

1. **No test, no lint, no CI gate.** A drifted `(~390)` does not break
   the build. The rule that demands the value lives in
   `knowledge/MAINTENANCE.md`, which an editing agent reads only when
   it is *explicitly* archiving a file — never when it is editing
   `AGENTS.md` to add a section. The forcing function fires at the
   wrong moment.
2. **Cost-asymmetry trap (same shape as
   [AP-001](./AP-001-spec-bypassing-workaround.md)).** The
   row-keeping work is paid up-front (re-count, re-edit, re-run gates,
   ~5 minutes per touched row), the benefit is paid downstream by
   *some other* agent at *some unknown* time. Under any rough
   per-PR-velocity heuristic, the row-keeping work is cut.
3. **The format mirrors a value that drifts.** The maintenance
   discipline asks the editing agent to keep two values in sync
   (`wc -l` of the file ↔ `(~N lines)` in `llms.txt`) without any
   mechanical link between them. The bucket scheme does not fix this
   directly — the raw count still drifts inside its bucket — but it
   widens the tolerance band 20× (from ±10 LOC at the rounding edge
   to ±300 LOC at the boundary edge for S, ±500 LOC for M, ±700 LOC
   for L). The boundary is the only event that *must* fire; routine
   drift is absorbed.

## Detection

Three layers, same shape as
[`AP-001` §Detection](./AP-001-spec-bypassing-workaround.md#detection):

- **Layer 1 — Change Classification + INVARIANT discipline.**
  M2's PR explicitly declares `CLASS: RELAX` + `INVARIANT: llms.txt
  rows carry size-bucket metadata sufficient for batch-decision
  routing (bucket label + raw count)`. A future PR that wants to
  *remove* the bucket label (e.g. «it's redundant with the raw
  count») would have to declare `CLASS: RELAX` and amend
  [`MAINTENANCE.md`](../MAINTENANCE.md#when-adding-a-new-file-under-docs-or-knowledge)
  in the same PR — visibility of the invariant change is the
  forcing function.
- **Layer 2 — periodic sweep (deferred, opportunistic).** A small
  `tools/check_llms_txt_sizes.py` that compares each row's `wc -l`
  to its declared bucket and fails CI if any row is in the wrong
  bucket is mechanically possible but **not landed in M2** —
  M2 chose the cheaper *boundary-as-forcing-function* route first
  (re-evaluate if the next sweep finds ≥ 5 % cross-bucket drift). The
  decision is recorded in
  [`exploration_log.md`](../trace/exploration_log.md) Q-12 §Rejected
  branches as «mechanise via CI script — wait for measurable need».
- **Layer 3 — review-time prompt** (passive, documentary). PR
  reviewers spot-check «if you added or removed a file in the same
  PR, does the llms.txt row's bucket label still match?» — the
  bucket boundaries are wide enough that this is almost always a
  no-op, but the prompt exists so the catalog entry has a complete
  three-layer story.

## Linked-ADR / Linked-rule

- [`knowledge/MAINTENANCE.md` §When adding a new file](../MAINTENANCE.md#when-adding-a-new-file-under-docs-or-knowledge)
  — owns the row-format rule that this anti-pattern strengthens.
- [`AGENTS.md` §PR Checklist rule #3](../../AGENTS.md#pr-checklist)
  — declares the 1000 / 2000 thresholds that informed the M / L
  boundary placement.
- [`AGENTS.md` §Change Classification](../../AGENTS.md#change-classification)
  — the Layer-1 forcing function for any future change to the
  invariant.

## Evidence

- Commits on the M2 branch `devin/1779458329-wave3-llms-txt-size-buckets`
  (this PR): sweep of all 58 rows + format amendment +
  [`anti-patterns/AP-002-stale-routing-index-counts.md`](./AP-002-stale-routing-index-counts.md)
  (this file) + Q-12 in
  [`trace/exploration_log.md`](../trace/exploration_log.md).
- Drift measurement script run on commit `2495703` (post-M1 merge):
  16 of 58 rows had `|actual − claimed| > 10`; 3 rows would have
  shifted bucket under the new scheme.
- Cross-link from
  [`AP-001`](./AP-001-spec-bypassing-workaround.md) §Why the wrong
  shape dominates — the cost-asymmetry-trap mechanism is the same
  shape; AP-002 is the routine variant of AP-001 (every-PR drift
  instead of one-shot relocation).
