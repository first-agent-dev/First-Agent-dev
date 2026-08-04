# PLAN: S11 — controlled deployment and closeout (operator live-verification sheet)

Plan-ID: `PLAN-cli-trace-S11-controlled-deployment`

Status: **READY TO EXECUTE** — no blocking questions. Operator scoping answers
recorded 2026-08-01 (§0.6).

**Every inspection block in this sheet was rehearsed against a real local run
before publication** (a genuine `fa run` with body capture on, then each block
executed verbatim through a real `sh -lc`). That rehearsal found **five
defects in this document**, all fixed here — see §7. S7's execution found two
such defects *during* operator time; this pass moves that cost off the
operator.

Depth: **P2** — evidence-gathering on a live deployment plus a controlled
failure-mode exercise. **No source edits during execution.**

Parent: [`cli-trace-substrate-rebaseline-2026-07-25.md`](./cli-trace-substrate-rebaseline-2026-07-25.md)
§Step S11 — the final step of the workplan.

Prior protocol this mirrors (and extends):
[`PLAN-cli-trace-S7-container-verification.md`](./PLAN-cli-trace-S7-container-verification.md)
· [`PLAN-cli-trace-S4-direct-container-baseline.md`](./PLAN-cli-trace-S4-direct-container-baseline.md)

Slices being verified: **S5–S10c**. The S10c surfaces are the ones that have
**never** run on real infrastructure and that change operator-visible
contracts.

---

## 0. Scope and execution boundary

### 0.1 IDEA

Every slice from S5 to S10c was proven against a mocked transport on a
developer box. The parent's Do-not is blunt about what that is worth:

> *do not call a local pytest pass a production deploy verification.*

This sheet converts the parent's six S11 exit criteria from PENDING into
recorded evidence, and it carries three things no previous sheet could:

1. **S10c changed two operator-visible exit codes.** `fa routing-check` now
   aborts a deploy on a bad `--config`; `fa workflow` now exits **1** on a
   non-`DONE` verdict. Both are consumed by shell `&&` chains on this host.
   A local test proves the integer; only the deployment proves the *consumer*.
2. **S10c.3 mutates existing deployment state.** The retroactive tightening
   pass chmods files under `/srv/first-agent/state` on the first run after
   deploy. That is intended — and it must be observed, not assumed.
3. **S11 Do #8 is the only criterion about failure behaviour**, and it has
   never been exercised: does the entrypoint reach an explicit standby state,
   or continue with an ambiguous workspace?

### 0.2 CONCRETE INTENT

Answer each with recorded output, never inference:

```text
IDENTITY   Is the running image built from the reviewed commit, and does the
           process import that source? (four independent views must agree)
PROXY      Is the agent container genuinely key-less, and does the LLM path
           work only through the proxy?
GATE       Does `fa routing-check` now ABORT fa-clean-rebuild.sh on a bad
           path, where it previously logged "OK" and built?
YAML       Do all five config-loading commands report exit 2 on malformed
           YAML instead of a traceback?
POSTURE    Are new artifacts 0600/0700, and were the PRE-EXISTING 0644 files
           actually repaired by the Q56 pass?
BODIES     Does FA_DEBUG_LLM_BODIES gate capture in both states, on the real
           path, by count only?
VERDICT    Does `fa workflow` exit 1 on a real BLOCKED/REPAIR verdict and 0 on
           a real PASS — with flow_state.json and global_history agreeing?
COST       What does a real request actually contain? (I-37 follow-up data)
STATS      Do the S9 projections read real deployed data?
FAILURE    Does an invalid auto-run configuration reach standby with a status
           file, rather than running with an ambiguous workspace?
DRIFT      After all of it, is the repo tree clean and the state consistent?
```

### 0.3 GOALS

