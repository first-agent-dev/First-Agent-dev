---
title: "Phase 1 Foundation — Detailed Implementation Plan (WorktreeManager, Profiles, PromptComposer, SubagentEnvelope, Skill Globs)"
source:
  - "knowledge/research/adr-13-14-implementation-plan-2026-07-11-v3-reduced.md"
  - "knowledge/research/substrate-formalization-and-reduction.md"
  - "knowledge/project-overview.md §1.2.6 Substrate Formality, §1.2.7 Pair over Autonomy"
  - "src/fa/workspace/worktree_manager.py"
  - "src/fa/inner_loop/profiles.py"
  - "src/fa/inner_loop/prompt_composer.py"
  - "src/fa/inner_loop/subagent_runner.py"
  - "src/fa/feature_flags.py"
  - "src/fa/inner_loop/transaction.py"
  - "src/fa/inner_loop/state.py"
compiled: "2026-07-12"
chain_of_custody: "Self-sufficient for Phase 1 implementation. Builds on Stage 0 and 0.5 prod-ready code (blackboard, telemetry, transaction, feature_flags, contextvar DI) verified 20 tests pass, ruff new files pass, markdown links 84 OK."
goal_lens: "Land WorktreeManager defensive Tier 1, Profiles dynamic toolset 600 vs 3000 tokens (-60%), PromptComposer cache-key per role stable hash including skills hash, SubagentEnvelope JSON full schema validated, Skill globs alwaysApply false, integrated into SessionState via DI, keeping main as pair partner, 1 cheap stateless subagent, measurable Pillar 3 KPI."
tier: stable
---

# Phase 1 Foundation — Детальный план разработки

> **Status:** active, self-sufficient for coding. Используй этот файл один, плюс `adr-13-14-implementation-plan-2026-07-11-v3-reduced.md` §Phase 1.
> **Принцип:** Topology complexity — симптом отсутствующего формального субстрата (Paper 2 §4.4). Сначала формализуем субстрат (Blackboard + Transaction уже готовы), потом добавляем простые абстракции. Main — pair partner, subagent — дешевый детерминированный кусочек пазла, clean slate ~1k.

## §0 Decision Briefing — что делаем на Phase 1 и зачем

**Проблема:** После Stage 0.5 у нас есть Blackboard, Telemetry, Transaction, FeatureFlags, но:
- WorktreeManager есть, но санитайзер не единообразный, пустой task_id дает коллизию `task` vs `agent/task-<uuid>`, нет теста на `main` vs `master` fallback.
- PROFILES есть как словарь, но нет функции `build_registry_for_role()` которая реально режет tools до 600 токенов и меряет токены.
- PromptComposer есть v2, но cache-key = role + hash_tools + hash_map, без hash скиллов. Описание с датой может попасть в хэш → кэш ломается каждый день.
- SubagentEnvelope есть в `subagent_runner.py`, но валидатор компилируется на уровне модуля — ок, но нет отдельного модуля, нет теста JSON round-trip, нет лимита 1 subagent через RuntimeLimits.
- Skill globs — фронтомatter `globs, alwaysApply` упомянут в PROFILES, но нет лоадера `should_load_skill()` который проверяет globs против текущих файлов.

