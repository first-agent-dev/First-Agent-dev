---
title: "Research — Критика Karpathy's LLM Wiki — разбор по источникам"
source:
  - "https://foundanand.medium.com/the-hidden-flaw-in-karpathys-llm-wiki-e3a86a94b459"
  - "https://dev.to/jgravelle/a-radical-diet-for-karpathys-token-eating-llm-wiki-59ng"
  - "https://ranjankumar.in/llm-wiki-synthesis-time-decision-rag-agentic-memory"
  - "https://github.com/ChavesLiu/second-brain-skill/blob/main/README.en.md"
  - "https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2"
  - "https://www.dougengelbart.org/content/view/110/460/"
compiled: "2026-04-24"
chain_of_custody: >
  Все цитаты, формулировки тезисов и цифры — через ссылки `source:`.
  Этот файл — критический пересказ, не первоисточник.
claims_requiring_verification:
  - "jDocMunch benchmark numbers (19.9× / 95%)"
  - "Claim that Karpathy wiki runs at ~100 articles / 400K words"
  - "rohitg00's list of eight extensions matches the current gist revision"
superseded_by: "knowledge/research/llm-wiki-critique.md"
---

# Research — Разбор источников критики LLM Wiki

> **Status:** superseded by [`research/llm-wiki-critique.md`](./llm-wiki-critique.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Companion source-list to the parent critique note. Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the active critique note instead.

> **Статус:** research note, 2026-04-24.
> **Parent:** [`llm-wiki-critique.md`](./llm-wiki-critique.md) — содержит
> TL;DR, факты о gist'е, кросс-резку и фактчек.
> **Companion:** [`llm-wiki-critique-first-agent.md`](./llm-wiki-critique-first-agent.md)
> — применимость к First-Agent и списки «берём / не берём».
>
> Этот файл — детальный разбор по каждому из шести источников с одинаковой
> структурой: **Тезис → Иллюстрация → Что сильно → Что слабо → Что берём**.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/llm-wiki-critique-sources.md
# compiled: 2026-04-24; 302 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`research/llm-wiki-critique.md`](./llm-wiki-critique.md) — read this instead of the pre-trim body.
- Original `source:`, `chain_of_custody:`, and `claims_requiring_verification:` lists are preserved in the frontmatter above (restored to their `cf7db4d` values; PR-M no longer modifies frontmatter).
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
