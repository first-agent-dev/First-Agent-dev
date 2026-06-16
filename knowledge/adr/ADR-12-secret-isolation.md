# ADR-12 — API-key isolation from the agent

- **Status:** accepted
- **Date:** 2026-06-16
- **Deciders:** operator + FA agent

## Context

The AIO runs the LLM agent inside the *same* container that holds the LLM
provider API keys. The agent has a `fs.run_bash` tool and `fs.read_file`/
`fs.write_file`, so a prompt-injected or misbehaving agent could try to read the
keys and exfiltrate them. The user requirement is concrete: *"no LLM can sniff
out my keys"* — asking the agent "remind me my Fireworks key" must yield only the
variable name, never the value; while legitimate questions about roles / request
schema must keep working.

Two exfiltration vectors existed before this ADR (verified in code):

- **V1 — file in sandbox:** `.env.fa` lived at the repo root, which is mounted as
  `/workspace`, so `fs.read_file /workspace/.env.fa` passed path-containment.
- **V2 — inherited env:** `fs.run_bash` ran `subprocess.run(...)` with no `env=`,
  inheriting the parent process environment, into which Docker Compose `env_file`
  had injected every key. `printenv`, `cat /proc/self/environ`, `python -c
  "os.environ"` all returned live keys.

Existing `SecretGuard` (input denylist) and `SecretRedactor` (output masking) are
best-effort filters, trivially bypassable (e.g. `cat /proc/self/environ`,
runtime base64) — not a boundary. Prior art (LangChain deepagents; Claude-Code
sandboxing reviews; the Hermes-agent CVE) all conclude: *secrets must live
outside any surface the sandboxed agent can reach.*

