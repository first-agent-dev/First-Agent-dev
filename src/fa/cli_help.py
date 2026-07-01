# ruff: noqa: RUF001
"""Bilingual (ru/en) command-help registry — single source of truth.

This module is the one place that describes every ``fa`` command and its
arguments in both Russian and English. Three consumers read from it:

1. The CLI itself (``fa <cmd> -h`` / ``fa -h``) renders the Russian help block
   as an argparse *epilog*, so argparse keeps doing the parsing/validation while
   operators get Russian explanations and copy-paste examples.
2. The host-side ``scripts/fa`` wrapper can print the same Russian help without
   entering the container.
3. A future WebUI consumes :func:`help_as_dict` (exposed by ``fa help --json``)
   to render per-command help buttons / tooltips. That JSON shape is the stable
   WebUI contract: ``{command: {summary_ru, summary_en, args:{name:{ru,en}},
   examples:[...]}}``.

Design rule (AGENTS.md #3 — every artefact has a consumer): adding a new
subcommand means adding one entry here; the CLI ``-h`` and the WebUI both pick
it up automatically.
"""

from __future__ import annotations

import json
from typing import TypedDict


class ArgHelp(TypedDict):
    """Bilingual help for a single argument or flag."""

    ru: str
    en: str


class CommandHelp(TypedDict):
    """Bilingual help for one ``fa`` subcommand."""

    summary_ru: str
    summary_en: str
    args: dict[str, ArgHelp]
    examples: list[str]


