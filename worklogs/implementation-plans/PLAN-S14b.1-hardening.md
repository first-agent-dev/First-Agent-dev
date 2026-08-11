# PLAN: S14b.1 hardening — bugfix pass on unified fs_search (v3, post-review)

**Plan-ID:** PLAN-S14b.1-hardening
**Status:** READY
**Depth:** P2 (focused security/perf/correctness hardening; no new features; no new files)
**Revision:** v3 (senior adversarial review v2 → found F1–F13; closed all)
**Upstream context:** Builds on PLAN-cli-trace-S14b-search-tools-memory-expansion.md §S14b.1 (applied uncommitted to working tree, HEAD `103fb89 fix`).
**Date:** 2026-08-11
**v1 → v2:** Added canary+throttle, binary NUL-sniff, Latin-1, symlink D-in-D, concurrency smoke.
**v2 → v3 (this):** Closed 13 review findings F1–F13: fixed F1 (holder short-circuit was blocking all refresh!), F2 (per-instance→module-level refresh state so ephemeral SearchIndex instances share canary/throttle), F3 (split _read_bytes for index vs _read_text for match-display, correct size caps), F4 (removed glob from _path_like), F5 (kept subagent-guard in search.search() as explicit D-in-D), F6 (unified sentinels into module-level _refresh_state), F7 (explicit signatures), F8 (_search_python_walk now always yields root-relative paths, no double-rel), F9 (symlink-escape test uses sibling tmp file, not /etc/passwd), F10 (non-existent subpath returns 0 results, not path_escape), F11 (documented InstantGrepIndex schema collision — intentional migration on first search_index use), F12 (LIKE-wildcard literal-match C1 test), F13 (refresh-state key matches sentinel key).

---

## Preflight log (re-verified 2026-08-11)

**Roots checked (read in full, not via plan description):**
- `src/fa/memory/search_index.py` (1011 lines) — index core, query helpers, FTS invocation, hit formatting.
- `src/fa/memory/_safe_walk.py` (304 lines) — file iterator, git-ls-files fast path, os.walk fallback.
- `src/fa/inner_loop/tools/fs_search.py` (631 lines) — handler, param parsing, _IndexHolder, response assembly.
- `src/fa/memory/fts_index.py` (218 lines) — InstantGrepIndex deprecation shim; **NOT modified** in this hardening; F11 noted.
- `src/fa/inner_loop/subagent_prompts.py` (204 lines) — _get_fts_files() calls SearchIndex directly (one of two production callers).
- `src/fa/skills/loader.py:204-213` — still uses `InstantGrepIndex.instant_grep()`. Out of scope; one-release deprecation cycle preserved. Follow-up ticket.
- `tests/test_fs_search.py` (497 lines, 25 tests) + `tests/test_safe_walk.py` (146 lines, 9 tests).
- `src/fa/inner_loop/{tool_names,profiles,loop,subagent_prompts,subagent_runner,tools/__init__,tools/blackboard_query}.py` — wiring verified correct; **no edits needed**.

**Bugs reproduced live against working tree (PoC-verified):**

| ID | Sev | File:line (pre-fix) | PoC |
|---|---|---|---|
| C1 | 🔴 CRIT | fs_search.py:241 `_resolve_subdir` | `root=/tmp/ws, subpath=../ws-secret` → str.startswith True → падает на `subdir.relative_to(root)` внутри _do_indexed_search → BLE001 маскирует в `search_failed 500`. |
| C2 | 🔴 CRIT | search_index.py:498-510 | include_tests фильтрует после FTS, но exclude_dirs в BM25/trigram ветках не применяется. `exclude_dirs=["vendored"]` пропускает `vendored/v.py`. |
| H1 | 🟠 HIGH | search_index.py:595 | `like = f"%{query}%"` без ESCAPE. Запрос `%` возвращает все индексированные триграммой файлы; `_` совпадает с любым одним символом. |
| H2 | 🟠 HIGH | _safe_walk.py:94-105, 270 | `_path_is_excluded(parts)` не принимает `extra_exclude_dirs`; git-ветка вызывает без них. Существующий тест зелёный потому что tmp_path без .git → os.walk. |
| M1 | 🟡 MED | search_index.py:250-253 + fs_search.py:278-279 | **Двойной** шортсёрк: module sentinel в ensure_indexed + `if holder._indexed: return None` в fs_search._ensure_index. Новые/удалённые файлы не видны через FTS; удалённые зависают как призрачные хиты. |
| M2 | 🟡 MED | search_index.py:374-380, 361-371 | _path_matches через голый fnmatch (без **); SQL `_path_like` превращает `src/**/*.py` → `src/%/%.py` (ровно один уровень вложенности). |
| M3 | 🟡 MED | search_index.py:339 | `_escape_fts_query` заворачивает весь запрос в `"..."` → multi-term запросы превращаются в phrase и не находят разрозненные вхождения через BM25. |

**Pre-existing test baseline (before this hardening):** 2618 passed, 14 pre-existing failures (providers_chain 2, pyrefly 2, s10a_cli_coverage 1, s12_marker_hygiene 1, s13_fail_closed_open 1, s13_message_rules 1, s5_state_root 6) — unrelated, preserved.

**Baseline static gates on new files:** ruff ✓, mypy 0 new errors.

---

## 0. Executive intent (§3)

**IDEA:** Довести fs_search до состояния production-grade discovery:
1. **Containment bulletproof**: is_relative_to в каждом boundary; D-in-D в _collect_matches.
2. **SQL meta hygiene**: LIKE escaping с ESCAPE clause; FTS MATCH построен безопасным токенайзером.
3. **Filters are uniform**: одна функция `_passes_filters` применяется на BM25/trigram/walk путях, без исключений.
4. **Index stays fresh with O(1) fast path**: canary stat (root + .git/index + .git/FETCH_HEAD) + 5s monotonic throttle; при промахе канарейки — quick-refresh по mtime/size с чисткой stale.
5. **Glob semantics match ripgrep/IDE**: `**` через PurePosixPath.match; `*.py` на любой глубине; `src/*.py` — ровно один уровень.
6. **Multi-term BM25 = AND, не phrase**: токенайзер сохраняет пользовательские `"phrase"` и trailing `*`, одиночные токены оборачивает в двойные кавычки для safety.
7. **Robust file reading**: NUL-sniff на первых 8КБ для определения бинари; UTF-8 strict → Latin-1 fallback (никогда не падает); отдельные cap'ы для индексации (100KB) и выдачи матчей (1MB).
8. **All fixes locked by C3 regression tests** с mutation kill-check.

**PROJECT MEANING:** fs_search — основной discovery-инструмент агента в цикле. Баг в containment = утечка; баг в фильтрах = токены впустую или неверный контекст; баг в рефреше = агент не видит только что созданные/удалённые файлы.

**NON-GOals (scope firewall):**
- NG1: нет новых CLI-verb (`fa reindex`); lazy auto-index по дизайну.
- NG2: нет inotify/fs-events/watcher (platform-specific, ломается в контейнерах).
- NG3: нет миграции схемы БД (SCHEMA_VERSION = 1 остаётся).
- NG4: нет правок wire-схемы (все параметры, output shape, error codes совместимы).
- NG5: нет имплементации order="path"/"match_count" (по-прежнему документация v1).
- NG6: InstantGrepIndex не удалять (deprecation один релиз-цикл).
- NG7: нет миграции `src/fa/skills/loader.py` на SearchIndex (отдельный тикет).
- NG8: нет векторного/эмбеддинг-поиска.
- NG9: нет brace/extglob `{a,b}` в globs.
- NG10: нет support для Windows-разделителей (PurePosixPath, posix-only).
- NG11: нет фазз-тестов, нет нагрузочных тестов на 100K-файловые монорепы.
- NG12: нет рефакторинга двойного скана walk-fallback-Python-walk в `search()` (есть оверхед, но не корректностный; откладываем).

---

## 1. Constants & invariants (public v3)

```python
# search_index.py module-level
SCHEMA_VERSION = 1
MAX_CONTENT_BYTES_INDEXED = 100_000     # cap for FTS content
MAX_MATCH_DISPLAY_BYTES = 1_000_000     # cap when reading for matches/regions snippets
SNIPPET_MAX_BYTES = 400
REFRESH_THROTTLE_SECONDS = 5.0          # at most one walk per (db,root) per 5s
BINARY_SNIFF_BYTES = 8192
_INDEX_CANARY_FILES = (".git/index", ".git/FETCH_HEAD")  # relative to root
_refresh_state: dict[str, dict] = {}    # key: f"{db_path}::{root}"; value: {last_mono, last_canary}
_indexed_for_process: set[str] = set()  # sentinel: full build done in this process for this key
```

