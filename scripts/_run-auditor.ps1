#requires -Version 5
<#
.SYNOPSIS
    Child wrapper: runs L3 auditor via Cursor SDK.
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
. (Join-Path $PSScriptRoot "_cursor-lib.ps1")

if (-not (Test-CursorApiKey)) { exit 1 }

Set-Location -Path $TaskRoot

$TaskId = Split-Path -Leaf $TaskRoot
$BranchName = "orchestrator/" + $TaskId
$env:ORCH_PATH_LOCAL = $PathLocal
$env:ORCH_BRANCH_NAME = $BranchName

Write-Host "L3 auditor (Cursor) -- task_root: $TaskRoot"
Write-Host "L3 auditor (Cursor) -- path_local: $PathLocal"
Write-Host "L3 auditor (Cursor) -- branch_audited: $BranchName"
if ($ExtraWritableDir) {
    Write-Host "L3 auditor (Cursor) -- extra_writable_dir: $ExtraWritableDir"
}
if ($Model) {
    Write-Host "L3 auditor (Cursor) -- model: $Model"
}
Write-Host ""

$py = Get-OrchestratorPython
$runner = Get-CursorRunnerScript
$args = @(
    $runner,
    "--phase", "auditor",
    "--task-root", $TaskRoot,
    "--project-path", $ProjectPath,
    "--orchestrator-root", $OrchestratorRoot,
    "--path-local", $PathLocal
)
if ($ExtraWritableDir) {
    $args += @("--extra-writable-dir", $ExtraWritableDir)
}
if ($Model) {
    $args += @("--model", $Model)
}
& $py @args
exit $LASTEXITCODE
