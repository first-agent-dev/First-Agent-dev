"""Top-level bash-command gate composing the three sandbox layers.

The gate is the single entry point the inner-loop (when it lands per
BACKLOG M-1) calls before forwarding a bash command to
``subprocess.run``. It does NOT execute anything itself — execution
stays with the inner-loop's run-shell tool — but it produces a
binary allow/deny decision plus a human-readable reason for the
audit log.

Pipeline (in order):

1. ``classifier.classify_command`` assigns a :class:`BashCategory`.
2. If the category is ``READ_ONLY`` → allow immediately. Read-only
   commands cannot mutate state and so do not need validation or
   containment checks.
3. If the category is ``DANGEROUS`` → check whether the command has a
   per-command validator (``rm`` / ``chmod`` are the two that can flip
   from dangerous to allowed under sufficiently narrow scope). For
   ``rm -rf`` etc. the validator is called and its decision wins;
   for ``dd`` / ``pkill`` / ``sudo`` / ``psql`` there is no validator
   and the gate denies.
4. Otherwise (``GIT_WRITE``, ``PACKAGE_INSTALL``, ``GENERAL_WRITE``)
   run ``validators.validate_command`` if a validator exists for the
   head token, then return its decision. ``GENERAL_WRITE`` with no
   matching validator is denied by default — the gate's stance is
   deny-unknown.

The gate is intentionally NOT capability-flag-aware. ADR-6 §Amendment
2026-05-20 (R-21, PR-2) shipped the five capability flags in
``fa.config``; whether the gate's caller actually invokes the gate is
controlled by those flags upstream. Keeping that wiring outside the
gate makes the gate easy to unit-test and lets the flags evolve
without touching the security layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fa.sandbox.classifier import BashCategory, classify_command
from fa.sandbox.secret_paths import command_reads_secret_path
from fa.sandbox.validators import ValidationResult, validate_command

__all__ = [
    "BashGateDecision",
    "evaluate_bash",
]


@dataclass(frozen=True)
class BashGateDecision:
    """Outcome of an ``evaluate_bash`` call.

    ``allow`` — the binary decision.
    ``category`` — the classifier's output (always populated, even
    when ``allow`` is False, so the audit log preserves *why* the
    command was dangerous).
    ``reason`` — human-readable explanation. For denials, contains the
    validator's reason where available; for allows, the empty default
    ``"ok"`` or the validator's success message.
    ``validator_result`` — the underlying :class:`ValidationResult`
    when a per-command validator ran; ``None`` when the decision was
    made purely from category routing.
    """

    allow: bool
    category: BashCategory
    reason: str
    validator_result: ValidationResult | None = None


def evaluate_bash(
    command: str,
    *,
    workspace_root: Path,
    allow_package_install: bool = False,
    allow_general_write: bool = True,
    secret_path_extra: tuple[str, ...] = (),
) -> BashGateDecision:
    """Evaluate ``command`` against the three-layer gate.

    ``workspace_root`` is the absolute path the path-containment layer
    treats as the trust boundary. The two ``allow_*`` flags are
    deliberately separate from the ADR-6 §Amendment 2026-05-20 R-21
    capability flags (those live in :mod:`fa.config`) — they let
    individual callers tighten the gate further without flipping a
    global flag. Both default to safe-by-default values:

    - ``allow_package_install=False`` mirrors Aperant's per-tool
      decision: package installs change the runtime environment and
      should require an explicit caller-side opt-in.
    - ``allow_general_write=True`` is the historical FA stance — once
      the path-containment + ADR-6 §Policy file accept a path, write
      operations like ``touch`` / ``mkdir`` / ``mv`` / ``cp`` inside
      the workspace are fine.

    The function is pure and side-effect-free (the path-containment
    syscall is observation-only — ``stat`` / ``realpath`` equivalent
    via ``Path.resolve()``).
    """
    category = classify_command(command)

    # Secret-isolation tripwire (ADR-12): deny reads of known secret paths
    # BEFORE the READ_ONLY fast-allow. This is defense-in-depth + the runtime
    # guard for the deploy key (LLM keys live in the egress proxy, not here).
    # Fail-closed: an unparseable command that references a secret prefix is
    # also denied (see ``command_reads_secret_path``).
    if command_reads_secret_path(command, extra_prefixes=secret_path_extra):
        return BashGateDecision(
            allow=False,
            category=category,
            reason="read of secret path blocked (ADR-12 secret isolation)",
        )

    if category is BashCategory.READ_ONLY:
        return BashGateDecision(
            allow=True,
            category=category,
            reason="read-only command",
        )

    validator_result = validate_command(command, workspace_root=workspace_root)

    if category is BashCategory.DANGEROUS:
        if validator_result is not None:
            return BashGateDecision(
                allow=validator_result.allow,
                category=category,
                reason=validator_result.reason,
                validator_result=validator_result,
            )
        return BashGateDecision(
            allow=False,
            category=category,
            reason="dangerous command with no per-command validator",
        )

    if category is BashCategory.PACKAGE_INSTALL:
        if not allow_package_install:
            return BashGateDecision(
                allow=False,
                category=category,
                reason=("package-install denied: caller did not pass allow_package_install=True"),
            )
        return BashGateDecision(
            allow=True,
            category=category,
            reason="package-install explicitly allowed by caller",
        )

    if category is BashCategory.GIT_WRITE:
        if validator_result is None:
            # `git` always matches the validator; this branch is a
            # defensive fall-through, never triggered in practice.
            return BashGateDecision(
                allow=False,
                category=category,
                reason="git-write command but no git validator output",
            )
        return BashGateDecision(
            allow=validator_result.allow,
            category=category,
            reason=validator_result.reason,
            validator_result=validator_result,
        )

    # GENERAL_WRITE: per-command validators may apply to a small set;
    # otherwise the caller flag is authoritative.
    if validator_result is not None:
        return BashGateDecision(
            allow=validator_result.allow,
            category=category,
            reason=validator_result.reason,
            validator_result=validator_result,
        )

    if not allow_general_write:
        return BashGateDecision(
            allow=False,
            category=category,
            reason=("general-write denied: caller did not pass allow_general_write=True"),
        )
    return BashGateDecision(
        allow=True,
        category=category,
        reason="general-write allowed by caller",
    )
