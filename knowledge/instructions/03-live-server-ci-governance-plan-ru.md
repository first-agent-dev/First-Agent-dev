---
title: План live-сервера: CI, безопасность, harness и GitHub governance
status: ready-for-live-execution
last-reviewed: 2026-07-21
language: ru
---

# План выполнения на live-сервере

Этот документ описывает ручное выполнение этапа S9 после подготовки рабочего
дерева. План рассчитан на оператора, который подключается к live-серверу по SSH
и хочет безопасно проверить CI, security gates, shipped harness и настройки
GitHub перед коммитом.

## 0. Важное ограничение

Агент не должен иметь права merge, approve или bypass. Коммит может сделать
оператор из VS Code или harness, но решение о merge остаётся за человеком.
Локальные hooks удобны, но bypassable. Источником истины является GitHub CI.

Команды ниже требуют прав оператора, Docker/Compose, доступ к GitHub и чистой
копии репозитория. Не передавайте API keys в команды, логи, issue или patch.

---

## 1. Подготовка live-сервера

### 1.1 Подключение и идентификация

```bash
ssh <user>@<live-host>
set -euo pipefail
hostname
uname -a
date -Is
id
```

Проверить, что это правильный сервер и правильный пользователь. Не продолжать,
если hostname, пользователь или дата неожиданны.

### 1.2 Получение репозитория

```bash
cd /srv/first-agent/repo
# Если это новая копия:
git clone <repo-url> First-Agent-dev
cd First-Agent-dev

# Если копия уже существует:
git fetch --all --prune
git status --short
git branch --show-current
git rev-parse HEAD
```

Работать только в ожидаемой ветке. Если дерево содержит чужие изменения:
остановиться и сохранить их владельцу; не выполнять `git reset --hard`.

### 1.3 Bootstrap

Обязательная команда для свежей копии:

```bash
just agent-bootstrap
```

Успешный результат обязан содержать точный маркер:

```text
FA_AGENT_READY=1
```

Проверка окружения:

```bash
python --version
uv --version
just --version
just hooks-status
uv lock --locked
```

Если marker отсутствует, не коммитить. Классифицировать проблему как
environment issue или product/checker defect и сохранить полный вывод.

---

## 2. Проверка intended CI workflow

### 2.1 Что должно происходить после коммита

Текущий intended flow:

1. Коммит в VS Code или harness.
2. Push в любую ветку.
3. GitHub запускает `Advisory CI` и `Authoring Guardrails` на `push`.
4. После открытия Pull Request те же проверки запускаются на `pull_request`.
5. В `Advisory CI/sanity-check` вызывается:

```bash
uv run just check
```

6. Отдельные jobs запускают `pip-audit`, `gitleaks` и container smoke checks.
7. Semgrep и mutation остаются schedule/manual advisory jobs, пока политика не
   изменит их статус.

Проверить локально отсутствие path-фильтров:

```bash
uv run python scripts/check_workflow_no_path_filter.py
```

Проверить workflow-файлы:

```bash
grep -R "^  push:\|^  pull_request:\|paths:\|paths-ignore:" -n .github/workflows
```

Ожидание: у blocking workflows есть `pull_request` и `push` без `paths` и без
ограничения только на `main`. Это обеспечивает запуск после коммита в
feature-ветку, ещё до создания PR.

### 2.2 Проверка GitHub Actions после push

После тестового или рабочего push открыть:

```text
GitHub → Actions → Advisory CI
GitHub → Actions → Authoring Guardrails
```

Проверить:

- workflow создан именно для нужного commit SHA;
- оба workflow действительно запустились;
- `sanity-check` не был skipped;
- `uv lock --check` прошёл;
- `uv run just check` был выполнен;
- coverage artifact создан даже при failure (`if: always()`);
- причина failure видна в job summary и не скрыта `|| true`.

Если запусков нет, проверить branch/event filters, а не повторять push
вслепую. Сохранить URL run и commit SHA.

---

## 3. S9: CI и security simulation

Выполнять сначала локальные проверки, затем Docker и внешние security gates.

### 3.1 Авторитетные локальные gates

