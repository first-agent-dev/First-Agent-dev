---
title: "Architect/Planner — рефакторинг системного промпта (v2.1, RU)"
compiled: "2026-04-26"
source:
  - knowledge/prompts/architect-fa.md
  - knowledge/prompts/architect-fa-compact.md
  - предыдущие версии Architect prompt (v1.0 и GPT-5.5 refactor) — приложены к
    исходному запросу, в репозиторий не коммитились
chain_of_custody: "Сам системный промпт лежит в knowledge/prompts/architect-fa.md
  и knowledge/prompts/architect-fa-compact.md. Цитаты конкретных правил/полей —
  оттуда. Ссылки на исследования (TDP, GraSP, VeriPlan, Reflexion и т.д.) — из
  attached improvements-research документа, перепроверять по arxiv-URL при
  использовании конкретных чисел."
claims_requiring_verification:
  - "TDP снижает потребление токенов до 82% — цифра из abstract attached
    research; перед цитированием перепроверить по arxiv 2601.07577."
  - "WHO Surgical Safety Checklist снизил смертность на 47% — Haynes et al.,
    NEJM 2009; перепроверить."
  - "Reflexion / Self-Verifying Reflection: формальная гарантия улучшения при
    ограниченных ошибках верификации — теоретический результат, перепроверить
    по оригинальной статье."
superseded_by: "knowledge/prompts/architect-fa-compact.md"
---

# Architect/Planner — рефакторинг системного промпта (v2.1)

> **Status:** superseded by [`knowledge/prompts/architect-fa-compact.md`](../prompts/architect-fa-compact.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Design diary for the Architect/Planner system prompt; the final prompts shipped in `architect-fa-compact.md` (default) and [`architect-fa.md`](../prompts/architect-fa.md) (full). Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the prompt files instead.

> **Статус:** active research note. Описывает рефакторинг системного промпта
> для роли Architect/Planner в multi-agent стэке Agent-FA. Конечный артефакт
> рефакторинга — два файла промптов в [`knowledge/prompts/`](../prompts/):
> [`architect-fa.md`](../prompts/architect-fa.md) (full) и
> [`architect-fa-compact.md`](../prompts/architect-fa-compact.md) (compact).
>
> Эта заметка — рассуждение и обоснование: что было плохо в исходных версиях
> промпта, какие принципы дизайна выбраны, почему v2.1 должен работать лучше,
> что осталось нерешённым.
>
> Связанные заметки:
> - [`agent-roles.md`](./agent-roles.md) — структурный ландшафт ролей агентов;
>   v2.1 ложится на роль «Architect / Planner» из его §5.
> - [`agentic-memory-supplement.md`](./agentic-memory-supplement.md) и
>   [`ai-context-os-memm-deep-dive.md`](./ai-context-os-memm-deep-dive.md) —
>   контекст-инжиниринг и память. v2.1 наследует принципы bounded reading и
>   evidence floor оттуда.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/architect-fa-refactor-ru.md
# compiled: 2026-04-26; 451 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`knowledge/prompts/architect-fa-compact.md`](../prompts/architect-fa-compact.md) — read this instead of the pre-trim body.
- Original `source:`, `chain_of_custody:`, and `claims_requiring_verification:` lists are preserved in the frontmatter above (restored to their `cf7db4d` values; PR-M no longer modifies frontmatter).
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
