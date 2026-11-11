#!/usr/bin/env python3
# ruff: noqa: RUF001, RUF002, RUF003, RUF100  # Русские строки и докстринги консоли.
"""Стенд проверки API-ключей для One AI API Key и Coarena.

Один файл, только стандартная библиотека. Режим — чат: каждый следующий запрос
содержит весь хвост диалога (роли ``system`` / ``user`` / ``assistant``), потому
что оба шлюза stateless и историю надо присылать заново.

Два шлюза, два формата провода:

* ``oneai`` (One AI API Key) — OpenAI: https://api.oneaiapikey.com/v1,
  Anthropic: https://api.oneaiapikey.com;
* ``coarena`` (Coarena) — OpenAI: https://coarena.ai/api/v1,
  Anthropic: https://coarena.ai/api.

Полезные запуски (Windows / Linux одинаково)::

    python scripts/api_key_probe.py --check
    python scripts/api_key_probe.py --platform coarena --list-models
    python scripts/api_key_probe.py --platform oneai --wire anthropic
    python scripts/api_key_probe.py -p coarena --prompt "привет, кто ты?"
    python scripts/api_key_probe.py -p coarena --questions questions.md

Чтение ответов. Длинный ответ уходит в постраничный просмотр (``less`` на
Linux/macOS, ``more`` на Windows), рассуждение по умолчанию скрыто, ответы
печатаются в ширину терминала. В чате ``/q ответ`` — перечитать ответы,
``/q рассуждение`` — показать рассуждение, ``/save`` — сохранить всё в файлы.
``--questions файл.md`` прогоняет вопросы из файла и раскладывает ответы по
файлам, чтобы сверять с эталоном в редакторе: заголовок ``## вопрос`` отделяет
вопросы, блок ``### Эталон`` внутри — образец для ручного сравнения.

Про ключи: заполните две константы ниже (``ONEAI_KEY``, ``COARENA_KEY``) либо
положите их в переменные окружения ``ONEAI_API_KEY`` / ``COARENA_API_KEY``.
Если ключ вставлен в файл, а файл лежит в git-репозитории — НЕ коммитьте его:
pre-commit с gitleaks остановит коммит, а при обходе ключ утечёт в историю.

Данные: Coarena сохраняет все промпты, ответы и рассуждения и может отдавать их
в датасетах — не отправляйте туда секреты и персональные данные.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, TypedDict

# scripts/ не является установленным пакетом: тот же shim, что в остальных
# gate-скриптах, чтобы импорт соседнего helper-модуля работал при прямом запуске.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._console import force_utf8_stdio

# ---------------------------------------------------------------------------
# Ключи. Заполните нужную строку (вторая может остаться пустой).
# ---------------------------------------------------------------------------
ONEAI_KEY = ""  # ключ One AI API Key, начинается на sk-
COARENA_KEY = ""  # ключ Coarena, начинается на coa_

USER_AGENT = "first-agent-api-key-probe/1.0"
DEFAULT_MODEL = "claude-sonnet-5-5"  # один и тот же id есть на обоих шлюзах
DEFAULT_MAX_TOKENS = 8192  # Anthropic-формат требует max_tokens явно
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_OUT = "probe-out"  # каталог для --save без --out

EFFORTS: tuple[str, ...] = ("off", "none", "minimal", "low", "medium", "high", "xhigh", "max")

# Anthropic-формат: «уровень усилий» выражается бюджетом thinking-токенов.
# Бюджет обязан быть меньше max_tokens, иначе шлюз вернёт 400.
_THINKING_BUDGETS: dict[str, int] = {
    "minimal": 1024,
    "low": 2048,
    "medium": 4096,
    "high": 6144,
    "xhigh": 7168,
    "max": 7680,
}


class Platform(TypedDict):
    """Статические адреса и подписи одного шлюза."""

    label: str
    openai_base: str
    anthropic_base: str
    models_url: str
    key_prefix: str
    env_var: str


PLATFORMS: dict[str, Platform] = {
    "oneai": {
        "label": "One AI API Key",
        "openai_base": "https://api.oneaiapikey.com/v1",
        "anthropic_base": "https://api.oneaiapikey.com",
        "models_url": "https://api.oneaiapikey.com/v1/models",
        "key_prefix": "sk-",
        "env_var": "ONEAI_API_KEY",
    },
    "coarena": {
        "label": "Coarena",
        "openai_base": "https://coarena.ai/api/v1",
        "anthropic_base": "https://coarena.ai/api",
        "models_url": "https://coarena.ai/api/v1/models",
        "key_prefix": "coa_",
        "env_var": "COARENA_API_KEY",
    },
}


# ---------------------------------------------------------------------------
# Цвет и ширина терминала
# ---------------------------------------------------------------------------
_COLOR = False


def _set_color(enabled: bool) -> None:
    global _COLOR
    _COLOR = enabled and not os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if _COLOR else text


def _bold(text: str) -> str:
    return _c("1", text)


def _dim(text: str) -> str:
    return _c("2", text)


def _cyan(text: str) -> str:
    return _c("36", text)


def _red(text: str) -> str:
    return _c("31", text)


def _green(text: str) -> str:
    return _c("32", text)


def _yellow(text: str) -> str:
    return _c("33", text)


def _screen_width() -> int:
    return max(40, min(shutil.get_terminal_size((100, 24)).columns, 100))


def _rule(width: int, title: str = "") -> str:
    if not title:
        return _dim("─" * min(width, 80))
    head = f"── {title} "
    tail = "─" * max(0, min(width, 80) - len(head))
    return _dim(head + tail)


# ---------------------------------------------------------------------------
# Чтение длинного вывода: постраничный просмотр
# ---------------------------------------------------------------------------
class Reader:
    """Печать ответов: порциями через ``less``/``more`` или сразу в терминал.

    ``less`` берётся с ``-R`` (не ломать цвет), ``-F`` (короткий ответ печатается
    сразу и просмотрщик закрывается), ``-X`` (не вытирать экран после выхода),
    ``-S`` (не переносить длинные строки — блоки кода остаются читаемыми).
    """

    def __init__(self, *, pager: str = "auto", width: int | None = None) -> None:
        self.width = width or _screen_width()
        self.pager = pager or "auto"

    def _pager_command(self) -> list[str] | None:
        if self.pager == "never" or not sys.stdout.isatty():
            return None
        if self.pager == "less":
            return ["less", "-R", "-F", "-X", "-S"]
        if self.pager == "more":
            return ["more"] if shutil.which("more") else None
        if shutil.which("less"):
            return ["less", "-R", "-F", "-X", "-S"]
        return ["more"] if shutil.which("more") else None

    def show(self, text: str) -> None:
        """Показать текст целиком: через пейджер, если он есть, иначе в поток."""
        command = self._pager_command()
        if command is None:
            print(text)
            return
        env = dict(os.environ)
        env.setdefault("LESSSECURE", "1")
        try:
            # Waiver: команда фиксированная (less/more), текст идёт в stdin.
            with subprocess.Popen(command, stdin=subprocess.PIPE, env=env) as proc:  # noqa: S603
                proc.communicate(text.encode("utf-8", errors="replace"))
        except OSError:
            print(text)

    def _window(self) -> int:
        """Сколько строк стабильно влезает в терминал (с запасом на оболочку)."""
        height = shutil.get_terminal_size((100, 30)).lines
        return max(8, height - 6)

    def needs_pager(self, lines: Sequence[str]) -> bool:
        """Блок не влезает в экран и терминал интерактивный."""
        return sys.stdout.isatty() and len(lines) > self._window()

    def hold(self, lines: Sequence[str], header: Sequence[str]) -> None:
        """Показать блок: короткий — сразу в терминал, длинный — в пейджер."""
        text = "\n".join([*header, "", *lines])
        if not self.needs_pager(lines):
            print(text)
            return
        self.show(text)

    def render(self, markdown: str) -> list[str]:
        return render_markdown(markdown, width=self.width)


def _header_lines(title: str, subtitle: str = "", width: int = 100) -> list[str]:
    lines = [_rule(width, title)]
    if subtitle:
        lines.append(_dim(subtitle))
    return lines


# ---------------------------------------------------------------------------
# Мини-рендер Markdown: заголовки, списки, цитаты, код, абзацы
# ---------------------------------------------------------------------------
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_SPAN = re.compile(r"`([^`]+)`")
_EM = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_BULLET = re.compile(r"^[-*+]\s+(.+)$")
_NUMBERED = re.compile(r"^(\d{1,3}[.)])\s+(.+)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_FENCE = re.compile(r"^```(.*)$")


def _strip_links(text: str) -> str:
    return _LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})", text)


def _unbold(text: str) -> str:
    return _BOLD.sub(lambda m: m.group(1) or m.group(2), text)


def _unspan(text: str) -> str:
    return _SPAN.sub(lambda m: m.group(1), text)


def _unem(text: str) -> str:
    return _EM.sub(lambda m: m.group(1), text)


def _inline(text: str) -> str:
    """Убрать разметку, которую терминал не рисует: **жирный**, `код`, [текст](url)."""
    for rule in (_strip_links, _unbold, _unspan, _unem):
        text = rule(text)
    return text


def _wrap_body(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def _wrap(text: str, width: int, first: str = "", rest: str = "") -> list[str]:
    """Перенос строки с висячим отступом (для маркеров списка)."""
    chunks = _wrap_body(text, max(20, width - len(first))) or [""]
    lines = [first + chunks[0]]
    lines.extend(rest + chunk for chunk in chunks[1:])
    return lines


class _BlockRenderer:
    """Накопитель строк ответа: абзацы, списки, цитаты, код, таблицы."""

    def __init__(self, width: int) -> None:
        self.width = width
        self.out: list[str] = []
        self._para: list[str] = []
        self._block = ""

    def flush(self) -> None:
        """Склеить накопленный абзац в перенесённые строки + пустая строка."""
        if not self._para:
            return
        joined = " ".join(self._para).strip()
        self._para.clear()
        self._block = "p"
        if joined:
            self.out.extend(_wrap(joined, self.width))
            self.out.append("")

    def start(self, kind: str) -> None:
        """Начать новый блок: пустая строка только при смене типа блока."""
        self.flush()
        if kind != self._block and self.out and self.out[-1].strip():
            self.out.append("")
        self._block = kind

    def heading(self, level: int, text: str) -> None:
        title = _inline(text)
        self.out.append(_bold(title))
        if level <= 2:
            self.out.append(_dim("─" * min(len(title), self.width)))
        self.out.append("")

    def code(self, lines: Sequence[str]) -> None:
        self.out.extend(_dim("  │ " + line.rstrip()) for line in lines)
        self.out.append("")

    def bullet(self, text: str) -> None:
        self.out.extend(_wrap(_inline(text), self.width, "  • ", "    "))

    def numbered(self, marker: str, text: str) -> None:
        self.out.extend(_wrap(_inline(text), self.width, marker + " ", "   "))

    def quote(self, text: str) -> None:
        self.out.extend(_wrap(_inline(text), self.width, "  │ ", "  │ "))

    def add_paragraph(self, text: str) -> None:
        """Добавить кусок обычного текста к текущему абзацу."""
        self._para.append(text)

    def result(self) -> list[str]:
        self.flush()
        while self.out and not self.out[-1].strip():
            self.out.pop()
        return self.out


def _render_line(renderer: _BlockRenderer, stripped: str) -> None:
    """Разобрать одну строку Markdown вне блока кода."""
    if not stripped:
        renderer.flush()
        return
    if stripped.startswith("|") and stripped.endswith("|"):
        renderer.start("table")
        renderer.out.append(_dim(stripped))
        return
    if re.fullmatch(r"([-*_])\1{2,}", stripped):
        renderer.start("hr")
        renderer.out.append(_rule(renderer.width))
        return
    heading = _HEADING.match(stripped)
    if heading:
        renderer.start("heading")
        renderer.heading(len(heading.group(1)), heading.group(2))
        return
    bullet = _BULLET.match(stripped)
    if bullet:
        renderer.start("list")
        renderer.bullet(bullet.group(1))
        return
    numbered = _NUMBERED.match(stripped)
    if numbered:
        renderer.start("list")
        renderer.numbered(numbered.group(1), numbered.group(2))
        return
    quote = _QUOTE.match(stripped)
    if quote:
        renderer.start("quote")
        renderer.quote(quote.group(1))
        return
    renderer.add_paragraph(_inline(stripped))


def render_markdown(text: str, *, width: int) -> list[str]:
    """Разложить ответ модели в готовые к печати строки с абзацами."""
    renderer = _BlockRenderer(width)
    fence: list[str] | None = None
    for raw in text.replace("\r\n", "\n").split("\n"):
        stripped = raw.strip()
        if fence is not None:
            if stripped.startswith("```"):
                renderer.code(fence)
                fence = None
            else:
                fence.append(raw)
            continue
        opening = _FENCE.match(stripped)
        if opening:
            renderer.start("code")
            fence = []
            lang = opening.group(1).strip()
            if lang:
                renderer.out.append(_dim(f"  ┆ {lang}"))
            continue
        _render_line(renderer, stripped)
    if fence is not None:
        renderer.code(fence)
    return renderer.result()


# ---------------------------------------------------------------------------
# Ошибки
# ---------------------------------------------------------------------------
class BenchError(Exception):
    """Ошибка настройки стенда (не ответ шлюза)."""


class ApiError(Exception):
    """Ответ шлюза с HTTP-статусом ошибки."""

    def __init__(self, status: int, code: str, message: str, request_id: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.request_id = request_id

    @classmethod
    def from_payload(cls, status: int, payload: Mapping[str, Any], headers: Mapping[str, str]) -> ApiError:
        """Разобрать конверт ошибки OpenAI (``error.code``) или Anthropic (``error.type``)."""
        inner = payload.get("error")
        code = ""
        message = ""
        if isinstance(inner, Mapping):
            code = str(inner.get("code") or inner.get("type") or "")
            message = str(inner.get("message") or "")
        elif isinstance(inner, str):
            message = inner
        top_level = payload.get("message")
        if not message and isinstance(top_level, str):
            message = top_level
        if not message:
            dumped = json.dumps(payload, ensure_ascii=False)
            message = dumped[:600] if dumped else "(пустое тело ответа)"
        return cls(status, code, message, request_id(headers))


def request_id(headers: Mapping[str, str]) -> str:
    """Id запроса для поддержки: Coarena отдаёт свой, One AI — X-Request-Id."""
    for name in ("x-coarena-request-id", "x-request-id", "request-id"):
        value = headers.get(name) or headers.get(name.title())
        if value:
            return value
    return ""


_HINTS: dict[str, str] = {
    "invalid_api_key": "ключ не принят: проверьте, что вставили его целиком, без кавычек и пробелов",
    "api_key_revoked": "ключ отозван — выпустите новый в консоли шлюза",
    "api_key_expired": "срок действия ключа истёк — выпустите новый",
    "conflicting_credentials": "отправлены два разных ключа; стенд шлёт один, проверьте переменную окружения",
    "insufficient_scope": "у ключа нет scope inference:write",
    "model_api_terms_required": "примите условия Model API один раз в браузере на coarena.ai/developers",
    "model_not_found": "такого model id нет: сверьтесь с --list-models (у шлюзов разный стиль id)",
    "unsupported_parameter": "модель не принимает это поле (часто thinking/output_config) — попробуйте --effort off",
    "unsupported_value": "значение поля не поддержано моделью (например, такой effort) — см. --list-models",
    "context_length_exceeded": "история переросла контекст модели — сбросьте её командой /reset",
    "rate_limit_exceeded": "лимит запросов: подождите и повторите (лимит обновляется за скользящее окно)",
    "concurrency_limit_exceeded": "уже идёт запрос к шлюзу — дождитесь ответа",
    "insufficient_quota": "дневной бюджет шлюза исчерпан — до следующего дня UTC",
    "paid_needs_deposit": "на счету нет пополнения: пополните баланс или возьмите модель с суффиксом :free",
    "free_needs_topup": "бесплатный лимит исчерпан: пополните баланс или подождите сутки",
    "insufficient_user_quota": "закончилась квота аккаунта",
    "daily_limit_free": "дневной лимит бесплатных запросов (100/сутки, сброс в 00:00 UTC)",
    "key_rate_limit": "слишком частые запросы по этому ключу — подождите",
    "overloaded_error": "апстрим перегружен — повторите через минуту",
    "upstream_error": "ошибка апстрима — повторите запрос",
    "upstream_timeout": "апстрим не ответил вовремя — повторите или снизьте effort",
    "model_unavailable": "модель сейчас недоступна — выберите другую",
    "server_busy": "шлюз занят — повторите через несколько секунд",
}

_STATUS_HINTS: dict[int, str] = {
    401: "ключ недействителен: проверьте значение в ONEAI_KEY / COARENA_KEY",
    402: "нужен депозит на балансе",
    403: "доступ запрещён: права ключа, условия использования или блокировка аккаунта",
    404: "неверный путь запроса — проверьте platform/wire (лишний или пропущенный /v1)",
    408: "шлюз не дождался начала ответа — снизьте effort или повторите",
    413: "тело запроса слишком большое — сократите историю",
    429: "упёрлись в лимит частоты или бюджета — подождите",
    500: "внутренняя ошибка шлюза — повторите",
    502: "ошибка апстрима — повторите",
    503: "модель или апстрим недоступны — выберите другую модель",
    504: "таймаут апстрима — повторите",
    529: "апстрим перегружен — повторите через минуту",
}


def describe_error(exc: ApiError) -> str:
    """Многострочное человекочитаемое описание ошибки шлюза."""
    head = f"HTTP {exc.status}" if exc.status else "ошибка потока"
    title = f"{head} · {exc.code}" if exc.code else head
    lines = [_red("✗ " + title), "  " + exc.message[:800]]
    hint = _HINTS.get(exc.code) or _STATUS_HINTS.get(exc.status)
    if hint:
        lines.append(_yellow("  → " + hint))
    if exc.request_id:
        lines.append(_dim("  request id: " + exc.request_id))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _read_body(raw: bytes) -> Mapping[str, Any]:
    if not raw:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {"raw": raw.decode("utf-8", errors="replace")[:600]}
    return payload if isinstance(payload, Mapping) else {"raw": payload}


def _http_error(exc: urllib.error.HTTPError) -> ApiError:
    headers = {str(k).lower(): str(v) for k, v in exc.headers.items()} if exc.headers else {}
    payload = _read_body(exc.read())
    return ApiError.from_payload(int(exc.code), payload, headers)


def _open_request(
    url: str,
    *,
    headers: Mapping[str, str],
    body: Mapping[str, Any] | None,
    timeout: float,
) -> Any:
    """Открыть соединение; для ошибок шлюза поднять :class:`ApiError`."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    method = "POST" if data is not None else "GET"
    # Waiver: схема зашита константами PLATFORMS (только https).
    request = urllib.request.Request(url, data=data, method=method)  # noqa: S310
    request.add_header("User-Agent", USER_AGENT)
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        # Waiver: схема зашита константами PLATFORMS (только https).
        return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
    except urllib.error.HTTPError as exc:
        raise _http_error(exc) from exc
    except urllib.error.URLError as exc:
        raise BenchError(f"сеть недоступна ({url}): {exc.reason}") from exc
    except TimeoutError as exc:
        raise BenchError(f"таймаут {timeout:.0f} с ({url})") from exc


