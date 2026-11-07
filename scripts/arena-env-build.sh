#!/usr/bin/env bash
# Recover this checkout's supported CPython 3.13.16 + frozen dev environment.
# See knowledge/arena-env-build.md for the contract, pins, and recovery notes.
set -Eeuo pipefail

readonly EXPECTED_PYTHON="3.13.16"
readonly UV_VERSION="0.13.7"
readonly DEFAULT_BUILD_ROOT="${HOME}/.cache/arena-python313"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel)"
BUILD_ROOT="${BUILD_ROOT:-$DEFAULT_BUILD_ROOT}"
PREFIX="$BUILD_ROOT/prefix"
SRC="$BUILD_ROOT/src"
PYTHON="$PREFIX/bin/python3.13"
JOBS="${JOBS:-2}"
MODE="run"

usage() {
  cat <<'EOF'
Usage: scripts/arena-env-build.sh [--check | --rebuild-python | --help]

  (no option)       Reuse a valid CPython/venv when possible, build CPython if
                    needed, sync this project's frozen dev dependencies, verify.
  --check           Read-only check of the current .venv; do not build or sync.
  --rebuild-python  Force a fresh staged CPython build from pinned source archives,
                    then sync and verify. Existing prefixes are preserved.
  --help            Show this help.

Overrides: BUILD_ROOT (default ~/.cache/arena-python313), JOBS (default 2),
           UV_BIN (optional path to the pinned uv executable).
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

on_error() {
  local rc=$?
  printf 'ERROR: command failed (exit %s, line %s): %s\n' "$rc" "${BASH_LINENO[0]:-?}" "${BASH_COMMAND:-?}" >&2
  exit "$rc"
}
trap on_error ERR

if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi
if [[ $# -eq 1 ]]; then
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --check) MODE="check" ;;
    --rebuild-python) MODE="rebuild" ;;
    *) usage >&2; exit 2 ;;
  esac
fi

if [[ ! -f "$PROJECT_ROOT/pyproject.toml" || ! -f "$PROJECT_ROOT/uv.lock" ]]; then
  fail "expected pyproject.toml and uv.lock under $PROJECT_ROOT"
fi

runtime_smoke() {
  local python="$1"
  "$python" - <<'PY'
import bz2
import ctypes
import sqlite3
import ssl
import zlib

connection = sqlite3.connect(":memory:")
connection.execute("CREATE VIRTUAL TABLE probe USING fts5(text)")
connection.execute("INSERT INTO probe VALUES ('fts works')")
assert connection.execute(
    "SELECT count(*) FROM probe WHERE probe MATCH 'works'"
).fetchone()[0] == 1
print("stdlib + SQLite FTS5 OK", ssl.OPENSSL_VERSION, sqlite3.sqlite_version)
PY
}

is_usable_python() {
  local python="$1"
  [[ -x "$python" ]] || return 1
  "$python" -c 'import sys; raise SystemExit(0 if sys.version_info[:3] == (3, 13, 16) else 1)' >/dev/null 2>&1 || return 1
  runtime_smoke "$python" >/dev/null 2>&1
}

check_project_venv() {
  local venv_python="$PROJECT_ROOT/.venv/bin/python"
  [[ -x "$venv_python" ]] || fail "project .venv is missing; run without --check to restore it"
  is_usable_python "$venv_python" || fail "project .venv must be CPython $EXPECTED_PYTHON with SSL/zlib/bz2 and SQLite FTS5"
  "$venv_python" -m pytest --version
  [[ -x "$PROJECT_ROOT/.venv/bin/ruff" ]] || fail "dev extra is incomplete: .venv/bin/ruff is missing"
  "$PROJECT_ROOT/.venv/bin/ruff" --version
  runtime_smoke "$venv_python"
  printf 'ENVIRONMENT_CHECK_OK: CPython %s; project dev tools present\n' "$EXPECTED_PYTHON"
}

if [[ "$MODE" == "check" ]]; then
  check_project_venv
  exit 0
fi

if [[ ! "$JOBS" =~ ^[1-9][0-9]*$ ]]; then
  fail "JOBS must be a positive integer (got: $JOBS)"
fi
mkdir -p "$BUILD_ROOT" "$SRC"
LOCK_DIR="$BUILD_ROOT/.arena-env-build.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  fail "another build may be active, or a stale lock exists: $LOCK_DIR (inspect before removing)"
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT
trap on_error ERR

