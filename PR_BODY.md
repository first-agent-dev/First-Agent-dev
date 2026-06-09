INTENT: FIX
CLASS: REPAIR
INVARIANT: Affects: ADR-7 §7 event schema audit trail must not contain plaintext secrets; ADR-9 §1 config-load validation requires API keys referenced via env vars, not inline values.

DEGREE-OF-FREEDOM CLOSED: The agent previously had no automated defense against embedding API keys in `fs.write_file` content or `fs.run_bash` commands; SecretGuard now denies such tool calls deterministically before execution.

DETERMINISTIC MECHANISM: SecretGuard.handle inspects `tool_call.params["content"]` and `tool_call.params["command"]` for exact-match, base64-encoded, URL-encoded, and shell-interpolated secret substrings, returning `Decision.deny("secret leak detected...")` when found: `src/fa/inner_loop/hooks/builtin.py:435`

## What ships

Comprehensive secrets-handling hardening closing gaps A–Q (original audit) and R–Z (outside-the-box review). The PR spans container integration, runtime redaction, agent self-protection, developer onboarding, deployment docs, and repo hygiene.

### Container integration (Steps 1–4)

- `.dockerignore` — excludes `.env*` from build context, except `.env.fa.template`
- `docker-compose.fa.yml` — bind-mounts `/srv/first-agent/state` → `/home/fa/.fa` for persistent `models.yaml`, `config.yaml`, `pr_draft.md`; removes dead `FA_CONFIG` / `FA_WORKSPACE` env vars
- `knowledge/examples/models.yaml.example` — safe reference template using `api_key_env` (never inline keys)
- `.env.fa.template` — LLM API key template with clear separation note: B2 backup credentials belong in `/srv/first-agent/secrets/backup.env`, NOT here

### Host scripts (Steps 5–6)

- `scripts/setup-fa-desktop.sh` — auto-creates `.env.fa` from template, `models.yaml` from example, backup credentials template; `chmod 700` on `state/` and `secrets/`
- `scripts/backup-fa.sh` — sources B2 credentials from `/srv/first-agent/secrets/backup.env`

### Deployment docs (Step 7)

- `knowledge/SETUP_AIO.md` — new Phase 7b (LLM API key setup), Docker trust boundary warning, log security note, backup security note, and dedicated **Secrets Management** subsection

### Repo hygiene (Steps 8–9)

- `.gitignore` — explicit `.env.fa`, `models.yaml`, `config.yaml`; `.env.fa.template` exception
- `.gitleaks.toml` — expanded allowlist for dummy test keys (`sk-test`, `fw-fake`, `b2-fake`, `nvapi-test`, `gsk-test`) with production secret policy comment block

### Runtime redaction (Steps 10–13)

- `src/fa/observability/redaction.py` — `SecretRedactor` class (stdlib-only, exact-match `str.replace()` + base64/URL-encoded form replacement), with `from_models_config()` factory. Raises typed `SecretRedactorError` when all requested env vars are missing/empty/short.
- `src/fa/inner_loop/state.py` — `EventLog` wires redactor via `_redact_value()` (handles `str`, `dict`, `list`, `tuple`)
- `src/fa/inner_loop/hooks/builtin.py` — `LearningObserver` redacts `result.summary` and `result.error.message` before writing to `knowledge/trace/`
- `src/fa/cli.py` — constructs `SecretRedactor` from loaded `ModelsConfig` (with `try/except SecretRedactorError`), passes to `EventLog` and `LearningObserver`

### Developer convenience (Step 14)

- `src/fa/cli.py` — optional `~/.fa/.env` loader extracted into `_load_fa_dotenv(path)` with specific exception handling (`FileNotFoundError`, `PermissionError`, `UnicodeDecodeError`) + `warnings.warn`. Never logs parsed key/value content.

### Agent self-protection (Step 15–16)

- `src/fa/inner_loop/hooks/builtin.py` — `SecretGuard` hook (`GuardMiddleware`) blocks `fs.write_file` and `fs.run_bash` containing verbatim, base64-encoded, URL-encoded, or shell-interpolated secret strings
- Registered in both `_cmd_smoke` (empty secrets, no-op) and `_cmd_run` (actual secrets from redactor)

### README (Step 15)

- Security section covering WSL dev (`~/.fa/.env`), AIO production (`.env.fa`), repo hygiene (`gitleaks`), and a dedicated **Secrets Management** table explaining category separation (LLM keys vs backup credentials vs deploy key)

## Test coverage

- `tests/test_observability_redaction.py` — 18 tests: exact match, substring, no false positive, multiline, nested dict, `from_models_config`, empty env var raises `SecretRedactorError`, `secrets` property, `EventLog` redaction (nested str/dict/list/tuple), no-redactor pass-through, very long secret, secret containing mask string, concurrent redaction (4 threads x 100 iterations), empty secret set no-op, secret multiple times, base64-encoded secret, URL-encoded secret, `SecretRedactorError` parametrized (missing/empty/too-short)
- `tests/test_inner_loop_builtin_hooks.py` — 10 tests: SecretGuard denies write with secret, allows write without secret, allows bash without secret, allows null tool call, base64-encoded secret in write_file, URL-encoded secret in write_file, shell-interpolated secret in run_bash, base64-encoded secret in run_bash, URL-encoded secret in run_bash, Jinja-style interpolated secret in run_bash
- `tests/test_cli_dotenv_loader.py` — 4 tests: missing file silently continues, malformed encoding warns, valid pairs loaded, warning does not leak values

## Review & Testing Checklist

- [x] `python -m py_compile` on all modified `.py` files
- [x] `python -m ruff check` passes on all modified `.py` files
- [x] `python -m pytest tests/test_observability_redaction.py tests/test_inner_loop_builtin_hooks.py tests/test_cli_dotenv_loader.py` — 40 passed
- [ ] Full test suite: `just test`
- [ ] `pre-commit run --all-files` (including gitleaks)
- [ ] `docker compose -f docker-compose.fa.yml config`

## Notes

- SecretRedactor now catches base64-encoded and URL-encoded forms of known secrets (in addition to exact-match). This closes the encoding-bypass gap without introducing false positives, because only known env values are checked.
- SecretGuard now detects shell variable interpolation (`echo $OPENROUTER_API_KEY`, `echo ${OPENROUTER_API_KEY}`, `echo {{OPENROUTER_API_KEY}}`) by resolving the variable name against `os.environ` and checking if the resolved value is in the known secret set.
- `HANDOFF.md` and `knowledge/llms.txt` updated in this PR.

## AI-Session trailer

All commits in this PR driven by LLM-agent session.
