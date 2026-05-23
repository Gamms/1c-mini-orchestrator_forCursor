#requires -Version 5
<#
.SYNOPSIS
    DEPRECATED forwarding shim. Use scripts/peek-task.ps1.
.DESCRIPTION
    Phase 5 Stage C2. See peek-analyst.ps1 header for rationale.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [int]$Tail = 30
)
[Console]::Error.WriteLine("DEPRECATED: use scripts/peek-task.ps1 (phase-agnostic)")
& (Join-Path $PSScriptRoot "peek-task.ps1") -TaskId $TaskId -Tail $Tail
exit $LASTEXITCODE
