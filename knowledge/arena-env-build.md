# Arena sandbox: восстановление Python test-environment

Это runbook для восстановления корректного тестового окружения этого проекта. Для обычного восстановления используйте исполняемый сценарий `scripts/arena-env-build.sh`; этот документ фиксирует его контракт, pins и диагностику. Не копируйте команды сборки между проектами: extras, lockfile и требования здесь относятся именно к `first-agent`.

## Быстрый путь

Из корня checkout:

```bash
./scripts/arena-env-build.sh
```

Сценарий выбирает самый короткий безопасный путь:

1. Проверяет, можно ли переиспользовать интерпретатор текущего `.venv`.
2. Иначе проверяет кэшированный toolchain в `${BUILD_ROOT:-$HOME/.cache/arena-python313}/prefix`.
3. Если пригодного CPython нет — собирает CPython 3.13.16 из закреплённых исходников в staging-prefix и публикует его только после runtime/FTS5 smoke.
4. Обеспечивает `uv 0.13.7` (переиспользует точную версию из `PATH`/`UV_BIN` или ставит её в отдельный cached tool-venv; системный Python не меняет).
5. Выполняет `uv sync --frozen --extra dev --python <выбранный CPython>` с системными CA-сертификатами, затем проверяет созданный `.venv`.

`uv sync` может обновить только локальный `.venv`; исходники проекта, системный Python, Git branch/index и пользовательские файлы сценарий не изменяет. Сборки, исходники, архивы и bootstrap `uv` находятся вне checkout в `BUILD_ROOT`. Ничего из этого кэша сценарий автоматически не удаляет.

### Режимы

```bash
./scripts/arena-env-build.sh --check          # read-only: проверить текущий .venv, без сети/sync/build
./scripts/arena-env-build.sh                  # fast path или восстановление + frozen dev sync
./scripts/arena-env-build.sh --rebuild-python # принудительная пересборка CPython в staging-prefix
```

Дополнительные настройки:

- `BUILD_ROOT=/путь` — перенести cache/build outputs.
- `JOBS=2` — число параллельных build jobs; значение по умолчанию намеренно умеренное для sandbox.
- `UV_BIN=/путь/к/uv` — явно выбрать исполняемый `uv`; он обязан быть версии `0.13.7`.

`--check` подтверждает версию CPython, необходимые stdlib-модули/SQLite FTS5, наличие `pytest` и `ruff`. Он **не** синхронизирует зависимости и не доказывает, что тесты проекта проходят. Обычный запуск подтверждает frozen sync и те же runtime/dev-tool smoke checks, но также **не запускает полный pytest suite**. После восстановления запускайте требуемые тесты и фиксируйте фактические результаты отдельно.

## Контракт окружения этого проекта

- Текущий recovery target: **CPython 3.13.16**. `pyproject.toml` и `uv.lock` формально допускают `>=3.13`; версия 3.13.16 выбрана как воспроизводимый локальный sandbox toolchain, а не выведена из этого диапазона автоматически.
- Проект имеет `uv.lock`; тестовая группа — extra `dev` из текущего `pyproject.toml`. Синхронизация выполняется с `--frozen`, чтобы не переписать lock и не разрешать новые версии.
- Проверяется не только `import sqlite3`: smoke создаёт FTS5 virtual table, вставляет и ищет строку. Также импортируются `ssl`, `zlib`, `bz2` и `ctypes`.
- `uv` закреплён на `0.13.7` и хранится/используется отдельно от системного Python и project `.venv`.
- Никакого `apt`, root, Docker, `pip install --break-system-packages` или ручного изменения системного Python не требуется.

## Закреплённые исходники CPython toolchain

Архивы загружаются с `codeload.github.com` по immutable commit, проверяются SHA-256 **до распаковки** и кэшируются. Хэши ниже относятся к соответствующим codeload tar archives; изменение commit или digest требует обновить их вместе и повторно проверить архивы.

