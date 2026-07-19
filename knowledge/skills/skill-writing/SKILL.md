---
name: skill-writing
description: |
  Canonical skill-writing rulebook for harness mutation.
  Load when proposing edits to skills, prompts, or harness components that
  carry a change contract. Contains CHANGE_CONTRACT_TEMPLATE per telemetry.py
  (Pillar 4 iteration via measurement, Paper §5.2.3 Self-Evolving without Regression).
status: active
last-reviewed: 2026-07-12
triggers:
  - "writing a new skill"
  - "modifying an existing skill"
  - "proposing a harness mutation"
  - "changing a component that needs change contract"
---

# Skill — Skill Writing + Change Contract for Harness Mutation

> **Purpose:** Governed mutation of harness (Paper §3.5.3 Governed Harness Mutation,
> §5.2.3 Self-Evolving without Regression). Every skill edit or harness component
> change must carry a change contract that is falsifiable via eval-harness.

## When to Load

- You are writing a new skill under `knowledge/skills/<name>/SKILL.md`
- You are modifying an existing skill (globs, alwaysApply, triggers)
- You are changing `src/fa/` components that alter retrieval, context packing,
  retry limits, permission boundaries, network access, credential handling
- You need to document which failure mode is targeted, invariants preserved,
  and rollback plan

## Skill Frontmatter Contract

Each skill file must have YAML frontmatter with:

```yaml
---
name: <skill-name>  # kebab-case, matches dir name
description: |
  What skill does, when to load. 1-3 sentences.
status: active | draft | archived
last-reviewed: YYYY-MM-DD
triggers:
  - "natural language trigger 1"
  - "trigger 2"
globs:  # optional, for alwaysApply false (ADR-15)
  - "src/**/*.py"
  - "knowledge/**/*.md"
alwaysApply: false  # default false, true only for MUST READ FIRST
---
```

### Globs (ADR-15)

- `globs` field: list of glob patterns where skill auto-applies
- `alwaysApply: false` means loader checks `globs` matches current files
  OR verb matches trigger
- Example: `globs: ["src/fa/inner_loop/tools/*.py", "knowledge/adr/*.md"]`
- Like Cursor Rules: `alwaysApply: false` + `globs` = conditional activation

### Invariants

- Each skill is single file `SKILL.md` under `knowledge/skills/<name>/`
- Name matches directory
- Description ≤ 200 chars per doc-maintenance skill row prose cap
- Triggers are natural language, not regex, for LLM readability
- No bare code fences: always ```python, ```bash, etc per AGENTS.md

## Change Contract Template for Harness Mutation

> Source: `src/fa/telemetry/telemetry.py` CHANGE_CONTRACT_TEMPLATE
> From Paper §5.2.3 Self-Evolving Harnesses without Regression

Copy this template into PR description when mutating harness:

```markdown
# Change Contract for Harness Mutation

## Which component modified
- e.g., src/fa/inner_loop/tools/run_bash.py, src/fa/memory/fts_index.py, knowledge/skills/skill-writing/SKILL.md

## Which failure mode it targets
- e.g., missing dependencies, weak tests, hallucinated APIs, flaky sandboxes, over-permissive tool calls, premature termination, token cost, 124 steps thrashing, context accumulation

## What improvement it predicts
- e.g., median tokens / completed task ↓20%, tool-calls ↓30%, cache hit ratio ↑15%, steps 124→30-40

## Which invariants it must preserve
- e.g., ADR-10 I-1 single-source-of-truth classifier, ADR-11 Level-0 TCB stdlib-only, ADR-12 secret isolation, ADR-7 §10 paired rows, ADR-14 stateful PTY persistence, ADR-15 write/write conflict detection

## Which evaluation can falsify it
- e.g., mini eval-harness 5 tasks (read repo, fix bug, add test, refactor, code-review) before/after, median tokens, tool-calls, USD cost, test pass rate
- e.g., fa run --role planner --task "Read repository and tell what you found" measure steps before/after target 30-40 vs 124 baseline

## How it can be rolled back
- e.g., git revert commit abc, restore previous prompt template, restore previous tool schema, rm -rf .fa/blackboard .fa/telemetry .fa/fts.db

## HITL required?
- e.g., Yes if alters permission boundaries, network access, credential handling, deployment behavior, human-review requirements (per §3.5.3 Governed Harness Mutation)
- No if only retrieval policy, context packing, retry limits, observability tools

## Evidence
- telemetry.jsonl run_ids: [...]
- blackboard entries: [...]
- artifact_ids: [...]
- eval-harness metrics: tokens/tool-calls before/after

## Compliance Checks
- [ ] AGENTS.md ATX headings, short lines ~150 chars, fenced code blocks with language tag
- [ ] No shell=True without # nosemgrep + ADR-6
- [ ] No Level-0 TCB external import per ADR-11
- [ ] FeatureFlags graceful degradation WARNING not crash
- [ ] Blackboard conflict detection write/write overlap
- [ ] Telemetry sanitization precise (SECRET_NAME_RE), not broad "key" in "keyboard"
- [ ] Tests 20+ pass, ruff check, mypy strict
```

## Skill Authoring Workflow

1. **Read MUST READ FIRST 5** per AGENTS.md pre-flight
2. **Grep glossary** for canonical definitions
3. **Check existing skills** via `blackboard.query(type="skill")` or `fs.instant_grep`
4. **Draft frontmatter** with name, description, triggers, globs, alwaysApply
5. **Write body** with Trigger, Reference, Workflow, Invariants sections
6. **Add change contract** if modifying harness component
7. **Verify**: `python -m ruff check`, `mypy --strict`, `pytest`, `markdown-link-check`
8. **Update llms.txt**? No, deprecated — use blackboard query, not manual BY-DEMAND INDEX
9. **Update DIGEST.md** if ADR and exploration_log.md per rule #9

## Prior Art

- Paper 2 §3.5.1 Deep Telemetry as Optimization Substrate
- Paper 2 §3.5.3 Governed Mutation: change contract + HITL for permission boundaries
- Paper 2 §5.2.3 Self-Evolving without Regression: evaluation that can falsify
- Cursor Rules: globs + alwaysApply false
- Claude Code: skill frontmatter with description and triggers
- ADR-16 Pair over Autonomy: checkpoint/undo/diff deterministic, not LLM

## References

- `src/fa/telemetry/telemetry.py` CHANGE_CONTRACT_TEMPLATE (source of truth)
- `knowledge/adr/ADR-14-*` and `ADR-15-*` for blackboard, telemetry, FTS
- `knowledge/skills/doc-maintenance/SKILL.md` for llms.txt deprecation and link integrity
