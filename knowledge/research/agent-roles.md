# Research — Agent Roles: graphify, CAMEL, и research-backed паттерны

> **Status:** superseded by [`adr/ADR-2-llm-tiering.md`](../adr/ADR-2-llm-tiering.md) (archived 2026-05-08; body trimmed 2026-05-11 per PR-M).
>
> Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Role-routing decision shipped in ADR-2 (cheat-sheet row in [`adr/DIGEST.md`](../adr/DIGEST.md)). Original content preserved below for audit / git-history reference; **do not load top-to-bottom** — open the superseder instead.

> **Статус:** research note, 2026-04-23. Написан до принятия ADR-1..ADR-6 как
> фундамент под role-routing. Разбирает два референс-репозитория
> (graphify, CAMEL) плюс более широкий ландшафт публикаций о multi-agent /
> role-playing LLM-системах, и выдаёт явные рекомендации «что брать в v0.1, что
> попробовать позже, что не брать».
>
> Текущее role-routing решение зафиксировано в
> [`adr/ADR-2-llm-tiering.md`](../adr/ADR-2-llm-tiering.md) (Planner / Coder /
> Debug / Eval, static config); этот документ — input под него и под будущий
> ADR-7 (inner-loop). Ограничения по ролям и LLM-провайдерам — в
> [`project-overview.md` §6](../project-overview.md).
>
> **Промпты здесь НЕ пишутся** — это сознательно, по запросу. Документ собирает
> *структурные* идеи, которые войдут в будущий промпт-пакет, но оставляет
> написание самих текстов на следующий этап.
>
> Связь с уже существующими заметками:
> - [`agent-video-research.md`](./agent-video-research.md) — пять YouTube-видео
>   о паттернах агентов; этот документ опирается на его словарь
>   (tool use / RAG / planning / multi-agent, harness, determinism).
> - [`knowledge/architecture.md`](../architecture.md) — трёхслойная модель
>   First-Agent (Interface / Cognitive / Execution). Роли из §5 ниже ложатся в
>   Cognitive слой.

## Body trimmed — pointer only

The full pre-trim body lives in git history. It is not reproduced here because earlier abstract-style trims of this file introduced factual drift (see PR-13 Agent Review). To read the original verbatim:

```bash
git show cf7db4d:knowledge/research/agent-roles.md
# 932 lines pre-trim
```

## Where the current canonical content lives

- Active superseder: [`adr/ADR-2-llm-tiering.md`](../adr/ADR-2-llm-tiering.md) — read this instead of the pre-trim body.
- Inbound cross-references from older PR descriptions, ADRs, and supersession chains continue to resolve at this path — that is why the file is kept as a stub.

## Routing

Excluded from `knowledge/llms.txt §BY-DEMAND-INDEX` for the OSS-agent routing surface. Do not load this file top-to-bottom; open the active superseder above, or run the `git show` recipe if audit context is needed.
