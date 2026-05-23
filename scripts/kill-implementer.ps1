#requires -Version 5
<#
.SYNOPSIS
    DEPRECATED forwarding shim. Use scripts/kill-task.ps1.
.DESCRIPTION
    Phase 5 Stage C2. See kill-analyst.ps1 header for rationale.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId
)
[Console]::Error.WriteLine("DEPRECATED: use scripts/kill-task.ps1 (phase-agnostic)")
& (Join-Path $PSScriptRoot "kill-task.ps1") -TaskId $TaskId
exit $LASTEXITCODE
