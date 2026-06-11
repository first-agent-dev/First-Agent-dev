# First-Agent Docker/AIO Usage Guide

> Обновлено: 2026-06-11  
> Назначение: единая практическая инструкция по Docker/AIO-скриптам First-Agent.

---

## 0. Важные уточнения к предыдущей инструкции

При повторной проверке я нашёл несколько моментов, которые важно явно зафиксировать:

1. **`FA_TASK` сам по себе не запускает агента.**  
   Auto-run включается только при:
   ```env
   FA_AUTO_RUN=1
   ```
   Это сделано специально, чтобы `restart: unless-stopped` не запускал одну и ту же задачу бесконечно.

2. **`scripts/fa-update.sh` всегда переключается на `main` и делает `git pull --ff-only origin main`.**  
   Это production-update скрипт для уже смерженного кода. Для теста feature-ветки вручную переключайтесь на нужную ветку и не используйте `fa-update.sh`, пока PR не смержен.

3. **`scripts/fa-update.sh` надо запускать из репо или по абсолютному пути из репо:**
   ```bash
   /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
   ```
   Он не копируется автоматически в `/srv/first-agent/scripts/` текущим `setup-fa-desktop.sh`. В `/srv/first-agent/scripts/` сейчас копируется backup script.

4. **`setup-fa-desktop.sh` генерирует systemd user service inline.**  
   В репо есть `scripts/fa.service` как шаблон, но setup-скрипт пишет свой unit в `~/.config/systemd/user/fa.service`. После изменения шаблона стоит проверить установленный unit:
   ```bash
   systemctl --user cat fa.service
   ```

5. **Тесты внутри контейнера лучше запускать через `uv run` из `/workspace`, а не из `/opt/first-agent`.**  
   `/opt/first-agent` — baked snapshot в read-only image. Живой код и writable dev venv находятся в `/workspace`.

---

## 1. Mental model

Production Docker setup состоит из трёх слоёв:

```text
Host Ubuntu AIO
└── systemd user service: fa.service
    └── docker compose
        └── container: first-agent
            ├── /workspace       -> bind mount репозитория
            ├── /home/fa/.fa     -> persistent state/config
            ├── /run/secrets/*   -> deploy key + known_hosts
            └── fa-entrypoint.sh -> stand-by / explicit auto-run
```

Ключевая идея:

> Контейнер по умолчанию — это **готовая среда для запуска агента**, а не бесконечно работающий агент.

Обычный режим:

```bash
docker exec -it first-agent bash
fa run --workspace /workspace --role coder --task "..."
```

Auto-run — отдельный явный режим через `FA_AUTO_RUN=1`.

---

## 2. Основные Docker-файлы

### `Dockerfile.fa`

Собирает Ubuntu-based runtime image.

Что делает:

- база: `ubuntu:24.04`;
- ставит системные зависимости:
  - `git`, `curl`, `openssh-client`, `universal-ctags`, build tools;
- создаёт пользователя `fa` с UID `1000`;
- ставит `uv`, `uvx`, `just`;
- ставит Python 3.13;
- создаёт image-owned venv:
  ```text
  /opt/fa-venv
  ```
- ставит runtime dependencies:
  ```bash
  uv sync --frozen --no-dev
  ```
- копирует entrypoint:
  ```text
  /usr/local/bin/fa-entrypoint.sh
  ```
- задаёт:
  ```dockerfile
  ENTRYPOINT ["/usr/local/bin/fa-entrypoint.sh"]
  ```

Важное поведение:

```text
PYTHONPATH=/workspace/src
```

Это значит, что bind-mounted код в `/workspace/src` имеет приоритет над baked snapshot. Обычные изменения `.py` файлов видны без rebuild image. Rebuild нужен при изменении зависимостей, Dockerfile, entrypoint и т.п.

---

### `docker-compose.fa.yml`

Описывает production service:

```text
first-agent
```

Важные настройки:

```yaml
container_name: first-agent
restart: unless-stopped
init: true
read_only: true
user: "1000:1000"
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
```

Основные mount points:

| Host path | Container path | Назначение |
|---|---|---|
| `/srv/first-agent/repo/First-Agent-dev` | `/workspace` | живой код проекта |
| `/srv/first-agent/state` | `/home/fa/.fa` | state/config/work logs |
| `/srv/first-agent/secrets/github_deploy_key` | `/run/secrets/git_key` | GitHub deploy key |
| `/srv/first-agent/secrets/known_hosts` | `/run/secrets/known_hosts` | pinned GitHub host key |

Writable tmpfs:

- `/tmp`
- `/home/fa/.cache`
- `/tmp/uv-cache`
- `/home/fa/.local`

Healthcheck:

```bash
fa --version
```

---

### `.env.fa.template`

Шаблон для `.env.fa`.

Содержит:

- LLM provider API keys;
- optional container auto-run controls.

Пример provider key:

```env
OPENROUTER_API_KEY=sk-or-v1-...
ANTHROPIC_API_KEY=sk-ant-...
```

Auto-run controls обычно закомментированы:

```env
# FA_AUTO_RUN=0
# FA_TASK=...
# FA_TASK_FILE=tasks/example.md
# FA_ROLE=coder
# FA_MAX_TURNS=16
# FA_RUN_ID=my-run-id
# FA_RESUME=0
# FA_CONFIG=/home/fa/.fa/models.yaml
```

**Не коммитьте `.env.fa`.** Он содержит секреты и игнорируется Git.

---

## 3. Скрипты верхнего уровня

### `scripts/fa-entrypoint.sh`

Используется **внутри контейнера** как Docker entrypoint.

Обычно руками его не запускают.

#### Режим 1 — stand-by, дефолт

Если нет command override и `FA_AUTO_RUN` не truthy:

```bash
sleep infinity
```

Контейнер живой и готов для:

```bash
docker exec -it first-agent bash
```

#### Режим 2 — command override

Если контейнеру передана команда, entrypoint делает:

```bash
exec "$@"
```

Пример:

```bash
docker compose -f docker-compose.fa.yml run --rm first-agent bash
```

#### Режим 3 — explicit auto-run

Включается только если:

```env
FA_AUTO_RUN=1
```

и задано ровно одно из:

```env
FA_TASK=...
```

или:

```env
FA_TASK_FILE=tasks/my-task.md
```

Что делает:

1. Валидирует task и env.
2. Запускает `fa run` как child process.
3. Пишет status file:
   ```text
   /workspace/.fa/entrypoint-status.txt
   ```
4. После завершения возвращается в stand-by.

Статусы:

```text
STANDBY
RUNNING
SUCCESS
FAILED
INVALID_CONFIG
TERMINATED
```

Проверить:

```bash
docker exec first-agent cat /workspace/.fa/entrypoint-status.txt
```

---

### `scripts/fa-update.sh`

Host-side update/deploy helper для AIO.

Основной способ обновлять production-деплой после merge в `main`:

```bash
/srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

Что делает:

1. Берёт lock:
   ```text
   /tmp/fa-update.lock
   ```
2. Логирует в:
   ```text
   /tmp/fa-update.log
   ```
3. Проверяет команды: `git`, `docker`, `sha256sum`, `awk`, `grep`, `sed`, `flock`.
4. Проверяет Docker disk usage.
5. Проверяет dirty working tree.
6. Делает:
   ```bash
   git fetch origin --prune
   git switch main
   git pull --ff-only origin main
   ```
7. Решает, нужен ли rebuild/restart.
8. Отслеживает изменение `.env.fa` через `.env.fa.sha256`.
9. Валидирует активные `FA_*` env rows.
10. Делает build/restart через Docker Compose.
11. Ждёт healthcheck.
12. Проверяет `fa --version` и core imports.
13. Опционально запускает tests внутри контейнера.
14. Печатает usage examples.
15. Делает `docker image prune` старых images.

Частые варианты:

```bash
# быстро обновить без тестов
SKIP_TESTS=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh

# auto-stash локальных изменений
AUTO_STASH=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh

# clean rebuild
NO_CACHE=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh

# не чистить старые images
PRUNE=0 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

Важное ограничение:

> Скрипт предназначен для `main`. Он сам переключается на `main`.

---

### `scripts/setup-fa-desktop.sh`

Первичный bootstrap Ubuntu Desktop/AIO host.

Запуск:

```bash
bash scripts/setup-fa-desktop.sh
```

Что делает:

- обновляет систему;
- ставит Docker CE из официального Docker apt repo;
- ставит Tailscale;
- создаёт `/srv/first-agent/...`;
- клонирует репозиторий, если его нет;
- создаёт `.env.fa` из шаблона;
- создаёт `/srv/first-agent/state/models.yaml` из example;
- создаёт backup credentials template;
- ставит user systemd service;
- настраивает базовую host security / power behavior.

После него обычно нужны ручные шаги:

```bash
sudo tailscale up --ssh
nano /srv/first-agent/repo/First-Agent-dev/.env.fa
nano /srv/first-agent/state/models.yaml
```

Затем:

```bash
bash scripts/fa-post-setup.sh
```

---

### `scripts/fa-post-setup.sh`

Второй этап после setup и ручной настройки.

Запускать после:

- Tailscale auth;
- GitHub deploy key;
- заполнения `.env.fa`;
- настройки `models.yaml`.

Запуск:

```bash
bash scripts/fa-post-setup.sh
```

Что делает:

1. Проверяет, что пользователь не root.
2. Проверяет Docker group.
3. Проверяет `.env.fa`.
4. Собирает контейнер:
   ```bash
   docker compose -f docker-compose.fa.yml build
   ```
5. Запускает контейнер:
   ```bash
   docker compose -f docker-compose.fa.yml up -d
   ```
6. Настраивает Git внутри `/workspace`.
7. Проверяет Git SSH.
8. Делает test branch push/delete.
9. Включает и запускает `fa.service`.
10. Настраивает backup cron, если есть B2 credentials.

---

### `scripts/fa.service`

Шаблон user systemd unit для управления Docker Compose service.

Обычно установленный путь:

```text
~/.config/systemd/user/fa.service
```

Управление:

```bash
systemctl --user status fa.service
systemctl --user start fa.service
systemctl --user stop fa.service
systemctl --user restart fa.service
```

Unit запускает:

```bash
docker compose -f docker-compose.fa.yml up -d
```

и останавливает:

```bash
docker compose -f docker-compose.fa.yml down
```

---

### `scripts/backup-fa.sh`

Backup через `restic` в Backblaze B2 S3-compatible endpoint.

Credentials ожидаются в:

```text
/srv/first-agent/secrets/backup.env
```

Пример:

```env
B2_KEY_ID=...
B2_APPLICATION_KEY=...
B2_BUCKET=...
```

Ручной запуск:

```bash
/srv/first-agent/scripts/backup-fa.sh
```

или из репо:

```bash
scripts/backup-fa.sh
```

Cron example:

```cron
0 3 * * * /srv/first-agent/scripts/backup-fa.sh >> /srv/first-agent/backup/backup.log 2>&1
```

---

### `scripts/check_protected_paths.py`

Не Docker runtime script.

Это CI/authoring guardrail для проверки protected paths. Обычно пользователю AIO-деплоя напрямую не нужен.

---

## 4. SSH/Tailscale скрипты

Каталог:

```text
scripts/ssh-tailscale/
```

Эти скрипты настраивают **host-level remote access**, не контейнер.

### `scripts/ssh-tailscale/README.md`

Главный runbook. Читать перед запуском остальных.

---

### `00-failsafe.sh`

Anti-lockout подготовка перед hardening.

Запуск:

```bash
cd scripts/ssh-tailscale
sudo bash 00-failsafe.sh
```

