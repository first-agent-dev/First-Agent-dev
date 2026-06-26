---
title: "Semi-autonomous LLM agents — критический разбор трёх источников vs ADR-1..6 (2026-05-01)"
compiled: "2026-05-01"
source:
  - 01.05+deep-research-report.md (user attachment, 256 lines, 2026-05-01)
  - 01.05+research_semi_autonomous_llm_agents.md (user attachment, 255 lines, 2026-05-01)
  - https://github.com/nextlevelbuilder/goclaw (default branch dev, latest release v3.10.0)
  - knowledge/adr/ADR-1-v01-use-case-scope.md
  - knowledge/adr/ADR-2-llm-tiering.md
  - knowledge/adr/ADR-3-memory-architecture-variant.md
  - knowledge/adr/ADR-4-storage-backend.md
  - knowledge/adr/ADR-5-chunker-tool.md
  - knowledge/adr/ADR-6-tool-sandbox-allow-list.md
  - knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md
  - knowledge/research/how-to-build-an-agent-ampcode-2026-04.md
  - knowledge/research/sliders-structured-reasoning-2026-04.md
chain_of_custody: >
  Все цитаты из трёх источников взяты дословно из
  user-attachments (deep-research-report, research_semi_autonomous_llm_agents)
  и публичной README репозитория goclaw на момент 2026-05-01. Точные
  номера абзацев — там, где это возможно из исходных markdown.
  Все architectural-выводы относительно First-Agent сверены с шестью
  принятыми ADR (ADR-1..ADR-6) и с предыдущей cross-reference-нотой
  от 2026-04-29. Любые рекомендации в §10 — input для будущих ADR,
  а не сами ADR; решения принимает проектный лид.
status: research
tier: deep-dive
supersedes: none
extends:
  - knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md
related:
  - knowledge/adr/ADR-1-v01-use-case-scope.md
  - knowledge/adr/ADR-2-llm-tiering.md
  - knowledge/adr/ADR-3-memory-architecture-variant.md
  - knowledge/adr/ADR-4-storage-backend.md
  - knowledge/adr/ADR-5-chunker-tool.md
  - knowledge/adr/ADR-6-tool-sandbox-allow-list.md
  - knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md
  - knowledge/research/how-to-build-an-agent-ampcode-2026-04.md
  - knowledge/research/sliders-structured-reasoning-2026-04.md
  - knowledge/research/agent-roles.md
links:
  - "../adr/ADR-1-v01-use-case-scope.md"
  - "../adr/ADR-2-llm-tiering.md"
  - "../adr/ADR-3-memory-architecture-variant.md"
  - "../adr/ADR-4-storage-backend.md"
  - "../adr/ADR-5-chunker-tool.md"
  - "../adr/ADR-6-tool-sandbox-allow-list.md"
  - "./cross-reference-ampcode-sliders-to-adr-2026-04.md"
  - "./how-to-build-an-agent-ampcode-2026-04.md"
  - "./sliders-structured-reasoning-2026-04.md"
mentions:
  - "OpenClaw"
  - "Hermes Agent"
  - "Pi Agent"
  - "GoClaw"
  - "MCP"
  - "Model Context Protocol"
  - "ReAct"
  - "Reflexion"
  - "ACI"
  - "Agent-Computer Interface"
  - "OpenHands"
  - "SWE-agent"
  - "Aider"
  - "LangGraph"
  - "Karpathy"
  - "AutoResearch"
  - "AlphaEvolve"
  - "AnthropicMCP"
  - "Wails"
  - "pgvector"
confidence: opinion
claims_requiring_verification:
  - "Все цифры по бенчмаркам (SWE-bench Verified ~70-77%, BrowseComp ~50%+,
     WebArena 57-81%) взяты из research_semi_autonomous_llm_agents.md как
     вторичный источник. До их использования в ADR — сверить с первичными
     paper'ами / GitHub README. На момент 2026-05-01 верификация не сделана."
  - "Утверждение, что все 20+ LLM-провайдеров goclaw поддерживают native
     tool-calling, не сверено: README перечисляет провайдеров, но не
     детализирует tool-protocol на уровне каждого slug'а."
  - "Утверждение «MCP — индустриальный стандарт 2026-го» опирается на
     consistent reference в трёх источниках (deep-report, semi-autonomous,
     goclaw README). Это сильная индикация, но не proof: ни один из
     источников не приводит market-share-цифр по adoption."
  - "Архитектурные выводы про несовместимость UC1 c многоуровневым
     OpenClaw-pipeline'ом (Gateway / Channel-plugins / Memory-plugins) —
     основаны на единственном UC1 acceptance-сценарии из ADR-1; они
     корректны под этот сценарий, но не претендуют на универсальность."
  - "ACI-цифры SWE-agent (12.5% SWE-bench early; non-negotiable for coding
     agents) — вторичные. До их фиксации в R-1 inner-loop ADR — сверить
     с paper Yang et al. 2024 (если будет нужна формальная ссылка)."
---

# Semi-autonomous LLM agents — критический разбор трёх источников vs ADR-1..6

