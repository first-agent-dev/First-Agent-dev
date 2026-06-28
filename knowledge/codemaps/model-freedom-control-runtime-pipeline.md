# Система управления степенью свободы модели — runtime / hook / CI pipeline

> Codemap ID: `Model_Freedom_Control_Runtime_Pipeline_20260628_141500`

Эта codemap описывает **всю реализованную в коде систему управления степенью свободы модели** в First-Agent на уровне:

- **контрактов** (`SKILL.md`, `pr_intent.py`),
- **человеческого git-hook seat** (`pre-commit`, `prepare-commit-msg`, `commit-msg`),
- **агентного producer seat** (`pr.prepare`),
- **trust boundary** (`PrDraftStore`),
- **runtime enforcement seat** (`IntentGuard` + `bash_intent` + role-scoped registries),
- **локальных/CI guardrails** (`just check`, `fa authoring-check`, CI workflows),
- **процессного merge ceiling** (PR-only agent rights, human merge).

Основная идея системы: **не позволять модели свободно выбирать дешёвый обходной путь там, где проект требует explicитно задекларированного намерения, инварианта и механизма закрытия степени свободы**. При этом enforcement распределён по нескольким seat-ам, и эти seat-ы намеренно имеют **разную строгость**.

---

## 1. Executive model

Система разделяется на шесть уровней:

1. **Contract source** — человеко- и агентно-читаемый canonical contract в `knowledge/skills/pr-creation/SKILL.md`.
2. **Semantic core** — детерминированный модуль `src/fa/hygiene/pr_intent.py`, который превращает контракт в код: классификатор staged diff, набор обязательных полей, валидатор commit/draft metadata, защиту от test-gaming.
3. **Human hook seat** — `prepare-commit-msg` / `commit-msg` / `pre-commit`. Это seat быстрого локального feedback, намеренно bypassable через `--no-verify`, и потому не считается authority.
4. **Agent producer seat** — tool `pr.prepare`, который заставляет модель явно записывать intent/invariant/work log в процессе сессии.
5. **Runtime enforcement seat** — `PrDraftStore` + `IntentGuard` + `bash_intent`, которые не дают мутировать workspace и staged tree, пока в текущей сессии не создан trusted draft.
6. **Authoritative guardrail + merge seat** — `just check`, `fa authoring-check`, CI workflows и human merge gate. Это не seat управления текущим tool call, а seat принятия/отклонения изменений в репозиторий.

Ключевая асимметрия:

- **hook seat** не должен быть настолько строгим, чтобы ломать обычный человеческий commit flow;
- **runtime seat** должен быть строгим, потому что именно там модель получает write-capability и соблазн сделать cheap workaround.

---

## 2. Component inventory

