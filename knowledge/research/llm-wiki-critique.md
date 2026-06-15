---
title: "Research — Критика Karpathy's LLM Wiki (core)"
source:
  - "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f"
  - "https://foundanand.medium.com/the-hidden-flaw-in-karpathys-llm-wiki-e3a86a94b459"
  - "https://dev.to/jgravelle/a-radical-diet-for-karpathys-token-eating-llm-wiki-59ng"
  - "https://ranjankumar.in/llm-wiki-synthesis-time-decision-rag-agentic-memory"
  - "https://github.com/ChavesLiu/second-brain-skill/blob/main/README.en.md"
  - "https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2"
  - "https://www.dougengelbart.org/content/view/110/460/"
compiled: "2026-04-24"
chain_of_custody: >
  For any specific claim (numbers, exact wording, benchmark results,
  directory layouts), cite the original URL listed in `source:`.
  Karpathy's gist and the critique posts are the authoritative texts —
  this note summarizes and critiques, it is not a source of truth for
  their specifics.
claims_requiring_verification:
  - "jDocMunch benchmark numbers (19.9× / 95%)"
  - "qmd feature list (BM25 + vector + LLM rerank, MCP server)"
  - "Karpathy-reported wiki scale (~100 articles, 400K words)"
---

# Research — Критика Karpathy's LLM Wiki (core)

> **Статус:** research note, 2026-04-24.
> **Scope:** разобрать критику [LLM Wiki-паттерна Карпатого][k-gist] (апрель
> 2026) и извлечь то, что применимо к *памяти/знанию* нашего собственного
> агента — не к персональной вики пользователя.
>
> **Заметка разбита на три файла** (см. правило ≤ 250 строк в
> [`knowledge/README.md`](../README.md)):
>
> 1. **Этот файл** — TL;DR, факты о самом gist'е, кросс-резка критики,
>    фактчек и открытые вопросы.
> 2. [`llm-wiki-critique-sources.md`](./llm-wiki-critique-sources.md) —
>    детальный разбор по шести источникам (Lahoti, Gravelle, Kumar,
>    ChavesLiu, rohitg00, Engelbart).
> 3. [`llm-wiki-critique-first-agent.md`](./llm-wiki-critique-first-agent.md)
>    — применимость к памяти *LLM-агента*, списки «берём / заглядываем /
>    не берём», интеграция с `agent-roles.md`, Engelbart как фрейм,
>    конкретные правки в репо, provenance-frontmatter template.

## Важное уточнение о preconditions

Пользователь в постановке задачи сообщил, что в репо «уже есть знание из
оригинального LLM Wiki gist». По факту в репо **нет прямых заимствований
из gist'а Карпатого** (`grep` по `knowledge/` + `docs/` по ключам
`karpathy|llm.?wiki|second.?brain|engelbart` даёт 0 совпадений
содержания). Поэтому документ **не обновляет существующее «знание из
gist»**, а **добавляет новое**: критический разбор паттерна + выводы,
точечно применимые к уже зафиксированным у нас вещам (трёхслойная
архитектура агента в [`knowledge/architecture.md`](../architecture.md)
и память проекта в [`knowledge/`](../README.md)).

## Связь с текущей фазой

Наш этап — «создать роли агента» ([`agent-roles.md`](./agent-roles.md)).
Этот документ не про роли; он про **субстрат**, на котором работают
роли — персистентное знание агента. Пересечение одно: роль *Critic*
получает дополнительный материал (см. [`-first-agent.md §7`][fa7]).

[k-gist]: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
[fa7]: ./llm-wiki-critique-first-agent.md#7-как-это-сочетается-с-agent-rolesmd

---

## 0. TL;DR

1. **Паттерн Карпатого — компиляция знаний** (raw-source → LLM-writer →
   wiki-pages → index.md) — *корректен на персональной шкале* (до ~100
   страниц, один ревьюер) и некорректен «в лоб» для команд и для **памяти
   автономного агента**. У всех трёх авторов-критиков один и тот же
   диагноз, просто под разными именами.
2. **Основной дефект — размытая chain of custody.** LLM-написанные
   summary индексируются наравне с первоисточниками; через серию
   перезаписей summary становится «источником», а оригинал перестаёт
   запрашиваться. Это *не* традиционная RAG-галлюцинация: системы,
   сверяющие wiki↔wiki, не видят рассинхрон wiki↔source. Пример с
   «2 %-дисконтом по контракту» (Lahoti / Kumar) иллюстративен, но
   структурно — это знакомый «эффект каскадного пересказа».
