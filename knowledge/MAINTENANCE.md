# Maintenance — files agents touch when archiving, superseding, or amending

> **Purpose.** Single canonical list of «touch these files when
> doing X» rules. Without this, the next sweep silently misses the
> cross-references that the prior archive PR landed (PR #2 archive
> of 10 research notes + 2 docs was the original prompt for this
> file — five inbound `devin-reference.md` links had to be hand-
> retargeted, and that cascade is exactly what should live here
> instead of in commit messages).
>
> **Maintenance rule for this file.** When a new artefact joins
> the cross-reference web (e.g. a new index file, a new tier of
> `DIGEST.md`, a new prompt template registered in `RESOLVER.md`),
> append a section here in the same PR.

## When archiving a research note

1. Add the `> **Status:** archived 2026-MM-DD` banner at top
   (in-place stub per PR #2, Option B — no separate `/archive/`
   directory).
2. Add `superseded_by:` frontmatter field if applicable.
3. Update [`knowledge/llms.txt`](./llms.txt) BY-DEMAND-INDEX —
   move the row to the «Archived» footer (never delete the row;
   preserve discoverability for an agent looking for the note by
   filename or topic keyword).
4. Cross-check [`HANDOFF.md`](../HANDOFF.md) §Current state — if
   the note was cited there as input to a current decision,
   replace the citation with the superseding artefact.
5. Cross-check [`knowledge/adr/DIGEST.md`](./adr/DIGEST.md) — if
   any DIGEST row's **Inputs** bullet pointed at this note, retarget
   to the superseder.
6. Cross-check [`docs/glossary.md`](../docs/glossary.md) — if any
   glossary row's `See:` link pointed at this note, retarget or
   remove.

## When merging an ADR amendment

1. Update [`knowledge/adr/DIGEST.md`](./adr/DIGEST.md) — extend
   the matching **Amendments** bullet of the ADR's row (per
   [AGENTS.md PR Checklist rule #9](../AGENTS.md#pr-checklist)
   second sentence).
2. Append (or amend) the block in
   [`knowledge/trace/exploration_log.md`](./trace/exploration_log.md)
   per rule #9 first sentence. For an amendment, attach a
   `## Q-N.amend-YYYY-MM-DD` sub-section (or follow-up paragraph
   under the existing `## Q-N`) with `Coupling:` referencing the
   original `Q-N` plus any prior amendments — the existing six
   blocks (`Q-1` through `Q-6`) plus the two `Q-1.amend-…`
   entries are the in-repo precedent.
3. Cross-check [`HANDOFF.md`](../HANDOFF.md) §Current state ADR
   list — bump the amendment date if the amended ADR is listed
   there.

## When superseding a non-research file

