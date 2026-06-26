# Prompts Library

Reusable prompts for recurring First-Agent tasks. Keep prompts short, versioned, and
reviewable — think of each file as a small contract with Agent.

## Rules

- **One prompt per file.** Filename: `<verb>-<slug>.md` (e.g. `research-topic.md`, `scaffold-module.md`).
- **Front-matter** at the top with purpose and inputs (see template).
- **Idempotent.** Running the same prompt twice should produce equivalent output, not
  compound on itself.
- **Link, don't paste.** Reference files/URLs; don't embed long excerpts.
- **No secrets.** Ever.

## Template

```markdown
---
purpose: <one-sentence description>
inputs:
  - <variable name>: <what to fill in>
last-reviewed: YYYY-MM-DD
---

[Objective]
...

[Context]
...

[Approach]
...

[Constraints]
...

[Acceptance]
...

[Out of scope]
...
```

## Index

| File | Purpose |
|---|---|
| [`RESOLVER.md`](./RESOLVER.md) | Intent-to-template dispatcher (T1-T5 plus role prompts). |
| [`research-topic.md`](./research-topic.md) | Research `<topic>` and produce a structured note. |
| [`research-briefing.md`](./research-briefing.md) | Goal-driven research briefing — paper / repo cross-reference with §0 Decision Briefing. |
| [`architect-fa.md`](./architect-fa.md) | Architect/Planner system prompt (full). |
| [`architect-fa-compact.md`](./architect-fa-compact.md) | Architect/Planner system prompt (compact). |

## Note on system prompts vs. task prompts

The template above (`[Objective] / [Context] / [Approach] / ...`) is for
**task prompts** sent to Agent to perform a single piece of work. Files
in this directory whose `purpose` describes a **role's system prompt**
(e.g. `architect-fa.md`) follow a different shape: short frontmatter +
short meta block + the literal system prompt inside a fenced `text`
block. They are intended to be loaded verbatim into the system slot of
an LLM API call, not consumed by Agent as a task.