Инварианты:
- **INV-HARDEN-1 (containment):** Любой возвращаемый `rel` является POSIX-путём относительно root, резолвится внутрь root, не содержит `..` или ведущего `/`.
- **INV-HARDEN-2 (filter uniformity):** Каждый кандидат перед добавлением в результат проходит через `_passes_filters(rel, subdir_rel, glob_pat, include_tests, exclude_set)`; нет ни одного кода, возвращающего хит в обход фильтра.
- **INV-HARDEN-3 (no LIKE wildcards):** Каждый SQL LIKE с пользовательскими данными использует `_escape_like(...)` и `ESCAPE '\'`.
- **INV-HARDEN-4 (fast path):** В steady-state (нет изменений ФС) ensure_indexed выполняет ≤3 stat-вызова и 0 SQL-запросов кроме одного commit-free PRAGMA/read для canary; настенное время <5мс.
- **INV-HARDEN-5 (fail-degraded):** Каждая внешняя граница (БД, ФС, subprocess, Unicode) обёрнута BLE001 и переводит систему в walk-fallback; необработанное исключение не может долететь до loop.
- **INV-HARDEN-6 (no new noqa):** Fixes не добавляют `# noqa`; любая C901 сложность декомпозируется на мелкие функции.
- **INV-HARDEN-7 (symlinks):** Любой symlink резолвится; пути, указывающие наружу, молча пропускаются; followlinks=False в os.walk (без циклов); симлинки внутрь дерева дедуплицируются.
- **INV-HARDEN-8 (binary/encoding):** Файлы с NUL-байтом в первых 8КБ не индексируются; текстовые файлы декодируются UTF-8 → Latin-1 (не падают, не silent-ignore).
- **INV-HARDEN-9 (result cap):** Ответ всегда ≤MAX_RESPONSE_BYTES (30КБ) за счёт _enforce_response_cap; обрезка отмечается флагом truncated.
- **INV-HARDEN-10 (shared refresh state):** Состояние рефреша (last_mono, last_canary, full-indexed) общее для всех SearchIndex в рамках процесса на один (db_path, root) — при создании нового экземпляра (subagent_prompts) он не запускает лишний refresh.

### Security contracts (CT-SEC)
- **SEC-1 (sibling-prefix):** path="../<basename-prefix-of-root>" → error code `path_escape`.
- **SEC-2 (like-wildcards):** query="%" возвращает 0 файлов (кроме файлов, содержащих буквальный "%"); query="_" не совпадает с каждым односимвольным токеном; query="100%" находит файлы с literal "100%".
- **SEC-3 (exclude_dirs is a hard filter):** `exclude_dirs=["X"]` гарантирует отсутствие файлов под `X/` в результате независимо от метода.
- **SEC-4 (glob escapes):** glob="../etc/*" → containment-enforced; результаты пусты или path_escape; не читается ни одного файла снаружи root.
- **SEC-5 (symlink outside):** symlink изнутри root, указывающий наружу, молча пропускается; контент снаружи не сканируется и не возвращается.
- **SEC-6 (stale symlink after index):** Если rel, присутствующий в fts_meta, к моменту поиска заменён на symlink за границу root — _collect_matches пропускает его (D-in-D).

---

## 2. Current state → Target state

### AS-IS (см. Preflight для 7 багов; здесь — важные детали интеграции, влияющие на план)

1. **Фатальная интеграционная проблема F1:** `_ensure_index` в fs_search.py шортсёркит на `if holder._indexed: return None`. Даже если в SearchIndex.ensure_indexed идеально реализовать quick-refresh + canary + throttle, основной поток never calls it после первого вызова. **Обязательно чинить одновременно с S1.**
2. **Дублирование sentinel (F6):** module-level `_indexed_for_process: set[str]` в search_index.py:51 и instance-level `self._indexed_for_session: bool` дублируют назначение. После фикса F2 храним оба флага в module-level `_refresh_state`.
3. **Чтение файлов с неверным cap (F3):** `_read_file_text(fp, max_bytes=MAX_CONTENT_BYTES_INDEXED=100_000)` используется и для индексации, и для выдачи snippet'ов в matches/regions. При max_file_size=1_000_000 агент может не увидеть совпадения в конце большого файла.
4. **_search_python_walk пере-перевычисляет rel (F8):** вызывает iter_searchable_files с `subdir` как корнем обхода, затем всё равно перевычисляет rel относительно root. Проще: передавать root в iter_searchable_files и применять subdir_rel через единый _passes_filters.
5. **Двойной обход ФС в search() после пустого FTS:** при пустом BM25+trigram запускается _search_python_walk, который снова проходит по всем файлам. Не чиним в этом патче (корректность не страдает), но оставляем комментарий о TODO.
6. **Stale caller в subagent_prompts._get_fts_files** создаёт эфемерный SearchIndex на каждый вызов. Модульное состояние refresh (F2) спасёт его от дублирующих refresh.

### TO-BE (машинно-проверяемые факты)

После применения S1–S10:
- Path containment: is_relative_to на _resolve_subdir + в search() как D-in-D + в _collect_matches как D-in-D; любой обход → PermissionError → ToolResult.fail("path_escape", ..., retryable=True).
- LIKE: все места используют `_escape_like() + ESCAPE '\'`; запросы с % _ \ не wildcard'ят.
- FTS: `_escape_fts_query` конструирует корректное MATCH-выражение (AND токенов, с сохранением phrase-кавычек и trailing-*); невалидный синтаксис не роняет систему → OperationalError ловится → fall back на trigram/walk.
- Filters: _passes_filters вызывается из BM25-post, trigram-post, _search_python_walk, и _collect_matches (D-in-D). exclude_set = frozenset; include_tests проверка через `"tests" not in parts` (совпадает с текущим поведением).
- Refresh: ensure_indexed вызывается на каждом fs_search-вызове (после фикса F1); внутри себя:
  1. Проверяет module-level _refresh_state по ключу.
  2. Если полный индекс не делался в этом процессе → _do_full_index.
  3. Иначе: canary-stat; если canary совпали и не прошёл throttle → return SearchStats() (empty, fast path).
  4. Иначе: _do_quick_refresh.
  - Canary fast path не делает ни одного SQL read/write (только os.stat на 2–3 файла).
- Glob: _path_matches использует PurePosixPath.match + basename-fnmatch fallback; SQL _path_like только subdir prefix (без glob pushdown).
- Symlink: _safe_walk резолвит symlink и проверяет is_relative_to; _collect_matches перепроверяет; symlink cycles невозможны (followlinks=False).
- Binary: файлы с NUL в первых 8КБ не индексируются; stats.errors += 1.
- Encoding: UTF-8 strict → Latin-1 → None (skip on any failure).
- Match display: _read_text_for_match до MAX_MATCH_DISPLAY_BYTES (1MB), не MAX_CONTENT_BYTES_INDEXED.
- Тесты: ≥23 новых/обновлённых C1/C3 теста; каждый фикс имеет kill-check; полный pytest сохраняет те же 14 pre-existing фейлов.

---

## 3. Contracts (жесткие)

### CT1 — _resolve_subdir (G1/SEC-1/SEC-4)
```python
def _resolve_subdir(root: Path, subpath: str | None) -> Path:
    """Resolve subpath under root; raise PermissionError on escape.
    PRE : root is an existing directory Path; subpath is a user-supplied string (may be None/"").
    POST: returned Path p satisfies p.is_absolute() AND p.is_relative_to(root.resolve())
          (resolved form — symlinks resolved, ".." collapsed).
    RAISES PermissionError("path escapes workspace root: {subpath}") from None on escape.
    """
```
- **Mechanism:** `root_resolved = root.resolve(); subdir = (root_resolved / (subpath or ".")).resolve(); if not subdir.is_relative_to(root_resolved): raise ...`
- **Failure surface:** несуществующий subpath не является escape (возвращается несуществующий Path, вызовы is_file/is_dir вернут False, поиск даст 0 результатов; NOT path_escape).
- **Kill-check:** восстановить str.startswith → T-SIBLING-ESCAPE фейлится (получаем search_failed 500 или результаты).

