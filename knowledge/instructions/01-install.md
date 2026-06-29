# Первичное развёртывание First-Agent (AIO, с нуля)

> Production-проверенный стек для запуска First-Agent в режиме 24/7 на выделенном
> мини-ПК (AIO — «всё в одном»). Эталонное «железо»: Intel i5-1235U (2P+8E,
> 12 потоков), 16 ГБ DDR4, NVMe SSD.
> Исследование-первоисточник: [`knowledge/research/First-Agent-ops-cross-reference.md`](../research/First-Agent-ops-cross-reference.md).

Этот документ — **однократная** установка «от чистого железа до первого
запущенного агента». Всё, что делается **повседневно** (обновление, бэкапы,
перезапуск, диагностика), вынесено в отдельное руководство:
**[`02-operations.md`](./02-operations.md)**. Здесь мы это не дублируем.

> Новичок в Docker? Сначала прочитайте «Глоссарий для новичка» и «Как устроено»
> в [`02-operations.md#2-глоссарий-для-новичка`](./02-operations.md#2-глоссарий-для-новичка) — там простыми словами объяснены
> контейнеры, образы, тома и сервис.

## Что вы получите в итоге

- **Ubuntu Desktop 24.04 LTS** в «почти headless» режиме (GUI остаётся для
  аварийного локального доступа).
- **Docker CE** из официального репозитория docker.com, со стеком FA из **двух**
  защищённых read-only контейнеров: `first-agent` (агент) и `fa-egress-proxy`
  (держит LLM-ключи; агент их не видит — изоляция секретов ADR-12).
- **Tailscale** как единственный путь удалённого доступа — SSH доступен
  **только** через интерфейс Tailscale.
- **systemd user service**, поднимающий FA при загрузке.
- **SSH deploy key** для ограниченного, не истекающего git push из контейнера.
- **restic → Backblaze B2** (S3-совместимый endpoint) — ночной офсайт-бэкап.
- Ожидаемый простой: **~1.5–2.4 ГБ RAM**, **~15–30 Вт от розетки**.

---

## Фаза 0 — что подготовить

| Что | Требование |
|-----|------------|
| **USB-флешка** | 8 ГБ+ для установщика Ubuntu Desktop 24.04 LTS |
| **Интернет** | Лучше проводной Ethernet (меньше возни с Wi-Fi драйверами) |
| **Аккаунт Tailscale** | Бесплатный тариф (20 устройств), [tailscale.com](https://tailscale.com) |
| **Аккаунт GitHub** | Доступ к репозиторию для deploy-ключей и branch protection |
| **Backblaze B2** | Бесплатный тариф (10 ГБ) для офсайт-бэкапа |
| **Телефон** | Приложение Tailscale (iOS/Android) для удалённой проверки |
| **Ваттметр / умная розетка** | Опционально — измерить потребление |

---

## Фаза 1 — настройка BIOS (до установки Ubuntu)

Зайдите в BIOS/UEFI. Эти настройки **критичны** для низкого потребления в 24/7.

| Параметр | Значение | Зачем |
|----------|----------|-------|
| **CPU C-states** | Enabled | Позволяет процессору уходить в глубокий сон |
| **Package C-state limit** | C10 (или C8, если C10 нет) | Самое глубокое состояние простоя |
| **PCIe ASPM** | L1 substates | Энергогейтинг линий PCIe |
| **Intel SpeedShift** | Enabled | Быстрее переключение P-state |
| **Restore on AC Power Loss** | Power On | Автозагрузка после отключения питания |
| **Wake on LAN** | Disabled | Лишняя поверхность атаки |
| **Legacy USB / Serial** | Disabled, если не нужны | Экономит пару ватт |
| **Secure Boot** | Опционально — отключите, если Linux-драйверы конфликтуют | |

Сохраните и выйдите.

---

## Фаза 2 — установка Ubuntu Desktop 24.04 LTS

1. Загрузитесь с USB-флешки.
2. Выберите **«Try or Install Ubuntu»**.
3. В установщике выберите **«Minimal installation»** (не полную с офисом и играми).
4. **Разметка диска:** ZFS или ext4 — оба подходят. ZFS умеет снапшоты; ext4 проще. Выберите одно.
5. **Пользователь:**
   - Создайте основного пользователя (например, `fa`).
   - Задайте надёжный пароль.
   - **НЕ ставьте «автоматический вход»** — это отмечено как риск безопасности.
6. Завершите установку, перезагрузитесь, выньте флешку.

---

## Фаза 3 — первая загрузка и сеть

1. Войдите на экране входа GNOME.
2. Подключите Ethernet (или Wi-Fi, если Ethernet недоступен).
3. Откройте терминал (`Ctrl+Alt+T`).
4. Проверьте интернет:

   ```bash
   curl -I https://github.com
   ```

   > `curl -I` запрашивает только заголовки ответа — быстрый способ проверить, что
   > сеть и DNS работают.

---

## Фаза 4 — получить скрипт установки

### Вариант A: на вашем ноутбуке (проверить перед развёртыванием)

```bash
git clone https://github.com/first-agent-dev/First-Agent-dev.git ~/First-Agent-dev
cd ~/First-Agent-dev
less scripts/setup-fa-desktop.sh
# Скопировать на USB или передать на AIO по scp
```

### Вариант B: прямо на AIO (если уже вошли в систему)

```bash
# Скачиваем ТОЛЬКО скрипт — репозиторий он клонирует в /srv/... сам
curl -fsSL -o /tmp/setup-fa-desktop.sh \
  https://raw.githubusercontent.com/first-agent-dev/First-Agent-dev/main/scripts/setup-fa-desktop.sh
less /tmp/setup-fa-desktop.sh
bash /tmp/setup-fa-desktop.sh
```

> Скрипт **самодостаточен** и **идемпотентен** — его можно скачать одним файлом и
> запускать сколько угодно раз: он не ломает уже настроенное.

**Что делает скрипт (по материалам cross-reference):**

- Обновляет системные пакеты.
- Удаляет `gnome-software` (известные утечки памяти ~2–3 ГБ).
- **Маскирует** (не удаляет) `tracker-miner-fs-3.service` — удаление пакета сломало
  бы метапакет `ubuntu-desktop`.
- Отключает `whoopsie` и `apport` (отчёты о сбоях).
- Отключает Bluetooth.
- Двойная защита от «засыпания» (`gsettings` + drop-in в `logind.conf.d`).
- Гасит экран через **60 секунд**, без блокировки.
- Ставит профиль питания **power-saver** через `power-profiles-daemon`.
- Усиливает SSH: только ключи, без root, `AllowUsers` (один аккаунт). Слой с
  ограничением по **диапазону Tailscale CGNAT** (`sshd Match Address`)
  применяется отдельно скриптами `scripts/ssh-tailscale/` — см. Фазу 5b.
- Настраивает UFW: по умолчанию запрет входящих; SSH разрешён **только** через
  интерфейс `tailscale0`.
- Ставит Docker CE из **официального apt-репозитория docker.com** (не из snap).
- Ставит Tailscale.
- Создаёт `/srv/first-agent/{repo,state,secrets,backup,routing}`.
- Генерирует **ED25519 deploy key**.
- Генерирует токен **`fa→proxy`** (`/srv/first-agent/secrets/fa_proxy_token`, 0600)
  — им агент аутентифицируется у egress-прокси (это не LLM-ключ).
- Создаёт шаблон файла LLM-ключей (`/srv/first-agent/secrets/fa.env`) — ключи
  вписываются в Фазе 7b; их читает только контейнер прокси.
- Пинит Ed25519 host-key GitHub в `/srv/first-agent/secrets/known_hosts`.
- Ставит `restic`.
- `xset dpms 0 0 60` — агрессивное гашение подсветки панели AIO (~5–15 Вт экономии).
- Пинит пакеты Docker CE через `apt-mark hold` (защита от внезапных апгрейдов).
- Включает `live-restore` Docker + ротацию логов демона (10m/3 файла), чтобы
  контейнеры переживали перезапуск демона, а логи не забивали диск.
- Добавляет еженедельный `docker image prune -f` в cron (только неиспользуемые образы).
- Настраивает unattended-upgrades с **авто-ребутом в 04:00**.
- Включает systemd **lingering**, чтобы user-сервисы переживали logout и
  поднимались после ребута.
- Ставит шаблон systemd user-сервиса в `~/.config/systemd/user/fa.service`.
- Создаёт шаблон скрипта бэкапа.

**Когда скрипт закончит — выполните напечатанные им «next steps» (Фазы 5–7 ниже).**

> Группа `docker`: скрипт добавил вашего пользователя в группу `docker`. Чтобы
> это применилось, **выйдите из системы и войдите снова** (или перезагрузитесь).
> Проверка: `id -nG | grep -w docker`.

---

## Фаза 5 — авторизация Tailscale

```bash
sudo tailscale up --ssh
```

1. В терминал выведется URL. Откройте его на телефоне или ноутбуке.
2. Войдите в аккаунт Tailscale.
3. AIO теперь в вашей частной сети (tailnet).

**Проверка с телефона (по сотовой сети, не Wi-Fi):**

1. Откройте приложение Tailscale.
2. В списке должен быть ваш AIO.
3. Скопируйте его Tailscale-IP (например, `100.x.y.z`).

**Тест SSH через Tailscale:**

```bash
# С ноутбука (НЕ с AIO)
ssh fa@100.x.y.z
```

Если сработало — удалённый доступ есть, и SSH не торчит в публичный интернет.

---

## Фаза 5b — углублённое усиление SSH-over-Tailscale (defense-in-depth)

`setup-fa-desktop.sh` (Фаза 4) задаёт базовую SSH/UFW-конфигурацию. Чтобы
добавить остальные слои защиты из ops-SSOT — фильтрацию IPv6 в UFW,
`sshd Match Address` по диапазонам Tailscale CGNAT, jail fail2ban с бэкендом
**systemd** (правильный для 24.04) и Tailscale ACL — запустите идемпотентные
скрипты в [`scripts/ssh-tailscale/`](../../scripts/ssh-tailscale/README.md). В них
встроен «dead-man failsafe», чтобы ошибка в firewall/sshd не заблокировала вас.

```bash
cd /srv/first-agent/repo/First-Agent-dev/scripts/ssh-tailscale
sudo bash 10-diagnose.sh                  # read-only аудит (запустить первым)
sudo bash 00-failsafe.sh arm              # + откройте ВТОРУЮ ssh-сессию и держите
sudo SSH_USER=fa bash 20-harden.sh        # применить слои (reload, не restart)
sudo bash 30-verify.sh                     # чек-лист; ненулевой код = провал
# примените tailscale-acl.jsonc в админ-консоли, затем:
sudo bash 00-failsafe.sh disarm           # только после успешного свежего логина
```

> **Какой `:22` отвечает?** `tailscale up --ssh` (Фаза 5) заставляет `tailscaled`
> отвечать на Tailscale-IP `:22`, **а не** системный `sshd`. Сессии Tailscale SSH
> управляются правилами `ssh` в `tailscale-acl.jsonc`; слои `sshd` Match-Address /
> UFW / fail2ban защищают «классический» путь восстановления через `sshd` (LAN или
> если Tailscale SSH отключат). `10-diagnose.sh` показывает, кто отвечает.
> Подробности — в [`README`](../../scripts/ssh-tailscale/README.md).

---

## Фаза 6 — GitHub Deploy Key + Branch Protection

1. Скрипт уже напечатал ваш **публичный deploy-ключ**. Показать снова:

   ```bash
   cat /srv/first-agent/secrets/github_deploy_key.pub
   ```

2. В репозитории на GitHub: **Settings → Deploy keys → Add deploy key**.
3. Вставьте публичный ключ, дайте имя (например, `fa-aio-deploy`) и поставьте
   галочку **«Allow write access»**.
4. **Settings → Branches → Add rule** для `main`:
   - Включите **«Require a pull request before merging»**.
   - Включите **«Require approvals»** (1).
   - Это не даст агенту случайно сделать force-push в `main`.
5. Агент должен пушить в ветки вида `agent/yyyy-mm-dd-topic`.

---

## Фаза 6b — SSH-диагностика и конфиг хоста

Скрипт создаёт `~/.ssh/config`, чтобы **хостовая оболочка** (не только контейнер)
могла делать fetch/pull из GitHub по deploy-ключу. Почему это важно:

1. **Git-операции на хосте** (`git fetch`, `git pull` в оболочке AIO) тоже
   требуют deploy-ключ — не только контейнер.
2. **Ротация known_hosts.** GitHub периодически меняет свой Ed25519 host-key. Если
   увидите `WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!`, обновите пин:

   ```bash
   ssh-keygen -f '/srv/first-agent/secrets/known_hosts' -R 'github.com'
   ssh-keyscan -H -t ed25519 github.com >> /srv/first-agent/secrets/known_hosts
   ```

3. **Контейнер видит устаревший known_hosts** — монтирование read-only. После
   обновления на хосте пересоздайте контейнер:
   `docker compose -f docker-compose.fa.yml down && docker compose -f docker-compose.fa.yml up -d`.
4. **Deploy-ключ без WRITE-доступа** — проверьте галочку «Allow write access» в
   Settings → Deploy keys.
5. **Проверка:**

   ```bash
   ssh -T git@github.com
   # Ожидается: "Hi <repo>! You've successfully authenticated..."
   ```

---

## Фаза 7 — собрать и запустить стек FA (ДВА контейнера)

Файлы `docker-compose.fa.yml` и `Dockerfile.fa` в корне репозитория описывают
**два** защищённых сервиса (изоляция секретов, ADR-12 Option C):

- **`first-agent`** — сам агент (`fs.run_bash` и т.д.). LLM-ключей у него нет.
- **`fa-egress-proxy`** — граница LLM-ключей: ключи смонтированы read-only
  **только сюда**; агент ходит к провайдерам через прокси, который подставляет
  реальный ключ вне досягаемости агента. У прокси нет `/workspace` и кода агента.

`depends_on: service_healthy` гарантирует, что агент не стартует, пока прокси не
станет healthy.

> **Порядок:** проверьте, что `setup-fa-desktop.sh` (Фаза 4) уже сгенерировал
> токен `fa→proxy` (`/srv/first-agent/secrets/fa_proxy_token`) — без него прокси
> не примет вызовы агента. Реальные LLM-ключи прописываются в **Фазе 7b** (ниже);
> прокси стартует healthy и с пустым файлом ключей, но `fa run` без ключей
> завершится ошибкой конфигурации — это ожидаемо до Фазы 7b.

```bash
cd /srv/first-agent/repo/First-Agent-dev

# Собрать образы (один образ на оба сервиса)
docker compose -f docker-compose.fa.yml build

# Запустить в фоне (compose поднимет прокси, затем агента)
docker compose -f docker-compose.fa.yml up -d

# Должны быть ОБА сервиса; дождитесь, пока fa-egress-proxy = healthy
docker compose -f docker-compose.fa.yml ps

# Логи (всех сервисов или только прокси)
docker compose -f docker-compose.fa.yml logs -f
docker compose -f docker-compose.fa.yml logs -f fa-egress-proxy
```

> Если `fa-egress-proxy` не становится healthy — проверьте
> `ls -l /srv/first-agent/secrets/fa_proxy_token /srv/first-agent/routing/models.yaml`
> и `docker compose -f docker-compose.fa.yml logs fa-egress-proxy`. Пока прокси
> не здоров, `first-agent` не запустится (это by design).

**Проверка bootstrap «в один заход»:**

После старта контейнера запустите post-setup — он проверит git SSH, запушит и
удалит тестовую ветку и включит systemd-сервис:

```bash
bash scripts/fa-post-setup.sh
```

Скрипт идемпотентен — безопасно перезапускать после любого `git pull` или
`docker compose build`.

**Применённое усиление (per cross-reference):**

- `read_only: true` — корневая ФС только для чтения.
- `cap_drop: [ALL]` — сняты все Linux-capabilities; **никаких `cap_add`** в
  рантайме (uv/just нужны только при сборке, под root, не во время работы).
- `security_opt: [no-new-privileges:true]` — контейнер не может повысить привилегии.
- `pids: 512` в `deploy.resources.limits` — защита от fork-бомбы (Compose схема v3).
- `user: "1000:1000"` — запуск не от root. **Важно:** файлы на хосте в
  `/srv/first-agent/{state,secrets}` должны принадлежать **uid 1000** (это делает
  `setup-fa-desktop.sh`/`fa-clean-rebuild.sh`); иначе контейнер не сможет читать
  ключи/писать state.
- Лимиты ресурсов: 8 ГБ RAM, 8 CPU.
- LLM-ключи смонтированы read-only **только в `fa-egress-proxy`**; в контейнере
  агента их нет ни в файле, ни в env (ADR-12 Option C). Агент получает лишь
  `FA_EGRESS_PROXY_URL` и read-only токен `/run/secrets/fa_proxy_token` (не ключ).
- Git-ключ смонтирован в `/run/secrets/git_key` (read-only).
- `GIT_SSH_COMMAND` с `IdentitiesOnly=yes`.
- Нет монтирования `/var/run/docker.sock`.
- `init: true` — `tini` собирает зомби-процессы (ответственность PID 1).
- `hostname: first-agent` — узнаваемо в логах и `docker ps`.
- tmpfs для `/tmp`, `~/.cache`, `~/.local`, `/tmp/uv-cache` — запись без нарушения
  read-only корня.

**Политика перезапуска:** в compose стоит `restart: unless-stopped`:

- При сбое контейнера или ребуте хоста он поднимается сам.
- Если вы **вручную** сделали `docker compose down`, он останется выключенным.
- Чтобы поднимался даже после ручного `docker stop`, поменяйте на
  `restart: always` в `docker-compose.fa.yml`.

**Поведение entrypoint:** образ использует `scripts/fa-entrypoint.sh`. По
умолчанию — режим ожидания (`sleep infinity`), агент запускают вручную через
`docker exec`. Подробно про режимы запуска агента (stand-by / auto-run /
planner→coder→eval) — в [`02-operations.md` §7](./02-operations.md).

**Включить автозапуск при загрузке:**

```bash
systemctl --user enable fa.service
systemctl --user start fa.service
```

---

## Фаза 7b — настроить API-ключи LLM

Стек закрывает git-аутентификацию (deploy-ключ) и API-ключи LLM. LLM-ключи живут
**вне репозитория и вне песочницы агента** — в `/srv/first-agent/secrets/fa.env`
(права `0600`). Они монтируются read-only **только в контейнер `fa-egress-proxy`**;
контейнер агента их не видит вообще. Агент обращается к провайдерам через прокси,
который подставляет реальный ключ вне досягаемости агента (ADR-12 Option C —
egress-injection proxy). `setup-fa-desktop.sh` создаёт файл-шаблон ключей и
генерирует токен `fa→proxy` автоматически.

1. Впишите реальные ключи в файл секретов (создан скриптом установки):

   ```bash
   micro /srv/first-agent/secrets/fa.env   # вписать ключи; раскомментировать нужные строки
   chmod 600 /srv/first-agent/secrets/fa.env
   ```

   > `.env.fa` в корне репо теперь хранит только несекретные `FA_*`-настройки
   > (`FA_AUTO_RUN`, `FA_TASK`, …) — API-ключей там быть не должно.

2. Проверьте, что есть `models.yaml` (копируется `setup-fa-desktop.sh`):

   ```bash
   ls /srv/first-agent/routing/models.yaml
   ```

   Если нет — скопируйте из примера:

   ```bash
   sudo mkdir -p /srv/first-agent/routing
   sudo cp knowledge/templates/models.yaml.example /srv/first-agent/routing/models.yaml
   ```

3. **Разделение по назначению:**
   - **Docker-деплой (AIO)**: ключи в `/srv/first-agent/secrets/fa.env`,
     смонтированы ro **только в `fa-egress-proxy`** (`/run/secrets/fa.env`).
     Контейнер агента ключей не получает; он ходит через прокси
     (`FA_EGRESS_PROXY_URL=http://fa-egress-proxy:8080`).
   - **Локальная разработка (WSL)**: без прокси `fa run` работает в legacy-режиме
     строгого файла — ключи в `~/.fa/.env` читаются в приватный стор (не в
     `os.environ`). Для прод-аналога можно поднять прокси и задать
     `FA_EGRESS_PROXY_URL`.
   - Не смешивайте — контейнер агента не читает ни `~/.fa/.env`, ни `fa.env`.

4. **Креды бэкапа** (`B2_KEY_ID`, `B2_APPLICATION_KEY`) идут в
   `/srv/first-agent/secrets/backup.env`, **не** к ключам LLM. Контейнеру они не нужны.

---

### Управление секретами

| Категория | Хранение | Область |
| --- | --- | --- |
| **API-ключи LLM** | `/srv/first-agent/secrets/fa.env` (хост, 0600) → ro mount `/run/secrets/fa.env` **только в `fa-egress-proxy`** | Только память процесса прокси; контейнер агента их **не видит** |
| **Токен fa→proxy** | `/srv/first-agent/secrets/fa_proxy_token` (хост, 0600) → ro mount в оба контейнера | Не ключ; только аутентифицирует агента у прокси |
| **Креды бэкапа** | `/srv/first-agent/secrets/backup.env` | Только хост (restic) |
| **Git deploy key** | `/srv/first-agent/secrets/github_deploy_key` → ro mount `/run/secrets/git_key` | Хост + контейнер агента (read-only; защищён bash-gate + редактором) |

**Почему так (ADR-12 — изоляция секретов):**

- **Агент не может прочитать ключи.** Три барьера: файл вне `/workspace`
  (песочница `fs.read_file`/`bash` не выходит за её пределы); ключи не в
  `os.environ` (значит `printenv`/`/proc/self/environ`/`os.environ` пусты);
  `fs.run_bash` запускается с очищенным allowlist-окружением.
- **Trust boundary оператора.** Член группы `docker` на хосте всё ещё может
  `docker inspect`/`docker exec` — но это вы, оператор, а не LLM. Держите
  операторский аккаунт эксклюзивным.
- `SecretRedactor` (точное совпадение + base64/hex/URL + скан декодированных окон)
  маскирует секреты в `events.jsonl` / `knowledge/trace/` — это резервный слой,
  не основная граница (основная — недоступность ключей агенту).
- restic шифрует бэкапы *до* загрузки в B2. Проверяйте восстановление ежеквартально.

---

## Фаза 8 — проверить git push из контейнера

```bash
# Войти в контейнер
docker exec -it first-agent bash

# Проверить, что git видит ключ
GIT_SSH_COMMAND="ssh -i /run/secrets/git_key -o IdentitiesOnly=yes -o UserKnownHostsFile=/run/secrets/known_hosts" git ls-remote $(git remote get-url origin | sed 's|https://github.com/|git@github.com:|')

# Если ок — тестовый push ветки
cd /workspace
git checkout -b agent/test-bootstrap
touch bootstrap-test.txt
git add bootstrap-test.txt
git commit -m "test: bootstrap verification"
GIT_SSH_COMMAND="ssh -i /run/secrets/git_key -o IdentitiesOnly=yes -o UserKnownHostsFile=/run/secrets/known_hosts" git push origin agent/test-bootstrap
```

Если push прошёл и ветка появилась на GitHub — аутентификация git работает
end-to-end. (`fa-post-setup.sh` из Фазы 7 делает эту проверку автоматически, а
также ждёт healthy у **обоих** контейнеров и проверяет, что у агента нет
LLM-ключа.)

**Проверка изоляции секретов (ADR-12) — у агента не должно быть LLM-ключа:**

```bash
# Нет файла ключей в контейнере агента (ожидаем «нет»):
docker exec first-agent sh -c 'cat /run/secrets/fa.env 2>&1 || echo "нет ключей у агента — OK"'
# Нет ключеподобных переменных окружения у агента (ожидаем пусто):
docker exec first-agent printenv | grep -iE 'API_KEY|TOKEN=|SECRET' || echo "в окружении агента ключей нет — OK"
# LLM-ключи есть ТОЛЬКО в контейнере прокси:
docker exec fa-egress-proxy sh -c 'test -s /run/secrets/fa.env && echo "ключи у прокси — OK"'
```

---

## Фаза 9 — настройка бэкапа

1. На [Backblaze B2](https://www.backblaze.com/b2) создайте bucket.
2. Сгенерируйте **Application Key** с доступом read/write к этому bucket.
3. Впишите креды в `/srv/first-agent/secrets/backup.env` (**не** в сам скрипт —
   `backup-fa.sh` читает этот файл через `source`, а сам скрипт перезаписывается
   из репо при каждом перезапуске `setup-fa-desktop.sh`, так что правки в нём
   потерялись бы). Шаблон с `CHANGEME` создаётся скриптом установки:

   ```bash
   micro /srv/first-agent/secrets/backup.env
   # B2_KEY_ID=your-key-id
   # B2_APPLICATION_KEY=your-app-key
   # B2_BUCKET=your-bucket-name
   ```

4. Инициализируйте репозиторий restic (однократно):

   ```bash
   source /srv/first-agent/secrets/backup.env
   export AWS_ACCESS_KEY_ID="$B2_KEY_ID"
   export AWS_SECRET_ACCESS_KEY="$B2_APPLICATION_KEY"
   RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/$B2_BUCKET"
   restic -r "$RESTIC_REPO" init
   ```

5. Проверьте бэкап:

   ```bash
   /srv/first-agent/repo/First-Agent-dev/scripts/backup-fa.sh
   ```

> Ночной запуск по cron, ручной бэкап и восстановление подробно описаны в
> [`02-operations.md` §8](./02-operations.md). `setup-fa-desktop.sh` /
> `fa-post-setup.sh` уже ставят ночной cron, если креды заполнены.

---

## Фаза 10 — проверка энергопотребления

1. **Простой по RAM:**

   ```bash
   free -h
   ```

   Ожидается: ~1.2–1.8 ГБ занято ОС + Docker.

2. **Профиль питания:**

   ```bash
   powerprofilesctl get
   ```

   Должно быть `power-saver`.

3. **Тест гашения экрана:** не трогайте мышь/клавиатуру 60 секунд. Экран должен
   погаснуть, но машина остаётся доступной по Tailscale SSH.

4. **Замер от розетки** (если есть ваттметр):
   - Экран включён, простой: ~20–35 Вт
   - Экран погашен: ~15–25 Вт
   - Цель cross-reference: ~7–15 Вт на CPU+плату (остальное — экран).

5. **Анализ powertop** (опционально):

   ```bash
   sudo powertop --html=/tmp/power-report.html
   ```

   Изучите HTML, но **не** включайте `powertop --auto-tune` как сервис — он не
   персистентен и может конфликтовать с `power-profiles-daemon`.

---

## Что дальше — повседневная эксплуатация

Установка завершена. Всё остальное (обновление/пересборка, управление сервисом,
запуск задач агента, бэкапы, восстановление, диагностика, шпаргалка команд) —
в **[`02-operations.md`](./02-operations.md)**. Чтобы не было двух источников
правды, эти разделы здесь намеренно не повторяются:

- **Старт/стоп/перезапуск агента** (удалённо через Tailscale) →
  [`02-operations.md` §6](./02-operations.md).
- **Обновление деплоя** (`fa-update.sh` и ручной путь) →
  [`02-operations.md` §4–5](./02-operations.md).
- **Бэкап и восстановление** → [`02-operations.md` §8](./02-operations.md).
- **Восстановление после сбоев и диагностика** →
  [`02-operations.md` §10](./02-operations.md).

---

## Ссылки

- [`scripts/setup-fa-desktop.sh`](../../scripts/setup-fa-desktop.sh) — автоматическое усиление хоста
- [`docker-compose.fa.yml`](../../docker-compose.fa.yml) — описание защищённого контейнера
- [`Dockerfile.fa`](../../Dockerfile.fa) — образ runtime FA
- [`scripts/fa.service`](../../scripts/fa.service) — systemd user-сервис
- [`.dockerignore`](../../.dockerignore) — исключения build-контекста
- [`scripts/backup-fa.sh`](../../scripts/backup-fa.sh) — скрипт бэкапа restic
- [`02-operations.md`](./02-operations.md) — повседневная эксплуатация (RU)
- [`knowledge/research/First-Agent-ops-cross-reference.md`](../research/First-Agent-ops-cross-reference.md) — трёхсточниковый cross-reference
- [`knowledge/research/homelab-deployment-24-7-2026-06.md`](../research/homelab-deployment-24-7-2026-06.md) — research-заметка с цитатами
