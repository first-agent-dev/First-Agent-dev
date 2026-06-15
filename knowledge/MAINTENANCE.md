# Maintenance — files agents touch when archiving, superseding, or amending

> **Purpose.** Single canonical list of «touch these files when doing X» rules. 
> **Maintenance rule for this file.** When a new artefact joins
> the cross-reference web (e.g. a new index file, a new tier of
> `DIGEST.md`, a new prompt template registered in `RESOLVER.md`),
> append a section here in the same PR.

## §When archiving a research note

1. Add the `> **Status:** archived 2026-MM-DD` banner at top
   (in-place stub per PR #2, Option B — no separate `/archive/`
   directory).
2. Add `superseded_by:` frontmatter field if applicable.
3. Update [`knowledge/llms.txt`](./llms.txt) BY-DEMAND-INDEX —
   re-path or remove the row. If the note was archived in place, move
   the row to the «Archived» footer; if the note was **deleted**, drop
   the row — never leave a row pointing at a missing file. (Pruning is
   allowed — see §When moving or pruning a doc.)
4. Cross-check [`HANDOFF.md`](../HANDOFF.md) §Current state — if
   the note was cited there as input to a current decision,
   replace the citation with the superseding artefact.
5. Cross-check [`knowledge/adr/DIGEST.md`](./adr/DIGEST.md) — if
   any DIGEST row's **Inputs** bullet pointed at this note, retarget
   to the superseder.
6. Cross-check [`knowledge/glossary.md`](./glossary.md) — if any
   glossary row's `See:` link pointed at this note, retarget or
   remove.

## §When moving or pruning a doc

Renaming, relocating, or deleting a file is allowed — pruning keeps the
repo navigable. The one hard rule is **no dangling links** (see
[`README.md` §Conventions](./README.md)). In the **same PR**:

1. `grep -rn '<old-filename>' .` (or the old relative path) to find
   every reference — markdown links, prose code-spans, code comments,
   test assertions, and `llms.txt` rows.
2. For a **move/rename**: re-path every reference to the new location.
   Remember that links *inside* the moved file also change depth — a
   file going one directory deeper turns `](../X)` into `](../../X)`.
3. For a **deletion**: remove the references (or retarget them to the
   superseding artefact). Drop the `llms.txt` row entirely.
4. Update [`knowledge/llms.txt`](./llms.txt) (BY-DEMAND INDEX rows and,
   if the doc is an entry point, a §TASK ROUTING row),
   [`HANDOFF.md`](../HANDOFF.md) only where a line is an *active* link
   (dated history prose stays as written), and the file indexes in
   [`README.md`](../README.md) §Основные файлы / [`AGENTS.md`](../AGENTS.md)
   §Repository Structure if a top-level entry changed.
5. Keep a `> **Status:** moved to <link>` stub at the old path **only**
   when an external entry point may still target it (e.g. a URL shared
   outside the repo). Otherwise no stub is needed.
6. Verify: the repo's internal-link checker must pass — run
   `python scripts/check_doc_links.py` (whole repo) or let the
   `check-doc-links` pre-commit hook run on the changed files — and a final
   `grep -rn '<old-path>'` returns nothing unexpected.

<<<<<<< HEAD
## §When merging an ADR amendment

1. Update [`knowledge/adr/DIGEST.md`](./adr/DIGEST.md) — extend
   the matching **Amendments** bullet of the ADR's row (per
   [`pr-creation` skill PR Checklist rule #9](skills/pr-creation/SKILL.md#pr-checklist)
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

## §When adding a new file under docs/ or knowledge/

Add a row in knowledge/llms.txt BY-DEMAND INDEX
under the matching folder section. Row format:
[path/to/file.md]: description.

For files >1200 LoC add 'Large' size tag [path/to/file.md] (Large);	 
such files are chunked / sectional read only.
Crossing a boundary triggers a prefix update.

Row prose cap - The description after the closing of the Markdown link MUST be ≤ 200 characters.
Keep llms.txt a routing index, If agent needs more context, follow link.

## §When adding a new prompt template

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

## §When adding a new anti-pattern entry

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
