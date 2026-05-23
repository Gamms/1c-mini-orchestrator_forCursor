#requires -Version 5
<#
.SYNOPSIS
    Child wrapper inside the spawned wt tab for auditor (Phase 4).
.DESCRIPTION
    Sets CWD to TaskRoot, redirects $env:CODEX_HOME to
    <TaskRoot>\.codex_home (where spawn-auditor.ps1 has written the
    per-task config.toml), then invokes `codex exec` with --cd,
    --add-dir, --dangerously-bypass-approvals-and-sandbox, optional
    -m, and a positional prompt.

    Stage 0 finding (Phase 4 SDD section 5.4.2): codex 0.130.0 has no
    `--config <path>` flag, so per-task MCP isolation is delivered via
    CODEX_HOME redirect rather than a CLI flag.

    Logs:
      - <TaskRoot>\audit.log    stdout/stderr of codex
      - <TaskRoot>\audit.status pid + exit code line after codex returns
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskRoot,
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$OrchestratorRoot,
    [Parameter(Mandatory=$true)][string]$PathLocal,
    [string]$ExtraWritableDir = "",
    [string]$Model = ""
)

$ErrorActionPreference = "Continue"

if (-not (Test-Path $TaskRoot)) {
    [Console]::Error.WriteLine("TaskRoot not found: $TaskRoot")
    exit 1
}

Set-Location -Path $TaskRoot

$promptPath = Join-Path $TaskRoot "prompt.auditor.md"
if (-not (Test-Path $promptPath)) {
    [Console]::Error.WriteLine("prompt.auditor.md not found at $promptPath")
    exit 1
}
$prompt = (Get-Content -Path $promptPath -Raw -Encoding UTF8).TrimEnd()

$codexHome = Join-Path $TaskRoot ".codex_home"
$codexHomeWin = $codexHome -replace '/', '\'
if (-not (Test-Path (Join-Path $codexHomeWin "config.toml"))) {
    [Console]::Error.WriteLine(".codex_home/config.toml not found under $codexHomeWin")
    [Console]::Error.WriteLine("spawn-auditor.ps1 should have rendered it; aborting.")
    exit 1
}

$TaskId = Split-Path -Leaf $TaskRoot
$BranchName = "orchestrator/" + $TaskId

# Env vars for any prompt-side substitution + CODEX_HOME redirect
$env:CODEX_HOME       = $codexHomeWin
$env:ORCH_PATH_LOCAL  = $PathLocal
$env:ORCH_BRANCH_NAME = $BranchName

Write-Host "L3 auditor -- task_root:         $TaskRoot"
Write-Host "L3 auditor -- project_path:      $ProjectPath"
Write-Host "L3 auditor -- orchestrator_root: $OrchestratorRoot"
Write-Host "L3 auditor -- path_local:        $PathLocal"
if ($ExtraWritableDir) {
    Write-Host "L3 auditor -- extra_writable_dir: $ExtraWritableDir"
}
Write-Host "L3 auditor -- branch_audited:    $BranchName"
Write-Host "L3 auditor -- CODEX_HOME:        $codexHomeWin"
if ($Model) {
    Write-Host "L3 auditor -- model:             $Model"
} else {
    Write-Host "L3 auditor -- model:             <codex default>"
}
Write-Host ""

$logPath    = Join-Path $TaskRoot "audit.log"
$statusPath = Join-Path $TaskRoot "audit.status"

# Build codex args. -m only when Model non-empty (codex falls back to
# its configured default model otherwise).
$codexArgs = @(
    "exec",
    "--cd", $TaskRoot,
    "--add-dir", $PathLocal,
    "--add-dir", $OrchestratorRoot
)
if ($ExtraWritableDir) {
    $codexArgs += @("--add-dir", $ExtraWritableDir)
}
$codexArgs += @("--dangerously-bypass-approvals-and-sandbox")
if ($Model) {
    $codexArgs += @("-m", $Model)
}
$codexArgs += @("--", $prompt)

$startedAt = (Get-Date).ToUniversalTime().ToString("o")

# Run codex; tee stdout/stderr to audit.log AND to current console.
# Use a try/finally to always write audit.status even on hard error.
$codexExit = -1
try {
    & codex @codexArgs 2>&1 | Tee-Object -FilePath $logPath | ForEach-Object { Write-Host $_ }
    $codexExit = $LASTEXITCODE
} catch {
    "ERROR invoking codex: $_" | Out-File -FilePath $logPath -Append -Encoding utf8
    $codexExit = 99
} finally {
    $endedAt = (Get-Date).ToUniversalTime().ToString("o")
    $statusLines = @(
        "pid=$PID",
        "exit=$codexExit",
        "started_at=$startedAt",
        "ended_at=$endedAt"
    )
    ($statusLines -join "`r`n") | Out-File -FilePath $statusPath -Encoding ascii
}

Write-Host ""
Write-Host "codex exit: $codexExit"
exit $codexExit
