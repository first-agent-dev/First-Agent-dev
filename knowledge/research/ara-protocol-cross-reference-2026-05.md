---
title: "Cross-reference review — Ara protocol (arXiv:2604.24658) vs First-Agent ADR-1..6 + HANDOFF (2026-05-04)"
compiled: "2026-05-04"
source:
  - "https://arxiv.org/abs/2604.24658"
  - "https://arxiv.org/html/2604.24658v2"
  - "https://arxiv.org/pdf/2604.24658v2"
  - "https://github.com/Orchestra-Research/Agent-Native-Research-Artifact"
  - "knowledge/adr/ADR-1-v01-use-case-scope.md"
  - "knowledge/adr/ADR-2-llm-tiering.md"
  - "knowledge/adr/ADR-3-memory-architecture-variant.md"
  - "knowledge/adr/ADR-4-storage-backend.md"
  - "knowledge/adr/ADR-5-chunker-tool.md"
  - "knowledge/adr/ADR-6-tool-sandbox-allow-list.md"
  - "knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md"
  - "knowledge/research/cutting-edge-agent-research-radar-2026-05.md"
  - "knowledge/research/agentic-memory-supplement.md"
  - "knowledge/research/memory-architecture-design-2026-04-26.md"
  - "knowledge/research/sliders-structured-reasoning-2026-04.md"
  - "HANDOFF.md"
  - "AGENTS.md"
chain_of_custody: >
  Цифры и формулировки из Ara paper цитируются по HTML-версии arXiv:2604.24658v2
  (rendered text сохранён локально в сессии Devin как `/tmp/paper.txt`,
  размер 224 657 символов). Цитаты приведены в английских блоках с
  привязкой к секции (§N или Appendix N.M). Mapping на ADR-1..6 и HANDOFF.md
  выполнен по текущему `main` фрика (`GrasshopperBoy/First-Agent-fork`),
  состояние на 2026-05-03 (HANDOFF.md last update). Ни один из четырёх
  layers Ara не реализован на момент написания ноты; все рекомендации —
  input для будущих ADR/PR, не сами решения.
status: research
tier: stable
supersedes: none
extends: []
related:
  - knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md
  - knowledge/research/cutting-edge-agent-research-radar-2026-05.md
  - knowledge/research/agentic-memory-supplement.md
  - knowledge/research/memory-architecture-design-2026-04-26.md
  - knowledge/research/sliders-structured-reasoning-2026-04.md
links:
  - "../adr/ADR-1-v01-use-case-scope.md"
  - "../adr/ADR-2-llm-tiering.md"
  - "../adr/ADR-3-memory-architecture-variant.md"
  - "../adr/ADR-4-storage-backend.md"
  - "../adr/ADR-5-chunker-tool.md"
  - "../adr/ADR-6-tool-sandbox-allow-list.md"
  - "./cross-reference-ampcode-sliders-to-adr-2026-04.md"
  - "./cutting-edge-agent-research-radar-2026-05.md"
mentions:
  - "Ara protocol"
  - "Agent-Native Research Artifact"
  - "Live Research Manager"
  - "Ara Compiler"
  - "ARA Seal"
  - "Orchestra Research"
  - "PaperBench"
  - "RE-Bench"
  - "https://arxiv.org/abs/2604.24658"
confidence: inferred
claims_requiring_verification:
  - "Ara paper (arXiv:2604.24658v2) — preprint от Orchestra Research, май 2026.
    Цифры benchmark-эффекта (QA 72.4 → 93.7 %; reproduction 57.4 → 64.4 %)
    взяты из abstract и §7. Не воспроизведены независимо в этой ноте."
  - "Цифра «failed runs составляют 90.2 % $ cost» из §1 (Appendix E.3) —
    METR eval-analysis-public dataset (Wijk et al., 2025). На корпусе First-Agent
    эта пропорция не измерена."
  - "Сопоставление «PAPER.md ≈ knowledge/llms.txt» — структурное, не функциональное.
    PAPER.md в Ara — это per-artifact manifest, llms.txt — repo-level URL index.
    Это две роли, частично перекрывающиеся."
  - "Все architectural recommendations §9 — input для будущих ADR (в первую
    очередь ADR-7 inner-loop), не сами ADR. Решения принимает project lead."
  - "Утверждения «принятие 1:1 layout Ara дорогое» и «branch DAG — cheap»
    не подкреплены измерениями LoC; опираются на контекст Phase S → M."
---

# Cross-reference review — Ara protocol vs First-Agent ADR-1..6

> **Статус:** research note, 2026-05-04.
>
> **Что внутри:** систематический проход по статье «The Last Human-Written
> Paper: Agent-Native Research Artifacts» (arXiv:2604.24658v2,
> Orchestra Research, май 2026) против шести принятых ADR и
> текущего HANDOFF.md, с явной выпиской того, **где Ara усиливает
> существующую архитектуру First-Agent**, **где обнажает пробелы**
> в способности агентов продолжать работу через сессии, и **где
> прямое заимствование некорректно** (research-paper artefact ≠
> coding-agent project). Goal — improve agent continuity на этом
> репо без переключения парадигмы.
>
> **Эта нота не предлагает менять ADR-1..6.** Она готовит структурированный
> input — пронумерованные рекомендации (§9) и открытые вопросы
> (§10) под решение лида. Сами правки ADR (если они нужны) —
> отдельные PR после согласования.
>
> **Адресовано:** будущему Architect/Coder-агенту FA, реквестеру и
> человеку-ревьюеру PR. Форма — нумерованные блоки, явные таблицы
> mapping'a, явные TL;DR на каждом разделе.

---

## 0. TL;DR — пять выводов на одной странице

1. **Ara и First-Agent независимо сошлись на одном принципе** —
   knowledge over narrative, filesystem-canonical Markdown как
   primary memory, progressive disclosure, layered access. Это не
   совпадение: оба проекта оптимизируют под LLM-агента как
   читателя. ADR-3 (Variant A "Mechanical Wiki") совместим с Ara
   философски; ничего отменять не нужно.
2. **Самый сильный gap для goal'а user'а («continuity между
   сессиями») — отсутствие explicit branching exploration graph.**
   First-Agent сейчас хранит решения как линейный список ADR-1..6
   с amendments и плоский набор research-нот. Ara §2.2 показывает,
   что для цельного восстановления research trajectory нужен
   `/trace/exploration_tree.yaml` с типизированными узлами
   (`question`, `decision`, `experiment`, `dead_end`, `pivot`) и
   `also_depends_on` рёбрами. Аналог в FA — cheap, additive ход,
   не отменяет ни одной ADR.
3. **Live Research Manager (Ara §3) — это именно то, чего не хватает
   HANDOFF.md.** HANDOFF обновляется retrospectively вручную (в
   среднем раз в несколько PR); Ara LRM строится как **agent skill**,
   которая run-ит трёхстадийный pipeline (Context Harvester → Event
   Router → Maturity Tracker) **на границе сессии**, превращая
   conversational state в типизированные events с provenance
   (`user` / `ai-suggested` / `ai-executed` / `user-revised`). Mapping
   на Agent Knowledge note + AI-Session trailer прозрачен, но требует
   формализации. Это — кандидат на ADR-8 (после ADR-7 inner-loop).
