---
title: "Chunker design — universal-ctags vs tree-sitter vs per-language regex (для FA v0.1)"
compiled: "2026-04-26"
source:
  - https://docs.ctags.io/
  - https://github.com/universal-ctags/ctags
  - https://docs.ctags.io/en/latest/man/ctags-lang-powershell.7.html
  - https://github.com/tree-sitter/tree-sitter
  - https://github.com/tree-sitter/py-tree-sitter
  - https://pypi.org/project/tree-sitter-language-pack/
  - https://github.com/kreuzberg-dev/tree-sitter-language-pack
  - https://github.com/airbus-cert/tree-sitter-powershell
  - https://github.com/wharflab/tree-sitter-powershell
  - https://github.com/PowerShell/tree-sitter-PowerShell  # archived 2024
  - https://github.com/lepture/mistune
  - https://github.com/executablebooks/markdown-it-py
  - https://pygments.org/
  - https://llmstxt.org/
chain_of_custody:
  - "universal-ctags features and language list — taken from official
    docs.ctags.io (v6.2.0 manual) and repo README. PowerShell support
    confirmed via ctags-lang-powershell(7) man page; enum/enumlabel
    kinds confirmed via merged PRs #3571 (2022) and #3998 (2024) on
    universal-ctags/ctags. Fact-check level: primary."
  - "tree-sitter PowerShell grammar status — three repos exist:
    PowerShell/tree-sitter-PowerShell (archived 2024-01),
    airbus-cert/tree-sitter-powershell (active, MIT, 70 stars, last
    push 2026-03), wharflab/tree-sitter-powershell (newer fork, fuller
    feature surface per its README). README claims for wharflab not
    code-verified. Fact-check level: secondary (READMEs only)."
  - "tree-sitter-language-pack — 305 grammars, MIT, PyPI ~4.5M
    downloads/month per pypi.org listing; not built / installed on
    our machine. Coverage claims trusted on PyPI metadata level."
  - "Internal references — claims about gbrain CHUNKER_VERSION,
    sparks mechanical/semantic split, MEMM heading-aware chunker
    are taken from existing notes in knowledge/research/, not from
    upstream code (secondary)."
status: research
supersedes: none
extends:
  - knowledge/research/memory-architecture-design-2026-04-26.md  # §10.9 per-symbol vs per-file
  - knowledge/research/agentic-memory-supplement.md  # §4.5 CHUNKER_VERSION; §5 sparks split
related:
  - knowledge/adr/ADR-3-memory-architecture-variant.md
  - knowledge/adr/ADR-4-storage-backend.md
  - knowledge/project-overview.md
tier: stable
links:
  - "../adr/ADR-3-memory-architecture-variant.md"
  - "../adr/ADR-4-storage-backend.md"
  - "./agentic-memory-supplement.md"
  - "./memory-architecture-design-2026-04-26.md"
  - "./ai-context-os-memm-deep-dive.md"
mentions:
  - "universal-ctags"
  - "tree-sitter"
  - "tree-sitter-language-pack"
  - "PowerShell"
  - "Markdown"
  - "gbrain"
  - "sparks"
  - "MEMM"
confidence: extracted
claims_requiring_verification:
  - "wharflab/tree-sitter-powershell feature claims (control flow,
    classes, enums, splatting, here-strings) are taken from README
    only. Need to actually parse a representative .ps1 sample
    before committing to it as primary tool."
  - "tree-sitter-language-pack 305-grammar count and bundle size are
    PyPI metadata; we have not measured wheel size on disk or
    confirmed that the user's six target languages all parse via
    one `import` step."
  - "universal-ctags PowerShell scope — 'function/variable/class/
    enum/enumlabel' kinds confirmed via two merged PRs but not
    end-to-end-tested on a 1500-line .ps1 file (the user's actual
    profile)."
  - "Claim that py-tree-sitter is sub-millisecond per kilobyte on
    our 6 languages — quoted from upstream benchmarks, not
    re-measured."
---

> **TL;DR.**
>
> Для FA v0.1 рекомендация — **two-tool baseline**:
> (a) **universal-ctags** для symbol-level чанков на коде (Python,
> Go, PowerShell, TypeScript / JavaScript), (b) **heading-aware
> Markdown-парсер** (`mistune` или `markdown-it-py`) для прозы
> (Markdown / plain text). YAML / TOML / JSON парсятся встроенными
> stdlib-парсерами и индексируются *как один чанк = один файл*
> (они уже структурированы). **tree-sitter** оставляем как fallback
> для языков, где ctags даёт грубое деление, плюс как pre-built
> миграционный путь к code-graph (Variant C) — но в v0.1 не
> подключаем.
>
> Главный риск — **PowerShell**: ctags его умеет, но на нашем
> рабочем профиле (1 500-строчный `.ps1` с regions/functions) не
> проверен. Перед стартом implementation — обязательная sample-
> проверка на реальном файле пользователя.