| Component | File | Type | Seat | Purpose |
| --- | --- | --- | --- | --- |
| `pr-creation` skill | `knowledge/skills/pr-creation/SKILL.md` | Contract source | Contract | Каноническое описание `INTENT / CLASS / INVARIANT / DOF / MECHANISM / TEST-EDITS` |
| `Intent` / `FixClass` | `src/fa/hygiene/pr_intent.py:45,55` | `StrEnum` | Semantic core | Закрытые enum-ы намерений и FIX-подклассов |
| `classify_intent()` | `pr_intent.py:164` | Function | Semantic core | Классификатор staged diff по path-shape |
| `render_prepare_buffer()` | `pr_intent.py:307` | Function | Semantic core | Генератор pre-populated header block для hook seat |
| `validate_commit_msg()` | `pr_intent.py:554` | Function | Semantic core | Строгая валидация rich PR-intent metadata |
| `validate_test_edits()` | `pr_intent.py:493` | Function | Semantic core | Защита от test-gaming через `TEST-EDITS:` |
| `has_pr_intent_headers()` | `pr_intent.py:414` | Function | Semantic core / hook adapter | Детектор любого PR-intent metadata header |
| `_cli_prepare()` | `pr_intent.py:905` | Function | Hook adapter | Hook-seat prefill логика |
| `_cli_validate()` | `pr_intent.py:942` | Function | Hook adapter | Hook-seat routing: manual-commit path vs strict metadata path |
| `pre-commit` | `src/fa/hygiene/hooks/pre-commit:1` | Shell hook | Human hook seat | Локальные autofix / hygiene hooks + targeted restage retry |
| `prepare-commit-msg` | `src/fa/hygiene/hooks/prepare-commit-msg:1` | Shell hook | Human hook seat | Pre-populate rich metadata skeleton only in non-skipped prefill flows |
| `commit-msg` | `src/fa/hygiene/hooks/commit-msg:1` | Shell hook | Human hook seat | Строгая validation только при наличии metadata block |
| `HOOK_NAMES` | `src/fa/hygiene/hooks/_util.py:14` | Constant | Hook infra | Единый список hook-seat scripts |
| `resolve_repo_root()` | `_util.py:24` | Function | Hook infra | Workspace anchor на `knowledge/llms.txt` |
| `resolve_git_dir()` | `_util.py:36` | Function | Hook infra | Нормальный checkout + worktree support |
| `resolve_hooks_dir()` | `_util.py:67` | Function | Hook infra | Реальный путь hooks directory |
| `_install_one()` | `hooks/install.py:33` | Function | Hook infra | Symlink/copy install одного hook file |
| `install_hooks()` | `hooks/install.py:90` | Function | Hook infra | Установка всех hook seats |
| `check_hooks()` | `hooks/status.py:38` | Function | Hook infra | Статус installed/stale/non-executable hooks |
| `PrDraftStore` | `src/fa/inner_loop/pr_draft.py:44` | Class | Trust boundary | Current-session trust wrapper вокруг `pr_draft.md` |
| `build_prepare_pr_tool()` | `src/fa/inner_loop/tools/prepare_pr.py:173` | Factory | Agent producer seat | Tool `pr.prepare` |
| `_render_draft()` | `prepare_pr.py:88` | Function | Agent producer seat | Канонический рендер draft body |
| `_validate_fix_fields()` | `prepare_pr.py:124` | Function | Agent producer seat | Fail-fast checks для FIX-only fields |
| `_validate_invariant_prefix()` | `prepare_pr.py:162` | Function | Agent producer seat | Prefix-check для `INVARIANT:` |
| `IntentGuard` | `src/fa/inner_loop/hooks/intent_guard.py:227` | `GuardMiddleware` | Runtime enforcement seat | Блокирует mutation без trusted draft |
| `_parse_typed_intent()` | `intent_guard.py:134` | Function | Runtime enforcement seat | D-5 override path |
| `_project_call()` | `intent_guard.py:156` | Function | Runtime enforcement seat | Проекция `fs.write_file`/`edit` в synthetic staged snapshot |
| `_bash_analysis_for_call()` | `intent_guard.py:209` | Function | Runtime enforcement seat | Связка с bash-effect classifier |
| `_requires_draft()` | `intent_guard.py:218` | Function | Runtime enforcement seat | Решение, требует ли call trusted draft |
| `BashIntentEffect` | `src/fa/inner_loop/bash_intent.py:46` | `StrEnum` | Runtime enforcement seat | `READ_ONLY / VERIFY_ONLY / INDEX_WRITE / REPO_WRITE / OPAQUE_EXEC` |
| `analyze_bash_for_intent()` | `bash_intent.py:127` | Function | Runtime enforcement seat | AST-based shell effect classifier |
| `build_run_bash_tool()` | `src/fa/inner_loop/tools/run_bash.py:14` | Factory | Tool surface | Bash execution tool |
| `build_scrubbed_env()` | `src/fa/inner_loop/tools/bash_env.py:70` | Function | Tool surface / secret isolation | Allowlist + fail-closed secret filter |
| `build_baseline_registry()` | `src/fa/inner_loop/tools/__init__.py:13` | Factory | Tool surface | Coder tool set |
| `build_planner_registry()` | `tools/__init__.py:32` | Factory | Tool surface | Planner read-only tool set |
| `build_eval_registry()` | `tools/__init__.py:49` | Factory | Tool surface | Eval read-only tool set |
| `_cmd_run()` registry/hook wiring | `src/fa/cli.py:630,726-797` | CLI orchestration | Runtime seat wiring | Собирает runtime seat из registry + hooks + draft store |
| Coder prompt `Declare intent` step | `src/fa/inner_loop/prompt.py:533-546` | Prompt contract | Prompt seat | Наталкивает модель вызвать `pr.prepare` до первой mutation |
| Local gates | `knowledge/ci-guardrails-reference.md:18-36` | Process layer | Local authority | `just check`, `fa authoring-check`, tests |
| Runtime hook pipeline | `ci-guardrails-reference.md:50-69` | Process layer | Runtime authority | `SandboxHook -> LoopGuard -> blockers -> IntentGuard -> AuditHook -> SecretGuard -> CostGuardian` |
| Hook seat reference | `ci-guardrails-reference.md:71-99` | Process layer | Human hook seat | Документирует narrowed hook-seat semantics |
| CI workflows + merge ceiling | `ci-guardrails-reference.md:101-150` | Process layer | Merge authority | CI + human merge |

---

## 3. Seat separation map

Эта система deliberately split по seat-ам. Один и тот же semantic rule не должен одинаково применяться во всех местах.

