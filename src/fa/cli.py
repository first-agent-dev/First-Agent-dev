# To hide internal ops commands from the public `--help` output without
# removing them from the parser entirely, pass `help=argparse.SUPPRESS`
# when defining the subparser. They will remain fully functional and
# documented in `cli_help.py` (e.g. via `fa help ops`), but will not
# clutter the default developer-facing CLI interface.
# Example:
#   smoke_parser = subparsers.add_parser("inner-loop-smoke", help=argparse.SUPPRESS)

from __future__ import annotations

import argparse
import json
import logging
import math
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
from typing import TYPE_CHECKING, Any

from fa import __version__
from fa.authoring_rules import RULE_ALLOWLIST
from fa.authoring_tcb import render_json, render_text, run_all
from fa.chunker import CHUNKER_VERSION, Chunk, default_chunker
from fa.cli_help import COMMANDS, help_as_json, render_command_help_ru, render_top_level_ru
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
    AttemptHistoryObserver,
    AuditHook,
    AuthExpiredBlocker,
    FailureClassifierObserver,
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
from fa.inner_loop.recovery.attempt_history import AttemptHistory
from fa.inner_loop.registry import ToolRegistry
from fa.inner_loop.runtime_limits import RuntimeLimits
from fa.inner_loop.session_db import SessionDatabase, SessionDatabaseError
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
    load_flow_state,
    parse_eval_report,
    write_eval_report,
    write_flow_state,
)
from fa.observability import CostGuardian
from fa.observability.redaction import SecretRedactor, SecretRedactorError
from fa.paths import fa_session_log_root, fa_state_root, tighten_fa_artifact_modes
from fa.providers import (
    DEFAULT_MODELS_YAML_PATH,
    ChainConfig,
    ChainEntry,
    ModelsConfig,
    ProviderChain,
    SecretStore,
    UrllibTransport,
    build_provider,
    load_models_config_from_path,
)
from fa.providers.base import Provider, RequestInfo, Transport
from fa.providers.debug_bodies import wrap_transport_for_debug_bodies
from fa.providers.errors import (
    ConfigurationError,
    ProviderChainExhaustedError,
    ProviderRequestShapeError,
)
from fa.providers.routing_lint import lint_models_config

if TYPE_CHECKING:  # pragma: no cover - typing only
    # fa.output is imported lazily inside _cmd_run (module-level import kept out
    # of the CLI's import path deliberately); these names are needed for
    # annotations only, so they are declared here rather than promoted to a
    # runtime import that would change startup behaviour.
    from fa.output import EventBus
    from fa.runtime import PtyPool
    from fa.stats import SessionAnalytics
from fa.roles import EvalFamilyConflictError
from fa.session.manager import RunContext, SessionContext, SessionManager, SessionManagerError
from fa.verifier import load_contracts_from_dir

logger = logging.getLogger(__name__)

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


def _valid_run_id(value: str) -> bool:
    return bool(_RUN_ID_RE.fullmatch(value))


def _session_manager_for_args(args: argparse.Namespace) -> SessionManager:
    """Build the lifecycle manager from deployment/test roots, never host topology."""
    workspace_override = getattr(args, "workspace", None)
    configured_workspace_root = os.environ.get("FA_WORKSPACE_ROOT")
    if configured_workspace_root:
        workspace_root = Path(configured_workspace_root)
    elif workspace_override is not None:
        workspace_root = Path(workspace_override).expanduser().resolve().parent
    elif Path("/sessions").is_dir() or Path("/repo").is_dir():
        workspace_root = Path("/sessions")
    else:
        workspace_root = Path.cwd()
    configured_source = os.environ.get("FA_SESSION_SOURCE")
    if configured_source:
        source_workspace: Path | None = Path(configured_source)
    else:
        source_workspace = Path("/repo") if Path("/repo").is_dir() else None
    return SessionManager(
        state_root=fa_state_root(),
        workspace_root=workspace_root,
        source_workspace=source_workspace,
    )


def _open_run_authority(run: RunContext) -> SessionDatabase:
    try:
        return SessionDatabase.open_existing(run.session_db_path, session_id=run.session_id)
    except SessionDatabaseError as exc:
        raise SessionManagerError(exc.code, str(exc)) from exc


def _resolve_workflow_lifecycle(
    args: argparse.Namespace,
    initial_run_id: str,
) -> tuple[str, SessionContext | None, RunContext | None, SessionDatabase | None]:
    """Resolve one workflow invocation context; legacy direct Namespaces stay local."""
    if not hasattr(args, "session_id"):
        return initial_run_id, None, None, None
    resolved_context = _resolve_cli_run_context(args)
    if resolved_context is None:
        raise RuntimeError("workflow session context unexpectedly absent")
    session_context, run_context, session_db = resolved_context
    args.workspace = run_context.workspace_path
    return run_context.run_id, session_context, run_context, session_db


def _resolve_cli_run_context(
    args: argparse.Namespace,
) -> tuple[SessionContext, RunContext, SessionDatabase] | None:
    """Resolve production context or return None for explicit legacy fixtures."""
    private_run = getattr(args, "_run_context", None)
    if private_run is not None:
        session = getattr(args, "_session_context", None)
        if session is None:
            raise SessionManagerError("session_context_missing", "workflow stage has no session context")
        authority = getattr(args, "_session_db", None) or _open_run_authority(private_run)
        return session, private_run, authority
    if not hasattr(args, "session_id"):
        # Existing isolated unit fixtures construct a Namespace directly. They
        # remain outside the production CLI lifecycle claim until migrated.
        return None
    manager = _session_manager_for_args(args)
    session = manager.create_or_attach_session(
        session_id=getattr(args, "session_id", None),
        workspace_override=getattr(args, "workspace", None),
    )
    run = manager.begin_run(session, getattr(args, "run_id", None) or None)
    return session, run, _open_run_authority(run)


