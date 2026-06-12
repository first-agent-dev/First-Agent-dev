from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from dataclasses import asdict
from pathlib import Path

from fa import __version__
from fa.authoring_rules import RULE_ALLOWLIST
from fa.authoring_tcb import render_json, render_text, run_all
from fa.chunker import CHUNKER_VERSION, Chunk, default_chunker
from fa.inner_loop import (
    EventLog,
    SessionState,
    ToolCall,
    load_runtime_limits_from_path,
    run_session,
)
from fa.inner_loop.coder_loop import DEFAULT_MAX_TURNS, drive_session
from fa.inner_loop.hooks import (
    AuditHook,
    AuthExpiredBlocker,
    HookRegistry,
    IntentGuard,
    LearningObserver,
    LockfileBlocker,
    LoopGuard,
    RateLimitBlocker,
    SandboxHook,
    SecretGuard,
    VerifierObserver,
)
from fa.inner_loop.pr_draft import PrDraftStore
from fa.inner_loop.tools import (
    build_baseline_registry,
    build_eval_registry,
    build_planner_registry,
    build_prepare_pr_tool,
)
from fa.observability import CostGuardian
from fa.observability.redaction import SecretRedactor, SecretRedactorError
from fa.providers import (
    DEFAULT_MODELS_YAML_PATH,
    ChainConfig,
    ChainEntry,
    ProviderChain,
    UrllibTransport,
    build_provider,
    load_models_config_from_path,
)
from fa.providers.base import Provider, Transport
from fa.providers.errors import ConfigurationError
from fa.roles import EvalFamilyConflictError
from fa.verifier import load_contracts_from_dir

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _valid_run_id(value: str) -> bool:
    return bool(_RUN_ID_RE.fullmatch(value))


def _load_fa_dotenv(path: Path) -> None:
    """Load key=value pairs from ``path`` into ``os.environ`` (setdefault).

    Fails gracefully with a warning on missing file, permission error,
    or malformed encoding.  Never logs the parsed key/value content.
    """
    import warnings

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except PermissionError as exc:
        warnings.warn(
            f"Permission denied reading {path}: {exc}",
            stacklevel=2,
        )
        return
    except UnicodeDecodeError as exc:
        warnings.warn(
            f"Malformed encoding in {path} ({exc.encoding}): {exc}",
            stacklevel=2,
        )
        return
    except OSError as exc:
        warnings.warn(f"Could not load {path}: {exc}", stacklevel=2)
        return

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k:
            os.environ.setdefault(k, v)


