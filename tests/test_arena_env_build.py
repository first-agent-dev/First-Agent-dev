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

    _write_executable(
        bin_dir / "python",
        '#!/usr/bin/env bash\nif [[ "$1" == "-m" ]]; then echo \'pytest 9.0.3\'; else cat >/dev/null; fi\n',
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
