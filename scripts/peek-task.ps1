#requires -Version 5
<#
.SYNOPSIS
    Phase-agnostic peek for any Orchestrator task (Cursor runtime).
.DESCRIPTION
    Auto-detects the active phase by scanning tasks/<TaskId>/ for known
    packet files in priority order (auditor -> implementer -> sdd-writer
    -> analyst). Dispatches to scripts/_python/peek_cursor_run.py.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [int]$Tail = 30
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_cursor-lib.ps1")

$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskRoot = Join-Path $OrchestratorRoot "tasks\$TaskId"

if (-not (Test-Path $TaskRoot)) {
    Write-Host "STATUS: task_root_missing ($TaskRoot)"
    exit 0
}

$phases = @(
    [ordered]@{ Name="auditor";     Packet="auditor_packet.json"     },
    [ordered]@{ Name="implementer"; Packet="implementer_packet.json" },
    [ordered]@{ Name="sdd-writer";  Packet="sdd_writer_packet.json"  },
    [ordered]@{ Name="analyst";     Packet="task_packet.json"        }
)

$detected = $null
foreach ($p in $phases) {
    $packetPath = Join-Path $TaskRoot $p.Packet
    if (Test-Path $packetPath) {
        $detected = [ordered]@{
            Name       = $p.Name
            PacketPath = $packetPath
        }
        break
    }
}

if (-not $detected) {
    Write-Host "STATUS: no_packet_found (none of: task_packet.json, sdd_writer_packet.json, implementer_packet.json, auditor_packet.json in $TaskRoot)"
    exit 0
}

Write-Host ("phase: {0}" -f $detected.Name)
Write-Host ("packet: {0}" -f $detected.PacketPath)

$helper = Join-Path $PSScriptRoot "_python\peek_cursor_run.py"
if (-not (Test-Path $helper)) {
    [Console]::Error.WriteLine("peek_cursor_run.py missing at $helper")
    exit 1
}

$py = Get-OrchestratorPython
& $py $helper --task-root $TaskRoot --phase $detected.Name --tail $Tail
exit $LASTEXITCODE