def _get_json(url: str, headers: Mapping[str, str], timeout: float) -> Mapping[str, Any]:
    with _open_request(url, headers=headers, body=None, timeout=timeout) as response:
        return _read_body(response.read())


def _post_json(
    url: str, headers: Mapping[str, str], body: Mapping[str, Any], timeout: float
) -> tuple[dict[str, Any], dict[str, str]]:
    """POST без стриминга: тело и заголовки ответа."""
    with _open_request(url, headers=headers, body=body, timeout=timeout) as response:
        payload = dict(_read_body(response.read()))
        response_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
    return payload, response_headers


def iter_sse(lines: Iterable[bytes]) -> Iterator[tuple[str, str]]:
    """Собрать server-sent events: (event, data), данные склеиваются через \\n."""
    event = ""
    data: list[str] = []
    for raw in lines:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data:
                yield event, "\n".join(data)
            event = ""
            data.clear()
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            event = value
        elif field == "data":
            data.append(value)
    if data:
        yield event, "\n".join(data)


# ---------------------------------------------------------------------------
# Ответ модели
# ---------------------------------------------------------------------------
@dataclass
class Reply:
    """Собранный ответ: текст, рассуждение, служебные поля."""

    text: str = ""
    reasoning: str = ""
    model: str = ""
    request_id: str = ""
    stop_reason: str = ""
    in_tokens: int = 0
    out_tokens: int = 0
    reasoning_tokens: int = 0