| Seat | Trigger | Strictness | Why it exists | Why it is not enough alone |
| --- | --- | --- | --- | --- |
| **Prompt seat** | модель читает `CODER_SYSTEM_PROMPT` | мягкий | заранее встраивает workflow и требование `pr.prepare` в reasoning path | модель может не послушаться; нет deterministic enforcement |
| **Human hook seat** | локальный `git commit` | средний | быстрый feedback человеку, если он явно использует rich metadata | bypassable (`--no-verify`), не должен ломать обычный manual flow |
| **Agent producer seat** | `pr.prepare` tool call | строгий | заставляет модель materialize intent/invariant/work log в machine-readable form | сам по себе не блокирует mutation, если никто не проверяет existence/trust |
| **Trust boundary seat** | `PrDraftStore` | строгий | отличает “draft из этой сессии” от stale/external file | не знает про staged diff и mutation semantics |
| **Runtime enforcement seat** | mutating tool call | очень строгий | реальный gate перед mutation; связывает draft + projected staged snapshot + shell effect class | не защищает human local git workflow |
| **Local authority seat** | `just check` / `fa authoring-check` | строгий | deterministic repo acceptance locally | не управляет каждым tool call в живой сессии |
| **CI / merge seat** | PR pipeline + human review | authoritative | финальный gate для merge | не улучшает поведение модели в текущей сессии |

---

## 4. Catalog of freedom-closing mechanisms

Ниже перечислены механизмы, которые прямо уменьшают степень свободы модели в коде.

### 4.1 Semantic narrowing
- **Closed enums** (`Intent`, `FixClass`) — модель не может придумать новую категорию (`pr_intent.py:45-60`).
- **Prefix-shaped `INVARIANT` contract** — `RESEARCH → n/a`, `ADR-RULE → Contract:`, `IMPLEMENT → Implements:`, `FIX → Affects:` (`pr_intent.py:368-387`, `623-638`).
- **FIX-only clause requirement** — если `INTENT: FIX`, обязательны `CLASS`, `DEGREE-OF-FREEDOM CLOSED`, `DETERMINISTIC MECHANISM` (`validate_commit_msg`, `pr_intent.py:593-699`).
- **Citation resolution** — `DETERMINISTIC MECHANISM` должен указывать на реальный `path/file.ext:line` (`resolve_citation`, `pr_intent.py:714-779`).
- **Anti-tautology** — DOF и MECHANISM не могут быть одной и той же строкой (`pr_intent.py:690-699`).

### 4.2 Diff-shape narrowing
- **Path-shape classifier** превращает staged diff в один из пяти `Intent` без LLM judgement (`classify_intent`, `pr_intent.py:164-188`).
- **Cross-category priority** не даёт diff одновременно считаться всем подряд (`_INTENT_PRIORITY`, `pr_intent.py:63-70`).
- **Mirror-path filtering** защищает от случайного classification noise от `HANDOFF.md` / `DIGEST.md` / `llms.txt` (`pr_intent.py:72-103`).

### 4.3 Test-gaming closure
- `validate_test_edits()` блокирует delete/rename test files under every intent (`pr_intent.py:493-550`).
- under FIX, modify existing tests only with explicit `TEST-EDITS:` declaration (`pr_intent.py:538-548`).
- runtime `IntentGuard` reuses the same rule so the same policy applies both in hook seat and in tool-execution seat (`intent_guard.py:303-307`; `ci-guardrails-reference.md:58-69`).

### 4.4 Draft trust closure
- `PrDraftStore.write_text()` records digest of exact bytes produced by `pr.prepare` (`pr_draft.py:67-72`).
- `read_current_text()` trusts file only if on-disk bytes still match current-session digest (`pr_draft.py:74-91`).
- `clear(remove_file=...)` resets stale trust at session start / resume boundary (`pr_draft.py:56-64`; `cli.py:755-763`).

### 4.5 Mutation gating
- `IntentGuard` denies mutation when no trusted draft exists (`intent_guard.py:129-130`, `275-281`).
- `build_baseline_registry` / `build_planner_registry` / `build_eval_registry` narrow available tool set by role (`tools/__init__.py:13-64`).
- only coder gets `fs.write_file`; planner/eval are read-only plus `fs.run_bash` for reconnaissance/verification.

### 4.6 Shell-effect narrowing
- `bash_intent.py` classifies shell commands into five effect classes (`bash_intent.py:1-25`, `46-58`).
- unknown / ambiguous shell syntax defaults to `OPAQUE_EXEC`, never optimistic `REPO_WRITE` (`bash_intent.py:22-24`, `127-148`).
- `READ_ONLY` and `VERIFY_ONLY` do not require draft; `INDEX_WRITE`, `REPO_WRITE`, `OPAQUE_EXEC` do (`intent_guard.py:121-127`, `218-224`).
- `REPO_WRITE` projects touched paths into synthetic `StagedPath` rows, so runtime classification sees the about-to-be-produced snapshot (`intent_guard.py:156-194`, `290-299`).

### 4.7 Environment narrowing
- `build_scrubbed_env()` passes only allowlisted env vars to `fs.run_bash`, then drops any credential-looking names fail-closed (`bash_env.py:28-89`).
- this reduces model freedom to exfiltrate secrets via child processes.

