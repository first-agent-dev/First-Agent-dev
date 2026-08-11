# FA host/deployment anatomy (для агентов)

Проверенная сводка по стенду `fa@fa-HP` (актуально на 2026-08-09).

## Участники
- **Хост:** `fa@fa-HP` (Ubuntu), пользователь `fa` (не-root, нужен `sudo` для `/srv/first-agent`, docker).
- **Репозиторий:** `/srv/first-agent/repo/First-Agent-dev` (НЕ `~/First-Agent-dev`).
- **Wrapper `/usr/local/bin/fa`** → symlink на `<repo>/scripts/fa`.
- **Контейнер `first-agent`** — Python-код FA, **не имеет LLM-ключей**.
- **Контейнер `fa-egress-proxy`** — подставляет ключи в upstream, слушает `http://fa-egress-proxy:8080`.

## Bind mounts (`docker-compose.fa.yml`)
| host source | container target | режим | содержимое |
|---|---|---|---|
| `<repo>` | `/repo` | ro | исходники (build-context, не runtime-import) |
| `/srv/first-agent/sessions` | `/sessions` | rw | per-session workspace-клоны |
| `/srv/first-agent/state` | `/home/fa/.fa` | rw | state root: runs, session.db, drafts |
| `/srv/first-agent/routing/models.yaml` | `/home/fa/.fa/models.yaml` | ro | действующая конфигурация ролей |
| `/srv/first-agent/secrets/fa_proxy_token` | `/run/secrets/fa_proxy_token` | ro | fa→proxy токен |
| `/srv/first-agent/secrets/fa.env` | `/run/secrets/fa.env` | ro, **только proxy** | реальные API-ключи |

Агент **не видит** `fa.env` с ключами — proxy inject их сам.

## Как код попадает в контейнер
- `Dockerfile.fa` копирует `src/` в `/opt/first-agent/src` и делает `uv sync --frozen --no-dev` → `/opt/fa-venv` во время `docker build`.
- Runtime imports идут из `/opt/first-agent/src`, venv `/opt/fa-venv`.
- `/repo` bind-mount не используется для рантайм-импорта.
- Изменения Python-кода требуют `fa update` (git pull + build + up + smoke).
- `/usr/local/bin/fa` в контейнере = `scripts/fa-entrypoint.sh`, он в итоге вызывает `fa` из `/opt/fa-venv/bin`.

## Путь команды `fa ...` с хоста
`scripts/fa` (хостовый wrapper):
1. `COMPOSE=(docker compose -f <repo>/docker-compose.fa.yml)`.
2. Infra-глаголы (`logs|status|up|down|restart|update|shell|...`) запускает на хосте через `exec "${COMPOSE[@]}" ...`.
3. Прочие команды (`run|probe|conformance|selfcheck|workflow|...`) → `exec "${COMPOSE[@]}" exec first-agent fa "$@"` **внутри контейнера**.
4. `TTY_FLAG=(-T)` если stdin не терминал; иначе пусто (проброс TTY).
5. **Env vars хоста не пробрасываются** в `docker compose exec` по умолчанию. Нужен флаг `-e VAR=...`.

## Артефакты внутри контейнера
| путь | что |
|---|---|
| `~/.fa/models.yaml` | bind на `/srv/first-agent/routing/models.yaml` (ro) |
| `~/.fa/session-log/<run_id>/` | per-run logs: `events.jsonl`, `llm_bodies.jsonl`, `manifest.json` |
| `~/.fa/session-log/conformance/conf-<prov>-<ts>/` | результаты live-conformance |
| `~/.fa/sessions/<uuid>/session.db` | authoritative SQLite (таблица `event_log`, в т.ч. usage-строки) |
| `/sessions/<session-id>/` | workspace-клон текущей сессии |
| `/run/secrets/fa_proxy_token` | fa→proxy токен |

`events.jsonl` — проекция; для cache-ratio читай `session.db`.

## Proxy-режим (критично!)
При выставленном `FA_EGRESS_PROXY_URL` (в контейнере он есть):
- Агент работает с `SecretStore({})` (пустой), ключи не нужны локально.
- Обязателен вызов `_proxy_rewrite_chain(chain, proxy_url)` → переписывает `entry.base_url`
  на `<proxy>/route/<name>` и добавляет `X-FA-Proxy-Token` в `extra_headers`. **Пропустил → 401 на все запросы.**
