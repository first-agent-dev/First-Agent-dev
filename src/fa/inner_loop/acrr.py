"""ACRR proxy — Adjusted Context-to-Result Ratio (S5, CT6).

A cheap stand-in for the E3 paper's efficiency metric: how many distinct files
a run had to READ per distinct file it actually CHANGED. Low is efficient;
high means the run spent its context wandering.

Deliberately a *proxy*. The full E3 cost model C(pi) weighs tokens, latency and
tool mix; this counts files, because files are what the event log already
records losslessly and what an operator can reason about without a cost table.

Why ``files_changed == 0`` returns ``None`` rather than a number
---------------------------------------------------------------
The obvious implementation divides by ``max(files_changed, 1)``. That makes the
metric's most pathological input — read ten files, change nothing, i.e. pure
unproductive exploration — numerically IDENTICAL to a healthy run that read ten
files and changed one. The one condition this metric exists to surface would be
the one condition it cannot express, so the sentinel is unfalsifiable.

``None`` keeps "undefined ratio" distinguishable from "ratio of 10" and forces
the display layer to say so out loud ("n/a (no files changed)").
"""

from __future__ import annotations

__all__ = ["compute_acrr_proxy"]


def compute_acrr_proxy(files_read: int, files_changed: int) -> float | None:
    """Return distinct files read per distinct file changed.

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
        >>> compute_acrr_proxy(5, 5)
        1.0
        >>> compute_acrr_proxy(20, 2)
        10.0
        >>> compute_acrr_proxy(10, 0) is None
        True
    """
    if files_read < 0 or files_changed < 0:
        raise ValueError(f"file counts cannot be negative (files_read={files_read}, files_changed={files_changed})")
    if files_changed == 0:
        return None
    return files_read / files_changed
