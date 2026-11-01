# PTY, состояние и вывод инструментов: сравнение октябрьских harness

Дата исследования: 2026-11-01. Исследование, не приёмка и не решение Q107.
Смотрены только доступные публичные исходники, спецификации и релизы; тесты
чужих продуктов и эксперименты на их production deployment не проводились.
Фиксируем SHA: ссылки на код не должны дрейфовать при изменении ветки.

## 1. Сначала различить три состояния

1. **Контекст модели** — история сообщений, вызовов инструментов и их ответов,
   после selection/compaction. PTY сам не передаёт предыдущие ответы в LLM.
2. **Файловое состояние** — файлы, процессы и артефакты общего workspace. Их
   изменения могут переживать отдельные tool calls и без постоянного shell.
3. **Состояние shell** — `cwd`, переменные, функции, активированное окружение и
   связанные с живым shell jobs. Для этого требуется отдельный механизм: живой
   shell, либо явно сохранённая/восстановленная часть состояния. PTY не обязан
   быть единственным способом сохранить живой shell, но даёт терминальную
   семантику и взаимодействие с интерактивными программами; обратная сторона —
   контрольные коды, нормализация, геометрия и границы вывода.

**Пример:** сначала `export X=42`, потом `echo "$X"`. История разговора может
сохранить текст обеих операций, а значение `X` всё равно потеряется в новом
процессе. Наоборот, `echo 42 > /workspace/x` и следующий read файла увидят
общий файл и без общего процесса. При подмене revision/view последнее обещание
перестаёт быть автоматически верным.

## 2. Версии и честные границы исследования

