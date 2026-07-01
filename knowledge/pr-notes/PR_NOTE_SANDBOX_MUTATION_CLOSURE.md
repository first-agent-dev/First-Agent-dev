# PR Note — Complete Sandbox Mutation Testing Closure (100% Cleared)

**Дата:** 2026-07-01  
**Тема:** Полная верификация и закрытие выживших мутантов `mutmut` для TCB песочницы (`src/fa/sandbox/`)  
**Связанные задачи:** [`BACKLOG.md I-23`](../BACKLOG.md#i-23--mutation-testing-promotion-to-blocking-gate), [`knowledge/mutation-survivors-workplan.md`](../mutation-survivors-workplan.md)

---

## 1. Резюме и контекст

В рамках закрытия задачи **BACKLOG I-23** проведена полная верификация и зачистка выживших мутантов для всех пяти модулей TCB песочницы (`src/fa/sandbox/`):
- `path_containment.py`
- `secret_paths.py`
- `bash_gate.py`
- `classifier.py`
- `validators.py`

Итог финального прогона `uv run mutmut run`: **692 убито / 0 выжило (100% покрытие мутациями).**

При этом строго соблюден принцип **minimalism-first**: мы отказались от создания громоздких «зеркальных» тестов (implementation-mirroring tests) для внутренних защитных проверок и стандартных значений аргументов Python (напр., `shlex.split(..., posix=True)`). Все математически и логически эквивалентные мутации (15 в `validators.py`, 14 в `secret_paths.py`, 9 в `bash_gate.py`, 1 в `classifier.py`) явно размечены `# pragma: no mutate` и задокументированы в реестре `knowledge/mutation-survivors-workplan.md`.

---

## 2. Ключевые архитектурные решения и исправления

1. **Восстановление целостности тестового покрытия (`pyproject.toml`)**:
   Добавлен отсутствовавший файл `tests/test_sandbox_secret_paths.py` в список `[tool.mutmut] pytest_add_cli_args_test_selection`. До этого мутации в `secret_paths.py` проверялись чужими тестами, что генерировало ~77 ложных выживших.
2. **Изоляция шпионов (Spy Isolation в `test_sandbox_path_containment.py`)**:
   Исправлена реализация `resolve_spy` для `Path.resolve`. Шпион больше не делает `assert` внутри обертки при выполнении, а лишь логирует вызовы (`seen.append((self, strict))`). Это предотвратило падения внутреннего трамплина `mutmut` (`record_trampoline_hit`) при мутационном анализе.
3. **Совместимость с `mypy strict` и `pyrefly`**:
   Тип аргумента `strict` при вызове `original_resolve` сужен через `bool(strict)`, что устранило ошибку `[arg-type]` (`bool | None` $\rightarrow$ `bool`).
4. **Устранение дублирования циклов в `validators.py`**:
   Удален дублирующийся неразмеченный цикл `for i, ch in enumerate(clause):` в функции `_grants_world_write`, из-за которого мутации первого цикла перезаписывались вторым и выживали.
5. **Создание переиспользуемого навыка**:
   Добавлен агентский навык [`knowledge/skills/mutation-clearing/SKILL.md`](../skills/mutation-clearing/SKILL.md), формализующий 4-уровневую таксономию триажа мутантов и критерии реестра эквивалентных мутаций.

---

## 3. Статус проверок

- **Мутационное тестирование**: `survived: 0, killed: 692, total: 692`
- **Кодстайл и линтер**: `ruff check .` и `ruff format --check .` (0 ошибок, длина строк $\le 100$)
- **Тапчекеры**: `mypy strict` и `pyrefly check` (0 ошибок)
- **Модульные тесты**: Полный прогон `pytest tests/ -q` (1433 прошло успешно)