```bash
just lock-check
just dependency-contract-check
just authoring-check
just contract-check
just no-mocked-dataclasses
just typecheck
just lint
just test
```

`just test` может завершиться failure только из-за coverage gate. Это не повод
понижать threshold во время проверки. Сохранить значение coverage и список
uncovered modules.

### 3.2 Docker build и smoke

```bash
docker build -f Dockerfile.fa -t fa-image:ci .
docker run --rm --user 1000:1000 --read-only --tmpfs /tmp \
  fa-image:ci fa --version
docker run --rm --user 1000:1000 --read-only --tmpfs /tmp \
  fa-image:ci fa egress-proxy --help >/dev/null
```

Проверить mount topology и writable session state:

```bash
mkdir -p /tmp/fa-ci-repo /tmp/fa-ci-sessions /tmp/fa-ci-state
cd /tmp/fa-ci-repo
git init -q
git config user.email ci@test
git config user.name ci
git commit --allow-empty -q -m init
sudo chown -R 1000:1000 /tmp/fa-ci-sessions /tmp/fa-ci-state
cd -

docker run --rm --user 1000:1000 --read-only \
  --tmpfs /tmp --tmpfs /home/fa/.cache --tmpfs /home/fa/.local \
  -v /tmp/fa-ci-repo:/repo:ro \
  -v /tmp/fa-ci-sessions:/sessions \
  -v /tmp/fa-ci-state:/home/fa/.fa \
  -e FA_RUN_ID=ci-smoke \
  fa-image:ci bash -c '
    set -euo pipefail
    test -d /sessions/ci-smoke/.git
    test -f /sessions/.active
    test "$PWD" = "/sessions/ci-smoke"
    fa --version
  '

sudo rm -rf /tmp/fa-ci-repo /tmp/fa-ci-sessions /tmp/fa-ci-state
```

Нельзя считать build достаточным: image должен стартовать от uid 1000 на
read-only rootfs и иметь writable только разрешённые mount points.

### 3.3 Security gates

```bash
uv run pip-audit

gitleaks detect --no-banner --redact --source .

# Если Semgrep установлен локально:
semgrep --config=p/python --config=p/owasp-top-ten

# Mutation — только после проверки scope в pyproject.toml:
uv run mutmut run
uv run mutmut results
uv run mutmut export-cicd-stats
```

Для каждого failure записать:

- точную команду;
- commit SHA;
- exit code;
- artifact/log URL;
- категорию: product defect, checker defect, environment issue,
  pre-existing debt или regression.

Не использовать `|| true`, чтобы сделать локальный результат зелёным. В CI
advisory jobs `continue-on-error` допустим только если это явно является
политикой workflow и failure всё равно виден оператору.

---

## 4. Проверка shipped harness path

### 4.1 Bootstrap и CLI

```bash
just agent-bootstrap
FA_AGENT_READY=1 uv run fa --version
uv run fa --help
uv run fa egress-proxy --help
```

### 4.2 Реальный session path

Провести минимальный тест в временном workspace:

```bash
tmp=$(mktemp -d)
cd "$tmp"
git init -q
git config user.email ci@test
git config user.name ci
echo '# harness smoke' > README.md
git add README.md
git commit -q -m init

# Запустить shipped CLI в штатной роли/режиме проекта.
# Использовать только тестовый provider/config; реальные ключи не печатать.
uv run fa run --help
```

Затем проверить в фактическом продуктово поддерживаемом режиме:

- session DB создана в per-run state location;
- JSONL — только mirror, authority остаётся SQLite;
- EventLog содержит start/turn/tool/result/stop события;
- EventBus/renderer показывает соответствующие OutputEvent;
- blocked command возвращает structured deny/error code;
- provider failure возвращает nonzero outcome;
- PTY Ctrl+C останавливает worker и не оставляет hanging process;
- workspace containment отклоняет `../` и symlink escape;
- secrets не попадают в env, logs, artifacts или tool output.

Проверять не только текст. Основные oracles:

1. event kind + structured fields;
2. SessionOutcome/exit code;
3. tool trajectory;
4. provider call count/token band;
5. filesystem/session DB;
6. deny/error code.

После smoke test уничтожить временный workspace и проверить отсутствие
лишних процессов:

```bash
ps aux | grep -E 'fa|tmux|pexpect' | grep -v grep || true
```

---

## 5. Ручная проверка GitHub governance

Владелец репозитория открывает:

```text
Settings → Rules → Rulesets
Settings → Branches → Branch protection rules
Settings → Collaborators / Access
Settings → Actions → General
```

Проверить на ветке `main`:

- required status checks включают authoritative sanity-check;
- Authoring Guardrails является required check, если это политика проекта;
- PR review/Code Owner policy соответствует проектному решению;
- force-push и deletion main запрещены;
- agent identity не имеет merge/approve/bypass permission;
- maintainer emergency override остаётся возможным и аудируемым;
- required checks используют правильные имена jobs, без старых duplicate names;
- workflow permissions минимальны (`contents: read` для CI jobs);
- Dependabot/secret scanning или выбранные эквиваленты включены согласно
  security policy.

Создать тестовый PR из feature-ветки и убедиться, что merge заблокирован при
падении required check. Не нажимать merge в ходе проверки.

---

## 6. Финальный review worktree

Перед коммитом:

```bash
git status --short
git diff --check
git diff --stat
git diff --name-status
git diff -- .github/workflows justfile pyproject.toml scripts knowledge worklogs
```

Проверить отдельно:

- нет секретов и временных файлов;
- нет `.fa/` runtime state в staged changes;
- нет удалённых/ослабленных тестов;
- нет глобальных Ruff/mypy/coverage suppressions;
- изменения тестов соответствуют правилу `TEST-EDITS:` там, где применимо;
- имя `scripts/fa_host_layout_audit.py` отражено во всех docs/deploy refs;
- `uv.lock` соответствует `pyproject.toml`;
- patch начинается от ожидаемого base commit.

Полный локальный финал:

```bash
uv lock --locked
just agent-bootstrap
just check
```

Если `just check` красный только из-за coverage, не изменять gate в этом же
коммите без отдельного policy decision. Сохранить coverage report и открыть
следующий coverage slice.

---

## 7. Коммит из VS Code или harness

### Вариант A: VS Code

```bash
git status --short
git add -A
git diff --cached --check
git commit -m "ci: close quality and guardrail gaps"
git push origin <feature-branch>
```

Не использовать `--no-verify` без документированного operator-only emergency
reason. После push открыть Actions и проверить оба push workflow.

### Вариант B: harness

Harness должен выполнить те же preflight checks, показать diff человеку и
остановиться перед commit, если нет явного human authorization. Минимальный
контракт:

```text
1. report branch + base SHA;
2. show changed files and diff summary;
3. run just check;
4. report failures without hiding them;
5. request human confirmation;
6. commit only after confirmation;
7. push only to the agreed branch;
8. return commit SHA and workflow URLs.
```

---

## 8. Применение подготовленного patch

Patch создаётся от commit:

```text
db6fd884e38092e44254a1f33f6c259aa1297d2b
```

На целевой копии:

```bash
git fetch --all --prune
git switch <target-branch>
git reset --hard db6fd884e38092e44254a1f33f6c259aa1297d2b

git apply --check first-agent-quality-closure.patch
git apply --index first-agent-quality-closure.patch
git status --short
git diff --cached --check
```

Если patch предназначен для review, не использовать `--index`; сначала
проверить обычный diff. Если `git apply --check` не проходит, остановиться и
сохранить конфликт вместо ручного silent merge.

После применения повторить bootstrap, `just check`, security simulation и
проверку GitHub Actions. Patch не является доказательством CI: доказательством
является успешный run на commit, который будет отправлен в GitHub.

---

## 9. Критерии завершения

Считать live execution завершённым только при наличии:

- commit SHA и clean/объяснимого worktree;
- `FA_AGENT_READY=1`;
- локальных check logs;
- Docker smoke evidence;
- pip-audit/gitleaks/Semgrep/mutation disposition;
- harness session-path evidence;
- GitHub Actions run URLs;
- ручной governance checklist с владельцем и датой;
- patch apply verification, если использовался patch;
- отдельного списка оставшихся coverage gaps.

Не объявлять CI зелёным по одному локальному тесту или по импорту символа.
