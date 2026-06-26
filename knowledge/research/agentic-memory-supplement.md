---
title: "Agentic Memory — supplement: Mem0 paper + дельты к batch-1/batch-2 + gstack"
compiled: "2026-04-26"
source:
  - https://arxiv.org/abs/2504.19413
  - https://arxiv.org/html/2504.19413v1
  - https://github.com/garrytan/gstack
  - https://github.com/garrytan/gbrain
  - https://github.com/yogirk/sparks
  - https://github.com/Larens94/codedna
  - "user-dossier: agentic-dossiers v2.md (Arena.ai Agent Mode, four repos: gstack, codedna, gbrain, sparks)"
chain_of_custody:
  - "Mem0 paper — arXiv:2504.19413v1 (Chhikara et al., 28 Apr 2025).
    Прочитан полный HTML; цитируемые цифры взяты из §4.4 Latency
    Analysis и §4.3 Performance Comparison."
  - "v2 dossier (Arena.ai Agent Mode) — secondary source. Цитируемые
    архитектурные паттерны сверены с README/SPEC.md upstream-репо
    выборочно (codedna SPEC, sparks-contracts.md, gbrain INSTALL_FOR_AGENTS),
    но не построчно с кодом — это secondary-проход."
  - "Дельты вычислялись против двух наших нот: batch-1 §3.6 (codedna)
    и batch-2 §3.1 (gbrain), §3.4 (sparks). gstack у нас не покрывался."
status: research
supersedes: none
extends:
  - knowledge/research/llm-wiki-community-batch-1.md  # §3.6 codedna
  - knowledge/research/llm-wiki-community-batch-2.md  # §3.1 gbrain, §3.4 sparks
  - knowledge/research/ai-context-os-memm-deep-dive.md  # forthcoming via PR #12 (в полёте при создании этой ноты)
related:
  - knowledge/research/llm-wiki-critique.md
  - knowledge/research/llm-wiki-critique-first-agent.md
  - knowledge/research/agent-roles.md
claims_requiring_verification:
  - "Mem0 'p95 search 0.200s, p95 total 1.44s vs full-context 17.117s'
    (paper §4.4) — измерено на LOCOMO (10 conversations × ~26 000 tokens),
    железо/embedding-модель в paper'е указаны (GPT-4o-mini, dense
    embeddings, без upreply названия модели). На других корпусах цифры
    могут отличаться."
  - "Mem0 '26% relative improvement в LLM-as-Judge vs OpenAI memory'
    — относительное число; baseline-конфигурация OpenAI ChatGPT memory
    в paper описана через manual extraction в playground (§4.4 last
    paragraph), что не вполне fair-baseline."
  - "v2 dossier цифры о звёздах/процессах в репо — на дату его генерации
    (Arena.ai run); не сверял заново."
  - "gstack нашими инструментами не клонировался в этой сессии — анализ
    идёт по v2 dossier как primary, спот-чек по upstream README."
scope: |
  Дополнение к двум основным research-нотам:
  (a) дельта по codedna — что batch-1 не покрыл из v2 dossier;
  (b) дельта по gbrain и sparks — что batch-2 не покрыл из v2 dossier;
  (c) gstack — новый репо, не было в наших разборах;
  (d) Mem0 paper (arXiv:2504.19413) — production-grade memory
  architecture, прямо релевантна задаче FA, у нас отсутствовала.

  Цель — закрыть пробелы первого прохода и связать community-паттерны
  с research-grade архитектурой Mem0.
superseded_by: "knowledge/adr/ADR-3-memory-architecture-variant.md"
---

# Agentic Memory — supplement

> **Status:** superseded by [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Survey delta to ADR-3 (memory architecture variant); cheat-sheet row in [`adr/DIGEST.md`](../adr/DIGEST.md). Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the ADR instead.

> **Статус:** research note, 2026-04-26.
> **Что внутри:** дельты к существующим нотам и одна крупная новая
> ссылка (Mem0 paper). Батч-1 и батч-2 остаются каноном для первичного
> разбора шести+пяти проектов; этот файл их *не* заменяет — он
> добавляет то, что в первом проходе ушло в фон.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/agentic-memory-supplement.md
# compiled: 2026-04-26; 597 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) — read this instead of the pre-trim body.
- Original `source:`, `chain_of_custody:`, `claims_requiring_verification:`, and `related:` lists are preserved in the frontmatter above (restored to their `cf7db4d` values; PR-M no longer modifies frontmatter).
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