### CT2 — _escape_like (G2/SEC-2)
```python
@staticmethod
def _escape_like(text: str, esc: str = "\\") -> str:
    """Escape LIKE meta-characters so the returned string matches text literally.
    POST: when used as the right-hand side of a SQL LIKE with ESCAPE '<esc>',
          it matches exactly the input text (%, _, esc act as literals).
    """
```
- **Mechanism:** `text.replace(esc, esc+esc).replace("%", esc+"%").replace("_", esc+"_")` (esc первым!).
- **PURE:** yes.
- **Kill-check:** сделать identity → T-LIKE-ESCAPE-PERCENT фейлится.

### CT3 — _passes_filters (G3/SEC-3/SEC-4)
```python
@staticmethod
def _passes_filters(
    rel: str,
    *,
    subdir_rel: str,                 # "" or "dir/dir/" with trailing "/"
    glob_pat: str | None,
    include_tests: bool,
    exclude_set: frozenset[str],
) -> bool:
    """Single authority for query filters.
    PRE : rel is POSIX relative path from root, no leading "./", uses "/".
    POST: returns True iff ALL:
        1. not subdir_rel OR (rel + "/").startswith(subdir_rel) OR rel == subdir_rel.rstrip("/")
        2. include_tests OR "tests" not in Path(rel).parts
        3. exclude_set.isdisjoint(Path(rel).parts)
        4. glob_pat is None OR _path_matches(rel, glob_pat)
    """
```
- **PURE:** yes.
- **Call sites:** `_search_bm25` post-fetch, `_search_trigram` post-fetch, `_search_python_walk` pre-yield, `_collect_matches` D-in-D.
- **Kill-check:** убрать exclude_set branch → T-EXCLUDE-DIRS-BM25 фейлится; skip D-in-D в _collect_matches → T-STALE-SYMLINK фейлится.

### CT4 — ensure_indexed + canary/throttle (G4)
```python
def ensure_indexed(self,
    root: Path,
    *,
    patterns: tuple[str, ...] = DEFAULT_PATTERNS,
    extra_exclude_dirs: frozenset[str] | None = None,
    include_tests: bool = True,
    max_file_size: int = MAX_CONTENT_BYTES_INDEXED,
    force: bool = False,
) -> SearchStats:
    """Idempotent lazy index build + bounded-budget incremental refresh.
    POST:
        - If _refresh_state[key].full_index_done is False OR force:
            run _do_full_index(...) — full walk, populate files_fts + files_fts_bm25 + fts_meta,
            clean stale, commit, set full_index_done=True.
        - Else:
            canary = _stat_canaries(root)
            if not force and throttle-not-expired and canary == last_canary:
                return SearchStats()   # FAST PATH — no walk, no SQL writes.
            else:
                _do_quick_refresh(...) — walk with mtime/size compare, upsert changed,
                delete stale (DELETE only where not (root/rel).is_file()), commit,
                update last_canary and last_mono.
    """
```
- **Canary stat:** кортеж mtime для (root, .git/index, .git/FETCH_HEAD). Несуществующие пути → 0.0. Никогда не поднимает OSError (try/except).
- **Throttle:** `time.monotonic() - state["last_mono"] < REFRESH_THROTTLE_SECONDS`. После full_index и quick_refresh — обновить.
- **Quick-refresh пропускает чтение контента** при совпадении (mtime, size) с fts_meta.
- **Stale cleanup** удаляет только строки fts_meta, для которых `(root/rel).is_file()` возвращает False (или возбуждает OSError → трактовать как отсутствие).
- **Kill-check:** always-refresh (skip canary check) → T-CANARY-FASTPATH не проходит (spy на iter_searchable_files показывает вызов); skip stale-delete → T-DELETED-FILE фейлится.

### CT5 — _path_matches (G5)
```python
@staticmethod
def _path_matches(rel: str, glob_pat: str | None) -> bool:
    """POSIX glob matching; **-aware; bare-name convenience for patterns without '/'.
    POST:
      if glob_pat is None → True
      else → PurePosixPath(rel).match(glob_pat)
           OR ('/' not in glob_pat and fnmatch(PurePosixPath(rel).name, glob_pat))
    """
```
- subdir_rel больше не принимает (это работа _passes_filters).
- **Kill-check:** убрать PurePosixPath.match → T-GLOB-DOUBLESTAR фейлится; убрать basename fallback → T-GLOB-BARE-EXT фейлится.

### CT6 — _escape_fts_query (G6)
```python
@staticmethod
def _escape_fts_query(query: str) -> str:
    """Construct a safe FTS5 MATCH rhs implementing implicit-AND semantics.
    POST: returns a string that is always a valid FTS5 MATCH expression where
        - whitespace-separated bare tokens are AND-joined (implicit FTS5 AND);
        - each bare token is wrapped in "..." to escape FTS5 operators,
          with trailing "*" preserved as a prefix operator OUTSIDE quotes:
          e.g. auth* -> "auth"*;
        - user-quoted phrases "..." are preserved verbatim with embedded " doubled;
        - unmatched open quote is auto-closed at end of input.
    EXAMPLES:
        auth middleware         -> "auth" "middleware"
        "auth middleware"       -> "auth middleware"
        auth*                   -> "auth"*
        hello "world peace" now -> "hello" "world peace" "now"
        he"llo                  -> "he""llo"
        foo (bar) baz           -> "foo" "(" "bar" ")" "baz"   (operators treated as literal)
    """
```
- **PURE:** yes.
- **Mechanism:** state machine (i=0..n): skip whitespace; if chr == '"' enter phrase mode (scan to closing ", удваивая вложенные "); иначе сканить до пробела/кавычки; если токен оканчивается на *, отделить префикс и вынести * за кавычки.
- **Do-not:** не поддерживать AND/OR/NOT/NEAR/колонки явно (всё заворачивается в кавычки как литералы); не ломать на синтаксических ошибках (мы сами всегда генерируем валидный синтаксис, но FTS5 может ругнуться на особые случаи — они ловятся try/except на execute и возвращают [], подключая trigram fallback).
- **Kill-check:** восстановить wrap-all → T-MULTITERM-BM25 фейлится.

### CT7 — _read_bytes_for_index / _read_text_for_match (G7)
```python
@staticmethod
def _is_binary(sample: bytes) -> bool:
    """Return True if the byte sample contains a NUL (binary file heuristic)."""
    return b"\x00" in sample

@staticmethod
def _read_bytes(fp: Path, max_bytes: int) -> bytes | None:
    """Read up to max_bytes; return None on OSError."""

@staticmethod
def _read_text_for_index(fp: Path) -> str | None:
    """Read up to MAX_CONTENT_BYTES_INDEXED for FTS.
    - Returns None (skip) if file looks binary (NUL in first BINARY_SNIFF_BYTES bytes).
    - Decodes UTF-8 strict; on failure falls back to Latin-1 (never fails).
    - Returns None only on binary detection or IO error.
    """

@staticmethod
def _read_text_for_match(fp: Path, max_bytes: int) -> str:
    """Read up to max_bytes for snippet/context display.
    - Does NOT binary-sniff (if we're here the file already passed filters).
    - UTF-8 strict → Latin-1 fallback; on IO error returns "".
    """
```
- **Kill-check:** убрать NUL sniff → T-BINARY-SKIPPED фейлится.

### CT8 — _path_is_excluded (G8/H2)
```python
def _path_is_excluded(
    parts: tuple[str, ...],
    extra_exclude_dirs: frozenset[str] = frozenset(),
) -> bool:
    """Return True if any path component is in (BASE ∪ EXTRA ∪ extra_exclude_dirs)
    or matches any EXCLUDE_DIR_GLOBS via fnmatch.
    """
```
- Called from **обеих** веток iter_searchable_files (git + walk). Walk-ветка дополнительно in-place prune dirnames с тем же effective_exclude для производительности.
- **Kill-check:** убрать extra_exclude_dirs параметр → T-SAFE-WALK-GIT-EXTRA-EXCLUDE фейлится.

---

## 4. Path inventory (P1–P21) + flag matrix unchanged from v2
(Оставлены; все пути по-прежнему покрыты; добавлены пути для быстрого canary path и module-state access.)

---

## 5. Step-by-step implementation (карточки, в исполнительном порядке)

**Порядок: чистые хелперы сначала (S2, S3, S5, S6) → безопасный обход (S7) → ядро индекса (S1) → handler-контур (S4) → тесты (S8, S9) → финальная верификация (S10).**

