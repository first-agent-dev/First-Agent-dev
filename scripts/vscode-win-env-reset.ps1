<#
  Bootstrap / reset script for First-Agent-dev repo.

  This script:
    - resolves the repo root and validates it
    - ensures uv/just/bash are discoverable on PATH (and persists PATH for the User scope)
    - resets local git hooks (refusing to touch global/system hooksPath)
    - wipes local caches and the virtual environment, then rebuilds them
    - reinstalls repo hooks via `just install`
    - stops and prompts you to run all checks manually

  WARNING: this is destructive locally: it removes .venv, tool caches, and any
  repo-local git hook scripts (backed up first under .git/fa-hook-backup), and it
  permanently updates the current user's PATH environment variable.

  Usage:
    .\vscode-win-env-reset.ps1            # asks for confirmation
    .\vscode-win-env-reset.ps1 -Force     # skips confirmation
#>
param(
  [switch] $Force
)

$ErrorActionPreference = "Stop"
# PS 7.3+: without this, native non-zero exits become terminating errors and
# break Invoke-Native messaging.
$PSNativeCommandUseErrorActionPreference = $false
Set-StrictMode -Version Latest

function ConvertTo-PathEntry {
  param([AllowNull()][string] $PathEntry)

  if ([string]::IsNullOrWhiteSpace($PathEntry)) {
    return $null
  }

  return $PathEntry.Trim().TrimEnd('\')
}

function Test-PathEntryEquals {
  param(
    [string] $Left,
    [string] $Right
  )

  $a = ConvertTo-PathEntry $Left
  $b = ConvertTo-PathEntry $Right
  if ($null -eq $a -or $null -eq $b) {
    return $false
  }

  return $a.Equals($b, [System.StringComparison]::OrdinalIgnoreCase)
}

function Add-UniquePathEntries {
  param(
    [string[]] $Existing,
    [string[]] $ToAdd,
    [ref] $Changed
  )

  $result = @($Existing | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $didChange = $false

  foreach ($candidate in $ToAdd) {
    if ([string]::IsNullOrWhiteSpace($candidate)) {
      continue
    }

    $alreadyPresent = $false
    foreach ($existing in $result) {
      if (Test-PathEntryEquals $existing $candidate) {
        $alreadyPresent = $true
        break
      }
    }

    if (-not $alreadyPresent) {
      $result += $candidate
      $didChange = $true
    }
  }

  if ($null -ne $Changed) {
    $Changed.Value = $didChange
  }

  return $result
}

function Get-GitConfigValues {
  param(
    [Parameter(Mandatory = $true)]
    [string[]] $GitArgs
  )

  # git config --get* returns exit 1 when the key is absent — that is normal.
  $output = & git @GitArgs 2>$null
  $code = $LASTEXITCODE

  if ($code -notin 0, 1) {
    throw "git $($GitArgs -join ' ') failed with exit code $code"
  }

  if ($code -eq 1 -or $null -eq $output) {
    return @()
  }

  return @($output | ForEach-Object { "$_".Trim() } | Where-Object { $_ })
}

function Invoke-Native {
  param(
    [Parameter(Mandatory = $true)]
    [string] $Exe,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $ArgumentList
  )

  if ($null -eq $ArgumentList) {
    $ArgumentList = @()
  }

  Write-Host ""
  Write-Host ">>> $Exe $($ArgumentList -join ' ')" -ForegroundColor Cyan
  & $Exe @ArgumentList

  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $Exe $($ArgumentList -join ' ')"
  }
}

Write-Host ""
Write-Host "=== First-Agent-dev bootstrap / reset ===" -ForegroundColor Green
Write-Host "This script will:"
Write-Host "  - verify repo root and required tools (git, uv, just, bash)"
Write-Host "  - may permanently update your User PATH (uv tools + Git bash/cmd)"
Write-Host "  - clear local core.hooksPath and refuse global/system hooksPath"
Write-Host "  - backup then remove local git hook files"
Write-Host "  - remove .venv and local tool caches"
Write-Host "  - reinstall deps/hooks"
Write-Host "  - STOP and prompt you to run checks manually"
Write-Host ""

if (-not $Force) {
  $confirm = Read-Host "Continue? (y/N)"
  if ($confirm -notmatch '^(y|yes)$') {
    throw "Aborted by user."
  }
}

Write-Host ""
Write-Host "STEP 0 — Prerequisites" -ForegroundColor Green

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  throw "git is not installed or not on PATH."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  throw "uv is not installed or not on PATH."
}

Write-Host ""
Write-Host "STEP 1 — Resolve repository root" -ForegroundColor Green