def _text_of(value: Any) -> str:
    """Достать текст из строки или из списка content-блоков."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping):
                chunk = item.get("text") or item.get("content")
                if isinstance(chunk, str):
                    parts.append(chunk)
        return "".join(parts)
    return ""


def _int_of(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _apply_openai_usage(reply: Reply, usage: Mapping[str, Any]) -> None:
    reply.in_tokens = _int_of(usage.get("prompt_tokens")) or _int_of(usage.get("input_tokens"))
    reply.out_tokens = _int_of(usage.get("completion_tokens")) or _int_of(usage.get("output_tokens"))
    details = usage.get("completion_tokens_details")
    if isinstance(details, Mapping):
        reply.reasoning_tokens = _int_of(details.get("reasoning_tokens"))


def _apply_anthropic_usage(reply: Reply, usage: Mapping[str, Any]) -> None:
    reply.in_tokens = max(reply.in_tokens, _int_of(usage.get("input_tokens")))
    reply.out_tokens = max(reply.out_tokens, _int_of(usage.get("output_tokens")))


def parse_openai_reply(payload: Mapping[str, Any], headers: Mapping[str, str]) -> Reply:
    """Разобрать нестриминговый ответ /chat/completions."""
    reply = Reply(request_id=request_id(headers))
    rid = payload.get("id")
    if isinstance(rid, str):
        reply.request_id = rid or reply.request_id
    model = payload.get("model")
    if isinstance(model, str):
        reply.model = model
    choices = payload.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], Mapping):
        first = choices[0]
        message = first.get("message")
        if isinstance(message, Mapping):
            reply.text = _text_of(message.get("content"))
            reply.reasoning = _text_of(message.get("reasoning_content")) or _text_of(message.get("reasoning"))
        stop = first.get("finish_reason")
        if isinstance(stop, str):
            reply.stop_reason = stop
    usage = payload.get("usage")
    if isinstance(usage, Mapping):
        _apply_openai_usage(reply, usage)
    return reply


def parse_anthropic_reply(payload: Mapping[str, Any], headers: Mapping[str, str]) -> Reply:
    """Разобрать нестриминговый ответ /v1/messages."""
    reply = Reply(request_id=request_id(headers))
    rid = payload.get("id")
    if isinstance(rid, str):
        reply.request_id = rid or reply.request_id
    model = payload.get("model")
    if isinstance(model, str):
        reply.model = model
    stop = payload.get("stop_reason")
    if isinstance(stop, str):
        reply.stop_reason = stop
    blocks = payload.get("content")
    if isinstance(blocks, list):
        texts: list[str] = []
        thoughts: list[str] = []
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            kind = block.get("type")
            if kind == "text":
                texts.append(_text_of(block.get("text")))
            elif kind == "thinking":
                thoughts.append(_text_of(block.get("thinking")))
        reply.text = "".join(texts)
        reply.reasoning = "".join(thoughts)
    usage = payload.get("usage")
    if isinstance(usage, Mapping):
        _apply_anthropic_usage(reply, usage)
    return reply


def _enter_openai_stream(response: Any, reply: Reply, tick: Callable[[Reply], None]) -> None:
    for _event, data in iter_sse(response):
        if not data or data.strip() == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if isinstance(chunk, Mapping):
            _apply_openai_chunk(chunk, reply)
        tick(reply)


def _apply_openai_chunk(chunk: Mapping[str, Any], reply: Reply) -> None:
    """Разложить один чанк /chat/completions в поля ответа.

    Рассуждение приходит отдельным полем, имя которого у шлюзов разное:
    ``reasoning_content`` (так его отдаёт One AI) или ``reasoning``.
    """
    if chunk.get("error"):
        raise ApiError.from_payload(0, chunk, {})
    rid = chunk.get("id")
    if isinstance(rid, str) and rid:
        reply.request_id = rid
    model = chunk.get("model")
    if isinstance(model, str) and model:
        reply.model = model
    usage = chunk.get("usage")
    if isinstance(usage, Mapping):
        _apply_openai_usage(reply, usage)
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], Mapping):
        return
    first = choices[0]
    stop = first.get("finish_reason")
    if isinstance(stop, str) and stop:
        reply.stop_reason = stop
    delta = first.get("delta")
    if isinstance(delta, Mapping):
        reply.reasoning += _text_of(delta.get("reasoning_content")) + _text_of(delta.get("reasoning"))
        reply.text += _text_of(delta.get("content"))


def _enter_anthropic_stream(response: Any, reply: Reply, tick: Callable[[Reply], None]) -> None:
    for event, data in iter_sse(response):
        if not data:
            continue
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        if not isinstance(chunk, Mapping):
            continue
        _apply_anthropic_event(event or str(chunk.get("type") or ""), chunk, reply)
        tick(reply)


def _apply_anthropic_event(kind: str, chunk: Mapping[str, Any], reply: Reply) -> None:
    """Разложить одно SSE-событие Anthropic в поля ответа.

    ``ping`` и незнакомые события игнорируются: набор событий у шлюзов
    отличается, падать на неизвестном нельзя.
    """
    if kind == "error":
        raise ApiError.from_payload(0, chunk, {})
    if kind == "message_start":
        message = chunk.get("message")
        if isinstance(message, Mapping):
            _apply_anthropic_message(message, reply)
    elif kind == "content_block_start":
        block = chunk.get("content_block")
        if isinstance(block, Mapping):
            if block.get("type") == "text":
                reply.text += _text_of(block.get("text"))
            elif block.get("type") == "thinking":
                reply.reasoning += _text_of(block.get("thinking"))
    elif kind == "content_block_delta":
        _apply_anthropic_delta(chunk.get("delta"), reply)
    elif kind == "message_delta":
        delta = chunk.get("delta")
        if isinstance(delta, Mapping):
            stop = delta.get("stop_reason")
            if isinstance(stop, str) and stop:
                reply.stop_reason = stop
        usage = chunk.get("usage")
        if isinstance(usage, Mapping):
            _apply_anthropic_usage(reply, usage)


def _apply_anthropic_message(message: Mapping[str, Any], reply: Reply) -> None:
    rid = message.get("id")
    if isinstance(rid, str) and rid:
        reply.request_id = rid
    model = message.get("model")
    if isinstance(model, str) and model:
        reply.model = model
    usage = message.get("usage")
    if isinstance(usage, Mapping):
        _apply_anthropic_usage(reply, usage)


def _apply_anthropic_delta(delta: Any, reply: Reply) -> None:
    if not isinstance(delta, Mapping):
        return
    delta_kind = delta.get("type")
    if delta_kind == "text_delta":
        reply.text += _text_of(delta.get("text"))
    elif delta_kind == "thinking_delta":
        reply.reasoning += _text_of(delta.get("thinking"))


# ---------------------------------------------------------------------------
# Настройки запуска
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    """Разобранные аргументы командной строки."""

    platform: str
    wire: str
    key: str
    model: str
    effort: str
    system: str
    max_tokens: int | None
    stream: bool
    timeout: float
    verbose: bool
    reasoning: bool = False
    save: bool = False
    pager: str = "auto"
    paged: bool = True
    questions: str = ""
    out: str = ""
    max_context_chars: int = 0
    width: int = 0


class Turn(TypedDict):
    """Один вопрос стенда и ответ модели на него."""

    index: int
    prompt: str
    text: str
    reasoning: str
    meta: str
    error: str
    reference: str
    files: list[str]


def _mask(key: str) -> str:
    """Показать ключ в логе, не выдав его целиком."""
    return key[:6] + "…" + key[-4:] if len(key) > 12 else "(короткий)"


def _redact(name: str, value: str) -> str:
    """Замаскировать значение секретного заголовка (остальные не трогаем)."""
    lowered = name.lower()
    if lowered == "authorization":
        scheme, _, credential = value.partition(" ")
        return f"{scheme} {_mask(credential)}" if credential else _mask(value)
    if lowered in {"x-api-key", "api-key"}:
        return _mask(value)
    return value


def _key_from(platform: str) -> str:
    """Ключ из константы файла, иначе из переменной окружения."""
    raw = COARENA_KEY if platform == "coarena" else ONEAI_KEY
    value = raw.strip() or os.environ.get(PLATFORMS[platform]["env_var"], "").strip()
    return value.strip("\"'").strip()


def _resolve_platform(requested: str | None) -> str:
    """Платформа из --platform, а без него — по тому, какой ключ заполнен."""
    if requested:
        return requested
    filled = [name for name in PLATFORMS if _key_from(name)]
    if len(filled) == 1:
        return filled[0]
    if not filled:
        raise BenchError(
            "не заполнен ни один ключ: впишите ключ в ONEAI_KEY или COARENA_KEY "
            "в начале файла (или задайте ONEAI_API_KEY / COARENA_API_KEY) и укажите --platform"
        )
    raise BenchError("заполнены оба ключа — укажите, какой проверяем: --platform oneai | coarena")


def _thinking_budget(effort: str, max_tokens: int, *, claude: bool) -> int | None:
    """Бюджет thinking для Anthropic-формата; None — thinking не включаем.

    Бюджет обязан быть меньше ``max_tokens``. Anthropic-модели требуют минимум
    1024 токена, прочие шлюзы принимают меньшие бюджеты.
    """
    base = _THINKING_BUDGETS.get(effort)
    floor = 1024 if claude else 512
    if base is None or max_tokens < floor * 2:
        return None
    budget = min(max(base, floor), max_tokens - 512)
    return budget if budget >= floor else None


# ---------------------------------------------------------------------------
# Клиент
# ---------------------------------------------------------------------------
class ChatClient:
    """Чат с выбранным шлюзом и форматом провода; история шлётся заново каждый ход."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        spec = PLATFORMS[settings.platform]
        self.label = spec["label"]
        self.models_url = spec["models_url"]
        self.openai_url = spec["openai_base"] + "/chat/completions"
        self.anthropic_url = spec["anthropic_base"] + "/v1/messages"
        self._tty = sys.stdout.isatty()
        self._progress_at = 0.0
        self.reader = Reader(pager=settings.pager, width=settings.width or None)
        self.question = ""
        self.reference = ""
        self.turns: list[Turn] = []

    # -- адреса и заголовки -------------------------------------------------
    @property
    def url(self) -> str:
        return self.openai_url if self.settings.wire == "openai" else self.anthropic_url

    def _auth_headers(self) -> dict[str, str]:
        """Заголовки авторизации: для списка моделей — самый совместимый вариант."""
        return {"Authorization": f"Bearer {self.settings.key}", "Content-Type": "application/json"}

    def _request_headers(self) -> dict[str, str]:
        headers = dict(self._auth_headers())
        if self.settings.wire == "anthropic":
            headers["x-api-key"] = self.settings.key
            headers["anthropic-version"] = ANTHROPIC_VERSION
        if self.settings.stream:
            headers["Accept"] = "text/event-stream"
        return headers

    # -- тело запроса: только необходимые поля + усилие ---------------------
    def _history_rows(self, history: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        if self.settings.system:
            rows.append({"role": "system", "content": self.settings.system})
        rows.extend({"role": str(row["role"]), "content": str(row["content"])} for row in history)
        return rows

    def build_body(self, history: Sequence[Mapping[str, str]]) -> dict[str, Any]:
        """Собрать тело запроса по спецификации выбранного формата."""
        if self.settings.wire == "openai":
            body: dict[str, Any] = {"model": self.settings.model, "messages": self._history_rows(history)}
            if self.settings.effort != "off":
                body["reasoning_effort"] = self.settings.effort
            if self.settings.max_tokens:
                body["max_completion_tokens" if self.settings.effort != "off" else "max_tokens"] = (
                    self.settings.max_tokens
                )
            if self.settings.stream:
                body["stream"] = True
                body["stream_options"] = {"include_usage": True}
            return body

        rows = self._history_rows(history)
        system = "\n\n".join(str(row["content"]) for row in rows if row["role"] == "system")
        turns = [{"role": str(row["role"]), "content": str(row["content"])} for row in rows if row["role"] != "system"]
        max_tokens = self.settings.max_tokens or DEFAULT_MAX_TOKENS
        body = {"model": self.settings.model, "max_tokens": max_tokens, "messages": turns}
        if system:
            body["system"] = system
        budget = _thinking_budget(self.settings.effort, max_tokens, claude="claude" in self.settings.model.lower())
        if budget:
            body["thinking"] = {"type": "enabled", "budget_tokens": budget}
        if self.settings.stream:
            body["stream"] = True
        return body

    # -- прогресс -----------------------------------------------------------
    def _tick(self, reply: Reply) -> None:
        if not self._tty:
            return
        now = time.monotonic()
        if now - self._progress_at < 0.1:
            return
        self._progress_at = now
        parts = [
            f"{len(reply.reasoning)} симв. рассуждения" if reply.reasoning else "",
            f"{len(reply.text)} симв. ответа",
        ]
        text = " · ".join(part for part in parts if part)
        sys.stdout.write("\r\x1b[2K" + _dim("  … " + text))
        sys.stdout.flush()

    def _clear_progress(self) -> None:
        if self._tty:
            sys.stdout.write("\r\x1b[2K")
            sys.stdout.flush()

    # -- запрос -------------------------------------------------------------
    def send(self, history: Sequence[Mapping[str, str]]) -> tuple[Reply, float]:
        """Отправить историю и вернуть ответ вместе с длительностью, в секундах."""
        body = self.build_body(history)
        headers = self._request_headers()
        if self.settings.verbose:
            self._dump(body, headers)
        started = time.monotonic()
        if not self.settings.stream:
            payload, response_headers = _post_json(self.url, headers, body, self.settings.timeout)
            replied = parse_openai_reply if self.settings.wire == "openai" else parse_anthropic_reply
            return replied(payload, response_headers), time.monotonic() - started

        reply = Reply()
        with _open_request(self.url, headers=headers, body=body, timeout=self.settings.timeout) as response:
            meta = {str(k).lower(): str(v) for k, v in response.headers.items()}
            if self.settings.verbose:
                self._dump_headers(meta)
            if self.settings.wire == "openai":
                _enter_openai_stream(response, reply, self._tick)
            else:
                _enter_anthropic_stream(response, reply, self._tick)
            reply.request_id = reply.request_id or request_id(meta)
        self._clear_progress()
        return reply, time.monotonic() - started

    def _dump(self, body: Mapping[str, Any], headers: Mapping[str, str]) -> None:
        shown = {name: _redact(name, value) for name, value in headers.items()}
        print(_dim(f"  POST {self.url}"))
        print(_dim("  headers: " + json.dumps(shown, ensure_ascii=False)))
        print(_dim("  body:    " + json.dumps(body, ensure_ascii=False)))

    def _dump_headers(self, headers: Mapping[str, str]) -> None:
        wanted = ("x-coarena-model", "x-coarena-dropped-params", "x-coarena-emulated", "x-fallback-from")
        shown = {name: headers[name] for name in wanted if name in headers}
        if shown:
            print(_dim("  ответ: " + json.dumps(shown, ensure_ascii=False)))

    # -- модели -------------------------------------------------------------
    def fetch_models(self) -> list[Mapping[str, Any]]:
        payload = _get_json(self.models_url, self._auth_headers(), self.settings.timeout)
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, Mapping)]
        return []

    def print_models(self) -> int:
        try:
            models = self.fetch_models()
        except ApiError as exc:
            print(describe_error(exc), file=sys.stderr)
            return 1
        if not models:
            print(_yellow("шлюз вернул пустой список моделей"))
            return 1
        lines = [_bold(f"{self.label}: {len(models)} моделей")]
        for model in models:
            mid = str(model.get("id") or "")
            extra: list[str] = []
            capabilities = model.get("capabilities")
            if isinstance(capabilities, Mapping):
                efforts = capabilities.get("efforts")
                if isinstance(efforts, list) and efforts:
                    extra.append("effort: " + "/".join(str(e) for e in efforts))
            endpoints = model.get("supported_endpoint_types")
            if isinstance(endpoints, list) and endpoints:
                extra.append("/".join(str(e) for e in endpoints))
            suffix = _dim("  " + " · ".join(extra)) if extra else ""
            lines.append(f"  {mid}{suffix}")
        lines.append(_dim(f"\nпо умолчанию в стенде: {self.settings.model}"))
        self.reader.show("\n".join(lines))
        return 0

    # -- проверка ключа -----------------------------------------------------
    def _probe(self, history: Sequence[Mapping[str, str]], max_tokens: int | None) -> tuple[Reply, float]:
        """Минимальный запрос для --check: сузить лимит ответа на один запрос."""
        settings = self.settings
        saved = settings.max_tokens
        settings.max_tokens = max_tokens
        try:
            return self.send(history)
        finally:
            settings.max_tokens = saved

    def check(self) -> int:
        """Проверить ключ: список моделей, затем минимальный реальный запрос."""
        width = _screen_width()
        print(_rule(width, "проверка ключа"))
        print(f"  шлюз:    {_bold(self.label)}  ({self.settings.platform})")
        print(f"  формат:  {self.settings.wire}  →  {self.url}")
        print(f"  модель:  {self.settings.model}   effort: {self.settings.effort}")
        print(f"  ключ:    {_mask(self.settings.key)}  ({len(self.settings.key)} симв.)")
        ok = True

        print(_dim("\n1) список моделей"))
        try:
            models = self.fetch_models()
            ids = [str(item.get("id") or "") for item in models]
            print(f"   {_green('✓')} {len(models)} моделей получено за запрос")
            if self.settings.model in ids:
                print(f"   {_green('✓')} {self.settings.model} есть в списке")
            else:
                print(f"   {_yellow('!')} {self.settings.model} в списке нет — сверьтесь с --list-models")
        except ApiError as exc:
            ok = False
            print("   " + describe_error(exc).replace("\n", "\n   "))

        print(_dim("2) минимальный запрос к модели"))
        history = [{"role": "user", "content": "Ответь одним словом: ok"}]
        probe_tokens = 2048 if self.settings.wire == "anthropic" else None
        try:
            reply, elapsed = self._probe(history, probe_tokens)
        except ApiError as exc:
            print("   " + describe_error(exc).replace("\n", "\n   "))
            print(_red("\nитог: ключ не прошёл проверку"))
            return 1
        except BenchError as exc:
            print(_red(f"   ✗ {exc}"))
            return 2

        answer = " ".join(_inline(reply.text).split())[:120]
        print(f"   {_green('✓')} ответ за {elapsed:.1f} с: {answer or '(пустой текст)'}")
        print(f"   {_dim(_meta(reply, elapsed))}")
        print(_green("\nитог: ключ работает" if ok else "\nитог: ключ работает, но список моделей отдал ошибку"))
        return 0

    # -- одиночный вопрос ---------------------------------------------------
    def ask_once(self, prompt: str) -> int:
        """Один вопрос без истории: удобно для сверки с эталоном."""
        print(_dim(f"{self.label} · {self.settings.model} · {self.settings.wire} · effort={self.settings.effort}"))
        turn, code = self._ask(prompt, [{"role": "user", "content": prompt}])
        if turn is not None:
            self._present(turn)
            self._autosave(turn)
        return code

    def _ask(self, prompt: str, history: Sequence[Mapping[str, str]]) -> tuple[Turn | None, int]:
        """Запрос + запись хода в журнал; код возврата как у процесса."""
        try:
            reply, elapsed = self.send(history)
        except ApiError as exc:
            line = describe_error(exc)
            print(line, file=sys.stderr)
            self._record(prompt, None, 0.0, line)
            return None, 1
        except BenchError as exc:
            print(_red(f"✗ {exc}"), file=sys.stderr)
            self._record(prompt, None, 0.0, _red(f"✗ {exc}"))
            return None, 2
        except KeyboardInterrupt:
            self._clear_progress()
            print(_dim("\n  прервано; в журнал не попало"))
            return None, 130
        return self._record(prompt, reply, elapsed), 0

    # -- сохранение ответов -------------------------------------------------
    def _save_turn(self, turn: Turn, directory: Path) -> list[str]:
        """Записать ответ, эталон и карточку сверки рядом друг с другом."""
        directory.mkdir(parents=True, exist_ok=True)
        number = f"{turn['index']:02d}"
        written: list[str] = []
        answer = directory / f"{number}-answer.md"
        answer.write_text(turn["text"].strip() + "\n", encoding="utf-8")
        written.append(str(answer))
        if turn["reasoning"].strip():
            thoughts = directory / f"{number}-reasoning.md"
            thoughts.write_text(turn["reasoning"].strip() + "\n", encoding="utf-8")
            written.append(str(thoughts))
        if turn["reference"].strip():
            reference = directory / f"{number}-reference.md"
            reference.write_text(turn["reference"].strip() + "\n", encoding="utf-8")
            written.append(str(reference))
        card = [
            f"# Вопрос {turn['index']}",
            "",
            "## Вопрос",
            "",
            turn["prompt"],
            "",
            "## Ответ модели",
            "",
            turn["text"].strip() or "_пусто_",
            "",
            "## Эталон",
            "",
            turn["reference"].strip() or "_эталон не задан_",
            "",
            "## Сверка",
            "",
            "- [ ] совпадает",
            "- [ ] частично",
            "- [ ] неверно",
            "",
            f"_{(turn['meta'] or turn['error']).strip()}_",
            "",
        ]
        review = directory / f"{number}-review.md"
        review.write_text("\n".join(card), encoding="utf-8")
        written.append(str(review))
        return written

    def _autosave(self, turn: Turn) -> None:
        if not self.settings.save:
            return
        directory = Path(self.settings.out or DEFAULT_OUT)
        turn["files"] = self._save_turn(turn, directory)
        review = directory / f"{turn['index']:02d}-review.md"
        print(_dim(f"  сохранено: {review}"))

    def _write_index(self, directory: Path) -> Path:
        """Оглавление каталога: вопрос → карточка сверки и файл ответа."""
        index = [f"# Ответы стенда · {self.label} · {self.settings.model}", ""]
        for turn in self.turns:
            number = f"{turn['index']:02d}"
            head = " ".join(turn["prompt"].split())[:110]
            index.append(f"- [{number}] {head} → `{number}-review.md`, `{number}-answer.md`")
        index.append("")
        index.append("_Сверка: откройте карточку в редакторе рядом с эталоном и отметьте пункт._")
        path = directory / "index.md"
        path.write_text("\n".join(index) + "\n", encoding="utf-8")
        return path

    def save_all(self) -> None:
        """Сохранить все ходы в каталог --out (или ./probe-out)."""
        if not self.turns:
            print(_yellow("  пока нечего сохранять"))
            return
        directory = Path(self.settings.out or DEFAULT_OUT)
        for turn in self.turns:
            turn["files"] = self._save_turn(turn, directory)
        index = self._write_index(directory)
        print(_dim(f"  сохранено в {directory}: {len(self.turns)} ход(ов) + {index.name}"))

    # -- пакетный режим -----------------------------------------------------
    def run_questions(self) -> int:
        """Прогнать вопросы из файла и разложить ответы по файлам."""
        path = Path(self.settings.questions)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(_red(f"ошибка: не прочитать {path}: {exc}"), file=sys.stderr)
            return 2
        questions = split_questions(raw)
        if not questions:
            print(_red(f"ошибка: в {path} нет вопросов (нужен заголовок ## или ###)"), file=sys.stderr)
            return 2
        directory = Path(self.settings.out or f"{path.stem}-out")
        if not self.settings.paged:
            print(_dim(f"{self.label} · {self.settings.model} · {self.settings.wire}"))
            print(_dim(f"вопросов: {len(questions)} · модели: нет истории, каждый вопрос отдельно"))
            print(_dim(f"ответы: {directory}"))
        for number, (question, reference) in enumerate(questions, start=1):
            head = question.splitlines()[0]
            print(_dim(f"\n[{number}/{len(questions)}] {head[: self.reader.width]}"))
            self.reference = reference
            self.question = question
            turn, code = self._ask(question, [{"role": "user", "content": question}])
            if turn is None:
                if code == 2:
                    return code
                turn = self._record(question, None, 0.0, "ошибка шлюза")
            turn["files"] = self._save_turn(turn, directory)
            review = directory / f"{turn['index']:02d}-review.md"
            print(_dim(f"   → {review}"))
        index = self._write_index(directory)
        print(_green(f"\nготово: {len(questions)} ответ(ов) в {directory}"))
        print(_dim(f"оглавление для сверки: {index}"))
        return 0

    # -- вывод ответа -------------------------------------------------------
    def _turn_lines(self, turn: Turn, *, answer: bool = True, reasoning: bool = False) -> list[str]:
        """Собрать блок для печати: заголовок, рассуждение, ответ, служебная строка."""
        width = self.reader.width
        label = f"вопрос {turn['index']}"
        if self.settings.wire == "anthropic" or self.settings.platform:
            label += f" · {self.settings.model} · {self.settings.wire}"
        lines = _header_lines(label, width=width)
        lines.append(_dim(turn["prompt"] if len(turn["prompt"]) <= width else turn["prompt"][: width - 1] + "…"))
        if turn["error"]:
            lines.append("")
            lines.extend(turn["error"].splitlines())
            return lines
        if reasoning and turn["reasoning"].strip():
            lines.append("")
            lines.append(_dim("── рассуждение " + "─" * max(0, width - 16)))
            lines.extend(_dim(line) for line in self.reader.render(turn["reasoning"]))
        if answer:
            lines.append("")
            body = self.reader.render(turn["text"])
            lines.extend(body or [_yellow("(модель вернула пустой текст)")])
        lines.append("")
        lines.extend(_dim(line) for line in _wrap(turn["meta"].strip(), width, "  ", "  "))
        return lines

    def _present(self, turn: Turn) -> None:
        """Показать ответ: длинный — в пейджере, короткий — сразу в терминал."""
        lines = self._turn_lines(turn, reasoning=self.settings.reasoning)
        if self.settings.paged and self.reader.needs_pager(lines):
            self.reader.hold(lines, [])
            number = turn["index"]
            hint = f"  вопрос {number} · /q {number} — перечитать · /q {number} расс — с рассуждением"
            print(_dim(hint))
            return
        print()
        print("\n".join(lines))

    def _record(self, prompt: str, reply: Reply | None, elapsed: float, error: str = "") -> Turn:
        turn: Turn = {
            "index": len(self.turns) + 1,
            "prompt": prompt,
            "text": reply.text if reply else "",
            "reasoning": reply.reasoning if reply else "",
            "meta": _meta(reply, elapsed) if reply else "",
            "error": error,
            "reference": self.reference,
            "files": [],
        }
        self.turns.append(turn)
        return turn

    # -- чат ----------------------------------------------------------------
    def repl(self) -> int:
        """REPL: каждый ход отправляет всю историю заново."""
        width = self.reader.width
        history: list[dict[str, str]] = []
        print(_rule(width, f"{self.label} · чат"))
        print(_dim(f"  {self.settings.wire} · {self.settings.model} · effort={self.settings.effort}"))
        hint = "  /help — команды · /q — перечитать ответ · /reset — история · /exit — выход"
        for line in _wrap_body(hint, width):
            print(_dim(line))
        while True:
            text = self._read_input()
            if text is None:
                self._finish()
                return 0
            if not text:
                continue
            if text.startswith("/"):
                if self._run_command(text, history):
                    self._finish()
                    return 0
                continue
            self._turn(text, history)

    def _finish(self) -> None:
        """Итог сессии: где лежат ответы, как их сохранить."""
        if not self.turns:
            return
        hint = f"ответов за сессию: {len(self.turns)} · /save — записать в файлы · /q — перечитать"
        print()
        for line in _wrap(hint, self.reader.width, "  ", "  "):
            print(_dim(line))

    @staticmethod
    def _read_input() -> str | None:
        """Прочитать реплику; None — выход по EOF или Ctrl+C."""
        try:
            raw = input(_cyan("\nвы> "))
        except EOFError:
            print()
            return None
        except KeyboardInterrupt:
            print(_dim("\nвыход"))
            return None
        return raw.strip()

    def _run_command(self, text: str, history: list[dict[str, str]]) -> bool:
        """Выполнить /команду; True — пора выходить из чата."""
        command, _, argument = text.partition(" ")
        argument = argument.strip()
        if command in {"/exit", "/quit", "/bye"}:
            return True
        if command == "/reset":
            history.clear()
            print(_dim("  история очищена"))
        elif command == "/help":
            self._help()
        elif command == "/history":
            self._show_history(history)
        elif command == "/save":
            if argument:
                self.settings.out = argument
            self.save_all()
        elif command == "/q":
            self._reread(argument)
        elif not self._set_option(command, argument):
            print(_yellow(f"  неизвестная команда {command!r}; /help"))
        return False

    def _set_option(self, command: str, argument: str) -> bool:
        """Команды-переключатели: /model, /effort, /reasoning, /pause, /width, /ref."""
        settings = self.settings
        if command == "/models":
            self.print_models()
        elif command == "/model" and argument:
            settings.model = argument
            print(_dim(f"  модель: {settings.model}  (история сохранена)"))
        elif command == "/effort" and argument in EFFORTS:
            settings.effort = argument
            print(_dim(f"  effort: {settings.effort}"))
        elif command == "/reasoning":
            settings.reasoning = not settings.reasoning
            print(_dim(f"  рассуждение: {'показывать' if settings.reasoning else 'скрыто'}"))
        elif command == "/pause":
            settings.paged = not settings.paged
            print(_dim(f"  постраничный просмотр: {'вкл' if settings.paged else 'выкл'}"))
        elif command == "/width" and argument.isdigit():
            self.reader.width = max(40, min(int(argument), 200))
            print(_dim(f"  ширина: {self.reader.width}"))
        elif command == "/ref":
            if argument:
                self.reference = argument
                if self.turns:
                    self.turns[-1]["reference"] = argument
                print(_dim("  эталон запомнен для текущего вопроса"))
            else:
                print(_dim("  эталон: " + (self.reference or "(не задан; /ref <текст>)")))
        else:
            return False
        return True

    def _show_history(self, history: Sequence[Mapping[str, str]]) -> None:
        chars = sum(len(str(row.get("content", ""))) for row in history)
        print(_dim(f"  ходов в истории: {len(history)} · символов: {chars}"))
        for row in history:
            head = " ".join(str(row.get("content", "")).split())[:80]
            print(_dim(f"    {row.get('role')}: {head}"))

    def _reread(self, argument: str) -> None:
        """Показать ответ ещё раз: /q, /q 2, /q рассуждение, /q 2 рассуждение."""
        if not self.turns:
            print(_yellow("  ответов пока нет"))
            return
        parts = argument.split()
        index = len(self.turns)
        reasoning = self.settings.reasoning
        for part in parts:
            if part.isdigit():
                index = max(1, min(int(part), len(self.turns)))
            elif part.startswith("расс") or part == "r":
                reasoning = True
        turn = self.turns[index - 1]
        if self.settings.paged:
            self.reader.show("\n".join(self._turn_lines(turn, reasoning=reasoning)))
        else:
            print("\n".join(self._turn_lines(turn, reasoning=reasoning)))

    def _turn(self, text: str, history: list[dict[str, str]]) -> None:
        """Один ход: вопрос уходит вместе со всей прежней историей."""
        limit = self.settings.max_context_chars
        if limit and _history_chars(history) > limit:
            print(_yellow(f"  история длиннее {limit} симв. — очищаю, чтобы не упереться в контекст"))
            history.clear()
        history.append({"role": "user", "content": text})
        turn, _code = self._ask(text, history)
        if turn is None:
            history.pop()
            return
        self._present(turn)
        self._autosave(turn)
        # Пустой текст нельзя класть в историю: Anthropic-формат отвергает пустой
        # content ассистента, и следующий ход упал бы в 400.
        history.append({"role": "assistant", "content": turn["text"] or "(пустой ответ)"})

    def _help(self) -> None:
        print(
            _dim(
                "  /q [N] [расс]    перечитать ответ N (последний по умолчанию), «расс» — с рассуждением\n"
                "  /ref [текст]     задать/показать эталон для сверки\n"
                "  /save [каталог]  сохранить все ответы в файлы (01-review.md, 01-answer.md)\n"
                "  /reasoning       показывать/скрывать рассуждение модели\n"
                "  /pause           включить/выключить постраничный просмотр\n"
                "  /width N         ширина строки\n"
                "  /reset           очистить историю\n"
                "  /history         что лежит в истории\n"
                "  /model <id>      сменить модель без потери истории\n"
                "  /effort <lvl>    off | none | minimal | low | medium | high | xhigh | max\n"
                "  /models          список моделей шлюза\n"
                "  /exit            выход"
            )
        )