| ID | Goal |
|---|---|
| **S11-G1** | Record deployment identity from four independent views; rule out source/image drift. |
| **S11-G2** | Prove the ADR-12 proxy boundary holds: no provider key in the agent container, and the LLM path works. |
| **S11-G3** | Prove the S10c.1 deploy gate aborts on a bad config path and on malformed YAML, across all five commands. |
| **S11-G4** | Prove the S10c.2 verdict-driven exit code on real verdicts, with artifacts agreeing. |
| **S11-G5** | Prove the S10c.3 artifact posture on new artifacts **and** the retroactive repair of existing ones. |
| **S11-G6** | Prove the debug-body gate on the deployed path, counts only. |
| **S11-G7** | Prove S9 stats/projections read real deployed data. |
| **S11-G8** | Prove the entrypoint fails to an explicit standby state (parent Do #8). |
| **S11-G9** | Capture request-anatomy data for the open I-37 question (AGENTS.md map at 48.4%). |
| **S11-G10** | Leave the deployment in a known-good, drift-free state with recorded evidence. |

### 0.4 NON-GOALS

- **No edits under `src/`, `tests/`, `scripts/` during execution.** If a fix is
  needed, it is a follow-up slice.
- **No fixes for anything found** — record and classify (§0.5).
- **Never print `llm_bodies.jsonl` contents, prompt text, response text, or key
  values.** Counts, byte sizes, and key *names* only (ADR-12). Where a step
  needs request anatomy, it prints **sizes per message role**, never content.
- **No `scripts/fa` wrapper for the acceptance proof** — parent Do-not; use
  `docker compose exec` directly. (`scripts/fa` may be used for convenience
  *outside* the numbered steps.)
- No source changes to fix I-37, I-34, I-35 — all remain open by decision.

### 0.5 STOP RULE

If a step's ACTUAL differs from EXPECTED: **record it, classify it, continue**
— unless it blocks the next step, in which case stop and report.

Classify every deviation into exactly one of the parent's categories:

```text
source drift · image drift · filesystem permission · proxy · provider ·
authority · rendering · sheet defect
```

**"Sheet defect" is a real and expected outcome.** S7's execution found two
authoring defects in its own sheet — a contradictory SQL predicate and an
absence-assertion with no positive control. If a command here looks like it
cannot fail, say so; that is a finding about this document, not about the
product.

### 0.6 Operator scoping answers (2026-08-01)

| Q | Answer | Consequence for this sheet |
|---|---|---|
| Live provider spend | *"maximum surface, multiple runs if needed. inference tokens are available"* | Full workflow matrix incl. repair mode; `probe --all-roles`; multiple runs. |
| Restart the live service for the failure test | **Yes** | §Step S11.9 stops and restarts `first-agent` with a broken env, then restores. |
| Existing-state mutation | **Record modes before and after, no backup** | §Step S11.1 takes a mode census *before* any run; §S11.6 diffs it. |

### 0.7 Time and cost estimate

Roughly **60–90 minutes** of operator attention. Provider spend is dominated by
S11.7 (workflow matrix): three `fa workflow` invocations, each planner→coder→
eval, one with up to 2 repair rounds — order of tens of thousands of tokens
total depending on the model. Everything before S11.5 is free.

---

## 1. Preconditions and environment

```bash
# ── Set once per session. Adjust only if your host layout differs. ───────
export COMPOSE=/srv/first-agent/repo/First-Agent-dev/docker-compose.fa.yml
export SERVICE=first-agent
export PROXY=fa-egress-proxy
export STATE=/srv/first-agent/state           # bind-mounted at /home/fa/.fa
export ROUTING=/srv/first-agent/routing/models.yaml
export REPO_DIR=/srv/first-agent/repo/First-Agent-dev

# Where this sheet's evidence is collected. Everything you paste back comes
# from here.
export EVID=/tmp/s11-evidence-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$EVID"
echo "EVIDENCE DIR: $EVID"

# Sanity: compose resolves, both services exist.
docker compose -f "$COMPOSE" ps | tee "$EVID/00-ps-before.txt"
```

**Expect:** both `first-agent` and `fa-egress-proxy` listed. Record their state
even if one is down — that is itself evidence.

> **`sh -lc` and PATH.** Every in-container block uses `sh -lc`, which sources
> the login profile. In this image `fa` is on the system PATH so that is fine —
> but if any step reports `fa: not found`, that is a **PATH problem in the
> shell, not a missing binary**. Re-run that block with `sh -c` instead of
> `sh -lc`, or call `/opt/fa-venv/bin/fa` explicitly, and record which you used.

> **Every step writes to `$EVID`.** At the end, §S11.11 bundles it. Do not rely
> on scrollback: several steps produce output longer than a terminal buffer.

---

## 2. The run-id namespace this sheet uses

All artifacts are namespaced `s11-*` so they are trivially separable from real
work and from S7's `s7-*` runs.

| run-id | Step | Purpose |
|---|---|---|
| `s11-run-a` | S11.5 | bodies OFF baseline |
| `s11-run-b` | S11.5 | bodies ON (`-e FA_DEBUG_LLM_BODIES=1`) |
| `s11-run-c` | S11.5 | `--detail debug`, bodies still OFF (coupling check) |
| `s11-run-d` | S11.5 | `--output-mode quiet` stdout contract |
| `s11-wf-linear` | S11.7 | linear workflow, verdict-driven exit code |
| `s11-wf-repair` | S11.7 | repair mode, budget exhaustion |
| `s11-wf-quiet` | S11.7 | workflow under quiet |
| `s11-autorun` | S11.9d | entrypoint auto-run positive control |
| `s11-yamlprobe` | S11.4d | malformed-config probe (no run dir expected) |

---

## Step S11.0 — Pre-flight: human diff review and deployment decision

Traces-to: **parent Do #1**, S11-G1.

This is the step the parent puts first and it is not ceremonial.

```bash
# 0a. What is about to be deployed, relative to what main has.
cd "$REPO_DIR"
git fetch --all --prune 2>&1 | tail -3
git log --oneline origin/main..HEAD | tee "$EVID/00-commits-to-deploy.txt" | head -40
echo "--- commit count ---"; git rev-list --count origin/main..HEAD

# 0b. The full diffstat. Read it. This is the human gate.
git diff --stat origin/main...HEAD | tee "$EVID/00-diffstat.txt" | tail -30

# 0c. Anything touching deploy-critical files gets read in full.
git diff origin/main...HEAD -- scripts/ Dockerfile.fa docker-compose.fa.yml \
  | tee "$EVID/00-diff-deploy-critical.patch" | head -100
echo "--- deploy-critical diff line count ---"
wc -l < "$EVID/00-diff-deploy-critical.patch"

# 0d. Working tree must be clean before we build an image from it.
git status --short | tee "$EVID/00-git-status.txt"
test -s "$EVID/00-git-status.txt" && echo "DIRTY — resolve before building" \
                                  || echo "clean"
```

**Expect:** the commit list matches the slices you intend to ship (S5…S10c);
the deploy-critical diff is reviewed by eye; the tree is clean.

**STOP if the tree is dirty.** An image built from a dirty tree cannot have its
revision recorded honestly, which invalidates S11-G1 and every step after it.

**Record:** the exact SHA you are deploying.

```bash
export DEPLOY_SHA=$(git rev-parse HEAD)
export DEPLOY_SHORT=$(git rev-parse --short HEAD)
echo "DEPLOY_SHA=$DEPLOY_SHA" | tee "$EVID/00-deploy-sha.txt"
```

---

## Step S11.1 — Pre-deploy state census (the "before" half of S11-G5)

Traces-to: S11-G5. Depends-on: S11.0. **Run this BEFORE rebuilding.**

S10c.3's retroactive pass will tighten modes on the first run after deploy.
That repair is only provable against a recorded "before".

```bash
# 1a. Full mode census of the live state tree, as the host sees it.
sudo find "$STATE" -printf '%m %y %u:%g %p\n' 2>/dev/null \
  | sort -k4 | tee "$EVID/01-modes-BEFORE.txt" | head -40
echo "--- total entries ---"; wc -l < "$EVID/01-modes-BEFORE.txt"

# 1b. The headline number: how many entries are group/other-accessible today?
# NOTE: pure string test on the octal digits. `strtonum()`/`and()` are GNU-awk
# builtins; on a mawk host (Debian/Ubuntu default) they are undefined, awk
# prints "function ... never defined" to stderr and emits NOTHING — a silent
# count of 0 that looks like a clean state tree. Measured on this box.
awk '$1 ~ /^[0-7][0-7][0-7]$/ {
       g = substr($1,2,1); o = substr($1,3,1);
       if (g != "0" || o != "0") print
     }' "$EVID/01-modes-BEFORE.txt" \
  | tee "$EVID/01-permissive-BEFORE.txt" | head -20
echo "--- permissive entries BEFORE ---"
wc -l < "$EVID/01-permissive-BEFORE.txt"

# 1c. Specifically the artifact classes I-36 named.
sudo find "$STATE" \( -name 'llm_bodies.jsonl' -o -name 'events.jsonl' \
                      -o -name '*.db' -o -name 'manifest.json' \) \
  -printf '%m %p\n' 2>/dev/null | sort | tee "$EVID/01-artifacts-BEFORE.txt"
```

```bash
# 1b-check. Prove the filter itself works before trusting its count.
# A harness that reports 0 because it is broken is indistinguishable from a
# clean state tree — this is the S12 "vacuous check" lesson applied to a
# shell one-liner.
printf '644 f x:x /probe/should-match\n700 d x:x /probe/should-not\n' \
  | awk '$1 ~ /^[0-7][0-7][0-7]$/ { g=substr($1,2,1); o=substr($1,3,1); if (g!="0"||o!="0") print }'
echo "^ MUST print exactly the 644 line. If it prints nothing, your awk is"
echo "  broken/unsupported and every permissive count in this sheet is a lie."
```

**Expect (before the S10c deploy):** a non-zero count of `0644` files and
`0755` directories. **If the permissive count is already 0**, note it — the box
may have been rebuilt recently, and S11.6's "repair" assertion then has nothing
to observe. That is a valid outcome, but say so rather than claiming a repair
that never happened.

**Record `01-permissive-BEFORE.txt` — S11.6 diffs against it.**

---

## Step S11.2 — Build and deploy the reviewed revision

Traces-to: **parent Do #2**, S11-G1.

```bash
# 2a. Build with the revision recorded IN the image.
cd "$REPO_DIR"
docker compose -f "$COMPOSE" build \
  --build-arg FA_SOURCE_REVISION="$DEPLOY_SHA" 2>&1 \
  | tee "$EVID/02-build.log" | tail -25
echo "BUILD_EXIT=${PIPESTATUS[0]}"

# 2b. Recreate BOTH services. The proxy loads its route table at startup, so a
#     routing change without a proxy recreate is a classic silent staleness bug
#     (R2-2 in docker-compose.fa.yml).
docker compose -f "$COMPOSE" up -d --force-recreate 2>&1 \
  | tee "$EVID/02-up.log" | tail -15

# 2c. Wait for health, then record it. Proxy first: the agent depends_on it.
sleep 20
docker compose -f "$COMPOSE" ps | tee "$EVID/02-ps-after.txt"
docker inspect --format '{{.Name}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} started={{.State.StartedAt}}' \
  first-agent fa-egress-proxy | tee "$EVID/02-health.txt"
```

**Expect:** build succeeds; both containers `running`; `fa-egress-proxy`
reports `healthy` (its healthcheck actually probes `/healthz`), `first-agent`
reports `healthy` (its healthcheck is only `fa --version`, which is weaker —
noted, not a defect).

> **If the build fails on the routing lint**, that is not a build failure — it
> is **S10c.1 working**. Jump to S11.3b, record it, fix `models.yaml`, and
> return here. Before S10c, a bad path would have printed "Routing lint: OK".

---

## Step S11.3 — Deployment identity from four independent views (S11-G1)

Traces-to: **parent Do #7**, S11-G1. Depends-on: S11.2.

The parent asks for four views precisely because any one of them can lie.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "=== VIEW 1: bind-mounted source revision (/repo) ==="
  cd /repo 2>/dev/null && git rev-parse HEAD 2>/dev/null || echo "NO_GIT_AT_/repo"

  echo "=== VIEW 2: what the interpreter actually imports ==="
  python -c "import fa,sys; print(fa.__file__); print(sys.executable)"

  echo "=== VIEW 3: installed distribution version ==="
  python -c "
try:
    from importlib.metadata import version, files
    print(\"version:\", version(\"first-agent\"))
except Exception as exc:
    print(\"metadata unavailable:\", exc)
"
  fa --version

  echo "=== VIEW 4: is agent-writable source shadowing the image? ==="
  echo "PYTHONPATH=${PYTHONPATH:-<unset>}"
  for p in /workspace/src/fa /sessions/*/src/fa; do
    [ -e "$p" ] && echo "SHADOW PRESENT: $p" || true
  done
  echo "(no SHADOW lines above = image code only)"
' 2>&1 | tee "$EVID/03-identity-container.txt"

# 3a. Image label + build metadata, from the host side.
docker inspect --format '{{.Config.Image}} {{json .Config.Labels}}' first-agent \
  | tee "$EVID/03-image-labels.txt"
docker image inspect "$(docker inspect --format '{{.Image}}' first-agent)" \
  --format 'created={{.Created}} id={{.Id}}' | tee -a "$EVID/03-image-labels.txt"

# 3b. THE COMPARISON. State it explicitly rather than eyeballing.
echo "host DEPLOY_SHA : $DEPLOY_SHA"      | tee "$EVID/03-drift-verdict.txt"
grep -A1 "VIEW 1" "$EVID/03-identity-container.txt" | tail -1 \
  | sed 's/^/container /' | tee -a "$EVID/03-drift-verdict.txt"
```

**Expect:** VIEW 1 == `$DEPLOY_SHA`. VIEW 2 resolves inside the image
(`/opt/first-agent/src/fa/__init__.py`, interpreter `/opt/fa-venv/bin/python`),
**not** `/repo` and **not** a `/sessions/...` clone.

**VIEW 4 — corrected 2026-08-03 (R11).** The original text said "prints no
`SHADOW PRESENT` line", which is **wrong for a long-lived host**. The glob
`/sessions/*/src/fa` matches every *historical* session clone, and each one is a
full repo checkout, so a box with 18 past sessions prints 18 lines. That is
normal accumulation, not drift.

What VIEW 4 actually tests is whether a session clone is **on the import path of
this process**. `scripts/fa-entrypoint.sh:199` prepends `${WORKSPACE}/src` to
`PYTHONPATH` **only** when `${WORKSPACE}/src/fa/__init__.py` exists, and only for
the workspace of the *current* session.

Read the two lines together:

| VIEW 2 | `PYTHONPATH` | verdict |
|---|---|---|
| `/opt/first-agent/src/fa/__init__.py` | `<unset>` | ✅ **image code** — inert clones on disk are irrelevant |
| `/sessions/<id>/src/fa/__init__.py` | contains `/sessions/...` | ❌ **source drift** — the process is running agent-writable code |

So the pass condition is **`PYTHONPATH=<unset>` and VIEW 2 under `/opt`**, not an
empty shadow list. A `SHADOW PRESENT` line only matters if VIEW 2 or `PYTHONPATH`
names that same path.

> **Housekeeping, not a defect:** N stale session clones are N full checkouts of
> disk. Worth a retention policy (→ BACKLOG), but they cannot affect a run whose
> `PYTHONPATH` is unset.

**Classification if they disagree:** VIEW 1 ≠ host ⇒ *source drift*; VIEW 2
inside `/repo` or a session ⇒ *source drift* (the process is not running image
code); image `created` older than the build ⇒ *image drift*.

**This is the anchor step. Every later result is only as trustworthy as this
line.**

---

## Step S11.4 — Proxy boundary and the S10c.1 config gates (S11-G2, S11-G3)

Traces-to: **parent Do #3**, S11-G2, S11-G3. Depends-on: S11.3.
**Cost: `probe` is ~10 tokens per role. Everything else here is free.**

### 4a. The agent container must hold NO provider key (ADR-12)

> **Strengthened during review.** The first draft checked one path
> (`/run/secrets/fa.env`). ADR-12's claim is broader — *the agent holds no LLM
> provider keys* — and a single-path check passes while a key arrives by another
> route. The realistic one is `models.yaml`: it is mounted **into the agent**
> read-only, and it is supposed to carry only `api_key_env` **names**. An
> inlined `api_key:` value there would defeat the whole design and the old
> check would still have printed OK.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "=== 1. env var NAMES containing key/token/secret (NAMES ONLY) ==="
  env | cut -d= -f1 | grep -Ei "key|token|secret|api" | sort || echo "(none)"

  echo "=== 2. what is mounted at /run/secrets ==="
  ls -l /run/secrets/ 2>/dev/null || echo "(no /run/secrets)"

  echo "=== 3. the provider key bundle must NOT be here ==="
  [ -e /run/secrets/fa.env ] && echo "VIOLATION: fa.env present in AGENT" \
                             || echo "OK: no fa.env in agent"

  echo "=== 4. models.yaml must reference env NAMES, never inline values ==="
  # Print only the KEY side of any api_key-ish line, never the value.
  grep -nE "api_key" /home/fa/.fa/models.yaml 2>/dev/null \
    | sed -E "s/(api_key[a-z_]*)[[:space:]]*:.*/\1: <redacted>/" \
    | head -20 || echo "(no api_key lines)"
  if grep -qE "^[[:space:]]*api_key[[:space:]]*:" /home/fa/.fa/models.yaml 2>/dev/null; then
    echo "VIOLATION: models.yaml contains an INLINE api_key (expected api_key_env)"
  else
    echo "OK: models.yaml uses api_key_env references only"
  fi

  echo "=== 5. any env var whose VALUE looks like a provider key? ==="
  # Shape-only test: report the NAME of any var whose value matches a common
  # key prefix. The value itself is never printed.
  python - <<"PY2"
import os, re
pat = re.compile(r"^(sk-|sk_live|xai-|gsk_|AIza|hf_|r8_|pplx-)")
hits = [k for k, v in os.environ.items() if isinstance(v, str) and pat.match(v)]
print("  key-shaped env values:", hits if hits else "none (OK)")
PY2

  echo "=== 6. positive control: the fa->proxy TOKEN *is* expected here ==="
  [ -e /run/secrets/fa_proxy_token ] \
    && echo "OK: fa_proxy_token present (not a provider key; proves the mount works)" \
    || echo "UNEXPECTED: no fa_proxy_token — is this the right container?"
' 2>&1 | tee "$EVID/04a-agent-keyless.txt"
```

**Expect:** `OK` on 3, 4 and 6; `none (OK)` on 5; only `fa_proxy_token`,
`git_key`, `known_hosts` under `/run/secrets`.

**Check 6 is the positive control** — without it, "no keys found" is equally
consistent with "the secrets mount is broken and nothing is there", which
would make checks 2–5 pass for the wrong reason.

**Any VIOLATION here is a P1 finding.** Stop, record, and report before
continuing — the remaining steps assume the boundary holds.

### 4b. `fa selfcheck` — the proxy seam, no provider call

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  fa selfcheck --role coder 2>&1 | tee "$EVID/04b-selfcheck.txt"
echo "SELFCHECK_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/04b-selfcheck.txt"
```

**Expect:** exit 0, `fa selfcheck: OK`, `/healthz reachable`,
`/routes returned N route(s)`, and a checked-route count. **Exit 1** means the
agent and proxy disagree about the route table — the message names the remedy.
**Exit 2** means local configuration is wrong. That 1-vs-2 split is itself part
of what S10c.5 preserved.

### 4c. `fa routing-check` — the deploy gate, in all four states (S10c.1)

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "=== C1: the REAL routing file (expect 0, or 1 if it has findings) ==="
  fa routing-check --config /home/fa/.fa/models.yaml; echo "EXIT=$?"

  echo "=== C2: a path that does not exist (I-40 — expect 2, was 0) ==="
  fa routing-check --config /home/fa/.fa/DOES-NOT-EXIST.yaml; echo "EXIT=$?"

  echo "=== C3: malformed YAML (expect 2 + a message, NOT a traceback) ==="
  printf "roles: [oops\n" > /tmp/s11-broken.yaml
  fa routing-check --config /tmp/s11-broken.yaml; echo "EXIT=$?"

  echo "=== C4: valid YAML, no roles (expect 0 — empty is a clean state) ==="
  printf "{}\n" > /tmp/s11-empty.yaml
  fa routing-check --config /tmp/s11-empty.yaml; echo "EXIT=$?"
' 2>&1 | tee "$EVID/04c-routing-check-matrix.txt"
```

**Expect:** C1 → 0 (or 1 with named findings); **C2 → 2** with
`config not found:` naming the path; **C3 → 2** with `not valid YAML` and a
line/column, **no Python traceback**; C4 → 0 with `no roles declared`.

> **C2 is the headline.** Before S10c this printed
> `WARNING: no roles declared` and returned **0**, and
> `scripts/fa-clean-rebuild.sh:471` treated that as a passing gate.

### 4d. Malformed YAML across **all five** commands (S10c.1, the wider fix)

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  printf "roles: [oops\n" > /tmp/s11-broken.yaml
  # These are the commands that actually PARSE models.yaml. Verified by
  # inspection: routing-check, probe, selfcheck, run and egress-proxy all call
  # load_models_config_from_path; stats does NOT and is deliberately absent --
  # including it would have produced a non-zero exit for an unrelated reason
  # and read as a pass.
  for cmd in "routing-check --config /tmp/s11-broken.yaml" \
             "probe --config /tmp/s11-broken.yaml --role coder --timeout 5" \
             "selfcheck --config /tmp/s11-broken.yaml --role coder"; do
    echo "=== fa $cmd"
    fa $cmd >/tmp/s11-out.txt 2>&1; rc=$?
    echo "EXIT=$rc"
    grep -qi "traceback" /tmp/s11-out.txt \
      && echo "  *** TRACEBACK LEAKED ***" && tail -5 /tmp/s11-out.txt \
      || echo "  no traceback (good)"
    head -3 /tmp/s11-out.txt
  done

  echo "=== fa run with malformed config (expect 2, no traceback) ==="
  fa run --task ping --run-id s11-yamlprobe --config /tmp/s11-broken.yaml \
         --max-turns 1 >/tmp/s11-run-out.txt 2>&1; echo "EXIT=$?"
  grep -qi "traceback" /tmp/s11-run-out.txt \
    && echo "  *** TRACEBACK LEAKED ***" || echo "  no traceback (good)"
  head -3 /tmp/s11-run-out.txt

  echo "=== fa egress-proxy with malformed config (expect 2, no port bound) ==="
  # The 5th and most deployment-relevant caller: this is what the PROXY
  # CONTAINER runs at startup, so a traceback here is a crash-loop rather than
  # a readable error. The config load precedes serve(), so no port is bound.
  fa egress-proxy --models /tmp/s11-broken.yaml \
                  --secrets /run/secrets/fa_proxy_token \
                  --token-file /run/secrets/fa_proxy_token \
                  --listen 127.0.0.1:59999 >/tmp/s11-ep-out.txt 2>&1
  echo "EXIT=$?"
  grep -qi "traceback" /tmp/s11-ep-out.txt \
    && echo "  *** TRACEBACK LEAKED ***" || echo "  no traceback (good)"
  head -3 /tmp/s11-ep-out.txt
' 2>&1 | tee "$EVID/04d-yaml-all-commands.txt"
```

**Expect:** every command exits **2** with a structured message and **no**
`Traceback`. Before S10c all five printed one.

### 4e. `fa probe` — the real provider path (~10 tokens per role)

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  fa probe --all-roles --timeout 30 2>&1 | tee "$EVID/04e-probe.txt"
echo "PROBE_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/04e-probe.txt"
```

**Expect:** exit 0 and an `OK` line per role. This is the first real provider
call and it proves the whole chain — agent → proxy → provider → back — with the
key injected *outside* the agent container.

> **`${PIPESTATUS[0]}`, not `$?` (R12).** Every host-side capture in this sheet
> pipes the command into `tee`, and `$?` after a pipeline reports the **last**
> element — `tee`, which essentially always succeeds. The live run showed
> `fa probe: FAIL` on the planner role and `PROBE_EXIT=0` in the same paste.
> `_cmd_probe` returns `1 if any_failure else 0` (`cli.py:2982`), so the true
> exit was 1. Fixed at all seven host-side sites; the in-container
> `; echo "EXIT=$?"` forms have no pipe and were always correct.

**Classification:** a failure here is *proxy* or *provider*, and S11.5 onward
will not work until it is resolved. **This is a blocking step.**

---

## Step S11.5 — The `fa run` matrix on the deployed path (S11-G6)

Traces-to: **parent Do #4, #5, #6**, S11-G6. Depends-on: S11.4e.

### 5a. Collision check — never overwrite prior evidence

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  for r in s11-run-a s11-run-b s11-run-c s11-run-d \
           s11-wf-linear s11-wf-repair s11-wf-quiet s11-autorun; do
    [ -e "/home/fa/.fa/session-log/$r" ] \
      && echo "COLLISION: $r — run §Rollback first" || echo "clear: $r"
  done
' 2>&1 | tee "$EVID/05a-collisions.txt"
```

**STOP if any COLLISION.** Run §Rollback, then return.

### 5b. Cell A — bodies OFF (baseline). Creates the session.

```bash
docker compose -f "$COMPOSE" exec -T -e FA_DEBUG_LLM_BODIES=0 "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --run-id s11-run-a --role coder --max-turns 1 \
         --output-mode console 2>&1 | tee "$EVID/05b-run-a.txt"
echo "EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/05b-run-a.txt"

# Capture the generated session id by finding the session whose DB holds this
# run — NOT by picking the newest directory, which races other activity.
SID=$(docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<"PY"
import json, pathlib, sqlite3
best = ""
for m in sorted(pathlib.Path("/home/fa/.fa/sessions").glob("*/manifest.json")):
    try:
        d = json.loads(m.read_text())
    except Exception:
        continue
    if d.get("status") != "active":
        continue
    try:
        n = sqlite3.connect(m.parent / "session.db").execute(
            "SELECT COUNT(*) FROM event_log WHERE run_id=?", ("s11-run-a",)).fetchone()[0]
    except Exception:
        n = 0
    if n:
        best = d["session_id"]
print(best)
PY' | tr -d '\r' | tail -1)
export SID
echo "SID=$SID" | tee "$EVID/05b-sid.txt"
```

**Expect:** exit 0; `SID` non-empty, shaped `session-<32 hex>`.
**STOP if `SID` is empty** — every later step keys on it.

### 5c. Cell B — bodies ON (the env-mode question, parent Do #4)

```bash
# Parent Do #4 is explicit: a host-only export must NOT be assumed to reach an
# already-running container. Prove both directions.
echo "=== B1: host export only (must NOT enable capture) ==="
FA_DEBUG_LLM_BODIES=1 docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  sh -lc 'echo "in-container FA_DEBUG_LLM_BODIES=${FA_DEBUG_LLM_BODIES:-<unset>}"' \
  2>&1 | tee "$EVID/05c-env-host-only.txt"

echo "=== B2: explicit -e (MUST reach the process) ==="
docker compose -f "$COMPOSE" exec -T -e FA_DEBUG_LLM_BODIES=1 "$SERVICE" \
  sh -lc 'echo "in-container FA_DEBUG_LLM_BODIES=${FA_DEBUG_LLM_BODIES:-<unset>}"' \
  2>&1 | tee -a "$EVID/05c-env-host-only.txt"

echo "=== B3: the run with capture ON ==="
docker compose -f "$COMPOSE" exec -T -e FA_DEBUG_LLM_BODIES=1 "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --run-id s11-run-b --role coder --max-turns 1 \
         --session-id "$SID" 2>&1 | tee "$EVID/05c-run-b.txt"
echo "EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/05c-run-b.txt"
```

**Expect:** B1 prints `<unset>` (or `0`) — the host export does **not** cross
the exec boundary; B2 prints `1`; B3 exits 0.

### 5d. Cell C — `--detail debug` must NOT enable body capture

```bash
docker compose -f "$COMPOSE" exec -T -e FA_DEBUG_LLM_BODIES=0 "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --run-id s11-run-c --role coder --max-turns 1 \
         --session-id "$SID" --detail debug 2>&1 | tee "$EVID/05d-run-c.txt"
echo "EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/05d-run-c.txt"
```

**Expect:** exit 0, **no** `llm_bodies.jsonl` for `s11-run-c`. This is the
coupling risk: verbosity and secret-capture must be independent controls.

### 5e. Cell D — `--output-mode quiet` stdout contract (I-38 / S8.4)

```bash
# $SID is passed as an env var, not spliced into the quoted script: the
# '"'"'-style nesting is fragile and this sheet already lost one block to it.
docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" sh -lc '
  fa run --task "Reply with the single word: pong" \
         --run-id s11-run-d --role coder --max-turns 1 \
         --session-id "$SID" --output-mode quiet \
         >/tmp/s11-quiet-stdout.txt 2>/tmp/s11-quiet-stderr.txt
  echo "EXIT=$?"
  echo "--- stdout bytes: $(wc -c < /tmp/s11-quiet-stdout.txt)"
  echo "--- stderr bytes: $(wc -c < /tmp/s11-quiet-stderr.txt)"
  echo "--- stdout content (this IS the payload, safe to show):"
  cat /tmp/s11-quiet-stdout.txt
  echo "--- does stdout contain a status line? (it must NOT)"
  grep -qE "^(OK|ERROR): " /tmp/s11-quiet-stdout.txt \
    && echo "  STATUS LINE ON STDOUT — I-38 regression" \
    || echo "  clean: no status line on stdout"
' 2>&1 | tee "$EVID/05e-run-d-quiet.txt"
```

**Expect:** stdout carries the model's payload only; the `OK: ...` status line
is on **stderr**. S8.4 fixed this; I-38 is the regression it closes.

### 5f. The body gate, by COUNT only (never content)

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  for r in s11-run-a s11-run-b s11-run-c s11-run-d; do
    f="/home/fa/.fa/session-log/$r/llm_bodies.jsonl"
    if [ -f "$f" ]; then
      echo "$r: PRESENT  rows=$(wc -l < "$f")  bytes=$(wc -c < "$f")  mode=$(stat -c %a "$f")"
    else
      echo "$r: absent"
    fi
  done
  echo "--- positive control: the runs really happened ---"
  for r in s11-run-a s11-run-b s11-run-c s11-run-d; do
    d="/home/fa/.fa/session-log/$r"
    [ -d "$d" ] && echo "$r: run dir present, $(ls -1 "$d" | wc -l) artifacts" \
                || echo "$r: RUN DIR MISSING — the run did not happen"
  done
' 2>&1 | tee "$EVID/05f-body-gate.txt"
```

**Expect:** `s11-run-b` **PRESENT** with rows ≥ 1; a, c, d **absent**.

> **The positive control is not optional.** S7's execution found that its C4
> step asserted an absence with no witness — a crashed run would have produced
> the passing string. An absence assertion without a liveness check is
> decoration.

---

## Step S11.6 — Artifact posture, before vs after (S11-G5)

Traces-to: S11-G5, **I-36 / Q56**. Depends-on: S11.5.

The S10c.3 tightening pass has now run at least four times (once per `fa run`).

```bash
# 6a. In-container view of the artifacts this sheet just created.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "=== files (expect 0600) ==="
  find /home/fa/.fa -type f \
       \( -name "*.jsonl" -o -name "*.db" -o -name "manifest.json" \) \
       -printf "%m %p\n" 2>/dev/null | sort | head -40
  echo "=== directories (expect 0700) ==="
  find /home/fa/.fa -type d -printf "%m %p\n" 2>/dev/null | sort | head -20
  echo "=== ANY group/other-accessible entry left? ==="
  find /home/fa/.fa \( -perm -g+r -o -perm -o+r \) ! -type l \
       -printf "%m %p\n" 2>/dev/null | tee /tmp/s11-permissive.txt | head -20
  echo "--- count: $(wc -l < /tmp/s11-permissive.txt)"
' 2>&1 | tee "$EVID/06a-modes-AFTER-container.txt"

# 6b. Host view + the diff that proves the retroactive repair.
sudo find "$STATE" -printf '%m %y %u:%g %p\n' 2>/dev/null \
  | sort -k4 > "$EVID/06b-modes-AFTER.txt"
# Same portable form as S11.1 — see the note there.
awk '$1 ~ /^[0-7][0-7][0-7]$/ { g=substr($1,2,1); o=substr($1,3,1); if (g!="0"||o!="0") print }' \
  "$EVID/06b-modes-AFTER.txt" > "$EVID/06b-permissive-AFTER.txt"

echo "permissive BEFORE: $(wc -l < "$EVID/01-permissive-BEFORE.txt")"
echo "permissive AFTER : $(wc -l < "$EVID/06b-permissive-AFTER.txt")"
echo "=== entries that were repaired (in BEFORE, not in AFTER) ==="
comm -23 <(awk '{print $NF}' "$EVID/01-permissive-BEFORE.txt" | sort) \
         <(awk '{print $NF}' "$EVID/06b-permissive-AFTER.txt" | sort) \
  | tee "$EVID/06b-repaired.txt" | head -30
echo "--- repaired count: $(wc -l < "$EVID/06b-repaired.txt")"

# 6c. Symlink safety (RK11): the pass must never chmod a link's target.
sudo find "$STATE" -type l -printf '%p -> %l\n' 2>/dev/null \
  | tee "$EVID/06c-symlinks.txt"
echo "(if any symlinks exist, verify their TARGETS were not modified)"
```

**Expect (corrected 2026-08-03, R13):** `06b-repaired.txt` lists the entries the
Q56 pass tightened, and `permissive AFTER` is **1, not 0** — see below.

**`models.yaml` cannot be repaired and must not be counted as a failure.**
`docker-compose.fa.yml:95-100` mounts it `read_only: true` at
`/home/fa/.fa/models.yaml`, nested inside the writable state dir. The pass walks
the whole root, so it *reaches* the file, but `Path.chmod` raises `OSError`
(`EROFS`/`EPERM`) and `paths.py:130` catches and skips it — deliberately
best-effort, since "a mode we cannot change is not worth failing a run over".

Predicted for the reference deployment, from an 11-entry BEFORE:

| entry | before → after |
|---|---|
| `.env.fa.sha256` | `664` → `600` |
| `global_history.db` | `644` → `600` |
| `session-log/`, `sessions/` | `755` → `700` |
| 3 × session dirs | `755` → `700` |
| 3 × `session.db` | `644` → `600` |
| **`models.yaml`** | **`644` → `644` (read-only mount, expected)** |

So **repaired = 10, permissive AFTER = 1**. A `permissive AFTER` of 0 would
actually be surprising — it would mean the ro mount is not in effect.

**Classification:** `models.yaml` remaining `644` is **not** a defect. It is
world-readable *routing config* containing env-var **names**, never secret
values — S11.4a already proved that. Any *other* leftover entry is a real
finding.

**If BEFORE was already 0**, record that the retroactive half had nothing to
repair on this host — the creation-mode half is still proven by 6a.

**Classification:** any remaining group/other-readable artifact is
*filesystem permission*.

---

## Step S11.6d — RK11: prove the symlink guard on live data (optional, ~30 s)

Traces-to: S11-G5 / RK11. Depends-on: S11.6. **Operator-gated: this deliberately
creates a symlink inside the live state tree.**

S11.6c found no symlinks, so the guard was never exercised — a *safe* outcome
but **not** evidence. `paths.py:123` skips symlinks before any `stat`/`chmod`
because `os.chmod` FOLLOWS links and `follow_symlinks=False` raises
`NotImplementedError` on Linux. Without the skip, a crafted link inside the
state root would have its **target's** mode rewritten.

The bait lives in `/tmp` — *outside* the state root — so a guard failure is
visibly a containment breach, not an internal mode change.

```bash
# 6d-1. Bait: a file OUTSIDE the state root, at a mode tighten would change.
sudo rm -f /tmp/rk11-target /srv/first-agent/state/rk11-evil
printf 'not ours\n' | sudo tee /tmp/rk11-target >/dev/null
sudo chmod 644 /tmp/rk11-target
sudo chown fa:fa /tmp/rk11-target

# 6d-2. The link, inside the walked tree, owned by the agent user.
sudo -u fa ln -s /tmp/rk11-target /srv/first-agent/state/rk11-evil

echo "=== BEFORE ==="
stat -c '%a %n' /tmp/rk11-target /srv/first-agent/state/rk11-evil \
  | tee "$EVID/06d-rk11-before.txt"

# 6d-3. Pre-check: the link must be INSIDE the tree the pass walks, or this
#       test proves nothing. (The vacuity guard — same discipline as S11.1's
#       1b-check.)
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  test -L /home/fa/.fa/rk11-evil \
    && echo "PRECHECK OK: link is visible inside the container" \
    || echo "PRECHECK FAILED: link not visible — this test would be vacuous"
' | tee -a "$EVID/06d-rk11-before.txt"

# 6d-4. Any fa run triggers tighten_fa_artifact_modes (cli.py:2423).
docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  fa run --task "Reply with the single word: pong" \
         --run-id s11-rk11 --role coder --max-turns 1 \
         >/dev/null 2>&1
echo "RUN_EXIT=$?"

# 6d-5. The oracle: the TARGET's mode is unchanged.
echo "=== AFTER ==="
stat -c '%a %n' /tmp/rk11-target /srv/first-agent/state/rk11-evil \
  | tee "$EVID/06d-rk11-after.txt"

if [ "$(stat -c '%a' /tmp/rk11-target)" = "644" ]; then
  echo "RK11 PASS: the pass did not follow the symlink"
else
  echo "RK11 FAIL: target mode changed to $(stat -c '%a' /tmp/rk11-target) \
— the pass followed a link OUT of the state root"
fi | tee -a "$EVID/06d-rk11-after.txt"

# 6d-6. Cleanup — leave the tree as found.
sudo rm -f /srv/first-agent/state/rk11-evil /tmp/rk11-target
```

**Expect:** `PRECHECK OK`; target stays `644`; `RK11 PASS`.

**Why `644` is the right bait mode:** it has group/other bits set, so it is
exactly the kind of entry the pass *wants* to tighten. A bait at `600` would be
skipped by the `if not current & 0o077: continue` fast-path
(`paths.py:127`) and the test would pass without ever reaching the symlink
branch — vacuous.

**If it FAILS:** `/tmp/rk11-target` becomes `600`. That is a containment breach —
a routine housekeeping pass reaching outside its own root — and is
**severity HIGH, stop the sheet**. Note this is exactly the mutation that
survived until S10c.3 added the guard.

**Note:** the link is created as `fa`, matching how a compromised agent would
create one. Creating it as root would test a path the agent cannot reach.

**The oracle was kill-checked before this step shipped** (sandbox, 2026-08-03):

| harness | target mode after | meaning |
|---|---|---|
| real `tighten_fa_artifact_modes` | `644` (unchanged), `tightened=0` | guard holds |
| same loop with the `is_symlink()` guard **removed** | **`700`** | oracle detects the breach |

So a `RK11 PASS` here is a real signal, not a check that cannot fail. Note the
sabotaged run rewrote the target to `700` — the *directory* mode — because
`chmod` followed the link and applied the dir rule to a file outside the root.

---

## Step S11.7 — The workflow verdict matrix (S11-G4) — **the expensive step**

Traces-to: **Q35b / S10c.2**, S11-G4. Depends-on: S11.5.
**Cost: three full planner→coder→eval pipelines, one with repair rounds.**

This is the only place the new exit-code contract meets a **real** evaluator
verdict. Locally it was proven with a scripted transport.

### 7a. Linear workflow — whatever the real evaluator decides

```bash
# NOTE (R14): `roles` and `task` are POSITIONAL, in that order. There is no
# `--task` flag — argparse rejects it as ambiguous against --task-planner /
# --task-coder / --task-eval and exits 2 before running anything.
docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  fa workflow planner,coder,eval \
              "Add a docstring to one small function; do not change behaviour." \
              --run-id s11-wf-linear --mode linear --max-turns 6 \
              2>&1 | tee "$EVID/07a-wf-linear.txt"
echo "WF_LINEAR_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/07a-wf-linear.txt"
```

### 7b. Repair mode — deliberately hard to satisfy, to drive a non-PASS verdict

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" \
  fa workflow planner,coder,eval \
              "Refactor the entire codebase for perfect performance and prove it formally." \
              --run-id s11-wf-repair --mode repair --max-repairs 2 --max-turns 4 \
              2>&1 | tee "$EVID/07b-wf-repair.txt"
echo "WF_REPAIR_EXIT=${PIPESTATUS[0]}" | tee -a "$EVID/07b-wf-repair.txt"
```

**An impossible task is the point**: it should exhaust the repair budget and
land on a non-`DONE` terminal status, which is the exit-1 path.

### 7c. THE ASSERTION — exit code vs artifacts must agree three ways

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<"PY"
import json, pathlib, sqlite3
root = pathlib.Path("/home/fa/.fa")
gh = root / "global_history.db"
for run in ("s11-wf-linear", "s11-wf-repair", "s11-wf-quiet"):
    d = root / "session-log" / run
    if not d.is_dir():
        print(f"{run}: NO RUN DIR"); continue
    fs = d / "flow_state.json"
    er = d / "eval_report.json"
    status  = json.loads(fs.read_text())["status"] if fs.is_file() else "NO_FLOW_STATE"
    verdict = json.loads(er.read_text()).get("verdict") if er.is_file() else "NO_EVAL_REPORT"
    row = "NO_GLOBAL_HISTORY_DB"
    if gh.is_file():
        try:
            # Table name is runs -- verified against the DDL in
            # global_history.py, not guessed. A wrong table name would raise on
            # every run and read as a product failure.
            row = sqlite3.connect(gh).execute(
                "SELECT stop_reason, exit_code FROM runs WHERE run_id=?", (run,)).fetchone()
            if row is None:
                row = "NO ROW FOR THIS RUN"
        except Exception as exc:
            row = f"QUERY FAILED: {exc}"
    expected = 0 if status == "DONE" else 1
    print(f"{run}: verdict={verdict} status={status} row={row} EXPECTED_EXIT={expected}")
PY' 2>&1 | tee "$EVID/07c-verdict-agreement.txt"
```

**Expect, per run — all four must agree:**

| terminal status | expected exit | `stop_reason` |
|---|---|---|
| `DONE` | **0** | `workflow_complete` |
| `FAILED` (BLOCKED) | **1** | `workflow_failed` |
| `REPAIR_REQUIRED` | **1** | `workflow_repair_required` |
| `REPLAN_REQUIRED` | **1** | `workflow_replan_required` |

Compare `EXPECTED_EXIT` against the `WF_*_EXIT` values you recorded.
**A mismatch is the single most important finding this sheet can produce** —
classify as *authority*.

> **If both workflows return PASS/`DONE`,** the exit-1 path is unproven on real
> data. Say so, and either re-run 7b with a harder task or record it as a
> residual gap. Do **not** claim the contract is verified from exit 0 alone.

### 7d. The consumer contract — a real `&&` chain

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "=== does a shell chain now STOP on a rejected verdict? ==="
  if fa workflow planner,coder,eval "Reply with the single word: pong" \
                 --run-id s11-wf-quiet --mode linear --max-turns 3 \
                 --output-mode quiet >/tmp/s11-wf-out.txt 2>/tmp/s11-wf-err.txt
  then
      echo "CHAIN CONTINUED (exit 0) — verdict was DONE"
  else
      echo "CHAIN STOPPED (exit $?) — this is the Q35b contract working"
  fi
  echo "--- stdout bytes: $(wc -c < /tmp/s11-wf-out.txt)"
  echo "--- stderr bytes: $(wc -c < /tmp/s11-wf-err.txt)"
' 2>&1 | tee "$EVID/07d-chain-contract.txt"
```

**Expect:** the branch taken matches the verdict. This is the operator-visible
behaviour that changed — `fa workflow && deploy` no longer proceeds on rejected
code.

---

## Step S11.8 — Trace integrity, stats projections, request anatomy (S11-G7, S11-G9)

Traces-to: S11-G7, S11-G9, **I-37**. Depends-on: **S11.5** (corrected 2026-08-03 — see §Re-sequencing).

> The original `Depends-on: S11.7` was **sequencing, not data**. Every run_id this step touches (`s11-run-b`, plus its own `s11-gh` / `s11-se` / `s11-so` probes) comes from S11.5, which passed. Nothing here reads a `s11-wf-*` artifact. **S11.8 can run now.**

### 8a. Authority vs mirror, and correlation on real rows

```bash
# $SID is passed as a container env var rather than string-interpolated into
# the heredoc: nested quote escaping here is fragile and was the source of a
# defect during this sheet's rehearsal.
docker compose -f "$COMPOSE" exec -T -e SID="$SID" "$SERVICE" sh -lc '
python - <<"PY"
import json, os, pathlib, sqlite3
sid = os.environ["SID"]
db  = pathlib.Path("/home/fa/.fa/sessions/%s/session.db" % sid)
con = sqlite3.connect(db)

print("=== rows per run (authority) ===")
for run, n in con.execute(
        "SELECT run_id, COUNT(*) FROM event_log GROUP BY run_id ORDER BY run_id"):
    print(f"  {run}: {n}")

print("=== authority vs JSONL mirror ===")
for run, n in con.execute(
        "SELECT run_id, COUNT(*) FROM event_log GROUP BY run_id ORDER BY run_id"):
    p = pathlib.Path(f"/home/fa/.fa/session-log/{run}/events.jsonl")
    m = sum(1 for _ in p.open()) if p.is_file() else "NO_MIRROR"
    verdict = "MATCH" if m == n else "MISMATCH"
    print("  %s: db=%s jsonl=%s %s" % (run, n, m, verdict))

print("=== orphan check (rows with no run_id) ===")
print("  orphans:", con.execute(
    "SELECT COUNT(*) FROM event_log WHERE run_id IS NULL OR run_id=\"\"").fetchone()[0])
print("  (positive control) total rows:", con.execute(
    "SELECT COUNT(*) FROM event_log").fetchone()[0])

print("=== session_id stamping (S4-F1 regression) ===")
print("  distinct session_id:", con.execute(
    "SELECT DISTINCT session_id FROM event_log").fetchall())

print("=== correlation: events carrying a tool_call_id ===")
print("  with tool_call_id:", con.execute(
    "SELECT COUNT(*) FROM event_log WHERE tool_call_id IS NOT NULL AND tool_call_id<>\"\"").fetchone()[0])

print("=== stray authorities anywhere on disk ===")
import subprocess
for base in ("/home/fa", "/sessions", "/tmp"):
    b = pathlib.Path(base)
    if not b.is_dir():
        print(f"  {base}: PATH ABSENT (could not look)"); continue
    hits = list(b.rglob("session.db"))
    print(f"  {base}: {len(hits)} session.db")
    for h in hits[:10]:
        print("   ", h)
PY' 2>&1 | tee "$EVID/08a-trace-integrity.txt"
```

**Expect:** db == jsonl per run; **orphans = 0** with a non-zero total as the
positive control; `distinct session_id` is `[('session-...',)]`, never `[('',)]`;
`session.db` files only under `/home/fa/.fa/sessions/`.

> **The `PATH ABSENT` branch matters.** S7's C7 used `2>/dev/null` and could not
> distinguish *searched-and-found-nothing* from *could-not-look*. This version
> says which.

### 8b. `fa stats` — S9 projections against real deployed data

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  echo "=== per-run JSON projection ==="
  fa stats --run-id s11-run-b --output json > /tmp/s11-stats.json 2>/tmp/s11-stats.err
  echo "EXIT=$?  stdout_bytes=$(wc -c < /tmp/s11-stats.json)"
  python -c "
import json,sys
d=json.load(open(\"/tmp/s11-stats.json\"))
print(\"  keys:\", sorted(d)[:12])
print(\"  run_id:\", d.get(\"run_id\"), \"turns:\", d.get(\"turns\"))
print(\"  tokens in/out:\", d.get(\"total_in\"), d.get(\"total_out\"))
"
  echo "=== global history (cross-run projection) ==="
  fa stats --global-history --output json > /tmp/s11-gh.json 2>&1
  echo "EXIT=$?"
  python -c "
import json
rows=json.load(open(\"/tmp/s11-gh.json\"))
print(\"  rows:\", len(rows))
for r in rows[-6:]:
    print(\"   \", r.get(\"run_id\"), r.get(\"stop_reason\"), \"exit=\", r.get(\"exit_code\"))
"
  echo "=== console rendering must go to STDERR, stdout stays parseable ==="
  fa stats --run-id s11-run-b --output text >/tmp/s11-so.txt 2>/tmp/s11-se.txt
  echo "  stdout_bytes=$(wc -c < /tmp/s11-so.txt) stderr_bytes=$(wc -c < /tmp/s11-se.txt)"
' 2>&1 | tee "$EVID/08b-stats.txt"
```

**Expect:** valid JSON on stdout; `global-history` rows include the S11 runs
with the **exit codes S11.7 recorded**; the text renderer writes to stderr with
stdout empty.

### 8c. Request anatomy — data for the open I-37 question (**sizes only**)

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
python - <<"PY"
import json, pathlib
p = pathlib.Path("/home/fa/.fa/session-log/s11-run-b/llm_bodies.jsonl")
if not p.is_file():
    print("no body file - cell B did not capture"); raise SystemExit

line = p.open().readline()
row  = json.loads(line)
print("captured row bytes:", format(len(line), ","))
print("row keys:", sorted(row))

# Schema VERIFIED against a real captured row, not guessed. The key is
# request_body (a dict), alongside response_body, logical_call_id,
# attempt_index, provider, slug, ts, kind.
rb = row.get("request_body")
if isinstance(rb, str):
    rb = json.loads(rb)
if not isinstance(rb, dict):
    print("unexpected request_body type:", type(rb).__name__); raise SystemExit

msgs = rb.get("messages", [])
print("--- %d messages: ROLE and SIZE only ---" % len(msgs))
total = 0
sizes = []
for i, m in enumerate(msgs):
    c = m.get("content")
    n = len(c) if isinstance(c, str) else len(json.dumps(c))
    total += n
    sizes.append(n)
    # First 40 chars ONLY, punctuation-stripped, to identify WHICH block this
    # is (base prompt vs AGENTS.md map vs tool listing). Never the task text.
    head = c[:40].replace(chr(10), " ") if isinstance(c, str) else "<structured>"
    safe = "".join(ch if (ch.isalnum() or ch in " .:/-_") else "?" for ch in head)
    print("  [%d] role=%-9s bytes=%8s  starts: %s" % (i, m.get("role"), format(n, ","), safe))

tools = rb.get("tools")
tb = len(json.dumps(tools)) if tools else 0
print("  native tools array bytes: %8s  count=%d" % (format(tb, ","), len(tools) if tools else 0))

grand = total + tb
print("--- totals: messages=%s + tools=%s = %s" % (format(total, ","), format(tb, ","), format(grand, ",")))
if grand:
    for i, n in enumerate(sizes):
        print("    [%d] %5.1f%%" % (i, 100.0 * n / grand))
    print("    tools %5.1f%%" % (100.0 * tb / grand))
print("--- I-37 watch: which single component is largest? ---")
PY' 2>&1 | tee "$EVID/08c-request-anatomy.txt"
```

**Expect:** a size breakdown per message role. **This prints the first ~40
characters of each system message only to identify which block it is** — never
user task text or model output. If any line looks like real content, stop and
redact before sharing.

**Purpose:** I-37 recorded the `AGENTS.md` map at **48.4%** of a live request
and the duplicated tool schemas at 36%. S10c.5 removed ~3.1 KB of whitespace
from the tool block; this step measures the *current* shape so the remaining
I-37 work is planned against fresh numbers.

---

## Step S11.9 — Entrypoint failure modes (S11-G8)

Traces-to: **parent Do #8**, S11-G8. Depends-on: S11.8. **No workflow dependency** — entrypoint failure modes are independent of the verdict matrix.

> **Rewritten after a code read of `scripts/fa-entrypoint.sh` (§7, R6–R8).**
> The first draft of this step would have produced misleading results for
> three separate reasons. All three are structural, not typos:
>
> 1. **`STATUS_FILE` moves mid-script.** It is
>    `${FA_STATUS_FILE:-${WORKSPACE}/.fa/entrypoint-status.txt}` at line 17
>    with `WORKSPACE=/workspace`, and is only redirected to
>    `/sessions/<id>/.fa/...` *after* the session clone succeeds (line 190).
>    `_validate_session_id` runs at line **157**, i.e. **before** the clone —
>    so the bad-session-id case still points at `/workspace`, which has **no
>    mount** on a `read_only: true` rootfs. `_write_status` then hits its
>    `mkdir -p` failure branch, logs `WARN`, and **returns without writing**.
>    Looking for a status file there finds nothing, and "no file" would have
>    been misread as "the entrypoint did not handle it". Verified by
>    simulating both regimes.
>    **Fix:** pass `FA_STATUS_FILE` explicitly to a writable path.
> 2. **`docker compose run` inherits the real bind mounts**, so each throwaway
>    container git-clones a fresh `/sessions/session-<ts>-<pid>` and — worse —
>    overwrites `/sessions/.active`, which `scripts/fa:39` reads to find the
>    live workspace. Four cases would leave four abandoned clones and an
>    `.active` pointing at a deleted directory.
>    **Fix:** snapshot `.active` before, restore after, and clean the clones.
> 3. **Only `bad-session-id` fails before the clone.** The other three fail in
>    `_load_task` (line 243), *after* it. Their status files therefore land in
>    different places. The step now states the expected path per case instead
>    of globbing hopefully.

### 9a. Snapshot the state this step is about to perturb

```bash
docker compose -f "$COMPOSE" ps first-agent | tee "$EVID/09a-before-break.txt"

# .active is read by scripts/fa to locate the live workspace. The throwaway
# containers below WILL overwrite it; capture it so 9e can put it back.
sudo cat /srv/first-agent/sessions/.active 2>/dev/null \
  | tee "$EVID/09a-active-before.txt" || echo "(no .active file)"

# Existing session clones, so 9e can delete only what THIS step created.
sudo ls -1 /srv/first-agent/sessions/ 2>/dev/null | sort \
  > "$EVID/09a-sessions-before.txt"
wc -l < "$EVID/09a-sessions-before.txt" | sed 's/^/session dirs before: /'
```

### 9b. Four invalid configurations, each with its status file at a KNOWN path

```bash
# FA_STATUS_FILE is set explicitly to /tmp (a tmpfs that always exists and is
# writable) so the status file lands somewhere readable REGARDLESS of which
# side of the session clone the failure occurs on. Without this, the
# bad-session-id case cannot write one at all — see the note above.
for CASE in both-tasks bad-task-file empty-task bad-session-id; do
  echo "=================== CASE: $CASE ==================="
  case "$CASE" in
    both-tasks)     EXTRA=(-e FA_TASK=hello -e FA_TASK_FILE=/tmp/x.txt) ;;
    bad-task-file)  EXTRA=(-e FA_TASK_FILE=/nonexistent/task.txt) ;;
    empty-task)     EXTRA=(-e FA_TASK="   ") ;;
    bad-session-id) EXTRA=(-e FA_TASK=hello -e FA_SESSION_ID="../escape") ;;
  esac

  timeout 120 docker compose -f "$COMPOSE" run --rm --no-deps \
    -e FA_AUTO_RUN=1 \
    -e FA_STATUS_FILE=/tmp/s11-entrypoint-status.txt \
    "${EXTRA[@]}" \
    --entrypoint sh "$SERVICE" -lc '
      /usr/local/bin/fa-entrypoint.sh &
      EP=$!
      # Poll rather than sleep a fixed time: standby is sleep-infinity, so
      # the script never exits and a fixed sleep is either flaky or slow.
      for i in $(seq 1 30); do
        [ -f /tmp/s11-entrypoint-status.txt ] && break
        sleep 1
      done
      echo "--- STATUS FILE ---"
      if [ -f /tmp/s11-entrypoint-status.txt ]; then
        cat /tmp/s11-entrypoint-status.txt
      else
        echo "NO STATUS FILE WRITTEN (unexpected: FA_STATUS_FILE was writable)"
      fi
      echo "--- is the entrypoint still alive (i.e. in standby)? ---"
      kill -0 $EP 2>/dev/null && echo "ALIVE -> reached standby (CORRECT)" \
                              || echo "EXITED -> did NOT reach standby"
      echo "--- did it start an fa run anyway? (it must NOT) ---"
      pgrep -af "fa run" || echo "no fa run process (CORRECT)"
    '
  echo "--- (a 120s timeout here also indicates standby, which is correct)"