# Optional: load ~/.fa/.env for local development convenience.
# Production (AIO) uses .env.fa in repo root loaded by Docker Compose.
_load_fa_dotenv(Path.home() / ".fa" / ".env")


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

    run_parser = subparsers.add_parser(
        "run",
        help="Drive an LLM-driven coder session against ~/.fa/models.yaml.",
        description=(
            "Resolve the per-role provider chain from --config (defaults "
            "to ~/.fa/models.yaml), bootstrap a SessionState + HookRegistry, "
            "and drive the session via fa.inner_loop.coder_loop.drive_session "
            "until the LLM signals done, the turn cap fires, or the provider "
            "chain is exhausted."
        ),
    )
    run_parser.add_argument(
        "--task",
        required=True,
        help="Task description injected as the first user message.",
    )
    run_parser.add_argument(
        "--role",
        default="coder",
        help="Acting role (matches a top-level key in ~/.fa/models.yaml).",
    )
    run_parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help="Path to the per-role chain config (default: ~/.fa/models.yaml).",
    )
    run_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root. Paths inside tools are resolved relative to this directory.",
    )
    run_parser.add_argument(
        "--max-turns",
        type=int,
        default=DEFAULT_MAX_TURNS,
        help=f"LLM-turn cap (default: {DEFAULT_MAX_TURNS}).",
    )
    run_parser.add_argument(
        "--run-id",
        default="",
        help="Override the run_id (default: derived from PID).",
    )
    run_parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help=(
            "Resume an existing workflow session. Preserves the PR draft file "
            "on disk so this session can read the previous role's work log, "
            "then update it with fresh progress."
        ),
    )
    run_parser.set_defaults(func=_cmd_run)

    authoring_parser = subparsers.add_parser(
        "authoring-check",
        help="Run the Level-0 authoring-guardrail kernel (ADR-11 two-tier TCB).",
        description=(
            "Run the frozen, stdlib-only Level-0 kernel over the workspace: "
            "parse the optional --manifest, enumerate + SHA-256 hash the "
            "snapshot, dispatch the static Level-1 allowlist, and emit sorted "
            "diagnostics. Exit 0 unless a HARD-BLOCK is present (fail-closed). "
            "For v0.1 the allowlist is empty, so a clean tree reports no "
            "diagnostics."
        ),
    )
    authoring_parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help=(
            "First-Agent workspace root (must contain knowledge/llms.txt; "
            "no walk-up). Defaults to the current directory."
        ),
    )
    authoring_parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=(
            "Optional path to a .fa/session.toml manifest. When omitted, "
            "session_hash is null and the seam is not bound."
        ),
    )
    authoring_parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text).",
    )
    authoring_parser.set_defaults(func=_cmd_authoring_check)

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
    limits = load_runtime_limits_from_path().limits
    registry = build_baseline_registry(
        workspace,
        bash_timeout_seconds=limits.bash_timeout_seconds,
    )
    log_path = workspace / ".fa" / "smoke-events.jsonl"
    log = EventLog(log_path)
    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))
    hooks.register(
        LoopGuard(
            repeat_warn=limits.loop_guard_repeat_warn,
            circuit_breaker=limits.loop_guard_circuit_breaker,
            window=limits.loop_guard_window,
        )
    )
    # R-4 BlockerMiddleware family: dormant on baseline tools (their
    # error codes don't match the rate-limit / lockfile / auth-expired
    # signatures) but the chain is wired so future API / browser / git
    # tools inherit the contract. The blockers attach to both BEFORE
    # and AFTER lifecycle points; ordering is `Sandbox -> LoopGuard ->
    # blockers` so non-progress patterns short-circuit before blocker
    # observations land.
    hooks.register(RateLimitBlocker(suppression_seconds=limits.rate_limit_suppression_seconds))
    hooks.register(LockfileBlocker(suppression_seconds=limits.lockfile_suppression_seconds))
    hooks.register(AuthExpiredBlocker(suppression_seconds=limits.auth_expired_suppression_seconds))
    audit = AuditHook(event_log=log)
    hooks.register(audit)
    hooks.register(
        SecretGuard(
            secrets=frozenset(),
        )
    )
    # R-45 CostGuardian: dormant on baseline tools (no ``cost=…``
    # artifact in ``ToolResult.artifacts``). Wired here so the chain
    # is stable when the T-2 LLM driver lands the artifact emitter
    # — mirrors the BlockerMiddleware-family rationale above.
    hooks.register(CostGuardian(budget_usd=limits.cost_budget_usd, event_log=log))
    # R-8 LearningObserver: writes discoveries/gotchas to the canonical
    # ``<workspace>/knowledge/trace/`` artifacts — the same path the
    # T-2 real runtime will use, so smoke literally exercises R-8's
    # intended cross-session memory surface. Repeated runs against
    # the live repo stay byte-identical (and therefore leave
    # ``git status`` clean) because three pieces fit together:
    #
    # 1. ``now="2026-05-21T00:00:00Z"`` pins ``record_discovery`` /
    #    ``record_gotcha`` timestamps for the smoke fixture (T-2
    #    omits ``now`` → live timestamps for real provenance).
    # 2. A seed baseline ``knowledge/trace/codebase_map.json`` is
    #    checked into the repo; the post-smoke contents match it
    #    byte-for-byte.
    # 3. ``record_gotcha`` skips the append when the file already
    #    ends with this exact section (fixed timestamp ⇒ identical
    #    bytes ⇒ dedup; live timestamp ⇒ section bytes differ ⇒
    #    append-only contract preserved).
    #
    # See ADR-7 §Sub-amendment 2026-05-21b «single canon root» +
    # «deterministic-clock injection» + «gotchas dedup» rules.
    hooks.register(
        LearningObserver(
            codebase_map_path=workspace / "knowledge" / "trace" / "codebase_map.json",
            gotchas_path=workspace / "knowledge" / "trace" / "gotchas.md",
            now="2026-05-21T00:00:00Z",
            redactor=None,
        )
    )
    # R-5 DSV: load every YAML contract under ``verifiers/`` so the
    # ``VerifierObserver`` can override LLM-claimed success on contract
    # mismatch (force_failure). Missing directory = empty contract map
    # = observer runs as a no-op, which keeps the smoke entrypoint
    # robust when the workspace is a fresh clone without contracts.
    contracts = load_contracts_from_dir(workspace / "verifiers")
    if contracts:
        hooks.register(VerifierObserver(contracts=contracts, event_log=log))
    state = SessionState(workspace_root=workspace, run_id="cli-smoke", log=log)
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
    results = run_session(calls, registry=registry, hooks=hooks, state=state, limits=limits)
    for result in results:
        status = "ERROR" if result.error is not None else "OK"
        print(f"{status}: {result.summary}")
    return 1 if any(result.error is not None for result in results) else 0