$repoRoot = & git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($repoRoot)) {
  throw "Not inside a git repository."
}
$repoRoot = $repoRoot.Trim()

Set-Location -LiteralPath $repoRoot

if (-not (Test-Path -LiteralPath "knowledge/llms.txt")) {
  throw "This does not look like First-Agent-dev repo root: knowledge/llms.txt is missing."
}

Write-Host "Repo root: $repoRoot"
Invoke-Native git status --short

Write-Host ""
Write-Host "STEP 2 — Ensure just/Git Bash paths are in current and user PATH" -ForegroundColor Green

$uvToolBin = & uv tool dir --bin
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($uvToolBin)) {
  throw "uv tool dir --bin failed."
}
$uvToolBin = $uvToolBin.Trim()

New-Item -ItemType Directory -Path $uvToolBin -Force | Out-Null

$gitRoots = [System.Collections.Generic.List[string]]::new()
foreach ($candidate in @(
    "C:\Program Files\Git",
    "C:\Program Files (x86)\Git"
  )) {
  if (Test-Path -LiteralPath $candidate) {
    $gitRoots.Add($candidate)
  }
}

$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if ($null -ne $gitCmd -and -not [string]::IsNullOrWhiteSpace($gitCmd.Source)) {
  # Typical layouts: <root>\cmd\git.exe or <root>\bin\git.exe
  $gitParent = Split-Path -Parent $gitCmd.Source
  $gitRootFromCmd = Split-Path -Parent $gitParent
  if (-not [string]::IsNullOrWhiteSpace($gitRootFromCmd) -and (Test-Path -LiteralPath $gitRootFromCmd)) {
    $gitRoots.Add($gitRootFromCmd)
  }
}

$pathsToAdd = [System.Collections.Generic.List[string]]::new()
$pathsToAdd.Add($uvToolBin)

foreach ($gitRoot in ($gitRoots | Select-Object -Unique)) {
  foreach ($sub in @("cmd", "bin", "usr\bin")) {
    $p = Join-Path $gitRoot $sub
    if (Test-Path -LiteralPath $p) {
      $pathsToAdd.Add($p)
    }
  }
}

$pathsToAddArray = @(
  $pathsToAdd |
    Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_) } |
    Select-Object -Unique
)

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($null -eq $userPath) {
  $userPath = ""
}

