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
                "ru": "Переопределить задачу для конкретной роли, напр. --task-planner \"...\".",
                "en": "Override the task for a specific role, e.g. --task-planner \"...\".",
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
                "en": "Max planner re-entry rounds in adaptive "
                "(default 1, hard ceiling 2).",
            },
        },
        "examples": [
            'fa workflow planner,coder,eval "Реализуй фичу X"',
            'fa workflow coder,eval "Доделай и проверь src/fa/y.py"',
            'fa workflow coder,eval "Доведи src/fa/y.py до green" --mode repair --max-repairs 2',
            'fa workflow planner,coder,eval "Проведи adaptive цикл" '
            '--mode adaptive --max-replans 1',
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


def help_as_dict() -> dict[str, CommandHelp]:
    """Return the full bilingual registry — the stable WebUI contract."""
    return COMMANDS


def help_as_json(*, indent: int = 2) -> str:
    """Serialize the registry as JSON (``fa help --json`` output)."""
    return json.dumps(COMMANDS, ensure_ascii=False, indent=indent)