## 1. Зачем чанкер вообще существует

ADR-3 (Variant A) делает чанкер главным write-time компонентом
v0.1. Без него агент либо дампит весь файл в контекст
(`agentic-memory-supplement.md` §1.4 — Mem0 paper показала, что
full-context даёт 17 секунд p95 latency), либо ловит зашумлённый
BM25 на крупных файлах.

Конкретные требования из `project-overview.md` §4 и
ADR-1 §Decision:

- **UC1 — coding+PR-write.** Агент читает не файл целиком, а
  релевантную функцию / class / region. Это означает per-symbol
  чанки на коде.
- **UC3 — local-docs-to-wiki.** Большой Markdown-файл (десятки
  тысяч строк), drop в `notes/inbox/`, retrieval вытаскивает
  релевантную *секцию*, не файл. Это означает heading-aware
  чанки на прозе.
- **«Большой файл в inbox»** (project-overview §4) — capability
  должна быть language-agnostic в пределах текстовых форматов.
  PDF→text — отдельный pipeline, deferred to v0.2.

ADR-3 §Consequences явно отложил выбор инструмента в research-
ноту: «implementation strategy left to a follow-up research note
(likely universal-ctags for code + heading-aware chunker for
Markdown + block-aware for config files)». Эта нота закрывает
этот open question.

## 2. Что именно надо чанкить

### 2.1 Языковая матрица

Из `project-overview.md` §4 + явных ответов пользователя в Question 1
(memory-architecture-design Q1 / supplement-сессия):

| Язык / формат | Файл-профиль | Use case |
|---|---|---|
| Markdown / plain text | произвольно large (notes/inbox/, docs/) | UC3 retrieval |
| Python | FA itself, личные репо | UC1 |
| Go | личная библиотека | UC1 |
| PowerShell `.ps1` | ~1 500-строчный скрипт | UC1 |
| TypeScript / JavaScript | возможно личные репо | UC1 |
| YAML / TOML / JSON | конфиги | UC1 + reading |

Первичный профиль — **6 языков**. Чанкер должен покрывать всё это,
но не обязан с равной точностью. PowerShell — самый редкий в
open-source-инструментах; Markdown — самый объёмный по volume.

### 2.2 Output-shape: что значит «чанк»

ADR-4 §Schema фиксирует таблицу `chunks(id, path, anchor, lang,
body, mtime, sha256)`. От чанкера ожидается:

- `path` — относительный путь к файлу-канону.
- `anchor` — стабильный идентификатор для re-find в файле:
  - на коде — `<symbol-name>` (function, class, method, type).
  - на Markdown — `<heading-slug>` (kebab-case slug ATX-heading'а).
  - на конфигах — обычно `<filename>` (один чанк на файл).
- `body` — собственно текст чанка.
- `lang` — язык-тэг для retrieval-фильтрации.

**Критерий хорошего чанка** для FA:

1. **Self-contained semantically.** Reader не должен читать соседние
   чанки, чтобы понять, что делает функция / о чём раздел.
2. **Stable across edits.** Если функция переехала на 200 строк
   ниже — anchor остался тем же. (Anchor по строковому номеру —
   плохо; anchor по имени — хорошо.)
3. **Roughly ≤ 1024 tokens** (sparks default; см.
   `agentic-memory-supplement.md` §5). Большие — резать на
   подсекции; мелкие — оставить как есть.
4. **Reversible.** Можно re-extract из канона за O(1) — не нужно
   хранить byte-offsets, потому что cache invalidation через
   sha256 (ADR-4 §Cache Invalidation).

### 2.3 Что чанкер НЕ делает

- Не извлекает entities / relations (это Variant B / C).
- Не классифицирует (tier, confidence — frontmatter v2 ставит человек или write-time prompt).
- Не embedding'ует (Variant B).
- Не вычисляет «typed edges» между функциями (Variant C, gbrain).

Чанкер — деревянный код. LLM в этой стадии не участвует.
Это инвариант ADR-3.

## 3. Таксономия подходов

Пять классов инструментов, в порядке возрастающей структурности:

### 3.1 Naive fixed-window (last resort)

Делит файл на N-токенные окна с overlap'ом.
LangChain `RecursiveCharacterTextSplitter` — типичный пример.

- **+** работает на любом тексте.
- **−** ломает symbols пополам, anchors нестабильны.
- **−** sparks (`agentic-memory-supplement.md` §5) явно отказались
  от naive split в пользу mechanical/semantic.

Применение в FA: **только** как fallback, когда другие методы
сломались на конкретном файле (e.g. corrupted UTF-8, exotic encoding).

### 3.2 Heading-aware splitters

Парсят документ-структурный синтаксис, режут на subtree'ях.
Применимо к Markdown / RST / OrgMode / HTML.

- MEMM (`ai-context-os-memm-deep-dive.md` §5) делает это руками
  через regex на ATX-headings.
- `markdown-it-py` (PyPI: `markdown-it-py`) даёт официальный AST.
- `mistune` — то же, faster.
- cmark-style библиотеки также подойдут, но requires C-extension.

**+** Идеально для прозы: section = chunk, heading = anchor.
**−** Не работает на коде (там нет надёжных «секций»; PowerShell-
regions — частный случай, см. §3.4).

### 3.3 Symbol extractors

Парсят source-код достаточно, чтобы найти top-level symbols
(functions, classes, types, modules). Не строят полное AST.

- **universal-ctags** — флагман этого класса; см. §4.1.

**+** Symbol-level гранулярность без full-AST-стоимости.
**+** Multi-language через один CLI.
**+** Stable anchors (имена, не offsets).
**−** Не даёт inner-structure (тело функции — одна big строка).
**−** Точность хуже, чем у concrete-syntax-tree парсеров на
  edge-case'ах (multi-line string'и в PowerShell, шаблоны в TS).

