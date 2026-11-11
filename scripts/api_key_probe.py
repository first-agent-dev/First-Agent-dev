#!/usr/bin/env python3
# ruff: noqa: RUF001, RUF002, RUF003, RUF100  # Русские строки и докстринги консоли.
"""Чат-стенд для Coarena (приоритет) и One AI API Key.

Один файл, только стандартная библиотека. Один маршрут на оба шлюза: OpenAI-формат
``POST {base}/chat/completions`` со стримом. Anthropic-формат убран намеренно —
второй путь удваивал код парсинга, не добавляя ничего к проверке ключа и модели.

Что умеет:

* чат как диалог: каждый запрос несёт весь хвост, поэтому модель помнит прошлые
  ходы; ``/q`` перечитывает ответ, ``/continue`` дописывает оборванный;
* вывод ответа в терминал с абзацами, таблицами и кодом (рассуждение скрыто);
* ``--save`` пишет диалог в markdown по ходу разговора;
* ``--models`` — доступные модели шлюза, ``--check`` — проверка ключа и модели;
* токены и усилие вручную: ``--max-tokens`` / ``/tokens``, ``--effort`` / ``/effort``.

Запуски::

    python api_key_probe.py                      # чат с Coarena
    python api_key_probe.py --models             # какие модели доступны
    python api_key_probe.py --check              # ключ + модель живы?
    python api_key_probe.py --prompt "привет"    # один вопрос и выход
    python api_key_probe.py --prompt-file в.txt  # то же, вопрос из файла
    python api_key_probe.py --save chat.md       # чат с записью в файл

Ключи: ``COARENA_KEY`` / ``ONEAI_KEY`` ниже либо переменные окружения
``COARENA_API_KEY`` / ``ONEAI_API_KEY``. Модель по умолчанию — ``COARENA_MODEL`` /
``ONEAI_MODEL``, перебивается ``-m``.

Важно про токены: ``reasoning_effort`` тратит **тот же** лимит, что и текст
ответа. На ``effort=high`` рассуждение легко занимает весь ``max_tokens``, и
ответ обрывается (``finish_reason: length``). Поэтому лимит отправляется всегда
явно, а обрезка видна в мета-строке.

Данные: Coarena сохраняет промпты, ответы и рассуждения и может отдавать их в
датасетах — секреты и персональные данные туда не отправлять.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# Настройки, которые правят руками
# ---------------------------------------------------------------------------
COARENA_KEY = ""  # или переменная окружения COARENA_API_KEY
ONEAI_KEY = ""  # или переменная окружения ONEAI_API_KEY

COARENA_MODEL = "claude-fable-5-2"  # id из --models, вписывается как есть
ONEAI_MODEL = "claude-opus-5-5"

# Лимит ответа в токенах, включая рассуждение. Потолок задаёт модель (см. --models:
# «вывод до N», у Coarena это 16384) — выше значения модель не примет, и шлюз
# вернёт 400. Поэтому значение подрезается по известному потолку с предупреждением.
MAX_TOKENS = 16384
REASONING_EFFORT = "high"  # off | low | medium | high | max
CACHE_MARK = "auto"  # кэш промпта: "auto" (5 мин) | "1h" | "off"
# Кэш у Anthropic-моделей копит до 4 контрольных точек на запрос. Ставим их на:
# system-промпт, на самый длинный вопрос истории (обычно вставленный файл) и на
# последний ход. Первые байты запроса неизменны — значит префикс кэшируется, и
# следующий ход платит за новую часть, а не за весь промпт.
CACHE_TOKENS = 1024  # минимум Anthropic: блок короче не кэшируется
SAVE_PATH = "chat.md"  # куда писать диалог при --save
SAVE_EVERY_TURN = True  # переписывать файл после каждого ответа

TOKENS_CEILING = 1_000_000  # выше — почти наверняка опечатка
EFFORTS = ("off", "low", "medium", "high", "max")


class Platform(TypedDict):
    """Адреса и подписи одного шлюза."""

    label: str
    base: str
    models_url: str
    env: str
    prefix: str


PLATFORMS: dict[str, Platform] = {
    "coarena": {
        "label": "Coarena",
        "base": "https://coarena.ai/api/v1",
        "models_url": "https://coarena.ai/api/v1/models",
        "env": "COARENA_API_KEY",
        "prefix": "coa_",
    },
    "oneai": {
        "label": "One AI API Key",
        "base": "https://api.oneaiapikey.com/v1",
        "models_url": "https://api.oneaiapikey.com/v1/models",
        "env": "ONEAI_API_KEY",
        "prefix": "sk-",
    },
}


# ---------------------------------------------------------------------------
# Консоль: цвет, ширина, перенос строк
# ---------------------------------------------------------------------------
_COLOR = True
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _c(code: str, text: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if _COLOR else text


def bold(text: str) -> str:
    return _c("1", text)


def dim(text: str) -> str:
    return _c("2", text)


def cyan(text: str) -> str:
    return _c("36", text)


def red(text: str) -> str:
    return _c("31", text)


def green(text: str) -> str:
    return _c("32", text)


def yellow(text: str) -> str:
    return _c("33", text)


def visible(text: str) -> int:
    """Длина строки без ANSI-последовательностей — по ней считаем перенос."""
    return len(_ANSI.sub("", text))


def width() -> int:
    """Ширина вывода: терминал, но не шире 120 и не уже 60 колонок."""
    try:
        columns = os.get_terminal_size(sys.stdout.fileno()).columns
    except OSError:
        columns = 100
    return max(60, min(columns - 2, 120))


def wrap(text: str, limit: int | None = None, indent: str = "", hanging: str = "") -> list[str]:
    """Перенести по словам, не ломая цвет: ширина считается по видимым символам."""
    limit = limit or width()
    lines: list[str] = []
    current = indent
    for word in text.split():
        candidate = f"{current}{word} "
        if visible(candidate) > limit and current.strip():
            lines.append(current.rstrip())
            current = f"{hanging or indent}{word} "
        else:
            current = candidate
    if current.strip():
        lines.append(current.rstrip())
    return lines or [indent]


def rule(title: str = "", limit: int | None = None) -> str:
    """Разделитель с заголовком внутри: ``── заголовок ──────``."""
    limit = limit or width()
    if not title:
        return "─" * limit
    head = f"── {title} "
    return head + "─" * max(0, limit - visible(head))


# ---------------------------------------------------------------------------
# Разметка ответа под терминал
# ---------------------------------------------------------------------------
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_NUMBERED = re.compile(r"^(\s*)(\d{1,2}[.)])\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")
_FENCE = re.compile(r"^\s*```")


def _inline(text: str) -> str:
    """Жирный, код, курсив, ссылки — в ANSI; таблицы уже прочитаны как текст."""
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: bold(m.group(1)), text)
    text = re.sub(r"(?<!\w)`([^`]+)`(?!\w)", lambda m: cyan(m.group(1)), text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", lambda m: _c("3", m.group(1)), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f"{m.group(1)} ({dim(m.group(2))})", text)
    return text


def cell_header(cells: Sequence[Sequence[str]]) -> list[str]:
    """Первая строка таблицы — шапка; в карточках она превращается в подписи."""
    return [str(cell).strip() for cell in cells[0]] if cells else []


def _table_cells(rows: Sequence[str]) -> list[list[str]]:
    """Разобрать строки markdown-таблицы в ячейки; строка-разделитель отбрасывается."""
    cells: list[list[str]] = []
    for row in rows:
        if _TABLE_SEP.match(row):
            continue
        cells.append([_inline(part.strip()) for part in row.strip().strip("|").split("|")])
    return cells


def _table_rows(cells: Sequence[Sequence[str]], limit: int) -> list[str]:
    """Таблица «как есть»: ячейки выровнены по колонкам, длинное — переносится.

    Годится для узких таблиц: если хоть одна колонка уже своего содержимого,
    перенос внутри ячейки читается хуже, чем карточки, поэтому выбор делает
    :func:`_table_block`.
    """
    columns = max(len(row) for row in cells)
    natural = [max(visible(row[i]) if i < len(row) else 0 for row in cells) for i in range(columns)]
    joiners = 3 * (columns - 1)
    available = limit - joiners
    if sum(natural) <= available:
        widths = natural
    else:
        share = available // columns
        widths = [min(width, share) for width in natural]
        while sum(widths) < available:  # отдать остаток самой длинной колонке
            index = max(range(columns), key=lambda i: natural[i] - widths[i])
            if widths[index] >= natural[index]:
                break
            widths[index] += 1
    lines: list[str] = []
    for number, row in enumerate(cells):
        wrapped = [wrap(row[i] if i < len(row) else "", widths[i]) or [""] for i in range(columns)]
        height = max(len(part) for part in wrapped)
        for line_number in range(height):
            pieces = [
                (part[line_number] if line_number < len(part) else "").ljust(widths[i])
                for i, part in enumerate(wrapped)
            ]
            lines.append(" · ".join(pieces).rstrip())
        if number == 0:
            lines.append(dim("·" * min(limit, len(lines[-1]) or limit)))
    return lines


def _card_label(header: Sequence[str], index: int, cap: int) -> str:
    """Подпись поля из шапки таблицы: без лишней длины, иначе ломается отступ."""
    label = str(header[index]).strip() if index < len(header) else ""
    if len(label) > cap:
        label = label[: cap - 1] + "…"
    return label


def _table_cards(cells: Sequence[Sequence[str]], limit: int) -> list[str]:
    """Широкая таблица — карточка на строку: заголовок, поля сеткой, разделитель.

    Подписи выравниваются в колонку, значения начинаются на одном отступе от
    края карточки — так поля читаются как список, а не как абзац с вставками.
    """
    header = cell_header(cells)
    rows = list(cells[1:])
    if not rows:
        return []
    natural = [str(header[index]).strip() if index < len(header) else "" for index in range(1, len(rows[0]))]
    longest = min(28, max((len(label) for label in natural), default=0))
    # «: » после подписи — часть отступа, иначе самая длинная ляжет вплотную к значению
    pad = longest + 2 if longest else 0
    labels = [_card_label(header, index, longest) for index in range(1, max(len(row) for row in rows))]
    lines: list[str] = []
    for number, row in enumerate(rows, start=1):
        title = next((cell for cell in row if cell.strip()), f"строка {number}")
        lines.append("")
        lines.extend(wrap(bold(f"{number}. {title}"), limit - 2, "┃ ", "┃   "))
        for index in range(1, len(row)):
            value = row[index]
            if not value.strip():
                continue
            label = labels[index - 1] if index - 1 < len(labels) else ""
            head = f"┃ {label.ljust(pad)}: " if label else "┃ "
            lines.extend(wrap(value, limit, head, " " * len(head)))
        if number < len(rows):
            lines.append(dim("┸" + "─" * min(limit - 2, 46)))
    return lines


def _table_block(rows: Sequence[str], limit: int) -> list[str]:
    """Таблица: узкую печатаем колонками, широкую — карточками.

    Считать «сколько влезет» по числу колонок бесполезно: четыре колонки в
    ширину терминала дают по ~27 символов и рвут слова. Поэтому пробуем
    колонки, а если самой узкой колонке остаётся меньше трети её содержимого —
    переключаемся на карточки, где текст идёт во всю ширину.
    """
    cells = _table_cells(rows)
    if not cells:
        return []
    columns = len(cells[0])
    natural = [max(visible(row[i]) if i < len(row) else 0 for row in cells) for i in range(columns)]
    share = (limit - 3 * (columns - 1)) // max(1, columns)
    cramped = any(size > share * 1.5 for size in natural[1:]) or share < 18
    if columns <= 1 or not cramped:
        return _table_rows(cells, limit)
    return _table_cards(cells, limit)


class _Renderer:
    """Разобрать markdown построчно и собрать строки под ширину терминала.

    Состояние (абзац, таблица, цитата, блок кода) копится между строками, поэтому
    обход идёт в одном месте, а вспомогательные методы только сбрасывают буферы.
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.lines: list[str] = []
        self.paragraph: list[str] = []
        self.table: list[str] = []
        self.quote: list[str] = []
        self.in_code = False

    def flush(self) -> None:
        """Вытолкнуть накопленный абзац, таблицу и цитату в вывод."""
        if self.paragraph:
            self.lines.extend(wrap(_inline(" ".join(self.paragraph)), self.limit))
            self.paragraph.clear()
        if self.table:
            self.lines.extend(_table_block(self.table, self.limit))
            self.table.clear()
        if self.quote:
            if self.lines and self.lines[-1]:
                self.lines.append("")
            for chunk in self.quote:
                self.lines.extend(dim(part) for part in wrap(_inline(chunk), self.limit - 2, "│ "))
            self.lines.append("")
            self.quote.clear()

    def fence(self) -> None:
        """Открыть или закрыть блок кода."""
        self.flush()
        if self.in_code:
            self.lines.extend([dim("  └" + "─" * 8), ""])
        else:
            self.lines.append(dim("  ┌─ код " + "─" * max(0, self.limit - 10)))
        self.in_code = not self.in_code

    def line(self, line: str) -> None:
        """Одна строка markdown: код, заголовок, список, цитата или текст абзаца."""
        if _FENCE.match(line):
            self.fence()
            return
        if self.in_code:
            self.lines.append(dim("  │ ") + line)
            return
        if not line.strip():
            self.flush()
            return
        if line.lstrip().startswith("|"):
            if self.paragraph or self.quote:
                self.flush()
            self.table.append(line)
            return
        if self.table:
            self.flush()
        heading = _HEADING.match(line)
        if heading:
            self.flush()
            if self.lines and self.lines[-1]:
                self.lines.append("")
            self.lines.extend([bold(_inline(heading.group(2).strip())), ""])
            return
        bullet = _BULLET.match(line)
        if bullet:
            self.flush()
            indent = " " * len(bullet.group(1))
            self.lines.extend(wrap(_inline(bullet.group(2)), self.limit, f"{indent}  • ", f"{indent}    "))
            return
        numbered = _NUMBERED.match(line)
        if numbered:
            self.flush()
            indent = " " * len(numbered.group(1))
            head = f"{indent}  {numbered.group(2)} "
            self.lines.extend(wrap(_inline(numbered.group(3)), self.limit, head, " " * visible(head)))
            return
        if line.lstrip().startswith(">"):
            if self.paragraph:
                self.flush()
            self.quote.append(line.lstrip()[1:].strip())
            return
        self.paragraph.append(line.strip())


