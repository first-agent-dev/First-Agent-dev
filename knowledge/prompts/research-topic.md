---
purpose: Research a topic and write a structured note into knowledge/research/.
inputs:
  - topic: the subject to research (e.g. "ReAct vs plan-and-execute orchestration")
  - slug: short kebab-case filename (e.g. "react-vs-plan-and-execute")
  - seed-links: 2-5 URLs to start from
last-reviewed: 2025-06-01
---

[Objective]
Research <topic> and produce a structured note in `knowledge/research/<slug>.md`.

[Context]
- Seed reading: <seed-links>
- Related code in this repo: (none yet / `src/...`)
- Related ADRs: (none yet / `knowledge/adr/...`)

[Approach]
1. Skim the 3-5 most relevant primary sources (papers, docs, reputable blog posts).
2. Produce the note with these sections, in order:
   - **TL;DR** (<=3 sentences)
   - **Key concepts** (bullet list, one line each)
   - **Trade-offs vs. our current approach**
   - **How it would fit into First-Agent** (sketch, no code)
   - **Open questions**
   - **Sources** (bulleted URL list)
3. Open a **draft** PR titled `research: <topic>`.

[Constraints]
- Cite every non-obvious claim with a URL at the end of the relevant line.
- **Pin the version and the date.** For arXiv, cite `{id}v{N}, retrieved {date}` — never a bare
  id. Numbers move between versions, and an unpinned citation silently becomes wrong.
- **Mark where the claim came from**: abstract, body, or table.
- **Quote the exact sentence** for any claim a decision will rest on. Paraphrase is where
  invented figures come from.
- Put a **90-day re-check date** on anything benchmark-derived.
- Markdown only. Keep the note under ~250 lines.
- No code changes in this PR.
- Do not mark the PR ready-for-review; a human will.

[Acceptance]
- File `knowledge/research/<slug>.md` exists with all required sections.
- All links return 2xx (spot-check any that look suspicious).
- PR is in draft state.

[Out of scope]
- Implementation changes.
- Modifying other research notes.