4. **Прямое заимствование 1:1 layout Ara (`/logic/`, `/src/`, `/trace/`,
   `/evidence/` на уровне репо) — некорректно для First-Agent.** Ara
   спроектирован для CS research paper artefact'а. First-Agent — это
   coding-agent framework: `experiment.md` и `evidence/` плохо
   маппятся на «следующий feature module». Ara надо адаптировать на
   уровне **knowledge/** (как структура research/ADR/HANDOFF), не
   репо-level. См. §7.
5. **ARA Seal (Ara §5.2) — three-stage review pipeline (conceptual /
   empirical / human) — частично уже реализован** через Agent Review +
   AGENTS.md PR Checklist + CI lint. Не хватает формального **Level 1
   structural integrity check** для knowledge/research/* (валидация
   frontmatter v1/v2, наличия chain_of_custody, проверка что все
   ссылки в `links:` существуют). Это — pre-commit hook, не ADR. См.
   §9 R-3.

Подробности — ниже. Чёткое разделение: §2 — пересказ Ara protocol для
агентов (чтобы не нужно было каждый раз читать paper заново); §3–§6 — пар-
ный mapping Ara four layers + LRM + Compiler + Seal на текущие artefact'ы
First-Agent; §7 — что НЕ применимо и почему; §8 — риски; §9 — пронуме-
рованные рекомендации (R-1..R-10); §10 — открытые вопросы (Q-1..Q-11)
под решение лида; §11 — список файлов, использованных в этой сессии;
§12 — что эта нота **намеренно не покрывает**.

---

## 1. Scope, метод

**Coverage.** Полный текст Ara paper'а (HTML v2, ~225 KB plain text после
strip) с акцентом на §1–6 (мотивация, protocol, LRM, Compiler, Seal,
research network), §10 (Limitations), §11 (Conclusion) и
Appendix A (Taxonomy of Reproduction-Critical Information; ARA by
example). Все шесть принятых ADR целиком; HANDOFF.md (2026-05-03);
AGENTS.md; project-overview.md; четыре связанных research-ноты.

**Не покрыто.** Appendix B–G (Compiler skill spec, LRM details, test
corpus, evaluation tables, extension case studies) — прочитан
selectively по нужде. Сам код Ara repo
(`github.com/Orchestra-Research/Agent-Native-Research-Artifact`) не
клонировался построчно — оценка идёт по paper'у как primary source.

**Метод.** Для каждого блока Ara (§2 Protocol, §3 LRM, §4 Compiler,
§5 Seal, §6 Research Network) задаются три вопроса: **(1)** есть ли
аналог в текущем First-Agent? **(2)** усиливает ли Ara существующее
решение, или обнажает пробел? **(3)** менять/добавлять до Phase M /
после ADR-7 / vXX deferred? При ответе «до ADR-7 / параллельно» —
рекомендация в §9 с cost-tag (cheap | medium | expensive).

**Ограничения.**

- Single-pass, без peer-review от второго LLM.
- Цифры из Ara abstract (QA 72.4 → 93.7 %, reproduction 57.4 → 64.4 %,
  90.2 % $ cost in failed runs) **не воспроизведены** в этой ноте.
- Сравнение с другими agent-paper'ами (например, `agent-roles.md`,
  `agentic-memory-supplement.md` Mem0) — не построчное; цитируется по
  заголовкам.
- На момент написания ноты `src/fa/` содержит только smoke CLI
  entrypoint. Все «как это интегрировать в код» — гипотетические.

---

## 2. Ara protocol — короткий пересказ для агентов

Цель параграфа — сэкономить контекст следующим сессиям: после этого
блока Ara можно цитировать без повторного fetch'а paper'а.

### 2.1 Мотивация (§1 paper)

Авторы вводят два structural cost'а publishing'а:

- **Storytelling Tax** — нарративная компиляция research'а удаляет
  branching trajectory: failed experiments, отвергнутые гипотезы,
  abandoned approaches. Цитата:

  > Failed runs account for 90.2 % of total dollar cost (and 59.2 %
  > of tokens), with a median failed-to-success token ratio of 113 ×.
  > (paper §1, ссылающийся на Appendix E.3 над METR eval-analysis-public,
  > 24 008 agent runs / 21 frontier models / RE-Bench)

- **Engineering Tax** — gap между «достаточно для review'а» (proza)
  и «достаточно для воспроизведения агентом» (specification).

Output — Ara protocol: четыре file-system layers + три ecosystem
mechanism'а (LRM / Compiler / Seal).

### 2.2 Четыре layers (§2.2)

Корневой манифест PAPER.md, ~500 токенов, чтобы агент мог сделать
triage. Дальше:

- **`/logic/` (Cognitive Layer)** — «**why** does this work».
  Файлы:
  - `problem.md` — gap, key insight.
  - `solution/` — architecture, algorithm, **convergence-critical
    heuristics** (отдельный класс, не «детали»).
  - `claims.md` — falsifiable assertions с explicit proof pointers.
  - `experiments.md` — verification plan.
  - `related_work.md` — **typed dependencies** (imports, bounds,
    baselines) вместо passive citations.

- **`/src/` (Physical Layer)** — «**how** is it implemented».
  Два режима:
  - **kernel mode** — только core modules с typed I/O (для
    algorithmic contributions, 1–2 порядка меньше full repo).
  - **repository mode** — full implementation плюс `index.md`,
    маппящий source files на Ara components (для systemic
    contributions: CUDA, distributed, systems).
  Плюс `configs/` (annotated hyperparams, search ranges) и
  `environment.md` (deps, hardware, seeds).

- **`/trace/` (Exploration Graph)** — «**what was tried**».
  - `exploration_tree.yaml` — research DAG как nested YAML с пятью
    типами узлов:
    - `question` — open research question;
    - `decision` — choice with alternatives + evidence;
    - `experiment` — metrics + claim linkage;
    - `dead_end` — hypothesis, failure mode, lesson;
    - `pivot` — trigger + rationale (when an earlier choice is
      invalidated).
    Nesting кодирует parent → child рёбра; field
    `also_depends_on` — convergence point.
  - `sessions/` — per-session records.

- **`/evidence/` (Evidence Layer)** — «**what are the numbers**».
  - `results/` — machine-readable metric tables.
  - `logs/` — training curves, resource usage.
  - **Withholding-as-access-control:** агент-верификатор может
    получить `/logic/` + `/src/` без `/evidence/`, чтобы предотвратить
    fabrication через копирование expected values.

**Forensic bindings** — cross-layer ссылки claims → experiments →
evidence → src. Пример пути доказательства: `claims.md` → `experiments.md`
→ `/evidence/` → конкретная строка raw output.

**Sufficiency criterion:** Ara «sufficient», когда достаточно
способный coding-агент может zero-shot воспроизвести core claim
**только из artefact'а**, без external context. Это
**capability-relative** — Ara, написанный сегодня, остаётся valid с
ростом моделей.

### 2.3 Live Research Manager (§3)

Skill (natural-language spec), которая:

- **silent, framework-independent** (P1) — composes file
  read/write/edit/shell без custom SDK, runs as background process;
- **faithful epistemic provenance** (P2) — каждый event тагается
  `user` / `ai-suggested` / `ai-executed` / `user-revised`, и
  raw observations stage-ятся в `/staging/` пока не накопились
  evidence (progressive crystallization);
- **comprehensive trajectory capture** (P3) — branching process
  (включая dead ends + pivots) пишется с cross-layer bindings
  на момент capture'а, версионируется (git), retroactive revisions
  — first-class, не destructive.

Pipeline на границе сессии (Figure 6 в paper):

1. **Context Harvester** — scans conversational history, tool
   outputs, experiment results, code diffs.
2. **Event Router** — классифицирует event в один из семи типов:

   | Event Type   | Structured Payload                     |
   |--------------|----------------------------------------|
   | `decision`   | choice, alternatives, evidence         |
   | `claim`      | statement, falsification criteria      |
   | `experiment` | metrics, claim linkage                 |
   | `heuristic`  | trick, sensitivity, bounds             |
   | `dead_end`   | hypothesis, failure mode, lesson       |
   | `pivot`      | trigger, rationale                     |
   | `observation`| raw finding, awaiting classification   |

   Тагается provenance, payload приведён к **factual-density**
   (telegraphic, quantitative — без хедж-проз).

3. **Maturity Tracker** — promote-ит staged observations в формальные
   entries по closure signals: topic abandonment, explicit researcher
   affirmation, empirical resolution, artifact-level commitment
   (Appendix C.2).

**Two timescales:**

- **Continuous** — на каждом session boundary trace events appended.
- **Periodic** — на milestone'е (hypothesis confirmed/refuted, prototype
  ready, design choice finalized) Maturity Tracker crystallizes.

**Cross-session continuity** (§3.2 last paragraph): manager
**stateless**, артефакт несёт память. На session-close manager пишет
короткий session record (events captured, claims touched, open
threads) и appendнит в session index. Следующая сессия читает индекс
+ current claims + staged observations и **поднимает только
relevant pieces** к текущему task'у — не «формальный briefing,
который никто не просил».

### 2.4 Ara Compiler (§4)

Many-to-one: PDF + repo + rubric + trajectory logs → один Ara,
conform §2. Два принципа:

- **Universal input, canonical output** — graceful degradation:
  PDF alone → valid artefact с stub-уровнем `/src/`; richer inputs
  populate progressively richer layers.
- **High-fidelity preservation** — каждое числовое значение,
  hyperparameter, architectural detail и negative finding из
  sources **должно появиться в artefact'е**; missing PDF-accessible
  info = compilation failure.
- **Knowledge lineage, not flat extraction** — forensic bindings
  recovery (claim ↔ experiment ↔ evidence ↔ code) — это
  **core compilation problem**, не просто populating layers.

Implementation — **agent skill** (Figure 7, `~482` lines):

1. Top-down generation (manifest → logic → src → evidence).
2. Iterative refinement через ARA Seal Level 1 validation feedback
   (2–3× iteration).
3. Source-aware enrichment.

### 2.5 Verification & Review (§5)

**ARA Seal** — machine-verifiable research credentials, three levels:

- **Level 1 — structural integrity.** Schema validation (manifest,
  layer files, frontmatter), forensic-binding link existence.
  Runs in seconds, in-loop при compilation.
- **Level 2 — Rigor Auditor.** Mutation benchmark: deliberately
  inject errors (orphan claims, fake numbers) и проверяется, ловит
  ли auditor. Paper'е reported: high recall на substantive injections,
  blind spot на orphans, две LLM-as-judge pathologies.
- **Level 3 — execution reproducibility.** Полный run кода на
  чистом окружении.

**Three-stage review pipeline** (§5.3):

- Stage 1: Conceptual (minutes) — Level 1 + simple LLM-judge.
- Stage 2: Empirical (hours–days) — Level 2 + Level 3.
- Stage 3: Human (days–weeks) — significance, novelty, taste.

P1 design principle: **automate the mechanical; reserve humans for
judgment**.

### 2.6 Цифры

- PaperBench QA: **72.4 % → 93.7 %** (Ara vs paper baseline, §7.2).
- RE-Bench reproduction: **57.4 % → 64.4 %** (§7.3).
- Caveat (§7.4): на open-ended extension preserved failure traces
  ускоряют слабые модели, но **могут constraining capable agent от
  «stepping outside the prior-run box»**. Это нетривиальная
  оговорка — failure preservation не всегда монотонно полезен.

---

## 3. Mapping: Ara four layers ↔ artefacts First-Agent

| Ara layer       | Цель                              | Аналог в FA сейчас                                                                                | Gap                                                                          |
|-----------------|-----------------------------------|---------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------|
| `/logic/`       | Why / claims / experiments       | ADR-1..6 (decisions); knowledge/project-overview.md (problem); knowledge/research/* (insights)   | Нет explicit `claims.md` с falsifiability criteria; нет `experiments.md`     |
| `/src/`         | How (kernel vs repo mode)        | `src/fa/` (только CLI smoke); `pyproject.toml` (env)                                              | Phase M только начнётся; конструктивно совпадает «kernel mode by default»    |
| `/trace/`       | What was tried (DAG)             | knowledge/research/*.md (плоский список); ADR amendments (linear)                                | **Нет branching DAG** с типизированными узлами; failure preservation ad-hoc  |
| `/evidence/`    | Raw outputs grounding claims     | (нет) — agent runs не сохраняются                                                                 | UC1 acceptance test'ов нет, eval traces нет                                  |
| PAPER.md        | ~500-tok manifest, layer index   | `knowledge/llms.txt`                                                                              | llms.txt — repo-level; нет per-research-note manifest'а                      |

### 3.1 `/logic/` ↔ ADR + project-overview + research

ADR-1..6 уже отвечают «why», но не как `claims.md` с
falsifiability. Цитата из ADR-3 §Decision:

> **Negative:** UC1 cross-session memory ("what did I think about
> this function 2 weeks ago") relies on session archive grep, not a
> queryable volatile store. Acceptable for v0.1; revisit in v0.2.

Это — **embedded claim** с implicit falsification criterion («acceptable
for v0.1»), но без формального типа. Ara требовал бы:

```yaml
# claims.md style
id: C1
statement: "v0.1 cross-session memory by session-archive grep is acceptable for UC1."
falsification: "If on the 5-fixture-session manual eval, more than 2/5 sessions surface 'I had to grep manually because grep returned > 5 results' — claim is falsified."
proof_pointers:
  - experiments.md#E1
  - evidence/results/uc1-eval-2026-Q3.md
```

ADR-3 этого формализма не имеет — **gap**, но не критичный для v0.1.
См. §9 R-2 (cheap, optional).

### 3.2 `/src/` ↔ src/fa/

Структурно совпадает «kernel mode» Ara: ADR-3 фиксирует «smallest LoC +
smallest dependency surface» для v0.1. Когда chunker будет реализован
(`src/fa/chunker/`), он естественно ляжет как kernel module с typed
I/O (`Chunk` dataclass, `Chunker` Protocol — ADR-5). Ara `index.md` в
`/src/` (маппинг source files на Ara components) на масштабе FA пока
overkill, но если v0.2 добавит несколько модулей, можно будет
рассмотреть.

### 3.3 `/trace/` ↔ research/ + ADR amendments — **главный gap**

Текущая структура хранит:

- ADR-1..6 — линейный список с amendments (ADR-2 имеет три
  amendments на одну ADR; ADR-3..5 имеют один-два каждая).
- knowledge/research/* — плоский набор `.md` файлов, связанных
  через `related:`/`links:` frontmatter.
- HANDOFF.md «Next steps (intended order)» — нумерованный список
  без typed links.

Ara показывает: чтобы агент мог продолжить работу с того же места,
ему нужен **branching DAG** с типами узлов. Конкретно для FA это
означает:

```yaml
# гипотетический knowledge/trace/exploration_tree.yaml (НЕ предложение
# создать прямо сейчас — иллюстрация формы)
- id: Q1
  type: question
  text: "Какая memory architecture для v0.1?"
  date: 2026-04-26
  closed_by: ADR-3
  alternatives:
    - id: A
      type: decision
      text: "Mechanical Wiki (Variant A)"
      chosen: true
      evidence: research/memory-architecture-design-2026-04-26.md
    - id: B
      type: dead_end
      text: "Hybrid Brain (Variant B)"
      reason: "UC4 deferred → main beneficiary missing"
      lesson: "B becomes attractive only if multi-user namespace appears"
    - id: C
      type: dead_end
      text: "Layered KG (Variant C)"
      reason: "user labelled overkill; cold-start empty"
      lesson: "graph density is necessary precondition"
```

Текущий ADR-3 cовершенно содержит ту же информацию (Option A / Option B /
Option C), но в **prose**, не в `dead_end` форме с `lesson:` полем.
Сейчас, чтобы агент в новой сессии понял, **почему** B/C отвергнуты —
он должен прочитать весь ADR-3 целиком. Если бы dead_end узлы были
machine-traversable, то LRM-аналог мог бы injectнуть в context только
relevant lessons.

Это — **самый сильный аргумент Ara для goal'а user'а**: «improve
ability of agents to continue work on this project». См. §9 R-1 (medium-cost).

### 3.4 `/evidence/` ↔ (отсутствует)

В FA нет места, где сохраняются raw outputs agent runs (manual eval
fixtures, LLM-as-judge runs). project-overview.md §3 говорит о
«5 fixture sessions», но fixtures сами по себе ещё нет. Ara `/evidence/`
дисциплина — **claim must point to results/<file>** — это та же
дисциплина, что AGENTS.md «Chain-of-custody rule», но материализованная в
file-system layer.

Для FA это станет relevant **когда первый module landed** (chunker), и
понадобятся sample-tests из chunker-design.md §8. См. §9 R-7 (defer).

### 3.5 PAPER.md ↔ knowledge/llms.txt

Аналогия частичная:

- `llms.txt` — repo-level URL index (один на репо).
- PAPER.md — per-artifact manifest (один на Ara).

Сейчас FA — это **один artefact** (сам project), поэтому llms.txt
выполняет обе роли. Если FA когда-нибудь станет hub-ом для нескольких
self-contained sub-projects, ситуация поменяется. Pre-v0.2 — изменений
не нужно.

---

## 4. Live Research Manager ↔ HANDOFF.md + Agent Knowledge note

Главный фокус для goal'а user'а («continuity между сессиями») — этот
параграф.

### 4.1 Текущая практика FA

Cross-session continuity сейчас обеспечивают:

- **HANDOFF.md** — manual Markdown, обновляется в среднем раз на 2–3 PR.
- **Agent Knowledge note** «First-Agent — current state pointer» (mirror
  of HANDOFF.md, canonical when they disagree).
- **AI-Session trailer** в commit messages (`AI-Session: <session-id>`),
  pattern lifted from `codedna` (см. agentic-memory-supplement.md §3).
- **AGENTS.md PR Checklist** rule #7 — «llms.txt reflects reality».

### 4.2 Что Ara LRM делает иначе

| Аспект                    | HANDOFF.md (FA сейчас)                              | Ara LRM                                                 |
|---------------------------|------------------------------------------------------|---------------------------------------------------------|
| Когда обновляется          | Manually, ad-hoc, batch (раз на N PR)                | На каждой session boundary (automatic)                  |
| Кто пишет                  | Last agent в сессии (один writer per merge)          | Background skill в любой кодинг-агент                   |
| Format                     | Free-form Markdown                                   | Typed events (7 типов), structured payloads             |
| Provenance                 | implicit (commit author, AI-Session trailer)         | explicit per-event (`user` / `ai-suggested` / ...)      |
| Granularity                | sections (Stage / ADRs / Open PRs / Next steps)      | per-event, per-claim                                    |
| Crystallization            | manual section rewrites                              | `staging/` → maturity tracker → formal entries          |
| Cross-session resumption   | агент читает весь HANDOFF.md (~7 KB)                 | агент читает только relevant pieces для current task    |

### 4.3 Где Ara улучшает текущую практику

Три наиболее практических элемента, переносимые в FA:

1. **Provenance tags на per-event уровне.** Вместо «AI-Session trailer
   per commit» (который слишком coarse — целый PR — и слишком тяжёлый —
   нужен git lookup) добавить frontmatter-поле в research-ноты:

   ```yaml
   provenance:
     - event: "ADR-1 amendment 2026-05-01: UC5 deferred"
       origin: user-revised
       session: 2b3711d6b29c497fba602cb48f850e4d
   ```

   Это additive, не ломает существующие ноты.

2. **Closure signals → автоматическое promote из staging.** Сейчас
   research-нота создаётся целиком и сразу мерджится. Ara показывает,
   что промежуточный stage `staging/` (или `inbox/` per
   project-overview §4) полезен: туда складываются raw observations,
   а promote в формальную ноту — по closure signal'у. **FA уже имеет
   аналог**: project-overview §4 описывает `notes/inbox/` как watched
   directory + `fa ingest`. Это staging. Что не хватает — **maturity
   tracker**: правила, когда `notes/inbox/foo.md` становится
   `knowledge/research/foo.md`. Текущая практика — это manual decision
   проектного лида; Ara предлагает закодифицировать closure signals.

3. **Stateless manager + artifact-as-memory.** Это уже **в** FA —
   HANDOFF.md и Devin note именно так и работают. Ara просто даёт
   формальный ярлык этому паттерну: artifact carries memory, manager
   is stateless. Полезный концептуальный clarification для будущих
   ADR amendments.

### 4.4 Где Ara НЕ переносится 1:1

- **Семь event types — overkill для FA сейчас.** v0.1 использовал бы
  максимум три (`decision`, `dead_end`, `pivot`) — остальные четыре
  (`claim`, `experiment`, `heuristic`, `observation`) релевантны
  только когда есть `/evidence/` layer.
- **«Background skill, runs at session boundary» в Devin** требует
  оркестрации (skill registration, session lifecycle hooks) — это
  ADR-7 уровня плюс ADR-8. Ad-hoc реализация в form'е MCP-skill
  возможна, но добавляет surface, который не нужен в v0.1.
- **«Periodic crystallization» по closure signals** — ADR-3 уже
  принципиально откладывает volatile store до v0.2. Maturity tracker
  туда естественно ляжет.

### 4.5 Вывод

Ara LRM — **не альтернатива HANDOFF.md, а его эволюция**. Конкретные
**cheap** шаги (которые можно сделать сейчас, до ADR-7):

- R-1: branching DAG в knowledge/trace/ (см. §9).
- R-4: формализовать closure signals для inbox → research promotion.
- R-5: provenance frontmatter v3 (опционально).

**Medium-cost** шаги (ADR-8 territory):

- Полноценный LRM как agent skill, с Context Harvester / Event Router /
  Maturity Tracker. Включается **после** того, как ADR-7 (inner-loop)
  определит tool-registry contract.

---

## 5. Ara Compiler ↔ ingest pipeline FA

### 5.1 Намерение совпадает

Ara Compiler берёт legacy PDF/repo/rubric → emits structured artefact.
FA `fa ingest <path-or-url>` (UC3) — тот же паттерн: heterogeneous
input → mechanical wiki entry. **ADR-5 chunker — это нижний слой
этого pipeline'а** (universal-ctags + markdown-it-py).

### 5.2 Чем Ara Compiler отличается

| Уровень                          | FA chunker (ADR-5)                                            | Ara Compiler (§4)                                                  |
|----------------------------------|---------------------------------------------------------------|--------------------------------------------------------------------|
| Goal                              | Detereministic split → indexed chunks for retrieval           | Forensic binding reconstruction → typed cross-layer references     |
| Input                             | Single file (any of supported formats)                        | PDF + repo + rubric + trajectory logs (multi-source)               |
| Output                            | `Chunk` dataclasses → SQLite FTS5                             | Full Ara file-system tree                                          |
| LLM at write time                 | Optional (page-type classification only)                      | Mandatory (skill-driven, top-down generation)                      |
| Failure handling                  | Drop chunk if parse fails                                     | Compilation failure if any PDF-accessible fact missing             |
| Iteration                         | Single-pass                                                   | 2–3× via ARA Seal Level 1 feedback                                 |

ADR-5 chunker и Ara Compiler — **different layers of the same pipeline**.
Chunker — это «extract sub-documents»; Ara Compiler — это «extract
forensic graph поверх множества chunks из множества файлов».

### 5.3 Что переносится

- **Forensic binding reconstruction** как **отдельный класс задачи**,
  не подмешанный в chunker. Сейчас в FA cross-references между
  research-нотами идут через `links:` / `related:` frontmatter и
  ad-hoc Markdown-ссылки. Если рассмотреть «links между чанками внутри
  research-нот» — это nullзначно, существует только prose.
  Recovering forensic bindings post-hoc — потенциальный v0.2 module
  («cross-reference indexer»). См. §9 R-6 (defer to v0.2).
- **Iterative refinement через Seal Level 1 feedback** — pattern,
  применимый для любого ingest pipeline'а в FA. Конкретно: после
  chunker-PR можно добавить small validator (frontmatter schema
  + reference existence + heading hierarchy), который запускается
  в pre-commit. Это уже §9 R-3.

### 5.4 Что НЕ переносится

- **PDF parsing high-fidelity** — UC3 включает PDF (через `fa ingest
  arxiv-html-summaries`), но не приоритет v0.1; Ara Compiler много
  внимания тратит именно на «numerical results in figure captions»
  (Appendix B). Для FA это medium-cost задача, не нужная для UC1.
- **«No PDF-accessible info missing = compilation failure»** — это
  слишком строгий критерий для FA. Mechanical Wiki accepts lossy
  ingestion (chunks, не facts). Adopting this strictness потребует
  reasoning-time LLM in chunker — что ADR-5 явно отвергает.

---

## 6. ARA Seal ↔ Agent Review + PR Checklist + CI

### 6.1 Что уже есть в FA

- **Conceptual review (Stage 1 в Ara terms)** — Agent Review (LLM-bot)
  + AGENTS.md PR Checklist (7 rules). Ловит structural issues
  (broken refs, frontmatter, code-fence language tags, llms.txt
  drift).
- **Empirical review (Stage 2)** — частично через CI: ruff +
  mypy --strict + pytest. Но в форке CI fork'а ограничен Devin
  Review (GitHub Actions effectively no-op). Реальный CI идёт
  upstream.
- **Human review (Stage 3)** — proect lead approves PR.

### 6.2 Что Ara добавляет

| Ara Seal Level                       | Аналог в FA                          | Gap                                                        |
|--------------------------------------|--------------------------------------|------------------------------------------------------------|
| L1 — structural integrity            | AGENTS.md PR Checklist + markdownlint| **Нет** automated frontmatter schema validator             |
| L2 — Rigor Auditor (mutation bench)  | (нет)                                 | **Нет** test, который deliberately injects errors          |
| L3 — execution reproducibility       | pytest + make check                   | Тесты пока smoke; нет fixture-based "reproduce ADR" tests  |

### 6.3 Самый важный actionable элемент

**Frontmatter v1 (mandatory) + v2 (optional) уже описан** в
knowledge/README.md (`compiled:`, `chain_of_custody:`,
`claims_requiring_verification:`, и т.д.). Сейчас это **honour-based**:
проверяется человеком при review'е. Ara Seal Level 1 показывает: это
**должно быть machine-checkable**. Конкретно:

- pre-commit hook, который parsит YAML frontmatter каждого
  `knowledge/**/*.md` и валидирует:
  - mandatory fields present (`compiled:` для research-нот);
  - `compiled:` >= max(date в тексте);
  - все пути в `links:` существуют;
  - `superseded_by:` указывает на existing файл.

Это — cheap (Python + `markdown-it-py` + `yaml`), additive (только
warnings sначала), ATOMIC под отдельный PR. См. §9 R-3.

### 6.4 Mutation benchmark — Level 2

Идея elegant: **deliberately inject errors** в Ara и проверять, ловит
ли Rigor Auditor (LLM-as-judge):

- inject orphan claim (claim без proof_pointer);
- inject fake number (число, которого нет в evidence);
- inject contradicting claim (противоречит другому claim в том же
  artefact'е).

Для FA mutation benchmark был бы тестом на качество AGENTS.md PR
Checklist'а. Например: «mutate research-ноту, удалив `chain_of_custody:`
и проверив, ловит ли Agent Review». Это полезный, но
non-blocking experiment — для v0.2.

### 6.5 Caveat из Ara

> The auditor exhibits high recall on substantive injections, a blind
> spot on orphans, and two LLM-as-judge pathologies in the auditor's
> scoring (paper §7.5).

Means: даже с mutation benchmark'ом auditor пропускает orphan claims
(claims без supporting links). Это **то самое**, что AGENTS.md
chain-of-custody rule пытается предотвратить prose-rule'ом. Структурный
(machine-checkable) chain-of-custody validator (§9 R-3) — superior к
LLM-judge.

---

## 6a. (Human+AI)² Research Network (§6 paper)

Параграф §6 paper'а — vision о том, как Ara enable-ит cross-team
collaboration: artefacts share-ятся машинно, agents читают чужие
`/trace/` и продолжают. Для First-Agent это relevant **только в
v0.2+** (multi-user namespacing, UC4). На v0.1 — single-user, single-
workstation; нет network эффекта.

**Однако** есть один паттерн из §6, который применим уже сейчас:
**parallel agent sessions writing to a shared artefact**. Это **тот
же** паттерн, что AGENTS.md «Stacked / sequenced PRs» + cutting-edge-
agent-research-radar §7 «one agent, one branch/workspace, one PR
target». Совпадение конвенций — независимая validation выбранного
направления.

---

## 7. Что НЕ применимо и почему

| Element                                               | Не применимо потому что                                                                                  |
|-------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| Layout `/logic/` `/src/` `/trace/` `/evidence/` на repo level | First-Agent — coding-agent project, не research-paper artefact. Существующий layout `docs/` `knowledge/` `src/` `tests/` лучше отражает domain. Ara-style layout надо адаптировать на уровне **knowledge/** (subfolder), не root. |
| `withholding /evidence/` для access control            | Нет multi-tier reviewers; single-user проект. Все agents имеют read-only доступ ко всему репо.            |
| `claims.md` с falsifiability per-claim                | ADR'ы уже выполняют эту роль на уровне «big decision»; per-claim formalism overkill для текстового проекта без empirical experiments. |
| `experiments.md` + `evidence/results/`                | UC1 acceptance — manual («feels usable on workstation»), no formal empirical claims в v0.1. |
| Compiler «PDF accessible info missing = failure»      | Strictness требует reasoning-time LLM в chunker — ADR-5 явно отвергает.                                    |
| Mutation benchmark Level 2 как CI gate                | Stochastic, дорого, требует full LLM-as-judge runs. Для FA — manual ad-hoc experiment, не CI gate.        |
| `(Human+AI)² Research Network`                         | v0.2+ (UC4 multi-user). На v0.1 single-user.                                                              |
| `~500` token PAPER.md manifest per artefact            | FA — один artefact (сам проект). llms.txt уже выполняет роль; per-research-note manifest overkill.        |
| Семь event types в LRM сейчас                         | Три (`decision` / `dead_end` / `pivot`) покрывают v0.1 случаи; остальные четыре требуют evidence layer.   |

---

## 8. Риски при наивном заимствовании

1. **Yak-shaving риск.** Ara — большой protocol (paper ~100 страниц). Желание
   «принять всё» приведёт к Phase S extension на месяцы; ADR-1..6 явно
   ограничивают v0.1, и Ara не должен этот scope inflate'ить. Митигация:
   рекомендации §9 строго размечены cost-tag'ами; всё `expensive` —
   defer до v0.2 минимум.
2. **Linearization → DAG конверсия.** Если конвертировать существующие
   ADR/research-ноты в DAG ретроактивно — это **сам по себе** trace-
   building task, требующий внимательного human review. Авто-конверсия
   через LLM создаст orphan узлы и fake bindings. Митигация: DAG
   строится **только для новых решений**, существующие artefact'ы
   остаются как есть, с обратными ссылками.
3. **Crystallization premature.** Ara P3 говорит «forcing premature
   structure would distort the record». В контексте FA это значит:
   не конвертировать staging-наблюдения в формальные claims без
   closure signal. Митигация: явные правила в §9 R-4.
4. **Failure preservation как constraining bias.** Цитата из paper'а
   §7.4:

   > Preserved failure traces in Ara accelerate progress, but can also
   > constrain a capable agent from stepping outside the prior-run box
   > depending on the agent's capabilities.

   Применимо к FA: если в trace dead_end узлах будет жёстко записано
   «B отвергнут», новый агент с лучшим reasoning может пропустить
   re-evaluation B при изменившемся контексте. Митигация: dead_end
   узлы должны хранить **lesson, не verdict** — формат поддерживает
   re-opening при появлении нового evidence (см. §9 R-1.2).
5. **Provenance fragmentation.** Если provenance тагается на per-
   event уровне в research-нотах, а git trailer на per-commit — два
   reconciliation'а. Митигация: trailer остаётся primary truth для
   commits; per-event provenance — secondary, для within-note
   navigation.
6. **Evaluation overhead.** ARA Seal Level 2 (mutation benchmark) и
   Level 3 (execution reproducibility) — дорогие. Если включить
   Level 2 в pre-commit, time-to-merge вырастет в 5×. Митигация:
   только Level 1 в pre-commit; Level 2 — manual ad-hoc.

---

## 9. Пронумерованные рекомендации (R-1..R-10)

Cost tags: **cheap** (≤ один PR, < 4 hours), **medium** (один-два PR,
1–3 days), **expensive** (multiple PR, week+).

### R-1 — Branching exploration DAG для knowledge/trace/ (medium)

**Что:** добавить `knowledge/trace/exploration_tree.yaml` с типизированными
узлами для решений, dead-ends, pivots в существующих ADR-1..6
amendments. Не reformat-ить ADR'ы; только сделать machine-traversable
overlay.

**Зачем:** прямо отвечает goal'у user'а — будущий агент в новой
сессии может прочитать `exploration_tree.yaml` за < 100 lines и
понять, **почему** Variant B/C отвергнуты, **что считалось** при
ADR-2 amendments, и **где** open questions сейчас.

**Cost tag:** medium. Конкретная декомпозиция:

- R-1.1 (cheap): добавить YAML schema в knowledge/README.md (документ).
- R-1.2 (cheap): backfill ADR-1..6 как dead_end / decision узлы для
  alternatives, **сохраняя `lesson:` поле, не verdict**.
- R-1.3 (medium): convention в AGENTS.md PR Checklist «новый ADR =
  новый node в exploration_tree». Опциональный pre-commit.

**Когда:** перед или параллельно с ADR-7 inner-loop. Не блокирует
ADR-7.

**Risk:** см. §8.4 (failure preservation as constraining bias) —
митигировано форматом узла.

### R-2 — Frontmatter v3: provenance per claim (cheap, optional)

**Что:** расширить frontmatter v2 schema (knowledge/README.md) с
optional полем `provenance:` на per-claim/event уровне:

```yaml
provenance:
  - event: "ADR-2 amendment 2026-05-01: MCP-shaped tool dispatch"
    origin: user-revised
    session: "2b3711d6b29c497fba602cb48f850e4d"
    date: "2026-05-01"