Перед каждым шагом:
- Доклад по шаблону: intent / current→target / mechanism / rationale / failure / DoD / negative proof / test-class / kill-check.
- После правки: `py_compile`, `ruff check`, `mypy --ignore-missing-imports`, целевой pytest, `git diff` инспекция.
- После каждого значимого шага: mutation kill-check (временно откатить fix, убедиться что новый тест краснеет, вернуть fix).

---

### Step S1 (core, P1/P2/P3/P4/P5/P7) — ensure_indexed split + canary + throttle + fix F1/F2/F6
**Traces-to:** G4, CT4, F1, F2, F6
**Files:** `src/fa/memory/search_index.py`, `src/fa/inner_loop/tools/fs_search.py` (последнюю чиним одновременно с F1 — холдер должен вызывать ensure_indexed на КАЖДЫЙ вызов).

**Edit A — `src/fa/memory/search_index.py` (top-of-file + __init__ + ensure_indexed):**

1. Добавить импорты: `import time` (для monotonic).
2. Добавить module-level константы и refresh state (§1).
3. В `SearchIndex.__init__`: убрать `self._indexed_for_session` (флаг переезжает в module-level _refresh_state). Оставить только `self.db_path`, `self._conn`, `self._available`.
4. Добавить приватные методы:
   - `_state_key(self, root: Path) -> str`: `f"{self.db_path}::{root.resolve()}"`.
   - `_stat_canaries(self, root: Path) -> tuple[float, ...]`: для (root, root/".git/index", root/".git/FETCH_HEAD") вернуть (mtime, ...); при OSError возвращать 0.0 для этого канала.
   - `_do_full_index(self, root, patterns, extra_exclude_dirs, include_tests, max_file_size, stats) -> None`: вынести текущее тело ensure_indexed (walk loop + stale cleanup + commit). Использовать _read_text_for_index (S3) вместо прямого read_text.
   - `_cleanup_stale_files(self, root, seen: set[str], stats) -> None`: общая для full/quick; выполняет DELETE для rel из fts_meta, где rel not in seen или не (root/rel).is_file().
   - `_do_quick_refresh(self, root, patterns, extra_exclude_dirs, include_tests, max_file_size, stats) -> None`: как описано в CT4; использует _read_text_for_index; обновляет stats.indexed/updated/skipped/errors.
5. Переписать public `ensure_indexed` в соответствии с CT4 (canary-first, throttle, full-index-sentinel в module state).
6. Сохранить `_connect()` неизменным (timeout=10, PRAGMA journal_mode=WAL, synchronous=NORMAL — это всё уже в коде).
7. Добавить комментарий над _migrate о F11 (schema collision с InstantGrepIndex — intentional).

**Edit B — `src/fa/inner_loop/tools/fs_search.py` (_ensure_index):**

Заменить текущую функцию:
```python
def _ensure_index(holder, root, max_file_size, warnings):
    if holder._indexed:
        return None
    ...
```
на:
```python
def _ensure_index(holder, root, max_file_size, warnings):
    """Ensure index is built and (if needed) quick-refreshed.
    Called on EVERY fs_search invocation; ensure_indexed's internal canary/throttle
    keeps steady-state cost to a few stat syscalls (<5ms).
    """
    try:
        index = holder.get()
    except Exception as exc:  # noqa: BLE001 - INV-HARDEN-5
        logger.warning("fs_search index unavailable: %s", exc)
        warnings.append(f"FTS index unavailable ({exc}); using streaming fallback")
        holder._indexed = False
        return None
    try:
        stats = index.ensure_indexed(
            root,
            include_tests=True,     # index superset; query-time filter in _passes_filters
            max_file_size=max_file_size,
        )
        holder._indexed = True
        return {
            "indexed": stats.indexed,
            "updated": stats.updated,
            "skipped": stats.skipped,
            "errors": stats.errors,
            "total_candidates": stats.total_candidates,
        }
    except Exception as exc:  # noqa: BLE001 - INV-HARDEN-5
        logger.warning("fs_search indexing failed: %s", exc)
        warnings.append(f"index build/refresh failed ({exc}); using streaming fallback")
        holder._indexed = False
        return None
```
- Ключевое: нет раннего возврата по `holder._indexed`. holder._indexed лишь отражает, что _last_ ensure_indexed не фейльнулся (используется в _handle для выбора indexed-vs-fallback пути).

**Edit C — `src/fa/inner_loop/tools/fs_search.py` (_handle):** убрать дублирующий трай-кэтч? Нет, оставить outer BLE001 на _do_indexed_search как сейчас (INV-HARDEN-5). Единственное изменение — _ensure_index вызывается всегда.

**Do-not:**
- Не запускать refresh в фоновом потоке.
- Не читать содержимое при совпадении (mtime, size).
- Не менять SCHEMA_VERSION; не делать миграций.
- Не поднимать новые исключения из quick-refresh; любая ошибка → self._available=False, rollback, walk-fallback.

**Exit criteria:**
- [ ] py_compile search_index.py, fs_search.py.
- [ ] ruff, mypy чисто.
- [ ] T-FIRST (cold start: index_stats.indexed ≥ 1).
- [ ] T-CANARY-FASTPATH (второй вызов сразу после первого; spy на iter_searchable_files не регистрирует вызов; wall <20мс; index_stats.skipped == 0, indexed == 0).
- [ ] T-THROTTLE (принудительный canary-miss через touch .git/index + monotonic patch до throttle-окна → walk не запускается).
- [ ] T-REFRESH (touch .git/index, промотать mono за throttle, добавить файл с уникальным токеном → BM25 находит).
- [ ] T-NEW-FILE, T-MODIFIED-FILE, T-DELETED-FILE.
- [ ] T-EPHEMERAL-INSTANCE-REFRESH-CACHE (создать SearchIndex дважды подряд; второй экземпляр использует canary fast path, не запуская walk — проверить через spy на iter_searchable_files).

**Kill-check:**
- Поставить `if holder._indexed: return None` обратно в _ensure_index → T-NEW-FILE/T-REFRESH фейлятся (холдер шортсёркит).
- Поставить `return SearchStats()` перед canary-обновлением (всегда fast-path) → T-NEW-FILE фейлится.
- Убрать stale-cleanup → T-DELETED-FILE фейлится.
- Убрать module-level _refresh_state (хранить в self) → T-EPHEMERAL-INSTANCE-REFRESH-CACHE фейлится.

---

### Step S2 (pure helpers, parallel-ready) — _escape_like + _escape_fts_query rewrite; simplify _path_like
**Traces-to:** G2, G6, CT2, CT6, F4
**Files:** `src/fa/memory/search_index.py`
**Depends-on:** none (чистые статики).

**Edit:**
1. Добавить `_escape_like` static (см. CT2).
2. Переписать `_escape_fts_query` согласно CT6 (токенайзер с состоянием; оборачивать bare tokens в кавычки, сохранять trailing `*` за кавычкой, удваивать внутренние `"`, авто-закрывать незакрытую фразу).
3. Упростить `_path_like` до subdir-prefix only:
   ```python
   @staticmethod
   def _path_like(subdir_rel: str) -> str:
       """SQL LIKE for subdir prefix pushdown (authoritative glob filtering post-fetch).
       Returns a LIKE pattern that matches all paths under subdir_rel (including subdir_rel itself
       when it is ""). All literal text is LIKE-escaped; no user data flows here un-escaped.
       """
       if not subdir_rel:
           return "%"
       return SearchIndex._escape_like(subdir_rel) + "%"
   ```
4. Обновить оба места вызова _path_like:
   - `_search_bm25`: params.append(self._path_like(subdir_rel)) (второй аргумент glob_pat — убрать).
   - `_search_trigram`: аналогично.
5. Обновить trigram LIKE:
   ```python
   like = f"%{SearchIndex._escape_like(query)}%"
   sql += "AND content LIKE ? ESCAPE '\\' "
   ```
6. В BM25 path LIKE тоже добавить `ESCAPE '\\'`.

**Do-not:**
- Не пытаться транслировать glob в LIKE (pushdown hint удалён как опасный и не дающий выигрыша при пост-фильтрации).
- Не поддерживать явные FTS операторы (AND/OR/NOT/колонки/NEAR) — всё заворачиваем в литералы.

