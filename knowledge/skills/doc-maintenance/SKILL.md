---
purpose: Session closure and doc hygiene discipline
trigger: At session close, or when moving/pruning/adding any file under knowledge/ or worklogs/
last-reviewed: 2026-07-18
---

# Doc Maintenance Skill

## Trigger

Load this skill at session close, or before any file move/prune/archive operation under `knowledge/` or `worklogs/`.

## §When closing a session

1. Update `worklogs/HANDOFF.md` per its §Session Protocol (overwrite §Current state, rewrite §Next).
2. If any new file was added under `knowledge/` or `worklogs/`, add a row to `knowledge/llms.txt` §BY-DEMAND INDEX (deprecated but still maintained for backwards compatibility).
3. If any new term was introduced, add to `knowledge/reference.md` §Terms.
4. If any ADR was amended, update `knowledge/adr/DIGEST.md` and append to `knowledge/trace/exploration_log.md`.
5. Run `grep -rn '<old-path>' .` for any files moved/renamed/deleted — fix every reference.
6. Verify: `python scripts/check_doc_links.py` passes.

## §When archiving a research note

1. Add `> **Status:** archived 2026-MM-DD` banner at top.
2. Add `superseded_by:` frontmatter if applicable.
3. Update `knowledge/llms.txt` — re-path or remove the row.
4. Cross-check `worklogs/HANDOFF.md` §Current state.
5. Cross-check `knowledge/adr/DIGEST.md`.
6. Cross-check `knowledge/reference.md` §Terms.

## §When moving or pruning a doc

**The one hard rule: no dangling links.** In the same PR:

1. `grep -rn '<old-filename>' .` to find every reference.
2. For a move/rename: re-path every reference. Adjust link depth.
3. For a deletion: remove refs or retarget to superseding artifact. Drop llms.txt row.
4. Update `knowledge/llms.txt`, `worklogs/HANDOFF.md` (active links only), `knowledge/reference.md`, and file indexes.
5. Verify: `python scripts/check_doc_links.py` passes and `grep -rn '<old-path>'` returns nothing unexpected.

## §When adding a new file under knowledge/ or worklogs/

1. Add a row in `knowledge/llms.txt` §BY-DEMAND INDEX under matching folder section.
2. Row format: `[path/to/file.md]: description.` Description ≤200 chars.
3. For files >1200 LoC add size tag: `[path/to/file.md] (Large)`.
4. If the file introduces a new term, add to `knowledge/reference.md` §Terms.
5. If the file has an ADR cross-reference, update DIGEST.md.

## §When merging an ADR amendment

1. Update `knowledge/adr/DIGEST.md` — extend the Amendments bullet.
2. Append to `knowledge/trace/exploration_log.md` per pr-creation skill rule #9.
3. Cross-check `worklogs/HANDOFF.md` §Current state ADR list.