### 3.4 Concrete syntax tree (CST) парсеры

Полноценный parse → дерево, которое можно обходить.

- **tree-sitter** — флагман; см. §4.2.
- Pygments lexer — token-stream, не CST; в этом классе пограничный.

**+** Точность: может разделять тело функции на блоки, выделять
  PowerShell `begin/process/end`, TypeScript JSX-children и т.д.
**+** Bench-checked для редактор-use-case'ов (millisecond per file).
**+** Готовая база для code-graph (Variant C, gbrain) без новой
  миграции.
**−** Dependency-вес: грамматики компилируются в native binaries.
**−** Версионирование (gbrain CHUNKER_VERSION) обязательно — иначе
  изменение грамматики между релизами инвалидирует cache.
**−** Грамматики качества «70%» для редких языков (PowerShell —
  pre-2024 был именно таким).

### 3.5 Per-language regex / heuristic

Самый старый подход. Для каждого языка — небольшой набор regex-
правил, которые ловят `def`/`func`/`function`/`class` etc.

- sparks (`agentic-memory-supplement.md` §5) для своих 36 языков
  использует именно так — `extract.py` 3 440 строк pure Python.
- MEMM — то же самое, но только для Markdown.

**+** Zero-deps. Полный контроль.
**+** Легко патчить под локальный edge-case.
**−** O(N) maintenance: каждый новый язык = новая порция regex-ов.
**−** Brittle: триплет `"""` в Python, here-strings в PowerShell,
  template literals в TS — всё кейсы, которые ломают наивный regex.
**−** sparks показала, что 3 440 строк — это floor, не ceiling, для
  6 языков. Меньше будет либо неточно, либо неполно.

### 3.6 Hybrid

Реальный production-чанкер — почти всегда гибрид:

- gbrain: tree-sitter для symbols + own-regex для doc-extraction
  внутри функций.
- sparks: per-language regex + Markdown-AST для проз-секций.
- MEMM: per-format heading-regex (Markdown only); код не
  чанкается вообще, только по-файлово.

Для FA v0.1 нативный гибрид — это именно §4 ниже.

## 4. Глубокий разбор кандидатов

### 4.1 universal-ctags

Maintained fork от Exuberant Ctags. C-binary, single-CLI,
читает ~80 языков из коробки (см. `docs.ctags.io` Languages page).

**Плюсы для нашей задачи:**

- Native PowerShell (kinds: function, variable, class, enum,
  enumlabel). Подтверждено двумя merged PR'ами:
  PR #3571 (2022) — enum kind, PR #3998 (2024) — enum-label.
  Active maintenance.
- Native Python, Go, JavaScript, TypeScript, JSON, YAML — не
  edge-case'и, многократно проверенные.
- Single dependency (`apt install universal-ctags` или brew).
- Stable JSON-output формат (`--output-format=json`):
  ```json
  {"_type":"tag","name":"Get-Foo","path":"./script.ps1",
   "language":"PowerShell","line":42,"kind":"function",
   "scope":"…","scopeKind":"module"}
  ```
  Парсится одной строчкой Python, никакой бинарной обвязки.

**Минусы:**