**Exit criteria:**
- [ ] py_compile, ruff, mypy.
- [ ] T-LIKE-ESCAPE-PERCENT (query="%" → 0 результатов в фикстуре без "%").
- [ ] T-LIKE-ESCAPE-LITERAL (файл с "100%" находится по query "100%").
- [ ] T-LIKE-ESCAPE-UNDERSCORE (query="_" не возвращает все файлы).
- [ ] T-LIKE-BACKSLASH (query="\\" трактуется как literal).
- [ ] T-MULTITERM-BM25 ("auth middleware" находит файл с подписью и токенами не подряд, method="fts5_bm25").
- [ ] T-PHRASE-QUOTED ('"Authentication Middleware"' находит только точную фразу, не разрозненные вхождения).
- [ ] T-PREFIX-STAR (query="auth*" → method="fts5_bm25", не только trigram).
- [ ] T-WEIRD-CHARS (query="(" / ")/" / "a:b/c" не крашит и что-то возвращает или 0 — не error).

**Kill-check:** identity _escape_like → T-LIKE-ESCAPE-PERCENT фейлится. Restore wrap-all-quotes in _escape_fts_query → T-MULTITERM-BM25 фейлится.

---

### Step S3 (pure helpers) — _read_bytes_for_index / _is_binary / _read_text_for_index / _read_text_for_match; fix F3
**Traces-to:** G7, CT7, F3
**Files:** `src/fa/memory/search_index.py`

**Edit:**
1. Добавить `_is_binary` static (b"\x00" in sample).
2. Заменить `_read_file_text` на два метода:
   - `_read_bytes(fp, max_bytes)`: читать до max_bytes байт; при OSError возвращать None.
   - `_read_text_for_index(fp)`: реализация по CT7 (NUL-sniff на первых BINARY_SNIFF_BYTES; UTF-8 strict; Latin-1 fallback; cap MAX_CONTENT_BYTES_INDEXED).
   - `_read_text_for_match(fp, max_bytes)`: до max_bytes; UTF-8 → Latin-1 → "" при ошибке; нет binary-sniff.
3. Обновить вызовы:
   - `_do_full_index` / `_do_quick_refresh` — использовать `_read_text_for_index`.
   - `_scan_file_matches` — принимать `text: str` как аргумент (caller читает).
   - `_collect_matches` — читать через `self._read_text_for_match(fp, max_file_size_display)`; вычислить max_file_size_display из параметра (протянуть max_file_size через сигнатуру).
   - `_build_matches_output` и `_build_regions_output` — использовать `_read_text_for_match(root/rel, max_bytes)`; протянуть max_bytes из search() через _format_hits → _build_*_output.
4. Сохранить `SNIPPET_MAX_BYTES` как cap на отдельно взятый snippet (применяется в _build_files_output, _build_matches_output).

**Do-not:**
- Не использовать chardet/cchardet.
- Не поднимать UnicodeDecodeError; латин-1 всегда сработает.
- Не индексировать файлы с NUL — они дают мусор в BM25.

**Exit criteria:**
- [ ] py_compile, ruff, mypy.
- [ ] T-BINARY-SKIPPED (файл с NUL в первых 8КБ + уникальный токен → токен не находится через любой метод).
- [ ] T-LATIN1-INDEXED (cp1251 файл с "привет" находится по query "привет").
- [ ] T-LARGE-FILE-MATCH (файл 500KB с уникальным токеном в конце → находит через matches-режим, не пропускает из-за 100KB cap).

**Kill-check:** убрать NUL-sniff → T-BINARY-SKIPPED фейлится; оставить cap 100KB на snippet-read → T-LARGE-FILE-MATCH фейлится.

---

### Step S4 (containment) — _resolve_subdir fix + subagent D-in-D comment; keep search() containment as D-in-D
**Traces-to:** G1, CT1, F5, F10
**Files:** `src/fa/inner_loop/tools/fs_search.py`, `src/fa/memory/search_index.py`

**Edit A (fs_search.py):**
Заменить _resolve_subdir на:
```python
def _resolve_subdir(root: Path, subpath: str | None) -> Path:
    """Resolve subpath under root; raise PermissionError on escape.
    Uses pathlib.is_relative_to on both resolved paths — canonical POSIX containment.
    Correctly handles sibling-prefix attacks (e.g. root='/work', subpath='../work-secret'),
    case-insensitive filesystems, and symlinks (both sides are resolve()d).
    Non-existent subpaths are NOT treated as escape — downstream stat/open will simply
    find 0 files, which matches ripgrep semantics.
    """
    if not subpath:
        subpath = "."
    root_resolved = root.resolve()
    subdir = (root_resolved / subpath).resolve()
    if not subdir.is_relative_to(root_resolved):
        raise PermissionError(f"path escapes workspace root: {subpath}") from None
    return subdir
```

**Edit B (search_index.py):**
В `search()` сохранить существующий try/except ValueError вокруг `subdir.relative_to(root)` как **defense-in-depth** для прямых потребителей (subagent_prompts) и добавить комментарий:
```python
# Defense-in-depth for direct callers (e.g. subagent_prompts._get_fts_files) that do not
# go through fs_search._resolve_subdir. The fs_search tool also validates at the handler
# level; this is a second safety net.
try:
    subdir.relative_to(root)
except ValueError:
    return SearchResult(
        query=query,
        method="literal_fallback",
        warnings=[f"path escapes workspace root: {subpath}"],
    )
```

**Edit C (search_index.py — _collect_matches D-in-D, F11 SEC-6):**
Перед чтением `fp = root / rel`:
```python
try:
    resolved = fp.resolve()
    if not resolved.is_relative_to(root):
        logger.warning("skipping indexed path outside root (stale/symlink): %s", rel)
        continue
    if not resolved.is_file():
        continue
except OSError as exc:
    logger.warning("stat failed for %s: %s", rel, exc)
    continue
```
(Заменяет текущий простой `if not fp.is_file(): continue`.)

**Edit D (_do_indexed_search simplification):**
Убрать спец-ветку `if subdir == root`:
```python
subpath_arg = subdir.relative_to(root).as_posix() or "."
```
(downstream _resolve_subdir в search() уже умеет ".")

**Do-not:**
- Не использовать os.path.commonpath.
- Не использовать str.startswith.
- Не санизировать путь удалением ".." вручную.
- Не менять текст ошибки "path escapes workspace root:" (на него завязаны тесты и ожидания оператора).

**Exit criteria:**
- [ ] py_compile, ruff, mypy.
- [ ] T-SIBLING-ESCAPE (sibling-prefix → path_escape).
- [ ] T-PATH-ESCAPE-CODE (классика ../../etc → path_escape, не search_failed).
- [ ] T-STALE-SYMLINK (создаём файл, индексируем, заменяем на symlink за границу, ищем → 0 утечек).
- [ ] T-NONEXISTENT-SUBPATH (несуществующая директория → 0 результатов, не path_escape, не ошибка).
- [ ] Существующий test_fs_search_rejects_path_escape по-прежнему зелёный.

**Kill-check:** восстановить str.startswith → T-SIBLING-ESCAPE фейлится. Убрать D-in-D в _collect_matches → T-STALE-SYMLINK фейлится.

---

### Step S5 (filter authority) — _passes_filters and route all hits through it; fix F8
**Traces-to:** G3, CT3, C2, F8
**Files:** `src/fa/memory/search_index.py`

**Edit:**
1. Добавить `_passes_filters` static по CT3.
2. Изменить сигнатуры `_search_bm25(self, query, *, limit, subdir_rel, glob_pat, include_tests, exclude_set)` и `_search_trigram(...)` — добавить `include_tests: bool, exclude_set: frozenset[str]`.
3. Внутри них: убрать инлайн-проверки поддиректории и glob; после fetch каждой строки:
   ```python
   if not self._passes_filters(rel, subdir_rel=subdir_rel, glob_pat=glob_pat,
                                include_tests=include_tests, exclude_set=exclude_set):
       continue
   ```
4. Убрать include_tests фильтрацию из `search()` (которая сейчас дублируется на строках ~498-510).
5. В `search()`: один раз конвертировать `exclude_dirs` в `exclude_set = frozenset(exclude_dirs or [])`; передавать во все три метода.
6. В `_search_python_walk`:
   - Вызывать `iter_searchable_files(root, ...)` (всегда от root; исправляет F8 — нет двойной релятивизации).
   - Убрать ручную поддиректорию/проверки glob; использовать _passes_filters.
   - Для производительности — по-прежнему передавать extra_exclude_dirs и include_tests в iter_searchable_files (walk-time prune).
   - Убрать строку `rel = str(fp.resolve().relative_to(root))` — rel уже приходит из iter_searchable_files в root-относительной POSIX форме.
7. Проверки include_tests и extra_exclude в iter_searchable_files остаются как early-prune; _passes_filters — семантический авторитет и для git-ветки, и для walk-ветки.

