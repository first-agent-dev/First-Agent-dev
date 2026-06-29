#!/usr/bin/env python3
"""Host layout + routing drift advisory for First-Agent deploys.

Read-only diagnostic. Designed for operators who want a quick, high-signal view
of host-side clutter / migration leftovers without changing anything.

Checks:
- canonical routing file presence
- legacy routing file presence
- redundant host scripts dir presence
- ambiguous nested state/state path presence
- shallow advisory drift between the checked-in example and deployed routing file

Exit codes:
- 0: audit completed (warnings may still be present)
- 2: fatal usage/runtime error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_FA_DIR = Path("/srv/first-agent")
DEFAULT_REPO_DIR = Path("/srv/first-agent/repo/First-Agent-dev")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _print_status(label: str, status: str, detail: str = "") -> None:
    line = f"[{status}] {label}"
    if detail:
        line += f": {detail}"
    print(line)


def _collect_top_level_roles(text: str) -> set[str]:
    roles: set[str] = set()
    for raw in text.splitlines():
        if not raw or raw.startswith(("#", " ", "\t")):
            continue
        if raw.rstrip().endswith(":"):
            roles.add(raw.split(":", 1)[0].strip())
    return roles


def _contains_deprecated_markers(text: str) -> list[str]:
    markers = [
        "httpx_retries",
        "proxy/models.yaml",
        "state/models.yaml",
        "~/.fa/models.yaml.example",
    ]
    return [m for m in markers if m in text]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Audit First-Agent host layout and routing drift")
    parser.add_argument("--fa-dir", type=Path, default=DEFAULT_FA_DIR)
    parser.add_argument("--repo-dir", type=Path, default=DEFAULT_REPO_DIR)
    args = parser.parse_args(argv)

    fa_dir = args.fa_dir
    repo_dir = args.repo_dir

    routing = fa_dir / "routing" / "models.yaml"
    legacy_state = fa_dir / "state" / "models.yaml"
    legacy_proxy = fa_dir / "proxy" / "models.yaml"
    host_scripts = fa_dir / "scripts"
    nested_state = fa_dir / "state" / "state"
    sessions = fa_dir / "sessions"
    state = fa_dir / "state"
    example = repo_dir / "knowledge" / "templates" / "models.yaml.example"

    print("First-Agent host layout audit")
    print(f"FA dir:   {fa_dir}")
    print(f"Repo dir: {repo_dir}")
    print()

    _print_status("routing/models.yaml", "OK" if routing.exists() else "WARN", str(routing))
    _print_status(
        "legacy state/models.yaml",
        "WARN" if legacy_state.exists() else "OK",
        str(legacy_state),
    )
    _print_status(
        "legacy proxy/models.yaml",
        "WARN" if legacy_proxy.exists() else "OK",
        str(legacy_proxy),
    )
    if host_scripts.exists():
        entries = (
            sorted(p.name for p in host_scripts.iterdir())
            if host_scripts.is_dir()
            else ["<not-a-dir>"]
        )
        _print_status("host scripts dir", "WARN", f"{host_scripts} -> {entries}")
    else:
        _print_status("host scripts dir", "OK", f"absent ({host_scripts})")
    _print_status(
        "nested /state/state",
        "WARN" if nested_state.exists() else "OK",
        str(nested_state),
    )
    _print_status("sessions dir", "OK" if sessions.exists() else "WARN", str(sessions))
    _print_status("state dir", "OK" if state.exists() else "WARN", str(state))
    _print_status("example models template", "OK" if example.exists() else "WARN", str(example))

    print()
    print("Routing drift advisory")
    if not example.exists():
        _print_status("example template", "WARN", "checked-in template missing; cannot compare")
        return 0
    if not routing.exists():
        _print_status("deployed routing", "WARN", "canonical routing file missing")
        return 0

    example_text = _read_text(example)
    routing_text = _read_text(routing)
    example_roles = _collect_top_level_roles(example_text)
    routing_roles = _collect_top_level_roles(routing_text)

    missing_roles = sorted(
        role
        for role in ("planner", "coder", "eval")
        if role in example_roles and role not in routing_roles
    )
    if missing_roles:
        _print_status(
            "roles", "WARN", f"deployed routing is missing example roles: {missing_roles}"
        )
    else:
        _print_status("roles", "OK", f"deployed roles: {sorted(routing_roles)}")

    deprecated = _contains_deprecated_markers(routing_text)
    if deprecated:
        _print_status("deprecated markers", "WARN", ", ".join(deprecated))
    else:
        _print_status("deprecated markers", "OK")

    expected_optional = ("timeout_seconds", "cooldown_seconds", "transport_retries")
    missing_optional = [name for name in expected_optional if name not in routing_text]
    if missing_optional:
        _print_status(
            "optional routing keys",
            "WARN",
            f"template documents keys absent from deployed file: {missing_optional}",
        )
    else:
        _print_status("optional routing keys", "OK")

    if routing_text == example_text:
        _print_status(
            "template drift", "OK", "deployed routing matches checked-in example exactly"
        )
    else:
        _print_status(
            "template drift",
            "WARN",
            "deployed routing differs from checked-in example (manual review advised)",
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