def render(text: str, limit: int | None = None) -> list[str]:
    """Разметку — в читаемый текст: заголовки, списки, код, таблицы, абзацы."""
    renderer = _Renderer(limit or width())
    for line in text.replace("\r\n", "\n").split("\n"):
        renderer.line(line.rstrip())
    renderer.flush()
    if renderer.in_code:
        renderer.lines.append(dim("  └" + "─" * 8))
    return renderer.lines


# ---------------------------------------------------------------------------
# Ошибки шлюза
# ---------------------------------------------------------------------------
class BenchError(Exception):
    """Ошибка настройки или локального состояния (код возврата 2)."""


class ApiError(Exception):
    """Ответ шлюза с ошибкой (код возврата 1)."""

    def __init__(self, status: int, code: str, message: str, request_id: str = "", retry_after: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id
        self.retry_after = retry_after


KNOWN_CODES: dict[str, str] = {
    "invalid_api_key": "ключ неверный или отозван",
    "api_key_revoked": "ключ отозван",
    "conflicting_credentials": "отправлены оба способа авторизации — оставьте один",
    "insufficient_scope": "у ключа нет права inference:write",
    "account_blocked": "аккаунт заблокирован",
    "model_api_terms_required": "на сайте Coarena не приняты условия использования API",
    "model_not_found": "такой модели нет — сверьтесь с --models",
    "model_api_off": "доступ к модели выключен для аккаунта",
    "context_length_exceeded": "история длиннее контекста — /reset или короче вопрос",
    "rate_limit_exceeded": "лимит запросов в минуту",
    "concurrency_limit_exceeded": "лимит одновременных запросов (2)",
    "insufficient_quota": "закончилась квота",
    "invalid_request": "шлюз не принял тело запроса",
    "unsupported_parameter": "параметр не поддерживается этой моделью",
    "upstream_error": "ошибка на стороне модели",
    "overloaded_error": "модель перегружена",
}


def describe_error(exc: ApiError) -> str:
    """Одна строка про ошибку плюс подсказка, что делать."""
    hint = KNOWN_CODES.get(exc.code, "")
    tail = f" · {hint}" if hint else ""
    if exc.retry_after:
        tail += f" · повторить через {exc.retry_after} с"
    if exc.request_id:
        tail += f" · id {exc.request_id}"
    return red(f"✗ {exc.status} {exc.code}: {exc.message}{tail}")


# ---------------------------------------------------------------------------
# HTTP и SSE
# ---------------------------------------------------------------------------
USER_AGENT = "api-key-probe/2.0"
TIMEOUT = 600.0


def _request_id(headers: Mapping[str, str]) -> str:
    """id запроса из заголовков; регистр имени у шлюзов разный."""
    lowered = {str(name).lower(): str(value) for name, value in headers.items()}
    for name in ("x-coarena-request-id", "x-request-id", "request-id"):
        value = lowered.get(name)
        if value:
            return value
    return ""


def _http_error(exc: urllib.error.HTTPError) -> ApiError:
    """Разобрать тело ошибки в ApiError, что бы ни прислал шлюз."""
    raw = ""
    try:
        raw = exc.read().decode("utf-8", "replace")
    except OSError:
        raw = ""
    code, message = "", raw.strip()[:300]
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, Mapping):
        error = payload.get("error", payload)
        if isinstance(error, Mapping):
            code = str(error.get("code") or error.get("type") or "")
            message = str(error.get("message") or message)
        elif isinstance(error, str):
            message = error
    headers: Mapping[str, str] = {str(name).lower(): str(value) for name, value in (exc.headers or {}).items()}
    retry = str(headers.get("retry-after") or "")
    return ApiError(exc.code, code or f"http_{exc.code}", message or "пустой ответ", _request_id(headers), retry)