def _history_chars(history: Sequence[Mapping[str, str]]) -> int:
    return sum(len(str(row.get("content", ""))) for row in history)


_QUESTION_HEADING = re.compile(r"^##\s+(?!#)(.+)$")
_REFERENCE_WORDS = r"(эталон|reference|expected|ответ[- ]эталон|эталонный ответ)"
_REFERENCE_HEADING = re.compile(rf"^#{{2,4}}\s+{_REFERENCE_WORDS}\s*$", re.IGNORECASE)
_NUMBERED_QUESTION = re.compile(r"^\d{1,3}[.)]\s+(.+)$")


class _QuestionBlock(TypedDict):
    """Сырые строки одного вопроса и его эталона."""

    question: list[str]
    reference: list[str]


def split_questions(raw: str) -> list[tuple[str, str]]:
    """Разобрать файл вопросов: заголовок ``## …`` начинает вопрос, ``### Эталон`` — образец.

    Всё до первого вопроса считается преамбулой и пропускается. Если заголовков
    нет, вопросы берутся из нумерованного списка (``1. …``). Файл вообще без
    разметки считается одним вопросом.
    """
    lines = raw.replace("\r\n", "\n").split("\n")
    numbered = not any(_QUESTION_HEADING.match(line) for line in lines)
    marker = _NUMBERED_QUESTION if numbered else _QUESTION_HEADING
    blocks: list[_QuestionBlock] = []
    in_reference = False
    for line in lines:
        opening = marker.match(line)
        if opening:
            blocks.append({"question": [opening.group(1)], "reference": []})
            in_reference = False
        elif _REFERENCE_HEADING.match(line.strip()):
            in_reference = True
        elif blocks and in_reference:
            blocks[-1]["reference"].append(line)
        elif blocks:
            blocks[-1]["question"].append(line)

    parsed = [("\n".join(block["question"]).strip(), "\n".join(block["reference"]).strip()) for block in blocks]
    parsed = [(question, reference) for question, reference in parsed if question]
    if parsed:
        return parsed
    plain = raw.strip()
    if plain and not any(line.lstrip().startswith("#") for line in lines):
        return [(plain, "")]
    return []