# ── The registry ──────────────────────────────────────────────────────────
# Keys are subcommand names exactly as registered in ``fa.cli.build_parser``.
# Arg keys use the canonical display form ("--role/-r", "task", "-") so the
# same string serves CLI rendering and the WebUI contract.
COMMANDS: dict[str, CommandHelp] = {
    "run": {
        "summary_ru": "Запустить LLM-сессию агента для одной роли.",
        "summary_en": "Drive an LLM coder session for one role.",
        "args": {
            "task": {
                "ru": "Текст задачи в кавычках (позиционный). '-' — читать задачу из stdin. "
                "Можно также через --task.",
                "en": "Task text in quotes (positional). '-' reads the task from stdin. "
                "Also accepted via --task.",
            },
            "--role/-r": {
                "ru": "Роль: planner | coder | eval (по умолчанию coder). Должна совпадать "
                "с ключом верхнего уровня в ~/.fa/models.yaml.",
                "en": "Role: planner | coder | eval (default coder). Must match a top-level "
                "key in ~/.fa/models.yaml.",
            },
            "--max-turns/-n": {
                "ru": "Лимит ходов LLM (по умолчанию 16).",
                "en": "LLM-turn cap (default 16).",
            },
            "--workspace/-w": {
                "ru": "Корень рабочего пространства; пути инструментов считаются "
                "относительно него.",
                "en": "Workspace root; tool paths resolve relative to it.",
            },
            "--config/-c": {
                "ru": "Путь к models.yaml (по умолчанию ~/.fa/models.yaml).",
                "en": "Path to models.yaml (default ~/.fa/models.yaml).",
            },
            "--run-id/-i": {
                "ru": "Переопределить run_id (по умолчанию выводится из PID).",
                "en": "Override the run_id (default derived from PID).",
            },
            "--resume": {
                "ru": "Продолжить существующую сессию: сохранить PR-draft на диске, чтобы "
                "прочитать work-log предыдущей роли.",
                "en": "Resume an existing session: preserve the on-disk PR draft so the "
                "previous role's work log can be read.",
            },
        },
        "examples": [
            'fa run "Исправь баг в src/fa/x.py"',
            'fa run -r planner "Спланируй рефакторинг модуля X"',
            'fa run -r coder -n 24 "Большая задача"',
            'git diff | fa run -r eval "Проверь этот дифф"',
        ],
    },
    "workflow": {
        "summary_ru": "Запустить multi-role workflow одной командой "
        "(planner → coder → eval) с общими run-id и workspace.",
        "summary_en": "Run a multi-role pipeline in one command (planner → coder → eval) "
        "with a shared run-id and workspace.",
        "args": {
            "roles": {
                "ru": "Список ролей через запятую в порядке выполнения, напр. planner,coder,eval "
                "(позиционный, первый).",
                "en": "Comma-separated roles in execution order, e.g. planner,coder,eval "
                "(first positional).",
            },
            "task": {
                "ru": "Текст задачи в кавычках (позиционный, второй). Передаётся каждой роли, "
                "если не задан per-role через --task-<role>.",
                "en": "Task text in quotes (second positional). Passed to every role unless "
                "overridden per-role via --task-<role>.",
            },
            "--task-<role>": {
                "ru": 'Переопределить задачу для конкретной роли, напр. --task-planner "...".',
                "en": 'Override the task for a specific role, e.g. --task-planner "...".',
            },
            "--workspace/-w": {
                "ru": "Общий корень рабочего пространства для всех ролей.",
                "en": "Shared workspace root for every role.",
            },
            "--run-id/-i": {
                "ru": "Общий run_id для всех ролей (по умолчанию генерируется "
                "из времени и задачи).",
                "en": "Shared run_id for all roles (default generated from timestamp + task).",
            },
            "--config/-c": {
                "ru": "Путь к models.yaml (по умолчанию ~/.fa/models.yaml).",
                "en": "Path to models.yaml (default ~/.fa/models.yaml).",
            },
            "--max-turns/-n": {
                "ru": "Лимит ходов LLM на каждую роль.",
                "en": "LLM-turn cap applied to each role.",
            },
            "--mode/-m": {
                "ru": "Стратегия маршрутизации: 'linear' — один проход; 'repair' — "
                "ограниченные coder→eval раунды; 'adaptive' — planner re-entry по eval route.",
                "en": "Routing strategy: 'linear' single pass; 'repair' bounded coder→eval "
                "rounds; 'adaptive' planner re-entry from the eval route.",
            },
            "--max-repairs": {
                "ru": "Макс. число раундов coder→eval в режимах repair/adaptive "
                "(по умолчанию 2, жёсткий потолок 3).",
                "en": "Max coder→eval repair rounds in repair/adaptive "
                "(default 2, hard ceiling 3).",
            },
            "--max-replans": {
                "ru": "Макс. число planner re-entry раундов в adaptive "
                "(по умолчанию 1, жёсткий потолок 2).",
                "en": "Max planner re-entry rounds in adaptive (default 1, hard ceiling 2).",
            },
        },
        "examples": [
            'fa workflow planner,coder,eval "Реализуй фичу X"',
            'fa workflow coder,eval "Доделай и проверь src/fa/y.py"',
            'fa workflow coder,eval "Доведи src/fa/y.py до green" --mode repair --max-repairs 2',
            'fa workflow planner,coder,eval "Проведи adaptive цикл" '
            "--mode adaptive --max-replans 1",
            'fa workflow planner,coder,eval --task-planner "Спланируй" --task-coder "Сделай" '
            '"Проверь результат"',
        ],
    },
    "selfcheck": {
        "summary_ru": "Диагностика пути LLM через egress-proxy (без обращения к провайдеру).",
        "summary_en": "Diagnose the egress-proxy LLM path (no provider call).",
        "args": {
            "--role/-r": {
                "ru": "Роль для проверки (по умолчанию coder).",
                "en": "Role to check (default coder).",
            },
            "--config/-c": {
                "ru": "Путь к models.yaml (по умолчанию ~/.fa/models.yaml).",
                "en": "Path to models.yaml (default ~/.fa/models.yaml).",
            },
        },
        "examples": ["fa selfcheck", "fa selfcheck -r planner"],
    },
    "probe": {
        "summary_ru": "Liveness-тест цепочки провайдеров реальным минимальным "
        "запросом (~10 токенов).",
        "summary_en": "Liveness-test the provider chain with a minimal real call (~10 tokens).",
        "args": {
            "--role/-r": {
                "ru": "Роль для проверки (по умолчанию coder).",
                "en": "Role to probe (default coder).",
            },
            "--all-roles": {
                "ru": "Проверить все роли из ~/.fa/models.yaml.",
                "en": "Probe every role in ~/.fa/models.yaml.",
            },
            "--config/-c": {
                "ru": "Путь к models.yaml (по умолчанию ~/.fa/models.yaml).",
                "en": "Path to models.yaml (default ~/.fa/models.yaml).",
            },
            "--timeout": {
                "ru": "Таймаут на запись в секундах (по умолчанию 30).",
                "en": "Per-entry timeout in seconds (default 30).",
            },
        },
        "examples": ["fa probe", "fa probe --all-roles", "fa probe -r planner --timeout 60"],
    },
    "stats": {
        "summary_ru": "Аналитика сессий: использование инструментов, файлы, токены, эффективность.",
        "summary_en": "Session analytics: tool usage, file access, tokens, efficiency.",
        "args": {
            "--run-id/-i": {
                "ru": "Анализировать конкретную сессию.",
                "en": "Analyze a specific session.",
            },
            "--since": {
                "ru": "Фильтр по возрасту (напр. 7d, 24h, 1h).",
                "en": "Filter by age (e.g. 7d, 24h, 1h).",
            },
            "--output": {
                "ru": "Формат вывода: console | json.",
                "en": "Output format: console | json.",
            },
            "--workspace/-w": {
                "ru": "Корень рабочего пространства (для анализа dead-zones в src/).",
                "en": "Workspace root (for src/ dead-zone analysis).",
            },
            "--dead-zones": {
                "ru": "Показать файлы src/, к которым ни одна сессия не обращалась.",
                "en": "Show src/ files never accessed by any session.",
            },
        },
        "examples": ["fa stats", "fa stats --since 7d", "fa stats -i work-1 --output json"],
    },
    "chunk": {
        "summary_ru": "Прогнать детерминированный chunker по одному файлу (для инспекции).",
        "summary_en": "Run the deterministic chunker on one file (for inspection).",
        "args": {
            "path": {"ru": "Путь к файлу (позиционный).", "en": "Path to the file (positional)."},
            "--output": {
                "ru": "Формат: text | json.",
                "en": "Format: text | json.",
            },
        },
        "examples": ["fa chunk README.md", "fa chunk src/fa/cli.py --output json"],
    },
    "authoring-check": {
        "summary_ru": "Запустить Level-0 ядро authoring-guardrails (ADR-11 two-tier TCB).",
        "summary_en": "Run the Level-0 authoring-guardrail kernel (ADR-11 two-tier TCB).",
        "args": {
            "--workspace/-w": {
                "ru": "Корень workspace (должен содержать knowledge/llms.txt).",
                "en": "Workspace root (must contain knowledge/llms.txt).",
            },
            "--manifest": {
                "ru": "Опциональный путь к .fa/session.toml.",
                "en": "Optional path to .fa/session.toml.",
            },
            "--output": {"ru": "Формат: text | json.", "en": "Format: text | json."},
        },
        "examples": ["fa authoring-check", "fa authoring-check --output json"],
    },
}

