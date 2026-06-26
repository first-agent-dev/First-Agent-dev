---
title: "Cross-reference review — ampcode + SLIDERS notes vs ADR-1..5 (2026-04-29)"
compiled: "2026-05-01"
# Originally compiled 2026-04-29; date bumped to 2026-05-01 when §11
# Q-1 / Q-2 supersession blockquotes were added (citing 2026-05-01
# events). Per AGENTS.md rule #4 `compiled:` ≥ all dates cited in text.
# Original compile date preserved in title and in commit history.
source:
  - knowledge/research/how-to-build-an-agent-ampcode-2026-04.md
  - knowledge/research/sliders-structured-reasoning-2026-04.md
  - knowledge/adr/ADR-1-v01-use-case-scope.md
  - knowledge/adr/ADR-2-llm-tiering.md
  - knowledge/adr/ADR-3-memory-architecture-variant.md
  - knowledge/adr/ADR-4-storage-backend.md
  - knowledge/adr/ADR-5-chunker-tool.md
  - knowledge/project-overview.md
  - docs/architecture.md
  - docs/workflow.md
  - knowledge/research/agent-roles.md
  - knowledge/research/memory-architecture-design-2026-04-26.md
  - knowledge/research/chunker-design.md
  - knowledge/research/agentic-memory-supplement.md
  - knowledge/research/llm-wiki-critique-first-agent.md
chain_of_custody: >
  Этот файл — синтез поверх двух недавно вмердженых research-нот
  (ampcode, SLIDERS) и пяти принятых ADR. Все factual-цифры по
  ampcode и SLIDERS уже верифицированы в parent-нотах
  (chain_of_custody там); здесь — кросс-проверка против ADR и
  consequent-проектные предложения, не пересказ источников.
  Любые цитаты из ampcode-статьи и SLIDERS-paper вынесены в
  английские блоки и помечены секцией parent-ноты.
status: research
tier: draft
supersedes: none
extends: []
related:
  - knowledge/adr/ADR-1-v01-use-case-scope.md
  - knowledge/adr/ADR-2-llm-tiering.md
  - knowledge/adr/ADR-3-memory-architecture-variant.md
  - knowledge/adr/ADR-4-storage-backend.md
  - knowledge/adr/ADR-5-chunker-tool.md
  - knowledge/research/how-to-build-an-agent-ampcode-2026-04.md
  - knowledge/research/sliders-structured-reasoning-2026-04.md
  - knowledge/research/agent-roles.md
  - knowledge/research/memory-architecture-design-2026-04-26.md
  - knowledge/research/chunker-design.md
links:
  - "../adr/ADR-1-v01-use-case-scope.md"
  - "../adr/ADR-2-llm-tiering.md"
  - "../adr/ADR-3-memory-architecture-variant.md"
  - "../adr/ADR-4-storage-backend.md"
  - "../adr/ADR-5-chunker-tool.md"
  - "./how-to-build-an-agent-ampcode-2026-04.md"
  - "./sliders-structured-reasoning-2026-04.md"
  - "./agent-roles.md"
  - "./memory-architecture-design-2026-04-26.md"
  - "./chunker-design.md"
mentions:
  - "ampcode"
  - "Thorsten Ball"
  - "SLIDERS"
  - "Stanford OV AL"
  - "Anthropic"
  - "Claude"
  - "Mem0"
  - "Variant A"
  - "Variant D"
confidence: opinion
claims_requiring_verification:
  - "Утверждение, что mid-tier OSS Coder (Nemotron 3 Super / Qwen 3.6 27B
    из ADR-2) хуже Claude 3.7 справляется с string-replace edit-форматом —
    эмпирически не проверено. Это риск, не факт. До implementation PR
    нужен фикстурный прогон 5–10 правок на каждой целевой модели."
  - "Оценка «cheap to add provenance fields сейчас» опирается на
    предположение, что v0.1 chunker ещё не написан и схема `chunks`
    ещё не залита миграцией. На момент 2026-04-29 это так
    (Phase S завершён, модулей в `src/fa/` нет). Если на момент
    чтения этой ноты chunker уже существует — оценка стоимости
    другая."
  - "Предложение про `tool_protocol: native | prompt` в models.yaml
    основано на предположении, что часть OSS-моделей в ADR-2
    (Nemotron 3 Super, Qwen 3.6 27B) к моменту implementation
    либо умеет, либо не умеет native tool-calling — это надо
    проверять на каждом конкретном слаге через provider, не
    утверждать заранее."
  - "Все архитектурные рекомендации §10 — input для будущих ADR,
    не сами ADR. Решения принимает пользователь."
superseded_by: "knowledge/research/efficient-llm-agent-harness-2026-05.md"
---

# Cross-reference review — ampcode + SLIDERS vs ADR-1..5

> **Status:** superseded by [`research/efficient-llm-agent-harness-2026-05.md`](./efficient-llm-agent-harness-2026-05.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Recommendations were absorbed into ADR-2 amendments (2026-04-29 `tool_protocol`, 2026-05-01 MCP shape) and the active inner-loop research note §10. Cheat-sheet rows in [`adr/DIGEST.md`](../adr/DIGEST.md). Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the ADR amendments or the active harness note instead.

> **Статус:** research note, 2026-04-29.
> **Что внутри:** систематический проход по двум недавно вмердженым
> research-нотам (ampcode, SLIDERS) и пяти принятым ADR (ADR-1 ..
> ADR-5), с явным выпиской того, **где исследования усиливают
> текущую архитектуру**, **где обнажают пробелы** и **где
> намечают тонкие натяжки**, которые лучше закрыть до старта
> implementation-фазы (memory + chunker + agent loop).
>
> **Эта нота не предлагает менять ADR.** Она готовит структурированный
> input — пронумерованные рекомендации (§10) и открытые вопросы
> (§11), на которые принимает решение проектный лид. Сами правки в
> ADR (если они нужны) — отдельный PR после согласования.
>
> **Adressovano:** будущему Architect/Coder-агенту FA, реквестеру
> и человеку-ревьюеру PR. Форма — нумерованные блоки, явные таблицы
> mappinga, явные TL;DR на каждом разделе.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md
# compiled: 2026-05-01; 1347 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`research/efficient-llm-agent-harness-2026-05.md`](./efficient-llm-agent-harness-2026-05.md) — read this instead of the pre-trim body.
- Original `source:`, `chain_of_custody:`, `claims_requiring_verification:`, and `related:` lists are preserved in the frontmatter above (restored to their `cf7db4d` values; PR-M no longer modifies frontmatter).
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