> **Статус:** research note, 2026-05-01.
> **Что внутри:** систематический проход по трём источникам про
> semi-autonomous LLM agents (deep-research-report от пользователя,
> research_semi_autonomous_llm_agents от пользователя, репозиторий
> [`nextlevelbuilder/goclaw`](https://github.com/nextlevelbuilder/goclaw))
> с критической фильтрацией: что из них реально применимо к
> First-Agent v0.1 (UC1 + UC3, single-user CLI, Python), что — input
> для будущих ADR (R-1 inner-loop, по cross-reference §10), а что —
> overhead production-grade платформы и не относится к нашему скоупу.

> **Эта нота не предлагает менять ADR без ответа лида.** Она явно
> разделяет (а) рекомендации, на которые лид уже согласился в чате
> (MCP forward-compat → ADR-2 amendment, UC5 → ADR-1 amendment), и
> (б) input-материал для будущих ADR (ACI principle, hooks
> primitive). Сами правки в ADR делаются в этом же PR, но в
> отдельных файлах — research-нота это **обоснование**, ADR
> amendment — **решение**.

---

## §0. TL;DR

Пять выводов в одну строку каждый.

1. **70 % контента deep-research-report.md — generic agent-arch 101**
   (OpenClaw / Hermes / Pi Agent overview, AGENTS.md / SOUL.md /
   RULES.md / SKILL.md decomposition, MCP-basics, hooks-overview).
   Образовательно полезно, **но к UC1 coding-agent с single-user CLI
   применимо точечно**. Большинство концепций уже либо покрыты
   ADR-1..6, либо out-of-scope для v0.1.

2. **research_semi_autonomous_llm_agents.md — самый плотный источник.**
   Дельные 2026-паттерны (ReAct, Reflexion, ToT, Planner-Executor,
   ACI, Self-Evolving), MCP-starter-топология c концретными
   tool-сигнатурами (`repo.search` / `repo.read(path, start_line,
   end_line)` / `repo.apply_patch` / `git.status` / `git.commit`),
   честный разбор Python vs Go. **Минус: рекомендация «Python brain +
   Go harness» противоречит ADR-1 (Python-only) — но новых аргументов
   для пересмотра ADR-1 в этом источнике нет.**

3. **goclaw как production-reference — overscope для v0.1.**
   Multi-tenant Postgres + RBAC + 7 channels + 20+ LLM-providers + 8-stage
   pipeline (`context → history → prompt → think → act → observe →
   memory → summarize`) + knowledge-graph + pgvector — это та
   платформа, которой First-Agent **никогда** не должен стать в
   рамках v0.1 / v0.2. Полезные nuggets единичные:
   3-Tier-Memory framing, Knowledge-Vault с `[[wikilinks]]` +
   filesystem-sync, 5-layer permission-system как референс к ADR-6.

4. **Три действительно ценных идеи для First-Agent** после
   критической фильтрации:
   - **MCP forward-compat awareness** → small ADR-2 §Amendment в
     этом же PR (зафиксировать, что `tool_protocol: native` в v0.1
     должен оставаться MCP-совместимым по shape, чтобы будущие
     R-1 inner-loop ADR и v0.2 расширения не требовали re-design).
   - **ACI principle** (windowed reads, bounded outputs, targeted
     edits) — input для R-1 inner-loop ADR (cross-reference §10
     R-1, ещё не написан); фиксируем здесь, чтобы R-1 не повторил
     ампкодовский full-file-dump pattern.
   - **Hooks-система как primitive** (pre-run / pre-tool / post-tool /
     post-run / on-event) — input для R-1; ADR-6 sandbox по факту
     уже один pre-tool-hook, audit-log — post-tool-hook; явная
     hook-абстракция в R-1 удержит cross-cutting concerns
     (sandbox / audit / HITL / validation) разделёнными.

5. **Отвергнуто как не применимое к UC1 / v0.1 после критики:**
   SOUL.md / RULES.md decomposition (overlap c ADR-6 + chatbot-bias),
   skills/SKILL.md modular catalog (премачурно), Python+Go hybrid
   (без новых аргументов против ADR-1), multi-tenant / RBAC из
   goclaw (out-of-scope), MCP-Resources / MCP-Prompts publishing
   (не нужно для single-user v0.1; forward-compat и так
   автоматически из текущего layout).

---

## §1. Scope, метод, что эта нота явно НЕ покрывает

### 1.1 Что покрывает

- Критический проход по трём источникам с приоритетом на **what's
  actually new for First-Agent** vs **что уже принято в ADR-1..6**.
- Сводный список «accept / defer / reject» по каждой найденной
  идее с явным reasoning, **почему** именно так.
- Текстовые блоки для двух amendment'ов (ADR-2 и ADR-1) и пометки
  суперседии в §11 cross-reference от 2026-04-29.

### 1.2 Что не покрывает

- **Не предлагает имплементацию.** Тулы / loop / sandbox-runner —
  всё это будет в R-1 inner-loop ADR и в Phase M PR'ах, не здесь.
- **Не выбирает provider'ов.** ADR-2 уже фиксирует 4-6 моделей,
  vendoring обсуждается в HANDOFF и в Agent Knowledge note.
- **Не сравнивает goclaw с OpenHands / LangGraph / SWE-agent
  построчно.** Это сравнение есть в research_semi_autonomous §1-§2
  и не реплицируется здесь.
- **Не пытается «принять» рекомендации semi-autonomous-источника
  про durable execution + LangGraph.** Они корректны для
  multi-user production-агента; для single-user CLI v0.1 они
  избыточны (см. §6.4 ниже).

### 1.3 Метод

Каждый источник прошёл по пяти вопросам:

1. **Что заявляется?** (дословно, с цитатой / номером строки.)
2. **Совместимо с какой ADR / какой решённой осью?** (concrete
   ADR-1..6 / cross-reference §10.)
3. **Покрыто ли уже принятым решением, или это gap?**
4. **Если gap — это gap для v0.1 или v0.2?**
5. **Если для v0.1 — это amendment к существующему ADR или новый
   ADR? Если research-input — куда направить (R-1, R-4, новый ADR)?**

Любой пункт, прошедший вопрос 5 положительно, попадает в §10
сводный список. Любой не прошедший — попадает в §11 «отвергнуто с
обоснованием», чтобы будущие сессии не возвращались к нему без
новых аргументов.

---

## §2. Источник 1 — `01.05+deep-research-report.md`

### 2.1 Что заявляется

Файл — компактный (256 строк) обзор архитектуры современного LLM-
агента с примерами OpenClaw, Hermes Agent, Pi Agent. Структура:

- Файлы конфигурации агента (`AGENTS.md`, `SOUL.md`, `RULES.md`,
  `skills/SKILL.md`, `TOOLS.md`, `LLMS.md` / `llms.txt`).
- Компоненты: Planner, Loop / Agent Core, Tool Manager, Memory
  (short + long), Interfaces (CLI / GUI / messengers).
- MCP-серверы (JSON-RPC, STDIO + HTTP/SSE, OAuth 2.1).
- Hooks: `pre-run`, `pre-tool`, `post-tool`, `post-run`,
  `on-event`.
- Multi-tool calls в одном LLM-ответе (function-calling pattern).
- Доп. темы: безопасность, тестирование, состояние, версионирование,
  observability, latency / cost.

### 2.2 Покрытие vs ADR

| Заявление | Совпадает с ADR? | Статус |
|-----------|------------------|--------|
| `AGENTS.md` как source of operational instructions | Да, у нас он же | Покрыто |
| `SOUL.md` (personality / tone / values) | Нет аналога | **Reject** (см. §2.4) |
| `RULES.md` (granular constraints) | Частично — overlap с ADR-6 sandbox | **Reject** (см. §2.4) |
| `skills/SKILL.md` modular skills | Нет аналога | **Defer** (premature for v0.1) |
| `TOOLS.md` per-tool docs | Нет аналога | **Defer** (нет инструментов в v0.1) |
| `LLMS.md` / `llms.txt` | Полный аналог: `knowledge/llms.txt` | Покрыто |
| Planner / Loop / Tool Manager / Memory / Interfaces | Concept'ы; ADR-1..6 покрывают по частям | Покрыто |
| MCP basics (JSON-RPC, STDIO, HTTP/SSE) | Не упомянут в ADR-2 | **Accept** (small ADR-2 amendment) |
| Hooks: pre-run / pre-tool / post-tool / post-run / on-event | Не упомянуты ни в одной ADR; ADR-6 sandbox = pre-tool-hook де-факто | **Accept as input for R-1** |
| Multi-tool calls в одном ответе | Не упомянуто; tool-loop ADR не существует (R-1 future) | **Defer to R-1** |
| OAuth 2.1 для MCP-серверов | Out-of-scope для local single-user v0.1 | Reject |
| Docker-sandbox для bash | Concrete v0.1: ADR-6 sandbox.toml вместо Docker | Покрыто частично; см. §2.5 |
| RLHF / fine-tuning | Out-of-scope ADR-2 («No fine-tuning v0.1») | Покрыто |
| Versioning of tools | Не упомянуто; future R-1 | Defer |
| Observability (TrueFoundry, W&B, traces) | Не упомянуто; ADR-6 audit-log это subset | Defer to R-1 / future |
| Cost / latency awareness | ADR-2 §Consequences упоминает cost guardrail | Покрыто частично |

### 2.3 Что взято в work (детально)

**(A) MCP forward-compat awareness.**

Цитата (`deep-research-report.md` §MCP-сервера, ~стр. 80):

> «Model Context Protocol – открытый стандарт для связи AI-агентов
> с внешними системами и инструментами. Его часто называют
> "USB-C для ИИ". MCP позволяет агенту "подключать" удалённые
> сервисы (файловые системы, базы данных, API) по единому
> протоколу JSON-RPC.»

Это совпадает с research_semi_autonomous §B (mcp-git / mcp-repo-fs /
mcp-runner / mcp-web как separate stdio-серверы) и с goclaw README
(MCP среди core features). Три независимых источника одинаково
утверждают: MCP — индустриальный стандарт shape для tool-call
boundary. **Risk-если-проигнорировать:** в R-1 inner-loop ADR
зафиксируем shape, который не совместим с MCP, и при v0.2 / v0.3
расширении на multi-client (Claude Desktop / другой MCP host)
придётся менять tool-loop / валидаторы.

**Action.** Small §Amendment к ADR-2 (~30-40 строк): «`tool_protocol:
native` в v0.1 на стороне agent ↔ LLM остаётся; на стороне
agent ↔ tools держим JSON-RPC-shaped структуру (name, params,
result, error), даже если в v0.1 это in-process Python-вызовы —
чтобы R-1 inner-loop ADR + v0.2 могли вынести tools в отдельные
MCP-серверы без re-design'а».

Реализационная нагрузка для v0.1 — нулевая: native function-calling
(Anthropic, OpenAI, Qwen native) **уже** даёт JSON-shape ввода/
вывода тулов. Amendment фиксирует это **как конвенцию**, не как
новый требование.

**(B) Hooks как primitive — input для R-1.**

Цитата (`deep-research-report.md` §Механизмы хуков, ~стр. 113):

> «Обычно выделяют такие основные точки:
> - pre-run (pre-session): перед стартом задачи или сессии.
> - pre-tool (pre-call): до вызова конкретного инструмента.
> - post-tool: сразу после получения результата от инструмента.
> - post-run (post-session): после завершения сессии/задачи.
> - on-event / on-message: иногда есть хуки для обработки
>   промежуточных событий агента.»

Это **clean-аbstraction**, которая уже неявно живёт в нашем
ADR-6: `Sandbox.check_read` / `Sandbox.check_write` это pre-tool
hooks, а audit-log в `~/.fa/state/sandbox.jsonl` это post-tool
hook. Если R-1 inner-loop ADR явно введёт **hook-pipeline** как
primitive, то можно будет добавить:

- pre-tool: sandbox-проверка (ADR-6) + JSON-schema-валидация
  входов tool'а (cross-reference §8.5 R-7-related).
- post-tool: audit-log (ADR-6) + redaction чувствительных
  output'ов.
- pre-run / post-run: HITL-checkpoint (cross-reference §3.5
  «human-in-loop on git push»), time/token budget enforcement.
- on-event: streaming-token-log для observability.

**Action.** Не трогаем существующие ADR. Зафиксировать в этой
ноте как **input для R-1**, чтобы автор R-1 явно рассмотрел
hook-pipeline дизайн при описании inner-loop'а.

### 2.4 Что отвергнуто (с reasoning)

**(а) `SOUL.md` (personality / tone / values).**

Источник аргументирует: «Здесь зафиксировано, что агент никогда не
делает». Аргумент сильный для **chatbot-агента** с пользователем-
не-разработчиком. Для UC1 (coding agent с PR-flow для самого
владельца) и UC3 (local docs to wiki) **личность агента
несущественна**: lead принимает PR'ы, видит diff'ы, agent не
взаимодействует с третьими лицами через мессенджеры (UC4 deferred).

Кроме того, "values" типа «никогда не делиться личными данными»
для local single-user агента дублируются sandbox-policy ADR-6
(pri-list путей). Отдельный SOUL.md создал бы duplication-
hazard: правка в одном месте, забыли в другом. Reject.

**(б) `RULES.md` (granular constraints).**

Та же логика: 90 % того, что попало бы в RULES.md, уже живёт в
ADR-6 (write-deny list, read-deny list, audit-log). Оставшиеся
10 % (например, «не push в main без явного --force»)
естественно описывается в R-1 inner-loop ADR как часть HITL-
checkpoint hook'а. Дублировать в `RULES.md` — premature.
Reject.

**(в) `skills/SKILL.md` modular catalog.**

Аргументы за:

- Динамическая загрузка по keyword'у экономит контекст-окно.
- В goclaw skills — first-class entity (admin UI, max 5 skills
  в Lite edition).

Аргументы против на v0.1:

- У нас в v0.1 **нет** dynamically-loaded prompt'ов: все system-
  prompt'ы статически живут в `knowledge/prompts/` (ADR-2 +
  RESOLVER.md). Это работает для UC1 + UC3 без потери context-
  window'а.
- Skill-catalog имеет смысл, когда у агента 5+ существенно
  разных задач, требующих разных tool-set'ов. UC1 и UC3 на
  фундаменте используют одни и те же 4 базовых tool'а
  (`read_file` / `list_files` / `edit_file` / `git_push_pr`).
  Skill-decomposition будет artificial.

Defer to v0.2 (если UC2 multi-source research / UC5 multi-LLM
experiment окажутся требующими skill-разделения).

**(г) `TOOLS.md` как human-readable docs.**

Когда у нас будут **хоть какие-то** tool'ы (sейчас нет), описание
будет не в `TOOLS.md`, а в R-1 inner-loop ADR как часть tool-
registry contract'а + соответствующие docstring'ы в Python.
Отдельный `TOOLS.md` premature.

### 2.5 Что покрыто частично — Docker vs ADR-6 sandbox

Source утверждает: «выводимых команд `bash` не должно быть в
состоянии навредить хост-машине – стоит использовать Docker-
песочницу». ADR-6 sandbox делает то же без Docker — через path-
allow-list + audit-log + одношагового CLI bypass'а.

**Trade-off:**

- **Docker:** более жёсткая изоляция (network, syscall, FS), но
  тяжёлый dependency, не работает на Windows-без-WSL без боли,
  startup latency.
- **ADR-6 path-allow-list:** lightweight, native Python, **не
  защищает** от network-egress бинарей и от child-процессов,
  выходящих за allow-list через `Path.resolve()` symlink-trick'и
  (об этом cross-reference §8.4 предупреждает явно).

ADR-6 сознательно выбрал path-allow-list **потому что** v0.1 —
single-user dev-машина, agent читает локальные репо, не
выполняет произвольный bash от пользователя. Network-egress в
v0.1 — это API-вызовы LLM-провайдеров через `requests`, не
sandboxed-bash. Docker — overhead, не повышающий security-bar
для нашего threat-model'а.

**Verdict.** ADR-6 остаётся как принято, no amendment. Если в
v0.2 появится `bash` как explicit-tool — пересмотреть и
рассмотреть Docker (cross-reference §10 R-2 уже это
предусматривает).

---

## §3. Источник 2 — `01.05+research_semi_autonomous_llm_agents.md`

### 3.1 Что заявляется

255 строк, более structure'd чем источник 1. Главные тезисы:

- **Primary recommendation: Python для brain, Go для harness**
  (subprocess / sandbox / PTY / MCP-серверы / static binaries).
- **Hybrid 2026 architecture wins for production-grade
  semi-autonomous systems.**
- ReAct (Yao 2022), Reflexion (Shinn 2023), ToT, Planner-Executor
  separation (arXiv 2503.09572), ACI (SWE-agent — Yang 2024),
  Self-Evolving (AutoResearch / AlphaEvolve / Darwin-Gödel-Machine /
  MemEvolve), Durable Execution (LangGraph / Temporal), MCP, few
  sharp tools, structured outputs.
- **MCP starter architecture** с конкретной топологией:
  - Python orchestrator (LangGraph / OpenHands-style) = MCP host.
  - Local stdio-серверы: `mcp-git`, `mcp-repo-fs`, `mcp-runner`,
    `mcp-web`.
  - Remote HTTP+SSE MCP только когда нужен multi-user.
- **Concrete tool surface:** `repo.search(query, paths?, regex?)`,
  `repo.read(path, start_line, end_line)`, `repo.apply_patch(patch)`,
  `repo.lint() / repo.test(target?)`, `git.status() / git.diff() /
  git.commit(message, trailers)`, plus `web.search`, `web.open`,
  `web.extract_citations`, `pdf.open`.

### 3.2 Покрытие vs ADR

| Заявление | Совпадает с ADR? | Статус |
|-----------|------------------|--------|
| Python primary | ADR-1 + ADR-2 (Python) | Покрыто |
| Go harness hybrid | ADR-1 (Python-only) | **Reject** (см. §3.4) |
| ReAct interleaving | Не в ADR; future R-1 | Defer to R-1 |
| Reflexion (verbal self-reflection + episodic memory) | ADR-2 §Amendment («v0.1 без Critic, Reflector — v0.2») | Покрыто (defer) |
| ToT (tree-of-thoughts) | Out-of-scope v0.1 | Reject |
| Planner-Executor separation | ADR-2 (Planner / Coder / Debug) | Покрыто |
| ACI: windowed reads / bounded outputs / targeted edits | Не в ADR; gap | **Accept as input for R-1** |
| Self-Evolving (AutoResearch / AlphaEvolve) | Out-of-scope v0.1; v0.2 заметка | Defer |
| Durable Execution + LangGraph | Out-of-scope v0.1 (single-session CLI) | Defer; см. §3.5 |
| MCP starter (mcp-git/repo-fs/runner/web) | См. §2.3-A | **Accept** (ADR-2 amendment) |
| Few sharp tools + structured outputs | Принцип; ADR-2 §Consequences согласуется | Покрыто (concept) |
| Tool surface tools/signatures | Concrete; не в ADR; future R-1 | Input for R-1 |
| Eval beyond pass@1 | ADR-2 (Eval role offline) | Покрыто |
| Sandboxing (Docker / Firecracker) | ADR-6 (path-allow-list) | См. §2.5 |
| RAG over knowledge/ | ADR-3 (Variant A FTS5) | Покрыто |

### 3.3 Что взято в work

**(A) ACI principle — input для R-1.**

Цитата (`research_semi_autonomous` §2 «For Coding Agent»):

> «ACI critical (SWE-agent insight): Windowed reads, targeted
> edits (not full file dumps), bounded outputs.»

Цитата (§C «Concrete tool surface»):

> «repo.read(path, start_line, end_line) → windowed»

Это **прямой контраст** с ампкодовским подходом: в
[`how-to-build-an-agent-ampcode-2026-04.md`](./how-to-build-an-agent-ampcode-2026-04.md)
(§3.1 / §5) `read_file(path)` возвращает **весь файл целиком**.
На малых файлах работает; на большом repo (наш UC1, 50k+ LoC
projects) full-file-dump → context-bloat → plan-degradation →
больше hallucinations (cross-reference §3.2 уже отмечает это
для Coder-tier).

Кроме `repo.read(path, start_line, end_line)`, ACI-принцип
расширяется на:

- `repo.search(query, paths?, regex?) → matches с line ranges`
  вместо raw grep-output (который для regex-binary может быть
  binary-noise).
- `repo.apply_patch(patch)` через unified-diff format
  (cross-reference §10 R-3 string-replace OK на всех тиерах,
  но unified-diff более compositional при множественных
  правках в одном файле).
- `repo.lint()` / `repo.test(target?)` через ADR-6 sandbox
  с hard cap на runtime (например, 30s / 100MB output).

**Action.** Не трогаем существующие ADR. Зафиксировать в этой
ноте как **input для R-1**, чтобы R-1 явно описал tool-
сигнатуры со windowed/bounded-конвенциями. Cross-reference §10
R-3 уже есть; этот блок дополняет его деталями ACI.

**(B) MCP starter topology — input для ADR-2 amendment + R-1.**

Цитата (`research_semi_autonomous` §B «Recommended starter
topology»):

> «mcp-git: safe git operations (status, diff, blame, apply
> patch, commit w/ template). No push by default. /
> mcp-repo-fs: file read/write but scoped (roots allowlist);
> plus "windowed reads" and "apply patch" APIs (ACI-ish). /
> mcp-runner: sandboxed command execution (tests, linters)
> with CPU/mem/time caps. / mcp-web: browser/search/PDF fetch
> in a separate sandbox, returning citations + extracted
> text.»

Comment'ы по нашему контексту:

1. **`mcp-repo-fs` ≈ ADR-6 sandbox + ACI tool-сигнатуры.**
   В v0.1 это in-process Python-функции, **не отдельный
   процесс**. ADR-2 amendment фиксирует именно
   tool-shape-совместимость, чтобы при v0.2 можно было вынести
   в отдельный stdio-сервер.

2. **`mcp-git` ≈ один из наших v0.1 tools** (`git.status`,
   `git.diff`, `git.commit`, без push-by-default, push через
   ADR-1 §Concrete v0.1 in-scope «push branch → open PR via
   `gh` CLI» с allow-list `~/.fa/repos.toml`).

3. **`mcp-runner` ≈ ADR-6 sandbox + lint/test runners.**
   Поднимать как отдельный stdio-server в v0.1 не нужно;
   вызовы синхронные in-process через subprocess, sandbox
   гарантирует path-isolation. CPU/mem/time-caps —
   defer to R-1.

4. **`mcp-web` — out of scope v0.1.** UC2 best-effort retrieval
   only без новой инфраструктуры (ADR-1 §Concrete v0.1
   in-scope). Web-tool ноут на v0.2 / UC2-уровне.

**Action.** ADR-2 §Amendment фиксирует MCP-shape compatibility
(JSON-RPC-shaped tool signatures с name/params/result/error),
чтобы v0.2 распилка на mcp-серверы была одношаговой config-
изменением, а не code-rewrite'ом. Никаких новых процессов в v0.1.

### 3.4 Что отвергнуто

**(а) Python+Go hybrid harness.**

Аргументы источника:

- Goroutines vs asyncio.GIL — лучше для concurrent web-search /
  test-run.
- `os/exec` без shell pitfalls — безопаснее.
- Static binary — проще deploy.
- Amp <400-line Go agent — proof of viability.

Контраргументы для нашего контекста:

- **UC1 single-user CLI на dev-машине лида.** Concurrency-
  scenario'и (parallel web-search) не существуют: UC2
  best-effort fan-out — это последовательный multi-LLM
  query, не CPU-bound. asyncio + httpx справляется без
  GIL-проблемы.
- **`os/exec` vs Python `subprocess.run(args, shell=False, ...)`** —
  оба избегают shell-injection при правильном использовании.
  Python `subprocess` с `shell=False` и list-args — тот же
  level безопасности.
- **Static binary полезен** для distribution в multi-user
  scenario; для single-user lead-машина py + .venv работает.
- **Amp-Go демонстрация ценна, но это именно proof-of-
  concept**, а не production-pattern. Anthropic Python SDK
  (которым пользуется ампкод) даёт ту же compactness.

ADR-1 (Python) принят с обоснованием в `project-overview.md`
§6, и три источника не приводят **новых** аргументов против.
Reject. Если в v0.2+ при нагрузке окажется, что Python harness
не справляется — пересмотреть отдельной ADR.

**(б) Durable execution + LangGraph + Temporal.**

Целевой use-case durable-runtime'ов: long-running multi-day
agentic tasks с checkpoint'ами и replay'ем. Klarna / Uber /
JPM пример'ы корректны для production-агентов, обрабатывающих
тысячи параллельных пользовательских запросов с SLA на
resumability.

UC1 single-session ingest-search-edit-push-PR flow по UC1
helper-сценарию занимает минуты, не дни. Crash mid-session —
пользователь (lead) перезапускает, без data-loss за счёт
git-state и `~/.fa/state/`. Persistent-state — ADR-3 SQLite
FTS5 + ADR-4 chunk-store — уже даёт нам нужный durability
для retrieval-state. LangGraph бы добавил overhead без gain'а
для single-user.

Defer-to-v0.2 если UC4 (multi-user TG) активируется.

**(в) Self-evolving (AutoResearch / AlphaEvolve / Darwin-Gödel-
Machine).**

Чистый research-frontier 2025-2026. Применимо к **ML-research-
агенту** (Karpathy editing `train.py`), не к coding+PR
помощнику single-user'а. v0.1 self-evolution — это не цель.

ADR-2 amendment уже зафиксировал «v0.1 inner-loop без Critic /
Reflector; v0.2 ADR на reflection». Self-evolution — следующий
шаг **за** Reflector'ом, далеко в будущем. Reject (для скоупа
этой ноты).

