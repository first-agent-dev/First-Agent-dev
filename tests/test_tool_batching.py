"""
Tests for Gap 8 Tool Call Batching Parallel read-only
Prior art: Claude Code, Pi, OpenCode parallel read-only via ThreadPool max 5
"""

def test_batching_grouping():
    READ_ONLY = {"fs.glob", "fs.grep", "fs.read_file", "fs.instant_grep"}

    calls = [
        {"name": "fs.glob"},
        {"name": "fs.read_file"},
        {"name": "fs.write_file"},
        {"name": "fs.run_bash"},
        {"name": "fs.grep"},
    ]

    parallel = [c for c in calls if c["name"] in READ_ONLY]
    sequential = [c for c in calls if c["name"] not in READ_ONLY]

    assert len(parallel) == 3
    assert len(sequential) == 2
    assert all(c["name"] in READ_ONLY for c in parallel)

def test_threadpool_parallel():
    from concurrent.futures import ThreadPoolExecutor
    import time

    def fake_tool(name):
        time.sleep(0.1)
        return f"result {name}"

    calls = ["fs.glob", "fs.grep", "fs.read_file"]

    start = time.time()
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fake_tool, name) for name in calls]
        results = [f.result() for f in futures]
    parallel_time = time.time() - start

    # Sequential would be 0.3s, parallel should be ~0.1s
    assert parallel_time < 0.25, f"Parallel should be faster, took {parallel_time}"
    assert len(results) == 3
