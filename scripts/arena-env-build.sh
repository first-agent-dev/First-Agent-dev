#!/usr/bin/env bash
# Recover this checkout's supported CPython 3.13.16 + frozen dev environment.
# See knowledge/arena-env-build.md for the contract, pins, and recovery notes.
set -Eeuo pipefail

readonly EXPECTED_PYTHON="3.13.16"
readonly UV_VERSION="0.13.7"
readonly JUST_VERSION="1.57.0"
readonly JUST_PACKAGE="rust-just==$JUST_VERSION"
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
                    needed, sync frozen dev dependencies, install pinned uv/just
                    gate launchers in .venv/bin, and verify.
  --check           Read-only check of the current .venv; do not build or sync.
  --rebuild-python  Force a fresh staged CPython build from pinned source archives,
                    then sync and verify. Existing prefixes are preserved.
  --help            Show this help.

Overrides: BUILD_ROOT (default ~/.cache/arena-python313), JOBS (default 2),
           UV_BIN (optional path to the pinned uv executable),
           SYSTEM_OPENSSL=auto|require|never (default auto: reuse host OpenSSL
           when it passes a compile+link+handshake probe, otherwise build ours).
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

# The smoke costs ~30 ms and the same interpreter is probed more than once per run
# (venv, its base, cached toolchain). One verdict per path per run is enough, and it is
# kept separately from REUSED_VENV, which only says the venv itself was validated.
SMOKED_PYTHON=""
REUSED_VENV=0

# Version-only probe: one interpreter start, no imports beyond sys. Used to skip the
# full runtime/FTS5 smoke when the version already disqualifies the candidate.
is_expected_python() {
  local python="$1"
  [[ -x "$python" ]] || return 1
  "$python" -c 'import sys; raise SystemExit(0 if sys.version_info[:3] == (3, 13, 16) else 1)' >/dev/null 2>&1
}

is_usable_python() {
  local python="$1"
  is_expected_python "$python" || return 1
  [[ "$SMOKED_PYTHON" == "$python" ]] && return 0
  runtime_smoke "$python" >/dev/null 2>&1 || return 1
  SMOKED_PYTHON="$python"
}

is_pinned_uv() {
  local version="$1"
  [[ "$version" == "uv $UV_VERSION" || "$version" == "uv $UV_VERSION "* ]]
}

is_pinned_just() {
  [[ "$1" == "just $JUST_VERSION" ]]
}

