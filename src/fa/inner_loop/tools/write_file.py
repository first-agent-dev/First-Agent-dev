from __future__ import annotations

import hashlib
import subprocess
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fa.inner_loop.registry import ToolResult, ToolSpec
from fa.inner_loop.tools.base import require_string, resolve_workspace_path


def _base_commit(root: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return res.stdout.strip()[:12]
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: _base_commit failed: {exc}")
    return "unknown"


def _file_hash(p: Path) -> str:
    try:
        if p.exists():
            return hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: _file_hash failed for {p}: {exc}")
    return "missing"


def _check_conflict(
    blackboard: Any,
    read_set: list[str],
    write_set: list[str],
    root: Path,
    llms_path: Path,
) -> ToolResult | None:
    """Return fail if conflict, else None. Safety: ignore if blackboard from different workspace."""
    if blackboard is None:
        return None

    # Safety check: blackboard must belong to current workspace_root, otherwise ignore (contextvar leak protection)
    try:
        bb_root = Path(getattr(blackboard, "root", Path("/"))).resolve()
        # Expected: bb_root == root/.fa/blackboard, so parent.parent == root
        # If not related, it's from different workspace (leaked contextvar) -> ignore
        try:
            # bb_root = <root>/.fa/blackboard
            expected_root = root.resolve()
            # Check if bb_root is inside expected_root/.fa
            if not (bb_root == expected_root / ".fa" / "blackboard" or bb_root.is_relative_to(expected_root)):
                # Also check if expected_root is parent of bb_root's parent.parent
                if bb_root.parent.parent.resolve() != expected_root.resolve():
                    # Different workspace, ignore conflict to avoid false positives from leaked session
                    return None
        except Exception:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            # If relative_to fails, do strict equality check only
            if bb_root != (root.resolve() / ".fa" / "blackboard"):
                # If roots differ, ignore
                # Additional safety: if blackboard path not under root, ignore
                try:
                    blackboard_path = Path(getattr(blackboard, "path", bb_root / "blackboard.jsonl")).resolve()
                    if not blackboard_path.is_relative_to(expected_root):
                        return None
                except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
                    pass
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable
        print(f"WARNING: safety check failed {exc}, ignoring")

    try:
        from fa.blackboard.blackboard import BlackboardEntry

        entry_id = f"write-{uuid.uuid4().hex[:8]}"
        base = _base_commit(root)
        lh = _file_hash(llms_path)

        new_entry = BlackboardEntry.create(
            id=entry_id,
            type="file_version",
            payload={"path": write_set[0] if write_set else "unknown"},
            read_set=read_set,
            write_set=write_set,
            assumptions=[f"base_commit {base}"],
            version_dependencies={"base_commit": base, "llms.txt": lh},
        )
        conflicts = blackboard.detect_conflict(new_entry)
        if conflicts:
            details = "; ".join([c.reason for c in conflicts])
            ids = [c.conflicting_entry_id for c in conflicts]
            return ToolResult.fail(
                "conflict_detected",
                f"Conflict for {write_set}: {details}. Conflicts: {ids}",
                retryable=True,
            )
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: Blackboard check failed: {exc}, allowing write")
    return None


def _write_blackboard_ok(
    blackboard: Any,
    read_set: list[str],
    write_set: list[str],
    root: Path,
    llms_path: Path,
    content: str,
) -> None:
    if blackboard is None:
        return
    # Same safety check as above
    try:
        bb_root = Path(getattr(blackboard, "root", Path("/"))).resolve()
        expected_root = root.resolve()
        if not (bb_root == expected_root / ".fa" / "blackboard" or bb_root.is_relative_to(expected_root)):
            if bb_root.parent.parent.resolve() != expected_root.resolve():
                return
    except Exception:  # noqa: BLE001, S110 # graceful degradation per Phase 0.5, failure-observable WARNING
        pass

    try:
        from fa.blackboard.blackboard import BlackboardEntry

        entry_id = f"write-ok-{uuid.uuid4().hex[:8]}"
        base = _base_commit(root)
        lh = _file_hash(llms_path)

        ok_entry = BlackboardEntry.create(
            id=entry_id,
            type="file_version",
            payload={"path": write_set[0], "bytes": len(content.encode())},
            read_set=read_set,
            write_set=write_set,
            assumptions=[f"file {write_set[0]} exists after write"],
            version_dependencies={"base_commit": base, "llms.txt": lh},
        )
        blackboard.write(ok_entry)
    except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
        print(f"WARNING: Blackboard write failed: {exc}")


def build_write_file_tool(workspace_root: Path) -> ToolSpec:
    root = workspace_root.resolve()

    def handler(params: Mapping[str, object]) -> ToolResult:
        data = dict(params)
        try:
            path = resolve_workspace_path(root, require_string(data, "path"))
            content = require_string(data, "content")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        try:
            rel_path = str(path.relative_to(root))
        except ValueError:
            rel_path = str(path)

        session: Any = None
        blackboard: Any = None
        transaction: Any = None
        try:
            from fa.inner_loop.context import get_current_session

            session = get_current_session()
            if session is not None:
                blackboard = getattr(session, "blackboard", None)
                transaction = getattr(session, "transaction", None)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            print(f"WARNING: get_current_session failed in write_file: {exc}")

        read_set: list[str] = []
        write_set: list[str] = [rel_path]
        try:
            if transaction is not None:
                read_set = list(transaction.read_set)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            print(f"WARNING: transaction.read_set failed: {exc}")

        llms_path = root / "knowledge" / "llms.txt"
        if not llms_path.exists():
            llms_path = root / "llms.txt"

        conflict_res = _check_conflict(blackboard, read_set, write_set, root, llms_path)
        if conflict_res is not None:
            return conflict_res

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except (OSError, PermissionError, ValueError) as exc:
            return ToolResult.fail("write_failed", str(exc), retryable=True)

        try:
            if transaction is not None:
                transaction.add_write(rel_path)
        except Exception as exc:  # noqa: BLE001 # graceful degradation per Phase 0.5, failure-observable WARNING
            print(f"WARNING: transaction.add_write failed: {exc}")

        _write_blackboard_ok(blackboard, read_set, write_set, root, llms_path, content)

        return ToolResult.ok(
            f"wrote {path.relative_to(root)}",
            result={"path": str(path), "bytes": len(content.encode("utf-8"))},
        )

    return ToolSpec(
        name="fs.write_file",
        description=(
            "Write UTF-8 file inside workspace. Declares read_set/write_set "
            "for blackboard conflict detection (Phase 0.5), fails with "
            "conflict_detected if concurrent write without coordination."
        ),
        input_schema={
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        },
        permission="workspace",
        handler=handler,
        tags=("fs", "write"),
    )


__all__ = ["build_write_file_tool"]
