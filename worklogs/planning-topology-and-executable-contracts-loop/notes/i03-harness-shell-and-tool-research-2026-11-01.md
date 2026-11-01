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
