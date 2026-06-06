---
title: "Linux dev environment on Windows 11 Pro — WSL2 recommended path"
source:
  - "https://learn.microsoft.com/en-us/windows/wsl/wsl-config (Advanced settings configuration in WSL)"
  - "https://rsw.io/best-wsl-settings-for-low-memory-systems-8gb-ram-or-less/"
  - "https://rsw.io/wsl-2-vs-docker-desktop-which-one-should-you-use/"
  - "https://cr0x.net/en/docker-desktop-vs-docker-wsl-speed/"
  - "https://github.com/astral-sh/uv-pre-commit (uv pre-commit hooks)"
  - "https://github.com/casey/just (cross-platform command runner)"
compiled: "2026-06-06"
chain_of_custody: |
  - WSL2 resource limits: Microsoft Learn wsl-config page (official docs, 2025-11-19 update).
  - Low-memory WSL2 tuning: rsw.io blog post (empirical, community-tested).
  - WSL2 vs Docker Desktop overhead: rsw.io comparison + cr0x.net benchmark (both community; no primary vendor benchmark exists).
  - uv toolchain parity: verified by reading justfile + pyproject.toml in this repo (no OS-specific deps beyond universal-ctags).
  - 9P filesystem performance penalty: widely reported in WSL2 GitHub issues; exact 10-50× figure is approximate community consensus.
goal_lens: "Document the recommended WSL2 development environment for First-Agent contributors on Windows, ensuring CI parity with minimal setup friction."
tier: stable
links: []
mentions: []
confidence: extracted
claims_requiring_verification:
- "`/mnt/c/` I/O is 10-50× slower than native ext4" — approximate community consensus; no vendor-published benchmark.
- "WSL2 VM memory is not dynamically shrunk" — documented in Microsoft Learn (memory reclamation requires `wsl --shutdown`).
---

> **Status:** active. Note produced via
> [`knowledge/prompts/research-briefing.md`](../prompts/research-briefing.md).
>
> §0 below is the Decision Briefing intended for the project lead and
> for future LLM agents reading the note from the top. It mirrors the
> chat-handover the agent posted at session end. §1.. are deep-dive
> sections; load them only when §0 is insufficient.

## 0. Decision Briefing

### R-1 — Recommend WSL2 + Ubuntu 24.04 as the canonical Windows dev environment

- **What:** For Windows 11 Pro contributors, WSL2 with Ubuntu 24.04 is the single recommended dev environment. A 6GB RAM cap + 2GB swap in `.wslconfig` keeps the i5-1235U/16GB machine responsive. The repo MUST be cloned inside WSL's native ext4 (`~/...`), never on `/mnt/c/`.
- **Project-axis fit (stable across notes):**
  - (A) reduces session-start noise: YES (~200 tokens saved per Windows contributor session — no more "why does `just check` fail on Windows?").
  - (B) helps LLM find context when needed: YES (pointer-shape to `.wslconfig` + setup commands).
- **Goal-lens fit (per session, dynamic):**
  - (C) advances chosen goal_lens "Document the recommended WSL2 development environment": YES — turns tribal knowledge into a repeatable, citable setup.
- **Cost:** cheap (<1h to write, <10 min for a contributor to follow).
- **Verdict:** TAKE
- **Concrete first step (if TAKE):** Create `knowledge/research/linux-dev-env-wsl2-2026-06.md` + update `knowledge/llms.txt` BY-DEMAND INDEX.

### Summary

| R-N | Verdict | Project-fit (A / B) | Goal-fit (C) | Cost | Alternative-if-rejected | User decision needed? |
|-----|---------|---------------------|--------------|------|--------------------------|------------------------|
| R-1 | TAKE    | YES / YES           | YES (dev-env docs) | cheap | Windows-native dev with CI-divergence caveats | No (TAKE)              |

## 1. TL;DR