```

**Зачем:** отвязать provenance от commit-уровня (AI-Session trailer),
позволить агентам в новой сессии быстро видеть «что я (agent
foo-session-X) изменил vs что user revised vs что ai-suggested».

**Cost tag:** cheap. Frontmatter additive; existing files не
backfill-ятся.

**Когда:** parallel с R-1 или после.

**Risk:** §8.5 — митигировано «commit trailer = primary truth».

### R-3 — Pre-commit frontmatter validator (cheap)

**Что:** Python script `tools/validate_frontmatter.py`, hooked in
.pre-commit-config.yaml, проверяет:

- Mandatory v1 fields present для всех `knowledge/**/*.md`.
- `compiled:` is YYYY-MM-DD и >= today's earliest cited date в тексте
  (regex find dates).
- `superseded_by:` указывает на existing file.
- Все пути в `links:` существуют.

**Зачем:** ARA Seal Level 1 для FA. Превращает honour-based
AGENTS.md rules #2, #4, #5, #7 в machine-checkable.

**Cost tag:** cheap (~150-200 LoC Python + tests + hook config).

**Когда:** в любой момент после Phase S; **не зависит от ADR-7**.
Можно сделать прямо сейчас.

**Risk:** false positives на корректных edge cases; митигация —
warning-only режим в первом PR.

### R-4 — Закодифицировать closure signals для inbox → research promotion (cheap)

**Что:** добавить в knowledge/README.md секцию «Promotion rules:
notes/inbox → knowledge/research/». Конкретные closure signals:

- Topic abandonment (no edits 14 days + no incoming refs).
- Empirical resolution (linked PR closed/merged).
- Explicit affirmation в commit message «promoted from inbox».
- Artifact-level commitment (note referenced from ADR or HANDOFF).

**Зачем:** Ara P2 maturity tracker без implementation'а; чисто
documentation rule. Снижает trust gap «когда черновик становится
research-нотой?».

**Cost tag:** cheap (один Markdown PR, ~50-80 lines).

**Когда:** parallel с R-1.

**Risk:** правила могут оказаться слишком жёсткими/мягкими — митигация:
оставить выбор за лидом, как с AGENTS.md rules.

### R-5 — Документация Ara mapping в docs/architecture.md (cheap)

**Что:** в docs/architecture.md добавить секцию «External references:
Ara protocol mapping». Кратко:

- Mechanical Wiki (ADR-3) ≈ Ara Cognitive + Physical layers.
- exploration_tree.yaml (R-1) ≈ Ara Exploration Graph.
- HANDOFF.md + Agent Knowledge note ≈ Ara Live Research Manager
  (artefact-as-memory).
- AGENTS.md PR Checklist ≈ Ara Seal Level 1.

**Зачем:** дать будущим агентам один pointer на Ara, чтобы не нужно
было заново читать paper при каждой сессии. Same pattern как
agent-roles.md / sliders pointer'ы.

**Cost tag:** cheap (~30-50 lines).

**Когда:** parallel с этой нотой; включить в тот же PR или follow-up.

### R-6 — Отложить в v0.2 roadmap: cross-reference indexer (defer)

**Что:** v0.2 module, который post-hoc reconstructs forensic bindings
across knowledge/research/* по `links:` / `related:` / inline
references. Output — read-time graph для multi-hop reasoning (UC2
deferred, см. ADR-1).

**Зачем:** Ara Compiler §4.1 «recovering lineage, not flat extraction».
Применимо когда корпус research-нот превысит ~20 файлов и
multi-hop вопросы появятся в реальной работе.

**Cost tag:** expensive. Defer to v0.2.

**Когда:** v0.2 post-Mechanical-Wiki baseline; параллельно с
volatile-store hooks (ADR-3 §Decision).

### R-7 — Отложить в v0.2 roadmap: evidence layer для eval fixtures (defer)

**Что:** `knowledge/evidence/` или `tests/fixtures/` — durable storage
для:

- 5-fixture-session UC1 eval results (project-overview §3).
- chunker sample-tests (chunker-design.md §8).
- LLM-as-judge baseline runs.

**Зачем:** Ara `/evidence/` дисциплина — ground claims в raw outputs.
До chunker landed - ничего не хранить (premature).

**Cost tag:** medium-to-expensive. Defer to ADR-7-or-after.

**Когда:** **после** chunker-PR (HANDOFF Next steps #2).

### R-8 — Не делать: 1:1 root-level layout adoption (rejected)

**Что:** **не** создавать `/logic/` `/src/` `/trace/` `/evidence/` на
root level репо.

**Почему:** см. §7. Maintain текущий layout (`docs/`, `knowledge/`,
`src/`, `tests/`).

### R-9 — Не делать: автоматический LRM как Devin skill в v0.1 (defer)

**Что:** **не** реализовывать full Live Research Manager (Context
Harvester + Event Router + Maturity Tracker) до ADR-7.

**Почему:** требует tool-registry + skill-loading mechanics, которые
зарезервированы для ADR-7. Ad-hoc реализация увеличит surface, который
надо будет переписывать после ADR-7.

**Однако** — в multi-agent / subagent контексте (parent-orchestrator
делегирует child'у; каждый child — своя session) LRM-pattern становится
сильно ценнее: parent читает per-child traces в один общий artefact, и
maturity tracker reconciles diverging exploration paths через
`exploration_tree.yaml` `also_depends_on` (R-1). Это та же ниша,
которую описывает Ara §6 «(Human+AI)² Research Network». Совместимо с
Variant A + D из ADR-3: LRM пишет в A (single source of truth), D
позже extract-ит структуру из уже типизированных events (в отличие
от current «extract from raw prose»).

**Reserved as ADR-8 placeholder.** Когда ADR-7 (inner-loop tool
registry + hooks) принят, открыть **ADR-8 — Session-trace
crystallization (Live Research Manager skill)**. Декомпозируется на:

- (a) Context Harvester — читает session log + tool outputs.
- (b) Event Router — классифицирует в типы из R-1 schema (`decision`,
  `dead_end`, `pivot`, плюс v0.2-расширение `claim`/`experiment`/
  `heuristic`/`observation` когда `/evidence` слой появится).
- (c) Maturity Tracker — promote из staging → формальные слои;
  reconcile diverging traces в multi-agent setting.

Реализация — natural-language skill (Anthropic skills format) или
MCP-server (transport-decision внутри ADR-7). Не ранее v0.2.

### R-10 — knowledge/STATE.md compression (medium)

**Что:** добавить новый `knowledge/STATE.md` (~60–80 строк, ~1 500
токенов) как single-screen «текущий момент» manifest, на который
ссылаются все session-bootstrap docs. HANDOFF.md уменьшается до
append-only журнала milestone-переходов; детальный state переезжает в
`knowledge/sessions/<date>-state-snapshot.md` как archive.

Поля STATE.md:

- `phase:` — R / S / M / какой именно module.
- `last_completed_pr:` — номер + 1 строка title.
- `next_action:` — 1 строка.
- `open_threads:` — 3–5 пунктов с pointer'ами на детали (включая
  ссылки на узлы `exploration_tree.yaml` от R-1).
- `recently_landed_adrs:` — 1–6 строк.
- **никаких** «Lessons», «Stage detail», «Cross-LLM session ритуала»
  — это всё остаётся в HANDOFF.md (append-only) или в
  `knowledge/sessions/`.

**Зачем:** прямой target для goal'а проекта «less session-start
noise». Текущий bootstrap-path (README + AGENTS + llms.txt + HANDOFF
+ project-overview) ≈ 808 строк ≈ 19 500 токенов. После сжатия
HANDOFF до append-only milestone-журнала и переноса детального
state в STATE.md: ~650 строк ≈ 16 000 токенов на старте; HANDOFF
читается selectively только когда нужны детали milestone'а.

**Cost tag:** medium. Декомпозиция:

- R-10.1 (cheap): новый `knowledge/STATE.md` skeleton + первый
  snapshot текущего HANDOFF в
  `knowledge/sessions/2026-05-state-snapshot.md`.
- R-10.2 (medium): сжать HANDOFF.md до append-only milestone-журнала;
  обновить README/AGENTS/llms.txt, чтобы session-bootstrap начинался
  с STATE.md.
- R-10.3 (cheap): convention в AGENTS.md «STATE.md обновляется одной
  строкой `next_action:` в конце каждой сессии; HANDOFF.md —
  append-only milestone log, не редактируй существующие записи».

**Когда:** **после R-1 (DAG) merged**, потому что STATE.md ссылается
на `exploration_tree.yaml` для open-threads детализации. Diff-план
обсуждается в чате до самого PR.

**Risk:** некорректный split «что в STATE vs что в HANDOFF» приведёт
к тому, что HANDOFF снова разрастётся. Митигация: convention в R-10.3
явно фиксирует «HANDOFF — append-only milestone log».

---

## 10. Открытые вопросы под решение лида

| #   | Вопрос                                                                                  | Когда отвечать          | Зависит от              |
|-----|------------------------------------------------------------------------------------------|-------------------------|--------------------------|
| Q-1 | R-1 (DAG) — landing as **single PR** или **R-1.1 → R-1.2 → R-1.3 stacked**?              | до старта PR            | соглашение               |
| Q-2 | R-1.2 backfill — все шесть ADR за один заход, или incremental (по одной)?               | при R-1                 | Q-1                      |
| Q-3 | R-2 (provenance v3) — landing вместе с R-1, или как отдельный schema-only PR?            | после R-1 plan          | —                        |
| Q-4 | R-3 (pre-commit validator) — Python только под dev (`[dev]` extras), или как separate package? | до R-3 implementation | dev-deps policy        |
| Q-5 | R-4 promotion rules — числовой порог «14 days no edits» или soft-rule только?            | при R-4 PR              | —                        |
| Q-6 | R-5 (Ara pointer in architecture.md) — в этой ноте PR, или follow-up?                   | до merge этого PR       | —                        |
| Q-7 | Признаём ли формально, что HANDOFF.md → потенциальный ADR-8 LRM (R-9)?                  | post-ADR-7              | ADR-7 status             |
| Q-8 | R-6 / R-7 — фиксировать в HANDOFF Next steps как explicit v0.2 items, или оставить implicit? | при следующем HANDOFF refresh | —              |
| Q-9 | Считать ли Ara-mapping notes полезными достаточно, чтобы делать аналогичные для будущих research-нот (Mem0, MemGPT, Letta)? | meta-process | —              |
| Q-10 | R-10 (STATE.md) — single PR (skeleton + sessions snapshot + HANDOFF compress + bootstrap docs update), или 3-step stacked (R-10.1 → R-10.2 → R-10.3)? | до старта R-10 PR | R-1 merged |
| Q-11 | ADR-8 placeholder — открывать stub-файл (`ADR-8-reserved.md`) уже сейчас, или ждать ADR-7? | до ADR-7 plan | ADR-7 status |

Q-1 / Q-2 — мой default рекомендация: **single PR R-1 за один заход**,
backfill всех шести ADR одновременно (≈ 200-300 строк YAML, читается
лидом за 15-20 минут).

Q-3 — **separate schema-only PR**, чтобы R-1 не блокировался на дискус-
сию о frontmatter v3.

Q-4 — **dev extras only**, без отдельного package.

Q-5 — **soft-rule**, без жёстких numeric thresholds в первой итерации.

---

## 11. Файлы, использованные в этой сессии

### Из репо First-Agent-fork

#### Top-level

- `README.md`
- `AGENTS.md`
- `HANDOFF.md`
- `pyproject.toml`
- `Makefile`
- `.pre-commit-config.yaml`

#### `docs/`

- `docs/README.md`
- `docs/workflow.md`
- `docs/architecture.md` (selectively)
- `docs/glossary.md` (selectively)

#### `knowledge/`

- `knowledge/README.md`
- `knowledge/llms.txt`
- `knowledge/project-overview.md`

#### `knowledge/adr/`

- `knowledge/adr/README.md`
- `knowledge/adr/ADR-template.md`
- `knowledge/adr/ADR-1-v01-use-case-scope.md`
- `knowledge/adr/ADR-2-llm-tiering.md`
- `knowledge/adr/ADR-3-memory-architecture-variant.md`
- `knowledge/adr/ADR-4-storage-backend.md` (header read; not full body)
- `knowledge/adr/ADR-5-chunker-tool.md` (header read; not full body)
- `knowledge/adr/ADR-6-tool-sandbox-allow-list.md` (header read; not full body)

#### `knowledge/research/`

- `knowledge/research/agentic-memory-supplement.md` (TL;DR + §1-§3 read)
- `knowledge/research/cross-reference-ampcode-sliders-to-adr-2026-04.md`
  (§0-§2 read for pattern reference)
- `knowledge/research/cutting-edge-agent-research-radar-2026-05.md`
  (§0-§3 read for pattern reference)
- `knowledge/research/memory-architecture-design-2026-04-26.md` (referenced
  via ADR-3, header read)
- `knowledge/research/sliders-structured-reasoning-2026-04.md` (referenced
  via HANDOFF; header read)

#### `knowledge/prompts/` (folder structure inspected; not read in detail)

- `knowledge/prompts/RESOLVER.md`
- `knowledge/prompts/research-topic.md`
- `knowledge/prompts/architect-fa.md`
- `knowledge/prompts/architect-fa-compact.md`

#### `src/`, `tests/`

- `src/fa/__init__.py`
- `src/fa/cli.py`
- `tests/test_cli.py`

### Внешние источники (не файлы репо)

- arXiv:2604.24658v2 (Ara paper, full HTML extracted to local plain
  text, ~225 KB).
- arXiv:2604.24658 abstract page (metadata).
- Agent Knowledge note `note-eb4e6b4ae1d4464b89f5392ed52e757a` — «First-
  Agent — current state pointer».

### Setup / verification commands run

- `git clone https://github.com/GrasshopperBoy/First-Agent-fork.git`
- `python3 -m venv .venv && pip install -e ".[dev]"`
- `pre-commit install`
- `make lint` → All checks passed.
- `make typecheck` → Success: no issues found in 3 source files.
- `make test` → 1 passed.
- `fa --help`, `fa --version`.
- `apt-get install universal-ctags` → 5.9.0.