### 4.8 Hook-seat narrowing
- `prepare-commit-msg` pre-fills rich metadata only in **non-skipped prefill flows**. Current implementation skips many common human flows (`message`, `template`, `squash`, `merge`, `commit`, empty `COMMIT_SOURCE`), so in practice this seat is much less invasive than a universal template injector (`prepare-commit-msg:19-44`).
- `commit-msg` now allows ordinary human commits with **no PR-intent headers at all**, but still strictly validates any explicit metadata block (`commit-msg:14-18,49-52`; `pr_intent.py:951-957`).
- `has_pr_intent_headers()` ensures partial malformed metadata does not silently pass as “manual commit” (`pr_intent.py:414-430`).

### 4.9 Pre-commit restage narrowing
- `pre-commit` snapshots the staged path set before running hooks (`pre-commit:39`).
- after hook-induced failure it re-stages **only already-staged files that hooks modified** (`pre-commit:45-60`).
- this avoids the dangerous widening effect of `git add -u`.

### 4.10 Repo acceptance narrowing
- `just check` is the authoritative local acceptance gate (`ci-guardrails-reference.md:18-36`).
- `fa authoring-check` gives deterministic authoring-time constraints (`ci-guardrails-reference.md:38-49`).
- CI + human merge remain the final authority (`ci-guardrails-reference.md:101-150`).

---

## 5. Trace 1 — Contract source becomes executable semantic core

Исходная human-readable contract surface — `knowledge/skills/pr-creation/SKILL.md` — материализуется в коде через `pr_intent.py`.

```text
SKILL.md §Reference / §Output format / §Test-edit declaration
└── pr_intent.py
    ├── Intent / FixClass enums <-- [1a]
    ├── path-shape buckets <-- [1b]
    ├── required-field table <-- [1c]
    ├── header constants <-- [1d]
    ├── strict validator <-- [1e]
    └── snapshot tests pin the two views <-- [1f]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `1a` | Closed enums | Five Level-1 intents, three FIX sub-classes | `pr_intent.py:45-60` |
| `1b` | Path-shape classifier | `ADR-RULE > IMPLEMENT > FIX > RESEARCH > CHORE` over staged paths | `pr_intent.py:164-188` |
| `1c` | Required-field contract | Per-intent required field list for buffer prefill | `pr_intent.py:260-295` |
| `1d` | Header constants | `INTENT`, `CLASS`, `INVARIANT`, `DOF`, `MECHANISM`, `TEST-EDITS` | `pr_intent.py:338-359` |
| `1e` | Validator core | Presence, shape, citation, tautology, test-edit rules | `pr_intent.py:554-699` |
| `1f` | Drift lock | `tests/test_pr_intent_snapshot.py` pins code ↔ skill contract | `tests/test_pr_intent_snapshot.py:1-174` |

---

## 6. Trace 2 — Human commit hook seat

Это seat локального feedback для человека. Он intentionally narrower, чем runtime seat.

```text
git commit
├── pre-commit hook <-- [2a]
│   ├── uv run pre-commit run <-- [2b]
│   ├── on hook autofix failure: inspect staged subset <-- [2c]
│   ├── re-stage ONLY modified staged files <-- [2d]
│   └── retry once <-- [2e]
│
├── prepare-commit-msg hook <-- [2f]
│   ├── skip for git-generated / message-source cases <-- [2g]
│   └── otherwise prefill INTENT buffer via _cli_prepare <-- [2h]
│
└── commit-msg hook <-- [2i]
    ├── skip for merge/cherry-pick/revert/amend <-- [2j]
    └── _cli_validate:
        ├── no PR-intent headers at all → allow manual commit <-- [2k]
        └── any metadata headers present → strict validation <-- [2l]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `2a` | Hook seat entry | `pre-commit` script in `.git/hooks/` | `hooks/pre-commit:1-66` |
| `2b` | Pre-commit execution | `uv run pre-commit run` under project env | `hooks/pre-commit:41-42` |
| `2c` | Staged snapshot | Capture staged paths before first run | `hooks/pre-commit:39` |
| `2d` | Targeted restage | Re-stage only already-staged files that changed | `hooks/pre-commit:45-60` |
| `2e` | One retry | Second `uv run pre-commit run` after targeted restage | `hooks/pre-commit:62-64` |
| `2f` | Template prefill seat | `prepare-commit-msg` script | `hooks/prepare-commit-msg:1-44` |
| `2g` | Auto-fill skip set | skip on `message/template/squash/merge/commit/""` | `hooks/prepare-commit-msg:19-37` |
| `2h` | Buffer prefill | `python -m fa.hygiene prepare` | `hooks/prepare-commit-msg:44` |
| `2i` | Validate seat | `commit-msg` script | `hooks/commit-msg:1-52` |
| `2j` | Git-generated skip | merge/cherry-pick/revert/amend bypass | `hooks/commit-msg:35-47`, `pr_intent.py:859-903` |
| `2k` | Manual-commit allow path | No PR-intent headers → ordinary manual commit path | `pr_intent.py:951-957` |
| `2l` | Strict metadata path | Any explicit headers → full validator path | `pr_intent.py:414-430`, `960-989` |

