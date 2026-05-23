#requires -Version 5
<#
.SYNOPSIS
    Validate analysis_report.json for a given TaskId. Exit codes per SDD section 5.1.
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

$validatePy = Join-Path $PSScriptRoot "_python\validate.py"
& python $validatePy $TaskRoot
exit $LASTEXITCODE