done 2>&1 | tee "$EVID/09b-entrypoint-failures.txt"
```

**Expect, for every case:** the log line
`Invalid auto-run configuration: <detail>`; a status file containing
`exit_code=2`, `status=INVALID_CONFIG` and a `detail=` line; the entrypoint
**ALIVE** in standby; and **no `fa run` process**.

The last check is the one that matters most — parent Do #8 asks whether the
entrypoint *continues with an ambiguous workspace*. "Reached standby" and
"did not start a run" are two different claims and both are asserted.

### 9c. The clone-failure path (a different `_fail_to_standby` call site)

```bash
# Cases in 9b fail in _load_task (line 243) or _validate_session_id (157).
# This one exercises line 177 — the git-clone failure — which is the branch
# that also has to REMOVE the partial clone before standing by.
timeout 120 docker compose -f "$COMPOSE" run --rm --no-deps \
  -e FA_AUTO_RUN=1 -e FA_TASK=hello \
  -e FA_STATUS_FILE=/tmp/s11-clone-status.txt \
  -e GIT_SSH_COMMAND=/bin/false \
  --entrypoint sh "$SERVICE" -lc '
    # Make the clone source unusable without touching the real /repo mount.
    export GIT_CONFIG_GLOBAL=/tmp/broken-gitconfig
    printf "[url \"nonexistent://\"]\n  insteadOf = file://\n" > "$GIT_CONFIG_GLOBAL"
    /usr/local/bin/fa-entrypoint.sh &
    EP=$!
    for i in $(seq 1 30); do
      [ -f /tmp/s11-clone-status.txt ] && break
      sleep 1
    done
    echo "--- STATUS ---"; cat /tmp/s11-clone-status.txt 2>/dev/null \
      || echo "no status file"
    echo "--- partial clone cleaned up? ---"
    ls -1 /sessions/ | tail -5
    kill -0 $EP 2>/dev/null && echo "ALIVE -> standby (CORRECT)" || echo "EXITED"
  ' 2>&1 | tee "$EVID/09c-clone-failure.txt"
