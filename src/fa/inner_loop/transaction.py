"""Transaction — read_set/write_set accumulation during execution.

Phase 0.5/1: Transaction with add_read/add_write, for blackboard conflict detection.

Per plan v3:
- Transaction read_set/write_set accumulated via SessionState
- Before write_file, declare read_set/write_set and call detect_conflict()
- Simple chain, pair over autonomy.

No external deps, stdlib only, thread-safe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Transaction:
    """Accumulates read/write sets during a session.

    Thread-safe, additive, never removes entries.
    """

    id: str
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    _read_set: set[str] = field(default_factory=set, init=False, repr=False)
    _write_set: set[str] = field(default_factory=set, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def add_read(self, path: str) -> None:
        with self._lock:
            self._read_set.add(str(path))

    def add_write(self, path: str) -> None:
        with self._lock:
            self._write_set.add(str(path))

    def add_reads(self, paths: list[str]) -> None:
        with self._lock:
            for p in paths:
                self._read_set.add(str(p))

    def add_writes(self, paths: list[str]) -> None:
        with self._lock:
            for p in paths:
                self._write_set.add(str(p))

    @property
    def read_set(self) -> list[str]:
        with self._lock:
            return sorted(self._read_set)

    @property
    def write_set(self) -> list[str]:
        with self._lock:
            return sorted(self._write_set)

    def snapshot(self) -> tuple[list[str], list[str]]:
        with self._lock:
            return sorted(self._read_set), sorted(self._write_set)


__all__ = ["Transaction"]