# Immutable upstream commits and SHA-256 digests of their codeload archives.
readonly CPYTHON_COMMIT="cbc944f4bc59639a444dd971c737788ba2283a91"
readonly CPYTHON_SHA256="172762c6e0b6e7fb9d323788b004d33703b29bf9908015e080e4646d9d43c1a5"
readonly OPENSSL_COMMIT="f2ca6496947165bc40da8422fc59b7b22926d84a"
readonly OPENSSL_SHA256="39977bbe62e40ee8ef2059a153fb4e2eadf6b0c47c4344484c681b6c0f8d1bb5"
readonly ZLIB_COMMIT="4dc98e1909830e2bdc2a9cc2236e3c5d5037335b"
readonly ZLIB_SHA256="1fe30e919eb560f495de9ee4bd7ba5216ce13f454affb4ccc32e15efa3878f5e"
readonly LIBFFI_COMMIT="e7a5ad74ebde4c7fc7ba679875dc46bda35e2a15"
readonly LIBFFI_SHA256="663f5d15e8e6f0d33438a44784dcd53f8edf72f3575648060be7a1a86240296a"
readonly BZIP2_COMMIT="05301997b2f9590f49c672cf3dfd3d3dfa7ad521"
readonly BZIP2_SHA256="ab14accac86cdd92021d50465deeb221b476d6675bd1383d3c7fb83751c2e0a3"
readonly SQLITE_COMMIT="f048e6a40879da9828ca2cf3b260f3e0a26117fb"
readonly SQLITE_SHA256="593de968b2a18824c15a1310e62d131b3203beb3fc81ead7d2e726832cf805c2"

fetch_source() {
  local name="$1" repository="$2" commit="$3" digest="$4"
  local archive="$SRC/${name}-${commit}.tar.gz"
  local source="$SRC/${name}-${commit}"
  local temporary

  if [[ ! -s "$archive" ]]; then
    temporary="$(mktemp "$SRC/.${name}.download.XXXXXX")"
    curl --fail --location --silent --show-error --retry 3 \
      "https://codeload.github.com/${repository}/tar.gz/${commit}" \
      --output "$temporary"
    printf '%s  %s\n' "$digest" "$temporary" | sha256sum --check --status \
      || fail "SHA-256 mismatch downloading $name ($commit)"
    mv -- "$temporary" "$archive"
  else
    printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status \
      || fail "cached archive checksum mismatch: $archive (preserved; inspect manually)"
  fi

  if [[ ! -d "$source" ]]; then
    temporary="$(mktemp -d "$SRC/.${name}.extract.XXXXXX")"
    tar -xzf "$archive" --strip-components=1 -C "$temporary"
    mv -- "$temporary" "$source"
  fi
  FETCHED_SOURCE="$source"
}

make_target_if_available() {
  local source="$1" target="$2"
  if [[ -f "$source/Makefile" ]] && grep -Eq "^${target}([[:space:]]|:)" "$source/Makefile"; then
    make -C "$source" "$target"
  fi
}

