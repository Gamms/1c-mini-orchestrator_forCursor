#requires -Version 5
<#
.SYNOPSIS
    Phase-agnostic kill for any Orchestrator task (Cursor runtime).
.DESCRIPTION
    Auto-detects the active phase, cancels the Cursor run via SDK when
    possible, kills wt windows whose title matches "<phase>:<TaskId>",
    and stamps killed_at on the packet.
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
    exit 1
}

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
    [Console]::Error.WriteLine("no packet found in $TaskRoot")
    exit 2
}

Write-Host ("phase: {0}" -f $detected.Name)
Write-Host ("title prefix: {0}" -f $detected.Title)

$killed = 0

$cancelHelper = Join-Path $PSScriptRoot "_python\cancel_cursor_run.py"
if ((Test-Path $cancelHelper) -and (Test-CursorApiKey)) {
    $py = Get-OrchestratorPython
    & $py $cancelHelper --task-root $TaskRoot --phase $detected.Name 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -eq 0) { $killed++ }
}

$titleMatch = "*{0}{1}*" -f $detected.Title, $TaskId
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

$psProcs = Get-Process -Name "powershell","pwsh","python","py" -ErrorAction SilentlyContinue |
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
Write-Host "killed $killed target(s) for TaskId=$TaskId (phase=$($detected.Name))"
exit 0