3. **Второй дефект — token-scaling.** `index.md` как основной
   навигационный объект ломается на ~50–100K токенов (это согласуется с
   известной деградацией long-context моделей — «lost in the middle», Liu
   et al. 2024). Решение: не **грузить** wiki, а **искать** по ней. Gist
   Карпатого это, кстати, прямо признаёт: «past a few hundred pages —
   возьми qmd» (гибридный BM25+vector поиск). Часть критики Gravelle — это
   straw-man поверх того, что и так сказано.
4. **Что хорошего в критике.** Она формализует три вещи, которых в
   исходном паттерне нет: (a) **синтез-тайм** как архитектурное решение
   (ingest-time vs query-time), (b) **стратификация корпуса** по
   стабильности, (c) **provenance-метаданные** (source, confidence,
   superseded_by). Это переводится в прямые рекомендации по
   `knowledge/`-слою нашего агента.
5. **Что сомнительно.** «Query-time всегда побеждает на большой шкале»
   (Lahoti) — абсолютизм; нужен гибрид. jDocMunch-бенчмарк (Gravelle) —
   корпоративный, сравнивается со **страшилкой** (загрузить весь wiki в
   контекст), которую Карпатый сам не рекомендует. Цифры 19.9× —
   маркетинговые. Экспоненциальная Ebbinghaus-decay (rohitg00) —
   метафора, а не измеренная механика для KB.
6. **Engelbart (1998, OHS Framework)** — не про вики и не про LLM, а про
   **open hyperdocument system** с типизированными объектами,
   адресуемыми на уровне абзаца/элемента, и про *bootstrapping* — тулы
   улучшают тулы. Для нас это философский якорь, не спецификация; его
   влияние ограничено [`-first-agent.md §8`][fa8].
7. **Что тащим в First-Agent** — см. [`-first-agent.md §6`][fa6]
   (приоритизированный список). Ключевые: provenance-frontmatter на
   заметках в `knowledge/`, явное разделение «stable vs volatile» в
   памяти агента, supersession вместо перезаписи, и *routing-раздел* в
   `AGENTS.md`.

[fa6]: ./llm-wiki-critique-first-agent.md#6-что-брать-что-не-брать
[fa8]: ./llm-wiki-critique-first-agent.md#8-engelbart-как-фрейм-не-спецификация

---

## 1. Что такое оригинальный LLM Wiki Карпатого (факты)

Нужно зафиксировать исходную спецификацию, иначе критику нельзя оценить.
Ниже — прямые цитаты из [gist'а][k-gist] без интерпретации.

**Суть паттерна (цитата):** «Instead of just retrieving from raw documents
at query time, the LLM **incrementally builds and maintains a persistent
wiki** — a structured, interlinked collection of markdown files that sits
between you and the raw sources.»

**Архитектура — три слоя:**

- `raw/` — immutable source documents, LLM только читает.
- `wiki/` — LLM-generated markdown, LLM *единолично* пишет и
  поддерживает.
- `schema` — файл типа `CLAUDE.md` / `AGENTS.md`: конвенции, формат
  страниц, workflow для ingest/query/lint.

**Операции:**

- **Ingest.** Новый source → LLM читает → пишет summary + обновляет
  10–15 связанных страниц → обновляет `index.md` и `log.md`.
- **Query.** Читать `index.md` → найти релевантные страницы →
  синтезировать ответ с цитатами. «Good answers can be filed back into the
  wiki as new pages» — явное разрешение петли **вики ест свои выходы**.
- **Lint.** Periodic health-check: противоречия, stale claims, orphan
  pages, недостающие cross-references.

**Навигация — два spec-файла:**

- `index.md` — content-oriented каталог, LLM обновляет на каждом ingest.
- `log.md` — chronological append-only: ingest/query/lint с префиксами.

**Масштаб по словам автора.** «Работает сюрприз-хорошо на moderate scale
(~100 sources, сотни страниц) и избавляет от embedding-based RAG
infrastructure». Явный потолок.

**Что он сам признаёт:**

- «At some point you may want to build small tools» → упоминает
  [qmd][qmd] (Tobi Lütke) — **гибридный BM25/vector search с LLM
  re-ranking** как MCP-сервер. То есть **автор изначально допускает
  переход в RAG** на больших шкалах.
- «This document is intentionally abstract. It describes the idea, not a
  specific implementation.» — явное self-caveat: это **идея-файл**, не
  prod-спецификация.
- Ссылка на Vannevar Bush's Memex (1945) как идейного предка.

[qmd]: https://github.com/tobi/qmd

Без этих двух признаний большая часть критики превращается в
«нашли у спецификации то, чего спецификация сама не утверждает».

---

## 2. Детальный разбор источников

Вынесен в отдельный файл: [`llm-wiki-critique-sources.md`](./llm-wiki-critique-sources.md).
Там по каждому из шести источников — тезис, иллюстрация, что сильно, что
слабо, что берём.

---

## 3. Кросс-резка: единая картина критики

У трёх критик (Lahoti, Gravelle, Kumar) один диагноз и три разных имени:

| Имя | Автор | О чём |
|---|---|---|
| Knowledge base poisoning | Lahoti | LLM-summary индексируется как источник; source drift |
| Token-bloat / index-bottleneck | Gravelle | Доступ «загрузи wiki» не масштабируется |
| Synthesis Horizon + chain-of-custody fracture | Kumar | Обобщение: где происходит синтез, и где теряется provenance |

Совпадение — не случайность. Все трое указывают на **одну и ту же пару
обязательств паттерна**:

1. **Provenance.** Каждый факт должен уметь показать свой источник на
   уровне конкретного span'а.
2. **Доступ по запросу, не по загрузке.** Размер артефакта не должен
   линейно влиять на стоимость одного вопроса.

Эти обязательства — *имплицитно* в gist'е Карпатого (он упоминает
source citations и рекомендует qmd для поиска), но не зафиксированы как
first-class обязанности схемы. В результате реализации паттерна в
большинстве случаев этих двух обязательств не соблюдают.

