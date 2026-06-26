---
title: "Сообщество LLM-Wiki — батч 1: что из этого реально работает в продакшне"
compiled: "2026-04-26"
source:
  - https://github.com/JuliusBrussee/cavemem
  - https://github.com/Larens94/codedna
  - https://github.com/kytmanov/obsidian-llm-wiki-local
  - https://github.com/cablate/llm-atomic-wiki
  - https://github.com/alexdcd/AI-Context-OS
  - https://github.com/agent-creativity/agentic-local-brain
  - "user-dossier: 0.+A+workflow+for+github+repo+analysisprompt.md"
  - "user-dossier: 1.+agentic-patterns-dossier+...+agentic-local-brain.md"
  - "user-dossier: 2.+cavemem_dossier.md"
  - "user-dossier: 3.+codedna_dossier.md"
chain_of_custody:
  - "Досье 1–3 написаны пользователем (MondayInRussian) по его собственному
    workflow-промпту (досье 0). Я их прочёл целиком и сверил с самими
    репозиториями, которые выкачал отдельно 2026-04-23/24."
  - "Все цифры о звёздах/коммитах — на дату фетча; могут устареть."
  - "Спорные числа (см. §6) проверял отдельно: README-первоисточник."
status: research
claims_requiring_verification:
  - "cavemem ~75% token reduction — claim автора, не измеренный бенчмарк;
     коэффициент зависит от домена входов."
  - "CodeDNA +17pp F1 SWE-bench — n=10 patches, DeepSeek 10/0/0;
     signal, не proof."
  - "CodeDNA p=0.040 на n=5 — статистически слабый, рядом с шумом."
  - "obsidian-llm-wiki '79K-line cli.py' в досье 1 — вероятно
     ~7.9K строк или 79KB; фактический размер не проверял."
  - "agentic-local-brain '98.2% protocol adoption' — это метрика
     CodeDNA, в досье склеилась с другим проектом."
  - "Звёзды/контрибьюторы всех шести репо — на дату фетча
     2026-04-23/24; дрифтят во времени."
scope: |
  Часть 2A исследования сообщества вокруг LLM Wiki-паттерна. Шесть проектов:
  cavemem, codedna, obsidian-llm-wiki-local, llm-atomic-wiki, AI-Context-OS,
  agentic-local-brain. Цель — отделить «то, что работает на проде» от
  «модно, но недоказано» в применении к нашему агенту (First-Agent).
  Часть 2B (gbrain, llm-wiki-kit, obsidian-wiki, sparks, mnemovault
  + safishamsi/graphify + сравнение с GraphRAG) — отдельным PR после
  одобрения этого.
related:
  - knowledge/research/llm-wiki-critique.md
  - knowledge/research/llm-wiki-critique-first-agent.md
  - knowledge/research/agent-roles.md
superseded_by: "knowledge/adr/ADR-3-memory-architecture-variant.md"
---

# Сообщество LLM-Wiki — батч 1

> **Status:** superseded by [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Survey input to ADR-3 (memory architecture variant); cheat-sheet row in [`adr/DIGEST.md`](../adr/DIGEST.md). Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the ADR instead.

> **Статус:** research note, 2026-04-26.
> **Что внутри:** разбор шести проектов сообщества, выросших вокруг идеи
> Карпатого о «LLM-вики». Цель — *production-ориентированный* отбор: что
> уже есть в чужой проверенной кодовой базе и что мы можем переиспользовать
> в First-Agent, а что — энтузиазм и YAGNI.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/llm-wiki-community-batch-1.md
# compiled: 2026-04-26; 433 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) — read this instead of the pre-trim body.
- Original `source:`, `chain_of_custody:`, `claims_requiring_verification:`, and `related:` lists are preserved in the frontmatter above (restored to their `cf7db4d` values; PR-M no longer modifies frontmatter).
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