def _resolve_task(positional: str | None, flag: str | None) -> str | None:
    """Resolve the effective task from positional arg, --task flag, or stdin.

    Precedence: an explicit --task wins over the positional (so the flag form
    stays authoritative for back-compat). A value of ``-`` (in either slot)
    means "read the task from stdin" (explicit pipe mode).

    Transparent Stdin: If stdin is not a TTY (data is piped) and a text prompt
    is also provided, they are concatenated (prompt first, piped data as context).
    If only piped data is present, it becomes the task.
    Returns ``None`` when no task source was supplied at all.
    """
    chosen = flag if flag is not None else positional

    # Read piped data if sys.stdin is not interactive
    piped_data = ""
    # In pytest, sys.stdin is often mocked (e.g. io.StringIO) which doesn't
    # have a real isatty() backing an FD, so we catch AttributeError/ValueError.
    try:
        # pytest replaces sys.stdin with a DontReadFromInput object
        # which throws OSError when read() is called. We should safely
        # handle isatty() returning False but read() failing.
        is_interactive = sys.stdin.isatty()
    except (AttributeError, ValueError, OSError):
        is_interactive = True

    if not is_interactive:
        try:
            import select

            # Quick check if there is data to read without blocking
            if select.select([sys.stdin], [], [], 0.0)[0]:
                piped_data = sys.stdin.read().strip()
        except (AttributeError, ValueError, OSError):
            # Fallback for Windows and StringIO mock test environments
            try:
                piped_data = sys.stdin.read().strip()
            except (AttributeError, ValueError, OSError):
                # Intentionally ignore unreadable/mock stdin on fallback; treat as empty.
                pass

    if chosen == "-":
        # Explicit stdin read. If we already read it via isatty check, use it,
        # otherwise read now (for the mocked sys.stdin tests).
        if not piped_data:
            try:
                piped_data = sys.stdin.read().strip()
            except (AttributeError, ValueError, OSError):
                # Intentionally ignore unreadable/mock stdin; treat as no input.
                pass
        return piped_data if piped_data else None

    if chosen is None:
        return piped_data if piped_data else None

    if piped_data:
        # We have both an explicit instruction and piped context.
        return f"{chosen}\n\n<stdin>\n{piped_data}\n</stdin>"

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
    return fa_state_root() / ".env"


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
            "FA_EGRESS_PROXY_URL set but no proxy token found (set FA_PROXY_TOKEN_FILE or /run/secrets/fa_proxy_token)"
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
        name = route_name_for(entry.provider, entry.model)
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
        epilog=render_top_level_ru() + "\n\nHint: `fa help <команда>` — можно проверить подробную справку.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    chunk_parser = subparsers.add_parser(
        "chunk",
        help=COMMANDS["chunk"]["summary_en"],
        description=(
            "Run the deterministic chunker on PATH and emit the produced "
            "chunks. Intended for manual inspection of the chunker output; "
            "the real indexing command (`fa reindex`) lands once storage is "
            "wired."
        ),
    )
    chunk_parser.add_argument("path", type=Path, help=COMMANDS["chunk"]["args"]["path"]["en"])
    chunk_parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help=COMMANDS["chunk"]["args"]["--output"]["en"],
    )
    chunk_parser.set_defaults(func=_cmd_chunk)

    smoke_parser = subparsers.add_parser(
        "inner-loop-smoke",
        help=COMMANDS["inner-loop-smoke"]["summary_en"],
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
        help=COMMANDS["inner-loop-smoke"]["args"]["--workspace"]["en"],
    )
    smoke_parser.add_argument(
        "--input",
        default="README.md",
        help=COMMANDS["inner-loop-smoke"]["args"]["--input"]["en"],
    )
    smoke_parser.add_argument(
        "--output",
        default=".fa/inner-loop-smoke.txt",
        help=COMMANDS["inner-loop-smoke"]["args"]["--output"]["en"],
    )
    smoke_parser.set_defaults(func=_cmd_inner_loop_smoke)

    run_parser = subparsers.add_parser(
        "run",
        help=COMMANDS["run"]["summary_en"],
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
        help=COMMANDS["run"]["args"]["--role/-r"]["en"],
    )
    run_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help=COMMANDS["run"]["args"]["--config/-c"]["en"],
    )
    run_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help=COMMANDS["run"]["args"]["--workspace/-w"]["en"],
    )
    run_parser.add_argument(
        "--session-id",
        default=None,
        help="Attach to an existing persistent session; omit to create a new session.",
    )
    run_parser.add_argument(
        "--max-turns",
        "-n",
        type=int,
        default=DEFAULT_MAX_TURNS,
        help=COMMANDS["run"]["args"]["--max-turns/-n"]["en"],
    )
    run_parser.add_argument(
        "--run-id",
        "-i",
        default="",
        help=COMMANDS["run"]["args"]["--run-id/-i"]["en"],
    )
    run_parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help=COMMANDS["run"]["args"]["--resume"]["en"],
    )
    run_parser.add_argument(
        "--output-mode",
        choices=("console", "quiet"),
        default="console",
        help=COMMANDS["run"]["args"]["--output-mode"]["en"],
    )
    run_parser.add_argument(
        "--detail",
        choices=("minimal", "standard", "verbose", "debug"),
        default="standard",
        help=COMMANDS["run"]["args"]["--detail"]["en"],
    )
    run_parser.add_argument(
        "--no-color",
        action="store_true",
        default=False,
        help=COMMANDS["run"]["args"]["--no-color"]["en"],
    )
    run_parser.set_defaults(func=_cmd_run)

    workflow_parser = subparsers.add_parser(
        "workflow",
        help=COMMANDS["workflow"]["summary_en"],
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
        help=COMMANDS["workflow"]["args"]["roles"]["en"],
    )
    workflow_parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help=COMMANDS["workflow"]["args"]["task"]["en"],
    )
    workflow_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=None,
        help=COMMANDS["workflow"]["args"]["--workspace/-w"]["en"],
    )
    workflow_parser.add_argument(
        "--session-id",
        default=None,
        help="Attach to an existing persistent session; omit to create a new session.",
    )
    workflow_parser.add_argument(
        "--run-id",
        "-i",
        default="",
        help=COMMANDS["workflow"]["args"]["--run-id/-i"]["en"],
    )
    workflow_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help=COMMANDS["workflow"]["args"]["--config/-c"]["en"],
    )
    workflow_parser.add_argument(
        "--max-turns",
        "-n",
        type=int,
        default=DEFAULT_MAX_TURNS,
        help=COMMANDS["workflow"]["args"]["--max-turns/-n"]["en"],
    )
    workflow_parser.add_argument(
        "--mode",
        "-m",
        choices=_WORKFLOW_MODES,
        default="linear",
        help=COMMANDS["workflow"]["args"]["--mode/-m"]["en"],
    )
    # S8.4: mirrors ``run``'s flag so one workflow invocation can be made
    # machine-parseable. Forwarded to every stage in ``_run_stage``.
    workflow_parser.add_argument(
        "--output-mode",
        choices=("console", "quiet"),
        default="console",
        help=COMMANDS["workflow"]["args"]["--output-mode"]["en"],
    )
    workflow_parser.add_argument(
        "--max-repairs",
        type=int,
        default=DEFAULT_MAX_REPAIRS,
        help=COMMANDS["workflow"]["args"]["--max-repairs"]["en"],
    )
    workflow_parser.add_argument(
        "--max-replans",
        type=int,
        default=DEFAULT_MAX_REPLANS,
        help=COMMANDS["workflow"]["args"]["--max-replans"]["en"],
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
        help=COMMANDS["help"]["summary_en"],
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
        help=COMMANDS["help"]["args"]["topic"]["en"],
    )
    help_parser.add_argument(
        "--json",
        action="store_true",
        help=COMMANDS["help"]["args"]["--json"]["en"],
    )
    help_parser.set_defaults(func=_cmd_help)

    selfcheck_parser = subparsers.add_parser(
        "selfcheck",
        help=COMMANDS["selfcheck"]["summary_en"],
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
        help=COMMANDS["selfcheck"]["args"]["--role/-r"]["en"],
    )
    selfcheck_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help=COMMANDS["selfcheck"]["args"]["--config/-c"]["en"],
    )
    selfcheck_parser.set_defaults(func=_cmd_selfcheck)

    routing_check_parser = subparsers.add_parser(
        "routing-check",
        help=COMMANDS["routing-check"]["summary_en"],
        description=(
            "Statically lint models.yaml for cross-role route conflicts (the "
            "same check fa egress-proxy performs at container-start time) and "
            "near-miss base_url typos, WITHOUT Docker, network, or a running "
            "proxy. Intended as a fast pre-build/pre-deploy gate."
        ),
        epilog=render_command_help_ru("routing-check"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    routing_check_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help=COMMANDS["routing-check"]["args"]["--config/-c"]["en"],
    )
    routing_check_parser.set_defaults(func=_cmd_routing_check)

    probe_parser = subparsers.add_parser(
        "probe",
        help=COMMANDS["probe"]["summary_en"],
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
        help=COMMANDS["probe"]["args"]["--role/-r"]["en"],
    )
    probe_parser.add_argument(
        "--all-roles",
        action="store_true",
        help=COMMANDS["probe"]["args"]["--all-roles"]["en"],
    )
    probe_parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_MODELS_YAML_PATH,
        help=COMMANDS["probe"]["args"]["--config/-c"]["en"],
    )
    probe_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help=COMMANDS["probe"]["args"]["--timeout"]["en"],
    )
    probe_parser.set_defaults(func=_cmd_probe)

    stats_parser = subparsers.add_parser(
        "stats",
        help=COMMANDS["stats"]["summary_en"],
        description=(
            "Parse events.jsonl files from past fa run sessions and render "
            "analytics: tool usage, file access patterns, token timelines, "
            "provider health, guard activity, dead zones, efficiency warnings."
        ),
        epilog=render_command_help_ru("stats"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    stats_parser.add_argument(
        "--run-id",
        "-i",
        default=None,
        help=COMMANDS["stats"]["args"]["--run-id/-i"]["en"],
    )
    stats_parser.add_argument(
        "--session-id",
        default=None,
        help="Restrict stats to one persistent session authority.",
    )
    stats_parser.add_argument(
        "--since",
        default=None,
        help=COMMANDS["stats"]["args"]["--since"]["en"],
    )
    stats_parser.add_argument(
        "--output",
        choices=("console", "json"),
        default="console",
        help=COMMANDS["stats"]["args"]["--output"]["en"],
    )
    stats_parser.add_argument(
        "--workspace",
        "-w",
        type=Path,
        default=Path.cwd(),
        help=COMMANDS["stats"]["args"]["--workspace/-w"]["en"],
    )
    stats_parser.add_argument(
        "--dead-zones",
        action="store_true",
        help=COMMANDS["stats"]["args"]["--dead-zones"]["en"],
    )
    stats_parser.add_argument(
        "--global-history",
        action="store_true",
        default=False,
        help="Show cross-run history from global_history.db (derived projection, not per-run events)",
    )
    stats_parser.set_defaults(func=_cmd_stats)

    authoring_parser = subparsers.add_parser(
        "authoring-check",
        help=COMMANDS["authoring-check"]["summary_en"],
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
        help=COMMANDS["authoring-check"]["args"]["--workspace"]["en"],
    )
    authoring_parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=COMMANDS["authoring-check"]["args"]["--manifest"]["en"],
    )
    authoring_parser.add_argument(
        "--output",
        choices=("text", "json"),
        default="text",
        help=COMMANDS["authoring-check"]["args"]["--output"]["en"],
    )
    authoring_parser.set_defaults(func=_cmd_authoring_check)

    proxy_parser = subparsers.add_parser(
        "egress-proxy",
        help=COMMANDS["egress-proxy"]["summary_en"],
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
        help=COMMANDS["egress-proxy"]["args"]["--models"]["en"],
    )
    proxy_parser.add_argument(
        "--secrets",
        type=Path,
        default=Path("/run/secrets/fa.env"),
        help=COMMANDS["egress-proxy"]["args"]["--secrets"]["en"],
    )
    proxy_parser.add_argument(
        "--token-file",
        type=Path,
        default=Path("/run/secrets/fa_proxy_token"),
        help=COMMANDS["egress-proxy"]["args"]["--token-file"]["en"],
    )
    proxy_parser.add_argument(
        "--listen",
        type=str,
        default="0.0.0.0:8080",
        help=COMMANDS["egress-proxy"]["args"]["--listen"]["en"],
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


# S7.5: one definition for the smoke identity. ``run_id`` and
# ``session_id`` must agree — the S4-F1 defect was precisely that the run
# was labelled while the session was left empty.
_SMOKE_SESSION_ID = "cli-smoke"


def _cmd_inner_loop_smoke(args: argparse.Namespace) -> int:
    workspace = args.workspace.resolve()
    limits = load_runtime_limits_from_path().limits
    registry = build_baseline_registry(
        workspace,
        bash_timeout_seconds=limits.bash_timeout_seconds,
    )
    # S7.5 / S4-F1 (Q28 option b). This command is a provider-free smoke check
    # of the M-1 registry + HookRegistry, so it is deliberately NOT part of the
    # persistent session model — but it still needs an EventLog.
    #
    # Previously it called ``EventLog(log_path)`` with no ``session_db``, so
    # ``SessionState.__post_init__`` defaulted one into existence at
    # ``<workspace>/.fa/session.db`` with an EMPTY ``session_id`` — an artifact
    # an operator cannot distinguish from the real authority.
    #
    # Empty is not inert: every identity guard is written
    # ``if self.session_id and ...`` (``state.py``; ``session_db.py``), and
    # ``event_count()`` drops its ``WHERE session_id = ?`` scoping. Measured,
    # that DB accepted a row stamped for a *different* session. Naming the
    # session re-arms those guards **by construction** rather than by adding a
    # new check, and confines the artifact to a clearly-labelled directory.
    smoke_root = workspace / ".fa" / "smoke"
    smoke_root.mkdir(parents=True, exist_ok=True)
    session_db = SessionDatabase(smoke_root / "session.db", session_id=_SMOKE_SESSION_ID)
    log = EventLog(
        smoke_root / "smoke-events.jsonl",
        run_id=_SMOKE_SESSION_ID,
        session_db=session_db,
        session_id=_SMOKE_SESSION_ID,
    )
    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))

    # LoopGuard warn_sink: emit loop_guard_warn event to EventLog so
    # the early-warning signal (repeat_warn threshold) reaches session.db
    # and the operator gets console visibility. Without warn_sink, the
    # _emit_warn method short-circuits and the event kind is dead code.
    def _smoke_loop_guard_warn_sink(detector: str, message: str) -> None:
        try:
            log.append(
                actor="hook",
                kind="loop_guard_warn",
                content={"detector": detector, "message": message},
            )
        except Exception as exc:  # noqa: BLE001 — observer must never block
            logger.warning("loop guard observer failed: %s", exc)

    hooks.register(
        LoopGuard(
            repeat_warn=limits.loop_guard_repeat_warn,
            circuit_breaker=limits.loop_guard_circuit_breaker,
            window=limits.loop_guard_window,
            warn_sink=_smoke_loop_guard_warn_sink,
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
    # R-3 FailureClassifierObserver + R-6 AttemptHistoryObserver: classify
    # tool failures and write recovery history so the coder-recovery prompt
    # can read it. Wired here so the smoke entrypoint exercises the same
    # hook chain as `fa run`.
    attempt_history = AttemptHistory(workspace / ".fa" / "attempt_history.json")
    hooks.register(FailureClassifierObserver(event_log=log))
    hooks.register(AttemptHistoryObserver(history=attempt_history))
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

    from fa.feature_flags import FeatureFlags

    state = SessionState(
        workspace_root=workspace,
        run_id=_SMOKE_SESSION_ID,
        log=log,
        feature_flags=FeatureFlags(blackboard_enabled=False),
    )
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


def _workflow_artifact_paths(run_id: str, *, base_dir: Path | None = None) -> _WorkflowArtifactPaths:
    """Return canonical workflow artifact paths under ``~/.fa/session-log``.

    Temporary physical model (workflow implementation plan 2026-06-29):
    human-readable draft remains ``pr_draft.md``; controller truth lives in
    separate JSON artifacts for eval verdicts and workflow state.
    """
    base_dir = base_dir or (fa_session_log_root() / run_id)
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
    print("\nHint: `fa help <команда>` — можно проверить подробную справку.")
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

# S8.7 — the aggregate ``global_history`` row's ``stop_reason`` is a SEMANTIC
# outcome, so it must be derived from the semantic authority (the terminal
# ``FlowState.status``) and not from ``result_code``.
#
# Why this mapping exists: every mode returns 0 when the pipeline merely RAN TO
# COMPLETION, regardless of the eval verdict (``_run_linear`` and
# ``_run_repair``/``_run_adaptive`` all ``return 0``). The previous
# ``"workflow_complete" if result_code == 0 else "workflow_failed"`` therefore
# recorded a BLOCKED run as ``workflow_complete`` — measured, three artifacts
# disagreeing about one run. Cross-run projections (``fa history``, S9) read
# this column, so a rejected run was counted as a success.
#
# ``exit_code`` is deliberately NOT changed here: that is a separate
# operator-visible contract (S8 plan Q35). Keeping them separate means this
# mapping fixes the projection without silently altering shell semantics.
_WORKFLOW_STATUS_TO_STOP_REASON: dict[str, str] = {
    "DONE": "workflow_complete",
    "FAILED": "workflow_failed",
    "REPAIR_REQUIRED": "workflow_repair_required",
    "REPLAN_REQUIRED": "workflow_replan_required",
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
    session_context: SessionContext | None = None
    run_context: RunContext | None = None
    session_db: SessionDatabase | None = None

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
    stage_kwargs: dict[str, object] = {
        "task_pos": None,
        "task": ctx.task_for(role),
        "role": role,
        "config": ctx.args.config,
        "workspace": ctx.args.workspace,
        "max_turns": ctx.args.max_turns,
        "run_id": ctx.run_id,
        "resume": not fresh,
        # S8.4: forward the operator's choice instead of hardcoding "console".
        # ``getattr`` default keeps legacy direct-Namespace callers (tests that
        # predate the flag) working unchanged.
        "output_mode": getattr(ctx.args, "output_mode", None) or "console",
        "detail": "standard",
        "no_color": False,
    }
    if ctx.run_context is not None and ctx.session_context is not None:
        stage_kwargs.update(
            {
                "session_id": ctx.session_context.session_id,
                "_session_context": ctx.session_context,
                "_run_context": ctx.run_context,
                "_session_db": ctx.session_db,
            }
        )
    stage_args = argparse.Namespace(**stage_kwargs)
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


def _read_back_terminal_state(flow_state_path: Path, run_id: str) -> FlowState | None:
    """Re-read the terminal ``FlowState`` this invocation just persisted (S8.3).

    This is the production consumer of ``flow_state.json``. Before S8.3 the
    artifact was write-only: ``load_flow_state`` had zero callers outside its
    defining module, while the ``global_history`` export synthesised a semantic
    outcome from an exit code. Reading the artifact back makes the persisted
    state the single source of terminal truth and lets the projection agree
    with it (see ``_WORKFLOW_STATUS_TO_STOP_REASON``).

    The ``run_id`` check is what makes this a *verification* rather than a
    decorative read: a stale or foreign ``flow_state.json`` left in the run
    directory is rejected instead of silently trusted, mirroring
    ``SessionManager._read_manifest``'s ``manifest_identity_mismatch`` guard.

    Fail-soft by contract. The workflow has already finished by the time this
    runs, so a projection read must never change the exit code or raise; every
    failure degrades to ``None`` and the caller keeps its previous behaviour.
    """
    try:
        state = load_flow_state(flow_state_path)
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning(
            "workflow terminal-state read-back failed for %s; falling back to exit-code semantics",
            run_id,
            exc_info=True,
        )
        return None
    if state.run_id != run_id:
        logger.warning(
            "workflow terminal-state identity mismatch at %s: artifact says %r, expected %r",
            flow_state_path,
            state.run_id,
            run_id,
        )
        return None
    return state


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


def _run_initial_roles(ctx: _WorkflowContext, roles: list[str]) -> tuple[int, int, EvalReport | None]:
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
                reason = f"repair budget exhausted ({progress.repair_round}/{max_repairs}); last route return_to_coder"
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
                f"\nfa workflow ─ repair round {progress.repair_round}/{max_repairs} (adaptive route return_to_coder)",
                file=sys.stderr,
            )
            for role in _canonical_loop_roles(roles, include_planner=False):
                result = _run_stage(
                    ctx,
                    role,
                    fresh=False,
                    progress=progress,
                    transition_reason=(f"repair round {progress.repair_round}: canonical {role} after return_to_coder"),
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
                    f"replan budget exhausted ({progress.replan_round}/{max_replans}); last route return_to_planner"
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
                        f"replan round {progress.replan_round}: canonical {role} after return_to_planner"
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
            f"\nfa workflow ─ repair round {progress.repair_round}/{max_repairs} (eval routed return_to_coder)",
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
        reason = f"repair budget exhausted ({progress.repair_round}/{max_repairs}); last route return_to_coder"
    else:
        reason = f"eval verdict {eval_report.verdict} after {progress.repair_round} repair round(s)"
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


def _workflow_exit_code(result_code: int, terminal_state: FlowState | None) -> int:
    """Map a workflow run to its process exit code (S10c.2 / Q35b).

    The exit code REPORTS THE VERDICT, not merely that the pipeline ran. Every
    mode returns 0 once its stages complete regardless of what the evaluator
    decided, so ``fa workflow && deploy`` used to proceed on BLOCKED code and
    any CI gate reading ``$?`` saw success.

    * ``0`` — terminal status ``DONE``: the work was accepted.
    * ``1`` — any other terminal status: it ran, it was not accepted.
    * ``result_code`` passthrough — a usage/configuration error (**2**) is a
      DIFFERENT contract and must stay distinguishable. "I invoked this
      wrongly" and "the code was rejected" have different fixes.

    ``terminal_state is None`` means the artifact was missing, corrupt, or
    belonged to another run. That keeps the pipeline's own answer rather than
    inventing a verdict; ``_read_back_terminal_state`` has already logged why.

    Pure and separately testable on purpose: the caller derives BOTH this and
    the aggregate row's ``stop_reason`` from one artifact read, and extracting
    the branch keeps ``_cmd_workflow`` under the C901 threshold — the ratchet
    flagged it at 16 the moment this logic was added inline.
    """
    if result_code != 0 or terminal_state is None:
        return result_code
    return 0 if terminal_state.status == "DONE" else 1


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

    per_role_task = {role: getattr(args, f"task_{role}", None) for role in ("planner", "coder", "eval")}
    for role in roles:
        if not (per_role_task.get(role) or base_task):
            print(
                f'fa workflow: no task for role {role!r} — pass a shared task or --task-{role} "..."',
                file=sys.stderr,
            )
            return 2

    max_repairs = _resolve_max_repairs(args)
    max_replans = _resolve_max_replans(args)
    if mode == "repair":
        missing = [r for r in ("coder", "eval") if r not in roles]
        if missing:
            print(
                f"fa workflow: --mode repair requires roles to include {' and '.join(missing)} (got {','.join(roles)})",
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

    # S8.2 — wall time for the whole invocation. Anchored BEFORE session
    # lifecycle resolution because session setup is part of what an operator
    # waits for. ``monotonic`` (not ``time.time``) so a wall-clock adjustment
    # mid-run cannot produce a negative or inflated duration; same pattern as
    # ``_cmd_run`` (``_run_start_mono``).
    _wf_start_mono = time.monotonic()
    try:
        run_id, session_context, run_context, session_db = _resolve_workflow_lifecycle(args, run_id)
    except SessionManagerError as exc:
        print(f"fa workflow: session error [{exc.code}]: {exc}", file=sys.stderr)
        return 2

    artifact_paths = _workflow_artifact_paths(
        run_id,
        base_dir=run_context.run_log_dir if run_context is not None else None,
    )
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
        session_context=session_context,
        run_context=run_context,
        session_db=session_db,
    )
    label = _render_mode_label(mode, max_repairs=max_repairs, max_replans=max_replans)
    print(f"fa workflow: run_id={run_id} mode={label} roles={'→'.join(roles)}", file=sys.stderr)
    if mode == "repair":
        result_code = _run_repair(ctx, roles, max_repairs)
    elif mode == "adaptive":
        result_code = _run_adaptive(ctx, roles, max_repairs, max_replans)
    else:
        result_code = _run_linear(ctx, roles)

    # S10c.2 / Q35b — read the persisted terminal state ONCE, here, and derive
    # two things from it: the aggregate row's ``stop_reason`` (S8.7, below) and
    # this command's exit code (at the terminal return).
    #
    # **Read it OUTSIDE the try block deliberately.** The export below is
    # best-effort and swallows every exception so telemetry can never break a
    # workflow. Binding this inside that block would make the exit code depend
    # on the export succeeding: an early failure (EventLog construction, a bad
    # import) is swallowed, execution reaches the return, and the name is
    # unbound -> UnboundLocalError escaping from the one place written never to
    # fail. One artifact read, two derived contracts, neither able to break the
    # other.
    terminal_state = _read_back_terminal_state(artifact_paths.flow_state, run_id)

    # Computed HERE, before the export, so the aggregate row's ``exit_code``
    # column and the process's own status are the same number by construction.
    exit_code = _workflow_exit_code(result_code, terminal_state)

    # LOGIC-11: Export single aggregate row to global_history.db after
    # workflow completes. Per-stage exports are skipped in _cmd_run when
    # outcome_sink is non-None, so each stage doesn't overwrite the previous
    # one's row. This single export reads ALL events from the shared
    # session.db and produces correct cross-stage telemetry.
    try:
        from fa.inner_loop.global_history import export_session_to_global_history
        from fa.inner_loop.state import EventLog as _EventLog

        session_dir = fa_session_log_root() / run_id
        log_path = session_dir / "events.jsonl"
        workflow_log = _EventLog(
            log_path,
            run_id=run_id,
            session_db=session_db,
            session_id=session_context.session_id if session_context is not None else "",
        )
        # Build a synthetic outcome for the aggregate row.
        # Token totals and tool breakdown come from _extract_telemetry_from_log
        # which reads the shared session.db correctly.
        # S8.3 / S8.7 — derive the semantic outcome from the persisted terminal
        # FlowState, not from result_code. Falls back to the historical
        # exit-code rule when the artifact is missing, corrupt, or belongs to
        # another run, so the export can never become less reliable than before.
        _fallback_stop_reason = "workflow_complete" if result_code == 0 else "workflow_failed"
        _stop_reason = (
            _WORKFLOW_STATUS_TO_STOP_REASON.get(terminal_state.status, _fallback_stop_reason)
            if terminal_state is not None
            else _fallback_stop_reason
        )
        aggregate_outcome = SessionOutcome(
            exit_code=exit_code,
            stop_reason=_stop_reason,
            turns=0,  # turns in global_history come from telemetry, not outcome
            final_text="",
            tool_results=(),
        )
        # Get model/family from the last role's chain config
        _models = load_models_config_from_path(ctx.args.config.expanduser().resolve(), require_api_keys=False)
        _last_role = roles[-1] if roles else "coder"
        _last_chain = _models.roles.get(_last_role)
        _last_model = _last_chain.name if _last_chain else ""
        _last_family = _last_chain.family if _last_chain else ""

        export_session_to_global_history(
            run_id=run_id,
            outcome=aggregate_outcome,
            log=workflow_log,
            role="→".join(roles),
            model=_last_model,
            family=_last_family,
            workspace_root=ctx.args.workspace,
            duration_ms=int((time.monotonic() - _wf_start_mono) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 — best-effort, never crash workflow
        import logging

        logging.getLogger(__name__).warning("workflow global_history export failed for %s: %s", run_id, exc)

    return exit_code


def _validate_run_args(args: argparse.Namespace) -> str | None:
    """Validate ``fa run``'s arguments; return the operator message, or ``None`` if valid.

    Extracted from ``_cmd_run`` (S10b.2). Pure apart from one documented
    mutation — see below — so it is unit-testable without a session, a config
    file, or a transport.

    **Returns a message rather than printing one.** The caller owns the stream
    and the exit code, which keeps every ``return 2`` in ``_cmd_run`` visible
    at one place instead of scattered through a helper. It also makes the
    guard order assertable directly: the message identifies which guard fired.

    **The one impurity, stated because hiding it would be worse:** a resolved
    task is written back to ``args.task``. ``_resolve_task`` merges the
    positional argument, ``--task`` and stdin, and the rest of ``_cmd_run``
    reads ``args.task``. Threading the resolved value out separately would
    change the call contract of everything downstream for no behavioural gain.

    Guard ORDER is part of the contract, not an implementation detail: the
    first failing guard decides the message an operator sees, and
    ``test_s10b_parity_validation_prologue`` pins each one by its unique
    wording (plan RK4).
    """
    resolved = _resolve_task(getattr(args, "task_pos", None), getattr(args, "task", None))
    if resolved is None:
        return "fa run: provide a task — positional (fa run \"...\"), --task, or '-' for stdin"
    args.task = resolved
    if not str(args.task).strip():
        return "fa run: task must be non-empty"
    if args.max_turns < 1:
        return "fa run: --max-turns must be a positive integer"
    if args.run_id and not _valid_run_id(args.run_id):
        return "fa run: --run-id must match [A-Za-z0-9_.-]{1,128}"
    if (
        getattr(args, "resume", False)
        and hasattr(args, "session_id")
        and not getattr(args, "session_id", None)
        and getattr(args, "_run_context", None) is None
    ):
        return "fa run: --resume requires --session-id and starts a new run"
    return None


def _resolve_run_models(
    *,
    config_path: Path,
    role: str,
    secrets: Mapping[str, str],
    proxy_url: str,
) -> tuple[ModelsConfig, ChainConfig] | str:
    """Load the models config and select ``role``'s chain, rewriting it for proxy mode.

    Extracted from ``_cmd_run`` (S10b.2). Returns ``(models, chain_config)`` on
    success, or the operator-facing error message as a ``str``.

    **Why a union return rather than raising.** These three failures are not
    exceptional — they are the ordinary "you configured it wrong" paths, and
    all three already produced ``return 2`` inline. Raising and re-catching at
    the call site would add a control-flow layer that changes nothing an
    operator sees. ``isinstance(result, str)`` at the caller keeps the exit
    code where the other exit codes live.

    The three failure modes stay distinct because
    ``test_s10b_parity_config_error`` and ``test_s10b_parity_unknown_role``
    assert branch-unique wording; collapsing them into one message would pass
    an exit-code-only test and fail those.

    **Known gap, pinned not fixed (I-40).** The ``except`` clause below does
    not catch ``yaml.YAMLError``, so a *malformed* config still escapes as a
    traceback rather than becoming a message here. That behaviour is unchanged
    by this extraction and is pinned by
    ``test_s10b_parity_unparseable_yaml_crashes``; fixing it is a product
    change and belongs to whichever slice owns I-40, not to a
    behaviour-invariance refactor.
    """
    proxy_mode = bool(proxy_url)
    try:
        models = load_models_config_from_path(config_path, env=secrets, require_api_keys=not proxy_mode)
    except (ConfigurationError, EvalFamilyConflictError, OSError) as exc:
        return f"fa run: configuration error: {exc}"

    chain_config = models.roles.get(role)
    if chain_config is None:
        known = sorted(models.roles)
        return f"fa run: role {role!r} not found in {config_path}; known: {known}"

    if proxy_mode:
        rewritten, proxy_err = _proxy_rewrite_chain(chain_config, proxy_url)
        if proxy_err:
            return f"fa run: {proxy_err}"
        chain_config = rewritten

    return models, chain_config


def _build_compactor_chain(
    models: ModelsConfig,
    *,
    transport: Transport,
    secrets: Mapping[str, str],
    proxy_url: str,
) -> ProviderChain | None:
    """Build the optional ``compactor`` provider chain; ``None`` if unconfigured.

    Extracted from ``_cmd_run`` (S10b.2).

    **The swallowed proxy error is deliberate and is preserved exactly.** If
    the proxy rewrite fails for the compactor, the original (un-rewritten)
    config is used rather than aborting the run — unlike the *primary* chain,
    where the same failure returns exit 2. That asymmetry is intentional:
    compaction is an optional capability, and losing it should degrade the run
    rather than kill it.

    It is called out here because it reads like a bug at a glance (``if not
    proxy_err:`` with no ``else``), and a future reader "fixing" it would turn
    a degraded run into a hard failure — a behaviour change no exit-code test
    on the happy path would catch. Pinned by
    ``test_s10b_parity_proxy_mode_builds_compactor_chain``.
    """
    compactor_config = models.roles.get("compactor")
    if compactor_config is None:
        return None
    if proxy_url:
        rewritten, proxy_err = _proxy_rewrite_chain(compactor_config, proxy_url)
        if not proxy_err:
            compactor_config = rewritten
    return _build_provider_chain(compactor_config, transport=transport, secrets=secrets)


def _build_role_registry(role: str, workspace: Path, *, bash_timeout_seconds: int) -> ToolRegistry:
    """Select the role-appropriate tool registry.

    Extracted from ``_cmd_run`` (S10b.2). Role-aware capability scoping:
    ``planner`` and ``eval`` get read-only tools; everything else gets the full
    baseline (read + write + bash).

    **This is a security boundary, not a convenience switch.** The ``else``
    branch is deliberately the permissive one, so an unrecognised role gets the
    baseline registry rather than failing closed — matching the pre-extraction
    behaviour exactly. Do not "tidy" this into an explicit allow-list without
    treating it as a product change: ``fa run --role <typo>`` currently gets
    write+bash tools, and that is what the shipped CLI does today.
    """
    if role == "planner":
        return build_planner_registry(workspace, bash_timeout_seconds=bash_timeout_seconds)
    if role == "eval":
        return build_eval_registry(workspace, bash_timeout_seconds=bash_timeout_seconds)
    return build_baseline_registry(workspace, bash_timeout_seconds=bash_timeout_seconds)


def _build_run_hook_registry(
    *,
    workspace: Path,
    log: EventLog,
    limits: RuntimeLimits,
    redactor: SecretRedactor | None,
    draft_store: PrDraftStore,
    run_log_dir: Path,
    output_bus_ref: list[EventBus],
) -> HookRegistry:
    """Assemble the guard/observer stack for a ``fa run`` session.

    Extracted from ``_cmd_run`` (S10b.2). Registration ORDER is behavioural,
    not cosmetic: ``SandboxHook`` is registered first so only
    workspace-contained paths reach ``IntentGuard``'s classifier, and the
    original ordering is preserved exactly.

    **``output_bus_ref`` is a one-element list, and that is on purpose.** In
    the pre-extraction code, ``_loop_guard_warn_sink`` was a closure over
    ``output_bus`` — a local that is not assigned until roughly 90 lines
    *later*, well after the hooks are registered. Python resolves closure
    variables at call time, so the sink saw the bus even though it did not
    exist at registration time.

    Passing ``output_bus`` by value here would silently break that: the
    parameter would bind ``None`` (or fail with ``UnboundLocalError``) and
    ``loop_warn`` console events would stop appearing — a *silent* observability
    regression, invisible to exit-code tests, in code whose entire purpose is
    operator visibility. A one-element list preserves the late binding
    explicitly, so the deferred read is a visible part of the signature
    instead of an accident of scoping that the next refactor deletes.
    """

    def _loop_guard_warn_sink(detector: str, message: str) -> None:
        try:
            log.append(
                actor="hook",
                kind="loop_guard_warn",
                content={"detector": detector, "message": message},
            )
        except Exception as exc:  # noqa: BLE001 — observer must never block
            logger.warning("loop guard observer failed: %s", exc)
        # FIX-5: emit loop_warn for console visibility.
        #
        # ``OutputEvent`` is imported HERE, at call time, not from module scope.
        # ``fa.output`` is deliberately not a module-level import in this file,
        # and annotating it under ``TYPE_CHECKING`` alone made this line raise
        # ``NameError`` at runtime — which the broad ``except`` below then
        # swallowed, silently killing every console ``loop_warn``. Caught by a
        # direct functional probe of this sink; no exit-code test would have
        # seen it. Keep the import inside the function.
        try:
            from fa.output import OutputEvent

            if output_bus_ref:
                output_bus_ref[0].emit(
                    OutputEvent(
                        type="loop_warn",
                        data={"detector": detector, "message": message},
                    )
                )
        except Exception as exc:  # noqa: BLE001 — observer must never block
            logger.warning("loop guard observer failed: %s", exc)

    hooks = HookRegistry()
    hooks.register(SandboxHook(workspace))
    hooks.register(
        LoopGuard(
            repeat_warn=limits.loop_guard_repeat_warn,
            circuit_breaker=limits.loop_guard_circuit_breaker,
            window=limits.loop_guard_window,
            warn_sink=_loop_guard_warn_sink,
        )
    )
    hooks.register(RateLimitBlocker(suppression_seconds=limits.rate_limit_suppression_seconds))
    hooks.register(LockfileBlocker(suppression_seconds=limits.lockfile_suppression_seconds))
    hooks.register(AuthExpiredBlocker(suppression_seconds=limits.auth_expired_suppression_seconds))
    # M-7 IntentGuard: reads the per-session PR draft at
    # ~/.fa/session-log/<run_id>/pr_draft.md (populated by the M-7 §Q-N
    # ``pr.prepare`` tool). Registered after SandboxHook so only
    # workspace-contained paths reach the intent classifier.
    hooks.register(IntentGuard(repo_root=workspace, draft_store=draft_store))
    hooks.register(AuditHook(event_log=log))
    hooks.register(SecretGuard(secrets=redactor.secrets if redactor is not None else frozenset()))
    hooks.register(CostGuardian(budget_usd=limits.cost_budget_usd, event_log=log))
    # R-3 FailureClassifierObserver + R-6 AttemptHistoryObserver: classify tool
    # failures and write recovery history so the coder-recovery prompt can read
    # it. These were defined but never registered (LOGIC-15), which made the
    # `recovery_action` event kind dead code in production.
    hooks.register(FailureClassifierObserver(event_log=log))
    hooks.register(AttemptHistoryObserver(history=AttemptHistory(run_log_dir / "attempt_history.json")))
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
    return hooks


def _build_pty_pool(*, workspace: Path, run_id: str) -> PtyPool | None:
    """Build the stateful PTY pool, or ``None`` if it cannot be initialised.

    Extracted from ``_cmd_run`` (S10b.2). FIND-007: the live CLI harness owns
    the pool, wired to the ``pty_pool_max_size`` feature flag.

    **Failure is not fatal by design.** Any error degrades to ``None``, and the
    bash tool falls back to stateless subprocess execution. That is why the
    broad ``except`` is correct here rather than sloppy — a PTY is an
    optimisation, and an environment without one (a container without a tty, a
    platform without ``pty``) must still run.

    ``os`` is read from module scope on purpose. Re-importing it inside the
    function shadows the module-level import and produces
    ``UnboundLocalError`` on the earlier ``os.getpid()`` reference in
    ``_cmd_run`` — a real bug that was fixed once already; the comment survives
    the extraction so it is not reintroduced.
    """
    try:
        from fa.runtime import PtyPool as _PtyPool

        try:
            max_size = int(os.environ.get("FA_PTY_POOL_MAX_SIZE", "2"))
        except (TypeError, ValueError):
            max_size = 2
        return _PtyPool(max_size=max_size, base_cwd=workspace, run_id=run_id)
    except Exception as exc:  # noqa: BLE001 - graceful degradation, fallback to subprocess
        logger.warning("Failed to init PtyPool for live CLI: %s, fallback stateless", exc)
        return None


def _build_output_bus(args: argparse.Namespace, output_mode: str) -> EventBus:
    """Build the console/quiet output bus for a run.

    Extracted from ``_cmd_run`` (S10b.2).

    ``fa.output`` is imported inside the function, preserving the pre-existing
    lazy-import decision rather than quietly promoting it to module scope: this
    module is the CLI entry point and its import cost is on every ``fa``
    invocation, including ``--help``.

    An unrecognised ``output_mode`` deliberately yields a bus with **no**
    renderer attached (``json`` mode is Phase 2). Events are still emitted and
    still reach the durable log; only the console rendering is absent. That is
    the shipped behaviour and is preserved exactly.
    """
    from fa.output import ConsoleRenderer, EventBus, QuietRenderer

    output_bus = EventBus()
    if output_mode == "console":
        output_bus.add(
            ConsoleRenderer(
                detail=getattr(args, "detail", "standard") or "standard",
                no_color=bool(getattr(args, "no_color", False)),
            )
        )
    elif output_mode == "quiet":
        output_bus.add(QuietRenderer())
    return output_bus


def _prepare_pr_draft(
    draft_store: PrDraftStore,
    draft_path: Path,
    *,
    resume: bool,
) -> tuple[str, str | None]:
    """Read any resumable PR draft and reset the store. Returns ``(text, error)``.

    Extracted from ``_cmd_run`` (S10b.2). ``error`` is ``None`` on success; a
    non-``None`` error is fatal (exit 2) at the call site.

    **Two failures, two different severities — and the asymmetry is the point.**

    * Failing to *read* an existing draft is a **warning**: the run continues
      with empty resume context. The operator loses continuity, not the run.
    * Failing to *clear* the draft store is **fatal**: M-7's ``IntentGuard``
      trusts the draft's provenance, so continuing with a stale or
      externally-fabricated draft would let a mutating tool run against
      intent the current session never established. Failing closed is the
      security-correct behaviour.

    Both are preserved exactly as they were inline. The warning is printed here
    rather than returned because it is not the caller's decision — there is no
    exit code attached to it, and returning "a message that is not an error"
    would invite a caller to treat it as one.
    """
    resume_draft_text = ""
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
        return resume_draft_text, f"fa run: failed to reset PR draft path {draft_store.path}: {exc}"

    return resume_draft_text, None


def _session_db_runtime_error_message(exc: RuntimeError, db_path: Path) -> str | None:
    """Map a session-database ``RuntimeError`` to an operator message.

    Extracted from ``_cmd_run`` (S10b.2). Returns ``None`` for a
    ``RuntimeError`` this function does not recognise, which the caller must
    treat as "re-raise" rather than "no error".

    LOGIC-8 + NEW-3: both ``SessionDatabase.append_event_row``
    (``event_log_write_failed``) and ``EventLog.append``
    (``event_log_authority_unavailable``) raise ``RuntimeError``, and they are
    distinguished by a marker in the message text. The two get distinct
    diagnostics because they mean different things to an operator: one is "the
    database is not reachable", the other is "it is reachable and rejected a
    write".

    **Returning ``None`` rather than a generic message is deliberate.** An
    unrecognised ``RuntimeError`` is a bug, not a misconfiguration, and it must
    surface as a traceback with its original stack. Collapsing it into a
    friendly string here would hide real defects behind a plausible-looking
    diagnostic — the exact failure mode this codebase's BLE001 rule exists to
    prevent.
    """
    exc_str = str(exc)
    if "event_log_authority_unavailable" in exc_str:
        return f"fa run: session database not available at {db_path}: {exc}"
    if "event_log_write_failed" in exc_str:
        return f"fa run: failed to write event to session database at {db_path}: {exc}"
    return None


def _cmd_run(
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
    prologue_error = _validate_run_args(args)
    if prologue_error is not None:
        print(prologue_error, file=sys.stderr)
        return 2

    workspace_override = getattr(args, "workspace", None)
    workspace = workspace_override.resolve() if workspace_override is not None else Path.cwd().resolve()
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
    resolved_models = _resolve_run_models(
        config_path=config_path,
        role=args.role,
        secrets=secrets,
        proxy_url=proxy_url,
    )
    if isinstance(resolved_models, str):
        print(resolved_models, file=sys.stderr)
        return 2
    models, chain_config = resolved_models

    # Resolve session/run context before transport wrapping and provider-chain
    # construction. The legacy branch is retained only for direct unit
    # Namespaces that predate the session selector field.
    session_context: SessionContext | None = None
    run_context: RunContext | None = None
    session_db: SessionDatabase | None = None
    try:
        resolved_context = _resolve_cli_run_context(args)
    except SessionManagerError as exc:
        print(f"fa run: session error [{exc.code}]: {exc}", file=sys.stderr)
        return 2
    if resolved_context is not None:
        session_context, run_context, session_db = resolved_context
        workspace = run_context.workspace_path
        run_id = run_context.run_id
        run_log_dir = run_context.run_log_dir
    else:
        run_id = args.run_id or f"run-{os.getpid()}"
        run_log_dir = fa_session_log_root() / run_id

    # I-36 retroactive half (S10c.3 / Q56). New artifacts are created 0600 by
    # `private_opener` and the SQLite pre-create, but an already-deployed tree
    # still holds 0644 files and 0755 directories from before that fix. Repair
    # them once per run, here, where the state root is known and before any new
    # artifact is written. Best-effort and idempotent; see the helper for why
    # symlinks are skipped and directories get 0700.
    tighten_fa_artifact_modes(fa_state_root())

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

    effective_transport: Transport = transport if transport is not None else UrllibTransport()
    effective_transport = wrap_transport_for_debug_bodies(
        effective_transport,
        run_log_dir=run_log_dir,
        redactor=redactor,
    )
    chain = _build_provider_chain(chain_config, transport=effective_transport, secrets=secrets)

    compactor_chain = _build_compactor_chain(
        models,
        transport=effective_transport,
        secrets=secrets,
        proxy_url=proxy_url,
    )

    limits = load_runtime_limits_from_path().limits
    # Role-aware registry: planner/eval get read-only tools, coder gets
    # the full baseline (read + write + bash).
    role = args.role
    # Per-role first-attempt sampling temperature. The coder gets a small amount
    # of sampling (0.2) for non-degenerate edits; planner/eval stay at 0.0 for
    # stable, reproducible planning/judgement. (ADR-7's T=1.0-on-retry is a
    # separate retry-policy concern handled by the FailureClassifierObserver.)
    session_temperature = DEFAULT_CODER_TEMPERATURE if role == "coder" else DEFAULT_TEMPERATURE
    registry = _build_role_registry(role, workspace, bash_timeout_seconds=limits.bash_timeout_seconds)

    # M-7 §Q-N: ``pr.prepare`` is the producer side of the
    # IntentGuard read seam. The shared ``PrDraftStore`` binds the
    # stable on-disk path to current-session provenance so stale or
    # externally-fabricated drafts are not trusted by the guard.
    draft_path = run_log_dir / "pr_draft.md"
    draft_store = PrDraftStore(draft_path)

    # --resume preserves the on-disk draft for the next role to read;
    # only the in-memory SHA-256 digest is reset, which forces the
    # current session to re-establish trust via a fresh ``pr.prepare``
    # call before any mutating tool is allowed (IntentGuard contract).
    # ``getattr`` fallback keeps pre-``--resume`` tests working.
    resume = getattr(args, "resume", False)

    # When resuming, inject the previous session's draft content as
    # mutable memory-summary context so the LLM sees the existing
    # plan/work-log from turn 1 without promoting it into pinned
    # standing governance. The draft lives under ~/.fa/session-log/
    # (not /workspace) so fs.read_file cannot reach it directly.
    resume_draft_text, draft_error = _prepare_pr_draft(draft_store, draft_path, resume=resume)
    if draft_error is not None:
        print(draft_error, file=sys.stderr)
        return 2
    registry.register(build_prepare_pr_tool(draft_store))
    log_path = run_log_dir / "events.jsonl"
    # redactor was already resolved above (before the transport was wrapped
    # for Tier-3 debug-body capture); reused here unchanged.
    try:
        log = EventLog(
            log_path,
            run_id=run_id,
            redactor=redactor,
            session_db=session_db,
            session_id=session_context.session_id if session_context is not None else "",
        )
    except RuntimeError as exc:
        db_path = log_path.parent / "session.db"
        print(
            f"fa run: session database not available at {db_path}: {exc}",
            file=sys.stderr,
        )
        return 2
    # Late-binding seam for the LoopGuard warn sink: the EventBus is not
    # constructed until the output section below, but the sink closes over it
    # and is invoked only during drive_session, i.e. after it exists. See
    # _build_run_hook_registry for why this is a list and not a value.
    output_bus_ref: list[EventBus] = []
    hooks = _build_run_hook_registry(
        workspace=workspace,
        log=log,
        limits=limits,
        redactor=redactor,
        draft_store=draft_store,
        run_log_dir=run_log_dir,
        output_bus_ref=output_bus_ref,
    )

    pty_pool = _build_pty_pool(workspace=workspace, run_id=run_id)

    state = SessionState(
        workspace_root=workspace,
        session_id=session_context.session_id if session_context is not None else "",
        run_id=run_id,
        log=log,
        session_db=session_db,
        pty_pool=pty_pool,
    )

    output_mode = getattr(args, "output_mode", None) or "console"
    output_bus = _build_output_bus(args, output_mode)
    output_bus_ref.append(output_bus)

    # Wire output_bus to state so bootstrap warnings and runtime hooks emit console events.
    state.attach_output_bus(output_bus)

    _run_start_mono = time.monotonic()
    try:
        outcome = drive_session(
            args.task,
            provider_chain=chain,
            compactor_chain=compactor_chain,
            registry=registry,
            hooks=hooks,
            state=state,
            role=role,
            acting_family=chain_config.family,
            limits=limits,
            max_turns=args.max_turns,
            system_prompt_extra="",
            initial_memory_summary=resume_draft_text,
            temperature=session_temperature,
            redactor=redactor,
            output=output_bus,
        )
    except RuntimeError as exc:
        # LOGIC-8 + NEW-3: EventLog authority or write failures.
        # Both SessionDatabase.append_event_row (event_log_write_failed) and
        # EventLog.append (event_log_authority_unavailable) can raise
        # RuntimeError. Catch both with explicit messages so the operator
        # sees a clear diagnostic instead of a raw Python traceback.
        message = _session_db_runtime_error_message(exc, log.path.parent / "session.db")
        if message is None:
            raise  # Re-raise unexpected RuntimeErrors
        print(message, file=sys.stderr)
        return 2
    _run_duration_ms = int((time.monotonic() - _run_start_mono) * 1000)
    # Slice 9: export to global_history.db as derived projection (best-effort, never crashes main)
    # LOGIC-11: skip per-stage export when called from _cmd_workflow (outcome_sink
    # is non-None). The workflow controller exports a single aggregate row after
    # all stages complete, avoiding INSERT OR REPLACE overwriting by later stages.
    if outcome_sink is None:
        try:
            from fa.inner_loop.global_history import export_session_to_global_history

            export_session_to_global_history(
                run_id=run_id,
                outcome=outcome,
                log=log,
                role=role,
                model=chain_config.name,
                family=chain_config.family,
                workspace_root=workspace,
                duration_ms=_run_duration_ms,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort export must not break run
            import logging

            logging.getLogger(__name__).warning("global_history export failed for %s: %s", run_id, exc)

    # Workflow seam: let an orchestrating caller capture the terminal outcome
    # (e.g. to parse the eval role's final message into ``eval_report.json``)
    # without changing this function's int return contract.
    if outcome_sink is not None:
        outcome_sink.append(outcome)
    status = "OK" if outcome.exit_code == 0 else "ERROR"
    # S8.4 / I-38 (Q32 option a, scoped to quiet). ``--output-mode quiet``
    # exists so ``fa run --task ... > result.txt`` yields a parseable artifact
    # — the contract ``QuietRenderer``'s docstring already promised and the CLI
    # did not keep: measured 34 bytes of status line on stdout under quiet, and
    # 102 bytes across a three-stage ``fa workflow``.
    #
    # Scoped deliberately. ``quiet`` is a console-verbosity control, so only it
    # moves the human status line to stderr; default ``console`` output is
    # byte-for-byte unchanged. Durable side effects (session.db rows, workflow
    # artifacts, the global_history row) are identical in both modes — quiet
    # never changes what is processed, only what is displayed.
    #
    # ``final_text`` stays on stdout in BOTH modes: it is the payload.
    status_stream = sys.stderr if output_mode == "quiet" else sys.stdout
    print(f"{status}: {outcome.stop_reason} (turns={outcome.turns})", file=status_stream)
    if outcome.final_text:
        print(outcome.final_text)
    return outcome.exit_code


def _cmd_routing_check(args: argparse.Namespace) -> int:
    """Lint ``models.yaml`` for cross-role route conflicts + near-miss URLs.

    Static, offline check (no Docker, no network, no running proxy): re-runs
    the exact route-conflict validation ``fa egress-proxy`` performs at
    container-start time, plus a same-provider near-miss base_url heuristic
    (catches a lone typo — e.g. '/v1' vs '/vl' — that a conflict check alone
    cannot see when there is no second entry to disagree with). Intended to
    run as a pre-build/pre-deploy gate: it fails in well under a second,
    before a Docker image build or a container crash-loop would otherwise
    surface the same problem.
    """
    config_path = args.config.expanduser().resolve()
    print(f"fa routing-check: {config_path}")

    # A gate that cannot read its input must FAIL, not pass (S10c.1 / I-40).
    #
    # ``load_models_config_from_path`` returns an EMPTY config for a missing
    # file by documented policy ("caller decides if absence is fatal",
    # config.py:323-326) — correct for `fa run`, wrong here. Without this
    # check a typo in the path fell through to the "no roles declared" branch
    # below and returned 0. `scripts/fa-clean-rebuild.sh:471` uses this exit
    # code as a pre-build deploy gate, so it logged "Routing lint: OK" and
    # proceeded to build having validated nothing.
    #
    # Absence is checked here, in the caller, precisely BECAUSE the loader's
    # policy is deliberate; a *parse* failure is different and is raised as
    # ConfigurationError by the loader itself.
    if not config_path.is_file():
        print(f"ERROR: config not found: {config_path}")
        return 2

    try:
        models = load_models_config_from_path(config_path, require_api_keys=False)
    except (ConfigurationError, EvalFamilyConflictError, OSError) as exc:
        print(f"ERROR: models config error: {exc}")
        return 2

    # Reached only when the file EXISTS and parsed: an empty-but-present
    # config is a legitimately clean state, so it stays exit 0.
    if not models.roles:
        print("WARNING: no roles declared; nothing to check.")
        return 0

    findings = lint_models_config(models)
    if not findings:
        print(f"fa routing-check: OK ({len(models.roles)} role(s) checked, no issues found)")
        return 0

    print("fa routing-check: ISSUES FOUND")
    for finding in findings:
        print(f"- [{finding.category}] {finding.message}")
    return 1


def _selfcheck_proxy_preflight(proxy_url: str) -> tuple[str, str | None]:
    """Validate proxy configuration before any network call. Returns ``(token, error)``.

    Extracted from ``_cmd_selfcheck`` (S10b.5). ``error`` is ``None`` when the
    local configuration is usable; otherwise it is the operator-facing message
    and the caller exits **2**.

    **All three failures here are exit 2 ("your configuration is wrong"), which
    is deliberately distinct from the exit 1 the probing phase returns ("the
    proxy is wrong").** Keeping the phases separate is what keeps that
    distinction honest: nothing in this function can produce a 1.

    The token check runs *before* the first request on purpose — issuing an
    unauthenticated call and reporting the resulting 401/403 would blame the
    proxy for a local omission.
    """
    if not proxy_url:
        return "", (
            "ERROR: FA_EGRESS_PROXY_URL is not set; the agent is not in proxy mode.\n"
            "Hint: in Docker deployment it should point to http://fa-egress-proxy:8080."
        )

    proxy_url_error = _validate_proxy_url(proxy_url)
    if proxy_url_error:
        return "", f"ERROR: invalid FA_EGRESS_PROXY_URL: {proxy_url_error}"

    proxy_token = _resolve_proxy_token()
    if not proxy_token:
        return "", ("ERROR: proxy token is missing; set FA_PROXY_TOKEN_FILE or mount /run/secrets/fa_proxy_token.")

    return proxy_token, None


def _selfcheck_fetch_proxy_routes(proxy_url: str, proxy_token: str) -> dict[str, bool] | None:
    """Probe ``/healthz`` and ``/routes``; return the route table, or ``None`` on failure.

    Extracted from ``_cmd_selfcheck`` (S10b.5). Prints its own progress and
    diagnostics — the output *is* the product of a diagnostic command — and
    returns ``None`` to mean "the caller should exit 1".

    **Every failure branch has distinct wording, and that is load-bearing.**
    They all produce exit 1, so the message is the only thing telling an
    operator what to do next: ``403`` means reconcile the token files, a non-200
    means read the proxy logs, a malformed body means the proxy is returning
    something unexpected. S10a's mutation sweep proved that asserting only the
    exit code lets a deleted branch fall through to the next one undetected,
    so each is pinned by its own string in the S10b.5 parity cells.

    The ``/routes`` body is untrusted input from across a process boundary: it
    is decoded, JSON-parsed and shape-validated defensively, and any failure
    becomes a diagnostic rather than a traceback.
    """
    health_url = _proxy_endpoint(proxy_url, "/healthz")
    try:
        health_status, _health_body = _selfcheck_http_get(health_url)
    except _SelfcheckNetworkError as exc:
        print(f"ERROR: proxy is not reachable at {health_url}: {exc}")
        print("Hint: check `docker compose logs fa-egress-proxy` and container health.")
        return None
    if health_status != 200:
        print(f"ERROR: proxy /healthz returned HTTP {health_status}.")
        print("Hint: check `docker compose logs fa-egress-proxy`.")
        return None
    print("OK: proxy /healthz reachable")

    routes_url = _proxy_endpoint(proxy_url, "/routes")
    try:
        routes_status, routes_body = _selfcheck_http_get(routes_url, headers={_PROXY_TOKEN_HEADER: proxy_token})
    except _SelfcheckNetworkError as exc:
        print(f"ERROR: proxy /routes is not reachable at {routes_url}: {exc}")
        print("Hint: check `docker compose logs fa-egress-proxy`.")
        return None
    if routes_status == 403:
        print("ERROR: proxy /routes rejected the fa→proxy token (HTTP 403).")
        print("Hint: verify FA_PROXY_TOKEN_FILE and /run/secrets/fa_proxy_token match the proxy.")
        return None
    if routes_status != 200:
        print(f"ERROR: proxy /routes returned HTTP {routes_status}.")
        print("Hint: check `docker compose logs fa-egress-proxy`.")
        return None

    try:
        routes_payload = json.loads(routes_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        print("ERROR: proxy /routes returned non-JSON or malformed JSON.")
        return None
    proxy_routes, payload_error = _selfcheck_parse_routes_payload(routes_payload)
    if payload_error:
        print(f"ERROR: unsafe or malformed proxy /routes payload: {payload_error}")
        return None
    print(f"OK: proxy /routes returned {len(proxy_routes)} route(s)")
    return proxy_routes


def _selfcheck_route_problems(
    expected_routes: Mapping[str, str],
    proxy_routes: Mapping[str, bool],
    *,
    config_path: Path,
    role_name: str,
) -> list[str]:
    """Compare the agent's expected routes against the proxy's table.

    Extracted from ``_cmd_selfcheck`` (S10b.5). Pure: takes two mappings,
    returns the list of human-readable problems. This is the actual purpose of
    ``fa selfcheck``, and being pure makes it directly testable without a proxy.

    Two distinct faults, two distinct remedies — do not merge them:

    * **absent** — the route is in ``models.yaml`` but not in the proxy's
      table, which means the proxy is running an older config and must be
      recreated.
    * **present but keyless** — the proxy knows the route but has no API key
      for it, which means ``fa.env`` is missing an entry.

    The remediation text is part of the contract; an operator follows it
    verbatim.
    """
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
    return problems


def _cmd_selfcheck(args: argparse.Namespace) -> int:
    """Diagnose the fa→egress-proxy→provider routing seam (ADR-12)."""
    proxy_url = _resolve_proxy_url()
    config_path = args.config.expanduser().resolve()
    role_name = str(args.role)

    print("fa selfcheck: egress proxy diagnostics")
    print(f"- proxy: {proxy_url or '<not set>'}")
    print(f"- config: {config_path}")
    print(f"- role: {role_name}")

    proxy_token, preflight_error = _selfcheck_proxy_preflight(proxy_url)
    if preflight_error is not None:
        print(preflight_error)
        return 2

    proxy_routes = _selfcheck_fetch_proxy_routes(proxy_url, proxy_token)
    if proxy_routes is None:
        return 1

    try:
        models = load_models_config_from_path(config_path, require_api_keys=False)
    except (ConfigurationError, EvalFamilyConflictError, OSError) as exc:
        print(f"ERROR: models config error: {exc}")
        return 2

    chain_config = models.roles.get(role_name)
    if chain_config is None:
        print(f"ERROR: role {role_name!r} not found in {config_path}; known: {sorted(models.roles)}")
        return 2

    from fa.egress_proxy.routing import ProxyConfigError

    try:
        expected_routes = _selfcheck_expected_routes(chain_config)
    except ProxyConfigError as exc:
        print(f"ERROR: could not compute agent route names: {exc}")
        return 2

    problems = _selfcheck_route_problems(expected_routes, proxy_routes, config_path=config_path, role_name=role_name)

    if problems:
        print("fa selfcheck: ERROR")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("fa selfcheck: OK")
    print(f"- checked role routes: {len(expected_routes)}")
    return 0


def _cmd_probe(
    args: argparse.Namespace,
    *,
    transport: Transport | None = None,
    secrets: Mapping[str, str] | None = None,
) -> int:
    """Liveness-test the LLM provider chain with a minimal real API call.

    Sends ``{"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}``
    through the full agent→proxy→provider path. No system prompt, no tools, no
    inner loop — pure provider connectivity and key-validity test.

    Cost: ~10 input tokens + 1 output token per chain entry probed.

    ``transport`` / ``secrets`` are optional injection seams (S10a.4), added so
    this command is testable at all: before them it built a live
    ``UrllibTransport`` internally and sat at **2%** coverage. Both default to
    ``None`` and resolve to exactly the previous collaborators, so an operator
    invocation is byte-identical to before.

    This mirrors ``_cmd_run`` (``transport``/``secrets``/``outcome_sink``) and
    ``_cmd_workflow``, which use the same keyword-only, default-to-real idiom
    and are production-used — ``_run_stage`` forwards ``transport=ctx.transport``
    on the real workflow path. Adopting the house pattern rather than inventing
    a second one; the two commands that already had it are also the two
    best-covered in this module.
    """
    config_path = args.config.expanduser().resolve()
    probe_timeout = int(args.timeout)

    proxy_url = _resolve_proxy_url()
    proxy_mode = bool(proxy_url)
    effective_secrets: Mapping[str, str] = (
        secrets if secrets is not None else (SecretStore({}) if proxy_mode else _load_secret_store())
    )

    try:
        models = load_models_config_from_path(config_path, env=effective_secrets, require_api_keys=not proxy_mode)
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

    effective_transport: Transport = transport if transport is not None else UrllibTransport()
    any_failure = False

    for role_name in role_names:
        chain_config = models.roles.get(role_name)
        if chain_config is None:
            print(f"fa probe: role {role_name!r} not found in {config_path}; known: {sorted(models.roles)}")
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
        probed_entries = tuple(replace(entry, timeout_seconds=probe_timeout) for entry in chain_config.chain)
        chain_config = replace(chain_config, chain=probed_entries)

        chain = _build_provider_chain(chain_config, transport=effective_transport, secrets=effective_secrets)

        print(f"\nfa probe: role={role_name} (model={chain_config.name}, family={chain_config.family})")

        request = RequestInfo(
            model_slug=chain_config.name,
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


def _resolve_stats_session_dirs(state_root: Path, selected_session_id: str | None) -> list[Path]:
    """Resolve which session directories ``fa stats`` should read.

    Extracted from ``_discover_stats_sources`` (S10b.4). Returns newest-first
    when scanning, or the single selected session.

    **An empty list and an error are different answers, deliberately.** No
    sessions at all returns ``[]`` (the caller reports "no matching sessions"),
    but an unmigrated ``session-log/`` tree raises ``legacy_trace_unsupported``.
    Collapsing the two would tell an operator holding legacy data that they
    simply have none — pinned by
    ``test_s10b_discover_legacy_layout_is_rejected_explicitly`` and its
    empty-state positive control.

    Read-only by contract: stats must never create a state root, manifest, or
    database, which is why this resolves paths by hand instead of going through
    ``SessionManager``.
    """
    from fa.stats import StatsSourceError

    sessions_root = state_root / "sessions"
    legacy_root = state_root / "session-log"

    if selected_session_id is not None:
        if not _valid_run_id(selected_session_id):
            raise StatsSourceError("invalid_session_id", "session_id must match [A-Za-z0-9_.-]{1,128}")
        session_dir = sessions_root / selected_session_id
        if not (session_dir / "manifest.json").is_file():
            raise StatsSourceError("unknown_session", f"session does not exist: {selected_session_id}")
        return [session_dir]

    if sessions_root.is_dir():
        session_dirs = sorted(
            (path for path in sessions_root.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if session_dirs:
            return session_dirs

    has_legacy = legacy_root.is_dir() and any(
        child.is_dir() and any(child.iterdir()) for child in legacy_root.iterdir()
    )
    if has_legacy:
        raise StatsSourceError(
            "legacy_trace_unsupported",
            "current FA sessions require session.db under sessions/<session-id>; legacy JSONL/DB was not migrated",
        )
    return []


def _validate_session_manifest(session_dir: Path, selected_session_id: str | None) -> tuple[str, Path, Path]:
    """Validate one session manifest; return ``(session_id, db_path, workspace_path)``.

    Extracted from ``_discover_stats_sources`` (S10b.4).

    **Every rejection carries a distinct ``StatsSourceError`` code, and the code
    is the operator contract** — the CLI prints it verbatim
    (``fa stats: source error [<code>]: ...``), so it is what a script greps
    and what a bug report quotes. All of these reach the operator as the same
    exit status, so the code is the *only* thing distinguishing them. Do not
    merge two of them for tidiness; each is pinned by name in
    ``test_s10b_discover_manifest_validation_codes``.

    ``manifest_path_mismatch`` is the security-relevant check: it refuses a
    manifest whose ``session_db_path`` points outside its own session
    directory, which is how a crafted or relocated manifest would redirect
    ``fa stats`` at a different session's database. Both sides are resolved
    before comparison so symlinks and ``..`` cannot slip past.
    """
    from fa.stats import StatsSourceError

    manifest_path = session_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StatsSourceError("manifest_corrupt", f"cannot read {manifest_path}: {exc}") from exc

    if not isinstance(manifest, dict) or manifest.get("status") != "active":
        raise StatsSourceError("manifest_corrupt", f"inactive or malformed manifest: {manifest_path}")

    session_id = manifest.get("session_id")
    if not isinstance(session_id, str) or not _valid_run_id(session_id):
        raise StatsSourceError("manifest_corrupt", f"invalid session_id: {manifest_path}")
    if selected_session_id is not None and session_id != selected_session_id:
        raise StatsSourceError("manifest_identity_mismatch", str(manifest_path))

    db_path = Path(str(manifest.get("session_db_path", ""))).expanduser().resolve()
    if db_path != (session_dir / "session.db").resolve():
        raise StatsSourceError("manifest_path_mismatch", str(manifest_path))

    workspace_path = Path(str(manifest.get("workspace_path", ""))).expanduser().resolve()
    return session_id, db_path, workspace_path


def _discover_stats_sources(
    *,
    state_root: Path,
    selected_session_id: str | None,
    selected_run_id: str | None,
    since_seconds: float | None,
) -> tuple[tuple[str, Path, Path, str], ...]:
    """Discover current-format ``(session, db, workspace, run)`` sources.

    This helper intentionally does not instantiate ``SessionManager``: stats is
    a read command and must not create state roots, manifests, or databases.
    """
    from fa.stats import StatsSourceError

    if selected_run_id is not None and not _valid_run_id(selected_run_id):
        raise StatsSourceError("invalid_run_id", "run_id must match [A-Za-z0-9_.-]{1,128}")
    session_dirs = _resolve_stats_session_dirs(state_root, selected_session_id)
    if not session_dirs:
        return ()

    sources: list[tuple[str, Path, Path, str]] = []
    for session_dir in session_dirs:
        session_id, db_path, workspace_path = _validate_session_manifest(session_dir, selected_session_id)
        try:
            db = SessionDatabase.open_existing(db_path, session_id=session_id)
            run_ids = (selected_run_id,) if selected_run_id is not None else db.list_run_ids()
        except SessionDatabaseError as exc:
            raise StatsSourceError(exc.code, str(exc)) from exc
        if since_seconds is not None and selected_run_id is None:
            if session_dir.stat().st_mtime < time.time() - since_seconds:
                continue
        for run_id in run_ids:
            if db.get_run_binding(run_id) is None:
                continue
            sources.append((session_id, db_path, workspace_path, run_id))
    return tuple(sources)


def _cmd_stats_global_history(args: argparse.Namespace) -> int:
    """Render the ``global_history.db`` projection (``fa stats --global-history``).

    Extracted from ``_cmd_stats`` (S10b.3). This is one of three independent
    renderers the command dispatches between; it reads the cross-run projection
    rather than per-session authority databases.

    **Stream split is the contract, not a detail.** ``--output json`` goes to
    **stdout** so the command composes in a pipeline; the human report goes to
    **stderr** so it never pollutes that stdout. Both directions are pinned by
    ``test_s10b_stats_parity_global_history_{json_goes_to_stdout,console_goes_to_stderr}``
    — an extraction that merged the renderers would still exit 0 and still
    print something.

    **The broad ``except`` is deliberate and stays.** A stats read is a
    diagnostic; any failure must become "exit 1 with a message" rather than a
    traceback. Note this is also why ``--since`` is validated by the CALLER,
    before dispatch: a usage error routed through here would surface as exit 1
    instead of exit 2 (S9.2/F6).
    """
    import time as _time

    try:
        from fa.inner_loop.global_history import GlobalHistoryStore, default_global_history_path

        # S8.8: one definition of the projection path, shared with the
        # writer. Reader and writer previously computed it independently,
        # which is how they came to disagree under FA_STATE_ROOT.
        db_path = default_global_history_path()
        store = GlobalHistoryStore(db_path=db_path)
        rows = store.read_all()
        if not rows:
            print(f"fa stats: no global history found at {db_path}", file=sys.stderr)
            return 1
        # Filter by --run-id if provided
        if getattr(args, "run_id", None):
            run_id = args.run_id
            rows = [r for r in rows if r.get("run_id") == run_id]
            if not rows:
                print(f"fa stats: run {run_id!r} not found in global history", file=sys.stderr)
                return 1
        # Filter by --since if provided (updated_at)
        if getattr(args, "since", None) and not getattr(args, "run_id", None):
            since_s = _parse_since(args.since)
            if since_s is not None:
                cutoff = _time.time() - since_s
                # updated_at is ISO, parse roughly? For simplicity, skip if can't parse
                filtered = []
                for r in rows:
                    try:
                        # Try to parse ISO, if fails keep
                        from datetime import datetime

                        dt = datetime.fromisoformat(r.get("updated_at", "").replace("Z", "+00:00"))
                        if dt.timestamp() >= cutoff:
                            filtered.append(r)
                    except (TypeError, ValueError, AttributeError):
                        filtered.append(r)
                rows = filtered
        if args.output == "json":
            import json as _json

            print(_json.dumps(rows, indent=2, default=str))
            return 0
        # Console rendering for global history
        print(f"\n{'═' * 50}\n📊 Global history: {len(rows)} runs\n{'═' * 50}\n", file=sys.stderr)
        for r in rows[:20]:
            print(
                f"  {r.get('run_id', ''):<20s} {r.get('role', ''):<8s} {r.get('model', ''):<20s} "
                f"{r.get('stop_reason', ''):<20s} turns={r.get('turns', 0)} "
                f"in={r.get('input_tokens', 0)} out={r.get('output_tokens', 0)}",
                file=sys.stderr,
            )
        if len(rows) > 20:
            print(f"  ... and {len(rows) - 20} more", file=sys.stderr)
        return 0
    except Exception as exc:  # CLI must report stats failure, never crash with traceback
        logger.error("fa stats: failed to read global history: %s", exc, exc_info=True)
        print(f"fa stats: failed to read global history: {exc}", file=sys.stderr)
        return 1


def _render_dead_zones(workspace: Path, sessions: list[SessionAnalytics]) -> None:
    """Append the ``--dead-zones`` report (``src/`` files no session touched) to stderr.

    Extracted from ``_cmd_stats`` (S10b.3). Writes nothing when there are no
    dead zones — silence means "full coverage", not "the check did not run".

    Reports to **stderr** and returns ``None`` rather than an exit code: an
    empty result is not an error, and the caller's exit status must not depend
    on it. S10a's mutation sweep found that deleting this whole block survives
    an exit-code-only assertion (0 either way), which is why
    ``test_s10b_stats_parity_dead_zones_report`` asserts the report *text*.
    """
    from fa.stats import find_dead_zones

    dead = find_dead_zones(workspace, sessions)
    if not dead:
        return
    sys.stderr.write(f"\n🔍 Dead zones ({len(dead)} src/ files never accessed):\n")
    for path in dead[:15]:
        sys.stderr.write(f"   {path}\n")
    if len(dead) > 15:
        sys.stderr.write(f"   ... and {len(dead) - 15} more\n")
    sys.stderr.flush()


def _cmd_stats(args: argparse.Namespace) -> int:
    """Analyze session logs — tool usage, file access, tokens, efficiency."""
    from fa.stats import (
        StatsSourceError,
        aggregate_sessions,
        parse_session_db,
        render_aggregate,
        render_session,
        render_session_json,
    )

    # S9.2 / F6 — validate --since ONCE, before either branch consumes it.
    #
    # One guard, not two: the --global-history filter below lives inside a
    # broad ``try/except Exception`` that returns 1, which is the wrong home
    # for a usage check, and two guards is two places to drift. Placing it
    # here also means invalid input is rejected before any DB work.
    #
    # ``getattr`` rather than ``args.since``: the two downstream call sites
    # disagree (one uses getattr, one a bare attribute), and this guard runs
    # ahead of both, so it must tolerate the loosest Namespace a caller builds.
    #
    # The ``run_id`` condition mirrors the existing precedence exactly —
    # --run-id overrides --since, so an unused --since is not validated
    # (S9 plan Q39: deliberate, pinned by test).
    _since_raw = getattr(args, "since", None)
    if _since_raw and not getattr(args, "run_id", None) and _parse_since(_since_raw) is None:
        print(
            f"fa stats: invalid --since value {_since_raw!r}; expected a positive duration like 7d, 24h or 30m",
            file=sys.stderr,
        )
        return 2

    # --global-history: active consumer for global_history.db projection (Slice 9)
    if getattr(args, "global_history", False):
        return _cmd_stats_global_history(args)

    workspace = args.workspace.resolve()
    state_root = fa_state_root()
    since_seconds = _parse_since(args.since) if args.since and not args.run_id else None
    try:
        sources = _discover_stats_sources(
            state_root=state_root,
            selected_session_id=getattr(args, "session_id", None),
            selected_run_id=args.run_id,
            since_seconds=since_seconds,
        )
    except StatsSourceError as exc:
        print(f"fa stats: source error [{exc.code}]: {exc}", file=sys.stderr)
        return 2

    if args.run_id and not sources:
        print(f"fa stats: run {args.run_id!r} not found in current session authorities", file=sys.stderr)
        return 1
    if not sources:
        print("fa stats: no matching sessions found", file=sys.stderr)
        return 1

    sessions = []
    workspaces: list[Path] = []
    for session_id, db_path, workspace_path, run_id in sources:
        try:
            result = parse_session_db(db_path, session_id=session_id, run_id=run_id)
        except StatsSourceError as exc:
            print(f"fa stats: source error [{exc.code}]: {exc}", file=sys.stderr)
            return 2
        if result is not None:
            sessions.append(result)
            workspaces.append(workspace_path)

    if not sessions:
        print("fa stats: no parseable sessions found", file=sys.stderr)
        return 1

    single = bool(args.run_id) and len(sessions) == 1
    if args.output == "json":
        import json as _json

        if single:
            payload: Any = render_session_json(sessions[0])
        else:
            payload = aggregate_sessions(sessions)
            payload["sessions_detail"] = [render_session_json(s) for s in sessions]
        print(_json.dumps(payload, indent=2, default=str))
        return 0

    if single:
        render_session(sessions[0])
    else:
        render_aggregate(sessions)

    if getattr(args, "dead_zones", False):
        _render_dead_zones(workspaces[0] if len(workspaces) == 1 else workspace, sessions)

    return 0


def _parse_since(value: str) -> float | None:
    """Parse ``'7d'`` / ``'24h'`` / ``'30m'`` into a positive number of seconds.

    Returns ``None`` for anything that is not a usable window: no suffix, an
    unknown suffix, non-numeric, empty, **negative**, **zero**, or non-finite.
    Never raises — the caller decides whether ``None`` is a usage error.

    **Why the sign check exists (S9 / F6).** Without it ``-5d`` parsed to
    ``-432000.0``. Both call sites compute ``cutoff = time.time() - since``,
    so a negative window pushed the cutoff into the *future* and filtered out
    every session; the operator saw ``no matching sessions found`` — a wrong
    answer indistinguishable from a legitimately empty result. Zero is
    rejected on the same principle: a zero-width window is never what anyone
    typed on purpose.

    ``float()`` also accepts scientific notation (``1e3h``) and that is
    deliberately kept — it is unusual input, not wrong input.
    """
    value = value.strip().lower()
    try:
        if value.endswith("d"):
            seconds = float(value[:-1]) * 86400
        elif value.endswith("h"):
            seconds = float(value[:-1]) * 3600
        elif value.endswith("m"):
            seconds = float(value[:-1]) * 60
        else:
            return None
    except ValueError:
        return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    return seconds


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
        routes.setdefault(route_name_for(entry.provider, entry.model), entry.api_key_env)
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
            f"fa authoring-check: not a First-Agent workspace (no knowledge/llms.txt at {workspace})",
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
        models = load_models_config_from_path(args.models.expanduser().resolve(), require_api_keys=False)
    except (ConfigurationError, OSError) as exc:
        print(f"fa egress-proxy: models config error: {exc}", file=sys.stderr)
        return 2

    chain_entries = [
        (entry.provider, entry.model, entry.base_url, entry.api_key_env)
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
        body = "".join(line.strip() for line in text.splitlines() if line and not line.startswith("-----"))
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
