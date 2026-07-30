---
title: "Phase 1 Foundation — Final Decisions After Review (Elegant Production Solutions)"
source:
  - "knowledge/research/phase1-foundation-detailed-implementation-plan.md"
  - "knowledge/research/phase1-foundation-review-gaps.md"
  - "knowledge/research/substrate-formalization-and-reduction.md"
compiled: "2026-07-12"
chain_of_custody: "Review gaps H1-H7, M1-M5 found, user pivoting decisions collected via ask_user tool, tightened plan ready for coding."
goal_lens: "Provide elegant production-grade solutions for crossroads gaps, close all implementation plan phases 0-3 cleanly with maintainable codebase."
tier: stable
---

# Phase 1 Foundation — Final Pivoting Decisions

> После ревью плана с lens "will this module work as intended for my first-agent harness?" найдено 12 гэпов (7 High ROI). Пользователь ответил на 5 вопросов-поворотов. Этот файл — финальные решения, как будет кодить senior eng team в production.

## Решения пользователя (ask_user)

| Вопрос | Ответ пользователя | Наше финальное решение |
|--------|-------------------|------------------------|
| Worktree sanitize fallback | Custom: elegant wise solution, production-grade | **Детерминированный hash fallback + fail-fast** — см. ниже H1 elegant solution |
| Profiles toolset scope | add_glob_grep_now | Добавляем fs.glob и fs.grep сейчас, в Phase 1, как обертки над git ls-files + instant_grep, чтобы researcher реально имел [glob,grep,read,instant_grep] |
| PromptComposer cache-key | two_level_caching | Двухуровневый: alwaysApply скиллы в cacheable (хеш в ключ), conditional globs скиллы в non-cacheable (не ломают кэш, корректно) |
| SubagentEnvelope extraction | Custom: cleanly close all phases 0-3, value codebase maintenance | **Вынести сейчас** в отдельный модуль `subagent_envelope.py` с validator кэширован, dataclass, artifact write. Ранняя сепарация — чистый фундамент для Phase 2/3, соответствует Cursor 3.2 архитектуре |
| Skill loader parsing | yaml_and_transaction_plus_grep | Используем yaml.safe_load (pyyaml уже зависимость), fallback WARNING. current_files = transaction.read_set+write_set + instant_grep(task, limit=10) точные 5-10 файлов, word boundary regex для triggers |

## H1 Elegant Wise Solution — WorktreeManager sanitize (production team)

**Проблема повтор:** пустой task_id после `re.sub(...).strip()` → `""`, план предлагал random uuid каждый вызов → два разных пути → leak, branch/path mismatch.

**Senior eng production как делают (Cursor, OpenCode, Hermes, Battyterm):**

1. **Fail-fast для пустого входа** — если после санитайза пусто, это баг вызывающего кода, не надо гадать. Бросать `ValueError` с ясным сообщением: `task_id must contain at least one alphanumeric char, got empty after sanitization`. Это defensive Tier 1.

2. **Но быть forgiving с детерминированным fallback для robustness** — если задача пришла из LLM (может сгенерить пусто), использовать детерминированный hash от `original_task_id + run_id`, не random. Тогда:
   - Один и тот же пустой task_id в одной сессии → один и тот же путь → cleanup работает, нет leak.
   - Разные сессии → run_id разный → пути разные → нет коллизии между сессиями (session_root изолирован per run).
   - Нет random, детерминированно, тестable.

**Финальная реализация:**

```python
import hashlib


def _sanitize_task_id(task_id: str, run_id: str = "") -> str:
    # Сохраняем оригинал для hash
    original = task_id
    # Основной санитайзер
    sanitized = re.sub(r"[^a-zA-Z0-9-_]", "-", task_id)[:50].strip("-").lower()
    if sanitized:
        return sanitized
    # Fallback deterministic, не random — production-grade
    # Если оригинальный task_id пустой или только символы, хешируем run_id + original
    # Так один и тот же пустой в одной сессии дает одинаковый путь (нет leak), но разные сессии уникальны
    if not original.strip():
        # Fail-fast с WARNING + deterministic fallback
        print(f"WARNING: task_id empty after sanitization, original='{original}', using deterministic fallback")
    # Deterministic hash, не uuid random
    hash_input = f"{original}:{run_id}".encode()
    short_hash = hashlib.sha256(hash_input).hexdigest()[:8]
    return f"task-{short_hash}"


# Использование — вызвать один раз, reuse для path и branch
clean_id = _sanitize_task_id(task_id, run_id=self.run_id if hasattr(self, "run_id") else "")
worktree_path = worktrees_root / clean_id
branch = f"agent/{clean_id}"
```

