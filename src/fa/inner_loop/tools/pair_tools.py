"""Pair over Autonomy tools — checkpoint, undo, diff, send_ctrl_c — Stage 0

Senior refactor v2:
- Checkpoint efficient automated per git-checkpoint skill + checkpoint commit patterns:
  * Frequency after every meaningful change ratchet effect
  * Atomic small commits clear messages
  * Ephemeral checkpoint branches agent/checkpoint-<run_id>-<ts> not pushed to origin (merges manual)
  * git add -A respects .gitignore (covers .fa/, node_modules), not -u tracked-only which misses new files
  * Fallback stash create/store for recovery without polluting history
- Undo restores via reset --hard to checkpoint id or branch, or stash pop
- Diff structured --stat + truncated preview token efficient
- send_ctrl_c via PtyPool DI
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from fa.inner_loop.registry import ToolResult, ToolSpec
import logging

logger = logging.getLogger(__name__)


def _run_git(args: list[str], cwd: Path, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    """Helper with timeout, failure-observable, no shell=True."""
    return subprocess.run(  # noqa: S603 -- trusted binary per ADR-6, list args, no shell
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def build_checkpoint_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        message = str(params.get("message", "checkpoint before task")).strip()
        if not message:
            message = "checkpoint before task"
        run_id = str(params.get("run_id", ""))[:12] or f"{int(time.time())}"

        try:
            # Check if changes exist
            status = _run_git(["git", "status", "--porcelain"], cwd=root, timeout=5)
            if status.stdout.strip() == "":
                return ToolResult.ok(
                    f"No changes to checkpoint at {root}",
                    result={"checkpoint_id": "no-changes", "message": message, "method": "no-op"},
                )

            # Stage all respecting .gitignore (covers .fa/, node_modules, etc)
            # -A respects .gitignore, includes new untracked not ignored, includes deletions
            add = _run_git(["git", "add", "-A"], cwd=root, timeout=10)
            if add.returncode != 0:
                logger.warning(f"git add -A failed: {add.stderr}")

            # Commit atomic small commit with clear message per checkpoint patterns doc
            commit_msg = f"checkpoint: {message}\n\n- run_id: {run_id}\n- timestamp: {int(time.time())}\n- auto checkpoint before task per pair over autonomy"
            commit = _run_git(["git", "commit", "-m", commit_msg], cwd=root, timeout=10)

            if commit.returncode == 0:
                rev = _run_git(["git", "rev-parse", "HEAD"], cwd=root, timeout=5)
                checkpoint_id = rev.stdout.strip() if rev.returncode == 0 else "unknown"
                # Create ephemeral checkpoint branch pointing to this commit, not checkout (keep current branch)
                branch_name = f"agent/checkpoint-{run_id}-{int(time.time()) % 100000}"
                # Sanitize branch name via same logic as worktree_manager
                import re

                branch_sanitized = re.sub(r"[^a-zA-Z0-9-_/]", "-", branch_name)[:80].strip("-")
                branch_res = _run_git(["git", "branch", branch_sanitized, checkpoint_id], cwd=root, timeout=5)
                # Branch creation failure is non-fatal, just warning
                if branch_res.returncode != 0:
                    logger.warning(f"checkpoint branch creation failed: {branch_res.stderr}")

                return ToolResult.ok(
                    f"Checkpoint created: {checkpoint_id} branch {branch_sanitized} - {message}",
                    result={
                        "checkpoint_id": checkpoint_id,
                        "branch": branch_sanitized,
                        "method": "commit_A_branch",
                        "message": message,
                    },
                )

            # Fallback: stash create + store (does not affect branch history, recoverable via stash list)
            # stash create returns hash, store saves it
            stash_create = _run_git(["git", "stash", "create"], cwd=root, timeout=10)
            if stash_create.returncode == 0 and stash_create.stdout.strip():
                stash_hash = stash_create.stdout.strip()
                store = _run_git(
                    ["git", "stash", "store", "-m", f"checkpoint: {message}", stash_hash],
                    cwd=root,
                    timeout=10,
                )
                if store.returncode == 0:
                    return ToolResult.ok(
                        f"Checkpoint via stash store: {stash_hash} - {message}",
                        result={
                            "checkpoint_id": stash_hash,
                            "method": "stash_create_store",
                            "message": message,
                        },
                    )

            # Last fallback: stash push --keep-index --include-untracked respects .gitignore
            stash_push = _run_git(
                ["git", "stash", "push", "-m", f"checkpoint: {message}", "--keep-index", "--include-untracked"],
                cwd=root,
                timeout=10,
            )
            if stash_push.returncode == 0:
                return ToolResult.ok(
                    f"Checkpoint via stash push: {message}",
                    result={
                        "checkpoint_id": stash_push.stdout.strip(),
                        "method": "stash_push_keep_index",
                        "message": message,
                    },
                )

            return ToolResult.fail(
                "checkpoint_failed",
                f"Commit and stash failed: {commit.stderr} {stash_push.stderr}",
                retryable=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult.fail("checkpoint_timeout", f"Checkpoint timed out: {exc}", retryable=True)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("checkpoint_error", f"Checkpoint failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.checkpoint",
        description="Create checkpoint via git add -A (respects .gitignore) + commit + ephemeral branch agent/checkpoint-<run_id>-<ts> (local only, not pushed to origin/main). Fallback stash create/store. For pair over autonomy, checkpoint before task, undo restores. Automated, merges to origin/main manual last step.",
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Checkpoint message"},
                "run_id": {"type": "string", "description": "Optional run_id for branch naming"},
            },
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "pair", "checkpoint"),
        max_context_bytes=1000,
    )


def build_undo_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        checkpoint_id = params.get("checkpoint_id")
        try:
            # If checkpoint_id is a branch name agent/checkpoint-*, checkout that branch or reset to it
            if checkpoint_id and isinstance(checkpoint_id, str):
                # If it's a branch, try checkout
                if checkpoint_id.startswith("agent/checkpoint-") or checkpoint_id.startswith("ai/"):
                    # Try to checkout existing branch
                    result = _run_git(["git", "checkout", checkpoint_id], cwd=root, timeout=10)
                    if result.returncode == 0:
                        return ToolResult.ok(
                            f"Checked out checkpoint branch {checkpoint_id}",
                            result={"restored_to": checkpoint_id, "method": "checkout_branch"},
                        )
                # If it's a commit hash >=7 chars
                if checkpoint_id != "no-changes" and len(checkpoint_id) >= 7:
                    result = _run_git(["git", "reset", "--hard", checkpoint_id], cwd=root, timeout=10)
                    if result.returncode == 0:
                        return ToolResult.ok(
                            f"Undone to checkpoint {checkpoint_id}",
                            result={"restored_to": checkpoint_id, "method": "reset"},
                        )

            # Try reset --hard HEAD~1 (undo last commit)
            reset = _run_git(["git", "reset", "--hard", "HEAD~1"], cwd=root, timeout=10)
            if reset.returncode == 0:
                return ToolResult.ok(
                    "Undone last commit via reset --hard HEAD~1",
                    result={"method": "reset_HEAD~1", "output": reset.stdout[:500]},
                )

            # Try stash pop
            pop = _run_git(["git", "stash", "pop"], cwd=root, timeout=10)
            if pop.returncode == 0:
                return ToolResult.ok(
                    "Undone via stash pop",
                    result={"method": "stash_pop", "output": pop.stdout[:500]},
                )

            return ToolResult.fail(
                "undo_failed",
                f"Reset and stash pop failed: {reset.stderr} {pop.stderr}",
                retryable=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult.fail("undo_timeout", f"Undo timed out: {exc}", retryable=True)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("undo_error", f"Undo failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.undo",
        description="Undo last checkpoint via git checkout checkpoint branch, or reset --hard <id>, or reset --hard HEAD~1, or stash pop — Ctrl+Z for pair over autonomy. Checkpoint branches local only, merges to origin/main manual.",
        input_schema={"type": "object", "properties": {"checkpoint_id": {"type": "string"}}},
        permission="workspace",
        handler=handler,
        tags=("fs", "pair", "undo"),
        max_context_bytes=1000,
    )


def build_diff_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            base = params.get("base", "HEAD")
            if not isinstance(base, str):
                base = "HEAD"
            target = params.get("target", "")
            # Structured summary: --stat first
            stat_cmd = ["git", "diff", "--stat", base]
            if target and isinstance(target, str) and target:
                stat_cmd = ["git", "diff", "--stat", f"{base}..{target}"]
            stat_res = _run_git(stat_cmd, cwd=root, timeout=10)
            stat_text = stat_res.stdout

            diff_cmd = ["git", "diff", base]
            if target and isinstance(target, str) and target:
                diff_cmd = ["git", "diff", f"{base}..{target}"]
            diff_res = _run_git(diff_cmd, cwd=root, timeout=10)
            diff_text = diff_res.stdout

            files_changed = []
            for line in stat_text.splitlines():
                if "|" in line:
                    files_changed.append(line.split("|")[0].strip())

            if len(diff_text) > 8000:
                preview = (
                    diff_text[:500]
                    + f"\n...[truncated {len(diff_text)} chars, {len(diff_text.splitlines())} lines]...\n"
                    + diff_text[-500:]
                )
                summary = f"Diff {len(diff_text)} chars, {len(diff_text.splitlines())} lines, {len(files_changed)} files (truncated preview)\n{stat_text[:1000]}"
                return ToolResult.ok(
                    summary,
                    result={
                        "diff": preview,
                        "stat": stat_text[:4000],
                        "files_changed": files_changed,
                        "truncated": True,
                        "full_chars": len(diff_text),
                        "lines": len(diff_text.splitlines()),
                    },
                )
            summary = f"Diff {len(diff_text)} chars, {len(diff_text.splitlines())} lines, {len(files_changed)} files\n{stat_text[:1000]}"
            return ToolResult.ok(
                summary,
                result={
                    "diff": diff_text,
                    "stat": stat_text,
                    "files_changed": files_changed,
                    "truncated": False,
                },
            )
        except subprocess.TimeoutExpired as exc:
            return ToolResult.fail("diff_timeout", f"Diff timed out: {exc}", retryable=True)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("diff_error", f"Diff failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.diff",
        description="Returns git diff structured between base and target (default HEAD) with --stat summary + truncated diff token efficient — for pair over autonomy review before PR, merges to origin/main manual last step.",
        input_schema={
            "type": "object",
            "properties": {"base": {"type": "string"}, "target": {"type": "string"}},
        },
        permission="read",
        handler=handler,
        tags=("fs", "pair", "diff"),
        max_context_bytes=4000,
    )


def build_send_ctrl_c_tool(pty_pool: object | None = None) -> ToolSpec:
    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            session_id = str(params.get("session_id", "main"))
            if pty_pool is None:
                return ToolResult.ok(
                    "No PTY pool available, Ctrl+C not needed (stateless bash)",
                    result={"session_id": session_id, "status": "no-pool"},
                )
            try:
                sessions = getattr(pty_pool, "sessions", {})
                msg = sessions[session_id].send_ctrl_c() if session_id in sessions else "session not found"
                return ToolResult.ok(
                    f"Sent Ctrl+C to {session_id}: {msg}",
                    result={"session_id": session_id, "msg": msg},
                )
            except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
                return ToolResult.fail(
                    "ctrl_c_failed",
                    f"Failed to send Ctrl+C to {session_id}: {exc}",
                    retryable=True,
                )
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            return ToolResult.fail("ctrl_c_error", f"Ctrl+C error: {exc}", retryable=False)

    return ToolSpec(
        name="fs.send_ctrl_c",
        description="Send Ctrl+C to PTY session to interrupt hanging command — for pair over autonomy, recover from hanging.",
        input_schema={"type": "object", "properties": {"session_id": {"type": "string"}}},
        permission="workspace",
        handler=handler,
        tags=("fs", "pair", "pty"),
        max_context_bytes=1000,
    )


__all__ = ["build_checkpoint_tool", "build_diff_tool", "build_send_ctrl_c_tool", "build_undo_tool"]