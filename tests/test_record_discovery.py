"""Smoke tests for ``record_discovery`` (R-8).

Coverage targets:

1. First call writes a new JSON file with the keyed entry.
2. Second call upserts a new key without disturbing the first.
3. Re-recording the same key overwrites in place (pure upsert,
   no merge / append).
4. Atomic-rename — no leftover .tmp file on success.
5. ``recorded_at`` is set from ``now`` argument (deterministic
   for tests).
6. Invalid key (spaces, leading dot dot, etc.) is rejected.
7. Corrupt existing file (non-object JSON) is rejected with a
   clear error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fa.tools import DiscoveryEntry, record_discovery


def test_record_discovery_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "codebase_map.json"
    record_discovery(
        "src/fa/chunker",
        DiscoveryEntry(
            summary="ADR-5 chunker package; entry point fa.chunker.default_chunker",
            pointers=("src/fa/chunker/__init__.py",),
            tags=("chunker",),
        ),
        path=target,
        now="2026-05-20T00:00:00Z",
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert "src/fa/chunker" in payload
    assert payload["src/fa/chunker"]["summary"].startswith("ADR-5 chunker")
    assert payload["src/fa/chunker"]["recorded_at"] == "2026-05-20T00:00:00Z"


def test_record_discovery_preserves_other_keys(tmp_path: Path) -> None:
    target = tmp_path / "codebase_map.json"
    record_discovery(
        "a",
        DiscoveryEntry(summary="first"),
        path=target,
        now="2026-05-20T00:00:00Z",
    )
    record_discovery(
        "b",
        DiscoveryEntry(summary="second"),
        path=target,
        now="2026-05-20T00:01:00Z",
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"a", "b"}


def test_record_discovery_overwrites_same_key(tmp_path: Path) -> None:
    target = tmp_path / "codebase_map.json"
    record_discovery(
        "key",
        DiscoveryEntry(summary="v1"),
        path=target,
        now="2026-05-20T00:00:00Z",
    )
    record_discovery(
        "key",
        DiscoveryEntry(summary="v2"),
        path=target,
        now="2026-05-20T00:01:00Z",
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["key"]["summary"] == "v2"
    assert payload["key"]["recorded_at"] == "2026-05-20T00:01:00Z"


def test_record_discovery_does_not_leak_tmp(tmp_path: Path) -> None:
    target = tmp_path / "codebase_map.json"
    record_discovery(
        "k",
        DiscoveryEntry(summary="s"),
        path=target,
        now="2026-05-20T00:00:00Z",
    )
    assert list(tmp_path.glob("*.tmp")) == []


def test_record_discovery_rejects_invalid_key(tmp_path: Path) -> None:
    target = tmp_path / "codebase_map.json"
    with pytest.raises(ValueError, match=r"discovery key"):
        record_discovery(
            "has spaces",
            DiscoveryEntry(summary="x"),
            path=target,
            now="2026-05-20T00:00:00Z",
        )


def test_record_discovery_rejects_corrupt_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "codebase_map.json"
    target.write_text('"not an object"', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        record_discovery(
            "k",
            DiscoveryEntry(summary="s"),
            path=target,
            now="2026-05-20T00:00:00Z",
        )


def test_record_discovery_stamps_timestamp_from_now_argument(
    tmp_path: Path,
) -> None:
    target = tmp_path / "codebase_map.json"
    record_discovery(
        "k",
        DiscoveryEntry(summary="s", recorded_at="ignored-on-write"),
        path=target,
        now="2026-05-20T12:00:00Z",
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["k"]["recorded_at"] == "2026-05-20T12:00:00Z"