---

## 12. Что эта нота намеренно НЕ покрывает

1. **Source-by-source разбор Appendix B (Compiler Skill Spec)** — ~482
   строк, описание top-down generation protocol. Релевантно когда FA
   реально захочет иметь Compiler-аналог; не релевантно для R-1..R-5.
2. **Appendix E (Evaluation tables, statistical analysis)** — paper'ные
   benchmark-результаты, не воспроизводимые в FA.
3. **Сравнение с Mem0 paper.** Mem0 уже разобран в
   `agentic-memory-supplement.md`; cross-cutting сравнение
   Ara-vs-Mem0 — отдельная research-нота, если станет нужно.
4. **Конкретный YAML-schema для exploration_tree.yaml.** R-1.1
   рекомендует это как cheap PR; этот документ ставит вопрос, не
   отвечает.
5. **Реализация R-3 (frontmatter validator).** Этот документ — input
   к decision, не код.
6. **Peer-review от второго LLM.** Single-pass Devin session.
7. **Cost-of-LRM-skill estimate.** R-9 откладывает full LRM до
   post-ADR-7; estimate имеет смысл только когда tool-registry
   contract (ADR-7) подписан.
8. **UC4 multi-user namespacing implications.** §6 paper'а описывает
   `(Human+AI)²` network — для v0.1 single-user не релевантно.

---

## Edits to other files

Этот PR (если landed как один PR) также обновляет:

- `knowledge/llms.txt` — новая строка в секции `## Research`,
  ссылающаяся на эту ноту (per AGENTS.md PR Checklist rule #7).

Никакие другие файлы (включая ADR-1..6, AGENTS.md, HANDOFF.md) **не**
меняются в рамках этой ноты. Все §9 рекомендации — **input** для
будущих PR, не самих изменений.