---

## 7. Trace 3 — Agent producer seat (`pr.prepare`)

Это seat, где модель явно materialize-ит intent и work log **до mutation**.

```text
LLM decides to mutate workspace
└── call pr.prepare <-- [3a]
    ├── parse params (intent, invariant, optional FIX fields, body) <-- [3b]
    ├── validate invariant prefix <-- [3c]
    ├── validate FIX-only fields presence/shape <-- [3d]
    ├── render canonical draft text <-- [3e]
    ├── re-run strict validator on rendered text <-- [3f]
    ├── ignore citation-only unresolved cases at draft-write time <-- [3g]
    └── write trusted current-session draft via PrDraftStore <-- [3h]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `3a` | Tool registration | `pr.prepare` registered by CLI into per-run registry | `cli.py:763` |
| `3b` | Param parsing | Required `intent` / `invariant`, optional FIX-only fields | `prepare_pr.py:181-188` |
| `3c` | Invariant prefix check | Mirror of core validator’s intent-prefix logic | `prepare_pr.py:162-170`, `199-201` |
| `3d` | FIX field gate | `fix_class` / `dof` / `mechanism` required only for FIX | `prepare_pr.py:124-160`, `203-207` |
| `3e` | Canonical renderer | Builds exact `INTENT/CLASS/INVARIANT/...` draft body | `prepare_pr.py:88-121`, `209-216` |
| `3f` | Defensive validator pass | Re-validates rendered text with shared validator | `prepare_pr.py:223-241` |
| `3g` | Draft-time citation relaxation | `mechanism_citation_unresolved` filtered because staging may not exist yet | `prepare_pr.py:229-241` |
| `3h` | Trusted write | `draft_store.write_text(rendered)` | `prepare_pr.py:243-249`; `pr_draft.py:67-72` |

---

## 8. Trace 4 — Trust boundary (`PrDraftStore`)

Этот слой отрезает cheap bypass, где модель или shell просто пишет файл по правильному пути без прохождения через `pr.prepare`.

```text
pr.prepare writes draft <-- [4a]
└── PrDraftStore.write_text()
    ├── atomic write to stable path <-- [4b]
    └── record current-session digest <-- [4c]

Later mutation check
└── PrDraftStore.read_current_text() <-- [4d]
    ├── no digest in memory → untrusted <-- [4e]
    ├── file missing/unreadable → untrusted <-- [4f]
    ├── digest mismatch after file tamper → untrusted <-- [4g]
    └── exact bytes still match current-session digest → trusted <-- [4h]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `4a` | Producer-side write | `pr.prepare` is the only trusted writer | `prepare_pr.py:243-249` |
| `4b` | Atomic file write | temp file + `os.replace` | `pr_draft.py:95-117` |
| `4c` | Session digest | `sha256(text)` cached in memory | `pr_draft.py:39-40`, `67-72` |
| `4d` | Trusted read path | Returns text only when current-session digest still matches | `pr_draft.py:74-91` |
| `4e` | Never prepared this session | `_current_digest is None` → deny later mutation | `pr_draft.py:81-82` |
| `4f` | Missing/unreadable file | deny trust on IO failure | `pr_draft.py:83-87` |
| `4g` | Tamper detection | digest mismatch revokes trust | `pr_draft.py:88-90` |
| `4h` | Trusted current text | exact match → draft accepted | `pr_draft.py:90-91` |

---

## 9. Trace 5 — Runtime mutation gate (`IntentGuard`)

Это главное runtime-enforcement seat: здесь declared intent перестаёт быть просто текстом и становится gate перед mutation.