# Host-side wrapper commands from scripts/fa. Keep operator-facing text here
# (not in the bash wrapper) so Python CLI help, host wrapper help, and future
# WebUI metadata have one source of truth.
HOST_COMMANDS: dict[str, CommandHelp] = {
    "logs": {
        "summary_ru": "Показать логи контейнера first-agent через docker compose logs.",
        "summary_en": "Show first-agent container logs via docker compose logs.",
        "args": {
            "-f/--follow": {"ru": "Смотреть поток логов в реальном времени.", "en": "Follow logs."},
            "--tail=N": {"ru": "Показать последние N строк.", "en": "Show the last N lines."},
            "--since=10m": {
                "ru": "Показать только свежие логи, например 10m или 1h.",
                "en": "Show logs since a duration such as 10m or 1h.",
            },
            "--timestamps": {"ru": "Показать timestamps.", "en": "Show timestamps."},
        },
        "examples": ["fa logs -f --tail=50", "fa logs --since=10m"],
    },
    "proxy-logs": {
        "summary_ru": "Показать логи контейнера fa-egress-proxy через docker compose logs.",
        "summary_en": "Show fa-egress-proxy container logs via docker compose logs.",
        "args": {
            "-f/--follow": {"ru": "Смотреть поток логов в реальном времени.", "en": "Follow logs."},
            "--tail=N": {"ru": "Показать последние N строк.", "en": "Show the last N lines."},
            "--since=10m": {"ru": "Показать только свежие логи.", "en": "Show fresh logs only."},
            "--timestamps": {"ru": "Показать timestamps.", "en": "Show timestamps."},
        },
        "examples": ["fa proxy-logs -f", "fa proxy-logs --tail=100"],
    },
    "status": {
        "summary_ru": "Показать состояние сервисов FA stack через docker compose ps.",
        "summary_en": "Show FA stack service status via docker compose ps.",
        "args": {},
        "examples": ["fa status"],
    },
    "up": {
        "summary_ru": "Запустить FA docker compose stack в фоне.",
        "summary_en": "Start the FA docker compose stack in the background.",
        "args": {},
        "examples": ["fa up"],
    },
    "down": {
        "summary_ru": "Остановить FA docker compose stack.",
        "summary_en": "Stop the FA docker compose stack.",
        "args": {},
        "examples": ["fa down"],
    },
    "restart": {
        "summary_ru": "Перезапустить runtime-контейнеры first-agent и fa-egress-proxy.",
        "summary_en": "Restart first-agent and fa-egress-proxy runtime containers.",
        "args": {},
        "examples": ["fa restart"],
    },
    "rebuild": {
        "summary_ru": "Пересобрать Docker images и поднять stack заново через "
        "docker compose up -d --build.",
        "summary_en": "Rebuild Docker images and bring the stack up with "
        "docker compose up -d --build.",
        "args": {},
        "examples": ["fa rebuild", "fa help clean-rebuild"],
    },
    "shell": {
        "summary_ru": "Открыть bash внутри first-agent; при активной isolated session "
        "войти сразу в её workspace.",
        "summary_en": "Open bash inside first-agent, using the active isolated session "
        "workspace when present.",
        "args": {
            "bash-args...": {
                "ru": "Любые аргументы bash, например -lc 'команда'.",
                "en": "Any bash arguments, e.g. -lc 'command'.",
            },
        },
        "examples": [
            "fa shell",
            "fa shell -lc 'pwd && git status --short'",
            "fa shell -lc 'uv run just check'",
        ],
    },
    "update": {
        "summary_ru": "Запустить scripts/fa-update.sh: обновить checkout, решить нужен ли "
        "build/restart, дождаться health и выполнить deploy checks.",
        "summary_en": "Run scripts/fa-update.sh: update checkout, decide build/restart, "
        "wait for health, run deploy checks.",
        "args": {
            "AUTO_STASH=1": {
                "ru": "Автоматически stash'ить грязное рабочее дерево перед git pull.",
                "en": "Automatically stash a dirty worktree before git pull.",
            },
            "SKIP_TESTS=1": {
                "ru": "Пропустить pytest на шаге проверки.",
                "en": "Skip pytest during verification.",
            },
            "SKIP_UV_SYNC=1": {
                "ru": "Не делать uv sync перед pytest.",
                "en": "Do not run uv sync before pytest.",
            },
            "NO_CACHE=1": {
                "ru": "Собирать Docker images без cache.",
                "en": "Build Docker images without cache.",
            },
            "PRUNE=0": {
                "ru": "Не делать docker image prune в конце.",
                "en": "Do not run docker image prune at the end.",
            },
            "PRUNE_UNTIL=72h": {
                "ru": "Возраст image prune filter (по умолчанию 72h).",
                "en": "Age for image prune filter (default 72h).",
            },
            "HEALTH_TIMEOUT_SECONDS=N": {
                "ru": "Сколько секунд ждать healthy-статус контейнера.",
                "en": "Seconds to wait for container health.",
            },
            "COMPOSE_BUILD_PULL=0": {
                "ru": "Не передавать --pull в docker compose build.",
                "en": "Do not pass --pull to docker compose build.",
            },
            "FORCE=1": {
                "ru": "Всегда build+deploy, как --force.",
                "en": "Always build+deploy, same as --force.",
            },
            "SERVICE_NAME_OVERRIDE=name": {
                "ru": "Переопределить compose service для agent-контейнера.",
                "en": "Override compose service for the agent container.",
            },
            "REPO_DIR=path": {
                "ru": "Путь к checkout First-Agent-dev.",
                "en": "Path to the First-Agent-dev checkout.",
            },
            "COMPOSE_FILE=file": {
                "ru": "Compose-файл относительно REPO_DIR.",
                "en": "Compose file relative to REPO_DIR.",
            },
            "LOCK_FILE=path": {
                "ru": "Lock-файл update-процесса.",
                "en": "Update-process lock file.",
            },
            "LOG_FILE=path": {"ru": "Лог update-процесса.", "en": "Update-process log file."},
            "--force": {"ru": "То же, что FORCE=1.", "en": "Same as FORCE=1."},
            "-h/--help": {"ru": "Показать эту справку wrapper'а.", "en": "Show this wrapper help."},
        },
        "examples": [
            "fa update",
            "SKIP_TESTS=1 AUTO_STASH=1 fa update",
            "NO_CACHE=1 HEALTH_TIMEOUT_SECONDS=120 fa update --force",
        ],
    },
    "clean-rebuild": {
        "summary_ru": "Запустить scripts/fa-clean-rebuild.sh: остановить stack, "
        "при необходимости обновить checkout, сделать backup, очистить runtime-состояние "
        "по env-флагам, пересобрать images и поднять контейнеры.",
        "summary_en": "Run scripts/fa-clean-rebuild.sh: stop stack, optionally update "
        "checkout, back up, clean runtime state by env flags, rebuild images, "
        "start containers.",
        "args": {
            "WIPE_STATE=1": {
                "ru": "Удалить state/ и sessions/, сбросить routing/models.yaml.",
                "en": "Delete state/ and sessions/, reset routing/models.yaml.",
            },
            "PRUNE=1": {
                "ru": "Выполнить docker system prune -af после teardown.",
                "en": "Run docker system prune -af after teardown.",
            },
            "NO_CACHE=0": {
                "ru": "Разрешить Docker cache при build (по умолчанию build без cache).",
                "en": "Allow Docker cache during build (default is no-cache build).",
            },
            "COMPOSE_BUILD_PULL=0": {
                "ru": "Не передавать --pull в docker compose build.",
                "en": "Do not pass --pull to docker compose build.",
            },
            "BUILD_PROGRESS=plain": {
                "ru": "Показать подробный BuildKit progress-вывод.",
                "en": "Show detailed BuildKit progress output.",
            },
            "NO_BACKUP=1": {
                "ru": "Пропустить backup state/routing/secrets (не рекомендуется).",
                "en": "Skip state/routing/secrets backup (not recommended).",
            },
            "ASSUME_YES=1": {
                "ru": "Не спрашивать подтверждение для destructive-флагов.",
                "en": "Do not prompt for destructive flags.",
            },
            "SKIP_UPDATE=1": {
                "ru": "Не делать git pull; использовать текущий checkout.",
                "en": "Do not git pull; use current checkout.",
            },
            "AUTO_STASH=1": {
                "ru": "Автоматически stash'ить грязное рабочее дерево перед pull.",
                "en": "Automatically stash a dirty worktree before pull.",
            },
            "GIT_BRANCH=main": {
                "ru": "Ветка, которую должен использовать deploy checkout.",
                "en": "Branch the deploy checkout should use.",
            },
            "HEALTH_TIMEOUT_SECONDS=N": {
                "ru": "Сколько секунд ждать healthy-статус каждого контейнера.",
                "en": "Seconds to wait for each container to become healthy.",
            },
            "FA_DIR=path": {
                "ru": "Корень деплоя (по умолчанию /srv/first-agent).",
                "en": "Deploy root (default /srv/first-agent).",
            },
            "REPO_DIR=path": {
                "ru": "Путь к checkout First-Agent-dev.",
                "en": "Path to the First-Agent-dev checkout.",
            },
            "COMPOSE_FILE=file": {
                "ru": "Compose-файл относительно REPO_DIR.",
                "en": "Compose file relative to REPO_DIR.",
            },
            "SERVICE=name": {
                "ru": "systemd user service name.",
                "en": "systemd user service name.",
            },
            "FA_USER=user": {"ru": "Владелец runtime-файлов.", "en": "Owner of runtime files."},
            "-h/--help": {"ru": "Показать эту справку wrapper'а.", "en": "Show this wrapper help."},
        },
        "examples": [
            "fa clean-rebuild",
            "WIPE_STATE=1 ASSUME_YES=1 fa clean-rebuild",
            "SKIP_UPDATE=1 NO_BACKUP=1 BUILD_PROGRESS=plain fa clean-rebuild",
        ],
    },
    "commit-traces": {
        "summary_ru": "Force-add и commit session trace artifacts: "
        "knowledge/trace/codebase_map.json и knowledge/trace/gotchas.md.",
        "summary_en": "Force-add and commit session trace artifacts.",
        "args": {},
        "examples": ["fa commit-traces"],
    },
    "sessions": {
        "summary_ru": "Показать session workspaces под /srv/first-agent/sessions, новые сверху.",
        "summary_en": "Show session workspaces under /srv/first-agent/sessions, newest first.",
        "args": {},
        "examples": ["fa sessions"],
    },
}

