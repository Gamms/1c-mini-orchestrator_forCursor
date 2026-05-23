#requires -Version 5
<#
.SYNOPSIS
    Validate sdd_metadata.json + sdd.md + session.jsonl evidence for a TaskId.
    Exit codes per Phase 2 SDD section 5.1.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId
)

$ErrorActionPreference = "Continue"
$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskRoot = Join-Path $OrchestratorRoot "tasks\$TaskId"

if (-not (Test-Path $TaskRoot)) {
    [Console]::Error.WriteLine("task_root not found: $TaskRoot")
    exit 4
}

$validatePy = Join-Path $PSScriptRoot "_python\validate_sdd.py"
& python $validatePy $TaskRoot
exit $LASTEXITCODE
