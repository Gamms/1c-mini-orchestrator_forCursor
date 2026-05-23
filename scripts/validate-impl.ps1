#requires -Version 5
<#
.SYNOPSIS
    Validate impl_metadata.json + branch + session.jsonl evidence for a TaskId.
    Exit codes per Phase 3 SDD section 5.5.1 (0..13).
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_cursor-lib.ps1")
$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskRoot = Join-Path $OrchestratorRoot "tasks\$TaskId"

if (-not (Test-Path $TaskRoot)) {
    [Console]::Error.WriteLine("task_root not found: $TaskRoot")
    exit 2
}

$validatePy = Join-Path $PSScriptRoot "_python\validate_impl.py"
& (Get-OrchestratorPython) $validatePy $TaskRoot
exit $LASTEXITCODE
