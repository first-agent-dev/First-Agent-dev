from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_UPDATE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fa-update.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_fa_update_script_has_valid_bash_syntax() -> None:
    subprocess.run(["bash", "-n", str(_UPDATE_SCRIPT)], check=True)


def test_fa_update_script_tracks_actual_build_inputs() -> None:
    text = _UPDATE_SCRIPT.read_text(encoding="utf-8")

    assert '"Dockerfile.fa"' in text
    assert '"uv.lock"' in text
    assert '"scripts/fa-entrypoint.sh"' in text
    assert '"Dockerfile"' not in text


def test_fa_update_env_validation_ignores_commented_optional_fa_vars() -> None:
    text = _UPDATE_SCRIPT.read_text(encoding="utf-8")

    assert "extract_active_fa_vars" in text
    assert "#?" not in text
    assert "optional commented controls ignored" in text


def test_fa_update_runs_dev_sync_in_writable_workspace_not_image_snapshot() -> None:
    text = _UPDATE_SCRIPT.read_text(encoding="utf-8")

    assert "cd /workspace && uv sync --frozen --extra dev" in text
    assert "--directory /opt/first-agent" not in text
    assert "uv run python -m pytest" in text