| Система | Взятый build | Источник и ограничение |
|---|---|---|
| OpenCode v2 | `v2.2.5`, 2026-10-30, commit `9bbb8ce18c80f099e0e448775f59d965ead40a21` | [Официальный релиз](https://github.com/anomalyco/opencode/releases/tag/v2.2.5). Буквальная ветка GitHub `2.0` — старый exploration commit `7a6ce05`, 2026-04-13, не октябрьская версия; branch `v2` также не самый свежий релиз. Поэтому изучен актуальный релиз поколения 2, а не выдана старая ветка за октябрь. |
| Codex CLI | `rust-v0.166.0`, 2026-10-29, commit `6ff1e1ca3b30fc8b914720681fcf5fe62e95f856` | [Официальный релиз](https://github.com/openai/codex/releases/tag/rust-v0.166.0), исходники открыты; именно CLI, не внутренности облачного сервиса. |
| Claude Code | `v2.1.316`, 2026-10-31, release `80c6959` | [Релиз](https://github.com/anthropics/claude-code/releases/tag/v2.1.316), [официальное описание инструментов](https://code.claude.com/docs/en/tools-reference). Полный исходный код CLI не опубликован в этом репозитории; внутреннее устройство оцениваем только по документированному поведению и changelog, не выдаём за просмотр исходников. |
| DeepSeek Harness | `dsh-v0.2.1-rc.5`, 2026-10-30, commit `b830ec950faba0a46dda564be3e2d854afed94f1` | [Официальный релиз](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.2.1-rc.5), исходники открыты. Это **release candidate**, не заявленная стабильная production-версия. |

Текущие документы Claude доступны как живые страницы: их контракт подтверждает
описание на дату исследования, а не позволяет доказать каждую внутреннюю деталь
конкретного бинарника `2.1.316`.

## 3. OpenCode v2.2.5 — отдельный PTY и отдельный shell/tool stream

- Обычный model-facing `shell`: один запуск команды через
  [`Shell.create`](https://github.com/anomalyco/opencode/blob/9bbb8ce18c80f099e0e448775f59d965ead40a21/packages/core/src/shell.ts#L270-L318)
  с явными `cwd`, окружением и `stdin: ignore`, через `ChildProcess` environment
  spawner. В просмотренном пути нет возобновления того же shell-процесса для
  следующего вызова. Это **не** утверждение, что во всём продукте отсутствует PTY.
- Для интерактивного терминала есть отдельный
  [`Pty`](https://github.com/anomalyco/opencode/blob/9bbb8ce18c80f099e0e448775f59d965ead40a21/packages/core/src/pty.ts#L182-L184)
  и persistent-PTY сервис. Не смешивать терминал пользовательского UI с transport
  вызова file/search. История session отдельно проецируется в LLM messages
  ([код](https://github.com/anomalyco/opencode/blob/9bbb8ce18c80f099e0e448775f59d965ead40a21/packages/core/src/session/runner/to-llm-message.ts#L319-L324)).
- В shell поток пишется в файл, модель получает хвост и ссылку при превышении
  лимита; [общий ToolOutput](https://github.com/anomalyco/opencode/blob/9bbb8ce18c80f099e0e448775f59d965ead40a21/packages/core/src/tool-output.ts#L13-L15)
  задаёт **2000 строк / 50 KiB**, файл хранится отдельно. Ограничение модельного
  preview не является доказательством ограниченной памяти/диска на всех слоях.
  В просмотренном коде записи `stream.write(chunk)` возвратное значение явно не
  проверяется — backpressure на этом конкретном стыке надо исследовать отдельно,
  а не утверждать, что оно доказано.
- `read` использует файловый provider и страницы; `grep` вызывает `rg` с argv
  через environment spawner и парсит stdout, не использует PTY-shell
  ([read](https://github.com/anomalyco/opencode/blob/9bbb8ce18c80f099e0e448775f59d965ead40a21/packages/core/src/tool/read-filesystem.ts#L14-L20),
  [rg](https://github.com/anomalyco/opencode/blob/9bbb8ce18c80f099e0e448775f59d965ead40a21/packages/core/src/ripgrep.ts#L118-L142)).
  Исторический [issue #45099](https://github.com/anomalyco/opencode/issues/45099)
  описывает переполнение контекста через иной session-shell путь; это **репорт для
  beta**, не доказательство, что он всё ещё воспроизводится на 2.2.5.

## 4. Codex CLI 0.166.0 — настраиваемый TTY, process id и лимиты

- [`exec_command` schema](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/shell_spec.rs#L35-L60):
  `tty=true` выделяет PTY; `false` или отсутствие — pipes. `workdir` явный.
  Это средство работать с **конкретным выполняющимся процессом**, не доказательство,
  что независимые вызовы `exec_command` разделяют `export`/`cd` одного shell.
  Длительный процесс имеет ID, его можно читать/посылать stdin; snapshot startup
  shell — отдельный механизм от сохранения любых интерактивных изменений.
- [Unified exec](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/unified_exec/mod.rs#L70-L75)
  задаёт default **10 000 output tokens** и внутренний потолок 1 MiB буфера;
  код сохраняет head/tail и `omitted_bytes`, затем явно маркирует сокращение.
  Это не означает полного архивирования произвольного stdout и не эквивалент Q97.
- [`apply_patch` — отдельный handler](https://github.com/openai/codex/blob/6ff1e1ca3b30fc8b914720681fcf5fe62e95f856/codex-rs/core/src/tools/handlers/apply_patch.rs),
  `exec-server` имеет filesystem операции; модельные tool-наборы зависят от сборки
  и конфигурации. Нельзя утверждать, что каждый Codex предоставляет отдельные
  model-facing read/grep, либо что они все используют PTY.
- Исторический [issue #50041](https://github.com/openai/codex/issues/50041)
  сообщает о потере chunks в одном канале наблюдения при отстающем watcher; это
  полезный риск для собственного теста, а не доказательство актуального бага 0.166.0.

## 5. Claude Code 2.1.316 — документированный контракт, не чтение закрытого кода

[Tools reference](https://code.claude.com/docs/en/tools-reference#bash-tool-behavior):
каждая Bash-команда — отдельный процесс; основной `cwd` переносится лишь в
определённых пределах, у subagent — нет; `export` между вызовами по умолчанию не
сохраняется. Начальные aliases/functions переносятся через shell snapshot;
`CLAUDE_ENV_FILE` — явный механизм переноса окружения. Это не равно живому
интерактивному shell и это не гарантирует сохранение любого состояния Bash.

`Read`, `Edit`, `Write`, поиск и Bash документированы как отдельные инструменты;
реализация/конкретные OS pipes из закрытого CLI по документу не доказываются.
[Официальный changelog](https://code.claude.com/docs/en/changelog) описывает
перенос больших tool results в файлы, preview и пределы, а release 2.1.309 —
исправление потери файла при неудачном копировании. Не делаем вывода, что такой
файл всегда полный, неограниченный или авторизованный для нашей архитектуры.
Документация также отдельно перечисляет `Read`/`Grep`/`Glob`; их доступность по
умолчанию зависит от платформы/режима и не является гарантией идентичного набора.

## 6. DeepSeek Harness RC — оба подхода в одном продукте

- В [standard preset](https://github.com/deepseek-ai/deepseek-harness/blob/b830ec950faba0a46dda564be3e2d854afed94f1/packages/bundle/web-app/presets/standard.patch.yml#L20-L30)
  `dsh-tool-bash` использует каждый раз новый shell; cwd/variables/functions не
  переходят от команды к команде. В
  [minimal preset](https://github.com/deepseek-ai/deepseek-harness/blob/b830ec950faba0a46dda564be3e2d854afed94f1/packages/bundle/web-app/presets/minimal.patch.yml#L34-L59)
  выбран `dsh-tool-bash-persistent`, отдельный PTY на owner с сериализацией.
  Его [контракт](https://github.com/deepseek-ai/deepseek-harness/blob/b830ec950faba0a46dda564be3e2d854afed94f1/packages/shell/tool-bash-persistent/README.md)
  сохраняет cwd/export/functions/jobs; при timeout, exit или cancellation shell
  сбрасывается и об этом сообщается. Default capture 16 000 **символов**, с
  явным clipping; это не гарантия полного вывода.
- One-shot [bash-local](https://github.com/deepseek-ai/deepseek-harness/blob/b830ec950faba0a46dda564be3e2d854afed94f1/packages/shell/bash-local/README.md)
  использует `bash -c`, default per-stream 64 000 **байт в памяти**, spill до
  67 108 864 **байт на stream**, а при ошибке spill может остаться только tail.
  `bash-local` сам по себе не sandbox; есть отдельный sandbox provider.
- Файловые инструменты идут через `ctx.fs` (line-window read, atomic write/edit,
  при подключении policy — observed version), а
  [search](https://github.com/deepseek-ai/deepseek-harness/blob/b830ec950faba0a46dda564be3e2d854afed94f1/packages/fs/tool-fs-search/README.md)
  запускает `rg` через subprocess **argv без shell**, с raw cap 20 000 000 bytes,
  отказом `SEARCH_RAW_OUTPUT_OVERFLOW` на неполном raw stdout и отдельным
  необязательным spill форматированного результата. Отказ/отсутствие spill не
  всегда ошибка — это их контракт, не автоматическое соответствие нашему Q97.
  Локальный provider может быть unconfined; политика зависит от композиции.

## 7. Что это значит для First-Agent

Наши `SessionState`, trace/events и `projection.project_for_model` уже являются
отдельными от PTY носителями истории и модельного контекста. Projection сохраняет
большой результат в `ArtifactStore`, а модели отдаёт ограниченное представление.
Но offload происходит **после** получения результата: он не спасает, если helper
уже потерял/исказил байты в PTY или `cell_worker` обрезал результат до 64 KiB.
Соответственно дальнейший переход к artifact-based результатам нельзя путать с
требованием Q97 о корректном получении исходного результата и его доступности.

Для **bash** первоначальная мотивация пользователя осмысленна: сохранение `cd`,
`export`, функций, jobs и интерактивности — заметная функциональность, которой
нет в fresh-process варианте. Не следует удалять/заменять PTY молча: это была бы
смена поведения. Сохранять state значит также явно описать reset, таймаут,
изоляцию на владельца, неопределённый завершённый/незавершённый процесс и
barrier для потомков.

Для **search/reach и file tools** перенос shell-state обычно не нужен: им нужен
один и тот же *авторизованный view/revision*, корректные ресурсы и доступ к
результату. Примеры других проектов подтверждают архитектурную состоятельность
раздельных исполнителей, но не доказывают безопасность нашего конкретного bridge.
В нашем проекте ещё сохраняются open problems metadata guard и Q102 handoff.

Рабочая рекомендация, **не принятое решение**: сохранить существующий PTY для
состояния bash и исследовать отдельный ограниченный non-PTY путь только для
allowlisted helper внутри того же cell/view. Механизм и API необходимо соотнести
с Q107 и действующей спецификацией, не открывая произвольный host subprocess.
Проверять как минимум: request/view binding, argv без shell, UTF-8 и вложенный
JSON, byte quotas всех буферов, backpressure/диск и cleanup, предотвращение
подмены/повторного исполнения, deadline, terminality и descendants, запись и
replay journal, безопасные handles/artifacts, полную доставку результата до
projection. При переполнении — явный отказ либо явно частичный результат с
доказуемо доступным остатком в рамках выбранного Q97, не фиктивный успех.

**Контекст модели:** ни 50 KiB, ни файл-артефакт не silver bullet: много малых
ответов тоже исчерпают общий бюджет, а всё содержимое может быть необходимо для
следующего действия. Нужны бюджет на весь запрос, страницы/сужение, явные
truncation и retrieval; не менять обещанный Q97 ради копирования чужих limits.
Дисковый spill, контроль памяти и изоляция артефакта друг друга не заменяют.

## 8. Q108: границы ответственности и проверка альтернатив (2026-11-01)

**Коррекция:** оператор отозвал случайный выбор Q108=B. Исследование E369 не
является решением. Публичный wire не менялся; Q108 открыт. Это архитектурная
оценка, не код, независимое review или host-приёмка.

### 8.1. Сначала разделить две задачи и три разных контракта

1. **Как выбрать исполнителя?** Сейчас v1 `EXEC` содержит только `{operation_id,
   profile_id, command, cwd, timeout_ms, session_id}`. `command` — непрозрачный
   shell-текст, существующий Bash имеет сохраняемое PTY-состояние. Непосредственный
   запуск разрешённого helper **без shell** в одном view требует доверенного
   признака/диспетчеризации, недоступных модели как произвольная программа или
   профиль. Но supervisor не обязан знать семантику `fs_search`, парсить Python,
   строить индекс или заменять ToolRegistry. Он должен проверять закрытую
   разрешённую категорию, view/grant, approved profile, ресурсы и one-shot
   reservation; конкретные поисковые параметры проверяет установленный helper.
2. **Как вернуть полный результат?** v1 `EXEC` возвращает только `{receipt}`;
   receipt содержит ≤64 KiB tail на канал. При одной операции и сохранении
   смысла всех остальных полей он физически не передаёт 4 MB результата.
   Это утверждение не запрещает *нескольких* операций или другого явно
   определённого transport, но они имеют свои затраты и ownership.
3. **Как сохранить контекст модели и доказательства?** `ExecutionReceipt` —
   факты авторизованного запуска/завершения, `ToolResult` — данные инструмента,
   `EventLog` — история взаимодействия, `project_for_model` — ограниченная
   проекция для модели. Это четыре разных назначения. Контекстное усечение
   после получения всего ToolResult не исправляет потерю на transport. Новый
   результат не должен становиться credential или доказательством terminality.

Моё утверждение E367, что *вообще* нужно расширять **receipt**, было чрезмерно
широким. Возможная совместимая по смыслу конструкция — оставить сам receipt v1
точно прежним, а в **отдельной версии ответа EXEC** передавать и данные результата.
Это всё равно изменение публичного машинного wire/результата и журналирования,
не просто внутренний worker discriminator; версия и совместимость не доказаны.
Другой путь — явный защищённый handle/поток. Нельзя решать, что он лучше, только
по факту большого размера ответа: он добавляет lifecycle и авторизацию чтения.

### 8.2. Варианты и честные границы

| Вариант | Что сохраняет | Что не решает или стоит |
|---|---|---|
| A. Обычный opaque shell-вызов helper в текущем v1 | Не добавляет wire selector; фиксированный argv можно вызывать как shell-команду, не заставляя supervisor классифицировать поисковый инструмент. Изначальная §4.2 описывала helper поверх EXEC. | Это не прямой non-PTY helper Q107; у нашего PTY доказаны трансформация Unicode/геометрия, 64-KiB tail, состояние shell и проблемы с descendants. Выдавать его за Q107 или полную выдачу нельзя. Сам факт, что supervisor не классифицирует, показывает: прежняя фраза «supervisor всегда обязан понимать search» была слишком сильной. |
| B. Несколько v1 EXEC и фрагменты | В принципе кодек каждого ответа остаётся старым; helper может быть выполнен один раз, а фрагменты прочитаны позже. | Нужны безопасное место хранения/целостность, предзаписанные IDs, восстановление при loss/crash, общие bounds, PTY и доступ к оригинальному output; эти механизмы пока не доказаны. Это не оправдывает интерпретацию magic-подстроки в opaque `command` или повторное выполнение helper. |
| C. Версионированный EXEC: закрытый helper-mode + один ограниченный полный результат рядом с прежним receipt | Один operation ID и понятное место проверки доверенного намерения; Bash/v1 остаются отдельными и неизменными. Сам supervisor работает с фиксированным helper и bounded untrusted данными, а не с индексом. Можно reuse существующие admission/journal/receipt. | Нужны явные wire/version/size/retention/memory budgets и compatibility/recovery; один inline frame не подходит автоматически для произвольного разрешённого размера. Это рекомендация для проверки, не доказанная реализация и не разрешение на новые права. |
| D. C + supervisor-owned bounded result object и chunked retrieval/stream | Отделяет малый receipt от большого результата и не требует повторного поиска; при корректной реализации уменьшает копирование и позволяет ограничить память. | Добавляет защищённый store/handle, quotas, cleanup, replay, cross-view authorization и семантику потери/повтора; простой новый файл в writable scratch или текущий ArtifactStore не даёт этих гарантий. Следует вводить только если измерения/максимумы показывают, что C не удовлетворяет Q97. |
| E. Новый публичный search RPC или произвольный generic-process endpoint | Явная классификация. | Нарушает текущие Q91/Q107: нет разрешения на новую публичную операцию или модельный выбор произвольного процесса; превращение authority в поисковый движок расширило бы TCB без необходимости. Не рекомендуется. |
| F. Host-root поиск, «удобное» усечение, повторный search | Легче связать существующий код. | Нарушает уже принятые view authority, Q97 или no-reexecution; исключить. |

Это не доказательство, что C единственный допустимый вариант. Например, B может
оказаться достижимым при отдельном безопасном replay/terminality дизайне, а A —
при другом доказанном PTY-механизме и соответствующем решении по Q107. Но сейчас
ни один из них не предъявил меньшей **полной** сложности и доказательств.

### 8.3. Проверка на существующих границах и измерениях

- Реальный `protocol.py::_object` запрещает лишние ключи; `PublicReply` и journal
  валидируют результат по operation, `_RECORD` хранит canonical input hash.
  `/tmp/probe_q108_boundaries_20261101.py` через настоящий v1 codec подтвердил:
  добавление mode, version 2, output field и tail 65 537 B отклоняются. Это C0,
  не доказательство совместимой v2 реализации.
- В том же C0 500 000 backslashes стали **1 000 012** bytes в JSON object и
  **2 000 028** при вложенном JSON string. Поэтому «передать тот же текст в
  ещё одном JSON» не равно «доставить его с маленьким запасом». `MAX_FRAME_BYTES`
  4 MiB, `MAX_TEXT_BYTES` 1 MiB и journal `_read` 4 MiB — независимые ограничения;
  отдельная строка поля может упереться в свой лимит раньше frame. Base64 даёт
  предсказуемое расширение около 4/3 для bytes, но тоже требует памяти и bounds.
- `fs_search._do_outline` обрезает по числу строк только пока строк больше одной;
  единственная большая строка может оставаться большой. `fs_reach` имеет поля
  с длинными идентификаторами и объявленный `_MAX_RESPONSE_BYTES`, который не
  обеспечивает общего доказанного предела результата. Нельзя выбрать удобные
  4 или 8 MiB и объявить parity, пока не выведен максимальный размер/разумная
  политика отказа для реально допущенных inputs и не проверен model-context risk.
- По E369 4 000 238 B дали 109 синтетических частей. Новый прямой локальный probe
  реального `OperationJournal` `/tmp/probe_q108_journal_20261101.py` выполнил
  109 искусственных `reserve → begin → record_container → complete`, прочитал
  две записи, получил **5 498 678 B** на диске и **0,792 s** на sandbox FS.
  Реальных authorization, EXEC, Docker, cell, сетевых потерь и конкуренции не
  было, это **не** оценка latency production-host. Помимо 436 транзакций, каждый
  действительный EXEC добавляет ID в `view.json` (`workspace.py:4999–5003`).
  `/tmp/probe_q108_view_limit_20261101.py` проверил только parser: пример
  view-record c 27 580 ID = **1 048 574 B**, следующий ID = **1 048 612 B** и
  `_read_json(..., 1 MiB)` даёт `CORRUPT_STATE`. Это ~253 набора по 109 **до**
  учёта других EXEC и старта helper; реальных 27 581 admissions не запускали.
  Первый запуск probe отработал exit 1 из-за режима временного файла, после
  `chmod 0600` exit 0. Это подтверждает дополнительный риск B и отдельный
  масштабный риск текущей view-структуры, а не production-инцидент.
- `Supervisor._completed` использует protected memory cache для original reply;
  `CommandReceipts.inspect` может вернуть receipt из durable DONE, но не произвольный
  отдельный ToolResult. После cache loss/restart полную выдачу нельзя обещать,
  пока отдельно не определён и не доказан путь восстановления с корректным
  grant/Q75; неизвестный исход нельзя повторить под новым ID. Версия запроса
  должна входить в проверяемую идентичность новой ветви так, чтобы не испортить
  canonical hashes уже записанного v1. `PublicReply`, result validators, journal
  и readers сегодня знают только одну форму операции; смена только codec
  недостаточна. Существующий реальный EXEC/INSPECT и старый replay не должны
  регрессировать, включая потерю кеша и отзыв разрешения.
- `CompletedReplyCache(max_public_bytes=...)` имеет локальный опциональный
  budget, но production composition сейчас создаёт его только по числу записей.
  Крупные данные в journal/cache/JSON потребуют **предварительного** допущения по
  памяти и диску, проверки ограничений при конкурентности, `ENOSPC`, release,
  сбоях fsync и максимальном retention. Факт сериализации не есть RSS proof.
  Spool в `/scratch` доступен другим процессам cell с тем же UID; hash выявляет
  подмену после вычисления, но не доказывает происхождение результата или
  terminality. Новый store не должен использовать workspace/capability как путь.

### 8.4. Что советуют практики и чего они не доказывают

- [AWS Builders’ Library: making retries safe](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
  описывает request token, проверку совпадения параметров и атомарность записи
  token/side effect; повтор с тем же ID и иным смыслом надо отклонять. Это
  поддерживает наше требование по binding и one-claim, но не доказывает exactly-once
  для Docker subprocess и не разрешает возрождение отозванного grant.
- [gRPC: flow control](https://grpc.io/docs/guides/flow-control/) различает запись
  в локальный framework buffer и реальную доставку, а
  [gRPC: retry](https://grpc.io/docs/guides/retry/) не обещает безопасный повтор
  после произвольного commitment. Сам факт «сделали streaming» не обеспечивает
  bounded memory всех слоёв, atomic DONE, replay или защиту от ложной terminality.
  Это сравнительный принцип, не предложение добавить gRPC/новый сервис.
- OpenCode/Codex/DeepSeek примеры в разделах 3–6 отделяют shell от file/search и
  применяют ограниченные результаты/спилл, но их sandbox и семантика отличаются;
  ни один пример не доказывает наш Q75/Q97 или необходимость конкретного v2 wire.

### 8.5. Предварительная рекомендация senior production review

**Рекомендация:** рассматривать C как наименьшее *явное* расширение существующей
execution boundary: доверенный контроллер выбирает фиксированный разрешённый
cell helper, supervisor только адмиттирует/исполняет/учитывает, алгоритм поиска
остаётся в cell; Bash и его receipt v1 не меняются. Это не должно быть «супервизор
теперь реализует поиск», новый публичный search API или произвольный Code Mode.
Если полные результаты не умещаются в доказанный суммарный budget, сравнить D
с B на измерениях и failure-path; не объявлять inline-only достаточным заранее.
Не выбирать пока между inline, chunked retrieval и bounded streaming как между
доказанными механизмами. Предыдущее Q108=A слишком широко описало «версионирование
receipt» и преждевременно подразумевало удобное хранение: сохранить его как историю,
но использовать более узкую формулировку решения.

До реализации: угроза и таблица v1/v2 compatibility (включая old durable DONE,
cache loss/revocation, EXEC vs INSPECT), исходный лимит и ресурсы, отражение
helper result в уже существующих session hooks/attribution, абсолютный deadline,
C0 codec, C1 реальные registry/session/UDS + worker без shell, C2 concurrency и
backpressure, C3 wrong grant/path/scratch/tamper/fault, producer и EDGE mutants,
реальный host cgroup/descendant/slow-reader/ENOSPC/kill/replay proof. L-TOOL-5
всё ещё требует planner-owned коррекции E365. Это подготовка acceptance, не PASS.

### 9. Реальные большие producers: данные для выбора транспорта (E373–E374)

После восстановления Python 3.13.16 / SQLite 3.53.4 FTS5 выполнены реальные
`project_tools._dispatch`, не синтетическая сериализация словаря. Каждый запуск —
отдельный процесс и временное дерево, без UDS, Docker, supervisor и host proof.
Сериализация — компактный UTF-8 JSON `ToolResult` (`summary`, `result`, `error`,
`artifacts`); `rss_peak_kib` — максимум **всего процесса**, а не размер reply.
Для сравнения нынешний `_envelope` во всех строках вернул `project_tool_failed`.

| fixture | вход bytes | полный JSON bytes | peak RSS KiB | время, с |
| --- | ---: | ---: | ---: | ---: |
| reach: один класс 60 000 `X`, 50 callers | 62 427 | 3 066 739 | 53 368 | 0,086 |
| reach: один класс 190 000 `X`, 50 callers | 192 427 | 9 696 739 | 99 432 | 0,254 |
| reach: 190 000 `X`, 50 callers и 50 callees, `both` | 195 248 | 19 203 206 | 165 996 | 1,175 |
| outline: markdown heading 1 999 990 `\\` | 1 999 993 | 4 000 238 | 53 700 | 0,095 |
| outline: heading 40 000 `я` | 80 003 | 80 258 UTF-8; 240 258 ASCII-safe | 30 788 | 0,007 |
| outline: heading 1 999 990 `U+0001` | 1 999 993 | 12 000 198 | 85 164 | 0,134 |
| reach: class `X` + 63 333 `U+FDF8`, 50 callers + 50 callees | 195 248 | 51 186 371 | 291 448 | 2,490 |

Для двунаправленного случая тот же probe также вызывал legacy
`build_fs_reach_tool(..., scratch_db=<temporary>)`; `result` совпал с memory
producer целиком, 50 callers + 50 callees, `truncated=False`. RSS/время в этой
строке включают **оба** producer и сравнение, это не нагрузочная оценка одной
production операции. Результат 19 203 206 bytes > 16 777 216-byte
`MAX_EXTENDED_FRAME_BYTES` ещё **до** base64/nested JSON; 8-MiB и существующий
16-MiB inline budget не дают parity. У `outline` одиночная строка не выкидывается
в цикле, ограничивающем список до более чем одного элемента, поэтому даже
`MAX_RESPONSE_BYTES=32768` не гарантирует такой предел результата. Отдельный
`MAX_TEXT_BYTES=1 MiB` в codec препятствует передаче большого поля даже при
увеличении frame. Эти фикстуры намеренно крайние, но под текущими локальными
правилами допустимы; это не оценка частоты или формальная верхняя граница всех
возможных inputs. `U+0001` допустим для локального legacy outline; для реального
view admission пока не проверен.

Рецепт существенного reach-контрпримера: в обычном `.py` файле класса с именем
`'X' * 190000`, метод `needle` вызывает `self.callee_0()` … `_49()`; методы
`caller_0` … `_49` вызывают `self.needle()`; методы `callee_0` … `_49` пустые.
Все методы в одном классе. Вызвать `_dispatch('fs_reach',
{'symbol':'needle','direction':'both','limit':50,'depth':1}, root=..., scratch=...)`.
Проверить размер source <= 200 000 (`_safe_walk` default), ровно 50 элементов
каждого направления и `truncated=False`, сравнить со старым producer и измерить
JSON в UTF-8, не печатая имена. `outline` создаётся как `'# ' + char * 1999990 +
'\n'` в `.md`, `output_mode='outline'`; все outputs должны проверяться, а не
считаться PASS только по коду выхода процесса.

Дополнительный E377 reach-контрпример использует допустимый Python-идентификатор
`U+FDF8` (ARABIC LIGATURE ﷺ), 3 UTF-8 bytes в исходнике и 8 bytes после NFKC
(`وسلم`). В классе ровно 63 333 символа, `needle`, 50 callers и 50 callees;
весь `.py` — 195 248 bytes, под `_safe_walk` 200 000-byte cap. Реальный memory
`_dispatch` выдал полные 50+50 и `truncated=False`; результат byte-for-byte
равен legacy `build_fs_reach_tool` producer. JSON ToolResult — **51 186 371 bytes**,
нормализованный qualname — 506 672 UTF-8 bytes. Таблица RSS/времени для этой
строки включает оба producer и сравнение и потому не является оценкой одного
production вызова. NFKC expansion меняет вывод E374: 19,2 MB был не сильнейшим
измеренным случаем; универсальный bound по raw file size из этих probes вывести
нельзя.

Отдельный E378 — локальный deterministic TOCTOU control, не live attacker proof:
monkeypatch после `_safe_walk` подменяет уже разрешённый in-root `.py` leaf на
symlink к соседнему файлу вне root непосредственно перед реальным
`StructuralIndex._index_one_file`. На exit 0 `fs_reach` вернул `resolved_to`
`path='a.py', qualname='escaped_secret'`, существовавший только во внешнем файле.
Причина: `_safe_walk` резолвит и проверяет containment при enumerating, а
`StructuralIndex._index_one_file` позднее делает `fp.read_bytes()`, который снова
разрешает leaf. `fs_search` аналогично передал путь, заменённый после safe-walk,
реальному `_read_text_for_index`; её search output повторно не выдал внешний
match (текущий path filter отказал), но само индексное чтение случилось. Ни один
probe не доказывает production reachability concurrent writer или Docker
boundary. Это новый security/consistency question Q109: до Q97 надо решить и
проверить descriptor-rooted no-follow reads для всего индексного read path либо
сильный immutable-generation pin, исключающий мутацию view на всё время обхода;
простое `resolve()`/повторная проверка пути не закрывает гонку. Не расширять
отказ на stable-view guarantee без user decision.

E379 threat-model review v0.1: `knowledge/project-overview.md` определяет текущую
цель как single power-user / single workstation; Telegram-группа около 10 человек
и per-user memory — future post-v0.2, не текущая multi-tenant deployment. Fixed
cell profile запускает от operator-configured UID/GID, монтирует только выбранные
`/workspace`, `/scratch`, approved read-only `/opt/toolchain-cache`; rootfs
read-only, без сети, host PID/daemon socket/supervisor paths, `CapDrop=ALL`,
private namespaces и closed seccomp profile. Это source/config shape, не host
acceptance evidence. В cell arbitrary Bash и будущий fixed helper имеют ту же
OS authority; helper не повышает privilege. Экспорт/authorization/seal основаны
на host authority и конечном tree, а `fs_search`/`fs_reach` — discovery, не
доказательство и не gate для publish. В persistent session `CellWorker.serve`
разрешает один активный RUN, но background descendants могут пережить shell
command; поэтому writer/read overlap реалистичен, хотя в E378 был лишь
детерминированно injected, не natural/concurrent C1 schedule.

Оценка: E378 — дефект точности/scope-attribution, **не подтверждённое host escape
или межсессионное чтение**. Текущий sandbox уже позволяет Bash читать те же
cell-visible rootfs/approved mounts; поэтому дополнительная hard isolation для
секретности не даёт нового security boundary и immutable-generation pin выглядит
неоправданной сложностью для v0.1. При этом тихо приписать `/etc`-символ файлу
`/workspace/a.py` — плохой discovery result и расходится с явной формулировкой
spec §4 («rooted readers enforce same [symlink] policy»). Минимум — выбрать
семантику: best-effort advisory live-tree search, без использования вывода как
evidence/authority, или строгая rooted no-follow view containment. Первая
сильнее соответствует single-user/YAGNI; вторая нужна, если «only files in the
admitted view» является буквальной гарантийной частью Q97. Исследовательская
запись не меняет пока этот контракт и не закрывает Q97; решение оставлено Q109.

**Вывод о границах:** увеличение frame само по себе не исправляет поле, cache,
журнал, идентичность и память. `operation_input_sha256` включает op/namespace/
view/payload, но не `protocol_version`; нельзя менять хеш старого DONE или
считать v1/v2 эквивалентными без явного доказательства. Q75 разрешает только
оригинальный защищённый **memory-cached** reply, с original proof и без новой
авторизации/работы; после cache loss существующий `_completed` возвращает
`EXECUTION_UNKNOWN`, `inspect` — receipt, не full tool result. Поэтому disk
spool/stream нельзя считать автоматически совместимыми с Q75: даже защищённые
чанки сами по себе не дают права реконструировать reply после потери памяти или
вернуть данные другому principal. Сам producer уже создаёт крупные объекты;
переименование последнего участка в streaming не доказывает bounded RSS, а
`CompletedReplyCache(max_public_bytes=...)` учитывает только canonical bytes,
не все копии и grants; production service сейчас его byte budget не задаёт.

Выбор транспорта пока открыт: требуется доказать максимальный результат для
всех реально поддержанных входов либо явно согласованный ресурсный контракт;
привязку каждого chunk/result к Q75; admission до работы, суммарную память,
backpressure, terminality, cancellation и старый v1 DONE. Один endpoint с новым
большим лимитом может оказаться проще защищённого spool, но нынешних измерений
недостаточно ни для его worst-case ceiling, ни для приемлемого host cost. Полный
результат в модель — отдельный риск управления контекстом (Q106), не повод
скрывать потерю ответа. Данные этого раздела не закрывают Q97/Q108/STEP2b.

Следствие для реализации: `SupervisorDispatcher._execute_reserved` сейчас создаёт
`PublicReply`, кодирует и валидирует полный ответ, пишет durable DONE и **потом**
вызывает `remember_completed`. Насыщение cache после DONE уже сегодня означает
недоступность оригинального ответа (следующий replay — `EXECUTION_UNKNOWN`),
а не основание повторить процесс. Для больших результатов недостаточно просто
выставить `max_public_bytes`: нужен доказанный порядок admission/reservation,
учёт одновременно живых копий и сохранение этого fail-closed поведения при
ошибке после DONE. Конкретный алгоритм и его совместимость с Q75 пока не выбраны.

### 10. External session: свежий и авторизованный выбор цели (E380)

Проверен [`worklogs/DEPLOYMENT-ANATOMY.md`](../../DEPLOYMENT-ANATOMY.md),
с явно указанной датой стенда 2026-08-09: `/sessions/<id>` — session workspaces,
`~/.fa` — state/DB/logs, контейнер агента не получает LLM keys, отдельный egress
proxy injects их upstream. Это историческая схема, не host proof для I03; она
подсказывает сохранять lookup по session ID, но не прямой общий mount `/sessions`
внутрь cell и не смешивать чужую историю.

Текущий код уже позволяет **переключить/attach весь run** на известную сессию:
`fa run chat --session-id <id>` → `SessionManager` валидирует manifest и выбирает
workspace path. Но это пока legacy host-path scope, не доказанный managed E2E:
`managed_execution_for_run` встречается в CLI для `fa workflow`, а `fa run chat` не
создаёт `ClientWorkspacePort`/managed EXEC. Если требуется искать B, оставаясь в
диалоге A, такого tool selector нет. Authority primitives уже есть:
`REGISTER_WORKSPACE(create=false)` возвращает актуальные workspace/current revision;
`PIN_READER` материализует immutable READ view и capability; `ClientWorkspacePort`
привязан к конкретной ViewRef/grant, но поддерживает только direct READ_FILE/WRITE_FILE.
`execution/project_tools.py` реализует cell-local fixed search/reach helper, однако
production caller через EXEC отсутствует; managed fs_search/fs_reach с port сейчас
fail-closed. Поэтому route ниже — reuse design, а не готовый E2E: нужен Q107/Q108
non-PTY integration. Весь proposed safe route: validated session ID
→ manifest/path внутри configured root → REGISTER current revision → PIN_READER
→ allowlisted helper on READ-only `/workspace` → stop/release. Модель не получает
host path, raw workspace_id, чужие DB/history, capabilities или выбор процесса;
Supervisor wire operations и EXEC не расширяются.

«Свежие» cross-session bytes имеют точный snapshot смысл: latest **published**
revision при создании pin, стабильная до конца этого read/turn; следующий запрос
перепривязывает latest. Незакоммиченный WRITE другого session не виден — читается
последняя опубликованная revision. Это проще и безопаснее, чем монтировать живой
чужой PTY view; если нужен его незакоммиченный результат, сначала target должен
publish. E376 per-call index не переносит stale cache между вызовами. Q97 result
transport/cache/context bounds остаются независимо открытыми.

Q110 закрыт ответом пользователя: нужен selector B **внутри текущего run A**.
Целевое направление — nullable `target_session_id` только на существующих
`fs_search`/`fs_reach`, с manifest resolution + REGISTER/PIN выше; это публичная
tool-schema правка, но её реализация всё ещё заблокирована незакрытыми Q97/Q108 и
открытой same-view частью Q109. Cross-session permissions beyond single local
operator/group aren't implemented in the Aug deployment note and require later
principal/ACL design; IDs сами по себе секретом/авторизацией не являются.

#### E381 wiring/cost audit after Q110 selection

Проверено выполнение до реальной ToolSpec: `build_fs_search_tool` и
`build_fs_reach_tool` при непустом `workspace_io` возвращают explicit failure
(никакого path fallback); профиль injects workspace port only from its caller, но
`src/fa/cli.py` сейчас не строит этот port. Cell-side `execution.project_tools`
обрабатывает только `fs_search`/`fs_reach`, запускает helper in-memory per call и
hard-refuses JSON envelope >60 KiB. Его production caller не найден; Q107/Q108
non-PTY EXEC расширение/adapter всё ещё отсутствует. Поэтому nullable
`target_session_id` не является небольшой standalone schema-only правкой.

For external pin only, immutable supervisor revision is mounted READ-only;
`_safe_walk` rejects resolved symlink targets outside root. With no concurrent cell
writer, E378's post-check leaf swap is not available during that read. This narrows
Q109's race to mutable WRITE-view discovery; it does not resolve its literal
same-view spec contract.

`REGISTER_WORKSPACE` existing-binding path calls `_verify_revision` (full snapshot of
retained revision) then `_snapshot` canonical source. `PIN_READER` validates the exact
revision again, and project_tools then indexes/searches it. Fresh latest per search
can therefore mean multiple full tree walks + a fresh index; no cheap current-revision
lookup by session exists. Measure actual tree size/latency and enforce deadlines before
shipping. No caching or wire amendment selected. This and the 60 KiB helper ceiling
leave Q97/Q108 open; the E377 51 MB producer is not accommodated by this helper.

#### E382: local authority and current helper resource probes

На текущем checkout (capture excludes `.git/.fa/.venv/.env`) real local
`WorkspaceAuthority` saw 1,861 entries / 66,607,919 logical bytes: first register
1.698 s; repeated register 0.394 s (revision snapshot 0.184 s + source snapshot
0.177 s); exact reader pin 0.229 s (another 0.184 s revision walk); release 0.002 s.
This confirms three full local snapshots per fresh re-register→pin, but is a single
warm-cache development host probe, not a production latency bound.

An immutable read-only local copy of the same bytes was fed to one subprocess per
helper. `fs_search`: 7.50 s, 131,144 KiB peak RSS, 2,034-byte result envelope;
`fs_reach`: 4.51 s, 63,344 KiB peak RSS, 1,423-byte envelope. Neither ran in the
approved Docker cell/cgroup, and no CLI EXEC or host acceptance was involved.
The values are concrete local implementation costs, not budgets/ceilings.

E377 was reproduced against the *current cell helper*, not merely the legacy
producer: a 195,500-byte source using `U+FDF8` yielded 50 callers + 50 callees;
the full JSON was 51,186,343 bytes. `_envelope` returned the expected 178-byte
`project_tool_failed`, but after serialization; single-process `ru_maxrss` rose
240,804 → 268,532 KiB from dispatch to envelope. Therefore 60 KiB response
refusal prevents partial success but **does not bound peak producer/serialization
memory**. The raw 200,000-byte file cap does not bound NFKC-expanded names or the
result JSON. Q97 must bound before full allocation, cover every output producer,
and test adversarial text/Unicode; exact limits and current production profile
remain unchosen/unverified.

Q110 is now answered: the desired interaction is same-run cross-read from A to B.
That does not close Q97/Q108 and is not authorization to wire a schema alone. The
minimal safe source selection remains latest committed revision, bound to the
REGISTER response, then immutable PIN; next read re-resolves/re-registers. A B
publish after REGISTER does not retarget the existing pin; the read is consistent
at its selection point.