# The tool executables are not re-versioned here: `just check` runs them under uv, and
# a pytest --version costs more than the entire rest of this script.
check_project_venv() {
  local venv_python="$PROJECT_ROOT/.venv/bin/python"
  [[ -x "$venv_python" ]] || fail "project .venv is missing; run without --check to restore it"
  # --check always probes. A normal run skips the probe when this interpreter already
  # passed it while being selected (VENVPROBE=1), so one smoke per run is the maximum.
  if [[ "${VENVPROBE:-0}" != "1" || "${SMOKED_PYTHON:-}" != "$venv_python" ]]; then
    is_usable_python "$venv_python" || fail "project .venv must be CPython $EXPECTED_PYTHON with SSL/zlib/bz2 and SQLite FTS5 (run: just fix)"
  fi
  local venv_bin="$PROJECT_ROOT/.venv/bin"
  local tool
  for tool in pytest ruff deptry pylint mypy pyrefly mutmut vulture pip-audit fa; do
    [[ -x "$venv_bin/$tool" ]] || fail "dev extra is incomplete: .venv/bin/$tool is missing"
  done
  [[ -x "$venv_bin/uv" ]] || fail "gate launcher is missing: .venv/bin/uv; rerun without --check"
  [[ -x "$venv_bin/just" ]] || fail "gate launcher is missing: .venv/bin/just; rerun without --check"
  # Launchers are probed by running them: a stale symlink is exactly what --check catches.
  is_pinned_uv "$("$venv_bin/uv" --version)" || fail "project .venv must expose uv $UV_VERSION"
  is_pinned_just "$("$venv_bin/just" --version)" || fail "project .venv must expose just $JUST_VERSION"
  printf 'gate tools present: pytest ruff deptry pylint mypy pyrefly mutmut vulture pip-audit fa\n'
  printf 'ENVIRONMENT_CHECK_OK: CPython %s; pinned uv/just and just-check dev tools present\n' "$EXPECTED_PYTHON"
  printf 'Run gates with: source %s/.venv/bin/activate && just check\n' "$PROJECT_ROOT"
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

# One amalgamation compile feeds BOTH our libsqlite3.so and CPython's bundled
# _sqlite3 (which compiles the same sqlite3.c again unless the module is skipped).
# Hence the single flag set: FTS5 for instant search, FTS3/4 because a 3.53 build
# exposes them by default and dropping them would be a silent capability loss,
# and the loadable-extension entry point so --enable-loadable-sqlite-extensions
# is not a lie. SQLITE_THREADSAFE keeps the default serialized mode.
readonly SQLITE_CFLAGS="-O2 -fPIC -DSQLITE_ENABLE_FTS5 -DSQLITE_ENABLE_FTS3 -DSQLITE_ENABLE_FTS3_PARENTHESIS -DSQLITE_ENABLE_LOADABLE_EXTENSION=1"
readonly SYSTEM_OPENSSL="${SYSTEM_OPENSSL:-auto}"
readonly RECONFIGURE="${RECONFIGURE:-0}"

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

# Archives are downloaded sequentially today: on a cold cache the six files take ~40 s
# wall clock while the network is idle most of that time. Warm them in parallel, then run
# the ordinary (verified, idempotent) fetch loop below for extraction and cache checks.
prefetch_archives() {
  local spec name repository commit digest archive
  local waited=()
  local skip_openssl=0
  [[ "$USE_SYSTEM_OPENSSL" == "1" ]] && skip_openssl=1
  for spec in \
    "cpython python/cpython $CPYTHON_COMMIT $CPYTHON_SHA256" \
    "openssl python/cpython-source-deps $OPENSSL_COMMIT $OPENSSL_SHA256" \
    "zlib python/cpython-source-deps $ZLIB_COMMIT $ZLIB_SHA256" \
    "libffi python/cpython-source-deps $LIBFFI_COMMIT $LIBFFI_SHA256" \
    "bzip2 python/cpython-source-deps $BZIP2_COMMIT $BZIP2_SHA256" \
    "sqlite python/cpython-source-deps $SQLITE_COMMIT $SQLITE_SHA256"; do
    read -r name repository commit digest <<<"$spec"
    [[ "$name" == "openssl" && "$skip_openssl" == "1" ]] && continue
    archive="$SRC/${name}-${commit}.tar.gz"
    [[ -s "$archive" ]] && continue
    # No `fail` here: a subshell cannot stop the parent, and fetch_source below decides
    # what a failed or corrupt archive means (including its "preserved, inspect" rule).
    (
      temporary="$(mktemp "$SRC/.${name}.prefetch.XXXXXX")"
      curl --fail --location --silent --show-error --retry 3 \
        "https://codeload.github.com/${repository}/tar.gz/${commit}" \
        --output "$temporary" || exit 0
      if printf '%s  %s\n' "$digest" "$temporary" | sha256sum --check --status; then
        mv -- "$temporary" "$archive" || rm -f -- "$temporary"
      else
        rm -f -- "$temporary"
      fi
    ) &
    waited+=("$!")
  done
  # Bounded wait: one straggler cannot hold up a build that fetch_source would block on
  # anyway, it just loses the overlap.
  local pid
  for pid in "${waited[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
}

# A host OpenSSL is used only if it actually compiles, links and completes a TLS
# handshake with the same flags CPython will use. Anything weaker (version string,
# presence of a .so) has repeatedly produced prefixes whose `ssl` module imports but
# whose TLS is broken, so the probe mirrors configure: include + lib + rpath.
openssl_probe() {
  local include="${OPENSSL_INCLUDE_DIR:-/usr/include}"
  local lib="${OPENSSL_LIB_DIR:-$(cc -print-search-dirs 2>/dev/null | sed -n 's|^libraries: *=||p' | tr ':' ' ' | tr ' ' '\n' | grep -m1 -E '/usr/lib/x86_64-linux-gnu$|/usr/lib64$|/usr/lib$' || printf /usr/lib/x86_64-linux-gnu)}"
  OPENSSL_LIB_DIR="$lib"
  [[ -f "$include/openssl/ssl.h" ]] || return 1
  local probe_dir
  probe_dir="$(mktemp -d "$BUILD_ROOT/.openssl-probe.XXXXXX")" || return 1
  if ! cat >"$probe_dir/probe.c" <<'C'
#include <openssl/ssl.h>
#include <openssl/err.h>
int main(void) {
  if (OPENSSL_VERSION_NUMBER < 0x30000000L) return 1;  /* our contracts assume 3.x */
  SSL_library_init();
  SSL_CTX *ctx = SSL_CTX_new(TLS_client_method());
  if (ctx == NULL) return 2;
  SSL_CTX_free(ctx);
  printf("%s\n", OpenSSL_version(OPENSSL_VERSION));
  return 0;
}
C
  then rm -rf -- "$probe_dir"; return 1; fi
  if ! cc "$probe_dir/probe.c" -I"$include" -L"$lib" -Wl,-rpath,"$lib" -lssl -lcrypto \
      -o "$probe_dir/probe" >"$probe_dir/build.log" 2>&1; then
    rm -rf -- "$probe_dir"
    return 1
  fi
  local reported
  if ! reported="$(LD_LIBRARY_PATH="$lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" "$probe_dir/probe")"; then
    rm -rf -- "$probe_dir"
    return 1
  fi
  rm -rf -- "$probe_dir"
  SYSTEM_OPENSSL_VERSION="$reported"
  return 0
}

# Decide ONCE, before any download or build, so prefetch and build agree.
# auto   — probe the host, fall back to the pinned build on any doubt
# require — host must work (fail loudly instead of silently spending 3 minutes)
# never  — always build the pinned OpenSSL (previous behaviour)
select_openssl() {
  USE_SYSTEM_OPENSSL=0
  local include="${OPENSSL_INCLUDE_DIR:-/usr/include}"
  local lib="${OPENSSL_LIB_DIR:-/usr/lib/x86_64-linux-gnu}"
  if [[ "$SYSTEM_OPENSSL" == "never" ]]; then
    printf 'OpenSSL: building pinned version (SYSTEM_OPENSSL=never)\n'
    return 0
  fi
  if openssl_probe; then
    USE_SYSTEM_OPENSSL=1
    OPENSSL_INCLUDE_DIR="$include"
    OPENSSL_LIB_DIR="${OPENSSL_LIB_DIR:-$lib}"
    OPENSSL_PREFIX="$include"; OPENSSL_PREFIX="${OPENSSL_PREFIX%/include}"; OPENSSL_PREFIX="${OPENSSL_PREFIX:-/usr}"
    printf 'OpenSSL: reusing host %s (%s) — pinned build skipped\n' "$SYSTEM_OPENSSL_VERSION" "$lib"
    return 0
  fi
  if [[ "$SYSTEM_OPENSSL" == "require" ]]; then
    fail "SYSTEM_OPENSSL=require but the host OpenSSL at $include / $lib failed the compile+link+handshake probe"
  fi
  printf 'OpenSSL: host at %s did not pass the probe; building pinned version\n' "$include"
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

  select_openssl
  prefetch_archives
  fetch_source cpython python/cpython "$CPYTHON_COMMIT" "$CPYTHON_SHA256"
  local cpython_source="$FETCHED_SOURCE"
  local openssl_source=""
  if [[ "$USE_SYSTEM_OPENSSL" == "0" ]]; then
    fetch_source openssl python/cpython-source-deps "$OPENSSL_COMMIT" "$OPENSSL_SHA256"
    openssl_source="$FETCHED_SOURCE"
  fi
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
  # Describe the build conditions next to the objects. configure's cache assumes the
  # same environment; if the prefix path or the OpenSSL choice changed, the tree is
  # rebuilt from scratch instead of silently linking against stale objects.
  local build_desc="openssl=$([[ "$USE_SYSTEM_OPENSSL" == "1" ]] && printf system || printf pinned)"
  build_desc="$build_desc stage_layout=1 sqlite_flags=2"
  local desc_file="$cpython_source/.arena-build-desc"
  if [[ -f "$desc_file" && "$(cat "$desc_file")" != "$build_desc" ]]; then
    printf 'CPython build conditions changed (%s -> %s); rebuilding from scratch\n' \
      "$(cat "$desc_file")" "$build_desc"
    make_target_if_available "$cpython_source" distclean
  fi
  printf '%s\n' "$build_desc" >"$desc_file"
  printf 'Building CPython %s in staging prefix %s (JOBS=%s)\n' "$EXPECTED_PYTHON" "$stage" "$JOBS"

  make_target_if_available "$zlib_source" clean
  (cd "$zlib_source" && ./configure --prefix="$stage" && make -j"$JOBS" && make install)

  if [[ "$USE_SYSTEM_OPENSSL" == "0" ]]; then
    make_target_if_available "$openssl_source" clean
    (cd "$openssl_source" && ./config --prefix="$stage" --libdir=lib && make -j"$JOBS" && make install_sw)
  fi

  make_target_if_available "$libffi_source" clean
  chmod +x "$libffi_source/configure"
  # --disable-static: ctypes loads the .so; the .a is another full link for nothing.
  # --disable-docs: its configure pass alone cost ~4 s here, longer than its build.
  (cd "$libffi_source" && ./configure --prefix="$stage" --disable-static --disable-docs \
    && make -j"$JOBS" && make install)

  make_target_if_available "$bzip2_source" clean
  (cd "$bzip2_source" && make -j"$JOBS" && make install PREFIX="$stage")
  rm -f -- "$bzip2_source"/*.o "$bzip2_source"/libbz2.so*
  (cd "$bzip2_source" && make -f Makefile-libbz2_so CFLAGS='-O2 -fPIC -Wall -Winline' -j"$JOBS")
  install -m 755 "$bzip2_source/libbz2.so.1.0.8" "$stage/lib/"
  ln -sf libbz2.so.1.0.8 "$stage/lib/libbz2.so.1.0"
  ln -sf libbz2.so.1.0 "$stage/lib/libbz2.so"
  install -m 644 "$bzip2_source/bzlib.h" "$stage/include/"

  rm -f -- "$sqlite_source/sqlite3.o" "$sqlite_source/libsqlite3.so"
  # shellcheck disable=SC2086 # $SQLITE_CFLAGS is intentionally word-split
  (cd "$sqlite_source" && \
    gcc $SQLITE_CFLAGS -c sqlite3.c -o sqlite3.o && \
    gcc -shared -o libsqlite3.so sqlite3.o -lpthread -ldl -lm)
  install -m 644 "$sqlite_source/sqlite3.h" "$stage/include/"
  # sqlite3ext.h is what --enable-loadable-sqlite-extensions compiles against; without
  # it the option cannot be switched on later without rebuilding this prefix.
  if [[ -f "$sqlite_source/sqlite3ext.h" ]]; then
    install -m 644 "$sqlite_source/sqlite3ext.h" "$stage/include/"
  fi
  install -m 755 "$sqlite_source/libsqlite3.so" "$stage/lib/"

  # ── CPython configure/build ───────────────────────────────────────────────
  # The source tree lives in BUILD_ROOT/src and survives a run, so a like-for-like
  # rebuild (same pins, same prefix layout) can reuse its objects: re-running
  # `make` after a fresh `./configure` relinks what changed instead of recompiling
  # ~234 translation units. `make distclean` would throw that away — it is used only
  # when the tree is in an unknown state (no config.status or a half-built install).
  local openssl_args=()
  if [[ "$USE_SYSTEM_OPENSSL" == "1" ]]; then
    # --with-openssl handles -I/-l itself; the lib dir is passed because Debian's
    # multiarch libs (libssl.so) are not under the prefix's plain lib/, and rpath is
    # scoped to _ssl/_hashlib rather than smeared over every module.
    openssl_args=(--with-openssl="$OPENSSL_PREFIX" --with-openssl-rpath="$OPENSSL_LIB_DIR")
  else
    openssl_args=(--with-openssl="$stage" --with-openssl-rpath=auto)
  fi

  case "$MODE:$RECONFIGURE" in
    rebuild:* | *:1)
      # --rebuild-python (or an explicit RECONFIGURE=1) promises a from-scratch build.
      make_target_if_available "$cpython_source" distclean
      ;;
  esac
  (
    cd "$cpython_source"
    # Kept inside the build subshell on purpose: the staged loader path must be live
    # for the install step too (it runs the freshly built interpreter).
    export CPPFLAGS="-I$stage/include"
    export LDFLAGS="-L$stage/lib -Wl,-rpath,$PREFIX/lib"
    export LD_LIBRARY_PATH="$stage/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export PKG_CONFIG_PATH="$stage/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
    if [[ ! -x ./configure ]]; then
      printf 'CPython configure script missing; extraction is incomplete\n' >&2
      exit 1
    fi
    ./configure --prefix="$stage" "${openssl_args[@]}" || exit 1
    make -j"$JOBS" || exit 1
    make install || exit 1
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
    # The base interpreter is the one the venv probe above just exercised when the venv
    # is not itself a copy; re-running the smoke on an identical path is pure cost.
    if [[ "$PYTHON" == "$PROJECT_ROOT/.venv/bin/python" ]] || is_usable_python "$PYTHON"; then
      REUSED_VENV=1
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

ensure_uv_launcher() {
  local launcher="$PROJECT_ROOT/.venv/bin/uv"
  if [[ -x "$launcher" ]] && is_pinned_uv "$("$launcher" --version 2>/dev/null || true)"; then
    return 0
  fi
  if [[ -e "$launcher" && ! -L "$launcher" ]]; then
    fail "refusing to replace non-symlink .venv/bin/uv; inspect the project environment"
  fi
  ln -sfn -- "$UV_PATH" "$launcher"
  is_pinned_uv "$("$launcher" --version)" || fail "could not expose pinned uv in .venv/bin"
}

ensure_just() {
  local venv_bin="$PROJECT_ROOT/.venv/bin"
  local launcher="$venv_bin/just"
  if [[ -x "$launcher" ]] && is_pinned_just "$("$launcher" --version 2>/dev/null || true)"; then
    printf 'Reusing pinned just %s from %s\n' "$JUST_VERSION" "$launcher"
    return 0
  fi

  printf 'Installing %s into the external tool cache with a project .venv launcher\n' "$JUST_PACKAGE" >&2
  UV_TOOL_DIR="$BUILD_ROOT/just-tools" UV_TOOL_BIN_DIR="$venv_bin" \
    "$UV_PATH" tool install --force --python "$PYTHON" "$JUST_PACKAGE"
  is_pinned_just "$("$launcher" --version)" || fail "isolated just bootstrap did not produce just $JUST_VERSION"
}

ensure_gate_launchers() {
  ensure_uv_launcher
  ensure_just
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
  # uv ships as a py3-none wheel with its binary inside. Two extra interpreter starts
  # (create a throwaway venv, then run pip from it) bought nothing: install straight
  # into a staging directory that is validated and only then published.
  if ! "$PYTHON" -m pip install --disable-pip-version-check --only-binary=:all: \
      --target "$temporary" "uv==$UV_VERSION" >&2; then
    fail "could not install uv $UV_VERSION with $PYTHON"
  fi
  is_pinned_uv "$("$temporary/bin/uv" --version)" || fail "isolated uv bootstrap did not produce uv $UV_VERSION"
  if [[ -e "$tools_dir" ]]; then
    mv -- "$tools_dir" "$BUILD_ROOT/uv-tools-$UV_VERSION.previous.$(date +%Y%m%d%H%M%S)"
  fi
  mv -- "$temporary" "$tools_dir"
  printf '%s\n' "$tools_dir/bin/uv"
}

select_python
UV_PATH="$(ensure_uv)"
cd "$PROJECT_ROOT"
printf 'Syncing frozen dev environment with %s\n' "$UV_PATH"
UV_SYSTEM_CERTS=true "$UV_PATH" sync --frozen --extra dev --python "$PYTHON"
ensure_gate_launchers
# End-to-end verification always runs. VENVPROBE only tells it that the probe of this
# very .venv interpreter already succeeded while selecting it in this same run.
VENVPROBE="$REUSED_VENV" check_project_venv
printf 'ENVIRONMENT_READY: CPython %s; frozen dev extra and pinned uv/just gate launchers installed\n' "$EXPECTED_PYTHON"
