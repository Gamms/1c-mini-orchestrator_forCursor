#requires -Version 5
<#
.SYNOPSIS
    Child wrapper: runs L3 implementer via Cursor SDK.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskRoot,
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$OrchestratorRoot,
    [Parameter(Mandatory=$true)][string]$PathLocal,
    [Parameter(Mandatory=$true)][string]$GiteaRemoteUrl,
    [string]$ExtraWritableDir = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_cursor-lib.ps1")

if (-not (Test-CursorApiKey)) { exit 1 }

Set-Location -Path $TaskRoot

$TaskId = Split-Path -Leaf $TaskRoot
$BranchName = "orchestrator/" + $TaskId
$env:ORCH_PATH_LOCAL = $PathLocal
$env:ORCH_BRANCH_NAME = $BranchName

Write-Host "L3 implementer (Cursor) -- task_root: $TaskRoot"
Write-Host "L3 implementer (Cursor) -- path_local: $PathLocal"
Write-Host "L3 implementer (Cursor) -- branch_name: $BranchName"
if ($ExtraWritableDir) {
    Write-Host "L3 implementer (Cursor) -- extra_writable_dir: $ExtraWritableDir"
}
Write-Host ""

$py = Get-OrchestratorPython
$runner = Get-CursorRunnerScript
$args = @(
    $runner,
    "--phase", "implementer",
    "--task-root", $TaskRoot,
    "--project-path", $ProjectPath,
    "--orchestrator-root", $OrchestratorRoot,
    "--path-local", $PathLocal
)
if ($ExtraWritableDir) {
    $args += @("--extra-writable-dir", $ExtraWritableDir)
}
& $py @args
exit $LASTEXITCODE
