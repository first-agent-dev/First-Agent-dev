# Coarena API: рабочий конспект

Документации в одном файле на сайте нет — есть отдельные страницы и справочник
эндпоинтов. Здесь только то, что нужно при работе со стендом: адреса, лимиты,
поля, ошибки. Всё проверено на живых запросах (ноябрь 2026).

## Адреса

| Что | URL |
|---|---|
| OpenAI-формат (`chat/completions`) | `https://coarena.ai/api/v1/chat/completions` |
| Anthropic-формат (`messages`) | `https://coarena.ai/api/v1/messages` |
| Список моделей (без ключа) | `https://coarena.ai/api/v1/models` |
| Заявка/лимиты/ключ | `https://coarena.ai/api/v1/{limits,key,usage,requests}` |
| Оценка ответа | `POST https://coarena.ai/api/v1/feedback` |

Ключ `coa_…`, заголовок `Authorization: Bearer …`; для `messages` — `x-api-key`
плюс `anthropic-version: 2023-06-01`. Оба сразу → 401 `conflicting_credentials`.

## Модель ≠ формат запроса

Coarena — агрегатор: за одним ключом стоят модели Anthropic, OpenAI, Google, xAI
и других. Формат провода выбирается отдельно от модели, и оба формата работают
с любой моделью:

| | `chat/completions` | `messages` |
|---|---|---|
| Модель Claude | работает | работает |
| Модель GPT/Gemini/Grok | работает | работает (тело уходит как есть) |
| Усилие | `reasoning_effort: high` | `thinking.budget_tokens: N` |
| Системный промпт | роль `system` в `messages` | поле `system` |
| Лимит ответа | `max_completion_tokens` | `max_tokens` (обязателен) |
| Рассуждение в стриме | `delta.reasoning_content` | блоки `thinking_delta` |

Практическое следствие: SDK привязывается к формату, а не к вендору модели.
`openai`-клиент с `base_url="https://coarena.ai/api/v1"` отвечает на Claude так
же, как `anthropic`-клиент с тем же адресом.

Что теряется при работе в OpenAI-формате с Claude: явный `budget_tokens`
(усилие задаётся уровнем, бюджет считает шлюз), `output_config`,
`stop_sequences`, tool-блоки Anthropic-вида, а рассуждение приходит
нестандартным полем `reasoning_content`. Всё остальное — модель, лимиты,
контекст, цены — одинаково.

## Лимиты

- 30 запросов в минуту на ключ+аккаунт+модель, 2 параллельных, $5 в сутки.
- 429 приходит с `retry-after`.
- Тело запроса до 8 МиБ; при этом 132 тыс. символов промпта уходят нормально
  (это ~54 тыс. токенов).
- Нестримленный ответ дольше 20 с добивается переводами строк — стрим лучше.

## Выходные токены: главная ловушка

`max_tokens` у моделей — **16384** (см. `/models`). Если лимит в запросе не
указан, шлюз применяет своё умолчание, и ответ молча обрывается:

```
"usage": {"completion_tokens": 8192,
          "completion_tokens_details": {"reasoning_tokens": 7668}},
"finish_reason": "length"
```

Рассуждение (`reasoning_effort`) расходует **тот же** бюджет, что и текст.
При `effort=high` на большом промпте оно занимает почти всё. Поэтому:

- всегда указывайте `max_completion_tokens` (OpenAI-формат) или `max_tokens`
  (Anthropic-формат) с запасом: на high берите **не меньше 16384**, лучше 32–64k;
- `reasoning_effort: high` — это не «больше текста», это «больше думать из того
  же лимита»;
- `finish_reason: "length"` = обрезано, а не «модель закончила».

## Поля запроса

**OpenAI-формат:** `model`, `messages`, `stream`, `stream_options.include_usage`,
`reasoning_effort` (`low|medium|high|xhigh`, у части моделей больше),
`max_completion_tokens`, `tools`, `response_format`. Неподдержанные параметры
шлюз выбрасывает и перечисляет в заголовке `x-coarena-dropped-params`.
Не работают: `n > 1`, logprobs, аудио → 400.

**Anthropic-формат:** `model`, `max_tokens` (обязателен), `messages`, `system`,
`thinking: {"type": "enabled", "budget_tokens": N}` — N **меньше** `max_tokens`,
`output_config`, `stop_sequences`. Тело уходит почти дословно.

## Заголовки ответа

`x-request-id`, `x-coarena-request-id`, `x-coarena-model`, `x-ratelimit-*`,
`x-coarena-dropped-params`. Любой id годится для `/feedback`; он же печатается
в мета-строке стенда как `id chatcmpl-…`.

## Ошибки

| Код | `code` | Что значит |
|---|---|---|
| 400 | `invalid_request`, `unsupported_parameter`, `context_length_exceeded`, `assistant_prefill_unsupported`, `content_filtered`, `request_too_large` | правится телом запроса |
| 401 | `invalid_api_key`, `api_key_revoked` | ключ |
| 403 | `insufficient_scope`, `account_blocked`, `model_api_terms_required` | условия использования не приняты |
| 404 | `model_not_found` | id модели — смотреть `/models` |
| 429 | `rate_limit_exceeded`, `concurrency_limit_exceeded`, `insufficient_quota` | ждать `retry-after` |
| 502/503/504 | `upstream_error`, capacity | повторить |
| 529 | `overloaded_error` | повторить |

## Приватность

Все промпты, ответы и рассуждения сохраняются и могут попадать в датасеты.
Секреты и персональные данные туда не отправлять.
