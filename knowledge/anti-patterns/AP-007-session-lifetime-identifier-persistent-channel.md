---
compiled: 2026-07-23
applies_to:
  - "ADR-14 stateful bash EventStream runtime (PtyPool/tmux backend)"
  - "Any correlation-ID / idempotency-key / completion-sentinel matched against a persistent, accumulating observation channel"
status: accepted
evidence: commits ab09b31, a19e9f5 (first-agent-dev/First-Agent-dev)
---

# AP-007 — Session-lifetime identifier reused against a persistent channel

> A sentinel/correlation token is generated once per session and reused
> across every subsequent operation. The matching code assumes "if my
> token is present, MY operation is done." That assumption silently
> breaks the moment the observation channel is PERSISTENT (remembers
> every past occurrence forever) rather than INCREMENTAL (consumed and
> reset per read) — because the token from operation N-1 is still
> sitting in the channel when operation N starts.

## §Symptom

A component issues one identifier (sentinel string, request ID,
correlation token) at construction/session-start time and reuses it
for every subsequent call. Matching logic scans an observation channel
for that identifier to detect completion. Two failure shapes emerge
depending on channel semantics, both present in the same code:

1. **Echo-vs-result collision (single call).** If the channel echoes
   the command/request BEFORE producing the result (a terminal
   echoing typed input before executing it), the identifier appears
   twice per call — once in the echo, once in the real result.
   `str.split(token)[0]` (first-match) returns the echoed input, not
   the result.
2. **Cross-call staleness (race, not just wrong text).** Once a fast
   call completes, its token stays in the channel forever (persistent
   scrollback). A SLOWER subsequent call reusing the same token can
   match the PRIOR call's already-satisfied completion marker on its
   very first poll — returning immediately with the wrong (stale,
   already-old) result, before the new operation has even finished.
   This is a correctness failure, not a display bug: a caller can be
   told a not-yet-finished operation succeeded.

## §Wrong shape

```python
class PtySession:
    def __init__(self, ...):
        # ONE token for the session's entire lifetime.
        self._exit_token = f"FA_EXIT_{uuid.uuid4().hex[:6]}"
        self._end_token = f"FA_END_{uuid.uuid4().hex[:6]}"

    def _run_tmux(self, command, timeout):
        full = f"({command}); echo {self._exit_token}:$? {self._end_token}"
        self.pane.send_keys(full)
        while ...:
            text = "\n".join(self.pane.cmd("capture-pane", ...).stdout)
            if self._end_token in text:          # matches ANY past occurrence
                ...
                clean.split(f"{self._exit_token}:")[0]   # first-match = wrong
```

`tmux capture-pane` always returns the pane's FULL persistent
scrollback — not an incremental "what changed since last read" buffer.
Once `self._end_token` has appeared once, it never leaves the
scrollback; every later poll sees it again.

## §Right shape

Generate a fresh, unique identifier PER OPERATION, and anchor
extraction on a START marker unique to that same operation — never
assume "first occurrence" or "any occurrence" of a repeated substring
identifies the current call:

```python
def _run_tmux(self, command, timeout):
    call_id = uuid.uuid4().hex[:8]  # fresh per invocation
    start_token = f"FA_START_{call_id}"
    exit_token = f"FA_EXIT_{call_id}"
    end_token = f"FA_END_{call_id}"

    full = f"echo {start_token}; ({command}); echo {exit_token}:$? {end_token}"
    self.pane.send_keys(full)
    while ...:
        text = "\n".join(self.pane.cmd("capture-pane", "-S", "-", ...).stdout)
        start_idx = text.rfind(start_token)  # anchor on THIS call's marker
        if start_idx == -1:
            continue
        remainder = text[text.find("\n", start_idx) + 1 :]
        if end_token in remainder:
            m = re.search(rf"{re.escape(exit_token)}:(\d+)", remainder)
            output = remainder[: m.start()]  # slice by MATCH POSITION, not split()
```

## §Why the wrong shape dominates

1. **The bug is invisible until you specifically test sequencing.**
   A single-command smoke test ("run one command, check output")
   passes even with the fully-broken code, because a single occurrence
   of a first-match token collision can coincidentally still resolve
   (or fail in a way that looks like an unrelated flake). The race
   only manifests with ≥2 calls in the same session, one slow after
   one fast — a scenario most unit tests never construct.
2. **"Consumed buffer" is the more common mental model.** Most
   request/response correlation patterns (HTTP request IDs,
   `pexpect.expect()`'s `.before`, message queues) DO consume/reset
   per read. An author who has internalized that model applies it by
   default to a channel (`tmux capture-pane`) that does not share it.
3. **Every static and even most dynamic checks pass.** No type
   checker or linter flags "this uuid is generated once outside a
   loop that should generate it per-iteration" as an error — it is
   syntactically and semantically valid Python; the defect is a
   protocol-level assumption about the channel's memory model.

## §Detection

1. **Any sentinel/correlation-ID pattern generated in `__init__` and
   reused across multiple calls to a channel-scanning method** is a
   candidate — check whether the channel is consumed-per-read
   (pexpect `.before`) or persistent (tmux `capture-pane`, log files,
   any append-only store).
2. **C1 regression test: two sequential calls, second slower than
   first.** `tests/test_pty_persistence.py::test_slow_command_does_not_return_stale_prior_result`
   is the worked kill-check: run a fast command, then
   `sleep 1.5 && echo SLOW_DONE` with a fresh token per call; assert
   BOTH the correct output AND that wall-clock elapsed time is
   consistent with actually waiting (`elapsed >= 1.3`), not an
   instant stale-match return.
3. **C1 regression test: N sequential fast calls, assert isolation.**
   `test_sequential_commands_do_not_bleed_into_each_other` — run
   `echo cmd0`, `echo cmd1`, ..., assert each call's result equals
   only its own expected output, never a mix of a previous call's
   echo/result.

## §Linked-ADR

- [ADR-14 Stateful bash EventStream runtime](../adr/ADR-14-stateful-bash-eventstream-runtime.md)
  — the PtyPool/tmux backend this incident lives in.
- [AP-006](./AP-006-protocol-adapter-collapsed-as-duplicate.md) — found
  in the same review pass; both are "type/lint-clean but semantically
  wrong" defects invisible to this repo's static gates.

## §Evidence

- `ab09b31` "123 123" (human-authored, 2026-07-14) — introduces the
  session-lifetime `self._exit_token`/`self._end_token` pattern and
  the `str.split(exit_token)[0]` first-match extraction, predating
  every agent session that later worked on this file.
- `a19e9f5` "fix(pty): repair heredoc hang and command_timeout
  misclassification in tmux backend" — reproduction: `sleep 2 &&
  echo SLOW_DONE` sent immediately after a fast command returns in
  0.01s with the fast command's stale output; fix generates
  `call_id = uuid.uuid4().hex[:8]` per invocation, anchors extraction
  on `text.rfind(start_token)` + regex-match position instead of
  `str.split()`; kill-check tests added, verified to fail when
  reverted to session-lifetime tokens.
