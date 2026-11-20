"""Source contract checks for the pinned local CPython toolchain builder."""

from __future__ import annotations

import subprocess
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "arena-env-build.sh"


def test_staged_shared_libraries_are_available_during_python_install() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    start = source.index('    cd "$cpython_source"')
    end = source.index("\n  )\n", start)
    build_subshell = source[start:end]

    staged_loader_path = 'export LD_LIBRARY_PATH="$stage/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"'
    assert staged_loader_path in build_subshell
    assert build_subshell.index(staged_loader_path) < build_subshell.index("make install")
    assert 'export LDFLAGS="-L$stage/lib -Wl,-rpath,$PREFIX/lib"' in build_subshell


def test_script_keeps_final_prefix_rpath_and_staged_smoke_gate() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    assert 'export LDFLAGS="-L$stage/lib -Wl,-rpath,$PREFIX/lib"' in source
    assert 'LD_LIBRARY_PATH="$stage/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" runtime_smoke' in source
    assert 'fail "staged CPython failed the runtime/FTS5 smoke test' in source


def test_normal_setup_installs_pinned_just_and_exposes_uv_before_checking() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    assert 'readonly JUST_VERSION="1.57.0"' in source
    assert 'readonly JUST_PACKAGE="rust-just==$JUST_VERSION"' in source
    assert 'UV_TOOL_DIR="$BUILD_ROOT/just-tools" UV_TOOL_BIN_DIR="$venv_bin"' in source
    assert 'tool install --force --python "$PYTHON" "$JUST_PACKAGE"' in source
    assert 'ln -sfn -- "$UV_PATH" "$launcher"' in source

    sync = source.index('UV_SYSTEM_CERTS=true "$UV_PATH" sync --frozen')
    launchers = source.index("ensure_gate_launchers", sync)
    check = source.index("check_project_venv", launchers)
    assert sync < launchers < check


