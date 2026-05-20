from __future__ import annotations

import argparse
import json
import shlex
import sys
from dataclasses import asdict
from pathlib import Path

from fa import __version__
from fa.chunker import CHUNKER_VERSION, Chunk, default_chunker
from fa.inner_loop import SessionState, ToolCall, run_session
from fa.inner_loop.hooks import AuditHook, HookRegistry, SandboxHook
from fa.inner_loop.tools import build_baseline_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fa",
        description="First-Agent command-line entrypoint.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    chunk_parser = subparsers.add_parser(
        "chunk",
        help="Run the deterministic chunker on a single file (smoke / inspection).",
        description=(
            "Run the deterministic chunker on PATH and emit the produced "
            "chunks. Intended for manual inspection of the chunker output; "
            "the real indexing command (`fa reindex`) lands once storage is "
            "wired."
        ),
    )
    chunk_parser.add_argument("path", type=Path, help="Path to the file to chunk.")
    chunk_parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help=(
            "Output format. 'text' prints a one-line-per-chunk summary; "
            "'json' emits the full Chunk records on stdout."
        ),
    )
    chunk_parser.set_defaults(func=_cmd_chunk)

    smoke_parser = subparsers.add_parser(
        "inner-loop-smoke",
        help="Exercise the M-1 registry + HookRegistry runtime without an LLM provider.",
        description=(
            "Run a deterministic read_file → write_file → run_bash sequence through "
            "the inner-loop registry and HookRegistry. This is a Phase-M smoke entry "
            "point, not the final `fa run` LLM surface."
        ),
    )
    smoke_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root. Paths are resolved relative to this directory.",
    )
    smoke_parser.add_argument(
        "--input",
        default="README.md",
        help="File to read before the smoke write/bash calls.",
    )
    smoke_parser.add_argument(
        "--output",
        default=".fa/inner-loop-smoke.txt",
        help="Workspace-relative file written by the smoke run.",
    )
    smoke_parser.set_defaults(func=_cmd_inner_loop_smoke)

    return parser


def _cmd_chunk(args: argparse.Namespace) -> int:
    path: Path = args.path
    if not path.exists():
        print(f"fa chunk: path not found: {path}", file=sys.stderr)
        return 2
    if not path.is_file():
        print(f"fa chunk: not a file: {path}", file=sys.stderr)
        return 2

    chunks = default_chunker().chunk_file(path)

    if args.output == "json":
        payload = {
            "chunker_version": CHUNKER_VERSION,
            "path": str(path),
            "chunks": [_chunk_to_dict(c) for c in chunks],
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    print(f"# {path}  ({len(chunks)} chunk(s); chunker {CHUNKER_VERSION})")
    for chunk in chunks:
        breadcrumb = " > ".join(chunk.breadcrumb) if chunk.breadcrumb else "<root>"
        print(
            f"- {chunk.anchor}  L{chunk.line_start}-{chunk.line_end} "
            f"B{chunk.byte_start}-{chunk.byte_end}  [{chunk.lang}]  ({breadcrumb})"
        )
    return 0


def _chunk_to_dict(chunk: Chunk) -> dict[str, object]:
    data = asdict(chunk)
    # ``asdict`` converts the breadcrumb tuple to a list, which is the
    # right shape for JSON output.
    return data


def _cmd_inner_loop_smoke(args: argparse.Namespace) -> int:
    workspace = args.workspace.resolve()
    registry = build_baseline_registry(workspace)
    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))
    audit = AuditHook()
    hooks.register(audit)
    state = SessionState(workspace_root=workspace, run_id="cli-smoke")
    calls = (
        ToolCall(name="fs.read_file", params={"path": args.input}, call_id="tc-read"),
        ToolCall(
            name="fs.write_file",
            params={"path": args.output, "content": "inner-loop smoke\n"},
            call_id="tc-write",
        ),
        ToolCall(
            name="fs.run_bash",
            params={"command": f"test -f {shlex.quote(args.output)}"},
            call_id="tc-bash",
        ),
    )
    results = run_session(calls, registry=registry, hooks=hooks, state=state)
    for result in results:
        status = "ERROR" if result.error is not None else "OK"
        print(f"{status}: {result.summary}")
    return 1 if any(result.error is not None for result in results) else 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return
    raise SystemExit(func(args))