- Это уже сделано в `_cmd_probe`, `_cmd_run`, после фикса — в `_run_live_conformance`. Новые команды CLI, бьющие в провайдер, должны повторять эту схему.
- `SecretRedactor.from_models_config(secrets, models, extra_values=_proxy_redactor_extra(), allow_empty=True)`.

## Live-conformance на отдельный провайдер
- `fa conformance --provider X` всегда тестирует роль **`coder`**, её **`chain[0]`**.
- Чтобы протестировать провайдер, не затрагивая действующий `models.yaml`, создай временный yaml в `/tmp/conf-X.yaml` с одной ролью `coder`, чья chain[0] указывает на нужного провайдера, и запускай:
  ```bash
  docker compose ... exec -e FA_DEBUG_LLM_BODIES=1 first-agent \
    fa conformance --provider X --config /tmp/conf-X.yaml
  ```
- `--provider X` влияет только на run-id/метки, реальная chain берётся из `coder.chain`.

## Отладка: как запускать с хоста
### Принудительный env в контейнер:
```bash
docker compose -f <repo>/docker-compose.fa.yml exec -e FA_DEBUG_LLM_BODIES=1 first-agent fa <cmd>
```
Для не-интерактивных добавляй `-T`, иначе оставляй TTY.

### llm_bodies.jsonl:
Включается `FA_DEBUG_LLM_BODIES=1`; для conformance лежит в `~/.fa/session-log/conformance/conf-<prov>-<ts>/llm_bodies.jsonl`. Запись потока обеспечивает `wrap_transport_for_debug_bodies` — его тоже надо вызвать в новой CLI-команде.

### Cache-hit ratio:
Формула: `cache_read / (cache_read + cache_creation + uncached_input)` по строкам `kind='usage'` в `session.db`.
Поля ответа: `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens`. Искать `session.db`, связанный с данным run_id, надо перебором `~/.fa/sessions/**/session.db` по подстроке `run_id` в content.

## Чек-лист агента при написании live-теста
1. Делай правки в sandbox `/home/user/First-Agent-dev`.
2. `uv run pytest -q` — полный зелёный прогон.
3. `bash -n scripts/*.sh`; проверь вручную, что функции определены до вызовов.
4. Для proxy-mode команда должна:
   - загрузить `models` с `require_api_keys=not proxy_mode`,
   - вызвать `_proxy_rewrite_chain`,
   - обернуть transport через `wrap_transport_for_debug_bodies` с `SecretRedactor(..., allow_empty=True)`.
5. Сгенерируй patch, проверь `git apply` в **чистом checkout** нужного HEAD.
6. Давай пользователю команды через heredoc `cat >/tmp/patch <<'EOF' ... EOF` (самый надёжный путь по SSH).
7. Порядок обновления стенда у пользователя: `git apply` → `commit/push` → `fa update` → live-проверки через прямой `docker compose exec -e ...`.

## Частые грабли
1. Не используй `fa <cmd> -e VAR=...` — wrapper не пробрасывает env.
2. Не расширяй рабочий `~/.fa/models.yaml` в экспериментах — делай `/tmp/conf-*.yaml`.
3. Не делай `cd ~/First-Agent-dev`; репо в `/srv/first-agent/repo/First-Agent-dev`.
4. `fa-update.sh` использует `flock -n /tmp/fa-update.lock`. Если "Another fa-update is running" — проверь `ps -p <pid>`, не убивай слепо.
5. Никогда не делай `set -m` + `kill -- -$$` в shell-скриптах — ломает sudo (pgroup-сигнал от sudo + паника EXIT-trap → "Убито"). Уборка детей — по PID, трекая долгих потомков.
6. Функции в bash — всегда выше точки вызова.
7. Всегда указывай базовый коммит для патча; если пользователь уже закоммитил предыдущую версию — инкрементальный patch или сначала `git checkout <base-sha> -- <file>`.

## Полезные однострочники (хост)
```bash
# Зомби/lock после fa-update
for p in $(ps -eo pid,cmd | grep -E 'fa-update\.sh|docker compose -f .*docker-compose\.fa\.yml' \
           | grep -v grep | awk '{print $1}'); do kill -KILL $p 2>/dev/null; done
rm -f /tmp/fa-update.lock

# Logs агента
docker compose -f <repo>/docker-compose.fa.yml logs --tail=200 first-agent

# Проверка proxy
docker compose -f <repo>/docker-compose.fa.yml exec first-agent fa probe
```