---

### `10-diagnose.sh`

Read-only диагностика Tailscale/SSH/UFW.

```bash
sudo bash 10-diagnose.sh
```

---

### `20-harden.sh`

Применяет SSH-over-Tailscale hardening.

```bash
sudo bash 20-harden.sh
```

Настраивает:

- UFW;
- sshd restrictions;
- Match Address;
- fail2ban-related checks.

---

### `30-verify.sh`

Read-only verification после hardening.

```bash
sudo bash 30-verify.sh
```

---

### `tailscale-acl.jsonc`

Пример Tailscale ACL policy для admin console.

Используется для:

- `tag:aio`;
- Tailscale SSH rules;
- доступа только нужному пользователю/device set.

---

## 5. Первый production-деплой

### Шаг 1 — получить репозиторий

Если репо ещё нет:

```bash
mkdir -p /srv/first-agent/repo
cd /srv/first-agent/repo
git clone https://github.com/first-agent-dev/First-Agent-dev.git
cd First-Agent-dev
```

Если вы запускаете `setup-fa-desktop.sh`, он сам клонирует репо при отсутствии.

---

### Шаг 2 — bootstrap host

```bash
bash scripts/setup-fa-desktop.sh
```

После добавления пользователя в Docker group может понадобиться logout/login или reboot.

---

### Шаг 3 — Tailscale

Минимально:

```bash
sudo tailscale up --ssh
```

Проверить:

```bash
tailscale status
```

Опциональный hardening:

```bash
cd scripts/ssh-tailscale
sudo bash 00-failsafe.sh
sudo bash 10-diagnose.sh
sudo bash 20-harden.sh
sudo bash 30-verify.sh
```

---

### Шаг 4 — secrets

```bash
nano /srv/first-agent/repo/First-Agent-dev/.env.fa
chmod 600 /srv/first-agent/repo/First-Agent-dev/.env.fa
```

Заполнить LLM provider keys.

---

### Шаг 5 — model config

Файл на host:

```text
/srv/first-agent/state/models.yaml
```

В контейнере:

```text
/home/fa/.fa/models.yaml
```

Минимальная форма:

```yaml
coder:
  model: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      slug: "provider/model"
      base_url: "https://openrouter.ai/api/v1"
      api_key_env: OPENROUTER_API_KEY
```

Для multi-role workflow добавьте `planner` и `eval`.

---

### Шаг 6 — post setup

```bash
bash scripts/fa-post-setup.sh
```

После успешного выполнения:

```bash
docker ps
systemctl --user status fa.service
```

---

## 6. Ежедневная работа

### Войти в контейнер

```bash
docker exec -it first-agent bash
```

Внутри:

```bash
cd /workspace
fa --version
```

---

### Запустить задачу вручную

```bash
fa run \
  --workspace /workspace \
  --role coder \
  --task "Сделай нужное изменение"
```

---

### Planner → Coder → Eval workflow

Planner:

```bash
fa run \
  --workspace /workspace \
  --role planner \
  --run-id feature-auth-001 \
  --task "Составь план для JWT auth"
```

Coder:

```bash
fa run \
  --workspace /workspace \
  --role coder \
  --run-id feature-auth-001 \
  --resume \
  --task "Выполни план из work log"
```

Eval:

```bash
fa run \
  --workspace /workspace \
  --role eval \
  --run-id feature-auth-001 \
  --resume \
  --task "Проверь реализацию по work log"
```

---

## 7. Auto-run режим

Использовать только осознанно.

В `.env.fa`:

```env
FA_AUTO_RUN=1
FA_TASK_FILE=tasks/my-task.md
FA_ROLE=coder
FA_RUN_ID=my-task-001
FA_MAX_TURNS=24
FA_RESUME=0
```

