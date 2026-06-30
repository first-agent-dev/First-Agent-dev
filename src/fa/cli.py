from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from fa import __version__
from fa.authoring_rules import RULE_ALLOWLIST
from fa.authoring_tcb import render_json, render_text, run_all
from fa.chunker import CHUNKER_VERSION, Chunk, default_chunker
from fa.cli_help import help_as_json, render_command_help_ru, render_top_level_ru
from fa.inner_loop import (
    EventLog,
    SessionState,
    ToolCall,
    load_runtime_limits_from_path,
    run_session,
)
from fa.inner_loop.coder_loop import (
    DEFAULT_CODER_TEMPERATURE,
    DEFAULT_MAX_TURNS,
    DEFAULT_TEMPERATURE,
    SessionOutcome,
    drive_session,
)
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
from fa.inner_loop.workflow_artifacts import (
    EvalReport,
    FlowState,
    FlowStatus,
    parse_eval_report,
    write_eval_report,
    write_flow_state,
)
from fa.observability import CostGuardian
from fa.observability.redaction import SecretRedactor, SecretRedactorError
from fa.providers import (
    DEFAULT_MODELS_YAML_PATH,
    ChainConfig,
    ChainEntry,
    ProviderChain,
    SecretStore,
    UrllibTransport,
    build_provider,
    load_models_config_from_path,
)
from fa.providers.base import Provider, RequestInfo, Transport
from fa.providers.errors import (
    ConfigurationError,
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
)
from fa.roles import EvalFamilyConflictError
from fa.verifier import load_contracts_from_dir

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _valid_run_id(value: str) -> bool:
    return bool(_RUN_ID_RE.fullmatch(value))


def _resolve_task(positional: str | None, flag: str | None) -> str | None:
    """Resolve the effective task from positional arg, --task flag, or stdin.

    Precedence: an explicit --task wins over the positional (so the flag form
    stays authoritative for back-compat). A value of ``-`` (in either slot)
    means "read the task from stdin" (pipe-friendly, llm/claude pattern).
    Returns ``None`` when no task source was supplied at all.
    """
    chosen = flag if flag is not None else positional
    if chosen is None:
        return None
    if chosen == "-":
        return sys.stdin.read().strip()
    return chosen


def _resolve_secrets_path() -> Path:
    """Locate the API-key file (secret-isolation invariant, ADR-12).

    Strict, file-only — keys are NEVER read from ``os.environ`` (so child
    processes such as ``fs.run_bash`` inherit nothing to exfiltrate). Resolution
    order:

    1. ``$FA_SECRETS_FILE`` (set by docker-compose to ``/run/secrets/fa.env``),
    2. AIO default ``/run/secrets/fa.env`` if it exists,
    3. WSL/dev default ``~/.fa/.env``.
    """
    override = os.environ.get("FA_SECRETS_FILE")
    if override:
        return Path(override)
    aio_default = Path("/run/secrets/fa.env")
    if aio_default.exists():
        return aio_default
    return Path.home() / ".fa" / ".env"


def _load_secret_store() -> SecretStore:
    """Build the private :class:`SecretStore` from the resolved secrets file.

    Lazy (called inside ``_cmd_run``), file-only, and does not touch
    ``os.environ``. (The old import-time dotenv loader that mutated the
    process environment has been removed entirely — ADR-12.)
    """
    return SecretStore.from_file(_resolve_secrets_path())


# Header the agent sends to the egress proxy to prove it is the fa process.
# It is NOT a provider key (leaking it only enables metered LLM calls via the
# proxy, a cost risk, never key disclosure).
_PROXY_TOKEN_HEADER = "X-FA-Proxy-Token"  # noqa: S105 - HTTP header name, not a secret
# Advertises the per-route upstream timeout (seconds) to the proxy so it forwards
# with the same deadline the agent uses, instead of a hardcoded ceiling.
_PROXY_TIMEOUT_HEADER = "X-FA-Timeout"


class _SelfcheckNetworkError(Exception):
    """Raised when fa selfcheck cannot reach the local egress proxy."""


def _resolve_proxy_url() -> str:
    """Return the egress-proxy base URL, or empty string for legacy mode.

    When ``FA_EGRESS_PROXY_URL`` is set, ``fa run`` operates in proxy mode:
    provider keys live in the proxy (not in this process), and the chain targets
    the proxy. When unset, the legacy strict-file SecretStore mode is used.
    """
    return os.environ.get("FA_EGRESS_PROXY_URL", "").strip()


def _resolve_proxy_token() -> str:
    """Read the fa→proxy bootstrap token (file pointer, never os.environ value).

    Resolution: ``$FA_PROXY_TOKEN_FILE`` → ``/run/secrets/fa_proxy_token``.
    """
    override = os.environ.get("FA_PROXY_TOKEN_FILE", "").strip()
    path = Path(override) if override else Path("/run/secrets/fa_proxy_token")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _proxy_rewrite_chain(chain_config: ChainConfig, proxy_url: str) -> tuple[ChainConfig, str]:
    """Resolve the proxy token and rewrite the chain, or return an error string.

    Extracted from ``_cmd_run`` to keep that function's complexity bounded.
    """
    proxy_token = _resolve_proxy_token()
    if not proxy_token:
        return chain_config, (
            "FA_EGRESS_PROXY_URL set but no proxy token found "
            "(set FA_PROXY_TOKEN_FILE or /run/secrets/fa_proxy_token)"
        )
    return (
        _apply_proxy_mode(chain_config, proxy_url=proxy_url, proxy_token=proxy_token),
        "",
    )


