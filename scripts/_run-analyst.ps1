#requires -Version 5
<#
.SYNOPSIS
    Child wrapper: runs L3 analyst via Cursor SDK.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskRoot,
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$OrchestratorRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_cursor-lib.ps1")

if (-not (Test-CursorApiKey)) { exit 1 }

Set-Location -Path $TaskRoot

Write-Host "L3 analyst (Cursor) -- task_root: $TaskRoot"
Write-Host "L3 analyst (Cursor) -- project_path: $ProjectPath"
Write-Host "L3 analyst (Cursor) -- orchestrator_root: $OrchestratorRoot"
Write-Host ""

$py = Get-OrchestratorPython
$runner = Get-CursorRunnerScript
& $py $runner `
    --phase analyst `
    --task-root $TaskRoot `
    --project-path $ProjectPath `
    --orchestrator-root $OrchestratorRoot
exit $LASTEXITCODE
