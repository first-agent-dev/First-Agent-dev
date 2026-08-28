"""E3 efficiency metrics — read amplification (S5) and full ACRR (S8, CT11).

Two metrics live here, deliberately kept side by side because they answer
different questions and fail in different ways.

``compute_read_amplification`` (S5)
    How many distinct files a run READ per distinct file it CHANGED. Oracle-free,
    works on failed runs, and is the same signal the S7 tripwire watches live.

``compute_cost`` / ``compute_cost_floor`` / ``compute_acrr`` (S8)
    The paper's actual cost model. ``ACRR = (C_act - C_min) / C_min`` where
    ``C = alpha*T_lat + beta*N_tok + gamma*N_tool + delta*N_file`` (E3 Eq. 1, Eq. 3).

Why ``files_changed == 0`` returns ``None`` rather than a number
---------------------------------------------------------------
The obvious implementation divides by ``max(files_changed, 1)``. That makes the
metric's most pathological input — read ten files, change nothing, i.e. pure
unproductive exploration — numerically IDENTICAL to a healthy run that read ten
files and changed one. The one condition this metric exists to surface would be
the one condition it cannot express, so the sentinel is unfalsifiable.

``None`` keeps "undefined ratio" distinguishable from "ratio of 10" and forces
the display layer to say so out loud ("n/a (no files changed)").

Why the floor EXCLUDES latency
------------------------------
Wall-clock time depends on the machine, the provider and the weather. A floor
that moved with it would not be a floor. E3 does exactly this in LLM-Case §7.7,
omitting measured latency so that ``C_min`` stays deterministic. ``alpha`` therefore
exists in :class:`CostWeights` and is applied by :func:`compute_cost`, but
:func:`compute_cost_floor` never uses it.

What ACRR does NOT measure
--------------------------
The floor is derived from the run's OWN change-set, which makes it
**self-referential**: a run that confidently changed the WRONG three files gets
a flattering score, because those three files define its own floor. ACRR
measures redundancy, never correctness. It is an efficiency metric sitting on
top of an assumption of success, which is also why the calibration view shows
successful runs only — a cheap failure is not an efficiency.

Weight derivation (measured 2026-08-27, this repo)
--------------------------------------------------
The paper's defaults ``(1.0, 0.02, 0.5, 1.5)`` do not transfer. Measured on real
change-sets from S5 and S7, they put the token axis at 52-92% of C and the file
axis at **0.43-2.17%**, numerically erasing the very axis E3 calls "the canonical
unit of redundancy".

The fix is not taste, it is an anchor. One median source file in this repo is
7234 bytes ~ 1808 tokens (measured across 155 ``src/*.py`` files). Holding the
paper's per-file weight ``delta = 1.5`` and requiring that a median file's TOKEN cost
come to half its FILE cost gives ``beta = 0.5*delta/1808 = 0.000415``. ``gamma = 0.1`` keeps
a tool call cheap beside a file. Under these, the floor's axis shares land at
file 9-59% / tokens 29-89% across one-file, two-file and five-file change-sets:
every axis stays material, neither dominates everywhere.

Replicating E3 §7.5 on our own numbers: over 4000 random weightings spanning
beta in [1e-5,1e-1], gamma in [1e-2,10], delta in [0.1,16], a wasteful run scored worse than a lean
one in **4000/4000 = 100%** of draws. The ORDERING is what is robust; the exact
constants are not sacred, which is why they are configurable rather than inlined.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BYTES_PER_TOKEN",
    "DEFAULT_WEIGHTS",
    "CostWeights",
    "compute_acrr",
    "compute_cost",
    "compute_cost_floor",
    "compute_read_amplification",
]

# Bytes-per-token divisor for the floor's token axis. A deliberate estimate, not
# a tokenizer: the floor must be reproducible from a file on disk without
# importing a model-specific vocabulary, and ~4 bytes/token is the standard
# rule of thumb for source text. Named so the assumption is visible and
# adjustable rather than buried as a literal `/ 4`.
BYTES_PER_TOKEN = 4


@dataclass(frozen=True)
class CostWeights:
    """Weights for E3 Eq. 1: ``C = alpha*T_lat + beta*N_tok + gamma*N_tool + delta*N_file``.

    Frozen because a cost model that can be mutated after a comparison has
    started is not a cost model. Construct a new instance to reweigh.

    Attributes:
        alpha: Per second of wall-clock latency. Applied by :func:`compute_cost`
            and deliberately UNUSED by :func:`compute_cost_floor`.
        beta: Per token.
        gamma: Per tool call.
        delta: Per file touched — the paper's "canonical unit of redundancy".
    """

    alpha: float = 1.0
    beta: float = 0.000415
    gamma: float = 0.1
    delta: float = 1.5


DEFAULT_WEIGHTS = CostWeights()


def compute_read_amplification(files_read: int, files_changed: int) -> float | None:
    """Return distinct files read per distinct file changed.

    Renamed from ``compute_acrr_proxy`` in S8: it was never an approximation of
    ACRR, it is a different and independently useful signal. Unlike ACRR it
    needs no floor, so it survives failed runs and is cheap enough to evaluate
    per-turn — which is exactly what the S7 tripwire does.

    Args:
        files_read: Count of DISTINCT paths read during the run.
        files_changed: Count of DISTINCT paths written or edited.

    Returns:
        ``files_read / files_changed``, or ``None`` when ``files_changed`` is
        zero — the ratio is genuinely undefined there, not infinite and not
        equal to ``files_read``.

    Raises:
        ValueError: If either count is negative. A count of files cannot be
            below zero, so a negative here means the caller's accounting is
            broken; failing loudly beats propagating a nonsense ratio into the
            projection where it would be read as a real measurement.

    Examples:
        >>> compute_read_amplification(5, 5)
        1.0
        >>> compute_read_amplification(20, 2)
        10.0
        >>> compute_read_amplification(10, 0) is None
        True
    """
    if files_read < 0 or files_changed < 0:
        raise ValueError(f"file counts cannot be negative (files_read={files_read}, files_changed={files_changed})")
    if files_changed == 0:
        return None
    return files_read / files_changed


def compute_cost(
    latency_s: float,
    tokens: int,
    tool_calls: int,
    files: int,
    *,
    weights: CostWeights = DEFAULT_WEIGHTS,
) -> float:
    """Return E3 Eq. 1 cost: ``alpha*T_lat + beta*N_tok + gamma*N_tool + delta*N_file``.

    Args:
        latency_s: Wall-clock seconds.
        tokens: Token count (input + output, per the caller's convention).
        tool_calls: Number of tool invocations.
        files: Number of distinct files touched.
        weights: Coefficients; see :class:`CostWeights`.

    Returns:
        The weighted sum. All four axes contribute; none is special-cased.

    Raises:
        ValueError: If any input is negative, matching
            :func:`compute_read_amplification`. A negative axis would silently
            subtract from cost and could even produce a negative C, which would
            then invert the sign of every ACRR computed against it.

    Examples:
        >>> compute_cost(0.0, 0, 0, 1, weights=CostWeights(0.0, 0.0, 0.0, 1.5))
        1.5
    """
    if latency_s < 0 or tokens < 0 or tool_calls < 0 or files < 0:
        raise ValueError(
            "cost inputs cannot be negative "
            f"(latency_s={latency_s}, tokens={tokens}, tool_calls={tool_calls}, files={files})"
        )
    return weights.alpha * latency_s + weights.beta * tokens + weights.gamma * tool_calls + weights.delta * files


def _resolve_within(workspace: Path, raw_path: str) -> Path | None:
    """Resolve ``raw_path`` against ``workspace``, or return ``None``.

    Recorded tool params are whatever the model passed, so a path may be
    absolute or workspace-relative (``fs_read_file`` normalises via
    ``resolve_workspace_path`` at call time, but the EventLog keeps the raw
    argument). Both must resolve to the same place here.

    Returns ``None`` — never raises — when the path escapes the workspace, does
    not exist, or is not a regular file. An export must not crash a session, and
    must never stat a path outside the root just because a run recorded one.
    """
    try:
        root = workspace.resolve()
        candidate = Path(raw_path)
        resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    except (OSError, ValueError, RuntimeError):
        return None
    if resolved != root and root not in resolved.parents:
        return None
    try:
        if not resolved.is_file():
            return None
    except OSError:
        return None
    return resolved


def compute_cost_floor(
    changed_paths: list[str] | tuple[str, ...],
    workspace: Path | str,
    output_tokens: int,
    *,
    weights: CostWeights = DEFAULT_WEIGHTS,
) -> float:
    """Return the minimum plausible cost of producing this run's change-set.

    The floor answers: *what would this exact set of edits have cost a run that
    wasted nothing?* Each axis is derived, not guessed:

    - **files** — the count of distinct changed paths. Irreducible: you cannot
      change a file without touching it.
    - **tokens** — each changed file's on-disk size divided by
      :data:`BYTES_PER_TOKEN`, plus the run's own ``output_tokens``. Reading a
      file you are about to edit is not redundancy, and the edit itself had to
      be emitted.
    - **tools** — ``2`` per changed file (one read, one write) plus ``1``
      verification call. The cheapest honest edit loop.
    - **latency** — EXCLUDED. See the module docstring.

    Args:
        changed_paths: Distinct paths the run changed. Duplicates are collapsed
            so a path recorded twice cannot inflate its own floor.
        workspace: Root that relative paths resolve against, and the boundary
            outside which nothing is statted.
        output_tokens: Tokens the run emitted.
        weights: Coefficients; see :class:`CostWeights`.

    Returns:
        The floor cost. A path that is missing, deleted, or outside the
        workspace contributes ``0`` tokens but still counts on the file and
        tool axes — it was changed, we simply cannot price its content.

    Raises:
        ValueError: If ``output_tokens`` is negative.

    Examples:
        >>> compute_cost_floor([], ".", 0) == 0.0
        True
    """
    if output_tokens < 0:
        raise ValueError(f"output_tokens cannot be negative (output_tokens={output_tokens})")

    distinct = sorted(set(changed_paths))
    n_files = len(distinct)
    if n_files == 0:
        # No change-set means no floor to speak of. Returning 0.0 keeps the
        # function total; compute_acrr turns a 0.0 floor into None rather than
        # dividing by it.
        return weights.beta * output_tokens

    root = Path(workspace)
    content_bytes = 0
    for raw in distinct:
        resolved = _resolve_within(root, raw)
        if resolved is None:
            continue
        try:
            content_bytes += resolved.stat().st_size
        except OSError:
            continue

    tokens = content_bytes // BYTES_PER_TOKEN + output_tokens
    tool_calls = 2 * n_files + 1
    return weights.beta * tokens + weights.gamma * tool_calls + weights.delta * n_files


def compute_acrr(cost_actual: float, cost_floor: float) -> float | None:
    """Return E3 Eq. 3: ``(C_act - C_min) / C_min``.

    Args:
        cost_actual: Measured cost of the run.
        cost_floor: Floor from :func:`compute_cost_floor`.

    Returns:
        ``0.0`` when the run hit its floor exactly (optimally lean), positive
        when it spent more, and ``None`` when the floor is ``<= 0`` — with no
        change-set there is no denominator, the same "undefined, not zero"
        distinction :func:`compute_read_amplification` makes.

        A NEGATIVE result is returned as-is and deliberately not clamped. A run
        cheaper than its own floor means the floor model is wrong — that is a
        signal worth seeing, and clamping it to 0.0 would disguise a modelling
        bug as a perfect run.

    Examples:
        >>> compute_acrr(10.0, 10.0)
        0.0
        >>> compute_acrr(30.0, 10.0)
        2.0
        >>> compute_acrr(5.0, 0.0) is None
        True
    """
    if cost_floor <= 0:
        return None
    return (cost_actual - cost_floor) / cost_floor