**(г) ToT (tree-of-thoughts) per step.**

Источник сам признаёт: «expensive for every step». ToT имеет
смысл для localized hard problems (bug-localization,
algorithm-design), а не как default planning-pattern. Может
вернуться в v0.2 как narrow Debug-role tool. Defer.

### 3.5 Что покрыто частично — Reflexion vs v0.1 «inner-loop без Critic»

Источник упоминает Reflexion (Shinn 2023) как «core for retry
loops in coding/research, 91% HumanEval in early tests».
ADR-2 §Amendment 2026-04-29 явно говорит:

> «v0.1 inner-loop has no Critic / Reflector role. The roles
> are exactly: Planner, Coder, Debug (manual escalation only),
> Eval (offline judge, out-of-band). Reflection / self-
> correction loops are v0.2 material; design is in-flight
> (user note, Apr 2026) and will land as a separate ADR.»

То есть **намеренно** v0.1 без Reflexion. Источник valid; наш
ADR — осознанный выбор. Покрыто.

Дополнительный нюанс: ADR-2 различает «no auto-escalation»
(нет cross-tier escalation) и «intra-role retry-loop allowed»
(Coder может ретраить failed `edit_file`). Это **уже** subset
Reflexion-shape без verbal self-reflection. Полная Reflexion
(verbal critique + episodic memory write) — v0.2.