$currentUserPaths = @($userPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$userPathChanged = $false
$updatedUserPaths = Add-UniquePathEntries -Existing $currentUserPaths -ToAdd $pathsToAddArray -Changed ([ref]$userPathChanged)

if ($userPathChanged) {
  [Environment]::SetEnvironmentVariable("Path", ($updatedUserPaths -join ";"), "User")
  Write-Host "Updated permanent User PATH." -ForegroundColor Yellow
}
else {
  Write-Host "User PATH already contains required entries."
}

$sessionPathChanged = $false
$sessionPaths = @($env:Path -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$env:Path = (Add-UniquePathEntries -Existing $sessionPaths -ToAdd $pathsToAddArray -Changed ([ref]$sessionPathChanged)) -join ";"

Write-Host "Added/confirmed PATH entries:"
$pathsToAddArray | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "STEP 3 — Ensure just is installed" -ForegroundColor Green

if (-not (Get-Command just -ErrorAction SilentlyContinue)) {
  Invoke-Native uv tool install rust-just
  $sessionPaths = @($env:Path -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  $ignored = $false
  $env:Path = (Add-UniquePathEntries -Existing $sessionPaths -ToAdd @($uvToolBin) -Changed ([ref]$ignored)) -join ";"
}

if (-not (Get-Command just -ErrorAction SilentlyContinue)) {
  throw "just is still not visible on PATH after installation."
}

if (-not (Get-Command bash -ErrorAction SilentlyContinue)) {
  throw "bash is not visible on PATH. Install Git for Windows or add Git bin/cmd to PATH."
}

Invoke-Native just --version
Invoke-Native bash -lc "command -v uv && command -v just && just --version"

Write-Host ""
Write-Host "STEP 4 — Reset local core.hooksPath only; refuse unsafe global hook override" -ForegroundColor Green

# Wrap in @() to prevent PowerShell from unwrapping empty arrays to $null,
# which throws under Set-StrictMode when accessing .Count
$localHookPath = @(Get-GitConfigValues -GitArgs @("config", "--local", "--get-all", "core.hooksPath"))
if ($localHookPath.Count -gt 0) {
  Write-Host "Removing local core.hooksPath:"
  $localHookPath | ForEach-Object { Write-Host "  $_" }
  Invoke-Native git config --local --unset-all core.hooksPath
}

$remainingHookPath = @(Get-GitConfigValues -GitArgs @("config", "--get-all", "core.hooksPath"))
if ($remainingHookPath.Count -gt 0) {
  Write-Host ""
  Write-Host "core.hooksPath is still set outside local repo scope:" -ForegroundColor Red
  $remainingHookPath | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
  throw "Refusing to install repo hooks into a global/system hooksPath. Remove or review this setting manually."
}

$hooksDir = & git rev-parse --git-path hooks
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($hooksDir)) {
  throw "Could not resolve git hooks directory."
}
$hooksDir = $hooksDir.Trim()
if (-not [System.IO.Path]::IsPathRooted($hooksDir)) {
  $hooksDir = Join-Path $repoRoot $hooksDir
}

New-Item -ItemType Directory -Path $hooksDir -Force | Out-Null
Write-Host "Effective hooks dir: $hooksDir"

Write-Host ""
Write-Host "STEP 5 — Backup and remove repo hook files" -ForegroundColor Green

# Resolve .git directory so we can store backups inside it (durable and untracked by git status)
$gitDir = & git rev-parse --git-dir
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($gitDir)) {
  throw "Could not resolve .git directory."
}
$gitDir = $gitDir.Trim()
if (-not [System.IO.Path]::IsPathRooted($gitDir)) {
  $gitDir = Join-Path $repoRoot $gitDir
}

$backupDir = Join-Path (Join-Path $gitDir "fa-hook-backup") (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$hookNames = @("pre-commit", "pre-push", "prepare-commit-msg", "commit-msg")

foreach ($name in $hookNames) {
  $target = Join-Path $hooksDir $name
  $item = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue

  if ($null -ne $item -and -not $item.PSIsContainer) {
    Copy-Item -LiteralPath $target -Destination (Join-Path $backupDir $name) -Force
    Remove-Item -LiteralPath $target -Force
    Write-Host "Backed up and removed: $target"
  }
}

Write-Host "Hook backup dir: $backupDir"

Write-Host ""
Write-Host "STEP 6 — Remove local caches and recreate clean .venv" -ForegroundColor Green

$cacheItems = @(
  ".ruff_cache",
  ".mypy_cache",
  ".pytest_cache",
  ".coverage",
  "coverage.xml",
  "htmlcov",
  ".mutmut-cache",
  "mutants",
  ".gremlins-cache",
  "gremlin-report.html"
)

foreach ($item in $cacheItems) {
  if (Test-Path -LiteralPath $item) {
    Remove-Item -LiteralPath $item -Recurse -Force
    Write-Host "Removed cache/artifact: $item"
  }
}

if (Test-Path -LiteralPath ".venv") {
  try {
    Remove-Item -LiteralPath ".venv" -Recurse -Force -ErrorAction Stop
    Write-Host "Removed .venv"
  }
  catch {
    throw "Cannot remove .venv (files likely locked by IDE/Python/antivirus). Close processes using the venv and rerun. Details: $($_.Exception.Message)"
  }
}

# Single sync after wipe
Invoke-Native uv sync --extra dev
Invoke-Native uv run python --version
Invoke-Native uv run pre-commit --version
Invoke-Native uv run pre-commit clean
Invoke-Native uv run pre-commit gc

Write-Host ""
Write-Host "STEP 7 — Reinstall repo hooks through the repo bootstrap" -ForegroundColor Green

Invoke-Native just install
Invoke-Native just hooks-status

Write-Host ""
Write-Host "STEP 8 — Verify hook shell can see uv and just" -ForegroundColor Green

Invoke-Native bash -lc "set -e; command -v uv; command -v just; uv --version; just --version"

Write-Host ""
Write-Host "=== Bootstrap complete ===" -ForegroundColor Green
Write-Host "The local environment has been rebuilt successfully."
Write-Host "Now fully restart VS Code (or your terminal/IDE) so it picks up the new .venv and PATH changes."
Write-Host ""
Write-Host "Hook file backups (if any): $backupDir"
Write-Host ""
Write-Host "Next steps (run manually):" -ForegroundColor Cyan
Write-Host "  1. uv run just fix           # Run autofixers (may require manual fixes)"
Write-Host "  2. uv run pre-commit run --hook-stage pre-commit --all-files"
Write-Host "  3. uv run just check          # Run linters, type checkers, and tests"
Write-Host ""
Write-Host "After making a commit, ensure your VS Code Source Control UI is working." -ForegroundColor Yellow