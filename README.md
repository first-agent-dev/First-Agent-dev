# First-Agent

Репозиторий, в котором я собираю **собственного LLM-агента** вместе с devin.ai/arena.ai

📖 **Развернуть / администрировать?** Начните отсюда:
**[knowledge/instructions/README.md](./knowledge/instructions/README.md)** —
установка, обновление и эксплуатация AIO-деплоя.

> **Статус:** 
Разработка ARD-9-llm-provider-client;
deterministic harness ADR-10-runtime determinism,
prep work for ADR-11-autoring determinism cretion;
first tests cli-ready.
---

## 1. Зачем это

**First-Agent** — research-backed implementation-first проект, стремящийся
стать open-source reference implementation для locally orchestrated coding
agents. Помимо самого факта построения работающего harness, проект ставит
4 явных цели (полная формулировка —
[`knowledge/project-overview.md` §1.1](./knowledge/project-overview.md#11-четыре-столпа-цели-project-goal--four-pillars)):

1. Пройти весь путь от формулировки до working prototype, документируя
   каждое архитектурное решение через ADR + research note. Ригор делает
   репо одновременно учебным инструментом и forkable reference.
2. Выпустить v0.1 как pragmatic single-user product под UC1 (coding+PR) +
   UC3 (local-docs-to-wiki) с hybrid-shape (filesystem-canon + lazy
   search-side scaling).
3. Построить **наиболее token- и tool-call-efficient harness** среди
   известных open-source / open-design агент-стэков под целевые UC1+UC3
   при single-user single-workstation use. KPI-числа фиксируются после
   landing UC5 (eval-harness) и первого baseline-run; до того стоят
   как `TBD`.
4. **Iteration via measurement.** База в v0.1 — способность агента писать
   собственные skills (`SKILL.md`-файлы) по итогам решённых задач и
   найденных улучшений. UC5 (post-v0.1) расширяется до eval-driven
   harness iteration.

**Принцип построения — minimalism-first.** Не «вырезать лишнее потом», а
не добавлять без research-evidence или измеренного KPI-impact. Подробнее:
[`knowledge/project-overview.md` §1.2](./knowledge/project-overview.md#12-enforceable-principle--minimalism-first).

Опора — research papers (Tsinghua module-ablation `arXiv:2603.25723`,
Stanford / Khattab Meta-Harness `arXiv:2603.28052v1`, Anthropic engineering
posts), MCP-экосистема, и Devin / Claude Code / OSS repo's как reference-агенты.

---

## 2. Scope — что входит и что не входит

Полная версия — в
[`knowledge/project-overview.md`](./knowledge/project-overview.md) §4–§5.
Краткая выжимка:

### В scope (v0.1)

- **UC1** — coding + PR-write end-to-end (FA + 1–2 controlled-list
  репозитория пользователя).
- **UC3** — local-docs-to-wiki (`fa ingest <path-or-url>`,
  chunk-aware retrieval, Q&A).
- Static role-routing LLM tiering (Planner / Coder / Debug),
  mechanical-wiki memory (no embeddings/graph в v0.1), SQLite FTS5
  индекс, sandbox + path allow-list для тулов.

### Вне scope (v0.1)

- **UC2** continuous multi-source research — best-effort.
- **UC4** multi-user Telegram chat — deferred.
- **UC5** semi-autonomous multi-LLM research/experiment — deferred
  (см. [ADR-1 Amendment 2026-05-01](./knowledge/adr/ADR-1-v01-use-case-scope.md)).
- Production-деплой, мульти-тенантность, биллинг, собственный веб-UI,
  обучение/дообучение моделей, агент-общего-назначения «на всё».

---

## 3. Как работать с этим репо

Полный inventory всех документов — в
[`knowledge/llms.txt`](./knowledge/llms.txt) (one-fetch индекс,
[llmstxt.org](https://llmstxt.org/) convention). Конвенции по
структуре и работе — в [`AGENTS.md`](./AGENTS.md).

Для нового человека / агента:

1. Прочитать [`AGENTS.md`](./AGENTS.md) — repo conventions, query routing.
2. Прочитать [`knowledge/llms.txt`](./knowledge/llms.txt) — карта
   репо в одном fetch'е.
3. Просмотреть [`knowledge/project-overview.md`](./knowledge/project-overview.md)
   — что v0.1 ships и что non-goal.
4. Просмотреть индекс ADR — [`knowledge/adr/README.md`](./knowledge/adr/README.md).
5. Проверить [`HANDOFF.md`](./HANDOFF.md) — текущий snapshot
   состояния репо для cross-LLM сессий.

Дальше — по необходимости (ADR / research-нота / промпт). Не нужно
загружать всё в контекст сразу; routing-table в
[`AGENTS.md` §Query Routing](./AGENTS.md#query-routing).

---

## 4. Основные файлы

- [`AGENTS.md`](./AGENTS.md) — конвенции и инструкции для AI-агентов.
- [`HANDOFF.md`](./HANDOFF.md) — snapshot состояния для cross-LLM сессий.
- [`knowledge/README.md`](./knowledge/README.md) — как устроена память
  проекта (frontmatter schema, конвенции, supersession-rule).
- [`knowledge/llms.txt`](./knowledge/llms.txt) — one-fetch индекс
  всех документов.
- [`knowledge/instructions/`](./knowledge/instructions/README.md) —
  инструкции по развёртыванию и эксплуатации (install + operations).
- [`knowledge/adr/README.md`](./knowledge/adr/README.md) — индекс ADR.
- [`knowledge/pr-notes/`](./knowledge/pr-notes/README.md) — архив PR-заметок.

---

## Security / API Keys

### Local Development (WSL)

Export API keys in your shell (e.g. `~/.bashrc`):
```bash
export OPENROUTER_API_KEY=sk-or-v1-...
```

Or use `~/.fa/.env` (auto-loaded by the FA CLI):
```bash
mkdir -p ~/.fa
cat > ~/.fa/.env <<EOF
OPENROUTER_API_KEY=sk-or-v1-...
EOF
```

`~/.fa/models.yaml` references env var names via `api_key_env` — never paste real keys into `models.yaml`. Both `models.yaml` and `config.yaml` are gitignored.

### Production Deployment (AIO)

1. Copy the template and edit with real keys:
   ```bash
   cp .env.fa.template .env.fa
   # Edit .env.fa
   chmod 600 .env.fa
   ```

2. Docker Compose loads `.env.fa` via `env_file:` (see `docker-compose.fa.yml`).

3. Default container mode is stand-by for manual operation:
   ```bash
   docker exec -it first-agent bash
   fa run --task "inspect the repo" --role planner --workspace /workspace
   ```
   For an intentional one-shot startup run, set `FA_AUTO_RUN=1` plus either
   `FA_TASK` or `FA_TASK_FILE`; the entrypoint writes
   `/workspace/.fa/entrypoint-status.txt` and then returns to stand-by.

4. `models.yaml` lives in `/srv/first-agent/state/` (persistent bind-mount, auto-copied by `setup-fa-desktop.sh`).

5. Backup credentials (`B2_KEY_ID`, `B2_APPLICATION_KEY`) go in `/srv/first-agent/secrets/backup.env`, NOT in `.env.fa`.

### Secrets Management

| Category | Storage | Scope |
| --- | --- | --- |
| **LLM API keys** | `~/.fa/.env` (WSL) or `.env.fa` (AIO) | Container runtime only |
| **Backup credentials** | `/srv/first-agent/secrets/backup.env` | Host only (restic) |
| **Git deploy key** | `/srv/first-agent/secrets/github_deploy_key` | Host + container (read-only mount) |

- **LLM API keys** are needed for every LLM call. Stored in `~/.fa/.env` (WSL) or `.env.fa` (AIO).
- **Backup credentials** (B2 keys) are needed by the host cron job, not the container. Keeping them separate limits blast radius if the container is compromised.
- **Git deploy key** is an SSH key for git push; mounted read-only into the container.

**Why the separation matters:**

- The container trust boundary (Docker group membership) means any operator can `docker inspect` and see container env vars. Backup credentials are never injected into the container, so a container compromise does not grant B2 access.
- restic encrypts backups *before* uploading. If an API key leaks into `events.jsonl` before `SecretRedactor` masks it, the encrypted backup still contains it. Redaction is the primary defense; separation is secondary.
- `SecretRedactor` (exact-match + base64/URL encoding detection) runs in the observability layer and masks secrets before they reach `events.jsonl` or `knowledge/trace/`.

### Repository Hygiene

- `gitleaks` runs as a pre-commit hook and in GitHub Actions CI.
- Dummy test keys are allowlisted in `.gitleaks.toml`.
- **Never commit real API keys.**

---