Перезапустить:

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml restart
```

Проверить:

```bash
docker exec first-agent cat /workspace/.fa/entrypoint-status.txt
```

После завершения задача не повторяется сама по себе, пока контейнер остаётся живым. Но если оставить `FA_AUTO_RUN=1` в `.env.fa` и пересоздать контейнер, задача снова стартует. После one-shot запуска лучше вернуть:

```env
FA_AUTO_RUN=0
```

или закомментировать auto-run variables.

---

## 8. Обновление production-деплоя

После merge в `main`:

```bash
/srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

Быстро без тестов:

```bash
SKIP_TESTS=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

С авто-stash:

```bash
AUTO_STASH=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

Clean rebuild:

```bash
NO_CACHE=1 /srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

---

## 9. Управление сервисом

```bash
systemctl --user status fa.service
systemctl --user restart fa.service
systemctl --user stop fa.service
systemctl --user start fa.service
```

Логи:

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml logs -f
```

Если контейнер сломан:

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml down
docker compose -f docker-compose.fa.yml up -d
```

---

## 10. Backup

Проверить credentials:

```bash
cat /srv/first-agent/secrets/backup.env
```

Ручной backup:

```bash
/srv/first-agent/scripts/backup-fa.sh
```

Проверить restore хотя бы иногда:

```bash
restic -r "$RESTIC_REPO" restore latest --target /tmp/restore-test
```

---

## 11. Troubleshooting

### Контейнер не healthy

```bash
docker ps
docker inspect first-agent --format='{{json .State.Health}}'
docker compose -f docker-compose.fa.yml logs --tail=200 first-agent
```

### `fa` не найден внутри контейнера

Проверить image build и PATH:

```bash
docker exec first-agent bash -lc 'echo $PATH && which fa && fa --version'
```

Если нет — rebuild:

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml build --no-cache
docker compose -f docker-compose.fa.yml up -d --force-recreate
```

### `.env.fa` поменялся, но контейнер не видит изменения

Нужно пересоздать контейнер:

```bash
cd /srv/first-agent/repo/First-Agent-dev
docker compose -f docker-compose.fa.yml up -d --force-recreate
```

или:

```bash
scripts/fa-update.sh
```

### Auto-run не стартует

Проверить:

```bash
docker exec first-agent env | grep '^FA_'
docker exec first-agent cat /workspace/.fa/entrypoint-status.txt
```

Убедиться, что есть:

```env
FA_AUTO_RUN=1
```

и ровно один task source:

```env
FA_TASK=...
```

или:

```env
FA_TASK_FILE=...
```

### Git push из контейнера не работает

Проверить:

```bash
docker exec -it first-agent bash
cd /workspace
echo "$GIT_SSH_COMMAND"
git ls-remote origin
```

Проверить host files:

```bash
ls -l /srv/first-agent/secrets/github_deploy_key
ls -l /srv/first-agent/secrets/known_hosts
```

---

## 12. Быстрая шпаргалка

### Первый деплой

```bash
bash scripts/setup-fa-desktop.sh
# logout/login or reboot if Docker group changed
sudo tailscale up --ssh
nano /srv/first-agent/repo/First-Agent-dev/.env.fa
nano /srv/first-agent/state/models.yaml
bash scripts/fa-post-setup.sh
```

### Обычная работа

```bash
docker exec -it first-agent bash
cd /workspace
fa run --workspace /workspace --role coder --task "..."
```

### Multi-role

```bash
fa run --workspace /workspace --role planner --run-id work-1 --task "Plan X"
fa run --workspace /workspace --role coder   --run-id work-1 --resume --task "Implement X"
fa run --workspace /workspace --role eval    --run-id work-1 --resume --task "Verify X"
```

### Обновить деплой

```bash
/srv/first-agent/repo/First-Agent-dev/scripts/fa-update.sh
```

### Логи

```bash
docker compose -f /srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml logs -f
```

### Статус auto-run

```bash
docker exec first-agent cat /workspace/.fa/entrypoint-status.txt
```

### Остановить/запустить сервис

```bash
systemctl --user stop fa.service
systemctl --user start fa.service
```
