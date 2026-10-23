"""Kernel cgroup-v2 population: the one fact that proves descendants are gone.

A stopped container, a closed PTY, a reaped shell and a Docker "exited" status
are all *requests*. The kernel's own `cgroup.events` is the observation: a
cgroup is empty when it reports `populated 0`, and nothing else here may be read
as terminality. Everything unreadable, absent, ambiguous or malformed is `None`
("cannot tell"), never `True`.

This module is deliberately a pure reader: it takes the cgroup root as an
argument so the local bank can prove the parsing and the no-follow rules on a
real filesystem without a container, and the deployed service passes the real
`/sys/fs/cgroup`. It never writes, mounts, kills or inspects Docker.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

_MAX_EVENTS_BYTES = 64 * 1024
_CONTAINER_ID = re.compile(r"[0-9a-f]{64}")
_POPULATED = re.compile(r"populated (\d+)")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


def _valid_parent(parent: object) -> str:
    """A configured cgroup parent: relative POSIX components, no escapes."""
    if not isinstance(parent, str) or not parent or parent.startswith("/") or "\\" in parent or "\x00" in parent:
        raise ValueError("cgroup parent")
    parts = parent.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("cgroup parent")
    return parent


def _expected_paths(root: Path, parent: str, container_id: str) -> tuple[Path, Path]:
    """cgroupfs (`<parent>/<cid>`) and systemd (`<parent>/docker-<cid>.scope`)."""
    base = root.joinpath(*parent.split("/"))
    return base / container_id, base / f"docker-{container_id}.scope"


def _populated(path: Path) -> bool | None:
    """One cgroup's population, or None when this path is not readable exactly."""
    try:
        fd = os.open(path, os.O_RDONLY | _NOFOLLOW)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None
        raw = os.read(fd, _MAX_EVENTS_BYTES + 1)
    except OSError:
        return None
    finally:
        os.close(fd)
    if len(raw) > _MAX_EVENTS_BYTES:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    matches = _POPULATED.findall(text)
    if len(matches) != 1:
        return None
    return int(matches[0]) == 0


def descendants_empty(cgroup_root: Path, cgroup_parent: str, container_id: str) -> bool | None:
    """True only for a readable `populated 0`; False for `> 0`; otherwise None.

    Both known driver layouts are probed because the layout is a daemon
    configuration fact, not something this reader may guess from a name. If
    neither layout is readable the answer is "cannot tell" — a missing cgroup is
    also what a wrong or unmounted path looks like.
    """
    if not isinstance(cgroup_root, Path) or not cgroup_root.is_absolute():
        raise ValueError("cgroup root")
    parent = _valid_parent(cgroup_parent)
    if not isinstance(container_id, str) or _CONTAINER_ID.fullmatch(container_id) is None:
        raise ValueError("container id")
    for path in _expected_paths(cgroup_root, parent, container_id):
        populated = _populated(path / "cgroup.events")
        if populated is not None:
            return populated
    return None
