"""
Tests for Gap 8 Tool Call Batching Parallel read-only
Prior art: Claude Code, Pi, OpenCode parallel read-only via ThreadPool max 5
"""

from __future__ import annotations


def test_batching_grouping() -> None:
    # S14b.1: fs_search is the single read-only discovery tool (replaces
    # fs_glob + fs_grep + fs_instant_grep, all of which were read-only).
    read_only = {"fs_search", "fs_read_file"}

    calls = [
        {"name": "fs_search"},
        {"name": "fs_read_file"},
        {"name": "fs_write_file"},
        {"name": "fs_run_bash"},
        {"name": "fs_search"},
    ]

    parallel = [c for c in calls if c["name"] in read_only]
    sequential = [c for c in calls if c["name"] not in read_only]

    assert len(parallel) == 3
    assert len(sequential) == 2
    assert all(c["name"] in read_only for c in parallel)
    # Old tool names must never appear as parallel-safe.
    for old in ("fs_glob", "fs_grep", "fs_instant_grep"):
        assert old not in read_only


def test_threadpool_parallel() -> None:
    import time
    from concurrent.futures import ThreadPoolExecutor

    def fake_tool(name: str) -> str:
        time.sleep(0.1)
        return f"result {name}"

    calls = ["fs_search", "fs_read_file", "fs_chronicle_search"]

    start = time.time()
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fake_tool, name) for name in calls]
        results = [f.result() for f in futures]
    parallel_time = time.time() - start

    assert parallel_time < 0.25, f"Parallel should be faster, took {parallel_time}"
    assert len(results) == 3
