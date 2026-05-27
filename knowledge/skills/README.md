# Skills Library

Per-task, agent-loadable disciplines. Each skill is a `SKILL.md`
file inside its own subdirectory; the subdirectory name doubles
as the skill's identifier. Skills are loaded **on demand** by the
agent when a matching trigger fires (e.g. «before opening a PR»
loads [`pr-creation/SKILL.md`](./pr-creation/SKILL.md)) — not as
part of session-start context.

## Scope — skill vs. prompt vs. ADR / AGENTS rule

The three loadpoints under `knowledge/` deliberately do different
things; choose the right one when adding a new artefact.

| Loadpoint                        | What lives here                                                                                       | When loaded                                                |
|----------------------------------|-------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| `knowledge/skills/<name>/SKILL.md` | Per-task discipline the agent picks up before doing a specific kind of work.                          | On-demand, triggered by a verb (e.g. «before opening a PR»).|
| `knowledge/prompts/*.md`          | Text intended for the LLM API **system slot** — role definitions, dispatcher prompts, retry-prefix shapes. | Once, at the start of a session or role-switch.            |
| `AGENTS.md` / `knowledge/adr/`    | Repo-wide rules and architectural decisions. Read by every agent every session.                       | Always.                                                    |

If the content is «always read» it belongs in `AGENTS.md` /
`knowledge/adr/`. If it is the **literal system prompt** for an
LLM API call, it belongs in `knowledge/prompts/`. If it is a
per-task workflow the agent loads only when about to perform
that task, it belongs here.

## Convention — directory-per-skill, `SKILL.md` capitalised

- One skill = one subdirectory. Filename inside is always
  `SKILL.md` (uppercase, no exceptions). Matches KAOS /
  Anthropic / Devin `.agents/skills/<name>/SKILL.md` shape so a
  future symlink (or auto-load mechanism per R-24) plugs in
  without renaming.
- Optional sibling files (`references/`, worked examples) live
  inside the same subdirectory. Reserved-name conflicts are
  avoided by keeping the skill's identifier in the
  subdirectory name, not the filename.
- Skills are addressable as `knowledge/skills/<name>/SKILL.md`
  from anywhere in the repo. No symlinks, no aliases — the path
  IS the identifier.

## Template

```markdown
---
name: <verb-or-task-slug>
description: <one-sentence purpose>
status: draft | active
triggers:
  - <natural-language trigger phrase>
  - <another trigger>
last-reviewed: YYYY-MM-DD
---

## Trigger

<one or two sentences naming the situation in which the agent
loads this skill — phrased as the user-facing or session
observation that fires it>

## Reference

<closed-enum tables, lookup matrices, contract shapes — content
that is **read** by the agent (and ultimately by a hook, when
the mechanisation lands). Reference content has no LLM decision
in it; the hook reads it as single source of truth.>

## Decision points

<the **judgement-bound** clauses — what the LLM must decide
when applying the skill. Not numbered orchestration steps
(those are A-bucket residue per ADR-10 I-2); only points where
the LLM exercises judgement that cannot be deterministically
encoded.>

## Output format

<the exact shape the agent must produce — header lines,
template fields, regex-validatable text. This section is the
single source of truth that any validating hook references.>

## What the hook validates

<the mechanical checks the harness performs on the agent's
output — framed as «the hook does this for you», not «you
must do this». Listing them here keeps the skill consistent
with the hook implementation; tests pin the two views.>

## Escalation

<what to do when the skill's gate fires — the failure mode the
skill is forcing-against, and how to handle it.>

## Worked example

<a concrete example or cross-link to the anti-pattern entry the
skill is forcing-against.>
```

## Index

| Skill                                                | Status | Trigger                                                                                       |
|------------------------------------------------------|--------|------------------------------------------------------------------------------------------------|
| [`pr-creation/SKILL.md`](./pr-creation/SKILL.md)     | active | Before opening any PR — load to derive `INTENT:` / `[CLASS:]` / `INVARIANT:` header lines and (for FIX) `DEGREE-OF-FREEDOM CLOSED:` / `DETERMINISTIC MECHANISM:` clauses. |
| [`repo-audit/SKILL.md`](./repo-audit/SKILL.md)       | active | When the user requests a repo-audit-style refactor or critical structural review. 7-phase workflow (P1 inventory → P7 capture-as-workflow). |

## Forward direction

The full filesystem-canon skill store (status workflow, draft →
active gate, shared-overlay layering, safe community import) is
tracked as
[`borrow-roadmap-2026-05.md` §R-24](../research/borrow-roadmap-2026-05.md#r-24--filesystem-canonical-skill-store--safe-community-import).
This directory is the **storage substrate** that R-24's
runtime store will load from when it lands; the conventions
above are forward-compatible (frontmatter keys `name`,
`description`, `status`, `triggers` match R-24's planned
schema; the SKILL.md filename matches the auto-load convention).