---

## 4. Фактчек

### 4.1. Что верно

- **Деградация long-context моделей реальна.** «Lost in the Middle» (Liu
  et al., 2024) подтверждает: recall теряется в середине длинного
  контекста. Это не «ничего не работает» — это «качество падает не
  линейно». Эффект хорошо воспроизводится.
- **Karpathy действительно описывает ~100 sources, 400K слов** — это
  цитируется Lahoti и Kumar, и подтверждается gist'ом (автор явно пишет
  «moderate scale, ~100 sources, hundreds of pages»).
- **qmd реально существует** ([github.com/tobi/qmd][qmd]), сделан
  Tobi Lütke, описан как hybrid BM25/vector search с LLM re-ranking и
  MCP-интерфейсом. Связка «wiki past 100 pages → qmd» — в самом gist'е.
- **Ingest реально трогает 10–15 страниц** — цитируется Kumar как
  утверждение Карпатого; в gist'е **буквально** стоит «a single source
  might touch 10-15 wiki pages».
- **Knowledge graph + typed relationships** — классика ИИ. Ссылки на
  Engelbart (typed links), DBpedia, WordNet, семантический веб. Engelbart
  как самый ранний источник — корректен.
- **Working/episodic/semantic/procedural memory** — стандартная
  таксономия из CogSci (Tulving, Atkinson-Shiffrin). Применение к LLM
  agent memory — стандартная практика (Generative Agents, MemGPT,
  Voyager).

### 4.2. Что сомнительно или overstated

- **«Query-time always wins at team scale» (Lahoti).** Overclaim.
  На практике архитектурная документация прекрасно компилируется один раз
  с ревью человеком; контракты — да, query-time. Kumer это и исправляет
  через стратификацию — но у самого Lahoti тезис звучит как absolutism.
- **jDocMunch-цифры 95% / 19.9× (Gravelle).** Нерепрезентативны. Baseline
  «загрузить весь wiki» — тот baseline, который Карпатый сам отговаривает.
  Правильный baseline был бы: «Карпатовский wiki + qmd поверх». По такому
  сравнению никаких 19.9× мы бы не увидели — оба подхода делают
  search-then-fetch, разница была бы в деталях реализации.
- **Ebbinghaus-decay для KB-фактов (rohitg00).** Метафора, не измерение.
  Применять как *эвристику* можно («decay = f(time, reinforcement)»), но
  не как «исторически валидированная экспонента».
- **«Shumailov model collapse → wiki drift» — расхожий, но неточный
  аналог.** Shumailov et al. (Nature 2024) о **training** на
  рекурсивно-генерируемых данных. В LLM Wiki нет дообучения — только
  retrieval. Структурная аналогия валидна (feedback loop ест свои
  выходы), но это не «тот же самый эффект».
- **«LLM Wiki — это современный Engelbart».** Верно лишь частично.
  Engelbart требовал типизации и fine-grained addressing, которых в
  исходном Wiki-паттерне нет. Критики, требующие типизированного графа
  (rohitg00) и routing (Kumar), на самом деле ближе к Engelbart'у, чем
  сам gist.

### 4.3. Чего критики не замечают

- **У паттерна есть важная честная оговорка «this is an idea file».**
  Никто из трёх критиков этого явно не цитирует. Часть критики ломится в
  открытую дверь.
- **Карпатый специально пишет «personal» во всех примерах.** Его кейсы —
  persistent **personal** knowledge base. Lahoti/Kumar честно расширяют на
  team, но их критика справедлива *к экстраполяции*, не к original
  claim'у.
- **Human-in-the-loop как часть дизайна.** В gist'е прямо: «I have the
  LLM agent open on one side and Obsidian open on the other. The LLM
  makes edits based on our conversation, and I browse the results in real
  time — following links, checking the graph view». Ревью не опциональное
  — оно часть паттерна. Критика «drift незаметен» относится к setup'ам,
  где это ревью выкинули.

