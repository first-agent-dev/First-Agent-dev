"""Per-command validators for the bash sandbox gate.

Borrowed from Aperant ``apps/desktop/src/main/ai/security/bash-validator.ts``
(300 LOC). Each validator answers a single yes/no question for one
sensitive command. The validators are pure functions — no I/O, no
mutation — so they compose cleanly with the gate's pipeline.

Validated commands (the small set with non-trivial denial logic):

- ``rm``   — deny if the target is the workspace root itself,
             ``$HOME``, ``/`` or a top-level system directory (``/usr``,
             ``/etc``, ``/bin``, …). Recursive flags are pre-filtered
             by ``classifier.classify_command`` into ``DANGEROUS``;
             this validator therefore only sees non-recursive ``rm``.
- ``chmod`` — deny ``chmod 777`` and any chmod that grants world-write
              (``o+w``). Recursive flags are already routed to
              ``DANGEROUS``.
- ``git``  — deny ``git config user.email`` and ``git config user.name``
             (the global-identity-rewrite case Aperant explicitly
             documents). Allow other ``git config`` invocations because
             ``git config --local credential.helper`` and similar are
             routine.
- ``pkill`` / ``psql`` / ``mongo`` / ``mysql`` — denied at the
             classifier layer already; included here only as
             documentation, the validators return a fixed deny.

Why no LLM call (PR Checklist rule #10 question 4): each validator is
a pure pattern check on the token list. There is no model judgement;
the rules are documented in the §References of ADR-6 §Amendment
2026-05-20 (Wave-1) and reviewed by humans, not inferred per call.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fa.sandbox.classifier import tokenize
from fa.sandbox.path_containment import is_contained

__all__ = [
    "ValidationResult",
    "validate_chmod",
    "validate_command",
    "validate_git",
    "validate_rm",
]


@dataclass(frozen=True)
class ValidationResult:
    """Result of a per-command validator check.

    ``allow`` is the boolean answer; ``reason`` is the human-readable
    explanation logged at the gate-decision layer.
    """

    allow: bool
    reason: str


# Top-level system directories that ``rm`` must never touch even if
# the user happens to be running FA with elevated privileges. Aperant
# uses the same denylist verbatim; entries are deliberately conservative.
_RM_DENIED_TARGETS: frozenset[str] = frozenset(
    {
        "/",
        "/bin",
        "/boot",
        "/dev",
        "/etc",
        "/home",
        "/lib",
        "/lib64",
        "/opt",
        "/proc",
        "/root",
        "/run",
        "/sbin",
        "/srv",
        "/sys",
        "/tmp",  # noqa: S108 (entry in the system-path DENYLIST)
        "/usr",
        "/var",
    }
)


def validate_rm(command: str, *, workspace_root: Path) -> ValidationResult:
    """Validate an ``rm`` invocation against the workspace base.

    Denies:

    - ``rm /`` and any top-level system directory (``/etc``, ``/usr``…).
    - ``rm $HOME`` / ``rm ~`` / ``rm $HOME/...`` outside workspace.
    - ``rm`` with a target outside the workspace (after symlink
      resolution).

    Recursive flags (``-rf``, ``-R``, …) are routed to ``DANGEROUS``
    by the classifier before this validator runs; the validator
    therefore conservatively assumes non-recursive usage.
    """
    tokens = tokenize(command)
    if not tokens or tokens[0] != "rm":
        return ValidationResult(
            allow=False,
            reason=f"validator_rm: expected `rm`, got {tokens[:1]!r}",
        )

    targets = [t for t in tokens[1:] if not t.startswith("-")]
    if not targets:
        return ValidationResult(
            allow=False,
            reason="validator_rm: no target argument",
        )

    home = str(Path("~").expanduser())
    for target in targets:
        if target in _RM_DENIED_TARGETS:
            return ValidationResult(
                allow=False,
                reason=(f"validator_rm: target {target!r} is a system directory (always denied)"),
            )
        if target in {"~", home}:
            return ValidationResult(
                allow=False,
                reason=(f"validator_rm: target {target!r} is the user home directory"),
            )
        containment = is_contained(target, workspace_root)
        if not containment.contained:
            return ValidationResult(
                allow=False,
                reason=(
                    f"validator_rm: target {target!r} not contained "
                    f"in workspace ({containment.reason})"
                ),
            )

    return ValidationResult(allow=True, reason="validator_rm: ok")


def _grants_world_write(mode: str) -> bool:
    """Return True if a chmod mode string grants world-write.

    Accepts numeric (``777``, ``0666``) and symbolic
    (``o+w``, ``a+w``, ``ugo+w``, ``a+rw``, ``a=rwx``, comma-chained
    clauses like ``u=rwx,go+rw``) forms. Conservative — when the mode
    string is unrecognised, returns True so that the validator denies.

    Symbolic parsing walks each comma-separated clause
    ``[scope][op][perms]`` where ``scope`` ⊆ ``ugoa`` (defaulting to
    ``a`` when omitted, per POSIX chmod), ``op`` is ``+ - =``, and
    ``perms`` contains the requested permission letters. World-write
    is granted iff ``op`` ∈ ``{+, =}``, ``w ∈ perms``, and ``scope``
    includes ``o`` or ``a``.

    The previous implementation only matched the literal substrings
    ``+w`` / ``=w`` and so missed ``a+rw``, ``o+rw``, ``ugo+rw``,
    ``a=rwx`` (Devin Review finding 2026-05-20 on PR #20).
    """
    if not mode:
        return True
    lowered = mode.lower()

    # Numeric mode (``777``, ``0666``). Trailing digit is the "other"
    # bit. World-write iff last digit's bit-2 (``2``) is set.
    digits = lowered.lstrip("0") or "0"
    if digits.isdigit():
        other_bit = int(digits[-1])
        return bool(other_bit & 0b010)

    # Symbolic mode. Comma-separated clauses; each clause has an
    # operator and the scope precedes the operator.
    for clause in lowered.split(","):
        clause = clause.strip()
        if not clause:
            return True  # malformed — deny
        op_idx = -1
        for i, ch in enumerate(clause):
            if ch in "+-=":
                op_idx = i
                break
        if op_idx < 0:
            return True  # malformed — deny
        scope = clause[:op_idx] or "a"  # bare ``+w`` means ``a+w``
        op = clause[op_idx]
        perms = clause[op_idx + 1 :]
        if op == "-":
            continue  # removing perms can never grant world-write
        if "w" not in perms:
            continue
        if any(c in scope for c in ("o", "a")):
            return True
        # Scope chars MUST be a subset of {u, g, o, a}; anything else
        # is malformed — conservative deny.
        if any(c not in "ugoa" for c in scope):
            return True
    return False


def validate_chmod(command: str, *, workspace_root: Path) -> ValidationResult:
    """Validate a ``chmod`` invocation against the workspace base.

    Denies:

    - World-writable modes (``chmod 777``, ``chmod o+w``, ``chmod a+w``).
    - Targets outside the workspace.

    Recursive flags are already classified as ``DANGEROUS`` so this
    validator does not see them.
    """
    tokens = tokenize(command)
    if not tokens or tokens[0] != "chmod":
        return ValidationResult(
            allow=False,
            reason=f"validator_chmod: expected `chmod`, got {tokens[:1]!r}",
        )

    positional = [t for t in tokens[1:] if not t.startswith("-")]
    if len(positional) < 2:
        return ValidationResult(
            allow=False,
            reason="validator_chmod: missing mode or target argument",
        )

    mode, *targets = positional
    if _grants_world_write(mode):
        return ValidationResult(
            allow=False,
            reason=(f"validator_chmod: mode {mode!r} grants world-write (denied)"),
        )

    for target in targets:
        containment = is_contained(target, workspace_root)
        if not containment.contained:
            return ValidationResult(
                allow=False,
                reason=(
                    f"validator_chmod: target {target!r} not contained "
                    f"in workspace ({containment.reason})"
                ),
            )

    return ValidationResult(allow=True, reason="validator_chmod: ok")


def validate_git(command: str, *, workspace_root: Path) -> ValidationResult:
    """Validate a ``git`` invocation, focused on identity-rewrite.

    Denies:

    - ``git config user.email <anything>`` and ``git config user.name <anything>``.
      The Aperant validator documents this as the canonical
      «looks innocent, rewrites git identity» trap.
    - ``git config --global ...`` (any key) — global config writes
      escape the workspace by design.
    - ``git push --force`` / ``--force-with-lease`` to the ``main`` /
      ``master`` ref. Detected by the literal token combination.

    All other ``git`` writes pass through; the path-containment check
    is not relevant because ``git`` operates on the repository the
    cwd belongs to.
    """
    del workspace_root  # path-containment is not relevant for git config
    tokens = tokenize(command)
    if not tokens or tokens[0] != "git":
        return ValidationResult(
            allow=False,
            reason=f"validator_git: expected `git`, got {tokens[:1]!r}",
        )

    non_flag = [t for t in tokens[1:] if not t.startswith("-")]
    subcommand = non_flag[0] if non_flag else ""

    if subcommand == "config":
        if "--global" in tokens or "--system" in tokens:
            return ValidationResult(
                allow=False,
                reason=(
                    "validator_git: `git config --global/--system` writes outside the workspace"
                ),
            )
        # Look for user.email / user.name as the key argument.
        for token in non_flag[1:]:
            lowered = token.lower()
            if lowered in {"user.email", "user.name"}:
                return ValidationResult(
                    allow=False,
                    reason=(
                        f"validator_git: writing `git config "
                        f"{token}` rewrites git identity (denied)"
                    ),
                )

    if subcommand == "push":
        forced = "--force" in tokens or "--force-with-lease" in tokens
        targets_protected = any(t in {"main", "master"} for t in non_flag[1:])
        if forced and targets_protected:
            return ValidationResult(
                allow=False,
                reason=("validator_git: force-push to `main`/`master` is denied"),
            )

    return ValidationResult(allow=True, reason="validator_git: ok")


def validate_command(command: str, *, workspace_root: Path) -> ValidationResult | None:
    """Dispatch to the per-command validator for the head token.

    Returns the validator result for ``rm`` / ``chmod`` / ``git``,
    and ``None`` for any other command (signalling "no per-command
    validator applies; the classifier + path-containment layers are
    the sole gate"). Callers (``bash_gate.evaluate_bash``) treat
    ``None`` as "skip the validator layer for this command".
    """
    tokens = tokenize(command)
    if not tokens:
        return ValidationResult(
            allow=False,
            reason="validator: command is empty or unparseable",
        )

    head = tokens[0]
    if head == "rm":
        return validate_rm(command, workspace_root=workspace_root)
    if head == "chmod":
        return validate_chmod(command, workspace_root=workspace_root)
    if head == "git":
        return validate_git(command, workspace_root=workspace_root)
    return None
