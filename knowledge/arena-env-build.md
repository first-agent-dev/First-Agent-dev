# Arena sandbox: Python test-environment recovery

Use this when the sandbox has only an older system Python and no `apt`/root. It builds an isolated CPython 3.13 toolchain; it does not modify the system Python. A cold build may take 10–15 minutes on 2 CPUs. Keep this guide in the checkout; caches and virtualenvs may disappear between sessions.

## 1. Locate this checkout and check what already exists

Run from anywhere inside the project:

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
BUILD_ROOT="${BUILD_ROOT:-$HOME/.cache/arena-python313}"
PY="$BUILD_ROOT/prefix/bin/python3.13"
cd "$PROJECT_ROOT"
python3 -VV
git status --short
git branch --show-current
[ -x "$PY" ] && "$PY" -VV || echo 'Python 3.13 not built'
[ -x .venv/bin/python ] && .venv/bin/python -VV || echo 'Project venv not built'
```

If the toolchain exists, skip to step 3. Do not assume another session's absolute paths or branch name apply here.

## 2. Build Python 3.13 from source (only if needed)

Run this block from the project checkout. It writes a temporary script into that checkout, while downloads and build outputs go under `$BUILD_ROOT`. Override `BUILD_ROOT` if desired. Start detached for long-running tool calls; check the log for `BUILD_DONE` before proceeding.

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
BUILD_ROOT="${BUILD_ROOT:-$HOME/.cache/arena-python313}"
mkdir -p "$BUILD_ROOT"
cat > "$PROJECT_ROOT/.arena-build-python313.sh" <<'BUILD_SCRIPT'
#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${BUILD_ROOT:-$HOME/.cache/arena-python313}"
SRC="$ROOT/src"; PREFIX="$ROOT/prefix"; JOBS="${JOBS:-2}"
mkdir -p "$SRC" "$PREFIX"
fetch() {
  local name="$1" url="$2" dir="$3" tmp
  [[ -s "$SRC/$name.tar.gz" ]] || curl -fL --retry 3 "$url" -o "$SRC/$name.tar.gz"
  if [[ ! -d "$SRC/$dir" ]]; then
    tmp="$SRC/.extract-$dir-$$"; mkdir "$tmp"
    tar -xzf "$SRC/$name.tar.gz" --strip-components=1 -C "$tmp"
    mv "$tmp" "$SRC/$dir"
  fi
}
fetch cpython https://codeload.github.com/python/cpython/tar.gz/refs/tags/v3.13.16 cpython-3.13.16
fetch openssl https://codeload.github.com/python/cpython-source-deps/tar.gz/refs/heads/openssl-3.0 cpython-source-deps-openssl-3.0
fetch zlib https://codeload.github.com/python/cpython-source-deps/tar.gz/refs/heads/zlib cpython-source-deps-zlib
fetch libffi https://codeload.github.com/python/cpython-source-deps/tar.gz/refs/heads/libffi cpython-source-deps-libffi
fetch bzip2 https://codeload.github.com/python/cpython-source-deps/tar.gz/refs/heads/bzip2 cpython-source-deps-bzip2
fetch sqlite https://codeload.github.com/python/cpython-source-deps/tar.gz/refs/heads/sqlite cpython-source-deps-sqlite

cd "$SRC/cpython-source-deps-zlib"; ./configure --prefix="$PREFIX"; make -j"$JOBS"; make install
cd "$SRC/cpython-source-deps-openssl-3.0"; ./config --prefix="$PREFIX" --libdir=lib; make -j"$JOBS"; make install_sw
cd "$SRC/cpython-source-deps-libffi"; chmod +x configure; ./configure --prefix="$PREFIX"; make -j"$JOBS"; make install
cd "$SRC/cpython-source-deps-bzip2"
make -j"$JOBS"; make install PREFIX="$PREFIX"
# Fresh PIC objects are required; this Makefile has no install target.
rm -f ./*.o libbz2.so*
make -f Makefile-libbz2_so CFLAGS='-O2 -fPIC -Wall -Winline' -j"$JOBS"
install -m755 libbz2.so.1.0.8 "$PREFIX/lib/"
ln -sf libbz2.so.1.0.8 "$PREFIX/lib/libbz2.so.1.0"
ln -sf libbz2.so.1.0 "$PREFIX/lib/libbz2.so"
install -m644 bzlib.h "$PREFIX/include/"
cd "$SRC/cpython-source-deps-sqlite"
gcc -O2 -fPIC -DSQLITE_ENABLE_FTS5 -c sqlite3.c -o sqlite3.o
gcc -shared -o libsqlite3.so sqlite3.o -lpthread -ldl -lm
install -m644 sqlite3.h "$PREFIX/include/"; install -m755 libsqlite3.so "$PREFIX/lib/"
cd "$SRC/cpython-3.13.16"
export CPPFLAGS="-I$PREFIX/include" LDFLAGS="-L$PREFIX/lib -Wl,-rpath,$PREFIX/lib"
export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
./configure --prefix="$PREFIX" --with-openssl="$PREFIX" --with-openssl-rpath=auto
make -j"$JOBS"; make install
"$PREFIX/bin/python3.13" -VV
"$PREFIX/bin/python3.13" - <<'PY'
import bz2, ctypes, sqlite3, ssl, zlib
c = sqlite3.connect(':memory:')
c.execute('CREATE VIRTUAL TABLE probe USING fts5(text)')
c.execute("INSERT INTO probe VALUES ('fts works')")
assert c.execute("SELECT count(*) FROM probe WHERE probe MATCH 'works'").fetchone()[0] == 1
print('stdlib + FTS5 OK', ssl.OPENSSL_VERSION, sqlite3.sqlite_version)
PY
echo BUILD_DONE
BUILD_SCRIPT

# Detached build; do not start another while this one is running.
setsid env BUILD_ROOT="$BUILD_ROOT" bash "$PROJECT_ROOT/.arena-build-python313.sh" \
  > "$BUILD_ROOT/build.log" 2>&1 < /dev/null &
echo "Build started; log: $BUILD_ROOT/build.log"
```