def _apply_proxy_mode(
    chain_config: ChainConfig,
    *,
    proxy_url: str,
    proxy_token: str,
) -> ChainConfig:
    """Rewrite a role's chain to target the egress proxy (ADR-12).

    Each entry's ``base_url`` becomes ``<proxy>/route/<name>`` and the entry
    carries the fa→proxy token via ``extra_headers``. No provider key is placed
    anywhere on the fa side — the proxy injects it.
    """
    from fa.egress_proxy.routing import route_name_for

    base = proxy_url.rstrip("/")
    new_entries = []
    for entry in chain_config.chain:
        name = route_name_for(entry.provider, entry.slug)
        headers = dict(entry.extra_headers)
        headers[_PROXY_TOKEN_HEADER] = proxy_token
        # Advertise this route's upstream timeout so the proxy forwards with the
        # SAME deadline the agent uses (clamped proxy-side). Without it the proxy
        # cut every upstream at a hardcoded 60s, so a model configured with a
        # longer timeout_seconds would 502 → chain_exhausted on slow providers.
        headers[_PROXY_TIMEOUT_HEADER] = str(entry.timeout_seconds)
        new_entries.append(
            replace(
                entry,
                base_url=f"{base}/route/{name}",
                extra_headers=headers,
            )
        )
    return replace(chain_config, chain=tuple(new_entries))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fa",
        description="First-Agent command-line entrypoint.",
        epilog=render_top_level_ru()
        + "\n\nПодсказка: `fa help <команда>` — подробная справка на русском.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        epilog=render_command_help_ru("run"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument(
        "task_pos",
        metavar="task",
        nargs="?",
        default=None,
        help=(
            "Task text (positional, quoted). Use '-' to read the task from stdin. "
            "Equivalent to --task; one of the two must be provided."
        ),
    )
    run_parser.add_argument(
        "--task",
        default=None,
        help="Task description injected as the first user message (alias of the positional task).",
    )
    run_parser.add_argument(
        "--role",
        "-r",
        default="coder",
        help="Acting role (matches a top-level key in ~/.fa/models.yaml).",
    )
    run_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help="Path to the per-role chain config (default: ~/.fa/models.yaml).",
    )
    run_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=Path.cwd(),
        help="Workspace root. Paths inside tools are resolved relative to this directory.",
    )
    run_parser.add_argument(
        "--max-turns",
        "-n",
        type=int,
        default=DEFAULT_MAX_TURNS,
        help=f"LLM-turn cap (default: {DEFAULT_MAX_TURNS}).",
    )
    run_parser.add_argument(
        "--run-id",
        "-i",
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
    run_parser.add_argument(
        "--output-mode",
        choices=("console", "quiet"),
        default="console",
        help="Output mode: console (per-turn progress to stderr) or quiet (final only).",
    )
    run_parser.add_argument(
        "--detail",
        choices=("minimal", "standard", "verbose", "debug"),
        default="standard",
        help="Console detail level (default: standard).",
    )
    run_parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help="Disable color output (sets NO_COLOR=1).",
    )
    run_parser.set_defaults(func=_cmd_run)

    workflow_parser = subparsers.add_parser(
        "workflow",
        help="Run a multi-role pipeline (planner→coder→eval) in one command.",
        description=(
            "Drive several roles in sequence over a single shared run-id and "
            "workspace. The first role starts fresh; every later role gets "
            "--resume automatically so it reads the previous role's PR draft. "
            "Stops on the first non-zero stage exit (fail-fast). With "
            "--mode repair, adds bounded coder→eval repair rounds driven by the "
            "machine-readable eval route (return_to_coder)."
        ),
        epilog=render_command_help_ru("workflow"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    workflow_parser.add_argument(
        "roles",
        help="Comma-separated roles in execution order, e.g. planner,coder,eval.",
    )
    workflow_parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task text (quoted). Passed to every role unless --task-<role> overrides it.",
    )
    workflow_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=Path.cwd(),
        help="Shared workspace root for every role.",
    )
    workflow_parser.add_argument(
        "--run-id",
        "-i",
        default="",
        help="Shared run_id (default: generated from timestamp + task slug).",
    )
    workflow_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help="Path to the per-role chain config (default: ~/.fa/models.yaml).",
    )
    workflow_parser.add_argument(
        "--max-turns",
        "-n",
        type=int,
        default=DEFAULT_MAX_TURNS,
        help=f"LLM-turn cap applied to each role (default: {DEFAULT_MAX_TURNS}).",
    )
    workflow_parser.add_argument(
        "--mode",
        "-m",
        choices=_WORKFLOW_MODES,
        default="linear",
        help=(
            "Routing strategy: 'linear' runs each role once; 'repair' adds "
            "bounded coder→eval repair rounds driven by the eval route "
            "(default: linear)."
        ),
    )
    workflow_parser.add_argument(
        "--max-repairs",
        type=int,
        default=DEFAULT_MAX_REPAIRS,
        help=(
            f"Max coder→eval repair rounds in --mode repair/adaptive "
            f"(default: {DEFAULT_MAX_REPAIRS}, hard ceiling {MAX_REPAIRS_CEILING})."
        ),
    )
    workflow_parser.add_argument(
        "--max-replans",
        type=int,
        default=DEFAULT_MAX_REPLANS,
        help=(
            f"Max planner re-entry rounds in --mode adaptive "
            f"(default: {DEFAULT_MAX_REPLANS}, hard ceiling {MAX_REPLANS_CEILING})."
        ),
    )
    # Per-role task overrides: --task-planner / --task-coder / --task-eval.
    for _role in ("planner", "coder", "eval"):
        workflow_parser.add_argument(
            f"--task-{_role}",
            default=None,
            help=f"Override the task text for the {_role} stage.",
        )
    workflow_parser.set_defaults(func=_cmd_workflow)

    help_parser = subparsers.add_parser(
        "help",
        help="Show bilingual (RU/EN) command help; --json for the WebUI contract.",
        description=(
            "Print the Russian command/argument help from the shared cli_help "
            "registry. With --json, emit the full bilingual registry that a "
            "WebUI consumes for per-command help buttons."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    help_parser.add_argument(
        "topic",
        nargs="?",
        default=None,
        help="Command to explain (e.g. run, workflow). Omit for the command list.",
    )
    help_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full bilingual help registry as JSON (WebUI contract).",
    )
    help_parser.set_defaults(func=_cmd_help)

    selfcheck_parser = subparsers.add_parser(
        "selfcheck",
        help="Diagnose the ADR-12 egress-proxy LLM path.",
        description=(
            "Check that the agent can reach the egress proxy, that the proxy's "
            "route table matches the selected role in ~/.fa/models.yaml, and "
            "that the proxy has a provider key for every selected route. The "
            "agent never reads provider key values; it only consumes the "
            "proxy's safe name/has_key diagnostics."
        ),
        epilog=render_command_help_ru("selfcheck"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    selfcheck_parser.add_argument(
        "--role",
        "-r",
        default="coder",
        help="Role to check (matches a top-level key in ~/.fa/models.yaml).",
    )
    selfcheck_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help="Path to the per-role chain config (default: ~/.fa/models.yaml).",
    )
    selfcheck_parser.set_defaults(func=_cmd_selfcheck)

    probe_parser = subparsers.add_parser(
        "probe",
        help="Liveness-test the LLM provider chain with a minimal API call.",
        description=(
            "Send a minimal LLM request (~10 tokens) through the full "
            "agent→proxy→provider path for the selected role (or all roles). "
            "Unlike `fa selfcheck` (which validates config and routing without "
            "touching a provider), `fa probe` makes a real API call and reports "
            "per-chain-entry results. Use it to verify that API keys are valid, "
            "models are available, and the network path works end-to-end."
        ),
        epilog=render_command_help_ru("probe"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    probe_parser.add_argument(
        "--role",
        "-r",
        default="coder",
        help="Role to probe (matches a top-level key in ~/.fa/models.yaml).",
    )
    probe_parser.add_argument(
        "--all-roles",
        action="store_true",
        help="Probe every role declared in ~/.fa/models.yaml.",
    )
    probe_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help="Path to the per-role chain config (default: ~/.fa/models.yaml).",
    )
    probe_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Per-entry timeout in seconds (default: 30).",
    )
    probe_parser.set_defaults(func=_cmd_probe)

    stats_parser = subparsers.add_parser(
        "stats",
        help="Analyze session logs — tool usage, file access, tokens, efficiency.",
        description=(
            "Parse events.jsonl files from past fa run sessions and render "
            "analytics: tool usage, file access patterns, token timelines, "
            "provider health, guard activity, dead zones, efficiency warnings."
        ),
        epilog=render_command_help_ru("stats"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    stats_parser.add_argument("--run-id", "-i", default=None, help="Analyze specific session.")
    stats_parser.add_argument("--since", default=None, help="Filter by age (e.g. 7d, 24h, 1h).")
    stats_parser.add_argument(
        "--output",
        choices=("console", "json"),
        default="console",
        help="Output format.",
    )
    stats_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=Path.cwd(),
        help="Workspace root (default: cwd).",
    )
    stats_parser.add_argument("--dead-zones", action="store_true", help="Files never accessed.")
    stats_parser.set_defaults(func=_cmd_stats)

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

    proxy_parser = subparsers.add_parser(
        "egress-proxy",
        help="Run the egress-injection proxy (ADR-12 secret isolation).",
        description=(
            "Run the LLM-key egress-injection proxy. Reads provider keys from "
            "--secrets and routing from --models, then injects the real key at "
            "the transport layer so the agent container never holds a key. "
            "Intended to run as a SEPARATE container from the agent."
        ),
    )
    proxy_parser.add_argument(
        "--models",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help="Path to models.yaml (routing source; non-secret).",
    )
    proxy_parser.add_argument(
        "--secrets",
        type=Path,
        default=Path("/run/secrets/fa.env"),
        help="Path to the provider-keys file (mounted ro into the proxy only).",
    )
    proxy_parser.add_argument(
        "--token-file",
        type=Path,
        default=Path("/run/secrets/fa_proxy_token"),
        help="Path to the fa→proxy bootstrap token file.",
    )
    proxy_parser.add_argument(
        "--listen",
        type=str,
        default="0.0.0.0:8080",
        help="host:port to bind (default 0.0.0.0:8080).",
    )
    proxy_parser.set_defaults(func=_cmd_egress_proxy)

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
    return data  # pyrefly: ignore[bad-return] — asdict() erases to Any; mypy strict accepts


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


def _slugify_task(task: str, *, limit: int = 24) -> str:
    """Derive a short, run-id-safe slug from a task string."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", task.strip().lower()).strip("-")
    return slug[:limit] or "task"


@dataclass(frozen=True)
class _WorkflowArtifactPaths:
    base_dir: Path
    eval_report: Path
    flow_state: Path


def _workflow_artifact_paths(run_id: str) -> _WorkflowArtifactPaths:
    """Return canonical workflow artifact paths under ``~/.fa/session-log``.

    Temporary physical model (workflow implementation plan 2026-06-29):
    human-readable draft remains ``pr_draft.md``; controller truth lives in
    separate JSON artifacts for eval verdicts and workflow state.
    """
    base_dir = Path.home() / ".fa" / "session-log" / run_id
    return _WorkflowArtifactPaths(
        base_dir=base_dir,
        eval_report=base_dir / "eval_report.json",
        flow_state=base_dir / "flow_state.json",
    )


def _cmd_help(args: argparse.Namespace) -> int:
    """Render bilingual command help; --json emits the WebUI contract."""
    if getattr(args, "json", False):
        print(help_as_json())
        return 0
    topic = getattr(args, "topic", None)
    if topic:
        rendered = render_command_help_ru(topic)
        if not rendered:
            print(f"fa help: неизвестная команда {topic!r}", file=sys.stderr)
            print(render_top_level_ru(), file=sys.stderr)
            return 2
        print(rendered)
        return 0
    print(render_top_level_ru())
    print("\nПодсказка: `fa help <команда>` — подробная справка по команде.")
    return 0


# ── Workflow controller (linear + bounded repair) ──────────────────────────
#
# Map the evaluator's verdict to a terminal FlowState status. The controller
# branches on the eval *route* (machine-readable), but records the verdict as
# the human-facing terminal status. Repair routing (return_to_coder) is handled
# by the repair loop; planner re-entry (return_to_planner) is NOT yet acted on
# and remains a recorded, non-looping outcome until the adaptive controller.
_EVAL_VERDICT_TO_TERMINAL_STATUS: dict[str, FlowStatus] = {
    "PASS": "DONE",
    "REPAIR_REQUIRED": "REPAIR_REQUIRED",
    "REPLAN_REQUIRED": "REPLAN_REQUIRED",
    "BLOCKED": "FAILED",
}

# Repair-loop budget defaults (workflow plan §4.6: 2 rounds, hard max 3).
DEFAULT_MAX_REPAIRS = 2
MAX_REPAIRS_CEILING = 3
DEFAULT_MAX_REPLANS = 1
MAX_REPLANS_CEILING = 2

_WORKFLOW_MODES = ("linear", "repair", "adaptive")


def _emit_eval_report(
    *,
    report_path: Path,
    final_text: str,
    run_id: str,
    plan_id: str,
    plan_version: int,
) -> EvalReport:
    """Parse the eval role's final message and persist ``eval_report.json``.

    The narrative draft (``pr_draft.md``) stays human-readable; this JSON is
    the controller's machine-readable source of truth for the eval verdict and
    route decision.
    """
    report = parse_eval_report(
        final_text,
        run_id=run_id,
        plan_id=plan_id,
        evaluation_id=f"{run_id}-eval",
        plan_version=plan_version,
    )
    write_eval_report(report_path, report)
    return report


@dataclass(frozen=True)
class _WorkflowContext:
    """Invariant per-run configuration shared by every workflow stage."""

    args: argparse.Namespace
    run_id: str
    base_task: str | None
    per_role_task: Mapping[str, str | None]
    artifact_paths: _WorkflowArtifactPaths
    transport: Transport | None
    secrets: Mapping[str, str] | None

    def task_for(self, role: str) -> str | None:
        return self.per_role_task.get(role) or self.base_task


@dataclass(frozen=True)
class _WorkflowProgress:
    """Mutable controller counters threaded through a workflow run."""

    plan_version: int = 1
    repair_round: int = 0
    replan_round: int = 0


@dataclass(frozen=True)
class _StageResult:
    """Outcome of dispatching one role stage."""

    role: str
    exit_code: int
    eval_report: EvalReport | None = None


def _status_for_role(role: str) -> FlowStatus:
    if role == "planner":
        return "PLANNING"
    if role == "coder":
        return "CODING"
    if role == "eval":
        return "EVALUATING"
    return "CODING"


def _run_stage(
    ctx: _WorkflowContext,
    role: str,
    *,
    fresh: bool,
    progress: _WorkflowProgress,
    transition_reason: str,
) -> _StageResult:
    """Dispatch one role session and, for ``eval``, persist its report.

    Writes a pre-dispatch FlowState mirror so the active role / repair round is
    inspectable even mid-run, then runs the role through :func:`_cmd_run`. For
    the ``eval`` role the terminal outcome is captured and translated into
    ``eval_report.json``.
    """
    write_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=str(ctx.base_task or ""),
            status=_status_for_role(role),
            active_role=role,
            active_plan_id=ctx.run_id,
            active_plan_version=progress.plan_version,
            repair_round=progress.repair_round,
            replan_round=progress.replan_round,
            last_actor="workflow",
            last_transition_reason=transition_reason,
        ),
    )
    stage_args = argparse.Namespace(
        task_pos=None,
        task=ctx.task_for(role),
        role=role,
        config=ctx.args.config,
        workspace=ctx.args.workspace,
        max_turns=ctx.args.max_turns,
        run_id=ctx.run_id,
        resume=not fresh,
        output_mode="console",
        detail="standard",
        no_color=False,
    )
    sink: list[SessionOutcome] = []
    code = _cmd_run(
        stage_args,
        transport=ctx.transport,
        secrets=ctx.secrets,
        outcome_sink=sink if role == "eval" else None,
    )
    report: EvalReport | None = None
    if role == "eval" and code == 0 and sink:
        report = _emit_eval_report(
            report_path=ctx.artifact_paths.eval_report,
            final_text=sink[-1].final_text,
            run_id=ctx.run_id,
            plan_id=ctx.run_id,
            plan_version=progress.plan_version,
        )
        print(
            f"fa workflow: eval verdict={report.verdict} "
            f"route={report.route_decision} → {ctx.artifact_paths.eval_report}",
            file=sys.stderr,
        )
    return _StageResult(role=role, exit_code=code, eval_report=report)


def _write_stage_failure_state(
    ctx: _WorkflowContext,
    role: str,
    code: int,
    *,
    progress: _WorkflowProgress,
) -> None:
    write_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=str(ctx.base_task or ""),
            status="FAILED",
            active_role=role,
            active_plan_id=ctx.run_id,
            active_plan_version=progress.plan_version,
            repair_round=progress.repair_round,
            replan_round=progress.replan_round,
            last_actor=role,
            last_transition_reason=f"stage exited {code}",
            blocked_reason=f"stage {role!r} exited {code}",
        ),
    )
    print(
        f"fa workflow: stage {role!r} exited {code} — pipeline stopped (fail-fast).",
        file=sys.stderr,
    )


def _write_terminal_state(
    ctx: _WorkflowContext,
    *,
    last_role: str,
    eval_report: EvalReport | None,
    progress: _WorkflowProgress,
    reason: str,
) -> None:
    status: FlowStatus
    route: str
    if eval_report is not None:
        status = _EVAL_VERDICT_TO_TERMINAL_STATUS.get(eval_report.verdict, "FAILED")
        route = eval_report.route_decision
        blocked = eval_report.summary if eval_report.verdict == "BLOCKED" else ""
    else:
        status = "DONE"
        route = ""
        blocked = ""
    write_flow_state(
        ctx.artifact_paths.flow_state,
        FlowState(
            run_id=ctx.run_id,
            task=str(ctx.base_task or ""),
            status=status,
            active_role=last_role,
            active_plan_id=ctx.run_id,
            active_plan_version=progress.plan_version,
            repair_round=progress.repair_round,
            replan_round=progress.replan_round,
            last_actor=last_role,
            last_transition_reason=reason,
            last_route_decision=route,
            blocked_reason=blocked,
        ),
    )


def _print_terminal_summary(
    ctx: _WorkflowContext,
    *,
    n_stages: int,
    eval_report: EvalReport | None,
    repair_rounds_used: int,
) -> None:
    if eval_report is not None and eval_report.verdict == "PASS":
        suffix = f" after {repair_rounds_used} repair round(s)" if repair_rounds_used else ""
        print(
            f"\nfa workflow: accepted (verdict=PASS){suffix} — run_id={ctx.run_id}",
            file=sys.stderr,
        )
        return
    if eval_report is not None:
        tail = f" (repair budget {repair_rounds_used} exhausted)" if repair_rounds_used else ""
        print(
            f"\nfa workflow: {n_stages} stage(s) ran (run_id={ctx.run_id}); "
            f"eval verdict={eval_report.verdict} route={eval_report.route_decision} "
            f"— not accepted{tail}.",
            file=sys.stderr,
        )
        return
    print(
        f"\nfa workflow: all {n_stages} stage(s) completed OK (run_id={ctx.run_id})",
        file=sys.stderr,
    )


def _resolve_max_repairs(args: argparse.Namespace) -> int:
    raw = getattr(args, "max_repairs", None)
    value = DEFAULT_MAX_REPAIRS if raw is None else int(raw)
    if value < 0:
        value = 0
    return min(value, MAX_REPAIRS_CEILING)


def _resolve_max_replans(args: argparse.Namespace) -> int:
    raw = getattr(args, "max_replans", None)
    value = DEFAULT_MAX_REPLANS if raw is None else int(raw)
    if value < 0:
        value = 0
    return min(value, MAX_REPLANS_CEILING)


def _render_mode_label(mode: str, *, max_repairs: int, max_replans: int) -> str:
    if mode == "repair":
        return f"repair (max repairs {max_repairs})"
    if mode == "adaptive":
        return f"adaptive (max repairs {max_repairs}, max replans {max_replans})"
    return mode


def _canonical_loop_roles(roles: list[str], *, include_planner: bool) -> tuple[str, ...]:
    canonical = ["planner", "coder", "eval"] if include_planner else ["coder", "eval"]
    return tuple(role for role in canonical if role in roles)


def _run_initial_roles(
    ctx: _WorkflowContext, roles: list[str]
) -> tuple[int, int, EvalReport | None]:
    progress = _WorkflowProgress()
    eval_report: EvalReport | None = None
    n_stages = 0
    for index, role in enumerate(roles):
        n_stages += 1
        print(f"\nfa workflow ─ stage {index + 1}/{len(roles)}: {role}", file=sys.stderr)
        result = _run_stage(
            ctx,
            role,
            fresh=index == 0,
            progress=progress,
            transition_reason=f"dispatching stage {index + 1}/{len(roles)}",
        )
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return result.exit_code, n_stages, eval_report
        if result.eval_report is not None:
            eval_report = result.eval_report
    return 0, n_stages, eval_report


def _run_adaptive(
    ctx: _WorkflowContext,
    roles: list[str],
    max_repairs: int,
    max_replans: int,
) -> int:
    """Run the initial role list, then normalize loops to canonical routes.

    After the first pass the controller no longer follows arbitrary role-list
    ordering. Repair transitions always run canonical ``coder -> eval``; planner
    re-entry always runs canonical ``planner -> coder -> eval``. This keeps the
    user-facing entry flexible enough for the initial pass while making the
    adaptive control surface deterministic and testable.
    """
    code, n_stages, eval_report = _run_initial_roles(ctx, roles)
    if code != 0:
        return code

    progress = _WorkflowProgress()
    if eval_report is None:
        _write_terminal_state(
            ctx,
            last_role=roles[-1],
            eval_report=None,
            progress=progress,
            reason="adaptive workflow completed without eval stage",
        )
        _print_terminal_summary(ctx, n_stages=n_stages, eval_report=None, repair_rounds_used=0)
        return 0

    while True:
        if eval_report.route_decision == "return_to_coder":
            if progress.repair_round >= max_repairs:
                reason = (
                    f"repair budget exhausted ({progress.repair_round}/{max_repairs}); "
                    "last route return_to_coder"
                )
                _write_terminal_state(
                    ctx,
                    last_role="eval",
                    eval_report=eval_report,
                    progress=progress,
                    reason=reason,
                )
                _print_terminal_summary(
                    ctx,
                    n_stages=n_stages,
                    eval_report=eval_report,
                    repair_rounds_used=progress.repair_round,
                )
                return 0
            progress = _WorkflowProgress(
                plan_version=progress.plan_version,
                repair_round=progress.repair_round + 1,
                replan_round=progress.replan_round,
            )
            print(
                f"\nfa workflow ─ repair round {progress.repair_round}/{max_repairs} "
                "(adaptive route return_to_coder)",
                file=sys.stderr,
            )
            for role in _canonical_loop_roles(roles, include_planner=False):
                result = _run_stage(
                    ctx,
                    role,
                    fresh=False,
                    progress=progress,
                    transition_reason=(
                        f"repair round {progress.repair_round}: canonical {role} "
                        "after return_to_coder"
                    ),
                )
                n_stages += 1
                if result.exit_code != 0:
                    _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
                    return result.exit_code
                if result.eval_report is not None:
                    eval_report = result.eval_report
            continue

        if eval_report.route_decision == "return_to_planner":
            if progress.replan_round >= max_replans:
                reason = (
                    f"replan budget exhausted ({progress.replan_round}/{max_replans}); "
                    "last route return_to_planner"
                )
                _write_terminal_state(
                    ctx,
                    last_role="eval",
                    eval_report=eval_report,
                    progress=progress,
                    reason=reason,
                )
                _print_terminal_summary(
                    ctx,
                    n_stages=n_stages,
                    eval_report=eval_report,
                    repair_rounds_used=progress.repair_round,
                )
                return 0
            progress = _WorkflowProgress(
                plan_version=progress.plan_version + 1,
                repair_round=progress.repair_round,
                replan_round=progress.replan_round + 1,
            )
            print(
                f"\nfa workflow ─ replan round {progress.replan_round}/{max_replans} "
                f"(plan version {progress.plan_version})",
                file=sys.stderr,
            )
            for role in _canonical_loop_roles(roles, include_planner=True):
                result = _run_stage(
                    ctx,
                    role,
                    fresh=False,
                    progress=progress,
                    transition_reason=(
                        f"replan round {progress.replan_round}: canonical {role} "
                        "after return_to_planner"
                    ),
                )
                n_stages += 1
                if result.exit_code != 0:
                    _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
                    return result.exit_code
                if result.eval_report is not None:
                    eval_report = result.eval_report
            continue

        reason = (
            f"eval verdict {eval_report.verdict} after {progress.repair_round} repair round(s) "
            f"and {progress.replan_round} replan round(s)"
        )
        _write_terminal_state(
            ctx,
            last_role="eval",
            eval_report=eval_report,
            progress=progress,
            reason=reason,
        )
        _print_terminal_summary(
            ctx,
            n_stages=n_stages,
            eval_report=eval_report,
            repair_rounds_used=progress.repair_round,
        )
        return 0


def _run_linear(ctx: _WorkflowContext, roles: list[str]) -> int:
    """Run every role once, in order. Fail-fast on any non-zero stage exit."""
    eval_report: EvalReport | None = None
    progress = _WorkflowProgress()
    for index, role in enumerate(roles):
        print(f"\nfa workflow ─ stage {index + 1}/{len(roles)}: {role}", file=sys.stderr)
        result = _run_stage(
            ctx,
            role,
            fresh=index == 0,
            progress=progress,
            transition_reason=f"dispatching stage {index + 1}/{len(roles)}",
        )
        if result.exit_code != 0:
            _write_stage_failure_state(ctx, role, result.exit_code, progress=progress)
            return result.exit_code
        if result.eval_report is not None:
            eval_report = result.eval_report
    _write_terminal_state(
        ctx,
        last_role=roles[-1],
        eval_report=eval_report,
        progress=progress,
        reason=(
            f"eval verdict {eval_report.verdict} (linear; no repair loop)"
            if eval_report is not None
            else "linear workflow completed"
        ),
    )
    _print_terminal_summary(ctx, n_stages=len(roles), eval_report=eval_report, repair_rounds_used=0)
    return 0


def _run_repair(ctx: _WorkflowContext, roles: list[str], max_repairs: int) -> int:
    """Run the role list once, then bounded ``coder -> eval`` repair rounds.

    The repair loop is driven purely by the machine-readable eval route:
    while the latest eval returns ``return_to_coder`` and the repair budget
    remains, re-run the coder then the eval. Any other route (``complete``,
    ``return_to_planner``, ``blocked``) stops the loop — planner re-entry is
    intentionally NOT performed in this slice; such verdicts are recorded, not
    acted on.
    """
    code, n_stages, eval_report = _run_initial_roles(ctx, roles)
    if code != 0:
        return code

    progress = _WorkflowProgress()
    while (
        eval_report is not None
        and eval_report.route_decision == "return_to_coder"
        and progress.repair_round < max_repairs
    ):
        progress = _WorkflowProgress(
            plan_version=progress.plan_version,
            repair_round=progress.repair_round + 1,
            replan_round=progress.replan_round,
        )
        print(
            f"\nfa workflow ─ repair round {progress.repair_round}/{max_repairs} "
            f"(eval routed return_to_coder)",
            file=sys.stderr,
        )
        coder_result = _run_stage(
            ctx,
            "coder",
            fresh=False,
            progress=progress,
            transition_reason=f"repair round {progress.repair_round}: return_to_coder",
        )
        n_stages += 1
        if coder_result.exit_code != 0:
            _write_stage_failure_state(ctx, "coder", coder_result.exit_code, progress=progress)
            return coder_result.exit_code
        eval_result = _run_stage(
            ctx,
            "eval",
            fresh=False,
            progress=progress,
            transition_reason=f"repair round {progress.repair_round}: re-evaluating",
        )
        n_stages += 1
        if eval_result.exit_code != 0:
            _write_stage_failure_state(ctx, "eval", eval_result.exit_code, progress=progress)
            return eval_result.exit_code
        eval_report = eval_result.eval_report

    budget_exhausted = (
        eval_report is not None
        and eval_report.route_decision == "return_to_coder"
        and progress.repair_round >= max_repairs
    )
    if eval_report is None:
        reason = "repair workflow completed"
    elif budget_exhausted:
        reason = (
            f"repair budget exhausted ({progress.repair_round}/{max_repairs}); "
            "last route return_to_coder"
        )
    else:
        reason = (
            f"eval verdict {eval_report.verdict} after {progress.repair_round} repair round(s)"
        )
    _write_terminal_state(
        ctx,
        last_role="eval" if eval_report is not None else roles[-1],
        eval_report=eval_report,
        progress=progress,
        reason=reason,
    )
    _print_terminal_summary(
        ctx,
        n_stages=n_stages,
        eval_report=eval_report,
        repair_rounds_used=progress.repair_round,
    )
    return 0


def _cmd_workflow(
    args: argparse.Namespace,
    *,
    transport: Transport | None = None,
    secrets: Mapping[str, str] | None = None,
) -> int:
    """Advance a task through the FA role protocol over one shared run-id.

    Modes (``--mode``):

    - ``linear`` (default): run every named role once, in order, fail-fast.
    - ``repair``: run the role list once, then bounded ``coder -> eval`` repair
      rounds driven by the machine-readable eval route (``return_to_coder``),
      up to ``--max-repairs`` (hard ceiling 3). Planner re-entry is not yet
      performed; non-repair routes are recorded, not acted on.
    - ``adaptive``: run the initial role list once, then normalize loop
      transitions to canonical ``coder -> eval`` / ``planner -> coder -> eval``
      routes based on the eval report's machine-readable route decisions.

    ``transport``/``secrets`` are forwarded to every stage so tests can inject
    deterministic seams.
    """
    roles = [r.strip() for r in str(args.roles).split(",") if r.strip()]
    if not roles:
        print("fa workflow: provide at least one role, e.g. planner,coder,eval", file=sys.stderr)
        return 2

    mode = getattr(args, "mode", None) or "linear"
    if mode not in _WORKFLOW_MODES:
        print(
            f"fa workflow: --mode must be one of {', '.join(_WORKFLOW_MODES)} (got {mode!r})",
            file=sys.stderr,
        )
        return 2

    run_id = args.run_id
    if run_id and not _valid_run_id(run_id):
        print("fa workflow: --run-id must match [A-Za-z0-9_.-]{1,128}", file=sys.stderr)
        return 2
    base_task = getattr(args, "task", None)
    if not run_id:
        seed = base_task or roles[0]
        run_id = f"wf-{int(time.time())}-{_slugify_task(seed)}"

    per_role_task = {
        role: getattr(args, f"task_{role}", None) for role in ("planner", "coder", "eval")
    }
    for role in roles:
        if not (per_role_task.get(role) or base_task):
            print(
                f"fa workflow: no task for role {role!r} — pass a shared task "
                f'or --task-{role} "..."',
                file=sys.stderr,
            )
            return 2

    max_repairs = _resolve_max_repairs(args)
    max_replans = _resolve_max_replans(args)
    if mode == "repair":
        missing = [r for r in ("coder", "eval") if r not in roles]
        if missing:
            print(
                f"fa workflow: --mode repair requires roles to include "
                f"{' and '.join(missing)} (got {','.join(roles)})",
                file=sys.stderr,
            )
            return 2
    if mode == "adaptive":
        missing = [r for r in ("planner", "coder", "eval") if r not in roles]
        if missing:
            print(
                f"fa workflow: --mode adaptive requires roles to include "
                f"{' and '.join(missing)} (got {','.join(roles)})",
                file=sys.stderr,
            )
            return 2

    artifact_paths = _workflow_artifact_paths(run_id)
    artifact_paths.base_dir.mkdir(parents=True, exist_ok=True)
    write_flow_state(
        artifact_paths.flow_state,
        FlowState(
            run_id=run_id,
            task=str(base_task or ""),
            status="PLANNING" if roles[0] == "planner" else "PLAN_READY",
            active_role=roles[0],
            active_plan_id=run_id,
            active_plan_version=1,
            last_actor="workflow",
            last_transition_reason=f"workflow initialized (mode={mode})",
        ),
    )

    ctx = _WorkflowContext(
        args=args,
        run_id=run_id,
        base_task=base_task,
        per_role_task=per_role_task,
        artifact_paths=artifact_paths,
        transport=transport,
        secrets=secrets,
    )
    label = _render_mode_label(mode, max_repairs=max_repairs, max_replans=max_replans)
    print(f"fa workflow: run_id={run_id} mode={label} roles={'→'.join(roles)}", file=sys.stderr)
    if mode == "repair":
        return _run_repair(ctx, roles, max_repairs)
    if mode == "adaptive":
        return _run_adaptive(ctx, roles, max_repairs, max_replans)
    return _run_linear(ctx, roles)


def _cmd_run(  # noqa: C901 - top-level run orchestration (config→chain→proxy→loop)
    args: argparse.Namespace,
    *,
    transport: Transport | None = None,
    secrets: Mapping[str, str] | None = None,
    outcome_sink: list[SessionOutcome] | None = None,
) -> int:
    """Drive an LLM-driven coder session.

    ``transport`` is the dependency-injection seam used by tests to
    swap in a deterministic fake transport; production callers pass
    ``None`` and the function constructs a :class:`UrllibTransport`.

    ``secrets`` is the analogous seam for the private API-key store
    (ADR-12). Production passes ``None`` and the function loads keys from
    the resolved secrets file (strict, file-only — never ``os.environ``);
    tests inject a :class:`SecretStore`/mapping directly.
    """
    if getattr(args, "no_color", False):
        os.environ["NO_COLOR"] = "1"
    resolved = _resolve_task(getattr(args, "task_pos", None), getattr(args, "task", None))
    if resolved is None:
        print(
            "fa run: provide a task — positional (fa run \"...\"), --task, or '-' for stdin",
            file=sys.stderr,
        )
        return 2
    args.task = resolved
    if not str(args.task).strip():
        print("fa run: task must be non-empty", file=sys.stderr)
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
    # Secret-isolation (ADR-12): API keys live ONLY in this private store, never
    # in os.environ. Every key reader below (config validation, provider chain,
    # redactor) is fed `secrets` instead of os.environ.
    proxy_url = _resolve_proxy_url()
    proxy_mode = bool(proxy_url)
    if secrets is None:
        # Proxy mode: provider keys live in the proxy, NOT this process. The
        # chain's key store is intentionally empty; only the deploy key / proxy
        # token are tracked (for the redactor). Legacy mode: strict-file store.
        secrets = SecretStore({}) if proxy_mode else _load_secret_store()
    try:
        models = load_models_config_from_path(
            config_path, env=secrets, require_api_keys=not proxy_mode
        )
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

    if proxy_mode:
        rewritten, proxy_err = _proxy_rewrite_chain(chain_config, proxy_url)
        if proxy_err:
            print(f"fa run: {proxy_err}", file=sys.stderr)
            return 2
        chain_config = rewritten

    effective_transport: Transport = transport if transport is not None else UrllibTransport()
    chain = _build_provider_chain(chain_config, transport=effective_transport, secrets=secrets)

    limits = load_runtime_limits_from_path().limits
    # Role-aware registry: planner/eval get read-only tools, coder gets
    # the full baseline (read + write + bash).
    role = args.role
    # Per-role first-attempt sampling temperature. The coder gets a small amount
    # of sampling (0.2) for non-degenerate edits; planner/eval stay at 0.0 for
    # stable, reproducible planning/judgement. (ADR-7's T=1.0-on-retry is a
    # separate retry-policy concern handled by the FailureClassifierObserver.)
    session_temperature = DEFAULT_CODER_TEMPERATURE if role == "coder" else DEFAULT_TEMPERATURE
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
    draft_path = Path.home() / ".fa" / "session-log" / run_id / "pr_draft.md"
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
    # the draft lives under ~/.fa/session-log/ (not /workspace) so
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
    log_path = Path.home() / ".fa" / "session-log" / run_id / "events.jsonl"
    # In proxy mode the provider keys are absent here (they live in the proxy),
    # so the redactor is seeded from the secrets the agent process DOES hold:
    # the fa→proxy token and the deploy key (read value-only, never logged).
    try:
        redactor = SecretRedactor.from_models_config(
            secrets,
            models,
            extra_values=_proxy_redactor_extra() if proxy_mode else (),
            allow_empty=proxy_mode,
        )
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
    # ~/.fa/session-log/<run_id>/pr_draft.md (populated by the M-7 §Q-N
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

    # ── Live output ─────────────────────────────────────────────────────────
    from fa.output import ConsoleRenderer, EventBus, QuietRenderer

    output_bus = EventBus()
    output_mode = getattr(args, "output_mode", None) or "console"
    if output_mode == "console":
        output_bus.add(
            ConsoleRenderer(
                detail=getattr(args, "detail", "standard") or "standard",
            )
        )
    elif output_mode == "quiet":
        output_bus.add(QuietRenderer())
    # json mode: Phase 2

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
        temperature=session_temperature,
        redactor=redactor,
        output=output_bus,
    )
    # Workflow seam: let an orchestrating caller capture the terminal outcome
    # (e.g. to parse the eval role's final message into ``eval_report.json``)
    # without changing this function's int return contract.
    if outcome_sink is not None:
        outcome_sink.append(outcome)
    status = "OK" if outcome.exit_code == 0 else "ERROR"
    print(f"{status}: {outcome.stop_reason} (turns={outcome.turns})")
    if outcome.final_text:
        print(outcome.final_text)
    return outcome.exit_code


def _cmd_selfcheck(args: argparse.Namespace) -> int:  # noqa: C901 - diagnostic flow
    """Diagnose the fa→egress-proxy→provider routing seam (ADR-12)."""
    proxy_url = _resolve_proxy_url()
    config_path = args.config.expanduser().resolve()
    role_name = str(args.role)

    print("fa selfcheck: egress proxy diagnostics")
    print(f"- proxy: {proxy_url or '<not set>'}")
    print(f"- config: {config_path}")
    print(f"- role: {role_name}")

    if not proxy_url:
        print("ERROR: FA_EGRESS_PROXY_URL is not set; the agent is not in proxy mode.")
        print("Hint: in Docker deployment it should point to http://fa-egress-proxy:8080.")
        return 2

    proxy_url_error = _validate_proxy_url(proxy_url)
    if proxy_url_error:
        print(f"ERROR: invalid FA_EGRESS_PROXY_URL: {proxy_url_error}")
        return 2

    proxy_token = _resolve_proxy_token()
    if not proxy_token:
        print(
            "ERROR: proxy token is missing; set FA_PROXY_TOKEN_FILE or mount "
            "/run/secrets/fa_proxy_token."
        )
        return 2

    health_url = _proxy_endpoint(proxy_url, "/healthz")
    try:
        health_status, _health_body = _selfcheck_http_get(health_url)
    except _SelfcheckNetworkError as exc:
        print(f"ERROR: proxy is not reachable at {health_url}: {exc}")
        print("Hint: check `docker compose logs fa-egress-proxy` and container health.")
        return 1
    if health_status != 200:
        print(f"ERROR: proxy /healthz returned HTTP {health_status}.")
        print("Hint: check `docker compose logs fa-egress-proxy`.")
        return 1
    print("OK: proxy /healthz reachable")

    routes_url = _proxy_endpoint(proxy_url, "/routes")
    try:
        routes_status, routes_body = _selfcheck_http_get(
            routes_url, headers={_PROXY_TOKEN_HEADER: proxy_token}
        )
    except _SelfcheckNetworkError as exc:
        print(f"ERROR: proxy /routes is not reachable at {routes_url}: {exc}")
        print("Hint: check `docker compose logs fa-egress-proxy`.")
        return 1
    if routes_status == 403:
        print("ERROR: proxy /routes rejected the fa→proxy token (HTTP 403).")
        print("Hint: verify FA_PROXY_TOKEN_FILE and /run/secrets/fa_proxy_token match the proxy.")
        return 1
    if routes_status != 200:
        print(f"ERROR: proxy /routes returned HTTP {routes_status}.")
        print("Hint: check `docker compose logs fa-egress-proxy`.")
        return 1

    try:
        routes_payload = json.loads(routes_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print("ERROR: proxy /routes returned non-JSON or malformed JSON.")
        return 1
    proxy_routes, payload_error = _selfcheck_parse_routes_payload(routes_payload)
    if payload_error:
        print(f"ERROR: unsafe or malformed proxy /routes payload: {payload_error}")
        return 1
    print(f"OK: proxy /routes returned {len(proxy_routes)} route(s)")

    try:
        models = load_models_config_from_path(config_path, require_api_keys=False)
    except (ConfigurationError, EvalFamilyConflictError, OSError) as exc:
        print(f"ERROR: models config error: {exc}")
        return 2

    chain_config = models.roles.get(role_name)
    if chain_config is None:
        print(
            f"ERROR: role {role_name!r} not found in {config_path}; known: {sorted(models.roles)}"
        )
        return 2

    from fa.egress_proxy.routing import ProxyConfigError

    try:
        expected_routes = _selfcheck_expected_routes(chain_config)
    except ProxyConfigError as exc:
        print(f"ERROR: could not compute agent route names: {exc}")
        return 2

    problems: list[str] = []
    for route_name, api_key_env in expected_routes.items():
        has_key = proxy_routes.get(route_name)
        if has_key is None:
            problems.append(
                f"route {route_name!r} is in {config_path} for role {role_name!r}, "
                "but is absent from proxy /routes — agent and proxy should read "
                "/srv/first-agent/routing/models.yaml; after editing it, "
                "restart/recreate the proxy (for example: scripts/fa-update.sh, or "
                "docker compose -f docker-compose.fa.yml up -d --force-recreate "
                "fa-egress-proxy)."
            )
        elif not has_key:
            problems.append(
                f"route {route_name!r}: key for {api_key_env} is absent in "
                "/srv/first-agent/secrets/fa.env (mounted as /run/secrets/fa.env "
                "in fa-egress-proxy)."
            )

    if problems:
        print("fa selfcheck: ERROR")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("fa selfcheck: OK")
    print(f"- checked role routes: {len(expected_routes)}")
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    """Liveness-test the LLM provider chain with a minimal real API call.

    Sends ``{"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}``
    through the full agent→proxy→provider path. No system prompt, no tools, no
    inner loop — pure provider connectivity and key-validity test.

    Cost: ~10 input tokens + 1 output token per chain entry probed.
    """
    config_path = args.config.expanduser().resolve()
    probe_timeout = int(args.timeout)

    proxy_url = _resolve_proxy_url()
    proxy_mode = bool(proxy_url)
    secrets: Mapping[str, str] = SecretStore({}) if proxy_mode else _load_secret_store()

    try:
        models = load_models_config_from_path(
            config_path, env=secrets, require_api_keys=not proxy_mode
        )
    except (ConfigurationError, EvalFamilyConflictError, OSError) as exc:
        print(f"fa probe: configuration error: {exc}", file=sys.stderr)
        return 2

    if not models.roles:
        print(f"fa probe: no roles found in {config_path}", file=sys.stderr)
        return 2

    if args.all_roles:
        role_names = sorted(models.roles)
    else:
        role_names = [args.role]

    transport: Transport = UrllibTransport()
    any_failure = False

    for role_name in role_names:
        chain_config = models.roles.get(role_name)
        if chain_config is None:
            print(
                f"fa probe: role {role_name!r} not found in {config_path}; "
                f"known: {sorted(models.roles)}"
            )
            any_failure = True
            continue

        if proxy_mode:
            rewritten, proxy_err = _proxy_rewrite_chain(chain_config, proxy_url)
            if proxy_err:
                print(f"fa probe: {proxy_err}", file=sys.stderr)
                any_failure = True
                continue
            chain_config = rewritten

        # Override timeout_seconds on every chain entry for the probe.
        probed_entries = tuple(
            replace(entry, timeout_seconds=probe_timeout) for entry in chain_config.chain
        )
        chain_config = replace(chain_config, chain=probed_entries)

        chain = _build_provider_chain(chain_config, transport=transport, secrets=secrets)

        print(
            f"\nfa probe: role={role_name}"
            f" (model={chain_config.model}, family={chain_config.family})"
        )

        request = RequestInfo(
            model_slug=chain_config.model,
            messages=({"role": "user", "content": "hi"},),
            temperature=0.0,
            max_tokens=1,
            tools=(),
        )

        start = time.monotonic()
        try:
            response, _call_id, attempts = chain.request(request)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            for attempt in attempts:
                status_icon = "✅" if attempt.error is None else "⚠️"
                error_text = f" {attempt.error}" if attempt.error else ""
                print(
                    f"  chain[{attempts.index(attempt)}] {attempt.provider}/{attempt.slug}"
                    f" {status_icon} {attempt.status}{error_text} ({attempt.ms}ms)"
                )
            tokens_text = f"in={response.in_tokens} out={response.out_tokens}"
            reply_preview = (response.text or "")[:60].replace("\n", " ")
            print(
                f"\nfa probe: OK ({elapsed_ms}ms, {tokens_text})"
                + (f' reply="{reply_preview}"' if reply_preview else "")
            )
        except ProviderChainExhaustedError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            for index, attempt in enumerate(exc.attempts):
                print(
                    f"  chain[{index}] {attempt.provider}/{attempt.slug}"
                    f" ❌ {attempt.status}"
                    f" {attempt.error or 'unknown'} ({attempt.ms}ms)"
                )
            n_entries = len(chain_config.chain)
            print(f"\nfa probe: FAIL — all {n_entries} entries failed ({elapsed_ms}ms)")
            any_failure = True
        except ProviderRequestShapeError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            print(f"  ❌ request shape error: {exc} ({elapsed_ms}ms)")
            print(f"\nfa probe: FAIL — request rejected ({elapsed_ms}ms)")
            any_failure = True

    return 1 if any_failure else 0


def _cmd_stats(args: argparse.Namespace) -> int:  # noqa: C901 — CLI dispatch
    """Analyze session logs — tool usage, file access, tokens, efficiency."""
    import time as _time

    from fa.stats import (
        aggregate_sessions,
        find_dead_zones,
        parse_session,
        render_aggregate,
        render_session,
        render_session_json,
    )

    workspace = args.workspace.resolve()
    runs_dir = Path.home() / ".fa" / "session-log"

    if not runs_dir.exists():
        print(f"fa stats: no runs found at {runs_dir}", file=sys.stderr)
        return 1

    # Discover sessions
    session_dirs: list[Path] = []
    if args.run_id:
        target = runs_dir / args.run_id
        if not target.exists():
            print(f"fa stats: run {args.run_id!r} not found at {target}", file=sys.stderr)
            return 1
        session_dirs = [target]
    else:
        session_dirs = sorted(
            [d for d in runs_dir.iterdir() if d.is_dir() and (d / "events.jsonl").exists()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )

    # Filter by --since (uses file mtime)
    if args.since and not args.run_id:
        since_s = _parse_since(args.since)
        if since_s is not None:
            cutoff = _time.time() - since_s
            session_dirs = [d for d in session_dirs if d.stat().st_mtime >= cutoff]

    if not session_dirs:
        print("fa stats: no matching sessions found", file=sys.stderr)
        return 1

    # Parse sessions
    sessions = []
    for d in session_dirs:
        result = parse_session(d / "events.jsonl")
        if result is not None:
            sessions.append(result)

    if not sessions:
        print("fa stats: no parseable sessions found", file=sys.stderr)
        return 1

    # Render
    if args.output == "json":
        import json as _json

        if args.run_id and len(sessions) == 1:
            print(_json.dumps(render_session_json(sessions[0]), indent=2, default=str))
        else:
            agg = aggregate_sessions(sessions)
            agg["sessions_detail"] = [render_session_json(s) for s in sessions]
            print(_json.dumps(agg, indent=2, default=str))
        return 0

    # Console
    if args.run_id and len(sessions) == 1:
        render_session(sessions[0])
    else:
        render_aggregate(sessions)

    # Dead zones
    if getattr(args, "dead_zones", False):
        dead = find_dead_zones(workspace, sessions)
        if dead:
            sys.stderr.write(f"\n🔍 Dead zones ({len(dead)} src/ files never accessed):\n")
            for p in dead[:15]:
                sys.stderr.write(f"   {p}\n")
            if len(dead) > 15:
                sys.stderr.write(f"   ... and {len(dead) - 15} more\n")
            sys.stderr.flush()

    return 0


def _parse_since(value: str) -> float | None:
    """Parse '7d', '24h', '1h' into seconds."""
    value = value.strip().lower()
    try:
        if value.endswith("d"):
            return float(value[:-1]) * 86400
        if value.endswith("h"):
            return float(value[:-1]) * 3600
        if value.endswith("m"):
            return float(value[:-1]) * 60
    except ValueError:
        return None
    return None


def _proxy_endpoint(proxy_url: str, path: str) -> str:
    return f"{proxy_url.rstrip('/')}/{path.lstrip('/')}"


def _validate_proxy_url(proxy_url: str) -> str:
    parsed = urllib.parse.urlparse(proxy_url)
    if parsed.scheme not in {"http", "https"}:
        return "expected http:// or https:// URL"
    if not parsed.hostname:
        return "missing host"
    return ""


def _selfcheck_http_get(
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: float = 5.0,
) -> tuple[int, bytes]:
    try:
        request = urllib.request.Request(url, method="GET")  # noqa: S310
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return int(response.status), response.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read()
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise _SelfcheckNetworkError(str(exc)) from exc


def _selfcheck_expected_routes(chain_config: ChainConfig) -> dict[str, str]:
    from fa.egress_proxy.routing import route_name_for

    routes: dict[str, str] = {}
    for entry in chain_config.chain:
        routes.setdefault(route_name_for(entry.provider, entry.slug), entry.api_key_env)
    return routes


def _selfcheck_parse_routes_payload(payload: object) -> tuple[dict[str, bool], str]:
    if not isinstance(payload, list):
        return {}, "expected a JSON list"
    routes: dict[str, bool] = {}
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            return {}, f"routes[{index}] is not an object"
        if set(item) != {"name", "has_key"}:
            return {}, f"routes[{index}] must contain only name and has_key"
        name = item["name"]
        has_key = item["has_key"]
        if not isinstance(name, str) or not name:
            return {}, f"routes[{index}].name must be a non-empty string"
        if not isinstance(has_key, bool):
            return {}, f"routes[{index}].has_key must be a boolean"
        routes[name] = has_key
    return routes, ""


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


def _cmd_egress_proxy(args: argparse.Namespace) -> int:
    """Run the egress-injection proxy (ADR-12 secret isolation).

    Reads provider keys from ``--secrets`` and routing from ``--models``; binds
    ``--listen`` and forwards POSTs to upstream providers with the real key
    injected. Runs in a separate container from the agent; the agent never holds
    a provider key.
    """
    from fa.egress_proxy.routing import ProxyConfigError, build_route_table
    from fa.egress_proxy.server import serve

    # Routing source (non-secret). Skip api_key presence check: keys live in the
    # proxy's own secrets file, validated below.
    try:
        models = load_models_config_from_path(
            args.models.expanduser().resolve(), require_api_keys=False
        )
    except (ConfigurationError, OSError) as exc:
        print(f"fa egress-proxy: models config error: {exc}", file=sys.stderr)
        return 2

    chain_entries = [
        (entry.provider, entry.slug, entry.base_url, entry.api_key_env)
        for role in models.roles.values()
        for entry in role.chain
    ]
    try:
        route_table = build_route_table(chain_entries)
    except ProxyConfigError as exc:
        print(f"fa egress-proxy: route table error: {exc}", file=sys.stderr)
        return 2

    secret_store = SecretStore.from_file(args.secrets.expanduser())
    secrets = dict(secret_store)

    token = _read_token_file(args.token_file.expanduser())
    if not token:
        print(
            f"fa egress-proxy: empty/missing proxy token at {args.token_file}",
            file=sys.stderr,
        )
        return 2

    host, _, port_str = args.listen.rpartition(":")
    if not host or not port_str.isdigit():
        print(f"fa egress-proxy: invalid --listen {args.listen!r}", file=sys.stderr)
        return 2

    serve(
        route_table=route_table,
        secrets=secrets,
        proxy_token=token,
        host=host,
        port=int(port_str),
    )
    return 0


def _read_token_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _proxy_redactor_extra() -> tuple[str, ...]:
    """Non-env secret values the redactor should mask in proxy mode."""
    return tuple(v for v in (_resolve_proxy_token(), _read_deploy_key_material()) if v)


def _read_deploy_key_material() -> str:
    """Return the deploy private-key body (value-only) for the redactor.

    Best-effort: returns the base64 body between the PEM markers so the redactor
    can mask it if it ever appears in tool output. Never logs the content.
    Returns empty string if the key is absent/unreadable (dev boxes).
    """
    for candidate in (Path("/run/secrets/git_key"),):
        try:
            text = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        body = "".join(
            line.strip() for line in text.splitlines() if line and not line.startswith("-----")
        )
        if len(body) >= 16:
            return body
    return ""


def _build_provider_chain(
    config: ChainConfig,
    *,
    transport: Transport,
    secrets: Mapping[str, str] | None = None,
) -> ProviderChain:
    """Wire a :class:`ProviderChain` against ``transport``.

    Production-side composition seam: every entry in ``config.chain``
    instantiates a fresh adapter via :func:`build_provider`, sharing
    the single transport. Tests can call this helper directly with a
    fake transport to exercise the wiring without touching the CLI
    argument-parsing layer.

    ``secrets`` is the private key source (ADR-12 secret isolation). It is
    forwarded to ``ProviderChain(env=...)`` so the chain reads API keys from the
    isolated store rather than ``os.environ``. When omitted the chain falls back
    to its own default (``os.environ``) — production always passes the store.
    """

    def factory(entry: ChainEntry) -> Provider:
        return build_provider(entry.provider, transport=transport)

    return ProviderChain(config, provider_factory=factory, env=secrets)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return
    raise SystemExit(func(args))