```text
Tool call about to execute
└── IntentGuard.handle(BEFORE_TOOL_EXEC) <-- [5a]
    ├── determine whether call requires draft <-- [5b]
    │   ├── direct mutating tool? <-- [5b1]
    │   └── bash effect classifier? <-- [5b2]
    ├── read trusted current-session draft <-- [5c]
    │   └── missing/untrusted → deny immediately <-- [5d]
    ├── read staged snapshot from git diff --cached --name-status <-- [5e]
    ├── project impending mutation into staged view <-- [5f]
    │   ├── direct file write/edit/apply_patch projection <-- [5f1]
    │   └── bash REPO_WRITE path projection <-- [5f2]
    ├── classify projected staged set <-- [5g]
    ├── typed INTENT override if draft explicitly declares one <-- [5h]
    ├── validate_commit_msg(draft_text, effective_intent, projected, repo_root) <-- [5i]
    ├── validate_test_edits(draft_text, classifier_intent, projected) <-- [5j]
    └── allow or deny with hook-like error wording <-- [5k]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `5a` | Guard entry | Runtime gate attaches only to `BEFORE_TOOL_EXEC` | `intent_guard.py:227-274` |
| `5b` | Draft requirement routing | `_requires_draft()` decides whether this call needs trusted draft | `intent_guard.py:218-224`, `275-277` |
| `5b1` | Direct mutators | `fs.write_file`, `fs.edit_file`, `fs.apply_patch` always require draft | `intent_guard.py:112-118`, `218-220` |
| `5b2` | Bash-mediated mutators | `bash_intent` decides `READ_ONLY / VERIFY_ONLY / INDEX_WRITE / REPO_WRITE / OPAQUE_EXEC` | `intent_guard.py:209-224`; `bash_intent.py:127-148` |
| `5c` | Trusted draft read | `draft_store.read_current_text()` | `intent_guard.py:279` |
| `5d` | Hard deny on missing/untrusted draft | same-session trust required | `intent_guard.py:280-281` |
| `5e` | Staged snapshot read | `git diff --cached --name-status` via injected runner | `intent_guard.py:282-288` |
| `5f` | Mutation projection | direct or bash-mediated path projection into synthetic staged set | `intent_guard.py:289-299` |
| `5g` | Classifier over projected view | shared classifier sees about-to-be-produced snapshot | `intent_guard.py:300` |
| `5h` | Typed intent override | `INTENT:` in draft can override classifier for shape-validation | `intent_guard.py:134-149`, `301-302` |
| `5i` | Shared semantic validator | same core validator as hook seat and `pr.prepare` | `intent_guard.py:303-308` |
| `5j` | Shared test-protection rule | classifier intent remains authoritative for test-edit policy | `intent_guard.py:309-312` |
| `5k` | Hook-like denial message | same semantic rule surface, different runtime seat | `intent_guard.py:313-318` |

---

## 10. Trace 6 — Bash effect classification and shell narrowing

`IntentGuard` would be too blunt if every `fs.run_bash` call required the same treatment. `bash_intent.py` narrows shell freedom before that point.

```text
fs.run_bash command
└── analyze_bash_for_intent(command) <-- [6a]
    ├── parse shell AST via bashlex <-- [6b]
    │   └── parse failure → OPAQUE_EXEC <-- [6c]
    ├── analyze command/list/pipeline nodes <-- [6d]
    ├── classify effect:
    │   ├── READ_ONLY <-- [6e]
    │   ├── VERIFY_ONLY <-- [6f]
    │   ├── INDEX_WRITE <-- [6g]
    │   ├── REPO_WRITE with projected paths <-- [6h]
    │   └── OPAQUE_EXEC fail-closed <-- [6i]
    └── reduce multi-clause analysis conservatively <-- [6j]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `6a` | Classifier entry | Main shell-effect classifier | `bash_intent.py:127-148` |
| `6b` | AST parse | `bashlex.parse(command)` | `bash_intent.py:135-136` |
| `6c` | Fail-closed parse fallback | malformed/unsupported shell → `OPAQUE_EXEC` | `bash_intent.py:137-146` |
| `6d` | Node analysis | command/list/pipeline decomposition | `bash_intent.py:151-177` |
| `6e` | Read-only commands | whitelisted non-mutating shell verbs | `bash_intent.py:62-99` |
| `6f` | Verify-only commands | test/lint commands that do not mutate | `bash_intent.py:7-19`, `123-124` |
| `6g` | Index write | `git add / git commit` family: draft required, validate live staged snapshot | `bash_intent.py:13-16` |
| `6h` | Repo write | deterministic file writes with projected `StagedPath`s | `bash_intent.py:15-18`, `203-208` |
| `6i` | Opaque execution | anything not confidently understood stays gated but without fake path claims | `bash_intent.py:18-24`, `192-199` |
| `6j` | Conservative reducer | mixed mutation classes can collapse to `OPAQUE_EXEC` | `bash_intent.py:180-213` |

---

## 11. Trace 7 — Prompt seat: how the model is nudged before enforcement

Prompting is not authority, but it is the first line of friction reduction. The coder prompt explicitly teaches the runtime ritual.