**Do-not:**
- Не пушить exclude_dirs в SQL (поддерживать в Python для единообразия; LIKE pushdown только для subdir prefix).
- Не убирать walk-time prune в iter_searchable_files (большой выигрыш на больших репо).

**Exit criteria:**
- [ ] py_compile, ruff, mypy.
- [ ] T-EXCLUDE-DIRS-BM25 (exclude_dirs=["vendored"], уникальный токен только в vendored/v.py → 0 через FTS).
- [ ] T-EXCLUDE-DIRS-TRIGRAM (аналогично, но принудительно через trigram: триграмма-специфичный токен).
- [ ] T-EXCLUDE-DIRS-WALK (regex=True для принудительного walk → то же поведение).
- [ ] T-UNIFORM-FILTERS (параметризованный: все комбинации output_mode × include_tests × exclude × glob × subpath × regex дают консистентный набор путей, независимо от того, какой метод их вернул).

**Kill-check:** убрать exclude_set проверку из _passes_filters → T-EXCLUDE-DIRS-BM25 фейлится.

---

### Step S6 (glob) — _path_matches rewrite (PurePosixPath + basename convenience)
**Traces-to:** G5, CT5, F7
**Files:** `src/fa/memory/search_index.py`

**Edit:**
Переписать _path_matches по CT5:
```python
@staticmethod
def _path_matches(rel: str, glob_pat: str | None) -> bool:
    if not glob_pat:
        return True
    from pathlib import PurePosixPath
    rel_path = PurePosixPath(rel)
    if rel_path.match(glob_pat):
        return True
    # Bare-name convenience: patterns without '/' match against the basename too
    # (so "*.py" matches at any depth, like ripgrep/IDE search).
    if "/" not in glob_pat and _fnmatch.fnmatch(rel_path.name, glob_pat):
        return True
    return False
```
- Удалить старый параметр `subdir_rel` из _path_matches (он теперь в _passes_filters).
- Обновить все вызовы (в BM25/trigram post-filter больше не вызывается напрямую — только через _passes_filters).

**Do-not:**
- Не использовать `Path.match()` (OS-native, ломается на Windows-разделителях).
- Не добавлять brace/extglob.

**Exit criteria:**
- [ ] T-GLOB-DOUBLESTAR (glob="src/**/*.py" находит src/a.py, src/sub/a.py, src/sub/deep/a.py).
- [ ] T-GLOB-BARE-EXT (glob="*.py" находит .py файлы на любой глубине).
- [ ] T-GLOB-SINGLE-LEVEL (glob="src/*.py" НЕ находит src/sub/a.py).
- [ ] Существующий test_fs_search_glob_filters_by_path_pattern остаётся зелёным.

**Kill-check:** убрать PurePosixPath.match → T-GLOB-DOUBLESTAR фейлится; убрать basename → T-GLOB-BARE-EXT фейлится.

---

### Step S7 (safe_walk) — _path_is_excluded signature; wire extra_exclude_dirs through git branch
**Traces-to:** G8, H2, CT8
**Files:** `src/fa/memory/_safe_walk.py`

**Edit:**
1. Расширить сигнатуру `_path_is_excluded(rel_parts, extra_exclude_dirs=frozenset())` по CT8; слить extra_exclude_dirs в effective set.
2. В git-ls-files ветке `iter_searchable_files`: вызывать `_path_is_excluded(parts, effective_exclude)` (effective_exclude уже вычислен выше).
3. В os.walk ветке: текущий in-place prune уже использует `effective_exclude` (включает extra_exclude_dirs и "tests"); оставить как есть для производительности и добавить комментарий, что он совпадает с _path_is_excluded.
4. Убедиться, что EXCLUDE_DIR_GLOBS проверяются в обеих ветках (git — через _path_is_excluded; walk — через prune).

**Exit criteria:**
- [ ] py_compile, ruff, mypy.
- [ ] T-SAFE-WALK-GIT-EXTRA-EXCLUDE (git init в tmp_path, mkdir buildout, buildout/x.py с уникальным токеном, git add -A; вызываем iter_searchable_files с extra_exclude_dirs=frozenset({"buildout"}) → buildout/x.py не выдаётся ни через git-fast-path).
- [ ] T-SAFE-WALK-GIT-GLOBS (создать fa.egg-info/PKG-INFO с уникальным токеном; git add; не должно выдаваться в git-ветке).
- [ ] Существующий test_iter_searchable_files_respects_extra_exclude_dirs (осыпается в os.walk из-за отсутствия .git) остаётся зелёным.

**Kill-check:** вернуть старую сигнатуру без extra_exclude_dirs → T-SAFE-WALK-GIT-EXTRA-EXCLUDE фейлится.

---

### Step S8 — Existing test updates
**Files:** `tests/test_fs_search.py`

1. `test_fs_search_second_call_does_not_reindex` переименовать в `test_fs_search_second_call_uses_canary_fast_path` и переписать под новый контракт:
   - первый вызов: index_stats is not None, indexed ≥ 1.
   - второй вызов сразу после первого: index_stats is not None (больше не None! это была баг-документация), indexed == 0, updated == 0, wall <20мс.
2. `test_fs_search_symlink_escape_blocked` переделать на sibling tmp-файл (F9):
   ```python
   outside = tmp_path.parent / f"outside_{uuid.uuid4().hex}.txt"
   outside.write_text("OUTSIDE_SECRET_TOKEN", encoding="utf-8")
   link = tmp_path / "src" / "escape_link"
   link.symlink_to(outside)
   ```
   Искать "OUTSIDE_SECRET_TOKEN" — не должно находиться.
3. Удалить зависимость от /etc/passwd.

---

### Step S9 — New regression tests
Подробный перечень тестов (имя, класс, оракул, paths covered):

| Test ID | Class | Asserts |
|---|---|---|
| T-SIBLING-ESCAPE | C3 | path="../<sibling-prefix-of-rootname>" → error.code=="path_escape" |
| T-PATH-ESCAPE-CODE | C1 | `../../etc` → code "path_escape" (не search_failed) |
| T-NONEXISTENT-SUBPATH | C1 | path="does_not_exist/" → 0 результатов, не ошибка |
| T-STALE-SYMLINK | C3 | индексируем файл, заменяем на symlink-out → 0 утечек контента через D-in-D |
| T-LIKE-ESCAPE-PERCENT | C3 | query="%" → 0 файлов, если нет literal "%" |
| T-LIKE-ESCAPE-LITERAL | C1 | файл с "100%" находится по query "100%" через trigram/fts |
| T-LIKE-ESCAPE-UNDERSCORE | C3 | query="_" не возвращает все файлы |
| T-LIKE-BACKSLASH | C1 | query="\\" не ломает SQL; literal match работает |
| T-EXCLUDE-DIRS-BM25 | C1 | exclude_dirs=["vendored"] → 0 из vendored/ через fts5_bm25 |
| T-EXCLUDE-DIRS-TRIGRAM | C1 | то же через trigram (уникальный токен, который не бьётся в BM25 из-за размера токенизатора) |
| T-EXCLUDE-DIRS-WALK | C1 | regex=True → то же через walk |
| T-UNIFORM-FILTERS | C2 | parametrize по output_mode × include_tests × exclude × glob × subpath × regex: инвариант "ни один путь результата не нарушает фильтр" |
| T-FIRST | C1 | холодный старт → index_stats.indexed ≥ 1 |
| T-CANARY-FASTPATH | C1 | второй вызов сразу после первого; spy iter_searchable_files не вызывается; wall <20мс |
| T-THROTTLE | C1 | canary-miss, но mono внутри throttle-окна → walk не запущен |
| T-REFRESH | C1 | canary-miss + throttle expired → quick refresh подхватывает новый файл |
| T-NEW-FILE | C1 | новый файл после истечения trottle найден через fts5_bm25 |
| T-MODIFIED-FILE | C1 | в существующий файл дописываем уникальный токен → найден через FTS |
| T-DELETED-FILE | C1 | файл удаляем → не возвращается |
| T-EPHEMERAL-INSTANCE-REFRESH-CACHE | C1 | второй экземпляр SearchIndex на том же db/root использует кэш canary (spy на iter_searchable_files не вызывается) |
| T-BINARY-SKIPPED | C1 | файл с NUL в первых 8КБ не индексируется; уникальный токен в нём не ищется |
| T-LATIN1-INDEXED | C1 | cp1251 файл с акцентами/кириллицей ищется |
| T-LARGE-FILE-MATCH | C1 | уникальный токен в позиции 500КБ файла (при max_file_size=1_000_000) находится в matches-режиме |
| T-GLOB-DOUBLESTAR | C1 | "src/**/*.py" на глубине 1,2,3 |
| T-GLOB-BARE-EXT | C1 | "*.py" на любой глубине |
| T-GLOB-SINGLE-LEVEL | C1 | "src/*.py" не включает глубину 2 |
| T-MULTITERM-BM25 | C1 | "auth middleware" находит файл с разрозненными токенами через fts5_bm25 |
| T-PHRASE-QUOTED | C1 | '"Authentication Middleware"' только точная фраза |
| T-PREFIX-STAR | C1 | "auth*" через fts5_bm25 |
| T-WEIRD-CHARS | C1 | запросы "(" / "a:b/c" / "foo[bar]" не ломают и не поднимают исключения |
| T-SAFE-WALK-GIT-EXTRA-EXCLUDE | C3 | extra_exclude_dirs в git-ветке |
| T-SAFE-WALK-GIT-GLOBS | C1 | *.egg-info не выдаётся в git-ветке |
| T-NO-ABSOLUTE-PATHS | C3 | ни в одном результате rel не начинается с "/" и не содержит ".." |

