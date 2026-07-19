# Worklogs — Session Work Artifacts

> Purpose: Condense all artifacts related to working in sessions and their outputs.
> This directory is the working surface; knowledge/ is the reference surface.

## Structure

```text
worklogs/
├── README.md              # this file
├── HANDOFF.md             # cross-session bootstrap + active work tracker (read first every session)
├── BACKLOG.md             # active milestones and tracked items
├── pr-notes/              # PR notes (moved from knowledge/pr-notes/)
├── implementation-plans/  # active and recent implementation plans
└── archive/               # finished work, unsorted (prune freely)
```

## How to use

1. **Every session starts here:** Read HANDOFF.md → BACKLOG.md → active plans (HANDOFF.md §Next points to them).
2. **Every session ends here:** Update HANDOFF.md; load doc-maintenance skill.
3. **Archive rule:** If a plan/note is >30 days old and no active work references it, move to archive/.
4. **Prune rule:** Archive items >90 days old with no cross-references can be deleted.
5. **Cross-references:** When moving files, update all refs per doc-maintenance skill.

## What goes where

| If it is… | Put it in… |
|---|---|
| Cross-session state (gotchas, landmarks, next priorities, active plan pointers) | HANDOFF.md |
| A tracked milestone or backlog item | BACKLOG.md |
| A PR note | pr-notes/ |
| An active implementation plan | implementation-plans/ |
| A finished plan, review, or session closure note | archive/ |
| A research finding or architecture decision | knowledge/research/ or knowledge/adr/ (NOT here) |
| A term definition or feature description | knowledge/reference.md (NOT here) |