def _cmd_run(
    args: argparse.Namespace,
    *,
    transport: Transport | None = None,
) -> int:
    """Drive an LLM-driven coder session.

    ``transport`` is the dependency-injection seam used by tests to
    swap in a deterministic fake transport; production callers pass
    ``None`` and the function constructs a :class:`UrllibTransport`.
    """
    if not str(args.task).strip():
        print("fa run: --task must be non-empty", file=sys.stderr)
        return 2
    if args.max_turns < 1:
        print("fa run: --max-turns must be a positive integer", file=sys.stderr)
        return 2
    if args.run_id and not _valid_run_id(args.run_id):
        print(
            "fa run: --run-id must match [A-Za-z0-9_.-]{1,128}",
            file=sys.stderr,
        )
        return 2

    workspace = args.workspace.resolve()
    config_path = args.config.expanduser().resolve()
    try:
        models = load_models_config_from_path(config_path, env=os.environ)
    except (ConfigurationError, EvalFamilyConflictError, OSError) as exc:
        print(f"fa run: configuration error: {exc}", file=sys.stderr)
        return 2
    chain_config = models.roles.get(args.role)
    if chain_config is None:
        known = sorted(models.roles)
        print(
            f"fa run: role {args.role!r} not found in {config_path}; known: {known}",
            file=sys.stderr,
        )
        return 2

    effective_transport: Transport = transport if transport is not None else UrllibTransport()
    chain = _build_provider_chain(chain_config, transport=effective_transport)

    limits = load_runtime_limits_from_path().limits
    # Role-aware registry: planner/eval get read-only tools, coder gets
    # the full baseline (read + write + bash).
    role = args.role
    if role == "planner":
        registry = build_planner_registry(
            workspace,
            bash_timeout_seconds=limits.bash_timeout_seconds,
        )
    elif role == "eval":
        registry = build_eval_registry(
            workspace,
            bash_timeout_seconds=limits.bash_timeout_seconds,
        )
    else:
        registry = build_baseline_registry(
            workspace,
            bash_timeout_seconds=limits.bash_timeout_seconds,
        )

    run_id = args.run_id or f"run-{os.getpid()}"
    # M-7 §Q-N: ``pr.prepare`` is the producer side of the
    # IntentGuard read seam. The shared ``PrDraftStore`` binds the
    # stable on-disk path to current-session provenance so stale or
    # externally-fabricated drafts are not trusted by the guard.
    draft_path = Path.home() / ".fa" / "state" / "runs" / run_id / "pr_draft.md"
    draft_store = PrDraftStore(draft_path)

    # --resume preserves the on-disk draft for the next role to read;
    # only the in-memory SHA-256 digest is reset, which forces the
    # current session to re-establish trust via a fresh ``pr.prepare``
    # call before any mutating tool is allowed (IntentGuard contract).
    # ``getattr`` fallback keeps pre-``--resume`` tests working.
    resume = getattr(args, "resume", False)

    # When resuming, inject the previous session's draft content as
    # system-prompt extra so the LLM sees the existing plan/work-log
    # from turn 1. This bridges the cross-session continuity gap:
    # the draft lives under ~/.fa/state/ (not /workspace) so
    # fs.read_file cannot reach it, but the system prompt can.
    resume_draft_text: str = ""
    if resume and draft_path.is_file():
        try:
            resume_draft_text = draft_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"fa run: warning — could not read existing draft at {draft_path}: {exc}",
                file=sys.stderr,
            )

    try:
        draft_store.clear(remove_file=not resume)
    except OSError as exc:
        print(
            f"fa run: failed to reset PR draft path {draft_store.path}: {exc}",
            file=sys.stderr,
        )
        return 2
    registry.register(build_prepare_pr_tool(draft_store))
    log_path = workspace / ".fa" / "runs" / run_id / "events.jsonl"
    try:
        redactor = SecretRedactor.from_models_config(os.environ, models)
    except SecretRedactorError as exc:
        print(f"fa run: secret redactor configuration error: {exc}", file=sys.stderr)
        return 2
    log = EventLog(log_path, run_id=run_id, redactor=redactor)
    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))
    hooks.register(
        LoopGuard(
            repeat_warn=limits.loop_guard_repeat_warn,
            circuit_breaker=limits.loop_guard_circuit_breaker,
            window=limits.loop_guard_window,
        )
    )
    hooks.register(RateLimitBlocker(suppression_seconds=limits.rate_limit_suppression_seconds))
    hooks.register(LockfileBlocker(suppression_seconds=limits.lockfile_suppression_seconds))
    hooks.register(AuthExpiredBlocker(suppression_seconds=limits.auth_expired_suppression_seconds))
    # M-7 IntentGuard: reads the per-session PR draft at
    # ~/.fa/state/runs/<run_id>/pr_draft.md (populated by the M-7 §Q-N
    # ``pr.prepare`` tool registered above) and enforces the same
    # classify_intent + validate_commit_msg rules as the M-6 git hooks.
    # Placed after SandboxHook so only workspace-contained paths reach
    # the intent classifier.
    hooks.register(IntentGuard(repo_root=workspace, draft_store=draft_store))
    hooks.register(AuditHook(event_log=log))
    hooks.register(
        SecretGuard(
            secrets=redactor.secrets if redactor is not None else frozenset(),
        )
    )
    hooks.register(CostGuardian(budget_usd=limits.cost_budget_usd, event_log=log))
    hooks.register(
        LearningObserver(
            codebase_map_path=workspace / "knowledge" / "trace" / "codebase_map.json",
            gotchas_path=workspace / "knowledge" / "trace" / "gotchas.md",
            redactor=redactor,
        )
    )
    contracts = load_contracts_from_dir(workspace / "verifiers")
    if contracts:
        hooks.register(VerifierObserver(contracts=contracts, event_log=log))
    state = SessionState(workspace_root=workspace, run_id=run_id, log=log)

    outcome = drive_session(
        args.task,
        provider_chain=chain,
        registry=registry,
        hooks=hooks,
        state=state,
        role=role,
        acting_family=chain_config.family,
        limits=limits,
        max_turns=args.max_turns,
        system_prompt_extra=resume_draft_text,
    )
    status = "OK" if outcome.exit_code == 0 else "ERROR"
    print(f"{status}: {outcome.stop_reason} (turns={outcome.turns})")
    if outcome.final_text:
        print(outcome.final_text)
    return outcome.exit_code


