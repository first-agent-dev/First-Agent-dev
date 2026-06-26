---
title: "AI-Context-OS (MEMM) — глубокий разбор бэкенда: что брать в First-Agent"
compiled: "2026-04-26"
source:
  - https://github.com/alexdcd/AI-Context-OS
  - "branch: codex/inbox-review-ui-phase2 (HEAD: 0fa0688)"
  - https://memm.dev/docs/architecture-and-operating-model/
  - https://memm.dev/docs/paper/
  - https://memm.dev/docs/whitepaper/
  - "user-dossier: AI-Context-OS+MEMM.txt"
  - "user-dossier: 0.+A+workflow+for+github+repo+analysisprompt.md"
chain_of_custody:
  - "Репозиторий клонирован 2026-04-26, ветка codex/inbox-review-ui-phase2
    отстаёт от main на 23 коммита (в основном UI-полировка InboxView).
    Бэкенд этой ветки полностью совпадает с main по содержимому ядра."
  - "Все цитируемые сниппеты — прямые выдержки из репо (line numbers
    указаны рядом). Цифры/паттерны проверены против
    src-tauri/src/core/*.rs, не по саммари."
  - "Цитаты из memm.dev/docs читаются как авторская позиция (Alex DC),
    не как peer-reviewed источник."
status: research
supersedes: none
extends:
  - knowledge/research/llm-wiki-community-batch-1.md  # §3.3 краткий обзор
related:
  - knowledge/research/llm-wiki-critique.md
  - knowledge/research/llm-wiki-critique-first-agent.md
  - knowledge/research/agent-roles.md
claims_requiring_verification:
  - "memm.dev/docs/whitepaper заявляет «sub-10ms на запрос» для Rust
    scoring engine — нет публичного бенчмарка с указанием размера
    корпуса/железа; считать как design target, не измерение."
  - "Заявление о ~`/`-стороне «filesystem-first» не отменяет того, что
    `engine.rs:execute_context_query` каждый раз делает полный
    `scan_memories(root)` + `read_memory(...)` для всех найденных файлов
    (engine.rs:96–107). На больших корпусах это станет узким местом —
    в коде нет в-памяти кэша или инкрементального индекса."
  - "Декларируется 4 типа онтологии (source/entity/concept/synthesis)
    как стабильный контракт; в `MemoryOntology` есть `Unknown` вариант
    с `#[serde(other)]` (types.rs:11–17). Это значит схема ещё дрифтит
    де-факто, что важно для совместимости."
scope: |
  Глубокий разбор бэкенда AI-Context-OS (MEMM) применительно к
  First-Agent. Не дублирует §3.3 в `llm-wiki-community-batch-1.md`,
  а раскрывает ровно то, о чём попросил пользователь: backend code
  snippets и архитектурные паттерны, пригодные для имплементации в
  нашем агенте позже. Без оценок «production-ready / нет» (это
  сделано в batch-1); фокус — что именно копировать на уровне
  кода/контракта и что — нет.
superseded_by: "knowledge/adr/ADR-3-memory-architecture-variant.md"
---

# AI-Context-OS (MEMM) — глубокий разбор бэкенда

> **Status:** superseded by [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Survey input to ADR-3 (memory architecture variant); cheat-sheet row in [`adr/DIGEST.md`](../adr/DIGEST.md). Mem0/Memm-style deltas live in [`research/agentic-memory-supplement.md`](./agentic-memory-supplement.md). Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the ADR instead.

> **Статус:** research note, 2026-04-26.
> **Что внутри:** дополняет §3.3 в
> [`llm-wiki-community-batch-1.md`](./llm-wiki-community-batch-1.md).
> Раскрывает: (1) карту бэкенда MEMM по модулям, (2) ключевые
> data-контракты, (3) точные code-snippets, готовые к адаптации в
> First-Agent, (4) WIP-добавления в ветке `codex/inbox-review-ui-phase2`
> (Inbox enrichment + Ingest Proposals), (5) что НЕ берём.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/ai-context-os-memm-deep-dive.md
# compiled: 2026-04-26; 801 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`adr/ADR-3-memory-architecture-variant.md`](../adr/ADR-3-memory-architecture-variant.md) — read this instead of the pre-trim body.
- Original `source:`, `chain_of_custody:`, `claims_requiring_verification:`, and `related:` lists are preserved in the frontmatter above (restored to their `cf7db4d` values; PR-M no longer modifies frontmatter).
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
