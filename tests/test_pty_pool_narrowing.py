"""Tests for PtySession pane narrowing and fallback behavior.

These tests verify the type-safe narrowing of self.pane and the
graceful degradation when tmux pane initialization fails.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fa.runtime.pty_pool import PtySession


class TestPtySessionPaneNarrowing:
    """Verify pane narrowing before dereference (PY7 closure)."""

    def test_pane_none_triggers_fallback(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """If tmux session exists but pane is None, RuntimeError is raised internally
        and caught by the outer except which falls back to pexpect.

        The narrowing check raises RuntimeError("tmux pane not available after session
        setup"), which is caught by the outer except Exception. This logs a warning
        and triggers pexpect fallback. The contract is: no AttributeError on None.send_keys().
        """
        import logging

        mock_server = MagicMock()
        mock_session = MagicMock()

        # Session exists but active_window.active_pane returns None
        mock_session.active_window.active_pane = None
        mock_server.new_session.return_value = mock_session

        # The narrowing check raises RuntimeError, caught by outer except -> fallback
        with caplog.at_level(logging.WARNING, logger="fa.runtime.pty_pool"):
            session = PtySession("test", tmp_path, server=mock_server)

        # Contract: no silent None dereference; falls back to pexpect
        assert session._is_fallback is True
        assert session.pane is None

        # Verify the warning was logged (open stand: errors are loud)
        assert any("tmux pane not available" in msg for msg in caplog.messages), (
            f"Expected 'tmux pane not available' warning in logs, got: {caplog.messages}"
        )

    def test_pane_available_sends_setup_cmd(self, tmp_path: Path) -> None:
        """When pane is available, setup command is sent."""
        mock_server = MagicMock()
        mock_session = MagicMock()
        mock_pane = MagicMock()

        mock_session.active_window.active_pane = mock_pane
        mock_server.new_session.return_value = mock_session

        # Mock the capture-pane command to return sentinel immediately
        mock_capture_result = MagicMock()
        mock_capture_result.stdout = ["FA_READY_test_abc123"]
        mock_pane.cmd.return_value = mock_capture_result

        PtySession("test", tmp_path, server=mock_server)

        # Verify send_keys was called with setup command
        assert mock_pane.send_keys.called
        call_args = mock_pane.send_keys.call_args[0][0]
        assert "PS1" in call_args
        assert "PROMPT_COMMAND" in call_args

    def test_pane_init_failure_falls_back_to_pexpect(self, tmp_path: Path) -> None:
        """If pane initialization fails, session falls back to pexpect."""
        mock_server = MagicMock()
        mock_session = MagicMock()

        # Make active_pane raise an exception
        type(mock_session).active_window = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("pane init failed"))
        )
        mock_server.new_session.return_value = mock_session

        session = PtySession("test", tmp_path, server=mock_server)

        # Should fall back to pexpect (or subprocess fallback)
        assert session._is_fallback is True
        assert session.pane is None


class TestPtySessionFallbackBehavior:
    """Verify pexpect fallback when tmux is unavailable."""

    def test_no_server_uses_pexpect_fallback(self, tmp_path: Path) -> None:
        """When no tmux server is provided, pexpect fallback is used."""
        session = PtySession("test", tmp_path, server=None)

        # Should be in fallback mode
        assert session._is_fallback is True
        assert session.pane is None

    def test_run_without_pane_returns_error_result(self, tmp_path: Path) -> None:
        """If _run_tmux is called with pane=None, it returns error result."""
        mock_server = MagicMock()
        mock_session = MagicMock()
        mock_pane = MagicMock()

        mock_session.active_window.active_pane = mock_pane
        mock_server.new_session.return_value = mock_session

        # Mock the capture-pane to return sentinel
        mock_capture_result = MagicMock()
        mock_capture_result.stdout = ["FA_READY_test_abc123"]
        mock_pane.cmd.return_value = mock_capture_result

        session = PtySession("test", tmp_path, server=mock_server)

        # Now set pane to None to simulate failure after init
        session.pane = None
        session._is_fallback = False

        result = session._run_tmux("echo hello", timeout=1)

        assert result.exit_code == -1
        assert "No pane available" in result.stdout


class TestPtySessionSentinelHandling:
    """Verify sentinel tokens are unique per session."""

    def test_sentinel_tokens_are_unique(self, tmp_path: Path) -> None:
        """Each session gets unique sentinel, exit, and end tokens."""
        session1 = PtySession("s1", tmp_path, server=None)
        session2 = PtySession("s2", tmp_path, server=None)

        # Tokens should include session_id
        assert "s1" in session1._sentinel_token
        assert "s2" in session2._sentinel_token

        # Tokens should be unique (UUID component)
        assert session1._sentinel_token != session2._sentinel_token
        assert session1._exit_token != session2._exit_token
        assert session1._end_token != session2._end_token