- **Hardware target:** i5-1235U (2P+8E, 12 threads), 16GB DDR4, NVMe SSD, Windows 11 Pro.
- **Recommended path:** WSL2 + Ubuntu 24.04, RAM-capped at 6GB via `%UserProfile%\.wslconfig`.
- **Critical filesystem rule:** Clone the repo inside WSL's native ext4 (`~/First-Agent-dev/`), NOT on `/mnt/c/...`. 9P translation layer makes `/mnt/c/` 10-50× slower for Git and file watchers.
- **Why not Windows native?** CI runs on `ubuntu-latest`; Windows-native dev risks path-separator, shell-quoting, `core.autocrlf`, and `universal-ctags` format divergences.
- **Alternative paths evaluated:** Docker Desktop (heavier RAM, overkill for single-user), Hyper-V VM (highest overhead, clunky file sharing). Both rejected for this use case.
- **Missing deps on Ubuntu:** `universal-ctags` (ADR-5 chunker requirement, installable via `apt`).

## 2. Scope, метод

- **Sources read:** Microsoft Learn WSL config docs, community WSL2 tuning blogs (rsw.io, Vincent Schmalbach), Docker Desktop vs WSL2 comparisons (rsw.io, cr0x.net), repo-internal verification (justfile, pyproject.toml system deps, CI workflow YAML).
- **Method:** Requirements-first matching. Enumerated all Windows→Linux dev environment options, scored against constraints (16GB RAM, convenience priority, CI parity, no local GPU need).
- **Deliberately excluded:** Local LLM inference setup (out of scope — user confirmed cloud APIs only), Windows-native Python dev (rejected due to CI parity risk), remote/cloud dev environments (Codespaces, Gitpod — require network + subscription, contradict local-first architecture).
- **Goal-lens (verbatim):** "Document the recommended WSL2 development environment for First-Agent contributors on Windows, ensuring CI parity with minimal setup friction."

## 3. Key concepts

- **WSL2** — Windows Subsystem for Linux v2. Lightweight VM with real Linux kernel, tight Windows integration (Explorer, VS Code Remote-WSL).
- **9P filesystem** — Protocol WSL2 uses to mount Windows drives (`/mnt/c/`). Adds translation overhead; fine for occasional file access, terrible for Git repos and file watchers.
- `.wslconfig` — Global WSL2 settings file in `%UserProfile%` (Windows side). Controls VM memory, CPU, swap across all distros.
- **Remote-WSL** — VS Code / Windsurf extension that runs the editor frontend on Windows while the backend (language server, terminal, debugger) runs inside WSL2.
- **Dual-boot** — Not evaluated (removed during planning; user scope: virtualized environment inside Windows).

## 4. Mapping / analysis

### 4.1 Option comparison matrix

