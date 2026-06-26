---
title: "Сообщество LLM-Wiki — батч 2: gbrain, sparks, obsidian-wiki, llm-wiki-kit, mnemovault, graphify + сравнение с research-backed GraphRAG"
compiled: "2026-04-23"
source:
  - https://github.com/garrytan/gbrain
  - https://github.com/MauricioPerera/llm-wiki-kit
  - https://github.com/Oshayr/LLM-Wiki
  - https://github.com/ar9av/obsidian-wiki
  - https://github.com/yogirk/sparks
  - https://github.com/kimsiwon-osifa7878/mnemovault
  - https://github.com/safishamsi/graphify
  - https://gist.github.com/agent-creativity/a4e090f888a516b313ddd1302e51c286
  - https://github.com/microsoft/graphrag
  - https://github.com/HKUDS/LightRAG
  - https://github.com/OSU-NLP-Group/HippoRAG
  - https://github.com/gusye1234/nano-graphrag
  - "user-dossier: 4.gbrain_dossier.md"
  - "user-dossier: 5.llm-wiki-kit_dossier.md"
  - "user-dossier: 6.obsidian-wiki_dossier.md"
  - "user-dossier: 7.sparks_dossier.md"
chain_of_custody:
  - "Досье 4–7 написаны пользователем (MondayInRussian); прочёл целиком,
    сверил с первоисточниками (репозитории, README, релизы) на 2026-04-23."
  - "Досье 5 у автора было неполным (репозиторий не открывался); я перепроверил
    первоисточник — MauricioPerera/llm-wiki-kit доступен и описан ниже из README."
  - "GraphRAG-имплементации описаны по их README + paper-абстрактам; глубокое
    чтение кода НЕ проводил — указываю это явно в §4 и §9."
  - "Все цифры о звёздах/коммитах — на дату фетча 2026-04-23."
status: research
claims_requiring_verification:
  - "gbrain ‘17 888 страниц / 4 383 человека / 723 компании / 21 cron’ — цифры из
     own-blog Garry Tan, не воспроизводимый бенчмарк."
  - "graphify ‘71.5x fewer tokens per query vs reading raw files’ — claim из
     README, методология бенчмарка не описана; принимаем как порядок-величины."
  - "Microsoft GraphRAG ‘global queries’ требуют LLM-вызова на каждое сообщество
     при индексации; стоимость на корпусе >50K токенов нелинейна."
  - "LightRAG ‘до 99% дешевле GraphRAG’ — claim из abstract paper; зависит от
     модели и корпуса."
  - "HippoRAG ‘single-step multi-hop’ — на бенчмарке MuSiQue/2WikiMultiHop;
     генерализуется не на любой домен."
  - "nano-graphrag ‘~800 LoC’ — на момент v0.0.x; репо растёт."
  - "agent-creativity gist — long-form блог об agentic-local-brain
     (уже в batch-1), не отдельный проект; в синтезе используется как
     supplement, не как primary source."
  - "Звёзды/контрибьюторы всех репо дрейфуют во времени; на момент фетча см. §3, §4."
scope: |
  Часть 2B исследования сообщества вокруг LLM-Wiki-паттерна и его сравнение
  с research-backed GraphRAG-реализациями. Пять community-проектов
  (gbrain, llm-wiki-kit, obsidian-wiki, sparks, mnemovault), плюс
  agent-creativity gist (как первоисточник нарратива agentic-local-brain),
  плюс safishamsi/graphify как граф-ориентированный community-проект.
  Потом сравнение с Microsoft GraphRAG, LightRAG, HippoRAG, nano-graphrag.
  Цель — выбрать минимальный набор паттернов, который мы реально применим
  в First-Agent, и понять, в какой момент имеет смысл переходить от
  filesystem-канона к графовой памяти.
related:
  - knowledge/research/llm-wiki-community-batch-1.md
  - knowledge/research/llm-wiki-critique.md
  - knowledge/research/llm-wiki-critique-first-agent.md
  - knowledge/research/agent-roles.md
superseded_by: "knowledge/adr/ADR-3-memory-architecture-variant.md"
---

# Сообщество LLM-Wiki — батч 2 + GraphRAG

> **Status:** superseded by [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Survey input to ADR-3 (memory architecture variant); cheat-sheet row in [`adr/DIGEST.md`](../adr/DIGEST.md). Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the ADR instead.

> **Статус:** research note, 2026-04-23.
> **Что внутри:** разбор пяти community-проектов (gbrain, llm-wiki-kit,
> obsidian-wiki, sparks, mnemovault), плюс safishamsi/graphify как
> graph-ориентированного представителя сообщества, плюс gist
> agent-creativity, плюс сравнение всего этого с research-backed
> GraphRAG (Microsoft GraphRAG, LightRAG, HippoRAG, nano-graphrag).
> Цель — отделить, что на самом деле даёт ROI в нашей задаче, от моды.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/llm-wiki-community-batch-2.md
# compiled: 2026-04-23; 535 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) — read this instead of the pre-trim body.
- Original `source:`, `chain_of_custody:`, `claims_requiring_verification:`, and `related:` lists are preserved in the frontmatter above (restored to their `cf7db4d` values; PR-M no longer modifies frontmatter).
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