**Цель Phase 1:** Приземлить 6 абстракций (WorktreeManager, Profiles, PromptComposer, SubagentEnvelope, FeatureFlags, Transaction уже готова, Skill globs) так, чтобы они были:
- **Defensive Tier 1** — проверки до действия, fail-fast, не silent fallback (Claude bug #55708 parent HEAD switched).
- **Токен-эффективны** — researcher 600 vs full 3000, измерено через chars/4 эвристику.
- **DI через SessionState** — нет глобального синглтона, shared Server инжектируется.
- **Failure-observable** — WARNING, не `except: pass`.

**Что НЕ делаем в Phase 1:** параллельные 2-3 субагента, Remote Runtime Extraction FastAPI, ThreadPool batching (это Phase 2), PtyPool in-process (Phase 3). Держим 1 субагента sequential single-shot — 100% стабильно, 0 scope creep, pair over autonomy.

## §1 Текущее состояние инвентарь (что уже есть)

| Модуль | Файл | Состояние | Гэпы для prod |
|--------|------|-----------|---------------|
| **WorktreeManager** | `src/fa/workspace/worktree_manager.py` | SharedDir + Isolated с `_sanitize_branch`, defensive asserts path exists/is_dir + worktree list contains, branch already checked out fail-fast, CWD lock, cleanup assert not exists + prune, main/master/HEAD fallback | Санитайзер дублируется (один для path `safe_task_id`, другой для branch `_sanitize_branch`), пустой task_id → `task` vs `task-<uuid>` коллизия, нет единого `_sanitize_task_id()` helper |
| **PROFILES** | `src/fa/inner_loop/profiles.py` | Словарь 5 ролей: researcher [glob,grep,read,instant_grep] 600, verifier [bash] 200, code-reviewer [read,grep], implementer full, planner read-only | Нет функции `build_registry_for_role`, нет подсчета токенов, нет динамической фильтрации по `stateless` |
| **PromptComposer** | `src/fa/inner_loop/prompt_composer.py` | `PromptParts(cacheable, non_cacheable)`, `_stable_hash`, `_hash_tool_defs_stable(names+input_schema, exclude description)`, `cache_key = f"fa-{role_id}-{hash_tools}-{hash_map}"`, `to_anthropic` с `cache_control ephemeral`, `to_openai` с `prompt_cache_key` | Нет hash скиллов, нет гарантии что description с датой исключен (сейчас исключен, но надо тест), нет `to_anthropic` с 4+1 брейкпоинтами, нет проверки что cacheable >1024 chars для Anthropic min |
| **SubagentEnvelope** | `src/fa/inner_loop/subagent_runner.py` | `SUBAGENT_ENVELOPE_SCHEMA` Goal, Verification, Risks, fastjsonschema compile cached, `SubagentEnvelope.from_verifier`, artifact write `.fa/subagents/<id>.json`, proxy_token foundation | Нет отдельного модуля `subagent_envelope.py`, нет JSON round-trip теста, нет проверки лимита `max_subagent_spawns_per_session=3` через RuntimeLimits, нет filtered history (task + relevant files from instant_grep, not full parent 124 steps) |
| **FeatureFlags** | `src/fa/feature_flags.py` | Frozen dataclass, `load_feature_flags` flat + nested, defaults anchored, warnings | Уже prod-ready, надо интегрировать prompt.caching флаг в PromptComposer |
| **Transaction** | `src/fa/inner_loop/transaction.py` | Dataclass id, started_at, _read_set/_write_set set + Lock thread-safe, add_read/add_write | Уже prod-ready, используется в SessionState |
| **Skill globs** | фронтомatter в PROFILES + `knowledge/skills/*/SKILL.md` | Поля `globs`, `alwaysApply` упоминаются, но нет лоадера | Нет `skill_loader.py` с `should_load_skill(skill_path, current_files, task_text) -> bool` |

## §2 Детальный дизайн по модулям — как буду разрабатывать

### Модуль 1: WorktreeManager — Defensive Tier 1, санитайзер единый

**Текущий код проблемы:**
```python
# Сейчас два места санитайзят по-разному:
safe_task_id = re.sub(r'[^a-zA-Z0-9-_]', '-', task_id)[:50].strip('-').lower() or "task"
branch = self._sanitize_branch(task_id)  # тоже re.sub но + "agent/" prefix + uuid fallback
# Если task_id = "" после санитайза, safe_task_id = "task", branch = "agent/task-<uuid>" -> коллизия если два пустых task_id
```

**План разработки, шаги верифицируемые:**

1. **Единый helper `_sanitize_task_id(task_id) -> str`:**
   - `sanitized = re.sub(r'[^a-zA-Z0-9-_]', '-', task_id)[:50].strip('-').lower()`
   - Если пусто после strip → `f"task-{uuid4 hex[:8]}"` — всегда уникальный, избегаем коллизии `task`.
   - Покрыть тестом: `"" → task-<hex>`, `"verify-auth login" → "verify-auth-login"`, `"HELLO!!!" → "hello"`.

2. **Использовать helper везде:**
   - `worktree_path = worktrees_root / _sanitize_task_id(task_id)`
   - `branch = f"agent/{_sanitize_task_id(task_id)}"` — теперь path и ветка консистентны, оба уникальны.

3. **Defensive checks оставить, усилить:**
   - `assert session_root.exists()` и `is_dir()` — уже есть.
   - После `git worktree add`: `assert path.exists()`, `assert path.is_dir()`, `assert str(path) in git worktree list --porcelain`.
   - Перед add: `_is_branch_checked_out_elsewhere(branch)` → fail-fast с деталями `git worktree list` (исправлено, есть).
   - `_resolve_base_branch` fallback `main` → `master` → `HEAD` — уже есть, тест `test_worktree_defensive_exists` проверяет.
   - CWD lock: в `run_stateless` assert `cwd == worktree_path` или `cwd.is_relative_to(worktree_path)`.

4. **SharedDir vs Isolated:**
   - `SharedDirWorktreeManager.create() -> session_root` — 100% стабильно, 0 кода, для v0.1 1 субагент лимит.
   - `IsolatedWorktreeManager` — future, но уже тестируем в `test_isolated_manager_branch_already_checked_out`.
   - Фабрика `WorktreeManagerFactory.from_flags(flags, session_root, repo_root)` — по `feature_flags.worktree_mode` возвращает нужный, DI через SessionState.

5. **Тесты:**
   - `test_sanitize_empty -> task-<hex>` (новый)
   - `test_sanitize_unicode -> verify-auth-login` (существующий `test_worktree_defensive`)
   - `test_shared_dir_returns_root`
   - `test_isolated_branch_already_checked_out` — уже есть.

**ROI:** Переписать только санитайзер helper (10 строк), остальное оставить. Не переписывать весь модуль — высокий ROI только на санитайзер.

**Интерфейс итоговый:**
```python
class WorktreeManager(ABC):
    def create_subagent_workspace(self, task_id: str, base_branch: str = "main") -> Path: ...
    def cleanup(self, path: Path) -> None: ...

def _sanitize_task_id(task_id: str) -> str:  # единый
    ...

class SharedDirWorktreeManager(WorktreeManager): ...
class IsolatedWorktreeManager(WorktreeManager): ...
```

### Модуль 2: PROFILES — динамический toolset, токен-подсчет 600 vs 3000

**Текущий код:** Словарь, нет функций.

**План:**

1. **Добавить `PROFILES` типизацию:**
```python
@dataclass(frozen=True)
class RoleProfile:
    description: str
    tools: list[str]
    max_tokens: int
    stateless: bool
    globs: list[str] = field(default_factory=list)
    alwaysApply: bool = False
```

2. **Функция `build_registry_for_role(role: str, base_registry: ToolRegistry) -> ToolRegistry`:**
   - Берет `PROFILES[role]["tools"]` → фильтрует из глобального реестра.
   - Возвращает новый `ToolRegistry` только с этими tools.
   - Пример:
```python
global_reg = build_baseline_registry(root)  # 11 tools ~3000 tokens
researcher_reg = build_registry_for_role("researcher", global_reg)
# researcher_reg.names() = ["fs.glob", "fs.grep", "fs.read_file", "fs.instant_grep"] -> ~600 tokens
```

3. **Подсчет токенов — эвристика chars/4 (как Pi agent, Kon):**
```python
def estimate_tokens(registry: ToolRegistry) -> int:
    total_chars = sum(len(json.dumps(t.input_schema)) + len(t.description) for t in registry.all_specs())
    return total_chars // 4  # как в Pi agent
```
   - Тест: `researcher 600 vs implementer 3000`, проверить `estimate_tokens(researcher_reg) < 700`.

4. **Dynamic flag `stateless`:** в `SubagentRunner` если `profile.stateless: True` → использовать `subprocess.run`, не PtyPool.

5. **Тесты:**
   - `test_profiles_researcher_600_vs_full_3000` — уже есть частично в `test_prompt_caching_per_role.py`, расширить.
   - `test_build_registry_for_role_filters` — проверить что `researcher` не имеет `fs.write_file`.

**ROI:** Не переписывать модуль, добавить 2 функции и dataclass — 50 строк, высокий ROI токен-экономии -60%.

### Модуль 3: PromptComposer — cache-key стабильный + hash скиллов

**Текущий код:**
```python
cache_key = f"fa-{role_id}-{hash_tools}-{hash_map}"
# hash_tools = hash(names+input_schema) — правильно, без description с датой
# hash_map = hash(agents_md_map)
```

**Гэпы:** нет hash скиллов, нет гарантии что description исключен, нет `alwaysApply` проверки.

**План:**

1. **Расширить `build_prompt_parts_v2` сигнатуру:**
```python
def build_prompt_parts_v2(
    base_system: str,
    agents_md_map: str,
    tool_defs: list[dict],
    role_id: str,
    skills: list[dict] = None,  # NEW: [{"name": "pr-creation", "globs": [...], "alwaysApply": false}]
    memory_summary: str = "",
    task: str = "",
    observations: list[dict] = None,
) -> tuple[PromptParts, str]:
```

2. **Hash скиллов:**
```python
def _hash_skills(skills: list[dict]) -> str:
    stable = [{"name": s["name"], "globs": s.get("globs", []), "alwaysApply": s.get("alwaysApply", False)} for s in sorted(skills, key=lambda x: x["name"])]
    return _stable_hash(stable)
```
   - Теперь `cache_key = f"fa-{role_id}-{hash_tools}-{hash_map}-{hash_skills}"`
   - Исключаем `description` с датой — уже сделано `_hash_tool_defs_stable` берет только `name` + `input_schema`, не `description`.

3. **Split cacheable vs non-cacheable:**
   - Cacheable: BASE system (роль), AGENTS.md map, tool defs для роли (стабильно), skills list (стабильно).
   - Non-cacheable: task, memory_summary, observations (меняются каждый ход).
   - Anthropic: `cache_control: {"type": "ephemeral"}` на последнем cacheable сообщении, 4 брейкпоинта макс, min 1024 токена. Проверяем что cacheable часть >1024.
   - OpenAI: `extra_body: {"prompt_cache_key": cache_key, "prompt_cache_retention": "1h"}` via LiteLLM.

4. **Интеграция с FeatureFlags:**
```python
flags = load_feature_flags_from_path()
if not flags.prompt_caching:
    # не добавляем cache_control, возвращаем обычный список сообщений
```

5. **Тесты:**
   - `test_cache_key_per_role_differs` — уже есть, расширить проверкой что hash не меняется если description имеет дату `2026-07-12` (добавляем description с датой в tool_defs, хэш должен остаться тем же).
   - `test_cache_key_includes_skills_hash` — одинаковые role+tools но разные skills → cache_key разный.
   - `test_cacheable_split_anthropic_has_cache_control` — проверить что последний cacheable имеет `cache_control`.

**ROI:** Переписать только `_hash_skills` + расширить сигнатуру, не переписывать весь модуль. 30 строк.

### Модуль 4: SubagentEnvelope — JSON full schema, валидатор кэширован, artifact write

**Текущий код:** в `subagent_runner.py`, schema есть, `validate_envelope = compile()` кэширован на уровне модуля, `SubagentEnvelope.from_verifier`, artifact write `.fa/subagents/<id>.json`.

**Гэпы:** нет отдельного модуля, нет round-trip теста, нет лимита через RuntimeLimits.

**План:**

1. **Вынести в отдельный файл `src/fa/inner_loop/subagent_envelope.py`:**
   - `SUBAGENT_ENVELOPE_SCHEMA` — полная схема Goal, Verification, Risks, token_usage, duration_ms, next_action (уже есть).
   - `validate_envelope = fastjsonschema.compile(SCHEMA)` — кэширован при импорте, не компилировать каждый раз (экономия токенов + времени).
   - `SubagentEnvelope` dataclass с `to_json()`, `from_verifier()`, `from_researcher()` (новый для structured websearch use case).

2. **Добавить два cheap детерминированных use case (из философии):**
   - `researcher` — структурированный websearch: вход query, выход JSON `{urls, snippets, summary}` `<500 токенов промпт`.
   - `verifier` — простая функция: вход spec, выход `{file_path, test_result}`.
   - Промпты минимальные, не full BASE+map: `<500 токенов`, clean slate ~1k, restricted tools.

3. **Лимит через RuntimeLimits:**
```python
class SubagentRunner:
    def __init__(self, ..., limits: RuntimeLimits = None):
        self.limits = limits or RuntimeLimits.anchored_defaults()
        self._spawn_count = 0

    def run_stateless(...):
        if self._spawn_count >= self.limits.max_subagent_spawns_per_session:
            raise RuntimeError(f"Subagent spawn limit {self.limits.max_subagent_spawns_per_session} reached")
        self._spawn_count += 1
        ...
```

4. **Artifact write + filtered history:**
   - History для субагента: не full parent 124 steps, а `task + relevant files from instant_grep` (5-10 файлов).
   - Write artifact `.fa/subagents/<task_id>.json` после успешной валидации, для worklog.md.

5. **Тесты:**
   - `test_envelope_valid_json_roundtrip` — создать, `to_json()`, `json.loads()`, `validate_envelope` passes.
   - `test_envelope_invalid_fails` — без required field → `JsonSchemaValueException`.
   - `test_runner_respects_spawn_limit` — 4й вызов при лимите 3 → raises.
   - `test_envelope_artifact_written` — проверить файл `.fa/subagents/<id>.json` существует.

**ROI:** Вынести 50 строк в новый файл, добавить 2 метода, не переписывать весь runner.

### Модуль 5: FeatureFlags + RuntimeLimits — уже prod-ready, проверить интеграцию

**Текущий:** `feature_flags.py` prod-ready, `runtime_limits.py` extended `max_subagent_spawns_per_session=3`.

**Что доделать:**
- В `SessionState` уже интегрирован, но надо проверить что `prompt.caching` флаг реально используется в `prompt_composer.py`.
- Добавить в `~/.fa/config.yaml` пример:
```yaml
feature_flags:
  blackboard.enabled: true
  telemetry.enabled: true
  tool_batching.enabled: false  # Phase 2 включает
  runtime.mode: in_process
  pty_pool.max_size: 2
  worktree.mode: shared
  prompt.caching: true
  prompt.cache_key_per_role: true
  offload_threshold: 8000
  max_subagent_spawns_per_session: 3
runtime_limits:
  max_iterations: 6
  max_subagent_spawns_per_session: 3
```

**Тест:** `load_feature_flags` flat + nested уже есть.

### Модуль 6: Transaction — уже prod-ready

**Текущий:** `transaction.py` с Lock, `add_read/add_write`, уже интегрирован в `state.py` и `read_file/write_file` через `contextvar`.

**Что доделать:** только верификация:
- `state.transaction.read_set` накапливается во время выполнения (не только декларируется upfront) — уже да, via `record_tool_call`.
- Добавить тест `test_transaction_accumulates_during_execution` в `test_tool_batching.py`? Already есть grouping test.

### Модуль 7: Skill globs — лоадер `should_load_skill`

**Текущий:** фронтомatter `globs`, `alwaysApply` в скиллах есть (например `skill-writing` пока без globs, но PROFILES имеет `globs`), но нет лоадера.

**План разработки — самый важный для токен-экономии:**

1. **Парсер frontmatter SKILL.md:**
   - Файлы `knowledge/skills/*/SKILL.md` имеют YAML frontmatter между `---`.
   - Использовать `tomllib` или простой парсер как в `config.py` — не тащить `pyyaml` (Level-0 TCB stdlib-only). Можно использовать `yaml` если есть, но лучше `fa._yaml_subset` или `python-frontmatter`? Держим stdlib: парсим между `---` строками, ищем `globs:` список.
   - Пример фронтомatter:
```yaml
---
name: skill-writing
globs:
  - "src/fa/inner_loop/tools/*.py"
  - "knowledge/skills/**/*.md"
alwaysApply: false
triggers:
  - "writing a new skill"
---
```

2. **Функция `should_load_skill(skill_path: Path, current_files: list[str], task_text: str) -> bool`:**
```python
def should_load_skill(skill_path: Path, current_files: list[str], task_text: str) -> bool:
    frontmatter = parse_frontmatter(skill_path)
    if frontmatter.get("alwaysApply") is True:
        return True
    globs = frontmatter.get("globs", [])
    if globs:
        for pattern in globs:
            # использовать fnmatch или Path.match, с поддержкой ** 
            for f in current_files:
                if fnmatch.fnmatch(f, pattern) or Path(f).match(pattern):
                    return True
    triggers = frontmatter.get("triggers", [])
    # trigger verb match: если слово из triggers есть в task_text
    task_lower = task_text.lower()
    for trig in triggers:
        if trig.lower() in task_lower:
            return True
    return False
```

3. **Интеграция в PromptComposer:**
   - Перед сборкой `cacheable` части, вызвать `should_load_skill` для каждого скилла в `knowledge/skills/`, собрать список тех что надо загрузить.
   - Только их content добавляется в cacheable, а не все 4 скилла — экономия токенов.
   - Hash скиллов включает только загруженные скиллы, а не все.

4. **Тесты:**
   - `test_skill_globs_match` — `globs: ["src/**/*.py"]`, `current_files=["src/fa/inner_loop/tools/write_file.py"]` → True
   - `test_skill_alwaysApply_false_no_match -> False`
   - `test_skill_trigger_verb_match` — task "writing a new skill" + trigger "writing a new skill" → True

5. **Файл новый:** `src/fa/skills/loader.py` (Level-1, stdlib only, no external deps, uses `fnmatch` + `pathlib`).

**ROI:** Новый модуль 80 строк, но экономит тысячи токенов, т.к. не грузит все скиллы каждый раз. Обязателен для prod.

## §3 Порядок разработки — зависимости и время

**Порядок по ROI + зависимости, всего 1 день (8 часов):**

1. **WorktreeManager санитайзер единый** — 0.5 часа, нет зависимостей, изолирован. Верификация: pytest `test_worktree_defensive` + новый `test_sanitize_empty`.

2. **PROFILES dynamic registry** — 1 час, зависит от ToolRegistry (уже есть). Верификация: `estimate_tokens` 600 vs 3000, `build_registry_for_role`.

3. **Skill globs loader** — 1 час, зависит от filesystem, fnmatch, frontmatter parser. Верификация: 3 теста globs/triggers/alwaysApply.

4. **PromptComposer + skills hash** — 1.5 часа, зависит от PROFILES (tool_defs per role) и skill loader (skills list). Верификация: cache-key отличается per role, включает skills hash, exclude date.

5. **SubagentEnvelope вынос + spawn limit** — 1 час, зависит от WorktreeManager, PROFILES, RuntimeLimits. Верификация: JSON round-trip, spawn limit, artifact write.

6. **FeatureFlags интеграция в PromptComposer** — 0.5 часа, уже done, проверить флаг `prompt.caching` реально выключает cache_control.

7. **Интеграционные тесты + верификация** — 1.5 часа, собрать всё в SessionState, запустить loop с 3 tool calls, проверить transaction read_set, blackboard conflict, telemetry, artifact offload, skill loading.

8. **Документация + DIGEST + exploration_log + ruff + mypy + markdown-link-check** — 1 час.

**Итого: ~7 часов, укладываемся в 1 день.**

**Граф зависимостей:**
```
WorktreeManager (isolated) 
  -> SubagentRunner (needs worktree)

PROFILES (static dict)
  -> build_registry_for_role (needs ToolRegistry)
  -> PromptComposer (needs tool_defs per role)

Skill globs loader (needs FS)
  -> PromptComposer (needs skills hash)
  -> SubagentEnvelope (needs filtered history)

FeatureFlags (done)
  -> PromptComposer (prompt.caching flag)
  -> WorktreeManagerFactory (worktree.mode)

Transaction (done)
  -> SessionState (already integrated)
  -> write_file/read_file (already integrated)
```

## §4 Тестинг стратегия — как верифицировать каждый шаг

**Unit тесты (для каждого модуля отдельно, быстро):**

- WorktreeManager: `test_sanitize_empty`, `test_sanitize_unicode`, `test_shared_dir_returns_root`, `test_isolated_branch_already_checked_out` (уже есть 3, добавить 2).
- PROFILES: `test_build_registry_for_role_filters`, `test_estimate_tokens_600_vs_3000`, `test_profile_stateless_flag`.
- PromptComposer: `test_cache_key_stable_excludes_date`, `test_cache_key_includes_skills_hash`, `test_cacheable_split_has_cache_control`, `test_prompt_caching_flag_disables_cache`.
- SubagentEnvelope: `test_envelope_json_roundtrip`, `test_envelope_invalid_fails`, `test_runner_spawn_limit`, `test_artifact_written`, `test_filtered_history_not_full_parent`.
- Skill loader: `test_should_load_globs_match`, `test_should_load_alwaysApply`, `test_should_load_trigger_verb`.
- FeatureFlags: уже есть flat + nested тесты, добавить `test_prompt_caching_flag`.

**Интеграционные тесты (медленнее, но важны):**

- `test_session_state_holds_all`: SessionState c transaction + blackboard + telemetry + feature_flags + artifact_store + pty_pool (None для Phase 1) — уже частично есть в loop integration.
- `test_loop_with_transaction_and_blackboard`: `run_session` с write_file + read_file + instant_grep → проверить transaction read/write + blackboard conflict + telemetry artifact_id.
- `test_skill_loader_in_prompt_composer`: собрать PromptParts с реальными SKILL.md файлами, проверить что загружаются только нужные скиллы.

**Ручные верификации (для acceptance из плана):**

- SharedDir returns session_root: `SharedDirWorktreeManager(session_root).create(...) == session_root`.
- Isolated creates worktree: `IsolatedWorktreeManager(...).create("verify-auth login")` → path `.../verify-auth-login` с branch `agent/verify-auth-login`, `git worktree list` содержит.
- Branch sanitization: `"verify-auth login" → "verify-auth-login"` — проверить.
- PROFILES researcher 600 vs full 3000 — `estimate_tokens`.
- SubagentEnvelope valid JSON round-trip — `envelope.to_json()` → `json.loads()` → `validate_envelope`.
- Cache keys differ per role — `build_prompt_parts_v2(..., role="planner")` vs `role="researcher"` → cache_key разные.
- No date in hash — tool_defs с description содержащим `2026-07-12` → hash одинаковый как без даты.
- Transaction read_set accumulated — `state.transaction.read_set` после `read_file` содержит путь.

**Метрики Pillar 3 (для eval-harness будущего):**

- Median tokens/completed task — пока не меряем, но можем замерить `estimate_tokens` для researcher vs full.
- Median tool-calls — пока не меряем, но tool batching Phase 2.
- Tools-in-context — уже меряем через `registry.names()` len.

## §5 Верификационный чеклист — acceptance из плана v3

- [ ] SharedDir returns session_root, Isolated creates worktree in temp dir with defensive asserts passing — `pytest tests/test_worktree_defensive.py -v`
- [ ] PROFILES researcher 600 vs full 3000 — `test_profiles_researcher_600_vs_full_3000`
- [ ] SubagentEnvelope valid JSON round-trip — `test_envelope_json_roundtrip`
- [ ] Cache keys differ per role, no date in hash, include skills hash — `test_cache_key_per_role`, `test_cache_key_stable_excludes_date`, `test_cache_key_includes_skills_hash`
- [ ] Branch sanitization "verify-auth login" → "verify-auth-login" — `test_sanitize_unicode`
- [ ] Transaction read_set accumulated during execution — `test_transaction_accumulates_during_execution` (уже есть частично, расширить)
- [ ] Skill globs loader checks globs matches current_files or triggers — `test_should_load_skill`
- [ ] FeatureFlags loader from ~/.fa/config.yaml with anchored defaults — уже done, `test_feature_flags`
- [ ] RuntimeLimits extended max_subagent_spawns_per_session=3 — уже done, проверить в `test_config`?

## §6 Риски и смягчения

- **libtmux не доступен:** Fallback pexpect с WARNING — уже реализовано в PtyPool, не трогаем в Phase 1 (PTY — Phase 3).
- **FTS5 trigram не доступен:** Fallback porter с WARNING — уже в fts_index.py.
- **Branch already checked out:** Fail-fast BranchAlreadyCheckedOutError с деталями — уже в worktree_manager, усилим сообщение.
- **Tool batching race:** Не делаем в Phase 1, только фундамент EventLog Lock (уже есть).
- **Cache-key contradiction:** Решено role_id + hash(names+schemas) + hash(agents_map) + hash(skills) — в этом плане добавим skills hash, exclude description.
- **Blackboard stale:** Пока не чистим, но Transaction накапливает read_set, Blackboard append-only.
- **Skill loader frontmatter парсер:** Может упасть если YAML сложный — graceful degradation: если парсер fails → return should_load=False + WARNING log, не crash.
- **Token counting эвристика chars/4:** Неточная, но как в Pi agent и Kon, достаточно для сравнения 600 vs 3000. Не использовать tiktoken — лишний деп.

## §7 Что переписывать, а что оставить — ROI

**Переписать (высокий ROI):**
- `_sanitize_task_id` helper в worktree_manager — 10 строк, фиксит коллизию.
- `build_registry_for_role` + `estimate_tokens` в profiles — 50 строк, дает -60% токенов.
- `_hash_skills` + расширить `build_prompt_parts_v2` — 30 строк, фиксит кэш-инвалидацию.
- `skill_loader.py` новый — 80 строк, экономит тысячи токенов, обязателен.
- `subagent_envelope.py` вынос — 50 строк, чистый интерфейс.

**Оставить (низкий ROI переписывать):**
- Весь `worktree_manager.py` — уже defensive checks, thread-safe, только санитайзер helper добавить.
- Весь `subagent_runner.py` — уже scrubbed env, proxy_token foundation, artifact write, только spawn limit добавить.
- `feature_flags.py`, `transaction.py`, `context.py` — уже prod-ready.

**Не трогать (Phase 2/3):**
- PtyPool, tool batching ThreadPool, instant_grep FTS5 incremental — Phase 2.
- EventStream Runtime FastAPI server — Phase 3.

## §8 Следующие шаги после Phase 1

**Phase 2 — Tool Batching + FTS5 (1 день):**
- ThreadPoolExecutor max 5 parallel read-only (glob,grep,read,instant_grep) → sequential log write Lock, EventLog thread-safe (уже Lock добавлен).
- InstantGrepIndex incremental mtime + stale cleanup (уже частично есть).
- Subagent cheap deterministic minimal prompt <500 tokens.

**Phase 3 — PtyPool in-process + Subagent Runner + Eval-Harness (2-3 дня):**
- PtyPool shared Server LRU fail-fast never reuse main maxSize=2, sentinel |||FA_READY|||, ANSI strip, fallback pexpect.
- run_bash.py thin client зависит от BashExecutor protocol, DI via SessionState.
- Mini eval-harness 5 tasks измерить 124→30-40 шагов.

**Итого: 4 main фазы после quick-win, ближе к pair philosophy "молча подумать и сделать одну задачу вместе".**

---

## §9 Как буду работать — verifiable steps MAX effort

1. **Читать AGENTS.md Pre-flight чеклист** — git log -n 5, grep glossary, grep research, subtraction-check, goal-lens declaration — в начале каждого кодинг-сеанса.
2. **Маленькие коммиты, каждый с верификацией:** один модуль = один коммит + `pytest <relevant> -v` + `ruff check <file>` + ручной тест.
3. **Failure-observable:** никаких `except: pass`, только `WARNING` с контекстом + `noqa: BLE001 - rationale` где нужно по ruff config.
4. **Контекст-бюджет <100k:** любой файл <8000 chars offload в ArtifactStore, активный контекст только preview + artifact_id.
5. **ATX headings, short lines ~150 chars, fenced code blocks с language tag** — по AGENTS.md.
6. **После каждого модуля:** `python scripts/check_doc_links.py` и `PYTHONPATH=src pytest tests/test_<module>.py -v`.
7. **Перед PR:** `HANDOFF.md` §Next, `DIGEST.md` row, `exploration_log.md` Q-N блок per pr-creation rule #9, `llms.txt` не трогаем (deprecated, auto via blackboard), `STAGE_1_VERIFICATION.md` новый.

Готов к кодинг-сессии Phase 1 Foundation — начинаю с WorktreeManager санитайзера.