HOST_USAGE: dict[str, str] = {
    "update": "fa update [env]",
    "clean-rebuild": "fa clean-rebuild [env]",
    "logs": "fa logs [flags]",
    "proxy-logs": "fa proxy-logs [flags]",
    "shell": "fa shell [bash-args...]",
}


def render_command_help_ru(command: str) -> str:
    """Render the Russian help epilog for one command (used as argparse epilog)."""
    entry = COMMANDS.get(command)
    if entry is None:
        return ""
    lines: list[str] = [entry["summary_ru"], ""]
    if entry["args"]:
        lines.append("Аргументы (RU):")
        width = max(len(name) for name in entry["args"])
        for name, help_pair in entry["args"].items():
            lines.append(f"  {name.ljust(width)}  {help_pair['ru']}")
        lines.append("")
    if entry["examples"]:
        lines.append("Примеры:")
        lines.extend(f"  {ex}" for ex in entry["examples"])
    return "\n".join(lines)


def render_top_level_ru() -> str:
    """Render the Russian one-line summary table for all commands."""
    lines = ["Команды (RU):"]
    width = max(len(name) for name in COMMANDS)
    for name, entry in COMMANDS.items():
        lines.append(f"  {name.ljust(width)}  {entry['summary_ru']}")
    return "\n".join(lines)