def _cmd_authoring_check(args: argparse.Namespace) -> int:
    workspace: Path = args.workspace.resolve()
    # Workspace resolution per AGENTS.md: anchor on the canonical marker
    # at cwd; never walk up the filesystem into a parent checkout.
    if not (workspace / "knowledge" / "llms.txt").exists():
        print(
            "fa authoring-check: not a First-Agent workspace "
            f"(no knowledge/llms.txt at {workspace})",
            file=sys.stderr,
        )
        return 2

    report = run_all(workspace, manifest_path=args.manifest, rules=RULE_ALLOWLIST)
    rendered = render_json(report) if args.output == "json" else render_text(report)
    print(rendered)
    return report.exit_code


def _build_provider_chain(
    config: ChainConfig,
    *,
    transport: Transport,
) -> ProviderChain:
    """Wire a :class:`ProviderChain` against ``transport``.

    Production-side composition seam: every entry in ``config.chain``
    instantiates a fresh adapter via :func:`build_provider`, sharing
    the single transport. Tests can call this helper directly with a
    fake transport to exercise the wiring without touching the CLI
    argument-parsing layer.
    """

    def factory(entry: ChainEntry) -> Provider:
        return build_provider(entry.provider, transport=transport)

    return ProviderChain(config, provider_factory=factory)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return
    raise SystemExit(func(args))