Все тесты добавляются в `tests/test_fs_search.py` (кроме T-SAFE-WALK-*, которые в `tests/test_safe_walk.py`).

**Style note:** использовать `_mk_tool(tmp_path)` и расширенный `_populate_sample_repo` с поддиректориями vendored/, src/sub/deep/, файлом с "%", бинарным файлом, cp1251 файлом, большим файлом. Там, где нужна реальная файловая система после первого индекса — трогать .git/index (или просто корневую директорию) и проматывать mono через monkeypatch, чтобы обеспечить срабатывание canary+throttle.

---

### Step S10 — Static gates, full test run, final patch + handoff
1. **py_compile** всех изменённых файлов:
   ```
   python3 -m py_compile src/fa/memory/_safe_walk.py src/fa/memory/search_index.py \
                         src/fa/inner_loop/tools/fs_search.py \
                         tests/test_fs_search.py tests/test_safe_walk.py
   ```
2. **ruff:**
   ```
   python3 -m ruff check src/fa/memory/_safe_walk.py src/fa/memory/search_index.py \
                          src/fa/inner_loop/tools/fs_search.py \
                          tests/test_fs_search.py tests/test_safe_walk.py
   ```
3. **mypy:**
   ```
   python3 -m mypy --ignore-missing-imports src/fa/memory/ src/fa/inner_loop/tools/fs_search.py
   ```
4. **Focused pytest:**
   ```
   PYTHONPATH=src python3 -m pytest tests/test_fs_search.py tests/test_safe_walk.py \
                                 tests/test_instant_grep.py \
                                 tests/test_blackboard_artifact_index.py \
                                 tests/test_blackboard_query_tool.py -v
   ```
5. **Full pytest:**
   ```
   PYTHONPATH=src python3 -m pytest tests/ -v 2>&1 | tee /tmp/pytest-full.log
   ```
   Сравнить список фейлов с базовыми 14-ю; допускается 0 новых.
6. **Mutation kill-check** всех 10-ти мутантов из §6 C4.
7. Обновить docstring/описание инструмента (fs_search.py _TOOL_DESCRIPTION):
   - Отметить что glob поддерживает `**` для рекурсии; bare `*.ext` совпадает на любой глубине.
   - Отметить что мульти-словные запросы ищут все слова (AND); точная фраза — в двойных кавычках.
8. Сгенерировать финальный патч:
   ```
   cd /home/user/First-Agent-dev
   git diff HEAD -- src/ tests/ AGENTS.md knowledge/ eval/ \
       > /home/user/s14b1-fs-search-unification.patch
   sha256sum /home/user/s14b1-fs-search-unification.patch
   ```

---

## 6. Verification (post-S10 gates)

### LIVE-PATH PROOF (продьюсер → потребитель → тест-оракул → kill-check)

| CT | Продьюсер (файл:символ) | Потребитель | Тест-оракул | Kill-check |
|---|---|---|---|---|
| CT1 (containment) | fs_search.py: _resolve_subdir | fs_search.py: _handle | T-SIBLING-ESCAPE: r.error.code=="path_escape" | вернуть str.startswith → тест падает |
| CT1-D-in-D | search_index.py: _collect_matches | _format_hits | T-STALE-SYMLINK: 0 утечек | убрать resolve+is_relative_to в _collect_matches → утечка |
| CT2 (LIKE) | search_index.py: _escape_like | _search_bm25, _search_trigram, _path_like | T-LIKE-ESCAPE-PERCENT: query="%" → 0 при отсутствии "%" | identity _escape_like → тест падает |
| CT3 (filters) | search_index.py: _passes_filters | BM25/trigram/walk/_collect_matches | T-UNIFORM-FILTERS: инвариант на матрице флагов | убрать exclude_set branch → T-EXCLUDE-DIRS-BM25 падает |
| CT4 (refresh) | search_index.py: ensure_indexed/_do_full_index/_do_quick_refresh/_stat_canaries | _ensure_index в fs_search.py, subagent_prompts._get_fts_files | T-CANARY-FASTPATH: <20мс, нет walk; T-NEW/MOD/DEL: изменения видны; T-THROTTLE: throttle соблюдается; T-EPHEMERAL-INSTANCE-*: кэш между экземплярами | всегда-fast-return → T-NEW-FILE падает; убрать stale cleanup → T-DELETED-FILE падает; вернуть early-return в _ensure_index → T-REFRESH падает |
| CT5 (glob) | search_index.py: _path_matches | _passes_filters | T-GLOB-DOUBLESTAR/BARE/SINGLE | убрать PurePosixPath.match → T-GLOB-DOUBLESTAR падает |
| CT6 (FTS) | search_index.py: _escape_fts_query | _search_bm25 | T-MULTITERM/PHRASE/PREFIX/WEIRD | восстановить wrap-all-quotes → T-MULTITERM падает |
| CT7 (binary/encoding) | search_index.py: _read_text_for_index/_is_binary | _do_full_index/_do_quick_refresh | T-BINARY-SKIPPED: бинарник не в индексе; T-LATIN1: latin-1 текст ищется; T-LARGE-FILE-MATCH: контент в конце большого файла ищется | убрать NUL sniff → T-BINARY падает; вернуть 100KB cap на snippet reads → T-LARGE-FILE-MATCH падает |
| CT8 (safe_walk) | _safe_walk.py: _path_is_excluded | iter_searchable_files (обе ветки) | T-SAFE-WALK-GIT-EXTRA-EXCLUDE; T-SAFE-WALK-GIT-GLOBS; существующий extra_exclude тест | вернуть старую сигнатуру → T-SAFE-WALK-GIT-EXTRA-EXCLUDE падает |

### C4 — Обязательная ручная мутация (после того как всё зелёное)

Все 10 мутаций обязаны дать красный тест:

1. Сделать `_escape_like = lambda text, esc="\\": text` (identity) → T-LIKE-ESCAPE-PERCENT fail.
2. Убрать exclude_set проверку из `_passes_filters` → T-EXCLUDE-DIRS-BM25 fail.
3. Убрать блок stale-cleanup в `_do_quick_refresh` → T-DELETED-FILE fail.
4. Заменить `PurePosixPath.match(glob_pat)` на `_fnmatch.fnmatch(rel, glob_pat)` (откат G5) → T-GLOB-DOUBLESTAR fail.
5. Заменить `is_relative_to` на строку startswith в _resolve_subdir → T-SIBLING-ESCAPE fail.
6. Вернуть wrap-all-quotes в _escape_fts_query → T-MULTITERM-BM25 fail.
7. Заставить _should_refresh всегда возвращать True (пропустить canary/throttle) → T-CANARY-FASTPATH fail (spy видит walk вызов).
8. Вернуть `if holder._indexed: return None` в _ensure_index → T-REFRESH fail.
9. Убрать бинарный NUL-sniff → T-BINARY-SKIPPED fail.
10. Убрать extra_exclude_dirs из сигнатуры _path_is_excluded → T-SAFE-WALK-GIT-EXTRA-EXCLUDE fail.

Любая «выжившая» мутация → усилить тест или поправить код.

---

## 7. Risks & rollback (обновлённые)