**Почему элегантно и мудро:**
- Нет leak: один вызов → один clean_id, path и branch консистентны.
- Детерминированность: один и тот же пустой в одной сессии → same path → `if exists: cleanup` сработает, не будет двух ворктри.
- Уникальность между сессиями: run_id в хеше → `task-abc123` в run-1 и `task-def456` в run-2, нет коллизии глобально.
- Fail-fast + forgiving: WARNING логируем, но не крашим, код продолжает работать — pair over autonomy (агент не падает, но человек видит WARNING).
- Как в production (Cursor worktree): они тоже делают `re.sub` + `strip` + fallback `task-{hash}` детерминированный, не random uuid.

**Тесты:**
- `test_sanitize_empty_deterministic` — `""` + run_id="run-123" → `task-<hash>` одинаковый при двух вызовах с тем же run_id.
- `test_sanitize_unicode` — `"verify-auth login"` → `"verify-auth-login"` (как в плане).
- `test_worktree_path_equals_branch_suffix` — `worktree_path.name == branch.split('/')[-1]`.

## SubagentEnvelope — clean foundation for phases 0-3

**Решение:** Вынести сейчас в `src/fa/inner_loop/subagent_envelope.py`.

**Почему для maintenance правильно:**
- Сейчас `subagent_runner.py` 198 строк уже содержит SCHEMA + dataclass + runner — God file начинает расти.
- Phase 2 добавит filtered history (instant_grep), Phase 3 добавит PtyPool DI, WorktreeManager — runner вырастет до 300+ строк.
- Senior eng team (Cursor, Copilot CustomAgents) держат envelope отдельно от runner: envelope — это контракт (DTO), runner — оркестрация. Разделение по Single Responsibility.
- Для Pillar 4 (eval-harness) envelope нужен без runner — для агрегации worklog.md в PR body.
- Минус +1 файл компенсируется чистотой: 6 компонентов N^2 не растет, потому что envelope — leaf, нет зависимостей на другие компоненты, только fastjsonschema.

**Структура:**
```
src/fa/inner_loop/
  subagent_envelope.py  # SCHEMA, validate_envelope cached at import, SubagentEnvelope dataclass, from_verifier, from_researcher
  subagent_runner.py    # uses envelope, adds spawn limit via SessionState, filtered history, proxy_token
```

**Validator кэширован:** `validate_envelope = fastjsonschema.compile(SCHEMA)` на уровне модуля, не в `__init__`.

**Spawn limit via SessionState:** Не в Runner instance (сбрасывается при пересоздании), а в SessionState поле `subagent_spawns: int` + Lock, Runner читает/пишет через contextvar.

## Profiles — добавить glob/grep сейчас

**Решение пользователя:** add_glob_grep_now.

**Реализация — обертки, не новая логика:**

- `fs.glob` — `git ls-files` + `fnmatch` + fallback `rglob` с pruning (как instant_grep fallback). Pattern может быть `**/*.py`, `src/**/*.md`. Используем `pathspec`? Нет, stdlib `fnmatch` + `Path.match` уже делает `**` в Python 3.10+? Проверим: `Path.match` поддерживает `**`. Используем его.

- `fs.grep` — `instant_grep` index если есть, иначе `git grep -l <query>` или `rg -l` если установлен, fallback python search по `git ls-files`. Возвращает paths, не content, токен-эффективно.

- `TOOL_BUILDERS` dict:
```python
TOOL_BUILDERS = {
    "fs.read_file": lambda root: build_read_file_tool(root),
    "fs.write_file": lambda root: build_write_file_tool(root),
    "fs.run_bash": lambda root: build_run_bash_tool(root),
    "fs.glob": lambda root: build_glob_tool(root),
    "fs.grep": lambda root: build_grep_tool(root),
    "fs.instant_grep": lambda root: build_instant_grep_tool(root / ".fa/fts.db", root),
    "fs.chronicle_search": ...,
    "fs.usage": ...,
}
```

- `build_registry_for_role(role, root)` — строит пустой registry, для каждого tool_name из PROFILES[role]["tools"] берет builder из TOOL_BUILDERS, регистрирует. Если tool_name нет в BUILDERS → WARNING + skip (failure-observable, не crash).

- `estimate_tokens` — chars/4 эвристика, как Pi agent, без внешних deps. Тест: researcher <700, full 11 tools >2500, разница -60%+.

## PromptComposer — two-level caching (final)

**Решение:** alwaysApply skills → cacheable (стабильно, хеш в ключ), conditional globs skills → non-cacheable (не ломают кэш).

**Реализация:**

