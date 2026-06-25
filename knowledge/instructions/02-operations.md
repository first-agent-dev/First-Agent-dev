# Руководство по эксплуатации First-Agent (Docker / AIO)

> Обновлено: 2026-06-17

Это полный практический мануал по развёртыванию, обновлению и администрированию
агента First-Agent на выделенном сервере (AIO — «всё в одном»). Здесь есть два
пути для каждой операции:

- **Авто** — готовые скрипты, которые делают всё за вас (рекомендуется).
- **Вручную** — пошаговые команды на случай, если скрипт не сработал.

---

## Содержание

1. [Что это и как устроено](#1-что-это-и-как-устроено)
2. [Глоссарий для новичка](#2-глоссарий-для-новичка)
3. [Первый запуск — кратко (полный гайд отдельно)](#3-первый-запуск--кратко-полный-гайд-отдельно)
4. [Ежедневное обновление и пересборка — авто](#4-ежедневное-обновление-и-пересборка--авто)
5. [Ежедневное обновление и пересборка — вручную](#5-ежедневное-обновление-и-пересборка--вручную)
6. [Управление сервисом и контейнером](#6-управление-сервисом-и-контейнером)
7. [Запуск задач агента](#7-запуск-задач-агента)
8. [Резервное копирование и восстановление](#8-резервное-копирование-и-восстановление)
9. [Безопасность и удалённый доступ](#9-безопасность-и-удалённый-доступ)
10. [Диагностика и типичные проблемы](#10-диагностика-и-типичные-проблемы)
11. [Шпаргалка](#11-шпаргалка)
12. [Справочник по скриптам](#12-справочник-по-скриптам)

---

## 1. Что это и как устроено

First-Agent работает не «голым процессом» на сервере, а внутри **Docker-контейнера**.
Представьте контейнер как изолированную коробку, в которой уже собрана вся среда
(Python, зависимости, сам агент). Это позволяет обновлять и перезапускать агента,
не трогая остальной сервер.

Развёртывание состоит из трёх слоёв:

```text
Сервер Ubuntu (AIO)
└── systemd user service: fa.service        ← автозапуск при загрузке
    └── docker compose                       ← оркестратор (ДВА контейнера)
        ├── контейнер: first-agent           ← сам агент (БЕЗ LLM-ключей)
        │   ├── /repo             → код хост-репозитория (bind-mount; READ-ONLY)
        │   ├── /sessions         → песочницы агента (bind-mount; RW; по одной на старт контейнера)
        │   ├── /home/fa/.fa      → постоянные данные/конфиг (кроме routing models.yaml)
        │   ├── /run/secrets/git_key + known_hosts → deploy-ключ (ro, ВНЕ /workspace)
        │   ├── /home/fa/.fa/models.yaml → /srv/first-agent/routing/models.yaml (ro)
        │   ├── /run/secrets/fa_proxy_token → токен fa→proxy (НЕ ключ; ro)
        │   ├── FA_EGRESS_PROXY_URL → агент ходит к провайдерам ТОЛЬКО через прокси
        │   └── fa-entrypoint.sh  → режим ожидания / разовый запуск задачи
        └── контейнер: fa-egress-proxy       ← граница LLM-ключей (ADR-12 Option C)
            ├── /run/secrets/fa.env → LLM API-ключи (ro; ТОЛЬКО здесь)
            ├── /etc/fa/models.yaml → тот же /srv/first-agent/routing/models.yaml (ro)
            │                          агент тоже видит файл ro, но не может его править
            ├── НЕТ /workspace и НЕТ PYTHONPATH=/workspace/src — прокси исполняет
            │   ТОЛЬКО неизменяемый код образа (агент не может подменить код прокси)
            └── инъецирует ключ вне досягаемости агента
```

Ключевые идеи, которые важно понять сразу:

- **Контейнер по умолчанию не «крутит» агента бесконечно.** Он стартует в
  режиме ожидания (stand-by) и ждёт, пока вы дадите ему задачу. Это сделано
  специально, чтобы политика автоперезапуска не запускала одну и ту же задачу
  в цикле.
- **Данные переживают пересборку.** Память агента, история и настройки лежат на
  хосте в `/srv/first-agent/state/`. Даже если удалить контейнер, данные
  останутся.
- **Код живёт на хосте**, в `/srv/first-agent/repo/First-Agent-dev/`, и
  «пробрасывается» внутрь контейнера. Поэтому правка исходников не всегда требует
  пересборки образа — а вот смена зависимостей или `Dockerfile.fa` требует.

Главные файлы (лежат в корне репозитория):

| Файл | Назначение |
|------|------------|
| `Dockerfile.fa` | Рецепт сборки образа контейнера (Ubuntu + Python + агент). |
| `docker-compose.fa.yml` | Описание запуска контейнера: лимиты, тома, сеть, healthcheck. |
| `/srv/first-agent/secrets/fa.env` | **API-ключи LLM** (на хосте, 0600, ВНЕ репозитория). Монтируется read-only **только в контейнер `fa-egress-proxy`** (`/run/secrets/fa.env`). Контейнер агента их НЕ видит; агент ходит к провайдерам через прокси, который подставляет ключ вне досягаемости агента (ADR-12 Option C). **Не коммитится.** |
| `/srv/first-agent/secrets/fa_proxy_token` | Токен fa→proxy (на хосте, 0600). Доказывает прокси, что вызов идёт от агента. **Не ключ** — утечка позволяет лишь платные вызовы через прокси, не раскрытие ключа. **Не коммитится.** |
| `.env.fa` | Только **несекретные** runtime-настройки (`FA_AUTO_RUN`, `FA_TASK`, …). API-ключей здесь больше нет. |
| `scripts/` | Скрипты установки, обновления, бэкапа и обслуживания. |


### 📂 Рабочие пространства (Workspace Isolation)

Начиная с ADR-13, агент **не меняет** исходный код в `/srv/first-agent/repo/First-Agent-dev`. Этот каталог монтируется в контейнер как `/repo` **read-only**.

- **Изоляция:** При каждом перезапуске контейнера (или старте первой задачи) автоматически создаётся изолированный клон хост-репозитория (`git clone --local`) в директории `/srv/first-agent/sessions/session-<ID>`.
- **Как это выглядит для агента:** Агент работает в этом изолированном клоне. Он может делать коммиты, создавать ветки и пушить их. Основной хост-репозиторий всегда остаётся чистым для `fa update`.
- **Доступ оператора:** Команда `fa shell` автоматически открывает `bash` внутри *активной* сессии агента, так что вам не нужно искать пути вручную.
- **fa stats:** Учитывайте, что `fa stats` по умолчанию показывает статистику только для *текущей* сессии. Если вам нужна статистика прошлой сессии, перейдите в её директорию (`cd /srv/first-agent/sessions/session-<ID>`) и запустите `fa stats` там.
- **Сброс сессии:** Если агент сильно "намусорил" или зашел в тупик — просто сделайте `fa restart` или `fa rebuild`. Контейнер перезапустится и создаст чистую сессию из актуального хост-репозитория.


### 📂 Рабочие пространства (Workspace Isolation)

Начиная с ADR-13, агент **не меняет** исходный код в `/srv/first-agent/repo/First-Agent-dev`. Этот каталог монтируется в контейнер как `/repo` **read-only**.

- **Изоляция:** При каждом перезапуске контейнера (или старте первой задачи) автоматически создаётся изолированный клон хост-репозитория (`git clone --local`) в директории `/srv/first-agent/sessions/session-<ID>`.
- **Как это выглядит для агента:** Агент работает в этом изолированном клоне. Он может делать коммиты, создавать ветки и пушить их. Основной хост-репозиторий всегда остаётся чистым для `fa update`.
- **Доступ оператора:** Команда `fa shell` автоматически открывает `bash` внутри *активной* сессии агента, так что вам не нужно искать пути вручную.
- **fa stats:** Учитывайте, что `fa stats` по умолчанию показывает статистику только для *текущей* сессии. Если вам нужна статистика прошлой сессии, перейдите в её директорию (`cd /srv/first-agent/sessions/session-<ID>`) и запустите `fa stats` там.
- **Сброс сессии:** Если агент сильно "намусорил" или зашел в тупик — просто сделайте `fa restart` или `fa rebuild`. Контейнер перезапустится и создаст чистую сессию из актуального хост-репозитория.

### 🔒 Где живут API-ключи и почему агент их не видит

LLM API-ключи хранятся **только** в `/srv/first-agent/secrets/fa.env` (на хосте,
права `0600`, вне репозитория) и монтируются read-only **только в контейнер
`fa-egress-proxy`**. Контейнер агента (`first-agent`) их вообще не монтирует и не
получает. Архитектура (ADR-12, Option C — egress-injection proxy):

```text
first-agent (агент + fs.run_bash)            fa-egress-proxy (ОТДЕЛЬНЫЙ контейнер)
  ProviderChain.base_url = ──── HTTP ───────►  читает /run/secrets/fa.env (ro)
    http://fa-egress-proxy:8080/route/<имя>    подставляет реальный ключ в заголовок
  шлёт X-FA-Proxy-Token (НЕ ключ)   ◄────────  форвардит провайдеру, отдаёт ответ
  ключей нет ни в файле, ни в env, ни в RAM    /workspace и кода агента здесь нет
```

Почему это надёжно (барьеры, каждый закреплён тестом):

1. **LLM-ключи отсутствуют у агента (основной барьер).** Ключ есть только в
   памяти процесса `fa-egress-proxy` — в **другом контейнере**. `fs.run_bash`
   агента не может прочитать ни файловую систему, ни память другого контейнера
   (разные mount/PID-неймспейсы). Даже полностью скомпрометированный агент может
   *воспользоваться* ключом (сделать запрос через прокси), но не может его
   *прочитать*. Граница — это изоляция контейнеров, а не трюк с uid, поэтому
   агенту не нужен root.
2. **Запрет на чтение секретных путей в bash (защита deploy-ключа + DiD).**
   `fs.read_file` ограничен path-containment. Для `fs.run_bash` read-команды
   (`cat`/`grep`/`dd`/`xxd`/…) раньше обходили containment — теперь bash-gate
   fail-closed отклоняет любую команду, читающую `/run/secrets`,
   `/srv/first-agent/secrets` или `~/.fa/.env` (`src/fa/sandbox/secret_paths.py`).
3. **Редактирование вывода к модели.** Любой результат инструмента проходит через
   единую точку редактирования перед отправкой в LLM
   (`coder_loop._redact`) — известное секретное значение маскируется в сыром,
   base64, hex, url- и реверс-виде. Если модель его не видит, она не сможет его
   повторить.
4. **Очищенное окружение bash.** `fs.run_bash` запускается с allowlist-окружением
   (без любых `*_API_KEY`/`*_TOKEN`/…), так что дочерние процессы ничего не
   наследуют.

**Редактировать ключи** (на хосте, редактором `micro`):

```bash
micro /srv/first-agent/secrets/fa.env        # вписать/изменить LLM API-ключи (читает ТОЛЬКО прокси)
systemctl --user restart fa.service          # пересоздать стек (прокси подхватит ключи)
```

> `config.yaml`, `models.yaml` (роли, схемы запросов к провайдерам) и `.env.fa`
> (несекретные `FA_*`) редактируются так же — на хосте. Спрашивать у агента про
> роли/схему запроса можно; сами ключи он физически не достанет.
>
> 📍 **Где какой файл лежит на хосте** (контейнер монтирует `state` как `~/.fa`):
>
> - `config.yaml` (опциональные capability-флаги) → `/srv/first-agent/state/config.yaml`
>   (читается как `~/.fa/config.yaml`). Файл **необязателен**: его отсутствие = все
>   флаги `false` (безопасный deny-by-default). Создавайте только чтобы что-то
>   включить — шаблон: [`knowledge/examples/config.yaml.example`](../examples/config.yaml.example).
> - `models.yaml` (маршрутизация) → `/srv/first-agent/routing/models.yaml` (см. ниже).
> - `.env.fa` (несекретные `FA_*`) → `/srv/first-agent/repo/First-Agent-dev/.env.fa`.
>
> Не uid 1000 на хосте? Тогда правка через `sudo micro <путь>`.
>
> ⚠️ **Источник истины для маршрутизации — `/srv/first-agent/routing/models.yaml`**
> (его и правьте). И агент, и прокси монтируют один и тот же файл read-only;
> отдельной копии `proxy/models.yaml` больше нет. Прокси загружает таблицу
> маршрутов **на старте**, поэтому после правки `routing/models.yaml` нужен
> restart/recreate прокси. Рекомендуемый путь — `fa-update.sh` (он заметит
> изменение routing-файла по hash и пересоздаст контейнеры). Ручной путь:
>
> ```bash
> cd /srv/first-agent/repo/First-Agent-dev
> docker compose -f docker-compose.fa.yml up -d --force-recreate fa-egress-proxy first-agent
> ```
>
> При первом обновлении после перехода на единый routing-файл скрипты мигрируют
> legacy `/srv/first-agent/state/models.yaml` или
> `/srv/first-agent/proxy/models.yaml` в `/srv/first-agent/routing/models.yaml`,
> если новый файл ещё не существует. После миграции legacy-файлы игнорируются.
> Если обновляетесь с очень старого checkout, где `fa-update.sh` ещё не умеет
> re-exec после `git pull`, для этого перехода надёжнее использовать
> `scripts/fa-clean-rebuild.sh` (он перезапускает себя после обновления) либо
> предварительно создать `/srv/first-agent/routing/models.yaml` вручную.
>
> **Остаточный риск (честно):** deploy-ключ git живёт в контейнере агента (нужен
> для `git push`). Барьеры 2–3 его защищают, но 100%-ную гарантию даст только
> «ограниченный git-интерфейс» — см. BACKLOG I-24. У LLM-ключей этого риска нет
> (их в контейнере агента нет вообще).

---

## 2. Глоссарий для новичка

Если вы никогда не работали с Docker — прочитайте эту таблицу один раз, дальше
будет понятнее.

| Термин | Простыми словами |
|--------|------------------|
| **Образ (image)** | «Слепок» готовой среды. Из него создаются контейнеры. |
| **Контейнер (container)** | Запущенный экземпляр образа — изолированная «коробка» с программой. |
| **`docker compose`** | Инструмент, который запускает контейнер по описанию из `docker-compose.fa.yml`. |
| **Сборка (build)** | Создание образа из `Dockerfile.fa`. Нужна при смене зависимостей. |
| **bind-mount / том (volume)** | «Окно» из папки хоста внутрь контейнера. Через него данные сохраняются. |
| **healthcheck** | Автопроверка «жив ли агент». Контейнер бывает `healthy` / `unhealthy`. |
| **systemd / сервис** | Менеджер автозапуска: поднимает контейнер при загрузке сервера. |
| **Tailscale** | Частная VPN-сеть. Через неё вы безопасно заходите на сервер. |
| **deploy key** | SSH-ключ, которым контейнер пушит код в GitHub. |
| **`-d` (detached)** | «Фоновый режим» — контейнер работает, консоль свободна. |
| **`-f файл`** | Указывает, какой compose-файл использовать (`-f docker-compose.fa.yml`). |

> Подсказка: почти все команды ниже запускаются из папки проекта. Перейдите в неё
> один раз и оставайтесь там:
>
> ```bash
> cd /srv/first-agent/repo/First-Agent-dev
> ```
>
> `cd` (change directory) — это просто «зайти в папку».

---

## 3. Первый запуск — кратко (полный гайд отдельно)

> Это руководство — про **повседневную эксплуатацию уже развёрнутого** агента.
> Полная пошаговая установка с нуля (BIOS → Ubuntu → Docker → Tailscale →
> deploy-ключ → первый запуск) **[`01-install.md`](./01-install.md)**.

Если коротко, первичное развёртывание — это **два скрипта и три ручных шага**
между ними (полностью «в один клик» нельзя без потери безопасности: deploy-ключ,
авторизация Tailscale и API-ключи требуют участия человека):

```text
[Скрипт 1] setup-fa-desktop.sh   ← система, Docker, Tailscale, клон репозитория
        │
        ▼
[Ручные шаги]  1) добавить deploy-ключ на GitHub (write access)
               2) sudo tailscale up --ssh   (авторизация в браузере)
               3) вписать API-ключи в /srv/first-agent/secrets/fa.env
        │
        ▼
[Скрипт 2] fa-post-setup.sh      ← сборка, проверка git push, запуск сервиса
```

Шпаргалка команд (подробности и пояснения — в [`01-install.md`](./01-install.md)):

```bash
bash scripts/setup-fa-desktop.sh
# 1) deploy-ключ на GitHub:  cat /srv/first-agent/secrets/github_deploy_key.pub
# 2) sudo tailscale up --ssh
# 3) micro /srv/first-agent/secrets/fa.env   (вписать API-ключи; вне /workspace)
# перелогиниться (применить группу docker), затем:
bash scripts/fa-post-setup.sh
docker ps    # должен быть контейнер first-agent в статусе Up ...
```

---

## 4. Ежедневное обновление и пересборка — авто

Когда в `main` на GitHub появился новый код, обновите деплой одной командой.
Это **главный сценарий повседневного администрирования.**

```bash
/srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

> Что делает `fa-update.sh` (по шагам, безопасно и предсказуемо):
>
> 1. **Preflight** — проверяет наличие команд, что Docker жив и есть место на диске.
> 2. **Git-обновление** — переключается на `main` и делает `git pull --ff-only`.
>    Если в рабочем дереве есть несохранённые правки — **останавливается**, чтобы
>    ничего не затереть (см. флаг `AUTO_STASH`).
> 3. **Анализ изменений** — сам решает, что нужно: только перезапуск или полная
>    пересборка (пересборка — если поменялись `Dockerfile.fa`, `uv.lock`,
>    `pyproject.toml`, `docker-compose.fa.yml`, `.dockerignore` или
>    `fa-entrypoint.sh`). Если изменений нет — ничего не делает.
> 4. **Проверка `.env.fa`** — если файл изменился, контейнер будет пересоздан,
>    чтобы подхватить новые переменные.
> 5. **Сборка и деплой**, затем **ожидание `healthy`**.
> 6. **Smoke-тесты** (быстрая проверка, что `fa` и импорты работают) и **pytest**
>    внутри контейнера (необязательные — не валят обновление).
> 7. **Очистка** старых образов.
>
> Скрипт защищён блокировкой (нельзя запустить две копии сразу) и ведёт лог в
> `/tmp/fa-update.log`.

### Полезные флаги (переменные окружения)

Указываются перед командой. Можно комбинировать.

| Команда | Когда использовать |
|---------|--------------------|
| `SKIP_TESTS=1 .../fa-update.sh` | Быстро обновить без прогона pytest. |
| `AUTO_STASH=1 .../fa-update.sh` | Автоматически отложить локальные правки перед обновлением. |
| `NO_CACHE=1 .../fa-update.sh` | Чистая пересборка «с нуля», игнорируя кэш слоёв. |
| `SKIP_UV_SYNC=1 .../fa-update.sh` | Не синхронизировать dev-зависимости перед тестами. |
| `PRUNE=0 .../fa-update.sh` | Не удалять старые образы после обновления. |
| `HEALTH_TIMEOUT_SECONDS=120 .../fa-update.sh` | Дать контейнеру больше времени стать `healthy`. |

Примеры:

```bash
# Обычное обновление
/srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh

# Быстро, без тестов, с авто-stash локальных изменений
SKIP_TESTS=1 AUTO_STASH=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh

# Полная чистая пересборка (например, после крупного апгрейда зависимостей)
NO_CACHE=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

> Важно: `fa-update.sh` всегда работает с веткой `main`. Для тестирования
> feature-ветки не используйте его — переключайтесь на ветку вручную (см. раздел 5).

---

## 5. Ежедневное обновление и пересборка — вручную

Используйте этот путь, если `fa-update.sh` по какой-то причине не отрабатывает
(конфликт версий, тест другой ветки, отладка). Все команды — из папки проекта.

```bash
cd /srv/first-agent/repo/First-Agent-dev
```

**1. Остановить контейнер** (данные при этом не теряются):

```bash
docker compose -f docker-compose.fa.yml down
```

> `down` аккуратно «тушит» контейнер. Тома с данными остаются на хосте.

**2. Скачать свежий код с GitHub:**

```bash
git pull origin main
```

> Если git ругается на несохранённые изменения (`working tree dirty`) — либо
> сохраните их (`git stash`), либо сбросьте: `git reset --hard HEAD`
> (осторожно — это удалит незакоммиченные правки).

**3. Пересобрать образ** (нужно, если менялись зависимости или `Dockerfile.fa`):

```bash
docker compose -f docker-compose.fa.yml build --no-cache
```

> `--no-cache` заставляет Docker собрать всё заново, игнорируя сохранённый кэш.
> Дольше, но гарантирует чистую сборку. Если зависимости не менялись, флаг можно
> опустить — будет быстрее.

**4. Запустить контейнер в фоне:**

```bash
docker compose -f docker-compose.fa.yml up -d --force-recreate
```

> `-d` — фоновый режим. `--force-recreate` пересоздаёт контейнер, чтобы он
> гарантированно подхватил новый образ и свежий `.env.fa`.

**5. Проверить, что всё поднялось:**

```bash
docker ps
docker compose -f docker-compose.fa.yml logs --tail=50
```

> Дождитесь в `docker ps` статуса `healthy` (может занять до минуты).

**Минимальный «жёсткий» перезапуск** (если агент завис, без обновления кода):

```bash
docker compose -f docker-compose.fa.yml down
docker compose -f docker-compose.fa.yml up -d
```

---

## 6. Управление сервисом и контейнером

Стек поднимается **`docker compose`**, а **systemd** добавляет автозапуск при
перезагрузке. Запомните разделение:

- **Поднять/обновить стек прямо сейчас** → `docker compose ... up -d` (основной
  способ; идемпотентен, не зависит от user-сессии / D-Bus / linger).
- **Автозапуск при ребуте** → один раз настроить `fa.service` (ниже).

> Почему compose — основной: контейнер живёт постоянно в режиме ожидания
> (`restart: unless-stopped`), а задачи запускаются в него через
> `docker compose exec` (а в будущем — через WebUI-бэкенд). `docker compose
> up -d` срабатывает всегда; `systemctl --user start` молча НЕ поднимет стек,
> если user-сервис не загружен (нет linger / не было `daemon-reload`) — частая
> засада.

**Поднять стек (всегда работает):**

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml up -d
docker compose -f docker-compose.fa.yml ps   # дождитесь: ОБА контейнера healthy
                                             # (сначала fa-egress-proxy, затем first-agent)
```

**Первичная настройка автозапуска (один раз, от пользователя `fa`):**
`setup-fa-desktop.sh` устанавливает юнит, но НЕ включает его (и предупреждает,
если не было user-сессии для `daemon-reload`). Завершите вручную:

```bash
loginctl enable-linger fa                # чтобы user-сервис жил без активной сессии
systemctl --user daemon-reload
systemctl --user enable fa.service       # автозапуск при загрузке
systemctl --user start  fa.service       # поднять сейчас
systemctl --user status fa.service       # ожидаем: active (exited), RemainAfterExit
```

> Если `systemctl --user` отвечает `Failed to connect to bus` — нет активной
> user-сессии: выполните `loginctl enable-linger fa`, затем зайдите по SSH
> заново как `fa` (полноценный логин) и повторите. До настройки автозапуска
> просто пользуйтесь `docker compose up -d`.

**Повседневное управление сервисом** (после настройки автозапуска):

```bash
systemctl --user status  fa.service   # текущее состояние
systemctl --user restart fa.service   # перезапустить (down + up -d; перечитает .env.fa)
systemctl --user stop    fa.service   # остановить
systemctl --user start   fa.service   # запустить
```

> После правки `.env.fa` достаточно `systemctl --user restart fa.service` —
> сервис выполняет `down` + `up -d`, пересоздаёт контейнер и перечитывает
> окружение. (Не путайте с `docker compose restart`, который окружение **не**
> перечитывает — см. раздел 7.3.) Эквивалент без systemd:
> `docker compose -f docker-compose.fa.yml up -d --force-recreate`.

Прямая работа с контейнером (для диагностики):

```bash
cd /srv/first-agent/repo/First-Agent-dev

docker ps                                              # запущенные контейнеры
docker compose -f docker-compose.fa.yml logs -f        # логи в реальном времени
docker exec -it first-agent bash                        # войти внутрь контейнера
```

> `logs -f` (follow) — поток логов вживую. Выйти из просмотра: `Ctrl+C` (агент
> при этом продолжит работать). Войдя внутрь через `docker exec`, выйти обратно:
> наберите `exit`.

Освободить место от мусора Docker (старые образы и слои):

```bash
docker system prune -f
```

> Запущенные контейнеры не пострадают. `setup-fa-desktop.sh` уже ставит
> еженедельную авто-очистку, но иногда полезно запустить вручную.

### 6.1. Чистая переустановка стека (снести контейнеры → собрать заново)

Когда нужно: после крупного апгрейда, «застрявшего» состояния, или просто чтобы
получить заведомо чистый стек. **Данные и ключи при этом сохраняются** — они
живут в host bind-mount'ах `/srv/first-agent/{state,routing,secrets}`, а не в контейнерах.

**Способ А — скрипт (рекомендуется).** Идемпотентный: **обновляет локальный репо
до `main`** (`git pull --ff-only` и перезапускает себя обновлённой версией),
делает бэкап, сносит контейнеры, пересобирает `--no-cache`, поднимает оба
контейнера и проверяет изоляцию секретов:

```bash
# Снести контейнеры + образы, обновить репо до main, пересобрать с нуля.
# Ключи и routing/models.yaml остаются.
/srv/first-agent/repo/First-Agent-dev/scripts/fa-clean-rebuild.sh

# Дополнительно сбросить state и routing/models.yaml — КЛЮЧИ остаются.
# Скрипт пересоздаст шаблон routing/models.yaml, его нужно будет заполнить.
WIPE_STATE=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-clean-rebuild.sh
```

> **Bootstrap на старом сервере:** если на машине ещё СТАРАЯ версия репо (этого
> скрипта/шага обновления там нет) — один раз обновите репо вручную, потом
> запустите скрипт:
>
> ```bash
> cd /srv/first-agent/repo/First-Agent-dev && git pull --ff-only origin main
> scripts/fa-clean-rebuild.sh
> ```

> Флаги: `WIPE_STATE=1` — сбросить весь `state/` (ключи в `secrets/` не трогаются);
> `PRUNE=1` — удалить все неиспользуемые образы и кэш сборки; `NO_BACKUP=1` —
> пропустить бэкап (не рекомендуется); `ASSUME_YES=1` — не спрашивать
> подтверждение для разрушающих флагов (нужно без TTY/из cron); `SKIP_UPDATE=1` —
> не трогать репо (использовать как есть); `AUTO_STASH=1` — отложить локальные
> правки перед `git pull` (иначе скрипт остановится). Скрипт **никогда** не
> удаляет `secrets/` и **не** запускает `setup-fa-desktop.sh` (тот
> переустанавливает весь хост) — только обновляет репо, пересоздаёт контейнеры
> и, при `WIPE_STATE=1`, шаблон `routing/models.yaml`.

**Способ Б — вручную** (если хотите контролировать каждый шаг):

```bash
cd /srv/first-agent/repo/First-Agent-dev

# 0) бэкап (на всякий случай)
TS=$(date +%Y%m%d-%H%M%S); sudo cp -a /srv/first-agent/state ~/fa-bk-$TS-state; sudo cp -a /srv/first-agent/routing ~/fa-bk-$TS-routing; sudo cp -a /srv/first-agent/secrets ~/fa-bk-$TS-secrets

# 1) обновить репо до main (чистая установка = последняя версия кода/compose)
git fetch origin && git switch main && git pull --ff-only origin main

# 2) остановить сервис и снести контейнеры
systemctl --user stop fa.service
docker compose -f docker-compose.fa.yml down --remove-orphans

# 3) (опц.) сбросить state — КЛЮЧИ В secrets/ НЕ ТРОГАЕМ
sudo rm -rf /srv/first-agent/state/*

# 4) догенерировать proxy-токен, если его нет (ключи сохраняются)
test -s /srv/first-agent/secrets/fa_proxy_token || \
  { head -c 32 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=' | \
    sudo tee /srv/first-agent/secrets/fa_proxy_token >/dev/null; \
    sudo chmod 600 /srv/first-agent/secrets/fa_proxy_token; }
# (если сбрасывали routing — создайте models.yaml из примера:)
# sudo mkdir -p /srv/first-agent/routing
# sudo cp knowledge/examples/models.yaml.example /srv/first-agent/routing/models.yaml

# 5) чистая пересборка и подъём двух контейнеров
docker compose -f docker-compose.fa.yml build --no-cache
docker compose -f docker-compose.fa.yml up -d
docker compose -f docker-compose.fa.yml ps        # ждём fa-egress-proxy = healthy, затем first-agent

# 6) вернуть автозапуск
systemctl --user start fa.service
```

> **Полностью «с нуля», включая ключи** (придётся заново вписать LLM-ключи и
> заново зарегистрировать deploy key на GitHub) — только сознательно:
> `sudo rm -rf /srv/first-agent/secrets/*` перед шагом 3. В обычной «чистой
> переустановке» этого делать НЕ нужно.

**Проверка изоляции после подъёма** (у агента не должно быть LLM-ключа):

```bash
docker exec first-agent sh -c 'cat /run/secrets/fa.env 2>&1 || echo "у агента ключей нет — OK"'
docker exec fa-egress-proxy sh -c 'test -s /run/secrets/fa.env && echo "ключи у прокси — OK"'
```

---

## 7. Запуск задач агента

Контейнер по умолчанию — это **готовая среда** (режим ожидания), а не вечно
работающий агент. Задачи запускаются командой `fa run` **внутри уже поднятого**
контейнера.

> **Сначала убедитесь, что стек запущен.** `docker compose exec` работает только
> с РАБОТАЮЩИМ контейнером и сам его не поднимает. Если видите
> `service "first-agent" is not running` — стек не запущен (см. §6 «Поднять
> стек» или troubleshooting в §10):
>
> ```bash
> cd /srv/first-agent/repo/First-Agent-dev
> docker compose -f docker-compose.fa.yml up -d
> docker compose -f docker-compose.fa.yml ps   # дождитесь: оба healthy
> ```

### 7.1. Ручной запуск (рекомендуется для интерактивной работы)

```bash
cd /srv/first-agent/repo/First-Agent-dev
# одноразовый вывод (для скриптов/CI):
docker compose -f docker-compose.fa.yml exec -T first-agent \
    fa run --role coder --task "Опишите задачу здесь"

# интерактивно (живой TTY) — уберите -T:
docker compose -f docker-compose.fa.yml exec first-agent \
    fa run --role coder --task "Опишите задачу здесь"
```

### 7.2. Workflow из трёх ролей (planner → coder → eval)

Каждая команда — это отдельный вызов LLM. Связываются через общий `--run-id`.

```bash
cd /srv/first-agent/repo/First-Agent-dev
CF="docker-compose.fa.yml"

# Планировщик
docker compose -f $CF exec -T first-agent \
    fa run --role planner --workspace /workspace --run-id work-1 --task "Спланируй X"

# Кодер (продолжает черновик планировщика)
docker compose -f $CF exec -T first-agent \
    fa run --role coder --workspace /workspace --run-id work-1 --resume --task "Реализуй X"

# Проверяющий (верифицирует работу кодера)
docker compose -f $CF exec -T first-agent \
    fa run --role eval --workspace /workspace --run-id work-1 --resume --task "Проверь X"
```

### 7.3. Авто-запуск одной задачи при старте контейнера

Полезно для разовых пакетных заданий. Включается **только** при `FA_AUTO_RUN=1`
(иначе из-за политики автоперезапуска задача крутилась бы в цикле).

Впишите в `.env.fa`:

```env
FA_AUTO_RUN=1
FA_TASK=Реализуй то, что описано в задаче
FA_ROLE=coder
FA_RUN_ID=batch-1
```

Затем **пересоздайте** контейнер и проверьте результат:

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml up -d --force-recreate
docker compose -f docker-compose.fa.yml exec -T first-agent \
    cat /workspace/.fa/entrypoint-status.txt
```

> Важно: именно `up -d --force-recreate`, а **не** `restart`. Команда `restart`
> только перезапускает контейнер со старым окружением и **не перечитывает**
> `.env.fa`; новые переменные подхватываются лишь при пересоздании контейнера
> (`up`). То же касается любого изменения `.env.fa` (см. раздел 10).
>
> Задаётся **либо** `FA_TASK` (текст), **либо** `FA_TASK_FILE` (путь к файлу
> внутри `/workspace`), но не оба сразу. После выполнения контейнер переходит в
> режим ожидания, оставаясь доступным для осмотра.

---

## 8. Резервное копирование и восстановление

Бэкапы делает скрипт `backup-fa.sh` через **restic** в облако Backblaze B2.
`setup-fa-desktop.sh`/`fa-post-setup.sh` ставят его в cron на каждую ночь.

### Что и где

- **Данные агента**: `/srv/first-agent/state/` (память, история, конфиг).
- **Секреты**: `/srv/first-agent/secrets/` (deploy-ключ, креды бэкапа).
- **Лог бэкапа**: `/srv/first-agent/backup/backup.log`.

### Настройка (один раз)

```bash
micro /srv/first-agent/secrets/backup.env
```

> Впишите реальные `B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET` вместо
> `CHANGEME`. Это ключи приложения Backblaze B2 с доступом на чтение/запись.

Инициализировать хранилище (только при первом использовании):

```bash
source /srv/first-agent/secrets/backup.env
export AWS_ACCESS_KEY_ID="$B2_KEY_ID" AWS_SECRET_ACCESS_KEY="$B2_APPLICATION_KEY"
restic -r "s3:https://s3.us-west-004.backblazeb2.com/$B2_BUCKET" init
```

### Ручной бэкап

```bash
/srv/first-agent/scripts/backup-fa.sh
```

> Скрипт сам делает бэкап и применяет политику хранения: 7 дневных, 4 недельных
> и 6 месячных копий.

### Восстановление (проверяйте хотя бы раз в квартал)

```bash
source /srv/first-agent/secrets/backup.env
export AWS_ACCESS_KEY_ID="$B2_KEY_ID" AWS_SECRET_ACCESS_KEY="$B2_APPLICATION_KEY"
RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/$B2_BUCKET"

restic -r "$RESTIC_REPO" snapshots                       # список копий
restic -r "$RESTIC_REPO" restore latest --target /tmp/restore-test
```

> `restore latest` достаёт последнюю копию в указанную папку. Проверьте, что
> файлы на месте, прежде чем доверять бэкапу.

---

## 9. Безопасность и удалённый доступ

Удалённый доступ к серверу настроен так, что SSH доступен **только через
Tailscale** (вашу частную сеть), а не из открытого интернета.

- **Повседневный доступ к агенту** с любого устройства — через Tailscale SSH:
  установите Tailscale на устройство, войдите в тот же аккаунт и подключайтесь
  (`ssh <user>@<имя-или-100.x-адрес-сервера>`). Ключи копировать не нужно.
- **Углублённое усиление защиты** (firewall, fail2ban, защита от блокировки
  самого себя) реализовано отдельным набором идемпотентных скриптов с подробным
  руководством:

  ```text
  scripts/ssh-tailscale/README.md
  ```

> Подробные пошаговые инструкции по hardening здесь не дублируются специально —
> чтобы не было двух источников правды. Открывайте
> [`scripts/ssh-tailscale/README.md`](../../scripts/ssh-tailscale/README.md): там
> описан безопасный порядок запуска `00-failsafe → 10-diagnose → 20-harden →
> 30-verify`, восстановление при блокировке и Tailscale ACL.

---

## 10. Диагностика и типичные проблемы

### `service "first-agent" is not running` при `docker compose exec` / `fa run`

Самая частая первая ошибка. Значит **стек не запущен** — `exec` требует уже
работающий контейнер и сам его не поднимает.

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml ps        # пусто/Exited → стек не поднят
docker compose -f docker-compose.fa.yml up -d     # поднять (основной способ)
docker compose -f docker-compose.fa.yml ps        # дождитесь: оба healthy
```

> Подвох: `systemctl --user start fa.service` может завершиться БЕЗ ошибки, но
> ничего не поднять, если user-сервис не загружен (нет linger / не было
> `daemon-reload` — см. предупреждения `setup-fa-desktop.sh`). Поэтому для
> «просто подними стек» используйте `docker compose up -d`; systemd настраивайте
> один раз для автозапуска при ребуте (§6).

### Контейнер не становится healthy

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker ps
docker inspect first-agent --format='{{json .State.Health}}'
docker compose -f docker-compose.fa.yml logs --tail=200 first-agent
```

> Смотрите последние строки логов — обычно там видно причину (нехватка памяти
> `OOM`, ошибка конфигурации, отсутствующий API-ключ).

### Внутри контейнера не находится команда `fa`

```bash
docker exec first-agent bash -lc 'echo $PATH && which fa && fa --version'
```

Если не находит — пересоберите образ:

```bash
docker compose -f docker-compose.fa.yml build --no-cache
docker compose -f docker-compose.fa.yml up -d --force-recreate
```

### Изменил `.env.fa`, но контейнер не видит изменений

Контейнер читает переменные при старте. Нужно его **пересоздать**:

```bash
docker compose -f docker-compose.fa.yml up -d --force-recreate
```

или просто запустите `scripts/fa-update.sh` — он сделает это сам.

### `chain_exhausted`, а в логах прокси `status=200`

Сначала исключите routing/key drift:

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml exec -T first-agent fa selfcheck
```

Если `fa selfcheck` показывает missing route или `has_key=false` — чините
проблему из его сообщения. Если `fa selfcheck` OK, запустите `fa probe`:

```bash
fa probe --role planner
```

Probe делает реальный API-вызов (~10 токенов) и покажет точную ошибку от
провайдера (404 модель не найдена, 401 ключ невалиден, timeout и т.д.).

Если probe OK, но `fa run` всё равно падает
с `chain_exhausted`, посмотрите логи прокси:

```bash
docker compose -f docker-compose.fa.yml logs --tail=200 fa-egress-proxy
```

Строка вида:

```text
egress-proxy route=<route> status=200 ms=<...>
```

означает только то, что upstream HTTP-запрос до провайдера вернулся с HTTP 200.
Это **не** гарантирует, что provider adapter получил валидный JSON-ответ нужной
схемы. `UrllibTransport` намеренно нормализует non-JSON / non-object JSON body
в `{}`; декодер не меняйте — это fail-closed дизайн.

Частые причины:

- неверный `slug`;
- wrong `base_url` / endpoint;
- провайдер вернул HTML/plaintext landing page;
- OpenAI-compatible adapter направлен на не-OpenAI-compatible endpoint;
- Anthropic/OpenAI request/response shape mismatch.

Что проверить:

```bash
micro /srv/first-agent/routing/models.yaml
docker compose -f docker-compose.fa.yml exec -T first-agent fa selfcheck
```

Если route есть и `has_key=true`, проверьте `provider`, `slug`, `base_url` и
adapter compatibility.

### Auto-run не стартует

```bash
docker exec first-agent env | grep '^FA_'
docker exec first-agent cat /workspace/.fa/entrypoint-status.txt
```

> Убедитесь, что задан `FA_AUTO_RUN=1` и ровно один источник задачи (`FA_TASK`
> **или** `FA_TASK_FILE`).

### Git push из контейнера не работает

```bash
docker exec -it first-agent bash -lc 'cd /workspace && echo "$GIT_SSH_COMMAND" && git ls-remote origin'
ls -l /srv/first-agent/secrets/github_deploy_key
ls -l /srv/first-agent/secrets/known_hosts
```

> Чаще всего причина: deploy-ключ не добавлен на GitHub с правом **write**, либо
> Tailscale не поднят (`sudo tailscale up --ssh`).

### `fa-update.sh` пишет «working tree dirty»

Вы (или агент) изменили файлы, и git отказывается их затирать. Варианты:

```bash
cd /srv/first-agent/repo/First-Agent-dev
git status                       # посмотреть, что изменилось
git stash                        # временно отложить изменения
# или, если изменения не нужны:
git reset --hard HEAD
```

Либо запустите обновление с авто-stash: `AUTO_STASH=1 .../fa-update.sh`.

### Docker отвечает «permission denied»

Ваш пользователь ещё не в группе `docker`. Выйдите из системы и зайдите снова
(или перезагрузитесь). Проверка: `id -nG | grep -w docker`.

### Агент завис / бесконечные ошибки / `OOM`

Скорее всего не хватило оперативной памяти. Сделайте жёсткий перезапуск
(раздел 5, минимальный перезапуск) и проверьте логи.

---

## 11. Шпаргалка

Все команды предполагают, что вы в папке проекта
(`cd /srv/first-agent/repo/First-Agent-dev`), либо используйте полные пути.

### Первый деплой

```bash
bash scripts/setup-fa-desktop.sh
# 1) добавить deploy-ключ на GitHub (write access)
# 2) sudo tailscale up --ssh
# 3) micro /srv/first-agent/secrets/fa.env   (вписать API-ключи)
# перелогиниться (группа docker), затем:
bash scripts/fa-post-setup.sh
```

### Обновить деплой (авто)

```bash
/srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

### Обновить деплой (вручную)

```bash
docker compose -f docker-compose.fa.yml down
git pull origin main
docker compose -f docker-compose.fa.yml build --no-cache
docker compose -f docker-compose.fa.yml up -d --force-recreate
```

### Сервис

```bash
systemctl --user status  fa.service
systemctl --user restart fa.service
```

### Удобный запуск из консоли хоста

Вместо длинного `docker compose -f docker-compose.fa.yml exec -T first-agent fa ...`
можно использовать wrapper-скрипт `scripts/fa`:

```bash
# Установка (одноразово):
sudo ln -sf /srv/first-agent/repo/First-Agent-dev/scripts/fa /usr/local/bin/fa

# После этого:
fa selfcheck --role planner     # вместо docker compose exec ... fa selfcheck ...
fa probe --role planner          # liveness-тест (~10 токенов)
fa run --role coder --task "..."
fa logs -f --tail=50             # логи agent-контейнера
fa proxy-logs -f                 # логи прокси
fa status                        # docker compose ps
fa restart                       # restart обоих контейнеров
fa rebuild                       # пересборка образов
fa shell                         # bash внутри контейнера
```

Все команды `fa`, которые не являются инфраструктурными (logs, status, up,
down, restart, rebuild, shell), автоматически передаются внутрь контейнера.
Новые Python-подкоманды (добавленные в `src/fa/cli.py`) работают через
wrapper без его изменения.

### Проверка доступности провайдера (liveness probe)

`fa selfcheck` проверяет конфигурацию и роутинг, но **не делает реальный
API-вызов**. Если модель временно недоступна (404 от Fireworks), selfcheck
покажет OK, а `fa run` упадёт с `chain_exhausted`.

Для проверки доступности используйте `fa probe`:

```bash
fa probe --role planner        # тест одной роли
fa probe --all-roles           # тест всех ролей из models.yaml
fa probe --role planner --timeout 60  # с увеличенным таймаутом
```

Probe делает минимальный API-вызов (~10 токенов) и показывает результат:
- ✅ — модель доступна, ключ валиден, с таймингом и токенами
- ❌ — с HTTP-статусом и ошибкой для каждого entry в chain

**Порядок диагностики:** `fa selfcheck` (бесплатно) → `fa probe`
(~10 токенов) → `fa run`.

### Логи и вход внутрь

```bash
fa logs -f                       # или: docker compose ... logs -f first-agent
fa proxy-logs -f                 # или: docker compose ... logs -f fa-egress-proxy
fa shell                         # или: docker exec -it first-agent bash
```

### Запуск задачи

```bash
fa run --role coder --task "..."
# или полная форма:
docker compose -f docker-compose.fa.yml exec -T first-agent \
    fa run --role coder --task "..."
```

### Уровни детализации вывода

`fa run` показывает прогресс в реальном времени на stderr:

```bash
# Стандартный вывод (по умолчанию):
fa run --role coder --task "..."

# Минимальный (только заголовки и итог):
fa run --role coder --task "..." --detail minimal

# Подробный (+ тайминги, токены, параметры инструментов):
fa run --role coder --task "..." --detail verbose

# Отладочный (+ текст модели):
fa run --role coder --task "..." --detail debug

# Без цвета (для логирования):
fa run --role coder --task "..." --no-color

# Тихий режим (только финальный ответ):
fa run --role coder --task "..." --output-mode quiet
```

Прогресс идёт в stderr — `fa run --task "..." > result.txt` сохраняет
только финальный ответ.

### Бэкап

```bash
/srv/first-agent/scripts/backup-fa.sh
```

---

## 12. Справочник по скриптам

Все скрипты лежат в `scripts/`. Идемпотентны (безопасно перезапускать).

| Скрипт | Что делает | Когда запускать |
|--------|------------|------------------|
| `setup-fa-desktop.sh` | Bootstrap хоста: система, Docker, Tailscale, репо, ключи, сервис. | Первый деплой, шаг 1. |
| `fa-post-setup.sh` | Сборка, проверка git push, запуск сервиса, cron бэкапа. | Первый деплой, шаг 2. |
| `fa-update.sh` | Умное обновление/пересборка с проверкой здоровья и тестами. | Каждое обновление. |
| `backup-fa.sh` | Бэкап в Backblaze B2 через restic + ротация. | По cron ночью / вручную. |
| `fa-entrypoint.sh` | Точка входа контейнера (stand-by / авто-run). | Внутри образа, вручную не нужен. |
| `fa.service` | Шаблон systemd user-сервиса (единый источник). | Ставится скриптом 1. |
| `ssh-tailscale/*` | Усиление защиты SSH-over-Tailscale + руководство. | См. раздел 9. |

> Внутренняя архитектура: `fa.service` и `backup-fa.sh` хранятся в одном
> экземпляре в репозитории и копируются на место при установке (без дублирования
> внутри установочного скрипта) — править нужно только файлы в `scripts/`.
> Скрипт `setup-fa-desktop.sh` намеренно самодостаточен: его можно скачать
> отдельным файлом и запустить (см. `knowledge/instructions/01-install.md`, Phase 4, Option B),
> поэтому он не подключает вспомогательные библиотеки.

---

> Файлы конфигурации в репозитории — единственный источник правды; это
> руководство только объясняет, как ими пользоваться.

*Соблюдение этого руководства обеспечивает стабильную, безопасную и
предсказуемую работу вашего сервера с First-Agent. Если что-то идёт не так —
начните с раздела 10 «Диагностика».*