```

**Expect:** `git clone/checkout failed for /sessions/<id>`, a status file, no
leftover partial clone for that id, and standby.

> **If the clone SUCCEEDS anyway**, this case proved nothing — record it as a
> sheet defect rather than as a pass. The `insteadOf` trick depends on git
> honouring `GIT_CONFIG_GLOBAL`, which is the documented behaviour but is not
> something this sheet could rehearse without a daemon.

### 9d. Positive control — a VALID auto-run RUNS THE TASK before standing by

```bash
# Without a positive control every assertion above is satisfiable by an
# entrypoint that stands by unconditionally.
#
# NOTE, corrected during review: a VALID auto-run also ends in _standby
# (fa-entrypoint.sh:296, "Auto-run completed once; transitioning to
# inspectable stand-by state"). So "reaches standby" does NOT distinguish
# success from failure — the discriminator is the STATUS LABEL and whether the
# task actually ran:
#     invalid -> status=INVALID_CONFIG, exit_code=2, no fa run child
#     valid   -> status=RUNNING then SUCCESS/FAILED, with a real run_id
# Asserting standby alone would have been a check that cannot fail.
timeout 240 docker compose -f "$COMPOSE" run --rm -d \
  --name s11-autorun-probe \
  -e FA_AUTO_RUN=1 \
  -e FA_TASK="Reply with the single word: pong" \
  -e FA_RUN_ID=s11-autorun \
  -e FA_MAX_TURNS=1 \
  -e FA_STATUS_FILE=/tmp/s11-good-status.txt \
  "$SERVICE" >/dev/null

