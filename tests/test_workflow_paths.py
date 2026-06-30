from __future__ import annotations

from pathlib import Path

from fa.cli import _workflow_artifact_paths


def test_workflow_artifact_paths_use_session_log_root(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    paths = _workflow_artifact_paths("wf-123")

    base = home / ".fa" / "session-log" / "wf-123"
    assert paths.base_dir == base
    assert paths.eval_report == base / "eval_report.json"
    assert paths.flow_state == base / "flow_state.json"