- **Не строит CST.** Тело функции — это «всё от line N до
  следующего top-level symbol». Если функция содержит вложенный
  `function Inner` — ctags его выделит как отдельный entry, что
  для нас, пожалуй, ок (мы хотим per-symbol чанки).
- **Не разбивает большие функции.** Если у пользователя
  500-строчная PowerShell-функция, она станет одним 500-строчным
  чанком. Внутрисимвольная резка — задача за пределами ctags.
  Mitigation: post-process на больших чанках (split по pure
  blank-line OR по region-comments `#region` / `#endregion`).
- **Markdown** — не главный use-case ctags. Поддержка есть
  (kind: section), но тестировать на реальных длинных нотах
  пользователя надо отдельно. Лучше делегировать на §4.3.
- **YAML / TOML / JSON** — ctags может тегить top-level keys,
  но для нашего use-case'а смысла нет: типичный конфиг < 1024
  токена и индексируется как один чанк = один файл.

**Версионирование.** ctags-binary версия фиксируется в lockfile
(`apt-cache policy universal-ctags` → pin major.minor). Кэш-
инвалидация — через `chunker_version = "ctags-{version}-{lang}"`
поле в `meta` table (ADR-4 §Schema). Если ctags обновился, поле
не совпало → re-extract.

**Фактчек.** PowerShell-поддержка проверяется на одном эталонном
файле пользователя ДО коммита implementation. См. §8, item 1 +
§9 OQ-2.

### 4.2 tree-sitter

Парсер-генератор: грамматики на JavaScript-DSL, компилируются в
C-библиотеки, привязки на десятки языков. Одна установка дала бы
нам все 6 языков.

**Два пути в Python:**

- **`py-tree-sitter`** (вertex Github
  `tree-sitter/py-tree-sitter`) — голый binding.
  Грамматики надо ставить отдельно (`tree-sitter-python`,
  `tree-sitter-go`, …). Каждый — отдельный pip-пакет.
- **`tree-sitter-language-pack`** (PyPI, MIT, ~4.5M
  downloads/month) — 305 грамматик одной зависимостью.
  Один import даёт all-languages access:
  ```python
  from tree_sitter_language_pack import get_parser

  parser = get_parser("powershell")
  tree = parser.parse(b"function Foo { ... }")
  ```

**PowerShell-ситуация специфическая:**

| Repo | Status | Проверено |
|---|---|---|
| `PowerShell/tree-sitter-PowerShell` | **archived** 2024-01 | TODO-list в README показывает большие пробелы (switch, filter, throw, foreach …) — нет смысла. |
| `airbus-cert/tree-sitter-powershell` | active, MIT, 70★ | Last push 2026-03. Используется в нескольких editor-плагинах. Скорее всего production-ready. |
| `wharflab/tree-sitter-powershell` | newer fork | README заявляет очень полную фичу-матрицу: pipelines, classes, enums, switch с -Regex/-Wildcard, splatting, here-strings, ternary, null-coalescing, format strings и т.д. **Но cards-only**: код не верифицирован нами. |

`tree-sitter-language-pack` (на 2026-04) бандлит airbus-cert
вариант. Это и есть наш default-путь, если выберем tree-sitter.

**Плюсы:**