# Poll for the terminal status label rather than sleeping a fixed time.
for i in $(seq 1 40); do
  LABEL=$(docker exec s11-autorun-probe sh -lc \
    'grep -h "^status=" /tmp/s11-good-status.txt 2>/dev/null | tail -1' 2>/dev/null)
  case "$LABEL" in status=SUCCESS|status=FAILED) break ;; esac
  sleep 5
done

docker exec s11-autorun-probe sh -lc '
  echo "--- final status file ---"; cat /tmp/s11-good-status.txt
  echo "--- did the run produce a run dir? ---"
  ls -1 /home/fa/.fa/session-log/s11-autorun 2>/dev/null \
    || echo "NO RUN DIR — the task did not actually run"
' 2>&1 | tee "$EVID/09d-valid-autorun.txt"

docker logs s11-autorun-probe 2>&1 | tail -20 >> "$EVID/09d-valid-autorun.txt"
docker rm -f s11-autorun-probe >/dev/null 2>&1 || true
```

**Expect:** `status=SUCCESS` (or `FAILED` with a real `exit_code` if the model
declined), `run_id=s11-autorun` in the status file, and a populated run
directory. **`status=INVALID_CONFIG` here would mean the 9b cases proved
nothing** — they would have been failing for a reason common to all runs.

This one drops `--no-deps`: a real run needs the proxy.

### 9e. Restore the state 9b/9c perturbed

```bash
# Remove ONLY the session clones this step created.
sudo ls -1 /srv/first-agent/sessions/ 2>/dev/null | sort \
  > "$EVID/09e-sessions-after.txt"
comm -13 "$EVID/09a-sessions-before.txt" "$EVID/09e-sessions-after.txt" \
  | tee "$EVID/09e-created-by-s11.txt"
while read -r d; do
  [ -n "$d" ] && [ "$d" != ".active" ] \
    && sudo rm -rf "/srv/first-agent/sessions/$d" \
    && echo "removed $d"
done < "$EVID/09e-created-by-s11.txt"

# Restore .active so scripts/fa still points at the real workspace.
if [ -s "$EVID/09a-active-before.txt" ]; then
  sudo cp "$EVID/09a-active-before.txt" /srv/first-agent/sessions/.active
  echo "restored .active -> $(sudo cat /srv/first-agent/sessions/.active)"
else
  sudo rm -f /srv/first-agent/sessions/.active
  echo "removed .active (there was none before)"
fi

# The live service was never stopped by this step, but confirm it regardless.
docker compose -f "$COMPOSE" ps | tee "$EVID/09e-after-restore.txt"
docker compose -f "$COMPOSE" exec -T "$SERVICE" fa --version \
  | tee -a "$EVID/09e-after-restore.txt"
```

**Expect:** only `s11`-era clones removed, `.active` restored byte-for-byte,
the live service still `running`/`healthy`.

**STOP and report if `fa --version` fails here.**

> **Why the live service is never stopped.** The operator approved restarts
> (§0.6), and the first draft used them. On reading the entrypoint it became
> clear that `docker compose run` exercises *the identical script* with the
> identical mounts, so stopping the 24/7 service buys no additional fidelity
> — it only adds a window in which the box is down. The one thing `run` cannot
> prove is that *the long-lived container instance* would behave the same;
> that is recorded in §6 as a known limitation rather than paid for with
> downtime.

## Step S11.10 — Post-run hygiene and drift re-check (S11-G10)

Traces-to: **parent Do #9**, S11-G10. Depends-on: S11.9. Its `s11-wf-*` references are inside a `[ -d "$d" ]` guard in a disk-usage listing, so absent workflow runs are skipped silently — the step degrades, it does not fail.

```bash
# 10a. The bind-mounted repo must be untouched by everything above.
cd "$REPO_DIR"
git status --short | tee "$EVID/10a-git-status.txt"
test -s "$EVID/10a-git-status.txt" && echo "DIRTY — investigate" || echo "clean"
echo "HEAD still: $(git rev-parse HEAD)  (expected $DEPLOY_SHA)"

# 10b. Identity re-check — nothing drifted during the session.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  cd /repo && git rev-parse HEAD
  python -c "import fa; print(fa.__file__)"
' 2>&1 | tee "$EVID/10b-identity-recheck.txt"

# 10c. No provider key leaked into the agent at any point.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  [ -e /run/secrets/fa.env ] && echo "VIOLATION" || echo "OK: still keyless"
  env | cut -d= -f1 | grep -Ei "api_key|_key$" | sort || echo "(no key-shaped env names)"
' 2>&1 | tee "$EVID/10c-keyless-recheck.txt"

# 10d. Container logs for anything unexpected (names/levels only).
docker compose -f "$COMPOSE" logs --tail 200 "$SERVICE" \
  > "$EVID/10d-agent-logs.txt" 2>&1
docker compose -f "$COMPOSE" logs --tail 200 "$PROXY" \
  > "$EVID/10d-proxy-logs.txt" 2>&1
grep -ciE "traceback|unhandled|critical" "$EVID/10d-agent-logs.txt" \
  | sed 's/^/agent traceback-ish lines: /'
grep -ciE "traceback|unhandled|critical" "$EVID/10d-proxy-logs.txt" \
  | sed 's/^/proxy traceback-ish lines: /'

# 10e. Disk footprint this sheet added.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  du -sh /home/fa/.fa 2>/dev/null
  for r in s11-run-a s11-run-b s11-run-c s11-run-d \
           s11-wf-linear s11-wf-repair s11-wf-quiet; do
    d=/home/fa/.fa/session-log/$r
    [ -d "$d" ] && echo "$(du -sh "$d" 2>/dev/null)"
  done
' 2>&1 | tee "$EVID/10e-footprint.txt"
```

**Expect:** repo clean and at `$DEPLOY_SHA`; identity unchanged; still keyless;
zero traceback lines.

---

## Step S11.11 — Bundle the evidence

```bash
tar -czf "$EVID.tar.gz" -C "$(dirname "$EVID")" "$(basename "$EVID")"
echo "BUNDLE: $EVID.tar.gz  ($(du -h "$EVID.tar.gz" | cut -f1))"
ls -1 "$EVID" | sed 's/^/  /'
```

**Before sharing:** skim `08c-request-anatomy.txt` and the `05e` quiet-mode
output. Everything else is counts, modes and exit codes. If any file contains
prompt or response prose, redact it.

---

## 3. Verdict table — fill this in as you go

| Step | Goal | Verdict | Classification if not MATCH |
|---|---|---|---|
| S11.0 diff review | — | ☐ MATCH ☐ DEVIATION | |
| S11.1 mode census BEFORE | G5 | ☐ recorded | permissive count: ____ |
| S11.2 build + health | G1 | ☐ MATCH ☐ DEVIATION | |
| S11.3 identity ×4 | G1 | ☐ MATCH ☐ DEVIATION | source / image drift |
| S11.4a keyless agent | G2 | ☐ MATCH ☐ **VIOLATION** | proxy |
| S11.4b selfcheck | G2 | ☐ MATCH ☐ DEVIATION | proxy |
| S11.4c routing-check ×4 | G3 | ☐ MATCH ☐ DEVIATION | rendering / authority |
| S11.4d YAML ×5 | G3 | ☐ MATCH ☐ DEVIATION | rendering |
| S11.4e probe | G2 | ☐ MATCH ☐ DEVIATION | proxy / provider |
| S11.5 run matrix A–D | G6 | ☐ MATCH ☐ DEVIATION | authority / rendering |
| S11.6 posture before/after | G5 | ☐ MATCH ☐ DEVIATION | filesystem permission |
| S11.7 verdict matrix | G4 | ☐ MATCH ☐ DEVIATION | **authority** |
| S11.8 trace + stats + anatomy | G7,G9 | ☐ MATCH ☐ DEVIATION | authority |
| S11.9b–c entrypoint standby ×5 | G8 | ☐ MATCH ☐ DEVIATION | |
| S11.9d autorun positive control | G8 | ☐ MATCH ☐ DEVIATION | (if this fails, 9b/9c prove nothing) |
| S11.9e state restored (`.active`) | G8 | ☐ MATCH ☐ DEVIATION | |
| S11.10 hygiene + drift | G10 | ☐ MATCH ☐ DEVIATION | source / image drift |
| S11.11 evidence bundled | — | ☐ done | bundle path: ____ |

**Exit criteria (parent §Step S11) — tick only with evidence in `$EVID`:**

- [ ] deployed commit and image revision recorded → `00-deploy-sha.txt`, `03-*`
- [ ] direct-container run completed → `05b`–`05f`
- [ ] session DB/events/body metadata verified → `05f`, `08a`
- [ ] proxy boundary verified without agent-side provider key → `04a`, `10c`
- [ ] no unresolved source/image drift → `03-drift-verdict.txt`, `10b`
- [ ] handoff updated with exact evidence → §4

---

## 4. After execution

1. Paste the verdict table plus any DEVIATION output back to the agent session.
2. Findings become BACKLOG items with a severity and a one-line reproduction —
   **not** fixes in this slice.
3. The agent updates `worklogs/HANDOFF.md` with the deployed SHA, the verdict
   table, and every finding.
4. Parent Do #10: **only after human approval**, commit/push through the PR
   workflow.

---

## 5. Rollback

```bash
# Remove ONLY this sheet's artifacts. Never a blanket state wipe.
docker compose -f "$COMPOSE" exec -T "$SERVICE" sh -lc '
  for r in s11-run-a s11-run-b s11-run-c s11-run-d \
           s11-wf-linear s11-wf-repair s11-wf-quiet \
           s11-autorun s11-yamlprobe; do
    rm -rf "/home/fa/.fa/session-log/$r" && echo "removed run dir: $r"
  done
  rm -f /tmp/s11-*.yaml /tmp/s11-*.txt /tmp/s11-*.json