| RK# | Риск | L | I | Митигация |
|---|---|---|---|---|
| R1 | Quick-refresh на больших репо медленнее ожидаемого (холодный canary-miss) | M | M | throttle 5с + canary O(1) ограничивают частоту walk; если профилирование покажет проблему на монорепе — следующий патч добавит depth-1 directory mtime canary или увеличит throttle. Мониторим через index_stats. |
| R2 | PurePosixPath.match подводит на странных паттернах | L | L | Базовые паттерны покрыты тестами; сложные паттерны всегда могут быть переписаны пользователем через regex=true (walk). |
| R3 | FTS5 MATCH на экзотическом запросе поднимает OperationalError | M | L | _search_bm25 уже обёрнут try/except sqlite3.Error; в этом случае возвращается [] → триграмма-путь пытается снова, затем walk. T-WEIRD-CHARS ловит регрессии. |
| R4 | Canary пропускает изменения (файл добавлен в глубокой поддир-рии без обновления mtime корня и без .git/index) | M | M | Root mtime обновляется при создании/удалении записей в нём, но не в глубине. .git/index обновляется при git add и дружественных операциях, но не при «write_file из агента» напрямую (создаёт файл без git add). **Решение:** в canary включить также корневую директорию, но и этого может быть недостаточно для глубоких изменений. В RK4-mitigation: после завершения quick-refresh мы также обновляем canary на текущее значение; если же за 5 секунд агент написал файл, то ближайший вызов после истечения throttle сделает walk и всё равно найдёт. Худший случай — 5 секунд задержки перед тем как BM25 найдёт новый файл через индекс; **walk-fallback в search() найдёт файл мгновенно в этом же вызове** (потому что он идёт после FTS и если FTS вернул 0, то он сканирует ФС напрямую — текущее поведение, которое не меняем). Корректность не страдает. |
| R5 | Stale cleanup удалит файл, который временно нечитаем (permission error) | L | L | (root/rel).is_file() возвращает False при permission denied и при несуществовании. Это может дать ложное удаление из индекса; файл будет переиндексирован при следующем refresh (когда права вернутся) или найден через walk. Приемлемый компромисс; логируем на WARNING. |
| R6 | LIKE ESCAPE через backslash ломается на кривом сборке sqlite | VL | L | try/except в _search_bm25/_search_trigram отлавливает OperationalError; падаем на trigram/walk. |
| R7 | Concurrent writes из двух процессов на один .fa/fts.db | L | M | WAL + busy_timeout=10 уже установлено; наблюдал в других проектах это достаточно для CLI-агента. T-CONCURRENT (добавляется в S9) — два потока ищут одновременно и корректно завершаются без corruption. |
| R8 | Latin-1 декодирование UTF-8 файлов даёт мусор | L | L | Latin-1 используется только при UnicodeDecodeError от UTF-8; валидный UTF-8 всегда декодируется первым. |
| R9 | Модульное _refresh_state может быть разделено между тестами в одном pytest-процессе | M | L | Тесты, которым нужна чистая среда, используют отдельный tmp_path и отдельный db_path (это уже есть в текущих тестах). Для canary-state тесты могут инвалидировать через monkeypatch модульный dict или вызывать ensure_indexed(force=True). |

### Откат
Один коммит. Rollback = `git revert <sha>`. Никаких схемных миграций, никаких флагов фич. `.fa/fts.db` совместим в обе стороны (схема не менялась, SCHEMA_VERSION = 1).

Горячее отключение без redeploy: заменить тело `ensure_indexed` на `return SearchStats()` (1 строка) — полностью отключает индекс, оставляя walk-fallback.

### Решения по Q (все приняты с дефолтами, не блокируют)
- **Q1** (частота refresh): every-call с canary-fast-path + 5с throttle.
- **Q2** (bare `*.py`): совпадает на любой глубине (ripgrep/IDE конвенция).
- **Q3** (refresh warnings в ответе): нет; индекс-статы уже возвращаются в index_stats. S15 телеметрия.
- **Q4** (encoding): UTF-8 strict → Latin-1 fallback.
- **Q5** (binary detection): NUL-sniff первых 8КБ.
- **Q6** (throttle duration): 5 секунд.

---

## 8. Definition of Done (фальсифицируемый)

**Cостояние ДО:** 7 воспроизводимых багов; 36 новых тестов не ловят ни один из них; неиспользованный потенциал production-grade.

**Состояние ПОСЛЕ:**
1. Все 7 багов (C1/C2/H1/H2/M1/M2/M3) исправлены.
2. Добавлена production-grade защита: canary+throttle, binary skip, Latin-1 fallback, D-in-D containment.
3. ≥30 новых/обновлённых тестов блокируют регрессии (полный список в S8+S9).
4. Все 10 мутантов из C4 убиваются (краснеют).
5. `py_compile`, `ruff check`, `mypy` — 0 ошибок на изменённых файлах.
6. `pytest tests/` — **те же самые 14 pre-existing фейлов**, 0 новых; все фокусные тесты зелёные.
7. Сгенерирован `/home/user/s14b1-fs-search-unification.patch` с SHA-256.
8. Операторская инструкция на русском: изменения поведения, команда `git apply`, smoke-test, rollback.

**Артефакты, которые меняются:**
- `src/fa/memory/search_index.py` (основные правки: split ensure_indexed, canary+throttle, _escape_like, _escape_fts_query, _passes_filters, _path_matches, _read_bytes/_read_text_for_index/_read_text_for_match, _is_binary, D-in-D в _collect_matches).
- `src/fa/memory/_safe_walk.py` (фиксу сигнатуры _path_is_excluded, протягивание extra_exclude в git-ветку).
- `src/fa/inner_loop/tools/fs_search.py` (фик _resolve_subdir; убрать early-return в _ensure_index; всегда вызывать ensure_indexed; упростить _do_indexed_search).
- `tests/test_fs_search.py` (обновлён sentinel-тест; добавлены C1/C3 тесты по списку S9).
- `tests/test_safe_walk.py` (добавлены C3/C1 тесты для git-ветки exclude).

Не меняются (проверено в preflight):
- Все wiring-файлы в inner_loop.
- InstantGrepIndex deprecation shim (fts_index.py).
- skills/loader.py (stale caller остаётся на отдельный тикет).
- Схема БД; SCHEMA_VERSION; публичный wire-формат fs_search.
- Любые зависимости (новых пакетов не добавляется).

---

## 9. Anti-theater checklist + READY gate

- [x] Каждый символ кода в изменяемых файлах прочитан (не через описание плана).
- [x] Каждый баг G1–G8 воспроизведён на live-коде (не умозрительно).
- [x] Каждая правка имеет продьюсера (конкретная функция), потребителя (конкретный вызов) и тест-оракула.
- [x] Каждый kill-check целится в продьюсер (не в потребителя).
- [x] Инвентарь путей (21 path) покрыт тестами.
- [x] Матрица флагов (15 комбинаций M-A..M-O и расширенная для униформных фильтров) — каждая покрыта.
- [x] Фичи используют реальные test-файлы/реальную sqlite/реальную FS — ноль mock-ов на SearchIndex.
- [x] Никаких нечётких глаголов «обработать нормально» — в каждом контракте явно указано «return None on OSError», «return [] на OperationalError» и т.п.
- [x] Q1–Q6 закрыты с дефолтами, не блокируют.
- [x] Каждый security-контракт SEC-1..6 имеет C3 тест.
- [x] Все ID перекрёстно разрешены (G1–G8, CT1–CT8, INV-HARDEN-1..10, SEC-1..6, P1–P21, S1–S10, T-*, RK1–RK9, Q1–Q6, NG1–NG12, F1–F13).
- [x] Найденные в ревью F1–F13 закрыты в соответствующих шагах; F11 документирована как осознанный политический выбор, а не баг.
- [x] Глубина P2 подтверждается объёмом изменений (250–400 LOC кода + ~300–400 LOC тестов).
- [x] Откат — однокоммитный, схема БД не меняется.
- [x] План НЕ начинает писать код до операторского «go».

**Статус: READY.**

---

## 10. Operator handoff (на русском, после прохождения всех ворот S10)

Будет написан ПОСЛЕ прохождения всех ворот и будет включать:
1. Сжатая сводка что изменилось (AND multi-term, ** glob, canary/throttle refresh, exclude_dirs на FTS, path_escape вместо 500, binary skip, latin-1).
2. Команда `git apply /home/user/s14b1-fs-search-unification.patch`.
3. Команда на smoke-test (несколько конкретных fs_search вызовов против First-Agent-репо).
4. Как читать index_stats в ответе.
5. Инструкция по откату (git revert).
6. SHA-256 патча.