---

## 10. Открытые вопросы

Чтобы не повторять паттерн «вики поглощает источники», фиксирую вопросы
*без* ответов:

1. **Где граница volatile / stable для нашего проекта?** Прямо сейчас:
   `knowledge/adr/` — stable; `knowledge/research/` — semi-stable
   (обновляется при significant findings); логи сессий пока нет. Нужен
   ли нам отдельный слой `knowledge/episodic/` или `knowledge/sessions/`
   для сырых session-digest'ов?
2. **Как решаем, что заметка устарела?** Сейчас — субъективно. Нужен ли
   явный цикл review (квартальный? per-module?) или триггер-based (когда
   ссылающаяся ADR меняется)?
3. **Где Critic (роль из `agent-roles.md`) пишет свои digest'ы?**
   Отдельный файл на сессию? Append к `log.md`? Решать при
   проектировании роли — сейчас просто регистрирую вопрос.
4. **Переход на qmd-like поиск — когда и на чём?** Не ранее первого
   модуля памяти. Триггер: README.md / index'ы перестают помещаться в
   контекст одной сессии.

---

## Sources

Критика и расширения:

- [s-lahoti]: Anand Lahoti. *The Hidden Flaw in Karpathy's LLM Wiki*.
  Medium, 2026-04 — [foundanand.medium.com][s-lahoti]
- [s-gravelle]: J. Gravelle. *A Radical Diet for Karpathy's Token-Eating
  LLM Wiki*. dev.to, 2026-04-12 — [dev.to][s-gravelle]
- [s-kumar]: Ranjan Kumar. *LLM Wiki Is Not a RAG Replacement — It's a
  Synthesis-Time Decision*. 2026-04-20 — [ranjankumar.in][s-kumar]
- [s-chaves]: ChavesLiu. *Second Brain Skill*. GitHub — [github.com/ChavesLiu][s-chaves]
- [s-rohit]: rohitg00. *LLM Wiki v2*. GitHub Gist (fork of karpathy/llm-wiki)
  — [gist.github.com/rohitg00][s-rohit]

Первоисточник:

- [k-gist]: Andrej Karpathy. *llm-wiki.md*. GitHub Gist, 2026-04-04 —
  [gist.github.com/karpathy][k-gist]

Исторический фрейм:

- [s-engelbart]: H. Lehtman, D. Engelbart, C. Engelbart. *Technology
  Template Project: OHS Framework*. Bootstrap Alliance, 1998 —
  [dougengelbart.org][s-engelbart]
- Vannevar Bush. *As We May Think*. The Atlantic, 1945.

Поддерживающая литература:

- [paper-lost-middle]: Liu et al. *Lost in the Middle: How Language
  Models Use Long Contexts*. TACL / arXiv 2307.03172, 2024.
- [p-park]: Park et al. *Generative Agents: Interactive Simulacra of
  Human Behavior*. arXiv 2304.03442, 2023.
- [p-memgpt]: Packer et al. *MemGPT: Towards LLMs as Operating Systems*.
  arXiv 2310.08560, 2023.
- [p-reflexion]: Shinn et al. *Reflexion: Language Agents with Verbal
  Reinforcement Learning*. arXiv 2303.11366, 2023.
- Tulving, E. *Episodic and Semantic Memory*. 1972 (таксономия working /
  episodic / semantic / procedural).
- Doyle, J. *A Truth Maintenance System*. AI 12(3), 1979 (супресессия и
  belief revision).
- Shumailov et al. *AI models collapse when trained on recursively
  generated data*. Nature, 2024 (training-side analog drift-эффекта;
  именно training, не retrieval).

Инструменты, упомянутые в критике:

- [qmd] (Tobi Lütke) — hybrid BM25/vector search + LLM re-ranking для
  markdown, как MCP.
- jDocMunch — sections-search MCP (vendor-self-benchmark; см.
  [`-sources.md`](./llm-wiki-critique-sources.md)).

[s-lahoti]: https://foundanand.medium.com/the-hidden-flaw-in-karpathys-llm-wiki-e3a86a94b459
[s-gravelle]: https://dev.to/jgravelle/a-radical-diet-for-karpathys-token-eating-llm-wiki-59ng
[s-kumar]: https://ranjankumar.in/llm-wiki-synthesis-time-decision-rag-agentic-memory
[s-chaves]: https://github.com/ChavesLiu/second-brain-skill/blob/main/README.en.md
[s-rohit]: https://gist.github.com/rohitg00/2067ab416f7bbe447c1977edaaa681e2
[s-engelbart]: https://www.dougengelbart.org/content/view/110/460/
