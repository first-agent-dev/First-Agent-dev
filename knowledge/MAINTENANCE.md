# Maintenance — files agents touch when archiving, superseding, or amending

> **Purpose.** Single canonical list of «touch these files when doing X» rules. 
> **Maintenance rule for this file.** When a new artefact joins
> the cross-reference web (e.g. a new index file, a new tier of
> `DIGEST.md`, a new prompt template registered in `RESOLVER.md`),
> append a section here in the same PR.

## § When archiving a research note

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

## § When merging an ADR amendment

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

## § When adding a new file under docs/ or knowledge/

Add a row in knowledge/llms.txt BY-DEMAND INDEX
under the matching folder section. Row format:
[path/to/file.md]: description.

For files >1200 LoC add 'Large' size tag [path/to/file.md] (Large);	 
such files are chunked / sectional read only.
Crossing a boundary triggers a prefix update.

Row prose cap - The description after the closing of the Markdown link MUST be ≤ 200 characters.
Keep llms.txt a routing index, If agent needs more context, follow link.

## § When adding a new prompt template

Add a row to knowledge/prompts/RESOLVER.md
intent table only if the same intent has resolved to the
same template twice — do not pre-populate speculative rows
(per RESOLVER.md §«When to add a row»).
Add a row to knowledge/llms.txt BY-DEMAND-INDEX
under «Prompts (knowledge/prompts/)».
If the prompt has an associated PR Checklist rule (e.g.
research-briefing.md ↔ rule #8), cross-link from both sides
so the rule survives without the prompt and the prompt's
header points at its enforcement clause.

## § When adding a new anti-pattern entry

Cheap-read overlay; authoritative source remains
knowledge/anti-patterns/README.md §How a new entry lands.
The catalog's own README owns the canonical 5-step checklist
(pick AP-NNN, fill schema sections, cross-link from ADR /
DIGEST / exploration_log, update llms.txt, include the line
in the PR description). This section exists only to keep the
maintenance surface complete — an agent reading
MAINTENANCE.md for «I am adding a new artefact that joins
the cross-reference web, which checklist applies?» finds the
pointer here without having to know the README exists.

Open knowledge/anti-patterns/README.md §How a new entry
lands and follow steps 1–5 verbatim.