def _write_executable(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def _fake_checkout(tmp_path: Path) -> Path:
    root = tmp_path / "checkout"
    scripts = root / "scripts"
    bin_dir = root / ".venv" / "bin"
    scripts.mkdir(parents=True)
    bin_dir.mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='fake'\n", encoding="utf-8")
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    script = scripts / "arena-env-build.sh"
    script.write_bytes(_SCRIPT.read_bytes())
    script.chmod(0o755)
    subprocess.run(["git", "init", "-q", str(root)], check=True)

    # Behaves like a provisioning interpreter: answers the version probe with exit 0,
    # reports itself as the venv base executable, and swallows the runtime smoke script
    # on stdin. Without the base-executable answer select_python would fall through to a
    # real CPython build.
    _write_executable(
        bin_dir / "python",
        "#!/usr/bin/env bash\n"
        'if [[ "$1" == "-m" ]]; then echo \'pytest 9.0.3\'; exit 0; fi\n'
        'if [[ "$2" == *"_base_executable"* ]]; then\n'
        '  echo "$(cd "$(dirname "$0")" && pwd)/python"; exit 0\n'
        "fi\n"
        "cat >/dev/null\n",
    )
    _write_executable(bin_dir / "uv", "#!/usr/bin/env bash\necho 'uv 0.13.7'\n")
    _write_executable(bin_dir / "just", "#!/usr/bin/env bash\necho 'just 1.57.0'\n")
    _write_executable(bin_dir / "ruff", "#!/usr/bin/env bash\necho 'ruff 0.16.0'\n")
    for tool in ("pytest", "deptry", "pylint", "mypy", "pyrefly", "mutmut", "vulture", "pip-audit", "fa"):
        _write_executable(bin_dir / tool, "#!/usr/bin/env bash\nexit 0\n")
    return script


def test_check_mode_accepts_pinned_gate_environment_without_mutating_it(tmp_path: Path) -> None:
    script = _fake_checkout(tmp_path)
    result = subprocess.run([str(script), "--check"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "pinned uv/just and just-check dev tools present" in result.stdout
    assert (script.parent.parent / ".venv" / "bin" / "just").exists()


def test_check_mode_fails_closed_when_just_or_uv_gate_launcher_is_missing(tmp_path: Path) -> None:
    script = _fake_checkout(tmp_path)
    bin_dir = script.parent.parent / ".venv" / "bin"
    (bin_dir / "just").unlink()
    missing_just = subprocess.run([str(script), "--check"], capture_output=True, text=True, check=False)
    assert missing_just.returncode != 0
    assert "gate launcher is missing: .venv/bin/just" in missing_just.stderr

    (bin_dir / "just").write_text("#!/usr/bin/env bash\necho 'just 1.57.0'\n", encoding="utf-8")
    (bin_dir / "just").chmod(0o755)
    (bin_dir / "uv").unlink()
    missing_uv = subprocess.run([str(script), "--check"], capture_output=True, text=True, check=False)
    assert missing_uv.returncode != 0
    assert "gate launcher is missing: .venv/bin/uv" in missing_uv.stderr


def _openssl_section(source: str) -> str:
    return source[source.index("openssl_candidates() {") : source.index("build_python() {")]


def test_host_openssl_is_discovered_not_assumed() -> None:
    """Arena updates packages; the script must find whatever 3.x is installed."""
    source = _SCRIPT.read_text(encoding="utf-8")
    section = _openssl_section(source)
    # pkg-config first (authoritative, knows multiarch/custom prefixes),
    # then a search list, then the Debian multiarch lib dir as a last resort.
    assert "pkg-config --exists openssl" in section
    assert "OPENSSL_SEARCH_INCLUDES" in source
    assert "/usr/local/include" in source and "/opt/openssl/include" in source
    assert "/usr/lib/x86_64-linux-gnu" in section
    # every candidate is probed; the first usable one wins
    assert "while IFS='|' read -r include lib" in section
    assert "OPENSSL_INCLUDE_DIR:-" in section


def test_openssl_version_policy_covers_any_stable_3x() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    section = _openssl_section(source)
    assert "readonly OPENSSL_MIN_MAJOR=3" in source
    assert "readonly OPENSSL_MAX_MAJOR=3" in source
    # compile-time major from the headers ...
    assert "OPENSSL_VERSION_NUMBER >> 28" in section
    # ... compared with the major the runtime library actually reports
    assert "OpenSSL_version_num() >> 28" in section
    assert "header/library major mismatch" in section
    # and the reachable range comes from the constants, not a hardcoded literal
    assert '-DMIN_MAJOR="$OPENSSL_MIN_MAJOR"' in section
    assert "0x30000000L" not in section


def test_openssl_probe_actually_runs_and_reports_why_it_failed() -> None:
    """Compile+link alone misses "imports fine, cannot handshake"."""
    section = _openssl_section(_SCRIPT.read_text(encoding="utf-8"))
    assert "SSL_CTX_new" in section
    assert '"$probe_dir/probe" 2>&1)' in section  # executed, output captured
    # failure detail must travel on stderr: the caller uses command substitution,
    # so a variable assignment inside the probe would be lost in the subshell.
    assert ">&2" in section
    assert "OPENSSL_PROBE_REASON" not in section
    # the caller preserves that detail for the operator
    assert "reason_file" in section
    assert "not usable" in section


def test_system_openssl_has_all_three_documented_outcomes() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    select = source[source.index("select_openssl() {") : source.index("build_python() {")]
    build = source[source.index("build_python() {") :]
    assert 'if [[ "$SYSTEM_OPENSSL" == "require" ]]; then' in select
    assert "SYSTEM_OPENSSL=require but no usable host OpenSSL" in select
    assert 'if [[ "$SYSTEM_OPENSSL" == "never" ]]; then' in select
    assert "building pinned version" in select
    assert 'if [[ "$USE_SYSTEM_OPENSSL" == "0" ]]; then\n    fetch_source openssl' in build
    assert '"openssl python/cpython-source-deps $OPENSSL_COMMIT $OPENSSL_SHA256"' in source


def test_cpython_tree_objects_are_reused_unless_conditions_changed() -> None:
    """Reuse objects only when the build conditions match, otherwise distclean."""
    source = _SCRIPT.read_text(encoding="utf-8")
    build = source[source.index("build_python() {") :]
    assert 'if [[ -f "$desc_file" && "$(cat "$desc_file")" != "$build_desc" ]]; then' in build
    assert "rebuilding from scratch" in build
    guard = build[build.index('if [[ -f "$desc_file"') :]
    guard = guard[: guard.index("  fi\n")]
    assert "distclean" in guard
    assert build.index('if [[ -f "$desc_file"') < build.index("./configure --prefix=")
    assert 'openssl=$([[ "$USE_SYSTEM_OPENSSL" == "1" ]]' in build
    assert "rebuild:* | *:1)" in build


def test_sqlite_is_built_once_with_flags_shared_with_bundled_module() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    assert 'readonly SQLITE_CFLAGS="' in source
    flags = source[source.index('readonly SQLITE_CFLAGS="') :].split('"')[1]
    assert "SQLITE_ENABLE_FTS5" in flags
    assert "SQLITE_ENABLE_FTS3" in flags
    assert "gcc -O2 -fPIC -DSQLITE_ENABLE_FTS5 -c" not in source
    assert 'install -m 644 "$sqlite_source/sqlite3ext.h"' in source


def _probe_c_source() -> str:
    """The C probe as the script ships it, so the test compiles the real code."""
    source = _SCRIPT.read_text(encoding="utf-8")
    start = source.index("cat >\"$probe_dir/probe.c\" <<'C'")
    start = source.index("\n", start) + 1
    end = source.index("\nC\n", start)
    return source[start:end]


_PROBE_STUB_HEADER = """
#include <stdio.h>
#ifndef FAKE_VERSION_NUMBER
#define FAKE_VERSION_NUMBER 0x30000000L
#endif
#define OPENSSL_VERSION_NUMBER FAKE_VERSION_NUMBER
#define OPENSSL_VERSION_TEXT "stub"
#define OPENSSL_VERSION 0
typedef struct ssl_ctx_st SSL_CTX;
const void *TLS_client_method(void);
SSL_CTX *SSL_CTX_new(const void *);
void SSL_CTX_free(SSL_CTX *);
const char *OpenSSL_version(int);
unsigned long OpenSSL_version_num(void);
"""

_PROBE_STUB_IMPL = """
#include <stdio.h>
#include "openssl/ssl.h"
#ifndef FAKE_RUNTIME_MAJOR
#define FAKE_RUNTIME_MAJOR 3
#endif
#ifndef FAKE_CTX_FAILS
#define FAKE_CTX_FAILS 0
#endif
const void *TLS_client_method(void) { return 0; }
SSL_CTX *SSL_CTX_new(const void *m) { (void) m; return FAKE_CTX_FAILS ? 0 : (SSL_CTX *) 1; }
void SSL_CTX_free(SSL_CTX *c) { (void) c; }
unsigned long OpenSSL_version_num(void) { return ((unsigned long) FAKE_RUNTIME_MAJOR) << 28; }
const char *OpenSSL_version(int t) { (void) t; return "stub runtime"; }
"""


def _run_probe(
    tmp_path: Path,
    *,
    header_major: int,
    runtime_major: int,
    context_fails: bool = False,
    min_major: int = 3,
    max_major: int = 3,
) -> subprocess.CompletedProcess[str]:
    """Compile the shipped probe against a stub OpenSSL with a chosen pair of majors."""
    include = tmp_path / "include" / "openssl"
    include.mkdir(parents=True)
    (include / "ssl.h").write_text(_PROBE_STUB_HEADER, encoding="utf-8")
    (include / "err.h").write_text("#pragma once\n", encoding="utf-8")
    (tmp_path / "stub.c").write_text(_PROBE_STUB_IMPL, encoding="utf-8")
    (tmp_path / "probe.c").write_text(_probe_c_source(), encoding="utf-8")
    binary = tmp_path / "probe"
    build = subprocess.run(
        [
            "cc",
            f"-DMIN_MAJOR={min_major}",
            f"-DMAX_MAJOR={max_major}",
            f"-DFAKE_VERSION_NUMBER=0x{header_major}0000000L",
            f"-DFAKE_RUNTIME_MAJOR={runtime_major}",
            f"-DFAKE_CTX_FAILS={int(context_fails)}",
            "-I",
            str(tmp_path / "include"),
            str(tmp_path / "probe.c"),
            str(tmp_path / "stub.c"),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    return subprocess.run([str(binary)], capture_output=True, text=True, check=False)


def test_probe_accepts_any_matching_3x_pair(tmp_path: Path) -> None:
    """3.0, 3.2, 3.5 ... must all pass: Arena updates packages, the script follows."""
    for major, minor in ((3, 0), (3, 2), (3, 5)):
        result = _run_probe(
            tmp_path / f"m{major}{minor}",
            header_major=major,
            runtime_major=major,
        )
        assert result.returncode == 0, result.stdout
    assert _run_probe(tmp_path / "ok", header_major=3, runtime_major=3).returncode == 0


def test_probe_rejects_versions_outside_the_supported_range(tmp_path: Path) -> None:
    below = _run_probe(tmp_path / "below", header_major=1, runtime_major=1)
    assert below.returncode == 1, "1.x headers must be rejected"
    above = _run_probe(tmp_path / "above", header_major=4, runtime_major=4)
    assert above.returncode == 1, "4.x headers must be rejected until the range is moved"
    runtime_above = _run_probe(tmp_path / "runtime-above", header_major=3, runtime_major=4)
    assert runtime_above.returncode == 2, "a 4.x runtime behind 3.x headers must be rejected"


def test_probe_rejects_header_library_major_mismatch(tmp_path: Path) -> None:
    """Split install: in-range headers, out-of-range library (`import ssl` works; TLS does not).

    Both orders matter. A library one major *below* the headers is caught by the
    range check first (exit 2), a library one major *above* them can only be caught
    by the explicit header/runtime comparison (exit 3) — which is the case this
    test pins, because that is the one a version-range check alone would miss.
    """
    older_runtime = _run_probe(tmp_path / "older", header_major=3, runtime_major=1)
    assert older_runtime.returncode == 2, older_runtime.stdout
    # Within a single-major policy range the range check always fires first, so the
    # comparison only has teeth while the range spans majors; widen it to prove it.
    mismatched = _run_probe(
        tmp_path / "newer",
        header_major=2,
        runtime_major=3,
        min_major=2,
        max_major=3,
    )
    assert mismatched.returncode == 3, mismatched.stdout
    assert "mismatch" in mismatched.stdout.lower()


def test_probe_rejects_a_library_that_cannot_build_a_tls_context(tmp_path: Path) -> None:
    result = _run_probe(tmp_path / "no-ctx", header_major=3, runtime_major=3, context_fails=True)
    assert result.returncode == 4
    assert "TLS client context" in result.stdout


def test_probe_range_comes_from_the_constants(tmp_path: Path) -> None:
    """The range is a policy constant, so moving it moves the behaviour."""
    strict = _run_probe(
        tmp_path / "strict",
        header_major=4,
        runtime_major=4,
        min_major=4,
        max_major=4,
    )
    assert strict.returncode == 0, "a raised policy range must accept 4.x"


def _run_select_openssl(tmp_path: Path, *, mode: str, include: str, lib: str) -> subprocess.CompletedProcess[str]:
    """Run the shipped select_openssl in isolation, with a stubbed fail()."""
    source = _SCRIPT.read_text(encoding="utf-8")
    consts = source[
        source.index("# Any stable OpenSSL 3.x is acceptable") : source.index('readonly OPENSSL_SEARCH_INCLUDES="')
    ]
    consts += source[source.index('readonly OPENSSL_SEARCH_INCLUDES="') :].split("\n", 1)[0] + "\n"
    functions = source[source.index("openssl_candidates() {") : source.index("build_python() {")]
    tmp_path.mkdir(parents=True, exist_ok=True)
    harness = tmp_path / "select.sh"
    harness.write_text(
        "#!/usr/bin/env bash\nset -Eeuo pipefail\n"
        f"BUILD_ROOT={tmp_path}\nmkdir -p $BUILD_ROOT\n"
        "fail() { printf 'FAIL: %s\\n' \"$*\" >&2; exit 9; }\n" + consts + "\n" + functions + "\nselect_openssl\n",
        encoding="utf-8",
    )
    harness.chmod(0o755)
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "SYSTEM_OPENSSL": mode,
        "OPENSSL_INCLUDE_DIR": include,
        "OPENSSL_LIB_DIR": lib,
    }
    return subprocess.run([str(harness)], capture_output=True, text=True, check=False, env=env)


def test_select_openssl_behaviour_for_each_mode(tmp_path: Path) -> None:
    """Behavioural, not textual: run the real selection logic.

    Arena updates its packages, so the contract is "find a usable 3.x or fall back",
    not "find exactly the version we shipped against".
    """
    unusable_include = str(tmp_path / "nope")
    lib = "/usr/lib/x86_64-linux-gnu"

    # auto + nothing usable: falls back to the pinned build, and says why.
    fallback = _run_select_openssl(tmp_path / "auto", mode="auto", include=unusable_include, lib=lib)
    assert fallback.returncode == 0, fallback.stderr
    assert "building pinned version" in fallback.stdout
    # the operator must learn which candidate failed and why
    assert "no openssl/ssl.h under" in fallback.stdout

    # require + nothing usable: aborts (exit 9 from the stubbed fail) with details.
    strict = _run_select_openssl(tmp_path / "require", mode="require", include=unusable_include, lib=lib)
    assert strict.returncode == 9, strict.stdout
    assert "SYSTEM_OPENSSL=require" in strict.stderr
    assert "no openssl/ssl.h under" in strict.stderr

    # never: does not even look, goes straight to the pinned build.
    never = _run_select_openssl(tmp_path / "never", mode="never", include=unusable_include, lib=lib)
    assert never.returncode == 0, never.stderr
    assert "SYSTEM_OPENSSL=never" in never.stdout
    assert "no openssl/ssl.h" not in never.stdout