| Источник | Commit | SHA-256 codeload archive |
|---|---|---|
| CPython 3.13.16 | `cbc944f4bc59639a444dd971c737788ba2283a91` | `172762c6e0b6e7fb9d323788b004d33703b29bf9908015e080e4646d9d43c1a5` |
| OpenSSL source dependency | `f2ca6496947165bc40da8422fc59b7b22926d84a` | `39977bbe62e40ee8ef2059a153fb4e2eadf6b0c47c4344484c681b6c0f8d1bb5` |
| zlib source dependency | `4dc98e1909830e2bdc2a9cc2236e3c5d5037335b` | `1fe30e919eb560f495de9ee4bd7ba5216ce13f454affb4ccc32e15efa3878f5e` |
| libffi source dependency | `e7a5ad74ebde4c7fc7ba679875dc46bda35e2a15` | `663f5d15e8e6f0d33438a44784dcd53f8edf72f3575648060be7a1a86240296a` |
| bzip2 source dependency | `05301997b2f9590f49c672cf3dfd3d3dfa7ad521` | `ab14accac86cdd92021d50465deeb221b476d6675bd1383d3c7fb83751c2e0a3` |
| SQLite source dependency | `f048e6a40879da9828ca2cf3b260f3e0a26117fb` | `593de968b2a18824c15a1310e62d131b3203beb3fc81ead7d2e726832cf805c2` |

The build retains the previously verified fixes: OpenSSL uses `--libdir=lib`; libffi's `configure` is made executable; bzip2 shared objects are freshly compiled with `-fPIC`; SQLite is compiled with `SQLITE_ENABLE_FTS5`; CPython uses the staged libraries during build and its final prefix for runtime lookup. A cold build may take 10–15 minutes on 2 CPUs. Set `JOBS` deliberately; aggressive parallelism can exhaust a small sandbox.

## Safeguards and failure recovery

- Cold builds require `curl`, `sha256sum`, `tar`, `gcc`, `make`, and `perl`. The script checks these before building.
- A wrong archive digest, unsupported Python, missing FTS5, failed `uv sync`, or missing test tools is a hard failure; there is no fallback to system Python or an unfrozen install.
- A newly built toolchain is assembled in a staging directory. It replaces `prefix` only after the staged Python passes the runtime/FTS5 smoke. A prior prefix is retained as `prefix.previous.<timestamp>`; failed staging directories and source archives are preserved for diagnosis.
- A checksum-mismatched cached archive is not silently deleted or redownloaded over; inspect it manually. A lock directory at `BUILD_ROOT/.arena-env-build.lock` means another run may be active or a previous process left a stale lock. Inspect before removing it.
- If the cold build fails, read the command and line reported by the script, then inspect `$BUILD_ROOT/src` and `.prefix-build.*`. Do not “fix” failures by changing system Python, dropping `--frozen`, or deleting unknown cache/worktree data.
- The script only guarantees environment construction and smoke checks. A successful `ENVIRONMENT_READY` is not a test-suite PASS, mutation PASS, W0 row closure, Docker result, or deployed-host acceptance.

## Verify and run tests

```bash
./scripts/arena-env-build.sh --check
.venv/bin/python -VV
.venv/bin/python -m pytest --version
.venv/bin/ruff --version
.venv/bin/python -m pytest -q path/to/relevant_tests.py
# Run the full suite only when appropriate:
.venv/bin/python -m pytest -q
```

Record actual commands, exit codes, counts, expected xfails, skips, and failures. A working interpreter, `pytest --version`, or FTS5 smoke alone does not mean the project's tests passed. Diagnose tracebacks; do not label failures environmental or pre-existing without evidence.

## Git/worktree safety

The recovery script must be run inside the intended checkout. Before using it, inspect `git status --short` and `git branch --show-current`; it does not repair stale Git pointers or discard work. It never switches branches, changes the index, or resets files. Keep build artifacts out of Git by using the default cache under `$HOME/.cache` (or another external `BUILD_ROOT`).
