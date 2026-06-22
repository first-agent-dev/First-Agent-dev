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
from dataclasses import asdict, replace
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
from fa.inner_loop.coder_loop import (
    DEFAULT_CODER_TEMPERATURE,
    DEFAULT_MAX_TURNS,
    DEFAULT_TEMPERATURE,
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
    )
    selfcheck_parser.add_argument(
        "--role",
        default="coder",
        help="Role to check (matches a top-level key in ~/.fa/models.yaml).",
    )
    selfcheck_parser.add_argument(
        "--config",
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
    )
    probe_parser.add_argument(
        "--role",
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


def _cmd_run(  # noqa: C901 - top-level run orchestration (config→chain→proxy→loop)
    args: argparse.Namespace,
    *,
    transport: Transport | None = None,
    secrets: Mapping[str, str] | None = None,
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

    # ── Live output ─────────────────────────────────────────────────────────
    from fa.output import ConsoleRenderer, EventBus, QuietRenderer

    output_bus = EventBus()
    output_mode = getattr(args, "output_mode", None) or "console"
    if output_mode == "console":
        output_bus.add(ConsoleRenderer(
            detail=getattr(args, "detail", "standard") or "standard",
        ))
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