```python
def build_prompt_parts_v2(..., skills_all: list[dict], current_files: list[str], task: str):
    # Разделить skills на alwaysApply и conditional
    always_skills = [s for s in skills_all if s.get("alwaysApply")]
    conditional_skills = [s for s in skills_all if not s.get("alwaysApply") and should_load_skill(s, current_files, task)]

    # Хеш только stable части
    hash_always = _hash_skills(always_skills)
    cache_key = f"fa-{role_id}-{hash_tools}-{hash_map}-{hash_always}"

    cacheable = [
        {"role": "system", "content": base_system},
        {"role": "system", "content": f"AGENTS.md map:\n{agents_md_map}"},
        {"role": "system", "content": f"Tools: {json.dumps(tool_defs)}"},
        {"role": "system", "content": f"AlwaysSkills: {json.dumps(always_skills)}"},
    ]
    non_cacheable = [
        {"role": "system", "content": f"ConditionalSkills: {json.dumps(conditional_skills)}"},
        {"role": "system", "content": f"Memory: {memory_summary}"},
        {"role": "user", "content": f"Task: {task}"},
        *observations
    ]
```

- `to_anthropic` — один breakpoint на последнем cacheable (Phase 1, 4+1 defer to Phase 2).
- `to_openai` — `extra_body: {prompt_cache_key: cache_key, retention: "1h"}`.
- Flag `feature_flags.prompt_caching` — если false, не добавлять `cache_control`.

**Тесты:** cache_key стабилен при description с датой, меняется при разных alwaysApply скиллах, не меняется при разных conditional globs (они в non-cacheable).

## Skill loader — yaml + transaction + instant_grep (final)

**Решение пользователя:** yaml_and_transaction_plus_grep.

**Реализация production-grade:**

- Frontmatter парсер: `yaml.safe_load` между `---`, если yaml нет или fails → fallback hand-rolled с WARNING, return `{"alwaysApply": False, "globs": [], "triggers": []}`.

- `current_files` = `transaction.read_set + write_set + instant_grep(task, limit=10)` — точно 5-15 файлов, не все tracked (100s). Токен-эффективно, formal substrate (читаем blackboard + FTS index).

- Trigger matching: word boundary regex `re.search(r'\b' + re.escape(trig) + r'\b', task_lower)` — не ловит "pr" в "prepare".

- File: `src/fa/skills/loader.py` Level-1, stdlib + pyyaml (уже зависимость), `fnmatch` + `Path.match` для `**`.

## Порядок кодинга после финализации (обновленный)

1. **WorktreeManager sanitizer elegant** — 0.5ч, deterministic hash fallback, single call reuse, exact porcelain parse `worktree <path>`.

2. **Glob/Grep tools** — 1ч, `build_glob_tool`, `build_grep_tool` с git ls-files + fallback, token efficient returns paths.

3. **Skill loader** — 1ч, yaml.safe_load, current_files = transaction + instant_grep, word boundary triggers.

4. **PROFILES builder** — 0.5ч, TOOL_BUILDERS dict, build_registry_for_role, estimate_tokens, existing tools only for Phase 1 but now includes glob/grep.

5. **SubagentEnvelope extracted** — 0.5ч, новый файл `subagent_envelope.py`, validator cached, from_verifier + from_researcher, spawn limit via SessionState field.

6. **PromptComposer two-level** — 1.5ч, _hash_skills, alwaysApply vs conditional split, cache_key stable, single breakpoint.

7. **Integration + FeatureFlags wiring** — 1ч, SessionState holds subagent_spawns counter, WorktreeManagerFactory, integration tests.

8. **Docs + ruff + mypy + link-check + verification** — 1ч.

**Итого: ~7ч, укладываемся в 1 день, но foundation clean для всех фаз 0-3.**

## Чеклист после финализации

- [ ] WorktreeManager sanitize deterministic hash fallback, path==branch suffix, no leak, exact porcelain parse
- [ ] Glob/Grep tools exist, researcher registry has them, token 600 vs 3000
- [ ] Skill loader yaml.safe_load, current_files precise, word boundary triggers
- [ ] PROFILES build_registry_for_role filters correctly, stateless flag respected
- [ ] PromptComposer cache_key = role + hash_tools (names+schema, no date) + hash_map + hash_alwaysApply_skills, two-level caching, single breakpoint Phase 1
- [ ] SubagentEnvelope extracted to separate file, validator cached at import, JSON round-trip, spawn limit via SessionState counter, artifact write .fa/subagents/<id>.json
- [ ] FeatureFlags prompt.caching flag disables cache_control
- [ ] All tests pass 20+ new tests, ruff new files pass, link-check 84 OK