'

# Session rows and the global-history rows are deliberately NOT deleted:
# they are the evidence. To retire the whole session instead:
#   docker compose -f "$COMPOSE" exec -T "$SERVICE" \
#     sh -lc 'rm -rf /home/fa/.fa/sessions/'"$SID"''
#
# To roll the deployment back to the previous revision:
#   cd "$REPO_DIR" && git checkout <previous-sha>
#   docker compose -f "$COMPOSE" build && \
#     docker compose -f "$COMPOSE" up -d --force-recreate
```

**Note:** S10c.3's mode tightening is **not** rolled back by the above, and
should not be — it only ever removes group/other access, is idempotent, and
reverting it would re-open I-36.

---

## 6. Known limitations of this sheet

Stated so a reader does not over-read the result:

1. **`first-agent`'s healthcheck is `fa --version`** — it proves the binary
   runs, not that the agent is functional. The proxy's healthcheck genuinely
   probes `/healthz`. S11.4b/4e are the real functional checks.
2. **S11.7 depends on a real evaluator verdict**, which is not deterministic. If
   every workflow returns `DONE`, the exit-1 path is unproven here even though
   local tests cover it. Recorded as a residual gap rather than papered over.
3. **S11.9 uses `docker compose run --rm`**, a fresh container rather than the
   live one. The entrypoint logic is identical; the *running instance* is not
   exercised. Chosen so the 24/7 service is never left broken.
4. **S11.8c prints the first ~40 characters of system messages** to identify
   blocks. That is a deliberate, minimal disclosure — sizes alone could not tell
   the `AGENTS.md` map from the tool block.
5. **Mode census needs `sudo`** on the host side. If unavailable, the
   in-container view (6a) is sufficient for the artifacts, but the
   before/after repair diff (6b) cannot be produced.

---

## 7. Rehearsal record — five defects found in this sheet before you ran it

S7's container sheet shipped with two "checks that cannot fail" and the
operator found them mid-execution. To avoid repeating that, every inspection
block here was executed against a **real** local `fa run` (body capture on),
verbatim, through a real `sh -lc`. That found five defects:

| # | Defect | How it would have presented | Fix |
|---|---|---|---|
| **R1** | S11.7c queried `FROM run_history` | The table is **`runs`** (verified against `global_history.py`'s DDL). Every verdict row would have read `QUERY FAILED: no such table` and looked like a *product* failure. | Corrected table name; the query now also distinguishes "no DB", "no row", and "query failed". |
| **R2** | S11.8c read `row["request"]["body"]` | The real key is **`request_body`**. The block printed `0 messages` — an empty result that reads as "nothing to see" rather than "wrong key". | Schema re-derived from a captured row: `request_body`, `response_body`, `logical_call_id`, `attempt_index`, `provider`, `slug`, `ts`, `kind`. |
| **R3** | Unquoted heredocs (`<<PY`) | The **shell expanded the Python** before the interpreter saw it: `` `runs` `` ran as command substitution and `sh: request_body: not found` appeared. | All four heredocs are now `<<"PY"`; a scan confirms **zero** backticks inside any `bash` block. |
| **R4** | An apostrophe inside `sh -lc '...'` | `global_history.py's DDL` **closed the quote mid-script**, producing `IndentationError` and a shell syntax error. | Apostrophe removed; a scan checks every `sh -lc` block. |
| **R5** | `--session-id '"$SID"'` nesting | The `'"..."'` splice is fragile and had already broken once. | `$SID` is passed with `-e SID="$SID"` and read via `os.environ` / `"$SID"`. |

Additionally, one **f-string with nested double quotes** inside a
double-quoted heredoc raised `NameError: name 'MATCH' is not defined`; all such
formatting is now `%`-style, which survives every quoting layer.

**Verified working in rehearsal** (real output, local run):

```text
rows per run:        s11-run-b: 7
authority vs mirror: db=7 jsonl=7 MATCH
orphans: 0           total (positive control): 7
distinct session_id: [('session-676b0c52...',)]
stray authorities:   /home/fa: PATH ABSENT (could not look)   <-- the S7.C7 fix
routing-check C2:    ERROR: config not found  EXIT=2
routing-check C3:    not valid YAML + line/column  EXIT=2
routing-check C4:    no roles declared  EXIT=0
request anatomy:     [0] 5,924  [1] 15  [2] 8,396  [3] 16  tools 8,762
```

That last line is worth noting before you start: on the **local** fixture the
tool block is now 8,396 B (was ~11.5 KB before S10c.5) and the `AGENTS.md` map
is nearly empty. On the **deployment** the map was 28,015 B — 48.4% of the
request. S11.8c will show whether that is still true, which is the input the
remaining I-37 work needs.

### Second pass — review against the entrypoint source (R6–R9)

A follow-up review read `scripts/fa-entrypoint.sh` and the compose mounts
line by line rather than trusting the first draft. Four more defects, all
structural:

| # | Defect | Why it mattered | Fix |
|---|---|---|---|
| **R6** | S11.4d's malformed-YAML loop included `fa stats` | **`_cmd_stats` never calls `load_models_config_from_path`** (verified by source inspection). It would have exited non-zero for an unrelated reason and been recorded as a pass — a check that cannot fail. | `stats` removed; **`egress-proxy` added** instead, which is the 5th real caller *and* the one the proxy container runs at startup. |
| **R7** | S11.9 looked for the status file under `/workspace` and `/sessions/*/` | `STATUS_FILE` is `${WORKSPACE}/.fa/...` with `WORKSPACE=/workspace` (line 16-17) and is **only** redirected to `/sessions/<id>/` *after* a successful clone (line 190). `_validate_session_id` runs at line **157**, before that — and `/workspace` has **no mount** on a `read_only: true` rootfs, so `_write_status` hits its `mkdir` failure branch and **writes nothing**. Simulated both regimes to confirm. "No status file" would have read as "the entrypoint mishandled it". | Every case now sets `FA_STATUS_FILE=/tmp/...` explicitly (an override the entrypoint already supports), so the evidence lands at a known, writable path regardless of which side of the clone the failure occurs on. |
| **R8** | S11.9's throwaway containers clobbered shared host state | `docker compose run` inherits the real binds, so each invocation git-clones a new `/sessions/session-<ts>-<pid>` **and overwrites `/sessions/.active`**, which `scripts/fa:39` reads to locate the live workspace. Four cases = four orphaned clones and an `.active` pointing at a deleted directory. | 9a snapshots `.active` and the session list; 9e restores `.active` byte-for-byte and removes **only** the clones this step created (via `comm`). |
| **R9** | S11.9d asserted "a valid auto-run must NOT stand by" | **Wrong.** A *successful* auto-run also ends in `_standby` (line 296: *"Auto-run completed once; transitioning to inspectable stand-by state"*). Standby therefore does not discriminate success from failure, and the positive control proved nothing. | 9d now discriminates on the **status label** (`SUCCESS`/`FAILED` vs `INVALID_CONFIG`) and on whether a run directory was actually produced. |

**S11.4a was also strengthened** from a single-path check to a six-part probe
after review: ADR-12 claims the agent holds *no* provider keys, but the draft
only tested `/run/secrets/fa.env`. The realistic bypass is an **inline
`api_key:`** in `models.yaml`, which is mounted into the agent read-only. The
new version checks env names, mount contents, the `fa.env` path, models.yaml
inlining, **env values by key-shape**, and carries a **positive control**
(`fa_proxy_token` must be present) so "no keys found" cannot be satisfied by a
broken mount.

Rehearsed against a fixture: all four violation shapes are detected, the real
key value is never printed (redacted to `<redacted>` / reported by name only),
and removing the token file correctly trips the positive control.

### What rehearsal could NOT cover

Honest limits — these blocks are unrehearsed and are the most likely place for
a sheet defect to remain:

- anything requiring `docker compose` (S11.2, S11.3, S11.9) — no daemon here;
- the `sudo find` host-side census (S11.1, S11.6b);
- `fa probe` / `fa selfcheck` against a real proxy (S11.4b, S11.4e);
- the workflow runs themselves (S11.7a/7b) — only their *inspection* block was
  rehearsed, against absent runs, which correctly printed `NO RUN DIR`.

If one of those misbehaves, classify it **sheet defect** and report the command
— do not assume the product is at fault.


---

## Execution note — R10, found during live S11.1 (2026-08-02)

**The permissive-count filter was gawk-only and silently reported 0 on a mawk
host.** `strtonum()` and `and()` are GNU-awk builtins. Under mawk (the Debian/
Ubuntu default) awk writes `function strtonum never defined` to stderr and emits
no rows, so the count is `0`.

Live evidence from the operator's first S11.1 run:

- **1a** listed 15 entries including seven `644` files and five `755` dirs;
- **1b** reported `--- permissive entries BEFORE --- 0`;
- **1c** listed the same `644` artifacts again.

1b contradicted 1a and 1c in the same paste. **The true count was 11 of 15.**

**Why it mattered more than a cosmetic bug.** S11.6 used the identical filter on
the "after" tree and then diffed the two. Both sides would have read 0, the diff
would have been empty, and the sheet's own guidance —

> *If BEFORE was already 0, record that the retroactive half had nothing to
> repair on this host*

— would have led the operator to file a clean, confident, **false** conclusion
that S10c.3's retroactive repair had nothing to do. The check could not fail,
so it proved nothing.

**Fixed:** both sites now use a pure string test on the octal digits
(`substr($1,2,1)`, `substr($1,3,1)`), which is POSIX awk and behaves identically
under mawk, gawk and busybox awk. **Added a 1b-check** that feeds the filter a
known-permissive and a known-private line and requires it to print exactly one —
the harness must prove itself before its output is trusted.

**Class:** identical to S12/RS8. A negative result from an instrument that was
never validated is not evidence of absence.


---

## Execution note — R11, found during live S11.3 (2026-08-03)

**VIEW 4's stated expectation was wrong on any long-lived host.** The sheet said
"VIEW 4 prints no `SHADOW PRESENT` line". The operator's box printed **18**.

The glob `/sessions/*/src/fa` matches every historical session clone. Each clone
is a full repo checkout, so the count grows with the number of sessions ever run
— 18 here, dating back to 2026-07-01. Nothing about that is drift.

The real test is whether a clone is **on the import path of the running
process**, which is decided by two other lines in the same output:

```
VIEW 2: /opt/first-agent/src/fa/__init__.py   <- image code
        /opt/fa-venv/bin/python
VIEW 4: PYTHONPATH=<unset>                     <- no clone on the path
```

`scripts/fa-entrypoint.sh:199` prepends `${WORKSPACE}/src` to `PYTHONPATH` only
when `${WORKSPACE}/src/fa/__init__.py` exists, and only for the *current*
session's workspace. With `PYTHONPATH` unset and VIEW 2 under `/opt`, the 18
clones are inert files on disk.

**Verdict for this run: NO source drift.** VIEW 1 == `DEPLOY_SHA` ==
`23468cb451efa6038a932a26a3fd6485fdc5054c`, VIEW 2 in the image, `PYTHONPATH`
unset.

**Corrected pass condition** (now in §S11.3): `PYTHONPATH=<unset>` **and** VIEW 2
under `/opt`. A `SHADOW PRESENT` line matters only if VIEW 2 or `PYTHONPATH`
names that same path.

**Also worth recording:** 18 stale session clones are 18 full checkouts of dead
disk. Housekeeping, not correctness → BACKLOG I-47.

### Baseline validity after an out-of-order merge

The operator merged the fixes and ran `fa clean-rebuild` *before* taking the
S11.1 census, which would normally destroy the "before" half of S11-G5.
**Checked: the baseline survived.** `tighten_fa_artifact_modes` is called from
`_cmd_run` only (`cli.py:2423`); `fa-clean-rebuild.sh:471` invokes
`fa routing-check`, which never calls it. The census correctly read **11
permissive of 15**, and the retroactive repair still has all 11 to fix on the
first real `fa run` in S11.5.


---

## Execution note — R12 + F1, found during live S11.4 (2026-08-03)

### R12 (sheet defect, HIGH) — `$?` after a pipe measured `tee`, not the command

`fa probe --all-roles` printed `fa probe: FAIL — request rejected` for the
planner role and `PROBE_EXIT=0` **in the same paste**. `_cmd_probe` ends
`return 1 if any_failure else 0` (`cli.py:2982`), so the real exit was **1**.

Cause: `cmd 2>&1 | tee f` followed by `echo "X_EXIT=$?"` reports the exit of the
**last** pipeline element. `tee` succeeds whenever the file is writable, so the
capture was pinned to 0 regardless of the command.

**Why it mattered beyond this step.** The same construction guarded
`WF_LINEAR_EXIT` and `WF_REPAIR_EXIT` in S11.7 — the checks that exist to prove
**Q35b** (`fa workflow` exits 1 on a non-`DONE` verdict). Both would have read 0
and "confirmed" the fix while measuring nothing. A blocking gate (4e) would also
have been recorded as passed.

Fixed at all **seven** host-side sites to `${PIPESTATUS[0]}`. The in-container
`sh -lc '... ; echo "EXIT=$?"'` forms have no pipe and were correct — confirmed
by 4c/4d reporting `EXIT=2` accurately on the same run.

**Class:** the third instrument defect in this sheet (R10 gawk, R11 shadow glob,
R12 pipe exit). All three produced a *confident wrong number* rather than an
error. Instruments in an operator sheet need the same kill-check discipline as
production tests.

### F1 (product finding, MED) — planner role rejected by Mistral

```
role=planner (model=mistral-medium-2604, family=mistral)
❌ 400 top_p must be 1 when using greedy sampling
   type=invalid_request_greedy_sampling code=3054
```

`fa probe` hardcodes `temperature=0.0` (`cli.py:2943`). `ProviderChain` then
fills unset sampling fields from `models.yaml`
(`chain.py:330-332`), and `mistral.py:150` emits `top_p` whenever it is not
`None`. The planner entry therefore ships `temperature=0` **and** a `top_p != 1`,
which Mistral rejects as contradictory: greedy sampling requires `top_p == 1`.

**coder and eval passed**, so the proxy boundary, key injection and provider
path are all proven. This is one role's sampling config, not an infrastructure
failure.

**Not fixed here** — S11 is a verification sheet, and the standing rule is to
convert findings to BACKLOG items rather than patch mid-run. → **I-48**.

**Consequence for the sheet:** 4e is marked a *blocking* step. It is blocking
for the **planner role only**; S11.5 uses `--role coder`, which is green. Recorded
as a known-failing role rather than a stop.


---

## Execution note — S11.5 result + R13, 2026-08-03

### S11.5 — all nine checks PASS

