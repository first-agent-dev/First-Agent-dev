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
    return source[source.index("openssl_probe() {") : source.index("build_python() {")]


def test_host_openssl_requires_a_probe_before_it_is_trusted() -> None:
    """A version string or a shared object is not evidence that TLS works.

    The probe must compile against the host headers, link against the host libs and
    actually run a TLS_client_method context — the failure mode it prevents is an
    `ssl` module that imports but cannot complete a handshake.
    """
    section = _openssl_section(_SCRIPT.read_text(encoding="utf-8"))
    assert "openssl/ssl.h" in section  # compile against real headers
    assert "-lssl -lcrypto" in section  # link, not just dlopen
    assert "SSL_CTX_new" in section  # a handshake-capable context is constructed
    assert "0x30000000L" in section  # contracts assume OpenSSL 3.x
    # and the probe binary is actually EXECUTED (not just built): the run is the
    # only step that can catch "imports fine, cannot complete a handshake".
    assert '"$probe_dir/probe")"' in section


def test_system_openssl_has_all_three_documented_outcomes() -> None:
    """require=fail loudly, auto=fall back and build, never=always build.

    Each outcome is asserted on the branch that implements it, so deleting a
    branch fails the test instead of silently changing the policy.
    """
    source = _SCRIPT.read_text(encoding="utf-8")
    select = source[source.index("select_openssl() {") : source.index("build_python() {")]
    build = source[source.index("build_python() {") :]

    # require: a failed probe must abort instead of silently spending minutes.
    assert 'if [[ "$SYSTEM_OPENSSL" == "require" ]]; then' in select
    assert "SYSTEM_OPENSSL=require but the host OpenSSL" in select
    # never: skip the probe and build the pinned archive.
    assert 'if [[ "$SYSTEM_OPENSSL" == "never" ]]; then' in select
    # auto (the default): a failed probe falls through to the pinned build.
    assert "did not pass the probe; building pinned version" in select
    # build: the archive is fetched and compiled only when the host was rejected.
    assert 'if [[ "$USE_SYSTEM_OPENSSL" == "0" ]]; then\n    fetch_source openssl' in build
    assert 'if [[ "$USE_SYSTEM_OPENSSL" == "0" ]]; then\n    make_target_if_available' in build
    # and it stays in the prefetch list, otherwise the fallback would rebuild the cache.
    assert '"openssl python/cpython-source-deps $OPENSSL_COMMIT $OPENSSL_SHA256"' in source


def test_cpython_tree_objects_are_reused_unless_conditions_changed() -> None:
    """Reuse objects only when the build conditions match, otherwise distclean."""
    source = _SCRIPT.read_text(encoding="utf-8")
    build = source[source.index("build_python() {") :]

    # 1. the conditions are compared, not merely written somewhere
    assert 'if [[ -f "$desc_file" && "$(cat "$desc_file")" != "$build_desc" ]]; then' in build
    assert "rebuilding from scratch" in build
    # 2. crossing that comparison runs distclean INSIDE the if, before configure
    guard = build[build.index('if [[ -f "$desc_file"') :]
    guard = guard[: guard.index("  fi\n")]
    assert "distclean" in guard
    assert "rebuilding from scratch" in guard
    assert build.index('if [[ -f "$desc_file"') < build.index("./configure --prefix=")
    # 3. the description covers what configure's cache depends on
    assert 'openssl=$([[ "$USE_SYSTEM_OPENSSL" == "1" ]]' in build
    # 4. --rebuild-python / RECONFIGURE=1 still force a from-scratch build
    assert "rebuild:* | *:1)" in build


def test_sqlite_is_built_once_with_flags_shared_with_bundled_module() -> None:
    source = _SCRIPT.read_text(encoding="utf-8")
    assert 'readonly SQLITE_CFLAGS="' in source
    flags = source[source.index('readonly SQLITE_CFLAGS="') :].split('"')[1]
    assert "SQLITE_ENABLE_FTS5" in flags  # instant search needs it
    assert "SQLITE_ENABLE_FTS3" in flags  # 3.53 default must not silently vanish
    assert "gcc -O2 -fPIC -DSQLITE_ENABLE_FTS5 -c" not in source  # no duplicate literal flags
    # installed from the source tree (a bare mention of the name is not enough)
    assert 'install -m 644 "$sqlite_source/sqlite3ext.h"' in source
