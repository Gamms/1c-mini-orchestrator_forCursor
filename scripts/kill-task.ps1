#requires -Version 5
<#
.SYNOPSIS
    Phase-agnostic kill for any Orchestrator task. Phase 5 Stage C1.
.DESCRIPTION
    Auto-detects the active phase the same way peek-task.ps1 does --
    by scanning tasks/<TaskId>/ for known packet files in priority
    order (auditor -> implementer -> sdd-writer -> analyst). Highest
    priority existing packet wins.

    Kills wt windows + powershell/pwsh/claude/codex/node processes whose
    MainWindowTitle matches "<phase>:<TaskId>" (the prefix set by the
    relevant spawn-*.ps1). Stamps the packet's killed_at field
    (UTC ISO-8601).

    Title prefix per phase:
        analyst:<TaskId>
        sdd-writer:<TaskId>
        implementer:<TaskId>
        auditor:<TaskId>

    Replaces the four per-phase wrappers kill-analyst.ps1 /
    kill-sdd-writer.ps1 / kill-implementer.ps1 / kill-auditor.ps1.
    Those wrappers remain as thin deprecation shims (Phase 5 Stage C2).

    ASCII-only. PowerShell 5.1.
    Exit 0: at least one process killed.
    Exit 1: task_root missing.
    Exit 2: no matching processes found.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId
)

$ErrorActionPreference = "Continue"
$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskRoot = Join-Path $OrchestratorRoot "tasks\$TaskId"

if (-not (Test-Path $TaskRoot)) {
    [Console]::Error.WriteLine("task_root not found: $TaskRoot")
    exit 1
}

# Phase descriptors in priority order: later phases supersede earlier ones.
$phases = @(
    [ordered]@{ Name="auditor";     Packet="auditor_packet.json";     Title="auditor:"     },
    [ordered]@{ Name="implementer"; Packet="implementer_packet.json"; Title="implementer:" },
    [ordered]@{ Name="sdd-writer";  Packet="sdd_writer_packet.json";  Title="sdd-writer:"  },
    [ordered]@{ Name="analyst";     Packet="task_packet.json";        Title="analyst:"     }
)

$detected = $null
foreach ($p in $phases) {
    $packetPath = Join-Path $TaskRoot $p.Packet
    if (Test-Path $packetPath) {
        $detected = [ordered]@{
            Name       = $p.Name
            Title      = $p.Title
            PacketPath = $packetPath
        }
        break
    }
}

if (-not $detected) {
    [Console]::Error.WriteLine("no packet found in $TaskRoot (none of: task_packet.json, sdd_writer_packet.json, implementer_packet.json, auditor_packet.json)")
    exit 2
}

Write-Host ("phase: {0}" -f $detected.Name)
Write-Host ("title prefix: {0}" -f $detected.Title)

$titleMatch = "*{0}{1}*" -f $detected.Title, $TaskId
$killed = 0

$wtProcs = Get-Process -Name "WindowsTerminal","wt" -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -like $titleMatch }
foreach ($p in $wtProcs) {
    try {
        Stop-Process -Id $p.Id -Force -ErrorAction Stop
        Write-Host "killed wt PID=$($p.Id) title=$($p.MainWindowTitle)"
        $killed++
    } catch {
        Write-Warning "failed to kill wt PID=$($p.Id): $_"
    }
}

# claude (Phases 1-3) and codex (Phase 4) plus their host shells / nodes.
$psProcs = Get-Process -Name "powershell","pwsh","claude","codex","node" -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -like $titleMatch }
foreach ($p in $psProcs) {
    try {
        Stop-Process -Id $p.Id -Force -ErrorAction Stop
        Write-Host "killed $($p.ProcessName) PID=$($p.Id)"
        $killed++
    } catch {
        Write-Warning "failed to kill $($p.ProcessName) PID=$($p.Id): $_"
    }
}

# Stamp killed_at on the packet for audit trail.
try {
    $packet = Get-Content -Path $detected.PacketPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $packet | Add-Member -NotePropertyName killed_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString("o")) -Force
    ($packet | ConvertTo-Json -Depth 10) | Out-File -FilePath $detected.PacketPath -Encoding utf8
} catch {
    Write-Warning "failed to stamp killed_at on $($detected.PacketPath): $_"
}

if ($killed -eq 0) {
    Write-Host "no matching processes found for TaskId=$TaskId (title pattern: $titleMatch)"
    exit 2
}
Write-Host "killed $killed process(es) for TaskId=$TaskId (phase=$($detected.Name))"
exit 0