---

## §4. Источник 3 — `nextlevelbuilder/goclaw` (Go-based platform)

### 4.1 Что заявляется

GoClaw — production-grade multi-tenant agent platform на Go,
переписанный из OpenClaw. README ([github.com/nextlevelbuilder/goclaw](https://github.com/nextlevelbuilder/goclaw))
заявляет:

- **8-Stage Agent Pipeline:** `context → history → prompt →
  think → act → observe → memory → summarize`. Pluggable
  stages, always-on execution.
- **4-Mode Prompt System:** Full / Task / Minimal / None с
  section-gating и cache-boundary-оптимизацией.
- **3-Tier Memory:** Working (conversation) → Episodic (session
  summaries) → Semantic (knowledge graph). Progressive loading
  L0/L1/L2.
- **Knowledge Vault:** document registry с `[[wikilinks]]`,
  hybrid search (FTS + pgvector), filesystem sync.
- **Agent Teams:** shared task boards, inter-agent delegation
  (sync/async), 3 orchestration modes (auto/explicit/manual).
- **Self-Evolution:** metrics → suggestions → auto-adapt с
  guardrails.
- **Multi-Tenant PostgreSQL:** per-user workspaces, encrypted
  API keys (AES-256-GCM), RBAC, isolated sessions.
- **20+ LLM-providers** (Anthropic native HTTP+SSE с prompt
  caching, OpenAI, OpenRouter, Groq, DeepSeek, Gemini, Mistral,
  xAI, MiniMax, DashScope, Claude CLI, Codex, ACP).
- **7 messaging channels:** Telegram, Discord, Slack, Zalo OA,
  Zalo Personal, Feishu/Lark, WhatsApp.
- **5-layer permission system,** rate-limiting, prompt-injection
  detection, SSRF protection.
- **Single binary** ~25MB, <1s startup, $5 VPS.
- **Lite edition (desktop):** Wails v2 + React, SQLite (FTS5),
  max 5 agents / max 1 team (5 members), no knowledge-graph,
  no RBAC.

### 4.2 Покрытие vs ADR — почему 90 % overscope

GoClaw — это **multi-user production agent platform с
team-orchestration'ом**, в которой:

- Один deployment обслуживает множество пользователей.
- Несколько agent'ов внутри организации делегируют задачи
  друг другу через task-board'ы.
- Канальный layer (Telegram / Slack / WhatsApp) подключает
  агента к организационным мессенджерам.
- RBAC + encryption + injection-detection требуются для
  multi-tenant безопасности.

ADR-1 жёстко зафиксировал: First-Agent v0.1 — **single-user CLI
helper** для одного владельца. UC4 (Telegram multi-user) —
deferred. UC5 (multi-LLM experiment) — out-of-scope. Большая
часть goclaw-features прямо из этой плоскости и в наш скоуп
не попадает.

### 4.3 Что взято в work

**Ничего нового против §2-§3.** Полезные nuggets из goclaw —
**подтверждение** уже принятых решений из других источников:

- **MCP — first-class** (среди core features). Подтверждает §2.3-A.
- **3-Tier Memory** (Working/Episodic/Semantic) ≈ shape ADR-3
  Variant A (`hot.md` working state + chunk-store FTS5
  episodic + structured wiki semantic). У нас это уже
  есть на уровне concept, без явной 3-tier-нумерации.
  Adding nothing new.
- **Knowledge Vault** с `[[wikilinks]]` + filesystem-sync —
  shape совпадает с нашим `knowledge/` markdown-canon
  (filesystem-canon principle, anchor IDs, supersession).
  `[[wikilinks]]`-формат у нас уже встречается местами в
  `knowledge/research/llm-wiki-*` (правда, не системно;
  cross-reference §10 R-9 namechecked).
- **5-layer permission system** ≈ analog ADR-6 sandbox с
  layered approach. Goclaw делит на: input-validation /
  auth / role-permission / rate-limit / output-sanitization.
  ADR-6 покрывает path-allow-list (input + output), rate-
  limit и rest — defer to R-1.
- **Single binary <1s startup** — Go-specific; для Python
  v0.1 невозможно без PyOxidizer / Nuitka, и не нужно
  (single-user dev-машина).

### 4.4 Что отвергнуто

**(а) 8-Stage Agent Pipeline** (`context → history → prompt →
think → act → observe → memory → summarize`).

Это «полный» pipeline, рассчитанный на agent с long-running
session'ами и сложной memory. Для UC1 single-action-PR-flow
большинство стадий сворачиваются:

- **context + history** — у нас один system-prompt
  (ARCHITECT-FA или RESOLVER-dispatched по T1-T5) + recent
  user messages. История не нужна (single-task per session).
- **prompt** — статический выбор из `knowledge/prompts/`.
- **think** — LLM-call (Planner-tier).
- **act** — tool-call (R-1 future ADR).
- **observe** — tool-result back to LLM.
- **memory** — `~/.fa/state/sandbox.jsonl` audit-log + chunk-
  store; не каждую turn'у пишется long-term memory.
- **summarize** — for v0.1 single-task не нужен; v0.2 add.

Naming inflation, не architectural-новизна. R-1 inner-loop
ADR опишет **3-stage minimal** loop (think → act → observe)
как ампкод; advance-фaзы (memory / summarize) — v0.2 если
понадобится.

**(б) Agent Teams + inter-agent delegation.**

UC4 (multi-user) deferred, UC5 (multi-LLM compare) — это **не**
agent-teams: это один control-loop, выполняющий одну и ту же
задачу несколькими LLM последовательно с компарацией результата
(см. §5 ниже). Goclaw teams нужен для multi-tenant org-flow
(2+ agents с раздельными task-board'ами); у нас всегда один
agent в session'е. Reject.

**(в) Multi-tenant PostgreSQL + RBAC + AES-256-GCM encryption.**

Single-user → one user → нет tenancy. API-keys у нас живут в
`~/.fa/secrets.toml` (locked-down via filesystem perms 0600);
RBAC между «агентом и пользователем» — nonsense (это один
человек). PostgreSQL вместо SQLite — overkill для single-user
(ADR-4 SQLite FTS5 уже выбран). Reject.

**(г) 7 messaging channels.**

UC4 deferred. Когда v0.2 активирует UC4 — **ровно один**
канал (Telegram, по `project-overview.md`). 7 каналов —
goclaw scope. Reject.

**(д) Self-Evolution с auto-adapt + guardrails.**

См. §3.4-(в). v0.1 не self-evolve. Reject (для текущей ноты).

**(е) Prompt Caching (Anthropic prompt cache markers).**

Anthropic-specific; даёт 2-10× cost-reduction для repeated
context. Полезно, **но**:

- Только Anthropic + native protocol (другие провайдеры —
  OpenRouter / vLLM — не поддерживают единообразно).
- Требует управления cache-boundary в prompt-template'е (4-mode
  prompt system у goclaw — именно про это).
- Для v0.1 single-task per session benefit'а почти нет: cache
  не успевает прогреться.

Defer to v0.2 если ADR-2 расширится на cost-optimisation.

### 4.5 Что покрыто частично — Knowledge Vault `[[wikilinks]]`

Goclaw указывает `[[wikilinks]]` как механизм cross-reference
в knowledge-vault'е, плюс filesystem-sync (FTS + pgvector).
Наш `knowledge/`:

- **filesystem-canonical** (markdown — source of truth) ✓
- **FTS5** через ADR-4 ✓
- **pgvector / embeddings** — defer (cross-reference §6 ADR-3
  Variant B/C/D обсуждает)
- **`[[wikilinks]]`** — частично; ad-hoc в нескольких
  research-нотах. **Не системно.**

`[[wikilinks]]` vs markdown-relative-links:

- `[[wikilinks]]` — короче, robust к перемещению файлов (если
  есть resolver), наглядно в Obsidian / Logseq.
- markdown-relative-links — стандартны, работают без resolver'а
  в любом markdown-renderer'е, но ломаются при перемещении.

Решение для v0.1 — **не менять**: cross-reference §10 R-9
(deferred); markdown-links продолжают работать; introducing
`[[wikilinks]]` сейчас потребовало бы resolver-tool'а на стороне
chunker'а или R-1. Отметить в R-9 как «goclaw подтверждает
ценность; отложено до Phase M chunker-PR'а».

---

## §5. Sources × ADR пересечения, по которым нужны действия

Сводная таблица.

| Источник | Цитата / тезис | ADR/Q | Действие |
|----------|---------------|-------|----------|
| deep-report §MCP + semi-autonomous §B + goclaw README | MCP — индустриальный стандарт shape для tool-call boundary | ADR-2, R-1 future | **ADR-2 §Amendment** + research-input |
| deep-report §Hooks | 5 hook-точек как primitive (pre-run / pre-tool / post-tool / post-run / on-event) | R-1 future | research-input |
| semi-autonomous §2 + §C | ACI: windowed reads, bounded outputs, targeted edits, унифицированные tool-signatures | R-1 future | research-input |
| semi-autonomous §B | mcp-git, mcp-repo-fs, mcp-runner, mcp-web как stdio-серверы | ADR-2 + R-1 future | research-input + ADR-2 amendment ссылается |
| semi-autonomous §C | Concrete tool surface: `repo.read(path, start_line, end_line)` etc. | R-1 future | research-input |
| semi-autonomous §2 | Few sharp tools / structured outputs / Anthropic warning | ADR-2 §Consequences | покрыто (concept) |
| semi-autonomous §3 | Python+Go hybrid | ADR-1 | **Reject + document** |
| goclaw README | 3-Tier Memory framing | ADR-3 | shape-confirmation, no change |
| goclaw README | 8-Stage Pipeline | R-1 future | reject как inflation |
| goclaw README | Multi-tenant / RBAC / 7 channels / 20+ providers | ADR-1 (out-of-scope), ADR-2 | reject |
| goclaw README | `[[wikilinks]]` knowledge-vault | cross-reference §10 R-9 | confirm deferral |
| goclaw README + semi-autonomous | Self-evolving (AutoResearch / AlphaEvolve) | ADR-2 amendment v0.2 reflection-ADR | defer |
| user request 2026-05-01 | UC5 — semi-autonomous multi-LLM research/experiment | ADR-1 §Out-of-scope | **ADR-1 §Amendment** |

Plus две reconciliation-метки в cross-reference §11:

| Cross-reference §11 ответ | Реальное состояние | Действие |
|----------------------------|--------------------|----------|
| Q-1: новый ADR-6 «inner-loop + tool contract» | ADR-6 уже = sandbox (PR #6 merged) | **Mark Q-1 superseded:** future inner-loop становится ADR-7 |
| Q-2: sandbox = amendment к ADR-1 | sandbox = ADR-6 (PR #6 merged) | **Mark Q-2 superseded:** sandbox остался отдельным ADR; ADR-1 без amendment по этому пункту |

---

## §6. Глубокая критика отдельных тезисов источников

### 6.1 Deep-research-report — generic vs UC1-specific

Deep-report даёт «hub-and-spoke» обзор agent-arch, что
полезно для **онбординга в общую тему**, но плохо передаёт
**trade-off'ы под конкретный use-case**. Например, описание
SOUL.md / RULES.md / SKILL.md — нейтральное и не объясняет:

- Когда decomposition стоит сложности (chatbot multi-turn с
  персистентной личностью).
- Когда decomposition вреден (single-user dev-tool, где
  persona = пустота, rules = sandbox).

Для First-Agent v0.1 — vеют дублицирующих файлов с
overlap'om в правилах. Принятие SOUL.md/RULES.md из deep-
report без критической линзы привело бы к docs-bloat без
выигрыша. **Lesson:** generic agent-arch литература требует
явного UC-аудита перед применением, иначе copy-paste-cargo-
cult.

### 6.2 Semi-autonomous §3 — Python vs Go аргументы

Источник делает честный side-by-side, но финальный verdict
«Python brain + Go harness» завязан на:

1. **Production scale** (multi-user, durable, deployable as
   single binary).
2. **Concurrent tool-calls на одном host'е** (parallel web-search,
   parallel test-run).
3. **«No abstraction ceiling, LLMs generate reliable Go code»**
   тезис.

Под наш UC1 single-user single-task:

1. Production scale — N/A.
2. Concurrent tool calls — выполняем последовательно
   (one tool per turn в ампкод-стиле). Async-overhead
   asyncio покрывает.
3. LLM-generation reliability — иронично, ADR-2 + cross-
   reference §3.2 предупреждает что mid-tier OSS coder
   худше Claude 3.7 на string-replace edit-формате; нет
   доказательств, что Go-target лучше Python-target для
   тех же моделей. Этот аргумент — folk-wisdom без бенчмарка
   в источнике.

**Vердикт.** Аргумент за Go-harness не выдерживает критики
для нашего скоупа. ADR-1 stays. Если в v0.2 при реальной
нагрузке окажется иначе — отдельная ADR с эмпирикой.

### 6.3 Semi-autonomous §2 — ACI как «non-negotiable»

Источник прямо пишет: «Non-negotiable for coding agents».
Это сильное утверждение.

**За (поддерживаю):**

- Cross-reference §3.2 (ампкод) уже flag'ал full-file-dump
  pattern как риск для Coder-tier на больших файлах.
- ADR-5 chunker уже выдает chunks с `byte_start/end` и
  `line_start/end` (PR #3 amendment) — **infrastructure
  готова** для windowed reads.
- ACI tool-сигнатуры hashable со sandbox-policy ADR-6
  (path-allow-list проверяет path before read; bounded
  range — natural extension).

**Против (нюанс):**

- «Non-negotiable» — overstated. Ampcode демонстрирует
  работающий agent с full-file-read на малых файлах. Для
  нашего UC3 (notes/inbox/ markdown-files обычно <100KB)
  full-file-read адекватен.
- Windowed read добавляет complexity на стороне prompt'а
  («as agent, я знаю, что мне нужны строки 50-100 — но
  откуда я это знаю до read'а?»). Решение — двухстадийный
  workflow: search → narrow read.

**Vердикт.** ACI важен, но **не non-negotiable** для всех
случаев. R-1 inner-loop ADR должен описать **обa shape'а**
(`repo.read(path)` для small files; `repo.read(path,
start_line, end_line)` для large) и **дать модель choose**
исходя из first read-size. Этот блок — input для R-1.

### 6.4 Semi-autonomous §2 — Durable Execution через LangGraph

Источник перечисляет: «Klarna, Uber, JPM» как production-
adopters. Это **financial / e-commerce контекст** с
long-running orchestration над transactions, requiring
checkpoints + replay для compliance.

Наш UC1 — **single-session ingest-search-edit-PR**, в
течение минут. Crash recovery — re-run от lead'a. SQLite
chunk-store + sandbox audit-log дают наблюдаемость post-hoc.
LangGraph-stateful-graphs добавили бы:

- Persistent state-machine (на чьём storage?).
- Checkpoint-ser/deser логику для каждого state'а.
- Resume-from-checkpoint протокол.
- Зависимость от LangChain ecosystem.

Для single-user CLI это — **pure overhead**. Defer.

### 6.5 Goclaw 4-Mode Prompt System — действительно ли применимо?

Goclaw имеет 4 режима system-prompt'а: Full / Task / Minimal /
None с section-gating и prompt-cache-boundary-оптимизацией.
Звучит впечатляюще, но это решает специфическую goclaw-
проблему: Anthropic prompt-caching работает только если
section-content внутри cache-boundary не меняется между
turn'ами.

Для First-Agent:

- Anthropic — один из провайдеров, но не unique. Mid-tier
  OSS (Qwen, GLM, Nemotron) — нет prompt-caching;
  4-mode-system бесполезен.
- Один static system-prompt из RESOLVER.md покрывает все
  v0.1-сценарии. T1-T5 dispatching — это уже select-among-
  prompts; нет нужды в section-gating per turn.

Reject как goclaw-specific complexity. Возможный future
v0.2 cost-optimization-ADR может рассмотреть Anthropic-
specific cache markers как narrow improvement, но это не
перенос goclaw-mechanism'а.

### 6.6 MCP — насколько глубокая ставка для v0.1?

Все три источника называют MCP «индустриальным стандартом
2026». Это сильный consistent signal. Однако:

- **MCP-spec 2024-2025 ещё в development.** Версионирование
  меняется (recent change: STDIO → STDIO+HTTP).
- **Adoption-numbers нет** в источниках. «20+ providers»,
  «embedded in Claude / ChatGPT» — без % share или rate
  growth.
- **Tooling в Python для MCP** (`mcp` package) ещё young —
  API-changes между minor-versions.

**Risk если поставим всё на MCP в v0.1:**

- API-breakage в `mcp` package между Phase M и Phase v0.2 →
  refactor.
- Если MCP standard эволюционирует на breaking-change —
  refactor.

**Risk если игнорируем MCP:**

- R-1 inner-loop ADR определит tool-shape, который не
  совместим с MCP-JSON-RPC, и v0.2 расширение требует
  больших изменений.

**Compromise (в ADR-2 amendment):** не **импортировать**
MCP-Python-package в v0.1, не ставить **зависимость**, но
**держать tool-signatures shape-compatible** (JSON-shaped
inputs/outputs с name/params/result/error). Это даёт нам
zero implementation cost сейчас и keep-options-open для
v0.2.

### 6.7 Kanban-style task-board из goclaw — потенциал для UC5?

Goclaw имеет shared task-board'ы для multi-agent delegation.
UC5 (semi-autonomous multi-LLM experiment) **не** про
multi-agent delegation, а про **same task → multiple LLM
runs → comparison report**.

Структура UC5 ближе к **eval-harness** (cross-reference §6
ADR-2 mentions «LLM-as-judge offline»), а не agent-team.
Для UC5 v0.2 нам нужен:

- Test-set спецификация (например, «10 issues из real
  repo»).
- Run-runner: same prompt → N моделей → N output'ов.
- Comparison-report-generator (templated markdown).

Goclaw task-board сюда не ложится. Reject как inspiration
для UC5; UC5 имеет own design под `eval-harness` shape, не
agent-team shape.

---

## §7. Что добавляют источники к cross-reference §10 рекомендациям

Сравнение с уже принятыми R-1..R-10 (после Q-1..Q-10
ответов лида) из cross-reference от 2026-04-29.

### 7.1 R-1 Inner-loop ADR — расширения от этой ноты

Cross-reference §10 R-1 уже описывает: tool registry contract,
sandbox/path allow-list (теперь = ADR-6), tool-protocol
negotiation, input validation, structured tool-call audit log.

**Добавляем в input для R-1:**

1. **MCP-shaped JSON-RPC structure** для tool-signatures
   (см. §2.3-A, §3.3-B).
2. **Hook-pipeline primitive:** pre-run / pre-tool / post-tool /
   post-run / on-event hooks как первоклассные точки
   расширения. ADR-6 sandbox это pre-tool-hook де-факто;
   audit-log — post-tool-hook (см. §2.3-B).
3. **ACI principle для tool-сигнатур:** windowed reads
   (`repo.read(path, start_line, end_line)`), bounded
   outputs (max-bytes/lines per result), targeted edits
   (`repo.apply_patch(unified_diff)`) — **в дополнение** к
   simple `repo.read(path)` и string-replace edit
   (cross-reference §10 R-3) (см. §3.3-A).
4. **Two-stage read pattern:** `repo.search` → narrow-by-
   line-range → `repo.read(path, start_line, end_line)` для
   больших файлов; `repo.read(path)` для маленьких. R-1
   должен описать heuristic threshold (например, by
   chunk-store size estimate) (см. §6.3).

### 7.2 R-2 Sandbox ADR — superseded by ADR-6

Cross-reference §11 Q-2 ответ говорил «sandbox = amendment
к ADR-1». Реальность: PR #6 ввёл ADR-6 как отдельный
ADR. Лид по §11 Q-1/Q-2 reconciliation выбрал «accept-as-is»;
ADR-6 остаётся, future inner-loop = ADR-7.

Эта нота **подтверждает** что ADR-6 — правильное решение:

- 350+ строк policy с TOML / globs / audit log / one-shot
  bypass плохо умещается в §«Concrete v0.1 in-scope list»
  ADR-1 (cross-reference §3.5 уже это было предупреждение).
- Goclaw 5-layer permission-system (§4.3) — independent
  reference: production-grade платформа выделяет permission
  system как separate concern, не нагружает scope-ADR.

### 7.3 R-3 string-replace edit-format — confirmation

Cross-reference §10 R-3 фикстура уже принята (Q-3 «string-replace
OK на всех тиерах → запинить в loop ADR»). semi-autonomous §C
дополняет: `repo.apply_patch(unified_diff)` как **второй
shape** для multi-edit cases (множественные правки в одном
файле), что выходит за scope simple string-replace.

**Input для R-1:** R-1 опишет два edit-shape'а:

1. `edit_file(path, old_string, new_string)` — single-edit
   (ампкод-style, простой mental-model для модели).
2. `apply_patch(unified_diff)` — multi-edit одной операцией;
   atomic, проверяемый через `git apply --check`.

R-3 фикстура (5-10 правок на каждой целевой модели) должна
тестировать **обa shape'а**, чтобы понять где какая модель
лучше (Coder-tier mid-OSS vs Anthropic).

### 7.4 R-4 Variant D — confirmation

Cross-reference §10 R-4 (Variant D / SLIDERS extraction layer
для v0.2) — без изменений. Ни одного из трёх источников не
обсуждает SLIDERS extraction-pattern, поэтому R-4 не
дополняется.

### 7.5 R-5 chunks schema — done

PR #3 уже добавил `parent_title`, `breadcrumb`, `byte_start/end`
в chunks schema. semi-autonomous §C tool-сигнатура
`repo.read(path, start_line, end_line)` теперь **естественно**
ложится поверх R-5: line_start/end уже в metadata; tool
просто фильтрует by них. Confirmation: PR #3 правильное
решение.

### 7.6 R-6 frontmatter `topic:` — done

PR #4 уже добавил `topic:` opt-in. Ни в одном из трёх
источников нет аргументов против; goclaw подтверждает ценность
тематического разделения через separate `tools/skills/` per-
domain. Confirmation.

### 7.7 R-7 ADR-2 single-loop — done

PR #5 уже добавил v0.1 inner-loop без Critic. ADR-2 amendment
2026-04-29 эксплицирует roles + tool_protocol field.

**Текущая (этой ноты) ADR-2 amendment** — отдельный
amendment про MCP forward-compat — orthogonal к R-7. Один
файл (ADR-2-llm-tiering.md) содержит **два amendment'а**:
2026-04-29 (R-7-related: tool_protocol + no-Critic) и
2026-05-01 (MCP forward-compat). Cumulative.

### 7.8 R-8 терминология (glossary + inline ADR-defines)

Cross-reference Q-8 ответ (a) — `docs/glossary.md` + inline
в каждой ADR кратко. Не сделано в PR-A..D. Source 1
(deep-report) добавляет термины, которые могут попасть в
glossary при будущей работе:

- **MCP, mcp-server, mcp-host, mcp-client.**
- **Hook (pre-tool / post-tool / pre-run / post-run / on-event).**
- **ACI (Agent-Computer Interface).**
- **Reflexion / Critic / Reflector.**
- **Self-evolving / AutoResearch.**

Не делаем PR на glossary в этой сессии; отмечаем как input
для будущей R-8-PR.

### 7.9 R-9 — `[[wikilinks]]` confirmation deferred

Goclaw подтверждает ценность; markdown-relative-links
продолжают работать; deferral remains.

### 7.10 R-10 — без изменений

R-10 (out-of-scope для cross-reference) — без касания.

---

## §8. Тонкие натяжки и open questions

### 8.1 ADR-1 in-scope vs UC5

UC5 — «semi-autonomous research/experiment across different
LLM models on the same task, producing comparable research
docs» — добавлен пользователем 2026-05-01.

**Натяжка:** ADR-1 §Concrete v0.1 in-scope list содержит
UC1 + UC3 + UC2 best-effort. UC5 не входит. Под UC5
требуется:

- Multi-LLM execution-runner (parallel или sequential).
- Common research-doc-template (которого у нас нет в
  formalised виде, хотя `knowledge/research/` имеет
  conventions через `knowledge/README.md`).
- Comparison-chart-generator (новый template-tool).

Все три — v0.2+ работа.

**Action:** ADR-1 §Out-of-scope amendment добавляет UC5
явно, чтобы будущие сессии не должны угадывать его статус.

### 8.2 ADR-2 vs MCP ecosystem assumption

Three sources independently call MCP industry standard, но
провайдеры в нашем ADR-2 (Qwen, Kimi, GLM, Nemotron) —
**не Anthropic ecosystem**. MCP-shape компатибельность
здесь означает не «integrate с Claude-Desktop», а «keep
the door open». Если в v0.2 lead решит, что MCP-distrib
не нужен, мы потеряем 0 (because amendment — convention,
не implementation).

### 8.3 ADR-6 vs goclaw 5-layer permission

Goclaw делит security на 5 слоёв (input-validation / auth
/ role-permission / rate-limit / output-sanitization).
ADR-6 covers только path-permission (input + output). Не
покрыто:

- Input-validation (JSON-schema на tool-input'ы) — input
  для R-1.
- Auth (для single-user N/A) — Skip.
- Rate-limit (per-tool, per-LLM) — input для R-1.
- Output-sanitization (PII redaction в audit-log) —
  partial: ADR-6 audit-log пишет path/result, не делает
  redaction. Future improvement.

**Action:** Не amendment ADR-6; зафиксируем гap'ы как
input для R-1.

### 8.4 ACI two-stage read vs ампкод single-stage

Ампкод (cross-reference §3.1 ingredients) явно use'ает
single-stage `read_file(path)`. Ampcode-LLM (Claude 3.7)
обрабатывает 200K-context, full-file-read обычно работает.

Mid-tier OSS Coder (Nemotron / Qwen 27B) имеют 32K-128K
контекст; full-file-read 50KB markdown-файл — **это
50K токенов**, фактически весь окно. Single-stage не
масштабируется на наш UC3 corpus (notes/inbox/ может
содержать 100KB+ файлы).

**Open question для R-1:** какой default — single-stage
для small или two-stage с обязательным search→read? R-3
фикстура по 5-10 правок на каждой модели должна включить
один сценарий с large file (~50KB), чтобы понять размер
gap'а.

### 8.5 Hooks vs straight tool-dispatcher

Если R-1 описывает hook-pipeline, добавляется complexity
~100-200 строк Python кода (hook-registry, ordered
execution, error-propagation). Ампкод — без hooks, прост.

**Trade-off:**

- Hook-system: clean separation of concerns, easy add
  new hook, audit-log/sandbox/HITL живут отдельно.
- No-hook (straight): меньше кода, дублирование
  (sandbox-check + audit-log в каждой tool-фунции).

Мой совет для R-1: **mini-hook-system** (только pre-tool +
post-tool), без pre-run / post-run / on-event в v0.1.
Минимум boilerplate, max-выгода (ADR-6 + audit-log
естественно ложатся). Pre-run / post-run / on-event —
defer to v0.2 reflection-ADR.

### 8.6 Chunk schema vs ACI tool surface — full integration

PR #3 amendment ADR-4/5 уже добавил byte/line offsets к
chunks. ACI tool-сигнатура `repo.read(path, start_line,
end_line)` теперь — простая выборка из chunk-store по
path + line-range фильтру.

**Эту инфраструктурную совместимость стоит зафиксировать
явно** в R-1 ADR (when written) — что tool-implementation
**не** читает файл-fs напрямую, а **обращается к chunk-
store + post-fetch fs-read для byte_start/end window'a**.
Это даёт consistent results vs ad-hoc fs.read и автоматически
inherit-ит sandbox-policy (chunk-store не индексирует
запрещённые pаths).

---

## §9. Сводка действий по этому PR

Этот PR содержит:

1. **NEW** `knowledge/research/semi-autonomous-agents-cross-reference-2026-05.md`
   (этот файл) — критический разбор трёх источников.
2. **AMEND** `knowledge/adr/ADR-2-llm-tiering.md` — §Amendment
   2026-05-01: MCP forward-compat (JSON-RPC tool-shape
   convention).
3. **AMEND** `knowledge/adr/ADR-1-v01-use-case-scope.md` —
   §Amendment 2026-05-01: UC5 в `Concrete v0.1 deferred list`.
4. **AMEND** `knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md`
   §11 — пометить Q-1 и Q-2 как `superseded` с явным
   reasoning'ом.
5. **UPDATE** `knowledge/llms.txt` — новая research-нота под
   `## Research`.

NOT в этом PR:

- **HANDOFF.md** — отдельный PR после review этого (по
  user-выбору Question 4 «safer»).
- **Agent Knowledge note** — обновится после отдельного PR.

---

## §10. Recommendations follow-up

### 10.1 In-scope этой сессии

- [x] Research note (этот файл).
- [x] ADR-2 §Amendment 2026-05-01 — MCP forward-compat.
- [x] ADR-1 §Amendment 2026-05-01 — UC5 deferred.
- [x] Cross-reference §11 supersession marks Q-1, Q-2.
- [x] `knowledge/llms.txt` updated.

### 10.2 Next session или future PR

- [ ] Update `HANDOFF.md` + Agent Knowledge note after
      this PR review (separate PR per user choice).
- [ ] R-1 inner-loop ADR (now будущий ADR-7): должен
      учесть input этой ноты (§7.1, §7.3, §8.4, §8.5,
      §8.6).
- [ ] Glossary (R-8, cross-reference Q-8): добавить термины
      MCP / Hook / ACI / Reflexion / Self-evolving (§7.8).
- [ ] R-3 фикстура с large-file scenario (§8.4) — уточнить
      test-cases.
- [ ] UC5 follow-up ADR (когда v0.2 активен): describe
      multi-LLM eval-harness shape (§6.7).

### 10.3 Permanently rejected

- Python+Go hybrid (§3.4-а).
- 8-Stage Pipeline (§4.4-а).
- Agent Teams / inter-agent delegation (§4.4-б).
- Multi-tenant / RBAC / 7 channels (§4.4-в, §4.4-г).
- Self-evolving auto-adapt в v0.1 (§4.4-д).
- 4-Mode Prompt System (§6.5).
- SOUL.md / RULES.md decomposition (§2.4-а, §2.4-б).
- Generic OAuth 2.1 для local single-user (§2.2).

---

## §11. Что эта нота НЕ покрывает

- Sub-tier evaluation Anthropic vs OpenRouter vs vLLM по
  каждой model-slug (это ADR-2 §References + ongoing
  `claims_requiring_verification`).
- Имплементация R-1 inner-loop ADR (это отдельная сессия).
- Concrete benchmarks SWE-bench / WebArena / BrowseComp
  (вторичные цифры процитированы из источников; primary-
  source verification — отдельная задача).
- Multi-LLM UC5 detailed design (отдельный future ADR).
- Gardrail для cost-control (already noted в ADR-2
  follow-up work).
- Comparison goclaw vs OpenHands vs SWE-agent vs Aider
  (за scope этой ноты; semi-autonomous §1-§2 покрывает).
- Anthropic prompt-caching как cost-optimization (§4.4-е
  defer to v0.2).

---

## §12. Ссылки и источники

### 12.1 Внешние

- `01.05+deep-research-report.md` — user-attachment
  2026-05-01, 256 lines.
- `01.05+research_semi_autonomous_llm_agents.md` —
  user-attachment 2026-05-01, 255 lines.
- [https://github.com/nextlevelbuilder/goclaw](https://github.com/nextlevelbuilder/goclaw)
  — README на момент 2026-05-01, default branch `dev`,
  latest release `v3.10.0` (2026-04-20).
- Anthropic MCP spec (`https://modelcontextprotocol.io`) —
  reference for JSON-RPC shape.
- SWE-agent (Yang et al., 2024) — для ACI claim
  verification (deferred).

### 12.2 Внутренние

- [`ADR-1`](../adr/ADR-1-v01-use-case-scope.md) — v0.1 use-case scope.
- [`ADR-2`](../adr/ADR-2-llm-tiering.md) — LLM tiering + tool_protocol.
- [`ADR-3`](../adr/ADR-3-memory-architecture-variant.md) — memory architecture Variant A.
- [`ADR-4`](../adr/ADR-4-storage-backend.md) — SQLite FTS5 storage + chunks schema.
- [`ADR-5`](../adr/ADR-5-chunker-tool.md) — chunker (universal-ctags + markdown-it-py).
- [`ADR-6`](../adr/ADR-6-tool-sandbox-allow-list.md) — sandbox + path-allow-list.
- [`cross-reference-ampcode-sliders-to-adr-2026-04`](./cross-reference-ampcode-sliders-to-adr-2026-04.md) — предыдущая cross-reference от 2026-04-29.
- [`how-to-build-an-agent-ampcode-2026-04`](./how-to-build-an-agent-ampcode-2026-04.md) — ампкод research-note.
- [`sliders-structured-reasoning-2026-04`](./sliders-structured-reasoning-2026-04.md) — SLIDERS research-note.

---

## §13. Метаданные

**Sliding decision-windows:**

- 2026-04-27: ADR-1 v0.1 use-case scope accepted.
- 2026-04-28: ADR-2 LLM tiering accepted.
- 2026-04-28: ADR-3 memory variant A accepted.
- 2026-04-28: ADR-4 storage SQLite FTS5 accepted.
- 2026-04-28: ADR-5 chunker accepted.
- 2026-04-29: ADR-2 §Amendment (tool_protocol + no-Critic) accepted.
- 2026-04-29: ADR-4/5 §Amendment (chunks provenance) accepted.
- 2026-04-29: ADR-6 sandbox + path-allow-list accepted.
- 2026-04-29: cross-reference review notes published.
- 2026-05-01: this note written; ADR-2 §Amendment (MCP forward-compat) proposed in same PR; ADR-1 §Amendment (UC5 deferred) proposed.

**File length:** 1371 lines (deep-dive tier <2000, AGENTS.md
rule #3 satisfied).

**Author:** Devin session
[`2b3711d6`](https://app.devin.ai/sessions/2b3711d6b29c497fba602cb48f850e4d).
