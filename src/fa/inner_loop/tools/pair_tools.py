"""Pair over Autonomy tools — checkpoint, undo, diff, send_ctrl_c — Stage 0

Fixes:
- Gap 5: git add -A risky → use git add -u (tracked only) + stash that respects .gitignore
- Improvement: diff returns structured summary --stat + truncated diff
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Mapping

from fa.inner_loop.registry import ToolResult, ToolSpec


def build_checkpoint_tool(workspace_root: Path) -> ToolSpec:
    root = Path(workspace_root).resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        message = str(params.get("message", "checkpoint before task"))
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            if status.stdout.strip() == "":
                return ToolResult.ok(
                    f"No changes to checkpoint at {root}",
                    result={"checkpoint_id": "no-changes", "message": message},
                )
            # Prefer tracked-only add to avoid adding .fa/, secrets, large untracked
            # git add -u respects .gitignore for tracked modifications
            # For new files that are relevant, user should add explicitly,
            # but we fallback to stash which also respects .gitignore by default
            add = subprocess.run(
                ["git", "add", "-u"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            # Try commit tracked changes
            commit = subprocess.run(
                ["git", "commit", "-m", f"checkpoint: {message}"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            if commit.returncode == 0:
                rev = subprocess.run(
                    ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True
                )
                checkpoint_id = rev.stdout.strip() if rev.returncode == 0 else "unknown"
                return ToolResult.ok(
                    f"Checkpoint created: {checkpoint_id} - {message}",
                    result={
                        "checkpoint_id": checkpoint_id,
                        "method": "commit_tracked",
                        "message": message,
                    },
                )
            # Fallback: stash push -m respects .gitignore unless --include-untracked
            stash = subprocess.run(
                ["git", "stash", "push", "-m", f"checkpoint: {message}"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            if stash.returncode == 0:
                return ToolResult.ok(
                    f"Checkpoint via stash: {message}",
                    result={
                        "checkpoint_id": stash.stdout.strip(),
                        "method": "stash_tracked",
                        "message": message,
                    },
                )
            return ToolResult.fail(
                "checkpoint_failed",
                f"Commit and stash failed: {commit.stderr} {stash.stderr}",
                retryable=False,
            )
        except Exception as exc:
            return ToolResult.fail("checkpoint_error", f"Checkpoint failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.checkpoint",
        description="Create checkpoint via git commit -u (tracked only) or stash push -m (respects .gitignore) — for pair over autonomy, checkpoint before task, undo restores.",
        input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
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
            if (
                checkpoint_id
                and isinstance(checkpoint_id, str)
                and checkpoint_id != "no-changes"
                and len(checkpoint_id) >= 7
            ):
                result = subprocess.run(
                    ["git", "reset", "--hard", checkpoint_id],
                    cwd=root,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    return ToolResult.ok(
                        f"Undone to checkpoint {checkpoint_id}",
                        result={"restored_to": checkpoint_id, "method": "reset"},
                    )
            reset = subprocess.run(
                ["git", "reset", "--hard", "HEAD~1"], cwd=root, capture_output=True, text=True
            )
            if reset.returncode == 0:
                return ToolResult.ok(
                    "Undone last commit",
                    result={"method": "reset", "output": reset.stdout[:500]},
                )
            pop = subprocess.run(
                ["git", "stash", "pop"], cwd=root, capture_output=True, text=True
            )
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
        except Exception as exc:
            return ToolResult.fail("undo_error", f"Undo failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.undo",
        description="Undo last checkpoint via git reset --hard HEAD~1 or stash pop — for pair over autonomy, Ctrl+Z equivalent.",
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
            stat_res = subprocess.run(stat_cmd, cwd=root, capture_output=True, text=True)
            stat_text = stat_res.stdout

            diff_cmd = ["git", "diff", base]
            if target and isinstance(target, str) and target:
                diff_cmd = ["git", "diff", f"{base}..{target}"]
            diff_res = subprocess.run(diff_cmd, cwd=root, capture_output=True, text=True)
            diff_text = diff_res.stdout

            # Parse files changed from stat
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
        except Exception as exc:
            return ToolResult.fail("diff_error", f"Diff failed: {exc}", retryable=False)

    return ToolSpec(
        name="fs.diff",
        description="Returns git diff structured between base and target (default HEAD) with --stat summary + truncated diff, token efficient — for pair over autonomy, review changes before PR.",
        input_schema={
            "type": "object",
            "properties": {"base": {"type": "string"}, "target": {"type": "string"}},
        },
        permission="read",
        handler=handler,
        tags=("fs", "pair", "diff"),
        max_context_bytes=4000,
    )


def build_send_ctrl_c_tool(pty_pool=None) -> ToolSpec:
    def handler(params: Mapping[str, object]) -> ToolResult:
        try:
            session_id = params.get("session_id", "main")
            if not isinstance(session_id, str):
                session_id = "main"
            if pty_pool is None:
                return ToolResult.ok(
                    "No PTY pool available, Ctrl+C not needed (stateless bash)",
                    result={"session_id": session_id, "status": "no-pool"},
                )
            try:
                msg = (
                    pty_pool.sessions[session_id].send_ctrl_c()
                    if session_id in pty_pool.sessions
                    else "session not found"
                )
                return ToolResult.ok(
                    f"Sent Ctrl+C to {session_id}: {msg}",
                    result={"session_id": session_id, "msg": msg},
                )
            except Exception as exc:
                return ToolResult.fail(
                    "ctrl_c_failed",
                    f"Failed to send Ctrl+C to {session_id}: {exc}",
                    retryable=True,
                )
        except Exception as exc:
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


__all__ = ["build_checkpoint_tool", "build_undo_tool", "build_diff_tool", "build_send_ctrl_c_tool"]