def render_host_command_help_ru(command: str) -> str:
    """Render detailed Russian help for one host-side wrapper command."""

    entry = HOST_COMMANDS.get(command)
    if entry is None:
        return ""
    lines: list[str] = [
        HOST_USAGE.get(command, f"fa {command}"),
        "",
        "Что делает:",
        f"  {entry['summary_ru']}",
        "",
    ]
    if entry["args"]:
        lines.append("Переменные окружения и параметры:")
        width = max(len(name) for name in entry["args"])
        for name, help_pair in entry["args"].items():
            lines.append(f"  {name.ljust(width)}  {help_pair['ru']}")
        lines.append("")
    else:
        lines.extend(["Параметры:", "  Нет.", ""])
    if entry["examples"]:
        lines.append("Примеры:")
        lines.extend(f"  {ex}" for ex in entry["examples"])
    return "\n".join(lines)


def render_host_top_level_ru() -> str:
    """Render the Russian one-line summary table for host-side wrapper commands."""

    lines = ["Инфраструктура на хосте (docker compose):"]
    width = max(len(name) for name in HOST_COMMANDS)
    for name, entry in HOST_COMMANDS.items():
        usage = HOST_USAGE.get(name, f"fa {name}").removeprefix("fa ")
        lines.append(f"  {usage.ljust(width + 12)}  {entry['summary_ru']}")
    return "\n".join(lines)