def _meta(reply: Reply, elapsed: float) -> str:
    parts: list[str] = []
    if reply.model:
        parts.append(reply.model)
    if reply.stop_reason:
        parts.append("stop: " + reply.stop_reason)
    if reply.in_tokens or reply.out_tokens:
        tokens = f"токены {reply.in_tokens}→{reply.out_tokens}"
        if reply.reasoning_tokens:
            tokens += f" (рассуждение {reply.reasoning_tokens})"
        parts.append(tokens)
    parts.append(f"{elapsed:.1f} с")
    if reply.request_id:
        parts.append("id " + reply.request_id)
    return "  " + " · ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="api_key_probe.py",
        description="Стенд проверки API-ключей One AI API Key и Coarena: чат с историей, вывод с абзацами.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "ключи: ONEAI_KEY и COARENA_KEY в начале файла либо переменные окружения\n"
            "        ONEAI_API_KEY / COARENA_API_KEY\n"
            'примеры: --check · --list-models · --prompt "привет" · --wire anthropic'
        ),
    )
    parser.add_argument(
        "-p",
        "--platform",
        choices=sorted(PLATFORMS),
        default=None,
        help="oneai = One AI API Key, coarena = Coarena (по умолчанию — по заполненному ключу)",
    )
    parser.add_argument(
        "--wire",
        choices=("openai", "anthropic"),
        default="openai",
        help="формат запроса: OpenAI chat/completions или Anthropic messages (по умолчанию openai)",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"model id (по умолчанию {DEFAULT_MODEL})")
    parser.add_argument(
        "--effort",
        choices=EFFORTS,
        default="low",
        help="уровень усилий: reasoning_effort (openai) или бюджет thinking (anthropic); off — поле не слать",
    )
    parser.add_argument("--system", default="", help="системный промпт (роль system); по умолчанию нет")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help=f"лимит ответа; по умолчанию не передаётся (anthropic: {DEFAULT_MAX_TOKENS})",
    )
    parser.add_argument("--no-stream", action="store_true", help="один JSON-ответ вместо SSE-потока")
    parser.add_argument("--timeout", type=float, default=300.0, help="таймаут одного запроса, с (по умолчанию 300)")
    parser.add_argument("--list-models", action="store_true", help="показать модели шлюза и выйти")
    parser.add_argument("--check", action="store_true", help="проверить ключ: список моделей + минимальный запрос")
    parser.add_argument("--prompt", default=None, help="отправить один вопрос и выйти")
    parser.add_argument(
        "--questions",
        default=None,
        metavar="ФАЙЛ",
        help="прогнать вопросы из файла (заголовок ## … , блок ### Эталон) и сохранить ответы",
    )
    parser.add_argument("--out", default="", metavar="КАТАЛОГ", help="куда писать ответы (по умолчанию <файл>-out)")
    parser.add_argument("--save", action="store_true", help="сохранять каждый ответ в файлы по ходу чата")
    parser.add_argument(
        "--reasoning",
        action="store_true",
        help="показывать рассуждение модели в чате (по умолчанию оно скрыто: ответ читается чище)",
    )
    parser.add_argument(
        "--pager",
        choices=("auto", "less", "more", "never"),
        default="auto",
        help="чем листать длинный ответ: auto (less/more), less, more, never — печатать сразу",
    )
    parser.add_argument("--no-pager", action="store_true", help="то же, что --pager never")
    parser.add_argument("--width", type=int, default=None, help="ширина строки (по умолчанию по терминалу)")
    parser.add_argument(
        "--max-context",
        type=int,
        default=0,
        metavar="СИМВОЛОВ",
        help="начинать историю заново, когда она длиннее N символов (0 — не чистить)",
    )
    parser.add_argument("--verbose", action="store_true", help="печатать тело запроса и служебные заголовки")
    parser.add_argument("--no-color", action="store_true", help="без ANSI-цвета")
    return parser.parse_args(argv)