```text
CODER_SYSTEM_PROMPT
├── planner → coder → evaluator chain context <-- [7a]
├── declare intent before first mutation <-- [7b]
├── for each step: read → write → verify → pr.prepare update <-- [7c]
├── if harness blocks your call: read deny reason and adapt <-- [7d]
└── maintain living work log in draft body <-- [7e]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `7a` | Role chain framing | coder knows it is middle seat in planner→coder→evaluator pipeline | `prompt.py:506-518` |
| `7b` | Declare intent first | explicit `pr.prepare` before first mutation | `prompt.py:533-536` |
| `7c` | Step protocol | read, mutate, verify, update work log | `prompt.py:538-547` |
| `7d` | Harness deny semantics | prompt tells model deny reason is a real constraint | `prompt.py:609-613` |
| `7e` | Living work log | draft body as operational memory surface | `prompt.py:592-599` |

---

## 12. Trace 8 — Hook infrastructure: install, health check, and local bootstrap

Эта часть не про semantic core, а про operational reliability того, что должно запускать hook seat.

```text
just install <-- [8a]
├── uv sync --extra dev <-- [8b]
├── install-hooks --> python -m fa.hygiene.hooks.install --force <-- [8c]
│   ├── resolve_repo_root() <-- [8d]
│   ├── resolve_hooks_dir() asks git first (`rev-parse --git-path hooks`) <-- [8e]
│   ├── install each hook via _install_one() <-- [8f]
│   │   ├── prefer symlink <-- [8g]
│   │   ├── fallback to copy <-- [8h]
│   │   └── ensure executability best-effort <-- [8i]
│   └── print installed paths <-- [8j]
├── hooks-status --> python -m fa.hygiene.hooks.status <-- [8k]
│   ├── resolve_hooks_dir() <-- [8l]
│   ├── compare installed file vs shipped source <-- [8m]
│   ├── check executability on POSIX <-- [8n]
│   └── final healthy/unhealthy verdict <-- [8o]
└── print bootstrap summary only after status passes <-- [8p]
```

| Location | Title | Description | File:Line |
| :--- | :--- | :--- | :--- |
| `8a` | Bootstrap entry | `just install` local bootstrap path | `justfile:9-17` |
| `8b` | Dev deps sync | ensures `pre-commit`, `pytest`, `bashlex`, etc. are installed | `justfile:10-12` |
| `8c` | Hook installer CLI | shell entrypoint into installer | `justfile:33-35`; `hooks/install.py:114-148` |
| `8d` | Workspace anchor | root must contain `knowledge/llms.txt` | `_util.py:24-33` |
| `8e` | Hook-dir resolution | asks Git first via `git rev-parse --git-path hooks`, so `core.hooksPath` and worktree/common-dir rules are honored; pure-Python fallback remains for resilience | `_util.py:36-107` |
| `8f` | Per-hook installer loop | install all `HOOK_NAMES` | `hooks/install.py:104-112` |
| `8g` | Symlink path | preferred install mode on non-Windows | `hooks/install.py:57-67` |
| `8h` | Copy fallback | fallback when symlink unavailable or on Windows | `hooks/install.py:61-70` |
| `8i` | Executability best-effort | chmod source + target | `hooks/install.py:72-88` |
| `8j` | Installer output | prints `installed (symlink|copy): path` | `hooks/install.py:142-144` |
| `8k` | Hook status CLI | shell entrypoint into health check | `justfile:41-42`; `hooks/status.py:105-112` |
| `8l` | Worktree-safe status path | same hooks-dir resolver as installer | `hooks/status.py:46-47`; `_util.py:67-79` |
| `8m` | Stale copy detection | compare installed content vs shipped source | `hooks/status.py:64-89` |
| `8n` | Executability check | non-executable hook is unhealthy on POSIX | `hooks/status.py:25-35`, `72-92` |
| `8o` | Health verdict | installed / stale / non-executable summary | `hooks/status.py:94-102` |
| `8p` | Fail-fast bootstrap | `just install` runs `just hooks-status` before success banner | `justfile:9-18` |

---

## 13. Data flow diagram

```text
                         Contract Source
                  knowledge/skills/pr-creation/SKILL.md
                                   │
                                   ▼
                    src/fa/hygiene/pr_intent.py
               (classifier + field tables + validator)
                     │                    │
         ┌───────────┘                    └───────────────┐
         ▼                                                ▼
 Human hook seat                                  Agent producer seat
 prepare-commit-msg / commit-msg                  pr.prepare tool
         │                                                │
         │                             writes canonical draft bytes
         ▼                                                ▼
 ordinary manual commit path                   PrDraftStore (stable path +
 or strict metadata path                       current-session digest)
                                                        │
                                                        ▼
                                              Runtime enforcement seat
                                             IntentGuard BEFORE_TOOL_EXEC
                                              │          │
                                    bash_intent        projected StagedPath view
                                              │          │
                                              └────┬─────┘
                                                   ▼
                                      allow / deny mutating tool call
                                                   │
                                                   ▼
                                       Tool execution / audit / CI / merge