def _open(request: urllib.request.Request) -> Any:
    try:
        return urllib.request.urlopen(request, timeout=TIMEOUT)  # noqa: S310  # адрес — константа файла
    except urllib.error.HTTPError as exc:
        raise _http_error(exc) from exc
    except urllib.error.URLError as exc:
        raise BenchError(f"сеть недоступна: {exc.reason}") from exc


def get_json(url: str, headers: Mapping[str, str]) -> Any:
    """GET и JSON: адрес всегда из PLATFORMS, не из аргументов командной строки."""
    with _open(urllib.request.Request(url, headers=dict(headers))) as response:  # noqa: S310  # адрес — константа
        return json.loads(response.read().decode("utf-8", "replace"))


def iter_sse(response: Any) -> Iterator[Mapping[str, Any]]:
    """Прочитать поток SSE и отдавать разобранные события."""
    for raw in response:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            if payload == "[DONE]":
                return
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(event, Mapping):
            yield event


# ---------------------------------------------------------------------------
# Ответ модели
# ---------------------------------------------------------------------------
class Reply:
    """Собранный ответ: текст, рассуждение, служебные поля."""

    def __init__(self) -> None:
        self.text = ""
        self.reasoning = ""
        self.model = ""
        self.request_id = ""
        self.stop_reason = ""
        self.in_tokens = 0
        self.out_tokens = 0
        self.reasoning_tokens = 0
        self.cached_tokens = 0  # вход, взятый из кэша промпта
        self.cache_write_tokens = 0  # сколько записано в кэш этим запросом
        self.first_token = 0.0  # секунды от старта запроса до первого куска текста или мысли

    @property
    def truncated(self) -> bool:
        return self.stop_reason == "length"