Wait for completion:

```bash
tail -f "$BUILD_ROOT/build.log"   # stop after BUILD_DONE
```

Known fixes embedded above: OpenSSL branch is `openssl-3.0` and must use `--libdir=lib`; libffi's configure may need `chmod +x`; bzip2 shared objects must be freshly compiled with `-fPIC`; SQLite is an amalgamation and needs `-DSQLITE_ENABLE_FTS5`. `import sqlite3` alone does not test FTS5. Avoid PGO (`--enable-optimizations`) unless its extra build time is warranted.

## 3. Create/refresh the project environment

Use the interpreter built above. Choose extras from the **current project's** `pyproject.toml`; do not copy extras from another repository. `--frozen` is for projects with a valid lockfile.

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
BUILD_ROOT="${BUILD_ROOT:-$HOME/.cache/arena-python313}"
export PATH="$BUILD_ROOT/prefix/bin:$PATH"
python3 -m pip install --break-system-packages uv
cd "$PROJECT_ROOT"
UV_SYSTEM_CERTS=true uv sync --frozen
# Add this project's test extra if needed, e.g. append: --extra dev
# Omit --frozen when the project has no lockfile.
```

## 4. Verify, then test

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"
.venv/bin/python -VV
.venv/bin/python - <<'PY'
import bz2, ctypes, sqlite3, ssl, zlib
c = sqlite3.connect(':memory:')
c.execute('CREATE VIRTUAL TABLE probe USING fts5(text)')
c.execute("INSERT INTO probe VALUES ('fts works')")
assert c.execute("SELECT count(*) FROM probe WHERE probe MATCH 'works'").fetchone()[0] == 1
print('runtime + FTS5 OK', ssl.OPENSSL_VERSION, sqlite3.sqlite_version)
PY
.venv/bin/python -m pytest --version
.venv/bin/python -m pytest -q path/to/relevant_tests.py
# Run the full suite when appropriate:
.venv/bin/python -m pytest -q
```

Report actual test counts and failures. A working interpreter, pytest import, or FTS5 smoke test does not mean the project's tests pass. Diagnose failures from their tracebacks; don't label them environmental or pre-existing without evidence.

## 5. Git recovery (brief)

Each session may use a different branch. Inspect the current checkout; never paste a branch name from an old handoff. If `HEAD` is stale, fetch the current branch and verify that on-disk files exactly match the intended remote commit before moving Git's pointer. Only then use `git reset --mixed <verified-commit>`; it preserves files. Never use `checkout`, `restore`, or `reset --hard` to repair a stale pointer or discard unsurveyed work.