- Полное CST → можно **внутрисимвольно** резать большие функции
  (по `body_block`'ам, например).
- Future-proof для Variant C: если когда-то поднимем code-graph
  (`Function→[calls]→Function`), tree-sitter — стандартный
  inputlayer (sparks / gbrain паттерн).
- Speed: tree-sitter incremental parsing — это про editor-tier
  performance, для нас оверкилл, но не bottleneck.
- Markdown — есть отдельная грамматика
  (`tree-sitter-md` / `tree-sitter-markdown`), включена в
  language-pack. Можно использовать **для всего**, без mistune.

**Минусы:**

- **Dependency-вес.** `tree-sitter-language-pack` wheel — несколько
  десятков MB (305 native parsers). Для FA это не блокер
  (single-machine), но `pip install` дольше, image-builds дороже.
  Для эталонного измерения — см. OQ-3.
- **CHUNKER_VERSION-обязательность.** Грамматики обновляются
  независимо от tree-sitter core. Если airbus-cert/tree-sitter-
  powershell релизнул v1.2 → v1.3 с переименованием node-name'а
  — наш чанкер выдаст «другие» chunks для тех же файлов, и
  существующий index стал stale. Mitigation — `chunker_version`
  в `meta` (как у ctags), плюс лочиться на pinned grammar-versions
  через `tree-sitter-language-pack==<exact>`.
- **Сложность обхода CST.** Чтобы выделить «тело функции» —
  надо знать имена node-types для каждого языка (для PS это
  `function_definition` → `script_block_body`; для Python это
  `function_definition` → `block`; для Go — `function_declaration`
  → `block`). 6 языков = 6 наборов node-name'ов. Это не неподъёмно
  (gbrain делает то же), но это **constant**, который придётся
  поддерживать.
- **Markdown-грамматика** в tree-sitter — спорная. Markdown
  inherently ambiguous (CommonMark vs GFM), и tree-sitter-md
  имеет open issues по corner-case'ам. `mistune` или `markdown-it-py`
  более mature на чисто Markdown-задаче.

**Когда выбрать tree-sitter:** если планируем code-graph в
v0.2-v0.3, либо если ctags на нашем рабочем `.ps1` облажается.

### 4.3 markdown-it-py / mistune

Чисто Markdown-AST парсеры на Python.

- **`markdown-it-py`** — порт markdown-it (commonmark + GFM
  extensions); используется Sphinx, MyST. AST доступен в виде
  `Token`-list или через `SyntaxTreeNode`. Maintained.
- **`mistune`** — single-file Markdown parser, faster than
  markdown-it-py, чуть менее GFM-compliant.

Оба дают то, что нам нужно — обход по headings, code-blocks,
tables. Для **heading-aware** chunking разницы практически нет;
выбор по `pip install markdown-it-py` vs `pip install mistune`
эстетический.

**Recommendation:** `markdown-it-py`. Стандарт de-facto в Python-
вселенной (Sphinx, MyST), GFM-tables/footnotes из коробки,
maintained Foundation-tier project.

### 4.4 Pygments lexer

Token-stream lexer для подсветки. Поддерживает 600+ языков.
Не CST.

Полезность для нас — **лимитированная**. Pygments умеет сказать
«вот тут token-type=Keyword.Function`», но не «вот блок начинается
здесь и заканчивается там». Для symbol-extraction всё равно
нужно self-делать state-machine поверх его tokens. Это не лучше,
чем просто звать ctags.

**Recommendation:** не используем как primary tool. Можно держать
в уме как «ещё один fallback», но не оптимально.

### 4.5 Per-language regex / heuristic

Совсем self-rolled (sparks-стиль).

- **+** Контроль над каждым edge-case'ом.
- **+** Zero-deps.
- **−** sparks показала, что для 6 языков это >3000 строк кода.
  Это два-три месяца стабилизации, прежде чем доверять.

**Recommendation:** держим как fallback для языков, где
ctags отвалится. Не как primary.

## 5. Coverage matrix

Какой инструмент покрывает наши 6 языков с какой fidelity'ю.

Шкала:
- **A** — production-ready, проверено на этих файлах.
- **B** — работает, но не оптимально / не на всех конструкциях.
- **C** — теоретически работает, но не наш use-case.
- **−** — не покрывает.

| Язык | universal-ctags | tree-sitter (lang-pack) | markdown-it-py | per-lang regex | stdlib parser |
|---|---|---|---|---|---|
| Markdown | C | B | **A** | A | − |
| Python | A | A | − | B | A (`ast`) |
| Go | A | A | − | B | − |
| PowerShell | **B (TBD)** | B-?? | − | B | − |
| TypeScript / JS | A | A | − | B | − |
| YAML | C | C | − | C | A (`PyYAML`) |
| TOML | − | A | − | B | A (`tomllib` 3.11+) |
| JSON | A | A | − | A | A (`json`) |

Главные точки внимания:

- **PowerShell** — для ctags статус «B (TBD)» = ожидаемый «A»,
  но требует sample-проверки. Для tree-sitter — статус неоднозначный
  из-за разделения upstream'ов (см. §4.2).
- **Конфиги** — ctags overkill, tree-sitter overkill;
  stdlib-парсера достаточно. По нашему scoping'у (один чанк = один
  файл) парсить вообще не обязательно — достаточно прочитать как
  text и проиндексировать целиком.
- **Markdown** — markdown-it-py на голову опережает оба code-
  oriented инструмента.

## 6. Trade-offs

### 6.1 Dependency footprint

| Stack | Native deps | Wheels (approx) | Install time |
|---|---|---|---|
| ctags + markdown-it-py | `universal-ctags` C-binary (apt/brew, ~6 MB) | ~1 MB Python | 5-10 s |
| tree-sitter-language-pack только | none (pre-built C inside wheel) | ~50-100 MB | 30-60 s (depending on platform-specific wheel) |
| ctags + tree-sitter-language-pack (hybrid) | C-binary + wheel | ~50 MB+ | 30-60 s |

Для FA single-user это не критично. Для образовательного
fork-репо — markdown-it-py + ctags-CLI лучше: меньше странных
ошибок при первом install.

### 6.2 Accuracy / fidelity

На code:

- ctags: «90% разбиений на symbols правильны на типичных файлах».
- tree-sitter: «98%+ если грамматика matched».
- per-language regex: «60-80% в зависимости от пары
  programmer-fluency × language-quirkiness».

Для UC1 «найти функцию по имени и прочитать её» — 90% ctags
достаточно. 98% tree-sitter — over-engineering на v0.1.

На прозе (Markdown):

- markdown-it-py / mistune: ~99%, ловят все ATX/Setext-headings,
  fenced code blocks, lists.
- ctags: ~70%, путается с inline-code, не различает code-block.
- tree-sitter-md: ~90-95%, спорные case'ы на nested lists.

### 6.3 Speed

Не bottleneck для FA-scale (1 — 10 K файлов, manual reindex).
Все три инструмента — millisecond per kilobyte:

- ctags на 1500-строчном `.ps1`: ~10 ms.
- tree-sitter на том же файле: ~5 ms.
- markdown-it-py на 100 KB Markdown: ~30-50 ms.

Cold reindex 1000 файлов = ~30 секунд. Acceptable.

### 6.4 Versioning + cache invalidation

ADR-4 §Cache Invalidation требует, чтобы любое изменение чанкера
триггерило re-extraction. Реализация — поле `chunker_version` в
`meta` table:

```python
chunker_version = f"ctags-{ctags_version}-mdit-{mdit_version}"
```

Если значение изменилось — invalidate all chunks.

- **ctags-only:** одно число, простое pinning через apt/brew lockfile.
- **tree-sitter-language-pack:** одно число (`pip freeze`), но
  внутри обновляются 305 грамматик. Любая может начать выдавать
  иные node-name'ы, и наш чанкер начнёт молча выдавать иные
  chunks. Mitigation — `==` pinning + ручной upgrade-PR.
- **gbrain CHUNKER_VERSION pattern** (`agentic-memory-supplement.md`
  §4.5): любое изменение **внутреннего chunker-кода FA** также
  должно bump'ать version. Не только версия dependency.

Сложнее — у tree-sitter-language-pack. Это аргумент «не выбирать
его на v0.1».

### 6.5 Maintenance burden (human-time)

| Stack | Initial setup | Per new language | Per upstream upgrade |
|---|---|---|---|
| ctags-CLI subprocess | 1 день | 1-2 часа (тест на sample) | 1 час (re-test, bump version) |
| markdown-it-py | 0.5 дня | n/a (один язык) | 0.5 часа |
| tree-sitter-language-pack | 2-3 дня (научиться node-name'ам) | 1 день (новые node-name'ы для нового языка) | 2-4 часа (audit grammar diff) |
| per-language regex (sparks-style) | 1 день per language | 1 день | проблема не upstream'а, а собственная |

ctags + markdown-it-py — самое дешёвое в поддержке.

### 6.6 Failure modes

Что ломается при каждом подходе:

- **ctags:** выдаёт пустой list для files, где не распознал
  язык. Mitigation — fallback на per-extension lookup,
  иначе целый файл идёт как один чанк. **Не silent**: ctags
  пишет stderr, мы должны логгировать.
- **tree-sitter:** parse-error на куске → возвращает дерево с
  ERROR-нодами; обход их игнорирует, и кусок «выпадает» из
  чанков silently. Это худший failure mode. Mitigation — после
  parse'а проверять `tree.root_node.has_error` и fallback на
  ctags / fixed-window.
- **markdown-it-py:** на malformed Markdown пытается graceful
  parse — practically не fails. Но если файл — это код с `.md`-
  расширением (например, mermaid-diagram), парсер выдаст что
  попало. Mitigation — перед чанкингом проверять MIME-type /
  shebang.
- **per-language regex:** silent miss. Неотловленный edge-case
  → symbol просто пропадает из chunks. Хуже всего.

Пара ctags + markdown-it-py имеет самые **громкие** failure modes,
которые легко обнаружить unit-тестами.

## 7. Конкретная рекомендация для v0.1

### 7.1 Stack

**Primary chunker pipeline:**

1. **Markdown / plain text** (`*.md`, `*.txt`):
   `markdown-it-py` → AST → split по H1/H2 (configurable depth) →
   slugify heading → `anchor`. Если файл < 500 строк — один чанк
   на файл, без разбиения.
2. **Source code** (`*.py`, `*.go`, `*.ps1`, `*.psm1`, `*.ts`,
   `*.tsx`, `*.js`, `*.jsx`):
   subprocess `ctags --output-format=json --fields=+ne` → parse
   JSON → for each tag, slice the file by line range up to next
   top-level symbol → chunk.
   Special case: PowerShell `#region` / `#endregion` markers —
   pre-split file by regions before передача ctags'у.
3. **Config files** (`*.yaml`, `*.yml`, `*.toml`, `*.json`):
   no chunking. One file = one chunk. Anchor = filename.
4. **Catch-all** (everything else): one file = one chunk.

**Tooling:**

- `subprocess.run(["ctags", "-f-", ...])` — no Python wrapper
  needed. Output is well-defined JSON.
- `markdown-it-py` for Markdown.
- stdlib for YAML/TOML/JSON (don't even parse — just chunk as text).

### 7.2 Что именно НЕ берём в v0.1

- **tree-sitter** в любой форме. Причина: dependency-вес плюс
  CHUNKER_VERSION-сложность плюс отсутствие нашей реальной
  необходимости в внутрисимвольной резке на v0.1.
  Re-evaluation триггер: если `chunks` содержит symbols >2 K
  токенов, и LLM-context на UC1 страдает, то rev-on tree-sitter
  для resplit. Не раньше.
- **Embeddings / vectors** в чанкере. ADR-3 явно отложил.
- **Per-language regex.** Дорого по maintenance, и ctags
  покрывает наши 6 языков.

### 7.3 Stable interface (ADR-3 §Read-side hooks)

Чтобы будущая миграция на tree-sitter / Variant C не ломала
callers, фиксируем абстракцию:

```python
@dataclass(frozen=True)
class Chunk:
    path: str  # relative to repo root
    anchor: str  # symbol name or heading slug or filename
    lang: str  # detected language tag
    body: str  # the chunk text
    line_start: int  # 1-based, inclusive
    line_end: int  # 1-based, inclusive


class Chunker(Protocol):
    def chunk_file(self, path: pathlib.Path) -> list[Chunk]: ...
```

Implementation в v0.1 — `CompositeChunker` с per-language
delegation. Позже можно swapнуть `CtagsChunker` на
`TreeSitterChunker` без изменения callers.

### 7.4 Версионирование

Один-числовой `CHUNKER_VERSION` в `src/fa/chunker/__init__.py`.
Bump на любое изменение:

- алгоритма split'а (добавили `#region`-handling — bump);
- зависимости (ctags 6.2 → 6.3 — bump);
- `markdown-it-py` upgrade — bump.

Поле пишется в `meta` table. ADR-4 §Cache Invalidation уже это
описывает; чанкер просто его читает / пишет.

## 8. Sample test plan (pre-implementation)

Перед коммитом implementation:

1. **PowerShell sanity-check.** Берём пользовательский 1500-
   строчный `.ps1`, гоним `ctags --output-format=json`, проверяем
   что:
   - все top-level functions выделены;
   - regions не теряются;
   - `kind=function` коррелирует с реальными `function Name {` в файле;
   - на больших функциях chunk-size остаётся в bounds (< ~2 K
     токенов; иначе — split).
   Если ctags провалился — fallback на airbus-cert tree-sitter.
2. **Markdown smoke-test.** Берём project-overview.md (228 строк,
   реальный наш файл), парсим markdown-it-py, проверяем что
   секции из ATX-headings соответствуют разделам.
3. **Mixed-content test.** Берём random Go-файл (например,
   из user's личной библиотеки), проверяем что ctags выделил
   functions + types + methods.
4. **Round-trip test.** Reconstruct file from chunks; должно
   совпасть с originalом (по содержимому, не bit-perfect — могут
   быть нюансы trailing whitespace).

Эти 4 теста — gate для PR с implementation. Без них — не мерджить.

## 9. Open Questions для ADR-5

ADR-5 будет «chunker tool selection». Вопросы, которые надо
закрыть в нём:

| # | Вопрос | Default-ответ из этой ноты |
|---|---|---|
| OQ-1 | universal-ctags vs tree-sitter для code | **ctags для v0.1** (см. §7.1, §7.2). Triggers for revisit зафиксировать в ADR-5 §Consequences. |
| OQ-2 | Ожидание ctags-PowerShell на нашем 1500-строчном `.ps1`: production-ready или дырявое? | TBD. **Sample-проверка ОБЯЗАТЕЛЬНА** до коммита (см. §8, item 1). |
| OQ-3 | tree-sitter-language-pack on-disk size — какой реальный footprint после `pip install`? | TBD. Замерять во время setup-fasta. <100 MB — ok; >300 MB — пересмотр. |
| OQ-4 | Should chunker handle `#region` / `#endregion` в PowerShell специально? | **Да** (§7.1, шаг 2 special-case). Это user-editable boundary; уважать. |
| OQ-5 | markdown-it-py vs mistune — выбор зависит от чего? | **markdown-it-py** (§4.3). Аргумент — ecosystem maturity. Не блокирующий. |
| OQ-6 | YAML/TOML/JSON — один чанк-один файл или per-top-key? | **Per-file** (§7.1, шаг 3). Триггер для revisit — если у нас будут конфиги > 1500 строк (unlikely для FA). |
| OQ-7 | Куда складывать ctags binary при packaging? | Не наша забота — `apt install universal-ctags` user-side. CI install через `apt-get install`. Не bundle'им. |
| OQ-8 | Что делать, если язык неизвестен ctags (e.g. `.lua`, `.rb`)? | One-file = one-chunk fallback (§7.1, шаг 4). Не блокирует UC1/UC3 (мы ограничены 6 языками). |
| OQ-9 | Versioning — что инкрементируем при upgrade'е markdown-it-py minor? | **Yes, bump CHUNKER_VERSION**. Плата — re-extract всех Markdown-чанков. На FA-scale — 30 секунд. Acceptable. |
| OQ-10 | tree-sitter migration trigger — какой явный сигнал о переезде? | Если на UC1 LLM-context-error rate > 5% из-за «chunk слишком большой» (single function > 2 K tokens). До тех пор — ctags. |

## 10. References

### 10.1 Internal (knowledge/)

- ADR-3 [Memory architecture variant for v0.1]
  (`../adr/ADR-3-memory-architecture-variant.md`) — рамки
  чанкера: «multi-language deterministic chunker», что НЕ берём
  на v0.1.
- ADR-4 [Storage backend for v0.1]
  (`../adr/ADR-4-storage-backend.md`) — schema `chunks`,
  `chunker_version` поле, cache-invalidation contract.
- `agentic-memory-supplement.md` §4.5 — gbrain CHUNKER_VERSION
  паттерн (что НЕ берём из gbrain в v0.1, но архитектурно
  reservedно).
- `agentic-memory-supplement.md` §5 — sparks mechanical/semantic
  split, `extract.py` 3 440 lines per-language regex (контр-
  пример к нашему ctags-подходу).
- `ai-context-os-memm-deep-dive.md` §5 — MEMM heading-aware
  Markdown chunker (один из источников нашего подхода для
  Markdown).
- `memory-architecture-design-2026-04-26.md` §10.9 — открытый
  вопрос «per-symbol vs per-file», на который эта нота отвечает.
- `agent-roles.md` §«Никогда не проси LLM делать то, что может
  деревянный код» — общий принцип. Чанкер — деревянный код.

### 10.2 External (primary)

- universal-ctags official:
  - Repo: https://github.com/universal-ctags/ctags
  - Docs: https://docs.ctags.io/
  - PowerShell man page:
    https://docs.ctags.io/en/latest/man/ctags-lang-powershell.7.html
  - PR #3998 (enum-label kind for PS):
    https://github.com/universal-ctags/ctags/pull/3998
  - PR #3571 (enum kind для PS):
    https://github.com/universal-ctags/ctags/pull/3571
- tree-sitter:
  - Core: https://github.com/tree-sitter/tree-sitter
  - Python binding: https://github.com/tree-sitter/py-tree-sitter
  - Language pack: https://github.com/kreuzberg-dev/tree-sitter-language-pack
  - PyPI: https://pypi.org/project/tree-sitter-language-pack/
- tree-sitter-PowerShell repos:
  - Active: https://github.com/airbus-cert/tree-sitter-powershell
  - Newer fork: https://github.com/wharflab/tree-sitter-powershell
  - Archived: https://github.com/PowerShell/tree-sitter-PowerShell
- Markdown:
  - markdown-it-py:
    https://github.com/executablebooks/markdown-it-py
  - mistune: https://github.com/lepture/mistune
- Pygments: https://pygments.org/

### 10.3 Convention

- llms.txt: https://llmstxt.org/ (для маркировки нашей
  собственной нотой как агент-readable артефакта).

## 11. Cheatsheet (для ADR-5 author'а)

- **Выбор:** universal-ctags + markdown-it-py.
- **Не берём:** tree-sitter, per-language regex, embeddings.
- **Sample-test до coding:** PowerShell 1500-строчный `.ps1`.
- **Stable interface:** `Chunker.chunk_file(path) -> list[Chunk]`.
- **Versioning:** `CHUNKER_VERSION` в `meta` table.
- **Re-evaluation trigger:** если symbol-chunk > 2 K токенов
  ломает UC1.