```

---

## 14. Freedom-closure matrix

| Model freedom | Closing mechanism | Seat |
| --- | --- | --- |
| Invent a new intent label | closed enum `Intent` | Semantic core |
| Avoid naming invariant | `INVARIANT:` required with prefix shape | Semantic core |
| Claim FIX without mechanism | `DEGREE-OF-FREEDOM CLOSED` + `DETERMINISTIC MECHANISM` required | Semantic core |
| Cite fake mechanism | `resolve_citation()` | Semantic core |
| Make tautological explanation | DOF vs MECHANISM anti-tautology check | Semantic core |
| Delete or rewrite tests to escape failing code | `validate_test_edits()` | Semantic core + Runtime seat |
| Mutate workspace before declaring intent | `IntentGuard` requires trusted `pr.prepare` draft | Runtime seat |
| Fake a draft by writing the file directly | `PrDraftStore` session digest trust | Trust boundary |
| Hide shell-side writes inside opaque command | `bash_intent` fail-closed `OPAQUE_EXEC` | Runtime seat |
| Exfiltrate env secrets from bash | `build_scrubbed_env()` allowlist + secret filter | Tool surface |
| Bypass human-local hook feedback | `--no-verify` still possible, therefore hook seat is convenience only | Process boundary |
| Merge unsafe code despite local bypass | `just check` / CI / human review | Local authority + Merge seat |

---

## 15. Important asymmetries and design choices

### 15.1 Hook seat is intentionally weaker than runtime seat
Ordinary human commits with no metadata are allowed through. This is not a bug; it is a boundary decision. The strict anti-cheap-workaround semantics belong primarily to the runtime seat, not to every human commit.

### 15.2 Shared validator is intentionally stronger than hook seat
`validate_commit_msg(...)` remains strict even though `_cli_validate(...)` now allows a manual no-header path. This is deliberate: the same validator powers `pr.prepare` and `IntentGuard`, where strictness is required.

### 15.3 `TEST-EDITS` authority is classifier-based, not typed-intent-based
The D-5 typed `INTENT:` override can affect shape-validation, but `validate_test_edits()` remains keyed on classifier intent. This prevents an agent from disarming test protection by editing its own declared intent.

### 15.4 Prompt seat reduces friction, not authority
The coder prompt tells the model to call `pr.prepare` before first mutation, but the actual authority is `IntentGuard`. Prompting nudges; runtime enforces.

---

## 16. Known limitations and residual gaps

1. **`--no-verify` remains a human bypass by design.** This is documented in `knowledge/ci-guardrails-reference.md:91,149`. Agent-side blocking of `git commit --no-verify` is a separate future hardening item.
2. **Hook seat does not parse staged PR note file contents.** Only commit message text and staged path list affect hook-seat validation. A staged `PR_NOTE_*.md` file is not a substitute for explicit commit-message metadata.
3. **`prepare-commit-msg` is currently mostly dormant for standard human flows.** Because empty `COMMIT_SOURCE` is skipped, many ordinary editor-based commits do not receive prefill. If you want a stronger or clearer prefill policy later, that is a separate boundary refinement.
4. **The branch name currently contains `U+2014` EM DASH.** This is not a runtime bug, but it is brittle automation hygiene.
5. **Installer still relies on best-effort chmod.** Correct tracked file mode in git reduces the need for source-mode repair, but copy/symlink portability still requires best-effort behavior.

---

## 17. High-ROI follow-up improvements

1. **Dedicated agent commit tool.** The cleanest long-term narrowing of model freedom would be a first-party commit tool (for example `git.commit_prepared`) that consumes the trusted current-session draft, appends the `AI-Session:` trailer deterministically, and avoids raw `git commit` through `fs.run_bash`.
2. **Explicit agent-mode signal for hook behavior.** If later you want stricter hook-seat behavior for agent-executed commits but not for humans, prefer an explicit runtime signal over heuristics on branch names or `COMMIT_SOURCE`.
3. **Clearer prefill policy.** The current `prepare-commit-msg` logic is intentionally narrow, but not obviously so from first read. A future simplification is to make prefill opt-in by an explicit env flag and document that policy directly.
4. **Shared-hooks operational note.** In git worktree layouts, hooks live in the common git dir and are therefore shared across sibling worktrees. This is correct for Git, but worth documenting for operators because reinstalling hooks in one worktree affects the others.
5. **Preserve non-1 exit codes in hook wrappers.** The `pre-commit` hook now preserves the first failure code when no retry happens, and the retry failure code when the second run still fails. This is mainly a diagnostics improvement (pre-commit usually exits 1 anyway), but it avoids masking `127`, `130`, and similar operator-relevant failures.

---

## 18. One-line summary

**First-Agent’s model-freedom-control system is not a single hook but a layered control pipeline: a human-readable skill becomes a strict semantic core; that core is consumed by a narrow human hook seat, a strict agent producer seat, a trust-preserving draft store, and a runtime mutation gate that uses projected staged snapshots and fail-closed shell classification to keep the model’s degrees of freedom small exactly where the codebase becomes mutable.**
