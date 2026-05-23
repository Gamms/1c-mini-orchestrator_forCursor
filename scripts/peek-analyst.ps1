#requires -Version 5
<#
.SYNOPSIS
    DEPRECATED forwarding shim. Use scripts/peek-task.ps1.
.DESCRIPTION
    Phase 5 Stage C2. peek-task.ps1 auto-detects the active phase
    (analyst/sdd-writer/implementer/auditor) from packet presence and
    dispatches to the correct session log parser. Keep this shim for
    one release for operator muscle-memory continuity; deletion deferred.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [int]$Tail = 30
)
[Console]::Error.WriteLine("DEPRECATED: use scripts/peek-task.ps1 (phase-agnostic)")
& (Join-Path $PSScriptRoot "peek-task.ps1") -TaskId $TaskId -Tail $Tail
exit $LASTEXITCODE