def _text_of(value: Any) -> str:
    """Текст из строки или списка блоков Anthropic-подобного вида."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for block in value:
            if isinstance(block, Mapping) and block.get("type") in (None, "text"):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return ""


def _int_of(value: Any) -> int:
    return value if isinstance(value, int) else 0


def apply_usage(reply: Reply, usage: Any) -> None:
    """Токены из финального чанка: prompt/completion и доля рассуждения."""
    if not isinstance(usage, Mapping):
        return
    reply.in_tokens = _int_of(usage.get("prompt_tokens"))
    reply.out_tokens = _int_of(usage.get("completion_tokens"))
    details = usage.get("completion_tokens_details")
    if isinstance(details, Mapping):
        reply.reasoning_tokens = _int_of(details.get("reasoning_tokens"))
    prompt_details = usage.get("prompt_tokens_details")
    if isinstance(prompt_details, Mapping):
        reply.cached_tokens = _int_of(prompt_details.get("cached_tokens"))
        reply.cache_write_tokens = _int_of(prompt_details.get("cache_write_tokens"))


def apply_chunk(reply: Reply, chunk: Mapping[str, Any]) -> None:
    """Один SSE-чанк: дельты текста и рассуждения, финальные поля."""
    if not reply.model:
        reply.model = str(chunk.get("model") or "")
    apply_usage(reply, chunk.get("usage"))
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return
    choice = choices[0]
    if not isinstance(choice, Mapping):
        return
    if choice.get("finish_reason"):
        reply.stop_reason = str(choice["finish_reason"])
    delta = choice.get("delta")
    if not isinstance(delta, Mapping):
        return
    thought = delta.get("reasoning_content") or delta.get("reasoning")
    if isinstance(thought, str) and thought:
        reply.reasoning += thought
        reply.first_token = reply.first_token or time.monotonic()
    piece = delta.get("content")
    if isinstance(piece, str) and piece:
        reply.text += piece
        reply.first_token = reply.first_token or time.monotonic()


# ---------------------------------------------------------------------------
# Настройки и ключи
# ---------------------------------------------------------------------------
class Settings:
    """Всё, что меняется в рантайме командами чата."""

    def __init__(
        self,
        platform: str,
        key: str,
        model: str,
        effort: str,
        max_tokens: int,
        system: str = "",
        save: str = "",
    ) -> None:
        self.platform = platform
        self.key = key
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.system = system
        self.save = save


def mask(key: str) -> str:
    """Ключ в виде ``coa_24…6ca4`` — достаточно, чтобы узнать свой."""
    return f"{key[:6]}…{key[-4:]}" if len(key) > 12 else "…"


def key_from(platform: str) -> str:
    """Ключ из файла или окружения; пустая строка — не задан."""
    local = COARENA_KEY if platform == "coarena" else ONEAI_KEY
    return (local or os.environ.get(PLATFORMS[platform]["env"], "")).strip()


def model_for(platform: str) -> str:
    return COARENA_MODEL if platform == "coarena" else ONEAI_MODEL


# ---------------------------------------------------------------------------
# Клиент
# ---------------------------------------------------------------------------
class ChatClient:
    """Чат с одним шлюзом: история шлётся заново каждый ход."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        spec = PLATFORMS[settings.platform]
        self.label = spec["label"]
        self.url = spec["base"] + "/chat/completions"
        self.models_url = spec["models_url"]
        self.turns: list[tuple[str, Reply | None, str]] = []  # вопрос, ответ, время
        self.model_ceiling = 0  # «вывод до N» из --models: выше модель не отдаст
        self.cached_prev = 0  # сколько входных токенов прошлого запроса взято из кэша

    # -- запрос ----------------------------------------------------------
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": USER_AGENT,
        }

    def apply_ceiling(self, limit: int) -> int:
        """Подрезать лимит по потолку модели и сказать об этом один раз.

        Шлюз вернёт 400 на max_completion_tokens выше потолка, поэтому лучше
        отправить допустимый максимум и объяснить, почему цифра меньше.
        """
        if self.model_ceiling and limit > self.model_ceiling:
            return self.model_ceiling
        return limit

    def learn_ceiling(self) -> None:
        """Узнать потолок вывода из списка моделей; молча — если список недоступен."""
        try:
            models = self.fetch_models()
        except (ApiError, BenchError):
            return
        for model in models:
            if str(model.get("id")) != self.settings.model:
                continue
            limit = model.get("max_tokens")
            if isinstance(limit, int) and limit > 0:
                self.model_ceiling = limit
                requested = self.settings.max_tokens
                self.settings.max_tokens = self.apply_ceiling(requested)
                if self.settings.max_tokens != requested:
                    print(
                        yellow(
                            f"  потолок {self.settings.model} — {limit} выходных токенов; "
                            f"лимит {requested} подрезан до {limit}"
                        )
                    )
            return

    @staticmethod
    def _block(text: str, marked: bool) -> Any:
        """Содержимое сообщения: строка либо блок с cache_control."""
        if not marked:
            return text
        return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral", "ttl": CACHE_MARK}}]

    def cache_marks(self, history: Sequence[Mapping[str, str]]) -> set[int]:
        """Индексы сообщений, где ставим контрольную точку кэша.

        Anthropic кэширует префикс до отмеченного блока включительно. Поэтому
        метки идут по возрастанию и не чаще четырёх: system + самый длинный
        вопрос (вставленный файл) + последний ход.
        """
        if CACHE_MARK == "off" or not history:
            return set()
        # Последний ход отмечаем всегда: именно он станет общим префиксом для
        # следующего запроса. Длинный вопрос (вставленный файл) отмечаем отдельно,
        # чтобы он кэшировался, даже когда разговор ушёл дальше.
        marks = {len(history) - 1}
        longest = max(range(len(history)), key=lambda i: len(str(history[i]["content"])))
        if longest != len(history) - 1 and len(str(history[longest]["content"])) >= CACHE_TOKENS * 2:
            marks.add(longest)
        return marks

    def build_body(self, history: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        """Тело запроса: лимит, усилие и контрольные точки кэша промпта."""
        rows: list[dict[str, Any]] = []
        if self.settings.system:
            system = self.settings.system
            rows.append({"role": "system", "content": self._block(system, CACHE_MARK != "off")})
        marks = self.cache_marks(history)
        for index, row in enumerate(history):
            text = str(row["content"])
            rows.append({"role": str(row["role"]), "content": self._block(text, index in marks)})
        body: dict[str, Any] = {
            "model": self.settings.model,
            "messages": rows,
            "stream": True,
            "stream_options": {"include_usage": True},
            "max_completion_tokens": self.apply_ceiling(self.settings.max_tokens),
        }
        if self.settings.effort != "off":
            body["reasoning_effort"] = self.settings.effort
        return body

    def _progress(self, reply: Reply, started: float) -> None:
        """Живой счётчик под строкой ввода: видно, что запрос идёт, а не висит."""
        if not sys.stdout.isatty():
            return
        now = time.monotonic()
        if now - getattr(self, "_tick_at", 0.0) < 0.25:
            return
        self._tick_at = now
        parts = [
            f"{len(reply.reasoning)} симв. рассуждения" if reply.reasoning else "",
            f"{len(reply.text)} симв. ответа",
        ]
        body = " · ".join(part for part in parts if part) or "ждём первый токен"
        sys.stdout.write("\r\x1b[2K" + dim(f"  {body} · {now - started:.1f} с"))
        sys.stdout.flush()

    def _clear(self) -> None:
        if sys.stdout.isatty():
            sys.stdout.write("\r\x1b[2K")
            sys.stdout.flush()

    def send(self, history: Sequence[Mapping[str, str]]) -> tuple[Reply, float]:
        """Стрим-запрос: текст печатается по мере прихода."""
        body = self.build_body(history)
        data = json.dumps(body, ensure_ascii=False).encode()
        request = urllib.request.Request(self.url, data=data, headers=self.headers(), method="POST")  # noqa: S310
        reply = Reply()
        started = time.monotonic()
        first = 0.0
        try:
            with _open(request) as response:
                reply.request_id = _request_id(dict(response.headers))
                for chunk in iter_sse(response):
                    before = len(reply.text) + len(reply.reasoning)
                    apply_chunk(reply, chunk)
                    if not first and len(reply.text) + len(reply.reasoning) > before:
                        first = time.monotonic() - started
                    self._progress(reply, started)
        except KeyboardInterrupt:
            self._clear()
            raise
        finally:
            self._clear()
        reply.first_token = first
        elapsed = time.monotonic() - started
        if not reply.text and not reply.reasoning:
            raise BenchError("шлюз вернул пустой ответ")
        self.cached_prev += reply.cached_tokens
        return reply, elapsed

    # -- текст и мета ----------------------------------------------------
    def meta(self, reply: Reply, elapsed: float) -> str:
        """Служебная строка под ответом: что пришло, за сколько, чем кончилось."""
        parts = [reply.model or self.settings.model]
        if reply.truncated:
            parts.append(yellow("ОБРЕЗАНО по лимиту (finish_reason=length)"))
        parts.append(f"токены {reply.in_tokens}→{reply.out_tokens}")
        if reply.cached_tokens:
            share = 100 * reply.cached_tokens // max(1, reply.in_tokens)
            parts.append(green(f"из входа {reply.cached_tokens} из кэша ({share}%)"))
        elif CACHE_MARK != "off":
            parts.append("кэш не сработал")
        if reply.reasoning_tokens:
            parts.append(f"из них рассуждение {reply.reasoning_tokens}")
        if reply.first_token:
            parts.append(f"первый токен {reply.first_token:.1f} с")
        parts.append(f"итого {elapsed:.1f} с")
        if reply.request_id:
            parts.append("id " + reply.request_id)
        return "  " + dim(" · ".join(parts))

    def turn_lines(self, reply: Reply | None, question: str, elapsed: str, *, reasoning: bool = False) -> list[str]:
        """Блок ответа: заголовок, вопрос, рассуждение, текст, мета."""
        limit = width()
        number = len(self.turns)
        lines = ["", bold(rule(f"ответ {number} · {self.settings.model}"))]
        lines.append(dim(" ".join(question.split())[: limit * 2]))
        if reply is None:
            return lines
        if reasoning and reply.reasoning.strip():
            lines.append("")
            lines.extend(dim("── рассуждение " + "─" * max(0, limit - 16)))
            lines.extend(dim(line) for line in render(reply.reasoning, limit))
        lines.append("")
        lines.extend(render(reply.text, limit) or [yellow("(модель вернула пустой текст)")])
        if reply.truncated:
            lines.append("")
            lines.extend(
                yellow(line)
                for line in wrap(
                    "ответ оборван лимитом: рассуждение съело почти весь max_tokens. "
                    "Продолжить — /continue, поднять лимит — /tokens 64000, понизить усилие — /effort medium",
                    limit,
                    "  ",
                    "  ",
                )
            )
        lines.append("")
        lines.append(self.meta(reply, _seconds(elapsed)))
        return lines

    # -- модели и проверка ----------------------------------------------
    def fetch_models(self) -> list[Mapping[str, Any]]:
        payload = get_json(self.models_url, {"Authorization": f"Bearer {self.settings.key}", "User-Agent": USER_AGENT})
        data = payload.get("data") if isinstance(payload, Mapping) else payload
        return [item for item in data or [] if isinstance(item, Mapping)]

    def print_models(self, pattern: str = "") -> int:
        """Список моделей шлюза: id, потолок вывода, поддерживаемые усилия."""
        try:
            models = self.fetch_models()
        except ApiError as exc:
            print(describe_error(exc), file=sys.stderr)
            return 1
        except BenchError as exc:
            print(red(f"ошибка: {exc}"), file=sys.stderr)
            return 2
        if pattern:
            needle = pattern.lower()
            models = [model for model in models if needle in str(model.get("id", "")).lower()]
        if not models:
            print(yellow("ничего не нашлось" if pattern else "шлюз вернул пустой список"))
            return 1
        print(bold(f"{self.label}: моделей {len(models)}" + (f" по «{pattern}»" if pattern else "")))
        for model in models:
            mid = str(model.get("id") or "")
            mark = "*" if mid == self.settings.model else " "
            extra = []
            limit = model.get("max_tokens")
            if isinstance(limit, int) and limit:
                extra.append(f"вывод до {limit}")
            capabilities = model.get("capabilities")
            if isinstance(capabilities, Mapping):
                efforts = capabilities.get("efforts")
                if isinstance(efforts, list) and efforts:
                    extra.append("усилия " + "/".join(str(e) for e in efforts))
            suffix = dim("   " + " · ".join(extra)) if extra else ""
            print(f" {mark} {mid}{suffix}")
        print(dim(f"«*» — выбрана сейчас; сменить: -m <id> или /model <id> (сейчас {self.settings.model})"))
        print(dim("«вывод до N» — максимум выходных токенов модели (текст + рассуждение), выше не отдаст"))
        return 0

    def check(self) -> int:
        """Проверка ключа: список моделей, наличие выбранной модели, минимальный запрос."""
        print(rule("проверка ключа"))
        print(f"  шлюз:    {self.label} ({self.settings.platform})")
        print(f"  адрес:   {self.url}")
        print(f"  модель:  {self.settings.model}   усилие: {self.settings.effort}   лимит: {self.settings.max_tokens}")
        print(f"  ключ:    {mask(self.settings.key)} ({len(self.settings.key)} симв.)")
        print()
        print("1) список моделей")
        try:
            models = self.fetch_models()
        except ApiError as exc:
            print("   " + describe_error(exc))
            return 1
        except BenchError as exc:
            print("   " + red(f"✗ {exc}"))
            return 2
        ids = [str(model.get("id")) for model in models]
        print(f"   ✓ моделей {len(ids)}")
        if self.settings.model in ids:
            print(f"   ✓ {self.settings.model} в списке")
        else:
            print("   " + yellow(f"! {self.settings.model} в списке нет — сверьтесь с --models"))
        print()
        print("2) минимальный запрос к модели")
        started = time.monotonic()
        try:
            reply, _elapsed = self.send([{"role": "user", "content": "Ответь одним словом: ок"}])
        except ApiError as exc:
            print("   " + describe_error(exc))
            return 1
        except BenchError as exc:
            print("   " + red(f"✗ {exc}"))
            return 2
        text = " ".join(reply.text.split())[:60]
        print(f"   ✓ ответ за {time.monotonic() - started:.1f} с: {green(text)}")
        print("   " + self.meta(reply, time.monotonic() - started).strip())
        print()
        print(green("итог: ключ работает"))
        return 0

    # -- сохранение ------------------------------------------------------
    def save(self) -> Path | None:
        """Записать диалог в markdown: вопрос, ответ, рассуждение, служебная строка."""
        if not self.settings.save or not self.turns:
            return None
        chunks = [f"# Диалог · {self.label} · {self.settings.model}", ""]
        for number, (question, reply, elapsed) in enumerate(self.turns, start=1):
            chunks.extend([f"## {number}. Вопрос", "", question.strip(), ""])
            if reply is None:
                chunks.extend(["_ответа нет_", ""])
                continue
            chunks.extend(["### Ответ", "", reply.text.strip(), ""])
            if reply.reasoning.strip():
                chunks.extend(
                    ["<details><summary>рассуждение</summary>", "", reply.reasoning.strip(), "", "</details>", ""]
                )
            chunks.extend([f"_{self.meta(reply, _seconds(elapsed)).strip()}_", ""])
        path = Path(self.settings.save)
        path.write_text("\n".join(chunks).strip() + "\n", encoding="utf-8")
        return path

    # -- чат -------------------------------------------------------------
    def ask_once(self, prompt: str) -> int:
        """Один вопрос без истории и без чата."""
        self.header_line()
        reply = self.turn(prompt, [{"role": "user", "content": prompt}])
        if reply is None:
            return 1
        return 0

    def turn(self, question: str, history: list[dict[str, str]]) -> Reply | None:
        """Один ход: запрос, печать ответа, запись в журнал и в файл."""
        started = time.monotonic()
        try:
            reply, _elapsed = self.send(history)
        except ApiError as exc:
            print(describe_error(exc), file=sys.stderr)
            self.turns.append((question, None, "0.0"))
            return None
        except BenchError as exc:
            print(red(f"✗ {exc}"), file=sys.stderr)
            self.turns.append((question, None, "0.0"))
            return None
        except KeyboardInterrupt:
            print(dim("\n  прервано; в журнал не попало"))
            return None
        elapsed = f"{time.monotonic() - started:.1f}"
        self.turns.append((question, reply, elapsed))
        print("\n".join(self.turn_lines(reply, question, elapsed)))
        saved = self.save() if (self.settings.save and SAVE_EVERY_TURN) else None
        if saved:
            print(dim(f"  сохранено: {saved}"))
        return reply

    def repl(self) -> int:
        """Чат: каждый ход несёт всю историю, поэтому модель помнит разговор."""
        history: list[dict[str, str]] = []
        limit = width()
        if not self.model_ceiling:
            self.learn_ceiling()
        print(rule(f"{self.label} · чат"))
        self.header_line()
        for line in wrap(
            "/help — команды · @файл — промпт из файла · /q — перечитать · /exit — выход", limit, "  ", "  "
        ):
            print(dim(line))
        if self.settings.save:
            print(dim(f"  диалог пишется в {self.settings.save}"))
        while True:
            try:
                text = input(cyan("\nвы> ")).strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print(dim("\nвыход"))
                break
            if not text:
                continue
            if text.startswith("/"):
                if self.command(text, history):
                    break
                continue
            if text.startswith("@"):
                path = text[1:].strip().strip("\"'")
                try:
                    text = Path(path).read_text(encoding="utf-8").strip()
                except OSError as exc:
                    print(red(f"  не прочитать {path}: {exc}"))
                    continue
                if not text:
                    print(yellow(f"  {path} пустой"))
                    continue
                print(dim(f"  промпт из {path}: {len(text)} символов"))
            if not text:
                continue
            history.append({"role": "user", "content": text})
            reply = self.turn(text, history)
            if reply is None:
                history.pop()
                continue
            history.append({"role": "assistant", "content": reply.text or "(пустой ответ)"})
        self.finish(history)
        return 0

    def finish(self, history: Sequence[Mapping[str, str]]) -> None:
        """Итог сессии: сколько ходов, где файл, как продолжить."""
        if not self.turns:
            return
        print(dim(f"\nходов за сессию: {len(self.turns)} · символов в истории: {_chars(history)}"))
        if self.cached_prev:
            print(dim(f"из кэша промпта взято {self.cached_prev} входных токенов"))
        saved = self.save()
        if saved:
            print(dim(f"диалог: {saved}"))
        elif self.turns:
            print(dim(f"чтобы сохранить диалог: --save {SAVE_PATH} (или /save {SAVE_PATH})"))

    def command(self, text: str, history: list[dict[str, str]]) -> bool:
        """Разобрать команду чата; True — выйти из чата."""
        name, _, argument = text.partition(" ")
        argument = argument.strip()
        settings = self.settings
        if name in ("/exit", "/quit", "/q!"):
            return True
        if name == "/help":
            self.help()
        elif name == "/models":
            self.print_models(argument)
        elif name == "/model" and argument:
            settings.model = argument
            self.model_ceiling = 0
            self.learn_ceiling()
            ceiling = f", потолок вывода {self.model_ceiling}" if self.model_ceiling else ""
            print(dim(f"  модель: {settings.model} (история сохранена){ceiling}"))
        elif name == "/effort" and argument in EFFORTS:
            settings.effort = argument
            print(dim(f"  усилие: {settings.effort} (уйдёт в следующем запросе)"))
        elif name == "/tokens" and argument.isdigit():
            value = int(argument)
            if value < 256:
                print(yellow("  меньше 256 токенов: ответ обрежется на полуслове"))
            elif value > TOKENS_CEILING:
                print(yellow("  больше миллиона: похоже на опечатку"))
            else:
                settings.max_tokens = value
                note = (
                    f"; потолок модели {self.model_ceiling}"
                    if self.model_ceiling and value > self.model_ceiling
                    else ""
                )
                print(dim(f"  лимит ответа: {settings.max_tokens} токенов (включая рассуждение){note}"))
        elif name == "/q":
            self.reread(argument)
        elif name == "/continue":
            self.continue_turn(argument, history)
        elif name == "/save":
            settings.save = argument or settings.save or SAVE_PATH
            saved = self.save()
            print(dim(f"  сохранено: {saved}" if saved else "  сохранять пока нечего"))
        elif name == "/reset":
            history.clear()
            print(dim("  история очищена (журнал и файл остались)"))
        elif name == "/cache" and argument in ("auto", "1h", "off"):
            global CACHE_MARK
            CACHE_MARK = argument
            print(dim(f"  кэш промпта: {CACHE_MARK}" + (" (метки снимаются)" if argument == "off" else "")))
        elif name == "/status":
            self.status()
        else:
            print(yellow(f"  неизвестная команда {name!r}: /help"))
        return False

    def header_line(self) -> None:
        """Строка с текущими настройками — перед запросом и в начале чата."""
        settings = self.settings
        print(dim(f"{self.label} · {settings.model} · усилие {settings.effort} · лимит {settings.max_tokens} токенов"))

    def status(self) -> None:
        """Что сейчас в настройках: модель, усилие, лимит, файл."""
        settings = self.settings
        print(dim(f"  шлюз:   {self.label} ({settings.platform}), модель {settings.model}"))
        print(dim(f"  усилие: {settings.effort} · лимит ответа: {settings.max_tokens} токенов"))
        print(dim(f"  запись: {settings.save or 'выключена (--save файл.md)'}"))
        print(dim(f"  кэш:    {CACHE_MARK} · попаданий в кэш за сессию: {self.cached_prev} токенов"))
        print(dim(f"  ходов:  {len(self.turns)}"))

    def help(self) -> None:
        text = (
            "@файл — отправить текст файла как вопрос\n"
            "/models [фильтр] — модели шлюза\n"
            "/model <id> — сменить модель\n"
            "/effort <off|low|medium|high|max> — усилие рассуждения\n"
            "/tokens <N> — лимит ответа (включая рассуждение)\n"
            "/q [N] [расс] — перечитать ответ, с «расс» — вместе с рассуждением\n"
            "/continue [N] — дописать оборванный ответ\n"
            "/cache <auto|1h|off> — кэш промпта (Anthropic)\n"
            "/save [файл] — записать диалог в markdown\n"
            "/status — текущие настройки\n"
            "/reset — очистить историю\n"
            "/exit — выход"
        )
        for line in text.splitlines():
            print(dim("  " + line))

    def reread(self, argument: str) -> None:
        """Показать ответ заново: ``/q``, ``/q 2``, ``/q 2 расс``."""
        if not self.turns:
            print(yellow("  ответов пока нет"))
            return
        number = len(self.turns)
        reasoning = False
        for part in argument.split():
            if part.isdigit():
                number = max(1, min(int(part), len(self.turns)))
            elif part.startswith("расс"):
                reasoning = True
        question, reply, elapsed = self.turns[number - 1]
        print("\n".join(self.turn_lines(reply, question, elapsed, reasoning=reasoning)))

    def continue_turn(self, argument: str, history: list[dict[str, str]]) -> None:
        """Дописать оборванный ответ: история та же плюс просьба продолжить."""
        if not self.turns:
            print(yellow("  нечего продолжать"))
            return
        number = len(self.turns)
        for part in argument.split():
            if part.isdigit():
                number = max(1, min(int(part), len(self.turns)))
        question, reply, _elapsed = self.turns[number - 1]
        if reply is None or not reply.text.strip():
            print(yellow("  в этом ходе нет текста, продолжать нечего"))
            return
        if number != len(self.turns) or not history or history[-1]["role"] != "assistant":
            print(yellow("  продолжаю только последний ход: он есть в текущей истории"))
            return
        rows = [*history, {"role": "user", "content": CONTINUE_PROMPT}]
        before = len(reply.text)
        print(dim("  продолжаю с места обрыва (промпт уходит повторно)"))
        started = time.monotonic()
        try:
            fresh, _took = self.send(rows)
        except (ApiError, BenchError) as exc:
            print(red(f"  {exc}"))
            return
        joined = reply.text.rstrip("\n") + "\n\n" + fresh.text.lstrip("\n")
        reply.text = joined
        reply.stop_reason = fresh.stop_reason
        reply.out_tokens = fresh.out_tokens
        reply.reasoning_tokens = fresh.reasoning_tokens
        reply.first_token = fresh.first_token
        history[-1] = {"role": "assistant", "content": joined}
        total = _seconds(self.turns[number - 1][2]) + (time.monotonic() - started)
        self.turns[number - 1] = (question, reply, f"{total:.1f}")
        print("\n".join(render(fresh.text, width())))
        print(dim(f"  было {before} символов, стало {len(joined)}"))
        if self.settings.save:
            self.save()


CONTINUE_PROMPT = "Продолжи ровно с места обрыва: без вступления, без повторов и без пересказа задачи."


def _chars(history: Sequence[Mapping[str, str]]) -> int:
    return sum(len(str(row.get("content", ""))) for row in history)


def _seconds(value: str) -> float:
    try:
        return float(value)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="api_key_probe.py",
        description="Чат-стенд для Coarena (приоритет) и One AI API Key: диалог, модели, проверка ключа.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "ключи: COARENA_KEY / ONEAI_KEY в начале файла либо COARENA_API_KEY / ONEAI_API_KEY\n"
            "модель: COARENA_MODEL / ONEAI_MODEL в начале файла либо -m\n"
            f"по умолчанию: шлюз coarena · усилие {REASONING_EFFORT} · лимит {MAX_TOKENS} токенов"
        ),
    )
    parser.add_argument(
        "-p", "--platform", choices=sorted(PLATFORMS), default="coarena", help="шлюз (по умолчанию coarena)"
    )
    parser.add_argument("-m", "--model", default=None, help="id модели этого шлюза")
    parser.add_argument(
        "--effort",
        default=REASONING_EFFORT,
        choices=EFFORTS,
        help=f"усилие рассуждения (по умолчанию {REASONING_EFFORT})",
    )
    parser.add_argument(
        "--max-tokens",
        "--tokens",
        dest="max_tokens",
        type=int,
        default=MAX_TOKENS,
        metavar="N",
        help=f"лимит ответа вместе с рассуждением (по умолчанию {MAX_TOKENS})",
    )
    parser.add_argument(
        "--models", nargs="?", const="", default=None, metavar="ФИЛЬТР", help="показать модели шлюза и выйти"
    )
    parser.add_argument("--check", action="store_true", help="проверить ключ и модель минимальным запросом")
    parser.add_argument("--prompt", default=None, help="один вопрос и выход")
    parser.add_argument("--prompt-file", default=None, metavar="ФАЙЛ", help="как --prompt, но текст из файла")
    parser.add_argument(
        "--save",
        nargs="?",
        const=SAVE_PATH,
        default="",
        metavar="ФАЙЛ",
        help=f"писать диалог в markdown (по умолчанию {SAVE_PATH})",
    )
    parser.add_argument(
        "--cache",
        default=CACHE_MARK,
        choices=("auto", "1h", "off"),
        help=f"кэш промпта (Anthropic): auto — 5 мин, 1h — час, off — без меток (по умолчанию {CACHE_MARK})",
    )
    parser.add_argument("--system", default="", help="системный промпт")
    parser.add_argument("--no-color", action="store_true", help="без ANSI-цвета")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    global _COLOR, CACHE_MARK
    _COLOR = not args.no_color
    CACHE_MARK = str(args.cache)
    _utf8_stdio()
    if args.max_tokens < 256:
        return usage_error("--max-tokens меньше 256: ответ обрежется на полуслове")
    if args.max_tokens > TOKENS_CEILING:
        return usage_error(f"--max-tokens больше {TOKENS_CEILING}: похоже на опечатку")
    key = key_from(args.platform)
    if not key:
        variable = "COARENA_KEY" if args.platform == "coarena" else "ONEAI_KEY"
        return usage_error(
            f"нет ключа: заполните {variable} в начале файла или задайте {PLATFORMS[args.platform]['env']}"
        )
    if not key.startswith(PLATFORMS[args.platform]["prefix"]):
        print(
            yellow(f"! ключ не начинается на {PLATFORMS[args.platform]['prefix']} — для этого шлюза это подозрительно")
        )
    settings = Settings(
        platform=args.platform,
        key=key,
        model=str(args.model or model_for(args.platform)),
        effort=str(args.effort),
        max_tokens=int(args.max_tokens),
        system=str(args.system),
        save=str(args.save),
    )
    client = ChatClient(settings)
    client.learn_ceiling()
    if args.models is not None:
        return client.print_models(str(args.models))
    if args.check:
        return client.check()
    if args.prompt_file:
        try:
            prompt = Path(str(args.prompt_file)).read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(red(f"ошибка: не прочитать {args.prompt_file}: {exc}"), file=sys.stderr)
            return 2
        if not prompt:
            print(red(f"ошибка: {args.prompt_file} пустой"), file=sys.stderr)
            return 2
        return client.ask_once(prompt)
    if args.prompt is not None:
        prompt = str(args.prompt)
        if prompt.startswith("@"):
            try:
                prompt = Path(prompt[1:].strip().strip("\"'")).read_text(encoding="utf-8").strip()
            except OSError as exc:
                print(red(f"ошибка: не прочитать {prompt[1:]}: {exc}"), file=sys.stderr)
                return 2
        return client.ask_once(prompt)
    return client.repl()


def usage_error(message: str) -> int:
    """Ошибка настроек: печать в stderr и код 2, как у остальных локальных ошибок."""
    print(red(f"ошибка: {message}"), file=sys.stderr)
    return 2


def _utf8_stdio() -> None:
    """Windows-консоль по умолчанию не в UTF-8: без этого кириллица ломается."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        sys.exit(130)
    except BenchError as error:
        print(red(f"ошибка: {error}"), file=sys.stderr)
        sys.exit(2)
