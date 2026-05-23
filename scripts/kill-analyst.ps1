#requires -Version 5
<#
.SYNOPSIS
    DEPRECATED forwarding shim. Use scripts/kill-task.ps1.
.DESCRIPTION
    Phase 5 Stage C2. kill-task.ps1 auto-detects the active phase
    (analyst/sdd-writer/implementer/auditor) from packet presence and
    kills the matching wt window + child processes. Keep this shim for
    one release for operator muscle-memory continuity; deletion deferred.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId
)
[Console]::Error.WriteLine("DEPRECATED: use scripts/kill-task.ps1 (phase-agnostic)")
& (Join-Path $PSScriptRoot "kill-task.ps1") -TaskId $TaskId
exit $LASTEXITCODE