Apply the same shape as «archiving a research note» (banner +
`superseded_by:`) but with the supersession marker spelled out
per [AGENTS.md PR Checklist rule #5](../AGENTS.md#pr-checklist):

```text
> **Status:** superseded by <link> (YYYY-MM-DD).
```

For YAML / TOML files that have no native blockquote, use a
top-of-file `#` comment block instead — the live precedent is
[`knowledge/trace/exploration_tree.yaml`](./trace/exploration_tree.yaml)
which carries this exact marker after PR-F merged.

## When adding a new file under `docs/` or `knowledge/`

Triggered by [AGENTS.md PR Checklist rule #7](../AGENTS.md#pr-checklist).
Applies forward-only (rule #7 rev landed 2026-05-12 — older
rows in `llms.txt` not retro-fitted, agents reading this section
should not back-fill existing rows).

1. Add a row in [`knowledge/llms.txt`](./llms.txt) BY-DEMAND INDEX
   under the matching folder section. Row format:

   ```text
   - [path/to/file.md](raw-url) (S, ~N lines): description.
   ```

   **Size bucket** — one of `S`, `M`, `L`, `XL` — prepended before
   the `~N lines` count. Boundaries (LOC, rounded to nearest ten):

   | Bucket | Range       | Batch guidance (mid-tier OSS LLM) |
   |--------|-------------|-----------------------------------|
   | **S**  | ≤ 300       | batch freely                      |
   | **M**  | 301 – 800   | batch 2–3 at most                 |
   | **L**  | 801 – 1500  | read alone                        |
   | **XL** | > 1500      | chunked / sectional read only     |

   `~N lines` — file length rounded to the nearest ten, preserved
   for additivity (agents can still sum raw counts for token
   budgeting). The bucket label enables a fast visual scan: an
   agent seeing `(S, …)` knows it can batch without arithmetic;
   `(XL, …)` is a stop-and-chunk signal. Drift tolerance: a file
   going from ~480 to ~510 lines stays `M` and the row needs no
   edit; only crossing a boundary triggers a row update.

   Relevant for mid-tier OSS models with smaller context windows;
   see
   [`research/bootstrap-cost-baseline-2026-05.md`](./research/bootstrap-cost-baseline-2026-05.md)
   §3 for the 6-file irreducible bootstrap core that this metadata
   enables agents to size in advance.
2. If the new file is a cheat-sheet or index that supersedes
   prose in another file (e.g. `adr/DIGEST.md` vs the per-ADR
   files, or `MAINTENANCE.md` vs the prose in
   [AGENTS.md PR Checklist](../AGENTS.md#pr-checklist) rules
   #5 / #7), write the description as «… cheap-read overlay;
   authoritative source remains \<link\>» so an agent knows
   when to skip vs when to drill down. Live precedent:
   `adr/DIGEST.md` row in `llms.txt`.
3. If the new file supersedes an existing file in the same PR,
   also run the «When superseding a non-research file» checklist
   above (banner + frontmatter + cross-references).

## When adding a new prompt template

1. Add a row to [`knowledge/prompts/RESOLVER.md`](./prompts/RESOLVER.md)
   intent table **only if the same intent has resolved to the
   same template twice** — do not pre-populate speculative rows
   (per `RESOLVER.md` §«When to add a row»).

## When adding a new anti-pattern entry

Cheap-read overlay; authoritative source remains
[`knowledge/anti-patterns/README.md` §How a new entry lands](./anti-patterns/README.md#how-a-new-entry-lands).
The catalog's own README owns the canonical 5-step checklist
(pick `AP-NNN`, fill schema sections, cross-link from ADR /
DIGEST / exploration_log, update `llms.txt`, include the line
in the PR description). This section exists only to keep the
maintenance surface complete — an agent reading
`MAINTENANCE.md` for «I am adding a new artefact that joins
the cross-reference web, which checklist applies?» finds the
pointer here without having to know the README exists.

1. Open [`knowledge/anti-patterns/README.md` §How a new entry
   lands](./anti-patterns/README.md#how-a-new-entry-lands) and
   follow steps 1–5 verbatim.
2. The llms.txt step (§How a new entry lands #4) is the same
   shape as the §When adding a new file under `docs/` or
   `knowledge/` checklist above — `(BUCKET, ~N lines)` with the
   size-bucket label (S / M / L / XL per the table above), row
   added under the §Anti-pattern catalog subsection.
3. Cross-link from the new entry's §Linked-ADR section back to
   the relevant ADR's worked-history note in the same PR (per
   [AGENTS.md PR Checklist rule #9](../AGENTS.md#pr-checklist)
   second sentence).
2. Add a row to [`knowledge/llms.txt`](./llms.txt) BY-DEMAND-INDEX
   under «Prompts (`knowledge/prompts/`)».
3. If the prompt has an associated PR Checklist rule (e.g.
   `research-briefing.md` ↔ rule #8), cross-link from both sides
   so the rule survives without the prompt and the prompt's
   header points at its enforcement clause.

## Cadence — recurring sweep

Every 30 days **or** every 5 merged research-note PRs (whichever
comes first), an agent runs a maintenance sweep:

1. `git log --since="30 days" -- knowledge/research/` to surface
   recently-added notes.
2. For each note older than 90 days that has not been cited in
   a PR description in the same window, evaluate archival per
   [`knowledge/project-overview.md` §1.2](./project-overview.md#12-enforceable-principle--minimalism-first)
   (minimalism-first question 3: «what capability is lost if it
   is removed?»).
3. For every archive decision, run the «When archiving a research
   note» checklist above.

Archive sweep is a documentation-only PR — research notes are
non-harness artefacts, so [AGENTS.md PR Checklist rule #10](../AGENTS.md#pr-checklist)
(4-question minimalism-first evidence for harness components) and
rule #11 (≤100 k token context budget) are both **exempt**.

## See also

- [`AGENTS.md` PR Checklist](../AGENTS.md#pr-checklist) — rules
  #5 (supersession), #7 (`llms.txt` reflects reality), #9 (ADR
  amendments cascade to `exploration_log.md` + `DIGEST.md`).
- [`knowledge/BACKLOG.md`](./BACKLOG.md) — deferred-ideas
  tracking; companion artefact to this file.
- [`HANDOFF.md`](../HANDOFF.md) §«When to update this file» —
  the only cross-reference rule that lives outside this file
  (because `HANDOFF.md` self-bootstraps before a session can
  read `MAINTENANCE.md`).
