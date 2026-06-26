# PR: Red Team Analysis Response (Secret Paths Python Bypass)

**Intent:** FIX
**Goal Lens:** Close critical shell sandbox escape and exfiltration vectors discovered during advanced Red Team testing.

## Summary

This PR fortifies `src/fa/sandbox/secret_paths.py` against string obfuscation and execution wrappers (e.g., Python scripts). 

## Changes

**Python Shell Wrapper / String Obfuscation Bypass (`secret_paths.py`)**:
- *Vulnerability:* The secret path protection previously relied solely on `shlex` token prefix matching. Commands like `python3 -c "print(open('/run/secrets/fa.env').read())"` successfully hid the secret path deep inside a single quoted argument, bypassing prefix checks.
- *Fix:* Implemented a deterministic fail-closed fallback inside `command_reads_secret_path`. Even if lexical tokenization succeeds, a raw substring search for any secret prefix across the entire command string is enforced.

*(Note: Other infrastructural blocks like `/proc` scanning and `docker`/`systemctl` constraints were already successfully merged in a prior commit)*

## Subtraction Evaluated
- Removing what makes this redundant: none.
- What capability is lost: unrestricted Python scripts directly addressing `/run/secrets`. 
- Open-source agent-stack precedent: standard string validation against protected namespaces.