def render_wrapper_usage_ru() -> str:
    """Render top-level help for the host-side scripts/fa wrapper."""

    return "\n\n".join(
        [
            "Использование: fa <команда> [аргументы...]",
            render_host_top_level_ru(),
            render_top_level_ru().replace("Команды (RU):", "Agent CLI внутри контейнера:"),
            "Справка:\n"
            "  fa help <topic>      Подробная справка по host-команде или agent-команде\n"
            "  fa <topic> --help    Флаги/параметры конкретной команды\n\n"
            "Примеры:\n"
            "  fa help clean-rebuild\n"
            "  fa clean-rebuild --help\n"
            "  fa help run\n"
            "  fa run --help\n\n"
            "Host-команды обрабатываются wrapper'ом. Agent-команды делегируются внутрь "
            "контейнера. Новые Python subcommands в src/fa/cli.py работают без изменения "
            "wrapper'а.",
        ]
    )


def host_help_as_dict() -> dict[str, CommandHelp]:
    """Return the host-side wrapper help registry."""

    return HOST_COMMANDS


def host_help_as_json(*, indent: int = 2) -> str:
    """Serialize host-side wrapper help as JSON."""

    return json.dumps(HOST_COMMANDS, ensure_ascii=False, indent=indent)


def help_as_dict() -> dict[str, CommandHelp]:
    """Return the full bilingual registry — the stable WebUI contract."""
    return COMMANDS


def help_as_json(*, indent: int = 2) -> str:
    """Serialize the registry as JSON (``fa help --json`` output)."""
    return json.dumps(COMMANDS, ensure_ascii=False, indent=indent)


def _main(argv: list[str] | None = None) -> int:
    """Small renderer CLI used by the host-side bash wrapper."""

    import argparse

    parser = argparse.ArgumentParser(prog="python -m fa.cli_help")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--wrapper-usage", action="store_true")
    group.add_argument("--host-topic")
    group.add_argument("--host-json", action="store_true")
    args = parser.parse_args(argv)

    if args.wrapper_usage:
        print(render_wrapper_usage_ru())
        return 0
    if args.host_topic is not None:
        rendered = render_host_command_help_ru(args.host_topic)
        if not rendered:
            return 2
        print(rendered)
        return 0
    if args.host_json:
        print(host_help_as_json())
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover - exercised via scripts/fa tests.
    raise SystemExit(_main())