build_python() {
  local missing=()
  local command
  for command in curl sha256sum tar gcc make perl; do
    command -v "$command" >/dev/null 2>&1 || missing+=("$command")
  done
  if ((${#missing[@]})); then
    fail "cold build requires these commands: ${missing[*]}"
  fi

  fetch_source cpython python/cpython "$CPYTHON_COMMIT" "$CPYTHON_SHA256"
  local cpython_source="$FETCHED_SOURCE"
  fetch_source openssl python/cpython-source-deps "$OPENSSL_COMMIT" "$OPENSSL_SHA256"
  local openssl_source="$FETCHED_SOURCE"
  fetch_source zlib python/cpython-source-deps "$ZLIB_COMMIT" "$ZLIB_SHA256"
  local zlib_source="$FETCHED_SOURCE"
  fetch_source libffi python/cpython-source-deps "$LIBFFI_COMMIT" "$LIBFFI_SHA256"
  local libffi_source="$FETCHED_SOURCE"
  fetch_source bzip2 python/cpython-source-deps "$BZIP2_COMMIT" "$BZIP2_SHA256"
  local bzip2_source="$FETCHED_SOURCE"
  fetch_source sqlite python/cpython-source-deps "$SQLITE_COMMIT" "$SQLITE_SHA256"
  local sqlite_source="$FETCHED_SOURCE"

  local stage
  stage="$(mktemp -d "$BUILD_ROOT/.prefix-build.XXXXXX")"
  printf 'Building CPython %s in staging prefix %s (JOBS=%s)\n' "$EXPECTED_PYTHON" "$stage" "$JOBS"

  make_target_if_available "$zlib_source" clean
  (cd "$zlib_source" && ./configure --prefix="$stage" && make -j"$JOBS" && make install)

  make_target_if_available "$openssl_source" clean
  (cd "$openssl_source" && ./config --prefix="$stage" --libdir=lib && make -j"$JOBS" && make install_sw)

  make_target_if_available "$libffi_source" clean
  chmod +x "$libffi_source/configure"
  (cd "$libffi_source" && ./configure --prefix="$stage" && make -j"$JOBS" && make install)

  make_target_if_available "$bzip2_source" clean
  (cd "$bzip2_source" && make -j"$JOBS" && make install PREFIX="$stage")
  rm -f -- "$bzip2_source"/*.o "$bzip2_source"/libbz2.so*
  (cd "$bzip2_source" && make -f Makefile-libbz2_so CFLAGS='-O2 -fPIC -Wall -Winline' -j"$JOBS")
  install -m 755 "$bzip2_source/libbz2.so.1.0.8" "$stage/lib/"
  ln -sf libbz2.so.1.0.8 "$stage/lib/libbz2.so.1.0"
  ln -sf libbz2.so.1.0 "$stage/lib/libbz2.so"
  install -m 644 "$bzip2_source/bzlib.h" "$stage/include/"

  rm -f -- "$sqlite_source/sqlite3.o" "$sqlite_source/libsqlite3.so"
  (cd "$sqlite_source" && \
    gcc -O2 -fPIC -DSQLITE_ENABLE_FTS5 -c sqlite3.c -o sqlite3.o && \
    gcc -shared -o libsqlite3.so sqlite3.o -lpthread -ldl -lm)
  install -m 644 "$sqlite_source/sqlite3.h" "$stage/include/"
  install -m 755 "$sqlite_source/libsqlite3.so" "$stage/lib/"

  make_target_if_available "$cpython_source" distclean
  (
    cd "$cpython_source"
    export CPPFLAGS="-I$stage/include"
    export LDFLAGS="-L$stage/lib -Wl,-rpath,$PREFIX/lib"
    export PKG_CONFIG_PATH="$stage/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
    ./configure --prefix="$stage" --with-openssl="$stage" --with-openssl-rpath=auto
    make -j"$JOBS"
    make install
  )

  if ! LD_LIBRARY_PATH="$stage/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" runtime_smoke "$stage/bin/python3.13"; then
    fail "staged CPython failed the runtime/FTS5 smoke test; staging prefix preserved at $stage"
  fi

  local previous=""
  if [[ -e "$PREFIX" ]]; then
    previous="$BUILD_ROOT/prefix.previous.$(date +%Y%m%d%H%M%S)"
    mv -- "$PREFIX" "$previous"
  fi
  if ! mv -- "$stage" "$PREFIX"; then
    if [[ -n "$previous" && -e "$previous" ]]; then mv -- "$previous" "$PREFIX"; fi
    fail "could not publish the verified toolchain; previous prefix restored if present"
  fi
  PYTHON="$PREFIX/bin/python3.13"
  runtime_smoke "$PYTHON"
  printf 'CPython toolchain ready: %s\n' "$PYTHON"
}

select_python() {
  if [[ "$MODE" != "rebuild" && -x "$PROJECT_ROOT/.venv/bin/python" ]] && \
      is_usable_python "$PROJECT_ROOT/.venv/bin/python"; then
    PYTHON="$("$PROJECT_ROOT/.venv/bin/python" -c 'import sys; print(sys._base_executable)')"
    if is_usable_python "$PYTHON"; then
      printf 'Reusing the validated project venv interpreter: %s\n' "$PYTHON"
      return 0
    fi
  fi
  if [[ "$MODE" != "rebuild" ]] && is_usable_python "$PYTHON"; then
    printf 'Reusing the validated cached toolchain: %s\n' "$PYTHON"
    return 0
  fi
  build_python
}

is_pinned_uv() {
  local version="$1"
  [[ "$version" == "uv $UV_VERSION" || "$version" == "uv $UV_VERSION "* ]]
}

ensure_uv() {
  local candidate="" version=""
  if [[ -n "${UV_BIN:-}" ]]; then
    [[ -x "$UV_BIN" ]] || fail "UV_BIN is not executable: $UV_BIN"
    candidate="$UV_BIN"
    version="$("$candidate" --version)"
    is_pinned_uv "$version" || fail "UV_BIN must be uv $UV_VERSION (got: $version)"
    printf '%s\n' "$candidate"
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    candidate="$(command -v uv)"
    version="$("$candidate" --version 2>/dev/null || true)"
    if is_pinned_uv "$version"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi

  local cached_uv="$BUILD_ROOT/uv-tools-$UV_VERSION/bin/uv"
  if [[ -x "$cached_uv" ]] && is_pinned_uv "$("$cached_uv" --version)"; then
    printf '%s\n' "$cached_uv"
    return 0
  fi

  local tools_dir="$BUILD_ROOT/uv-tools-$UV_VERSION"
  local temporary
  temporary="$(mktemp -d "$BUILD_ROOT/.uv-tools.XXXXXX")"
  printf 'Installing isolated uv %s under %s\n' "$UV_VERSION" "$tools_dir" >&2
  "$PYTHON" -m venv "$temporary"
  "$temporary/bin/python" -m pip install --disable-pip-version-check --only-binary=:all: "uv==$UV_VERSION" >&2
  is_pinned_uv "$("$temporary/bin/uv" --version)" || fail "isolated uv bootstrap did not produce uv $UV_VERSION"
  if [[ -e "$tools_dir" ]]; then
    mv -- "$tools_dir" "$BUILD_ROOT/uv-tools-$UV_VERSION.previous.$(date +%Y%m%d%H%M%S)"
  fi
  mv -- "$temporary" "$tools_dir"
  printf '%s\n' "$tools_dir/bin/uv"
}

select_python
UV_PATH="$(ensure_uv)"
printf 'Syncing frozen dev environment with %s\n' "$UV_PATH"
cd "$PROJECT_ROOT"
UV_SYSTEM_CERTS=true "$UV_PATH" sync --frozen --extra dev --python "$PYTHON"
check_project_venv
printf 'ENVIRONMENT_READY: CPython %s; frozen dev extra installed\n' "$EXPECTED_PYTHON"
