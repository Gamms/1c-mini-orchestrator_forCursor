#requires -Version 5
<#
.SYNOPSIS
    Validate audit_report.json + branch SHA + four MCP sessions for a TaskId.
    Exit codes per Phase 4 SDD section 5.5.2 (0..15).
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

$validatePy = Join-Path $PSScriptRoot "_python\validate_audit.py"
& (Get-OrchestratorPython) $validatePy $TaskRoot
exit $LASTEXITCODE