| check | measured | verdict |
|---|---|---|
| 5a collision | 8 run-ids clear | no evidence overwritten |
| 5b Cell A | `EXIT=0`, `SID=session-e4120b0a…` (32-hex) | ✅ |
| 5c B1 | in-container `FA_DEBUG_LLM_BODIES=<unset>` | ✅ **parent Do #4 proven** — a host export does *not* cross into a running container |
| 5c B2 | in-container `=1` via explicit `-e` | ✅ the documented mechanism works |
| 5c B3 | `EXIT=0` | ✅ |
| 5d Cell C | `--detail debug`, no bodies for `run-c` | ✅ verbosity and secret-capture are independent |
| 5e Cell D | stdout 5 B `pong`, stderr 29 B, no status line on stdout | ✅ **I-38 / S8.4** |
| 5f gate | `run-b` PRESENT rows=1 **mode=600**; a/c/d absent | ✅ |
| 5f control | all four run dirs present with artifacts | ✅ not vacuous |

Two results worth naming. **`mode=600` on `llm_bodies.jsonl`** is the S10c.3
*creation* half proven on live infrastructure — `debug_bodies.py:175` opens
through `private_opener`, and the file is the single most sensitive artifact FA
writes. And the **positive control in 5f** is what makes the three `absent`
lines mean anything: without it, "absent" is equally consistent with "the runs
never happened".

### R13 (sheet defect) — S11.6's "permissive AFTER = 0" is wrong here

`models.yaml` is mounted `read_only: true` (`docker-compose.fa.yml:95-100`) at
`/home/fa/.fa/models.yaml`, **nested inside** the writable state dir. The
retroactive pass walks the whole root, reaches it, and `Path.chmod` raises
`OSError`; `paths.py:130` catches and skips — by design.

Predicted: **repaired = 10, permissive AFTER = 1** (`models.yaml` at `644`).
A count of 0 would be *surprising*, implying the ro mount is not in effect.

Expectation corrected in §S11.6 so a correct outcome is not filed as a
deviation. `models.yaml` staying `644` is not a defect: it is routing config
holding env-var **names**, never values — S11.4a proved exactly that.

### I-48 re-diagnosed — the fault is the model, not the role

The operator swapped models between roles, which turned a guess into a
controlled experiment:

| run | `mistral-medium-2604` | `mistral-small-2603` |
|---|---|---|
| initial | planner → **400** | coder → 200, eval → 200 |
| after swap | coder → **400** | planner → 200, eval → 200 |

The 400 follows the **model**. My first diagnosis blamed the planner role and
was wrong. Also corrected: **FA never sends `top_p`** — `RequestInfo.top_p`
defaults to `None` (`base.py:52`), `chain.py:332` fills it only from an explicit
`sampling` block (the operator has none), and every provider emits it only when
not-None. The `top_p` in the error is therefore **server-side**, most likely
from `reasoning_effort: "high"` putting `mistral-medium-2604` into a
reasoning/greedy mode that conflicts with FA's `temperature=0.0`.

**This matters for the fix:** "omit `top_p` in `mistral.py`" would patch code
that is not at fault. I-48 now lists three discriminating probes to run first.

The 429s are ignored per operator instruction — the probe fires consecutive
requests inside a rate-limit window.


---

## Execution note — S11.6 result, 2026-08-03

### PASS. I-36 / S10c.3 proven on live infrastructure, both halves.

Predicted last turn: **repaired = 10, permissive AFTER = 1**.
Measured: **repaired = 10, permissive AFTER = 1.**

| check | measured | verdict |
|---|---|---|
| in-container files at `0600` | **14 / 14** | ✅ incl. `llm_bodies.jsonl`, every `session.db`, every `manifest.json` |
| in-container dirs at `0700` | **11 / 11** | ✅ incl. `/home/fa/.fa` itself |
| leftover group/other-accessible | **1** (`models.yaml` `640`) | expected — R13 |
| host BEFORE → AFTER | 11 → 1, repaired 10 | ✅ every baseline entry accounted for |
| symlinks in the state tree | none | RK11 **not exercised** — see below |

Every one of the 11 baseline entries is accounted for: 10 repaired,
1 (`models.yaml`) explained. This is the **retroactive** half of Q56 doing
exactly what it was written for, on a tree that had been accumulating `0644`
artifacts since June — and the **creation** half was already proven in S11.5 by
`llm_bodies.jsonl` arriving at `600`.

### F2 — two different `models.yaml` files, and the count coincidence

6a's leftover is `640`; the host census's leftover is `644`. Neither is a typo:
**they are different files.**

| | path | mode | who sees it |
|---|---|---|---|
| **A** legacy | `/srv/first-agent/state/models.yaml` | `644` | host only — **hidden** in the container by the nested ro mount (`docker-compose.fa.yml:94-99`) |
| **B** routing source | `/srv/first-agent/routing/models.yaml` | `640` | mounted ro at `/home/fa/.fa/models.yaml` **and** `/etc/fa/models.yaml` (proxy) |

Both views report "1 permissive entry", but about **different files**. The
matching count is a coincidence.

This refines R13. The container-side `640` is "reached, `chmod` refused by the
read-only mount, skipped by design" — R13 as written. The host-side `644` is
stronger: **`tighten` can never reach file A at all**, because the ro mount for
B covers that exact path inside the container. No number of future runs will
change it.

**Not a security finding.** A holds routing config with env-var *names* only
(S11.4a proved no values anywhere), and the container cannot read it. It is
**dead state**: a legacy file the mount deliberately shadows. → **I-49**, to
delete it and remove the ambiguity, not to chmod it.

### RK11 is not proven on live data

6c returned nothing: there are no symlinks in the state tree. That is a *safe*
outcome — nothing to follow — but it is **not** evidence the guard works. The
symlink-skip in `paths.py:123` remains proven only by
`test_s10c_tighten_pass_skips_symlinks` in CI. Recorded as a known limitation
rather than a tick, in the same spirit as §6's note about the exit-1 workflow
path.


---

## Execution note — R14, found during live S11.7 (2026-08-03)

**All three `fa workflow` invocations used a `--task` flag that does not exist.**

```
fa workflow: error: ambiguous option: --task could match
             --task-planner, --task-coder, --task-eval
WF_LINEAR_EXIT=2
```

The real signature (`cli.py:538-547`) is **two positionals**:

```
fa workflow <roles> [task] [options]
            ^^^^^^^ required, comma-separated, e.g. planner,coder,eval
                    ^^^^^^ optional, quoted task text
```

`--task-<role>` exists only as a per-role *override*. Argparse's prefix matching
saw `--task` as an ambiguous abbreviation of the three and exited **2** before
running anything.

**Why the sheet review missed it.** S11 was rehearsed against a real local
`fa run` (§1 of the review record), but `fa workflow` was only read, never
executed — and the three flags it *does* have all start with `--task`, which
reads plausibly. **A command line is not verified until it has been run.**

Fixed at all three sites (7a, 7b, 7d) to
`fa workflow planner,coder,eval "<task>"`.

**Good news in the failure:** `WF_LINEAR_EXIT=2` proves R12's `${PIPESTATUS[0]}`
fix works. Under the old `$?` this would have read **0** and been recorded as a
passing linear workflow that never ran.

### S11.6d added — RK11 on live data

S11.6c found no symlinks, so the guard was never exercised. Added an optional
~30 s step that plants a `644` bait file *outside* the state root, links to it
from inside, runs `fa run`, and asserts the target is untouched. Includes a
pre-check that the link is visible in the container (else the test is vacuous)
and cleanup. **Oracle kill-checked before shipping** — with the guard removed
the target goes `644 → 700`.


---

## Execution note — S11.6d PASS, S11.7a BLOCKED, 2026-08-03

### S11.6d — RK11 proven on live data

Target stayed **`644`**. The retroactive pass did **not** follow a symlink out
of the state root. Combined with the sandbox kill-check (guard removed →
`644 → 700`), this is a real signal: the `paths.py:123` skip is now proven on
production, not only in CI. **RK11 closed.**

### My advice deleted a required file — correction

I described `/srv/first-agent/state/models.yaml` as "dead state ... delete it".
The operator did, and the agent immediately reported
`role 'planner' not found ... known: []`. Restoring it fixed the deployment.

**Why I was wrong.** The compose file performs two *nested* binds — the state
dir at `/home/fa/.fa`, then the routing file at `/home/fa/.fa/models.yaml`. The
inner target lives inside the outer bind, so a file must exist at that path for
the kernel to attach the mount. **That file is the mountpoint stub.** Its
content is never read (the ro mount covers it), which is exactly what made it
*look* like dead state.

The compose comment — "this nested ro file mount hides any legacy
state/models.yaml" — reinforced the misreading. Both S11.6 observations stand
(the pass cannot repair it; the count will read 1 forever); only the remedy was
wrong. **I-49 rewritten**, and the fix is now "document it and have
`fa-clean-rebuild.sh` recreate it if missing", never "delete it".

*Lesson: "the process cannot read this file" and "this file is unnecessary" are
different claims. I proved the first and asserted the second.*

### S11.7a — BLOCKED by I-50 (P1), and the sheet cannot proceed as written

Two clean attempts (`--max-turns 6`, then `12`) both died identically:

```
stage 1/3 planner  OK: stopped_by_llm (turns=4)   in=61.2k
stage 2/3 coder    FAIL: request_shape (turns=1)  in=0
fa workflow: stage 'coder' exited 2 — pipeline stopped (fail-fast).
```

`in=0` means the provider rejected the **request body** before token
accounting. The same `mistral-small-2603` succeeded as `coder` standalone in
S11.5 and as `planner` in this very workflow — so the discriminator is the
**stage transition**, not the model (I-48) and not the role.

`_run_stage` passes `"resume": not fresh` (`cli.py:1210`), so the coder resumes
the planner's transcript, which ends in `fs.glob` / `fs.grep` / read tool calls.
A resumed transcript replayed under a *different* role's tool allowlist can
carry `tool_calls` referencing absent tools, or `tool` messages whose
`tool_call_id` no longer resolves — both are 400s. **Hypothesis, not yet
proven** → I-50 lists three discriminating experiments.

**Why local testing never caught it:** S8's workflow tests use a scripted
transport that accepts any body. Only a real provider validates request shape.
This is precisely the class of defect S11 exists to surface.

**Consequence for Q35b.** S11.7 was the only live proof of the exit-code
contract, and it cannot run until I-50 is resolved. What *is* proven:

- `fa workflow` exits **2** on a stage error, and fail-fast stops the pipeline —
  a shell `&&` chain does stop, which is the S10c.2 intent;
- **not** proven: exit **1** on a completed-but-non-`DONE` verdict, which needs
  an eval stage to actually run.

Recorded as an explicit gap, not a pass. §6's known limitation now has a second
cause.

### Two smaller observations

**`run_id_reused` fired correctly twice** — re-using `s11-wf-linear` and
`s11-wf-linear-2` was refused with a clear message and exit 2, rather than
silently overwriting prior evidence. That is the S5 namespace contract working
on live data; worth recording as a pass.

**The planner's output is good.** Four turns, real tool use, a plan naming a
specific function and file with acceptance criteria. Cache hit rates of 96–99%
on turns 2–4 show prompt caching working (`cache=74%` overall).


---

## Execution note — I-50 diagnostic round 1, 2026-08-03

The body-capture run **reproduced I-50 exactly** — third consecutive
reproduction, now with a different planner transcript (`fs.instant_grep`,
`fs.glob`, three reads, 6 turns) and a different target file. The coder still
dies at turn 1 with `in=0`.

**Reproducibility is now established.** Not a flake, not rate-limiting, not
model-specific: `mistral-small-2603` succeeds as planner in the same run.

### Why the diagnostic did not answer the question — I-51

The console printed:

```
⏳ retry in 0s (unknown/0)
FAIL: request_shape (turns=1)
```

`unknown/0` is a **placeholder**, not data. `coder_loop.py:1367-1379` hardcodes
`provider="unknown"` and `status=0` on the `api_retry` event, and puts the real
detail in a `reason` key — which `output.py:347-352` **never renders**. So the
provider's own explanation of the 400 is computed, attached, and then dropped
before it reaches the operator.

`fa probe` prints the same exception class in full (`cli.py:2978`), which is
exactly why I-48 was diagnosable in one run and I-50 has taken three.

**Logged as I-51 (P2).** It is the reason this step is slow.

### The detail IS durable — recover it without another provider call

`coder_loop.py:1363` writes `{"reason": "request_shape", "detail": str(exc)}`
to `events.jsonl` before returning. The failing run already on disk therefore
contains the provider's message:

> **`jq` is NOT installed in the agent image (R15).** The container is a lean
> runtime; `sh: jq: not found`. Every inspection must use the Python that is
> guaranteed present. Use an **unquoted-delimiter heredoc** (`<<"PY"`) so the
> shell does not expand `$` or backslashes before Python sees them.

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" python - <<"PY"
import json, pathlib
run = "s11-wf-diag"
p = pathlib.Path("/home/fa/.fa/session-log") / run / "events.jsonl"
if not p.is_file():
    print("NO events.jsonl at", p)
    raise SystemExit(1)
lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
stopped = []
for line in lines:
    try:
        r = json.loads(line)
    except Exception:
        continue
    if r.get("kind") == "run_stopped":
        stopped.append(r)
# Vacuity guard: distinguish "no matching rows" from "read nothing at all".
print("rows:", len(lines), "| run_stopped rows:", len(stopped))
if not stopped:
    print("NO run_stopped ROW - the stage never reached the handler")
for r in stopped:
    c = r.get("content", {})
    print("-" * 60)
    print("reason:", c.get("reason"))
    print("detail:", c.get("detail"))
PY
```

Zero tokens, zero risk, and it should print `status=<400|422> body={...}` —
the same shape `fa probe` showed for I-48.

**Do this before any further live workflow runs.** Three reproductions have
already been paid for; the answer is sitting in the last one.

### Note on `FA_DEBUG_LLM_BODIES` for a rejected request

Body capture records the exchange at the provider boundary. A request rejected
with 400 may or may not produce a row depending on where the raise happens
relative to the capture hook — `base.py:126` raises inside
`normalize_response`, i.e. **after** the HTTP call. If
`s11-wf-diag/llm_bodies.jsonl` exists, its **last** row is the rejected request
and is authoritative:

```bash
docker compose -f "$COMPOSE" exec -T "$SERVICE" python - <<"PY"
import json, pathlib
p = pathlib.Path("/home/fa/.fa/session-log/s11-wf-diag/llm_bodies.jsonl")
if not p.is_file():
    print("no body file - use the events.jsonl route above")
    raise SystemExit(0)