def _settings_from_args(args: argparse.Namespace) -> Settings:
    platform = _resolve_platform(args.platform)
    key = _key_from(platform)
    if not key:
        raise BenchError(
            f"пустой ключ для {PLATFORMS[platform]['label']}: впишите его в переменную "
            f"{'COARENA_KEY' if platform == 'coarena' else 'ONEAI_KEY'} в начале файла "
            f"или задайте {PLATFORMS[platform]['env_var']}"
        )
    prefix = PLATFORMS[platform]["key_prefix"]
    if not key.startswith(prefix):
        print(
            _yellow(f"! ключ не начинается на {prefix} — для {PLATFORMS[platform]['label']} это подозрительно"),
            file=sys.stderr,
        )
    if args.max_tokens is not None and args.max_tokens < 256:
        raise BenchError("--max-tokens меньше 256: ответ обрежется на полуслове")
    if args.questions and args.prompt:
        raise BenchError("--questions и --prompt вместе не имеют смысла: выберите один режим")
    return Settings(
        platform=platform,
        wire=str(args.wire),
        key=key,
        model=str(args.model),
        effort=str(args.effort),
        system=str(args.system),
        max_tokens=args.max_tokens,
        stream=not args.no_stream,
        timeout=float(args.timeout),
        verbose=bool(args.verbose),
        reasoning=bool(args.reasoning),
        save=bool(args.save),
        out=str(args.out),
        pager="never" if args.no_pager else str(args.pager),
        paged=not args.no_pager,
        questions=str(args.questions or ""),
        max_context_chars=int(args.max_context),
        width=int(args.width or 0),
    )


def main(argv: Sequence[str] | None = None) -> int:
    force_utf8_stdio()
    args = _parse_args(argv)
    _set_color(not args.no_color)
    try:
        client = ChatClient(_settings_from_args(args))
    except BenchError as exc:
        print(_red(f"ошибка: {exc}"), file=sys.stderr)
        return 2
    if args.list_models:
        return client.print_models()
    if args.check:
        return client.check()
    if args.questions:
        return client.run_questions()
    if args.prompt is not None:
        return client.ask_once(str(args.prompt))
    return client.repl()


def _stdout_guard(stream: TextIO) -> None:  # pragma: no cover - защита от cp866/cp1251
    """Не дать консоли упасть на символах, которых нет в её кодировке."""
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(errors="replace")
        except (OSError, ValueError):
            return


if __name__ == "__main__":
    _stdout_guard(sys.stdout)
    sys.exit(main())