| Criterion | A — WSL2 + Ubuntu | B — Docker Desktop | C — Hyper-V VM |
| :--- | :--- | :--- | :--- |
| Setup complexity | One PowerShell command | Install Docker Desktop + write Dockerfile | Hyper-V Manager → Quick Create |
| RAM overhead | ~6GB cap (tunable) | +1-2GB Docker daemon | Full static reservation |
| File sharing | Seamless (`\\wsl$\`, `/mnt/c/`) | Bind mounts (performance issues on Windows) | RDP / Enhanced Session (clunky) |
| CI parity | Native Linux behavior | Native Linux behavior | Native Linux behavior |
| IDE integration | VS Code/Windsurf Remote-WSL | Dev Containers extension | Remote-SSH / RDP |
| Maintenance | Low (Windows Update handles WSL) | Medium (Docker Desktop updates) | Medium (manual VM maintenance) |
| Best for | Single contributor, convenience | Team reproducibility | Full isolation / snapshots |
| **Verdict** | **TAKE** | SKIP (overkill) | SKIP (overhead) |

### 4.2 Hardware-specific tuning (i5-1235U / 16GB)

Windows 11 idle + IDE + browser consumes ~6-9GB. The `.wslconfig` below caps WSL2 at 6GB, leaving headroom:

```ini
[wsl2]
memory=6GB
processors=6
swap=2GB
localhostForwarding=true
```

- `memory=6GB`: Hard cap. WSL2 will not balloon past this.
- `processors=6`: Leaves 6 threads for Windows host (1235U has 12 threads total). Keeps P-core threads available for IDE responsiveness.
- `swap=2GB`: Safety valve for memory spikes (`mutmut`, heavy pytest). WSL2 defaults swap file to `%LOCALAPPDATA%\Temp\`.
- `localhostForwarding=true`: Required for Remote-WSL port forwarding.

Known issue: WSL2 VM memory is not dynamically reclaimed. After heavy usage, run `wsl --shutdown` to free RAM. VHDX grows dynamically but never auto-shrinks — run `wsl --manage Ubuntu-24.04 --set-sparse true` to enable sparse files.

### 4.3 Setup procedure (verified commands)

```bash
# 1. Install WSL2 + Ubuntu 24.04 (PowerShell as Administrator)
wsl --install -d Ubuntu-24.04
# Reboot when prompted.

# 2. Inside WSL2 Ubuntu — install system deps
sudo apt update && sudo apt install -y build-essential git curl universal-ctags

# 3. Install uv (Astral package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart shell or source ~/.local/bin/env

# 4. Install just (task runner)
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin

# 5. Install Python 3.13 via uv
uv python install 3.13

# 6. Clone repo INSIDE WSL native filesystem (NOT /mnt/c/)
git clone https://github.com/first-agent-dev/First-Agent-dev.git ~/First-Agent-dev
cd ~/First-Agent-dev

# 7. (Optional) Share Windows Git credentials
# git config --global credential.helper "/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe"

# 8. Install project + dev deps, hooks, verify
uv sync --extra dev
pre-commit install
just check

# 9. Open in Windsurf / VS Code
# Ensure "WSL" extension is installed, then from WSL terminal:
# code .
```

## 5. Risks and caveats

- **9P performance trap:** The most common WSL2 dev mistake is cloning repos to `/mnt/c/Users/...`. Git operations, `pre-commit`, and `uv sync` become painfully slow. Always use `~/...` inside WSL.
- **Memory reclamation:** WSL2 does not shrink its VM memory footprint automatically. If Windows feels sluggish after a heavy dev session, `wsl --shutdown` reclaims RAM immediately.
- **WSL2 filesystem quirks:** `inotify` watchers have higher limits on native ext4 than on 9P mounts. This is irrelevant if the repo lives on ext4.
- **Windows Defender:** Real-time scanning of WSL2 files can add I/O overhead. Excluding the WSL2 VHDX or the repo path from Defender scanning is an optional micro-optimization.
- **VHDX bloat:** The WSL2 virtual disk grows dynamically but never auto-compacts. Sparse files (`wsl --manage --set-sparse true`) mitigate this.

## 6. Numbered recommendations (R-1..R-K)

### R-1 — Canonical Windows dev path: WSL2 + Ubuntu 24.04 (cost: cheap)

For all Windows 11 Pro contributors, WSL2 is the single recommended environment. It provides:
- Native Linux behavior matching CI (`ubuntu-latest`).
- Lowest setup friction (single PowerShell command).
- VS Code / Windsurf Remote-WSL for near-native IDE experience.
- No `core.autocrlf`, path-separator, or shell-quoting drift.

First concrete action: create this research note + update `llms.txt`.

## 7. Open questions (Q-1..Q-M)

### Q-1 — Should we add a `CONTRIBUTING.md` that links to this note?

Currently there is no `CONTRIBUTING.md`. Adding one is standard OSS practice but may be premature for a single-user project. If a second Windows contributor joins, this note should be surfaced there.

## 8. Files used

- `knowledge/research/_template.md` — research note format
- `justfile` — verified cross-platform task runner (windows-shell already set)
- `pyproject.toml` — verified `universal-ctags` as only OS-level dep; `[tool.first-agent.system-dependencies]` block
- `.github/workflows/advisory.yml` — verified CI runs on `ubuntu-latest`
- `.github/workflows/pylint.yml` — verified CI runs on `ubuntu-latest`
- Microsoft Learn: `https://learn.microsoft.com/en-us/windows/wsl/wsl-config`
- rsw.io: `https://rsw.io/best-wsl-settings-for-low-memory-systems-8gb-ram-or-less/`
- rsw.io: `https://rsw.io/wsl-2-vs-docker-desktop-which-one-should-you-use/`

## 9. Out of scope

- Local LLM inference setup (ollama, llama.cpp, vLLM) — user confirmed cloud APIs only.
- Windows-native Python development (rejected due to CI parity risk; covered in §"Why not Windows native?").
- Cloud dev environments (GitHub Codespaces, Gitpod) — contradict local-first architecture.
- macOS dev environment — different hardware constraints, out of scope.
- Production deployment environment — this note is for development only.