rows = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
print("body rows:", len(rows))
last = json.loads(rows[-1])
req = last.get("request", last)
msgs = req.get("messages", [])
tools = [t.get("function", {}).get("name") for t in (req.get("tools") or [])]
declared = [tc.get("id") for m in msgs for tc in (m.get("tool_calls") or [])]
referenced = [m.get("tool_call_id") for m in msgs if m.get("role") == "tool"]
called = [tc.get("function", {}).get("name") for m in msgs for tc in (m.get("tool_calls") or [])]
print("n_messages:", len(msgs))
print("roles:", [m.get("role") for m in msgs])
print("tools[] declared:", tools)
print("tool_call ids declared:", declared)
print("tool_call_ids referenced:", referenced)
# ORACLE 1 - resumed-transcript hypothesis:
print("DANGLING tool_call_id (referenced, never declared):",
      [i for i in referenced if i not in declared])
print("CALLED but absent from tools[]:", sorted({c for c in called if c not in tools}))
# ORACLE 2 - Mistral rejects an assistant msg with neither content nor tool_calls:
print("EMPTY assistant msgs:",
      sum(1 for m in msgs if m.get("role") == "assistant"
          and not m.get("content") and not m.get("tool_calls")))
PY
```

The oracle for the resumed-transcript hypothesis: a `tool_call_id` in
`tool_msg_ids` with no match in `last_tool_call_ids`, or a `tool_calls` entry
naming a function absent from `tool_names`.


---

## Execution note — R15, 2026-08-03

**`jq` is not installed in the agent image.** `sh: 2: jq: not found`. The image
is a lean runtime: Python and the `fa` console script, nothing else assumed.

Both inspection blocks rewritten to use `python - <<"PY"`. Two details that
matter and were verified rather than assumed:

- **Unquoted heredoc delimiter** (`<<"PY"`, not `<<PY`). With a bare delimiter
  the *shell* expands `$` and backslashes before Python ever sees the script —
  the hazard already recorded in §Shell hazards. Writing this patch, my own
  outer heredoc collided with the inner `PY` terminator, which is the same
  class of bug appearing one level up.
- **Vacuity guard.** Each block prints the total row count alongside the
  matched count, so "no `run_stopped` row" is distinguishable from "read
  nothing at all". Without it an empty result looks identical to a clean run —
  the failure mode already hit twice in this sheet (R10 gawk, RS8 secret
  tests).

Both blocks were parsed with `ast.parse` before shipping (24 and 27 lines,
valid), and the events-log form was executed against a fixture reproducing the
real schema.

**Sheet-wide consequence:** no S11 step may assume a host-side tool exists
inside the container. The only safe primitives are `sh`, `python`, `find`,
`stat` and `fa` itself.


---

## Execution note — I-50 ROOT-CAUSED, 2026-08-03

```
status=400 code=3230 type=invalid_request_message_order
"Expected last role User or Tool (or Assistant with prefix True)
 for serving but got assistant"
```

**My hypothesis was wrong.** I predicted a dangling `tool_call_id` or a tool
absent from the coder's allowlist. It is neither: the request is rejected on
**message ordering**. The recovery command found the answer in a run that had
already failed — no extra provider calls.

**Mechanism, read from source:**

- `prompt_composer.py:123-125` appends the task as a `user` message and *then*
  `non_cacheable.extend(observations)` — history lands **after** the task;
- `coder_loop.py:450-490` rebuilds history from the session DB as `assistant`
  and `tool` messages only, never replaying `user_msg`;
- the planner ended `stopped_by_llm` on a text turn, so its last row is a
  `model_msg` with no tool call.

Net order: `[system ×3, user "Task: …", …history…, assistant]` — assistant last.

**It explains all four observations**, which is why it looked model-specific
(I-48) and then role-specific and was neither:

| scenario | history | last role | result |
|---|---|---|---|
| standalone `fa run` | empty | `user` | 200 |
| planner, stage 1 `fresh` | empty | `user` | 200 |
| coder, stage 2 `resume` | planner's turns | **assistant** | **400** |
| turn 2+ in one session | ends in tool result | `tool` | 200 |

**Why the suite missed it.** S8 drives the workflow through a scripted transport
that accepts any ordering, and `_assert_tool_pairing_invariant`
(`coder_loop.py:176`) checks tool-call/result **pairing** — not the **final
role**. The one invariant that mattered was never asserted. This is the clearest
example yet of why S11 exists: no amount of local testing against a fake
transport finds a rule only the real provider enforces.

**Fix is a judgement call, not a patch to slot in.** The smallest change is to
append the task *after* the observations, which is also the more natural reading
— a new instruction should follow inherited context. But it reorders the
prompt-cache key, and this deployment is currently seeing 74–99% cache hits, so
it must be measured. Three options and a recommendation are in I-50.

### S11.7 verdict: BLOCKED, and it is a success

The step cannot complete, but it produced its intended output: a P1 defect in
the deployed path, root-caused to two specific source lines, with a live error
body as evidence. That is a better result than a green tick.

**Q35b status — partially proven:**

- ✅ `fa workflow` exits **2** on a stage error and fail-fast halts the
  pipeline, so a shell `&&` chain does stop;
- ❌ exit **1** on a completed-but-non-`DONE` verdict is **not** proven and
  cannot be until I-50 clears, since the eval stage is unreachable.

Recorded as an explicit gap. §6's known limitation now has a second, concrete
cause.

**Recommendation:** skip 7b/7c/7d — they all need a working pipeline — and
continue at S11.8. Return to 7 after I-50 is fixed.


---

## Execution note — I-50 disposition, 2026-08-03

Researched before proposing a fix. The Mistral `3230`
`invalid_request_message_order` family is **not a Mistral quirk** — it is a
known cross-ecosystem class hitting opencode (#19517, #6346), LiteLLM (#17761),
LibreChat (#12429), crush (#279), dyad (#1543) and pydantic-ai (#3733).

Every mature harness converged on the same two decisions:

1. **canonical internal message list, normalized per provider at the boundary** —
   not a lowest-common-denominator shape, which would cost FA prompt caching
   (currently 74–99% live);
2. **capability flags rather than provider-name checks** — opencode's own issue
   lists name-matching as a detection criterion and then recommends a
   provider-level capability flag instead. Same lesson as S12's probes.

FA is well positioned: `chain.py:368` is the **only** call site that reaches a
provider, and `registry.py:35-38` already keys adapters by name. The fix is a
normalization pass at that one chokepoint.

**→ `PLAN-cli-trace-S13-message-normalization.md`.** S11.7b/7c/7d stay blocked
until it lands; S11.8 onward is unaffected and can proceed now.


---

## Re-sequencing after the S11.7 block — 2026-08-03

I-50 (P1) blocks the workflow verdict matrix. I re-derived the dependency graph
from what each step actually **reads**, rather than trusting the declared
`Depends-on` chain.

**Result: only S11.7b/7c/7d are blocked. Everything else can proceed now.**

| step | declared | real dependency | status |
|---|---|---|---|
| S11.7a | S11.5 | — | ⚠️ **run, blocked at stage 2** (I-50) — evidence captured |
| S11.7b/7c/7d | S11.5 | needs `flow_state.json` + `eval_report.json` from a completed pipeline | ❌ **blocked by I-50** |
| **S11.8** | S11.7 | reads `s11-run-b` + its own probes — **no `s11-wf-*`** | ✅ **can run now** |
| **S11.9** | S11.8 | entrypoint failure modes; workflow-independent | ✅ can run |
| **S11.10** | S11.9 | `s11-wf-*` only inside `[ -d ]`-guarded `du` | ✅ degrades gracefully |
| **S11.11** | — | bundles whatever exists | ✅ can run |

**Why the declared chain was wrong.** `Depends-on:` was written as a *narrative*
order — the sheet reads top to bottom. Only S11.7c actually consumes workflow
artifacts (`for run in ("s11-wf-linear", "s11-wf-repair", "s11-wf-quiet")`), and
it already handles absence with `NO RUN DIR`. Treating narrative order as a hard
dependency would have stalled six steps behind one defect.

**Recommended order from here:** S11.8 → S11.9 → S11.10 → S11.11, then return to
S11.7b/7c/7d after S13 lands.

**What S11.7 already bought us**, recorded so it is not re-litigated as a
failure: I-50 (P1, root-caused to two source lines), I-51 (P2), I-52 (P2), R14
(the `--task` flag that does not exist), R15 (`jq` absent from the image), and
the confirmation that R12's `${PIPESTATUS[0]}` fix works — `WF_LINEAR_EXIT=2`
was reported truthfully where the old `$?` would have printed 0.

**Q35b remains partially proven:** exit **2** on a stage error with fail-fast is
✅ demonstrated live; exit **1** on a completed-but-non-`DONE` verdict is ❌
unreachable until the pipeline completes.


---

## Execution note — R16/R17/R18, found during live S11.8a (2026-08-04)

Three separate problems in one paste. Only one was a real defect in the code
under test; all three were defects in **this sheet**.

### R16 (HIGH) — no `SID` guard: an empty variable fabricates an empty database

```
sqlite3.OperationalError: no such table: event_log
```

`$SID` was unset in the operator's new terminal, so the path became
`/home/fa/.fa/sessions//session.db`. **`sqlite3.connect()` creates the file if
it does not exist** — verified locally:

```
exists before connect: False
exists after connect : True
query error: OperationalError -> no such table: event_log
```

So the step did not merely fail: it **created a spurious empty `session.db`** on
the deployed box and then reported a confusing error about the schema.

Worse than the error is the near-miss. If any query had been written
`SELECT COUNT(*)` against a table that *did* exist in an empty db, it would have
returned **0** and been recorded as "0 orphans — clean". Same failure family as
R10 (gawk) and RS8 (vacuous secret tests): **a check whose input was never
validated reports a confident wrong number.**

Fixed: the step now refuses to run without `SID`, refuses if the `session.db`
does not already exist, opens **read-only** (`file:…?mode=ro`), and prints the
table list plus a `runs found:` positive control before any verdict.

### R17 (MED) — no session preflight for a fresh terminal

`$EVID` was also unset, so `tee` wrote nothing:
`tee: …/08a-trace-integrity.txt: Нет такого файла или каталога`. Evidence for
the step was silently lost while the step appeared to run.

The sheet's §0 preflight mints `EVID=$(date …)` — correct on day one, wrong on
day two, because it **creates a new empty directory** rather than re-attaching
to the existing one. Added a resumable preflight that re-attaches to the newest
`s11-evidence-*` and recovers `SID` from the deployed state rather than memory.

### R18 (LOW) — the "mangled" last line was a display artifact, not corruption

```
PY' 2>&1 | tee "$EVID/08a-…"ot look)"); continue AND tool_call_id<>\"\"…
```

Three fragments overlaid on one physical line: the real last line, plus
`…ot look"); continue` and `AND tool_call_id<>""…` from **earlier** lines of the
same block. The terminal wrapped and redrew in place instead of scrolling.
Nothing was corrupted and the text sent to the shell was correct.

**But the lesson stands:** a 40-line heredoc pasted into a live prompt is
fragile — one stray newline in the middle of `<<"PY"` and the shell executes a
partial script. Long blocks should be written to a file and executed, not
pasted. Recorded as a sheet-wide practice, not a one-off.


---

## Execution note — R19, and R16 confirmed by its own residue (2026-08-04)

The new preflight's guard fired on its first run:

```
SID     = session.db
STOP: no session.db at /home/fa/.fa/sessions/session.db
```

**This is R16 proving itself.** An empty `sid` collapses the directory level:

```
"/home/fa/.fa/sessions/%s/session.db" % ""   ->  /home/fa/.fa/sessions/session.db
```

so the pre-R16 command created a stray authority **directly under
`sessions/`**, alongside the real session directories. That file is now the
newest entry there, and my recovery line used `ls -1t … | head -1`, which lists
**files as well as directories** — so `SID` became the literal string
`session.db`.

Two lessons, both worth more than the fix:

1. **The guard did its job.** Without it, `SID=session.db` would have produced
   `/home/fa/.fa/sessions/session.db/session.db`, `connect()` would have created
   *another* empty database one level deeper, and the step would have reported
   zeros as clean results. The failure was caught at the input, which is exactly
   where R16 said it had to be.
2. **My fix for R16 was incomplete in the same way the first Windows encoding
   fix was.** I hardened the *consumer* (8a refuses a bad `SID`) but left the
   *producer* (`ls -1t`) able to emit one. Fixing one side of a data path and
   declaring the class closed is a repeat of the S12 output-then-input mistake.

**R19 fix:** recover `SID` with
`find … -mindepth 1 -maxdepth 1 -type d -name "session-*"`, newest by mtime.
A file cannot be selected, and the name filter pins the documented
`session-<32 hex>` shape. Reproduced against a fixture of the operator's exact
directory state: old logic returns `session.db`, new logic returns
`session-e4120b0a…`. A shape guard (`case "$SID" in session-*)`) rejects
anything else before it can be used.

**Added a residue check.** The preflight now reports any `*.db` / `*.db-wal` /
`*.db-shm` sitting directly under `sessions/` — a location where no legitimate
authority ever lives. It reports rather than deletes: removing a database on a
deployed box is an operator decision, and S11.8a's "stray authorities" check is
independently designed to catch exactly this.


---

## Execution note — R20, found before running S11.8a (2026-08-04)

The R19 preflight returned a **valid** session that was the **wrong** one:

```
SID = session-0e145f4970314d92bcc9e1aacf63dbf7
OK: session.db exists for SID=...
STRAY (R16 residue): /home/fa/.fa/sessions/session.db  0 bytes
```

`0e145f` is the **workflow** session created by S11.7 — identifiable in the
operator's own 7a output:

```
FTS5 db not exists at /sessions/session-0e145f4970314d92bcc9e1aacf63dbf7/.fa/fts.db
```

S11.5 ran all four `fa run` cells against `session-e4120b0a…` (`--session-id
"$SID"` on 5c/5d/5e). S11.7 then created a *newer* session, so
"newest directory" started resolving to the workflow session.

**Why this was dangerous rather than merely wrong.** 8a would have opened
`0e145f`, found `s11-wf-*` runs, printed a non-zero `runs found:` — **the
positive control passes** — and reported db/jsonl parity for a session the step
was never about. 8b/8c would then disagree when they queried `s11-run-b`. A
confident, well-formed answer about the wrong subject is worse than a crash.

**Third iteration of the same root cause.** `SID` recovery has now been wrong
three ways: a **file** instead of a directory (R19), an **empty** string (R16),
and a **valid-but-unrelated** directory (R20). The pattern is that each fix
tightened the *shape* of the answer without checking its *meaning*.

**R20 fix — select by content, not by metadata.** The preflight now picks the
session whose `event_log` actually contains `s11-run-b`, falling back to
newest-with-a-database only if no session owns it. Verified against a fixture
reproducing the live layout (older owner + newer workflow session + the R16
stray file): the old rule returns `0e145f`, the new rule returns `e4120b0a`.

**`STRAY … 0 bytes` confirms R16 exactly** — a zero-row database at
`sessions/session.db`, created by `sqlite3.connect()` on the collapsed path.
Left in place deliberately: S11.8a's "stray authorities" check is designed to
find precisely this, and leaving it gives that check a real positive instead of
a vacuous pass.
