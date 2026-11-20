# Q145 research: where an acquisition stage learns which projects exist (2026-11-11)

Operator asked for a research round instead of a choice, with the model that a project
name first appears in dialogue: a chat agent may create an empty `worklogs/<slug>/`, or
call `invoke_workflow` directly and have a full structure appear. With two projects
present, the system must be able to read them and the agent must choose.

## 1. What Q108-B actually decided

Not project discovery. The selected contract (`i03-harness-shell-and-tool-research:591`)
is:

- protocol v2 permits exactly `HEALTH` and `LIST_PROJECT_ARTIFACTS`;
- `LIST_PROJECT_ARTIFACTS` payload is a single already-validated `project_slug`;
- it returns closed kinds for `worklogs/<slug>`, `roadmap.md`, `increments`, plus sorted
  immediate children of `increments/`;
- "There is no recursion", 64-entry cap, 64 KiB reply cap, atomic refusal on excess.

So Q108-B answers "given a project, what canonical artifacts does it contain?" It never
answered "which projects are there?", and it does not claim to. The increment's phrase
"Q108-B pinned LIST" is accurate for what S5P1 wires; the project-selection half was
never in that decision.

## 2. What the operator's two scenarios actually do

Verified against `workspace.py::_install_destination/_install_commit`:

- The install creates **intermediate** components and makes the leaf a no-clobber
  `rename`. A pre-existing empty `worklogs/<slug>/` therefore makes the rename land on
  an existing directory: `EEXIST`/`ENOTEMPTY` → `SupervisorError("COLLISION")`.
- So "create an empty directory with the new slug, then bootstrap" **fails closed**. The
  working bootstrap path is the second one: the directory does not exist and the rename
  creates it atomically.
- This is why hints must distinguish "valid project" from "directory exists but holds no
  canonical roadmap" — the latter is not a selectable project and must not be offered as
  one, or the model will pick a slug that bootstrap then refuses.

## 3. Why the controller cannot build the hints itself

Three routes were checked and all are closed:

| Route | Result |
| --- | --- |
| Read `worklogs/*` from the controller's host tree | Violates the exact-view invariant (`Q108` rejected shortcut C). The controller root is a registered host path, not a capability. |
| Read the `_ReaderPin.entries` manifest directly | It is supervisor-private, cleared on `close()`, and never serialized. Bypassing the authority is the same rejected shortcut. |
| Use `fs_search` for navigation | Legal for a **chat** agent (`i03-...research:579`), and the tool does run cell-local. But in a managed workspace it requires a `project_tool_executor`, which W1 has not wired yet (`fs_search.py:1377-1380` returns `managed cell-local search index is unavailable`). |

There is also no persisted install registry to consult: `_install_finish` records a
revision/pointer, and the set of projects exists only as directory structure.

## 4. Corrected finding: `AMBIGUOUS_PROJECT` is reachable

I claimed `resolve_existing_choice` could never return `AMBIGUOUS_PROJECT` because it
filters the inventory by exact slug. Checked in code and refuted: two inventories for the
same slug produce `NeedsClarificationChoice("AMBIGUOUS_PROJECT")`. The branch is a guard
on the pure resolver's contract (the caller may hand it a duplicated inventory), not dead
code. No defect, no change.

## 5. Terminology that the docs use in two senses

The v2 rule sets name a `selection` **validator** with rules
`choice-malformed|choice-missing|unknown-project|unknown-increment|ambiguous-project|...`.
`ACQUISITION` (introduced in `62e49be`) is a **stage kind**. They are different layers and
must not be conflated: the stage produces a choice, the validator judges the acquisition
record.

## 6. What this means for Q145=A

Option A said "bounded hints from the existing pin, placed in the stage task". The
*source* is right and now confirmed as the only trustworthy one: the pinned revision
manifest. The *transport* does not exist — the manifest is inside the supervisor. Honest
options are therefore narrower than the question implied, and this is the escalation.