Research + plan: `knowledge/research/` (this PR's plan) and the threat-model in
the PR note.

## Options considered

### Option A — env-scrub the bash tool only

- Pros: small change; closes V2 for bash.
- Cons: keys still in `os.environ` of the `fa` process and in PID-1 env; any
  non-bash path that prints `os.environ` would leak. Not a real boundary.

### Option B — private in-memory SecretStore + file outside /workspace + bash scrub (chosen)

- Pros: keys never enter `os.environ`; never a file inside `/workspace`; bash
  child env additionally scrubbed. Three independent barriers. `ProviderChain`
  is already injectable, so it is a small change, not a rewrite.
- Cons: keys still exist in the `fa` process memory (unavoidable — something must
  call the API); a deep compromise of the `fa` process itself is out of scope.

### Option C — egress-injection proxy (Vercel-style)

- Pros: code can *use* a key via a proxy but never *read* it; mitigates the
  "use"-vector too.
- Cons: heavyweight; overkill for single-operator AIO v0.1. Recorded in BACKLOG.

## Decision update (2026-06-16): Option C brought forward to v0.1

A blocking security review of the Option-B implementation found the boundary was
not airtight: `fs.run_bash` READ_ONLY commands (`cat`/`grep`/`dd`/…) bypassed
sandbox path-containment and could read `/run/secrets/fa.env` and the deploy key
directly, and the model-facing tool-result channel was not redacted (only the
trace was). Moving the file out of `/workspace` defeats `fs.read_file` but not
`fs.run_bash`, which shares the agent's uid — file permissions cannot separate
"the `fa` process reading via SecretStore" from "the `fa` process reading via
`cat` in run_bash".

We therefore brought **Option C (egress-injection proxy)** forward into v0.1 as
the boundary for LLM provider keys, keeping Option B's barriers as
defense-in-depth and as the boundary for the GitHub deploy key.

```text
 first-agent container (USER fa)                 fa-egress-proxy container (USER fa)
 ── agent + fs.run_bash ──                        ── reads /run/secrets/fa.env (ro) ──
   ProviderChain.base_url = ───── HTTP ─────────►  injects real Authorization / x-api-key
     http://fa-egress-proxy:8080/route/<name>      forwards to the real provider
   carries X-FA-Proxy-Token (NOT a key)  ◄───────  returns provider JSON
   NO LLM-key file/env/memory here                 NO /workspace, no agent code
```

Properties: LLM provider keys exist on NO file, env var, or process memory the
agent's uid/namespace can reach. A fully prompt-injected agent can *use* a key
(make a metered call through the proxy) but can never *read* its value — the
boundary is the **container separation** (separate mount/PID namespaces), not a
uid trick, so it holds without running the agent container as root.

Guarantees (each test-enforced):

- **G1** — LLM keys unreachable by the agent: `tests/test_secret_isolation_invariants.py`
  (agent has no key mount / `FA_SECRETS_FILE`; proxy holds keys ro, no agent
  workspace), `tests/test_proxy_wiring_cli.py` (no provider key on the fa side).
- **G2** — deploy key not exfiltrable: `tests/test_sandbox_secret_paths.py` +
  `tests/test_secret_exfiltration.py` (bash-read of secret paths denied) and
  `tests/test_model_egress_redaction.py` (model channel masks any leaked value).
- **G4** — acceptance criterion ("remind me my key → name only"): the
  model-egress redactor masks the value in raw/base64/hex/url/reversed forms.

Residual (documented, not hidden): a determined attacker who both reads the
deploy-key file via a bash form the lexical tripwire misses AND applies an
exotic encoding the redactor doesn't know (e.g. gzip+xor) could still surface it.
The airtight closure is a constrained-git interface — recorded in BACKLOG as the
first unblock-ready follow-up. LLM keys do not share this residual (they are not
in the agent container at all).

## Decision (original Option B, retained as defense-in-depth)

We choose **Option B** for the in-process / deploy-key layers. Concretely
(enforced invariant):

1. **Keys live only in `/srv/first-agent/secrets/fa.env`** (host, `0600`),
   mounted **read-only** at `/run/secrets/fa.env` — *outside* `/workspace`, so the
   sandbox path-containment denies `fs.read_file`/`bash` access.
2. **Keys are read once into a private `SecretStore`** (`Mapping[str, str]`,
   `fa.providers.secret_store`) and never written to `os.environ`. All three
   key-readers (`load_models_config`, `ProviderChain`, `SecretRedactor`) take the
   store via their existing injectable `env=` seam. Strict file-only — no
   `os.environ` fallback (`docker run -e` does not feed provider auth).
3. **`fs.run_bash` runs with an allowlist-scrubbed child env** (`bash_env.py`)
   with a fail-closed secret-name filter applied after the allowlist, so even a
   re-introduced or operator-added key-named var cannot reach the shell.
4. Backstops: encoding-aware `SecretRedactor` (base64/hex + decoded-window scan)
   and broadened `SecretGuard` tripwires — defense-in-depth, not the boundary.

`.env.fa` is reduced to **non-secret** runtime controls (`FA_AUTO_RUN`, `FA_TASK`).

## Consequences

- Positive: an agent cannot read a key via file, env, `/proc`, interpreters, or
  runtime encoding — proven by `tests/test_secret_exfiltration.py` (CI-enforced).
  Legitimate provider calls work (store supplies the key to `ProviderChain`).
- Positive: regression-guarded by `tests/test_secret_isolation_invariants.py`
  (compose mount shape, no env-injection, bash scrub, cli reads from store).
- Negative: operator `docker compose run -e KEY=...` no longer feeds provider
  auth (documented); keys must be edited in the host secrets file then the
  container recreated.
- Follow-up: BACKLOG — egress allowlist (cheap "use"-vector limit) and, later,
  the egress-injection proxy (Option C) if remote sandboxes / multi-tenancy land.

## References

- `src/fa/providers/secret_store.py`, `src/fa/cli.py` (read-site threading)
- `src/fa/inner_loop/tools/bash_env.py`, `run_bash.py`
- `src/fa/observability/redaction.py`, `src/fa/inner_loop/hooks/builtin.py`
- `docker-compose.fa.yml`, `scripts/setup-fa-desktop.sh`, `scripts/fa-update.sh`
- `tests/test_secret_exfiltration.py`, `tests/test_secret_isolation_invariants.py`
- `knowledge/instructions/01-install.md` §Фаза 7b, `02-operations.md` §🔒
