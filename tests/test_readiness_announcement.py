"""S12.2 (CT2/GAP1): announce workspace readiness to the model.

Bootstrap success was silent (only degradation prints) and nothing in the
prompt told the model that ``.venv`` exists — the 2026-08-31 l2 row burned
12 of 20 turns on environment archaeology next to a working venv. The
announcement rides ``system_prompt_extra`` (cacheable prefix, D7-compliant:
the block is static per run).

Kill-check: removing ``_readiness_prompt_extra(workspace)`` from the
drive_session call site in _cmd_run makes the C1 test below fail.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fa.cli import _READINESS_PROMPT_EXTRA, _cmd_run, _readiness_prompt_extra, build_parser
from tests.test_cli_ergonomics import _TEST_SECRETS, _CapturingTransport

_CHAT_MODELS_YAML = """\
chat:
  name: "test-model"
  family: "openai"
  chain:
    - provider: openrouter
      model: "test/model"
      base_url: "https://example.invalid/v1"
      api_key_env: TEST_FA_RUN_KEY
"""


# ── C0: the predicate and the pinned wording ─────────────────────────────────


def test_extra_present_iff_venv_bin_exists(tmp_path: Path) -> None:
    assert _readiness_prompt_extra(tmp_path) == "", "raw clone must not announce readiness"
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    assert _readiness_prompt_extra(tmp_path) == _READINESS_PROMPT_EXTRA


def test_extra_wording_is_pinned(tmp_path: Path) -> None:
    """The wording is the product contract (plan CT2); drift breaks the
    live env-row expectations and the models' learned invocation."""
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    extra = _readiness_prompt_extra(tmp_path)
    assert "./.venv" in extra
    assert "uv run pytest" in extra
    assert "pr_prepare" in extra
    assert "CHORE" in extra


# ── C1: the shipped _cmd_run drive path actually delivers it ─────────────────


def _run_chat_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _CapturingTransport:
    config = tmp_path / "models.yaml"
    config.write_text(_CHAT_MODELS_YAML, encoding="utf-8")
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    transport = _CapturingTransport()
    args = build_parser().parse_args(
        ["run", "-r", "chat", "--config", str(config), "--workspace", str(tmp_path), "note the check"]
    )
    code = _cmd_run(args, transport=transport, secrets=_TEST_SECRETS)
    assert code == 0
    return transport


def test_drive_path_announces_ready_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    transport = _run_chat_capture(tmp_path, monkeypatch)
    assert transport.system_messages, "no system messages captured"
    joined = "\n".join(transport.system_messages)
    assert "Workspace ready:" in joined, "readiness block never reached the model"
    assert "uv run pytest" in joined


def test_drive_path_silent_without_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _run_chat_capture(tmp_path, monkeypatch)
    joined = "\n".join(transport.system_messages)
    assert "Workspace ready:" not in joined, "false readiness announcement on a raw clone"
