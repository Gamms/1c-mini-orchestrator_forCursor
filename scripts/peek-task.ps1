#requires -Version 5
<#
.SYNOPSIS
    Phase-agnostic peek for any Orchestrator task. Phase 5 Stage C1.
.DESCRIPTION
    Auto-detects the active phase by scanning tasks/<TaskId>/ for known
    packet files in priority order (auditor -> implementer -> sdd-writer
    -> analyst). The highest-priority existing packet wins -- later phases
    supersede earlier ones in the chain.

    Dispatches to the correct session log parser:
      * claude runtime (analyst / sdd-writer / implementer):
          discovers ~/.claude/projects/*Orchestrator*tasks*<TaskId>*/
          and tails the matching jsonl by mtime vs packet.created_at.
      * codex runtime (auditor):
          reads packet.codex_home and shells out to
          scripts/_python/peek_codex_rollout.py.

    Replaces the four per-phase wrappers peek-analyst.ps1 /
    peek-sdd-writer.ps1 / peek-implementer.ps1 / peek-auditor.ps1.
    Those wrappers remain as thin deprecation shims (Phase 5 Stage C2)
    that forward to this script.

    ASCII-only. PowerShell 5.1. Exits 0 even when the session log is
    absent (prints STATUS: ...).
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [int]$Tail = 30
)

$ErrorActionPreference = "Continue"
$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$TaskRoot = Join-Path $OrchestratorRoot "tasks\$TaskId"

if (-not (Test-Path $TaskRoot)) {
    Write-Host "STATUS: task_root_missing ($TaskRoot)"
    exit 0
}

# Phase descriptors in priority order: later phases supersede earlier ones.
$phases = @(
    [ordered]@{ Name="auditor";     Packet="auditor_packet.json";     Runtime="codex"  },
    [ordered]@{ Name="implementer"; Packet="implementer_packet.json"; Runtime="claude" },
    [ordered]@{ Name="sdd-writer";  Packet="sdd_writer_packet.json";  Runtime="claude" },
    [ordered]@{ Name="analyst";     Packet="task_packet.json";        Runtime="claude" }
)

$detected = $null
foreach ($p in $phases) {
    $packetPath = Join-Path $TaskRoot $p.Packet
    if (Test-Path $packetPath) {
        $detected = [ordered]@{
            Name       = $p.Name
            Runtime    = $p.Runtime
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
Write-Host ("runtime: {0}" -f $detected.Runtime)
Write-Host ("packet: {0}" -f $detected.PacketPath)

# Parse common packet fields.
$createdAt = $null
$codexHome = $null
try {
    $packet = Get-Content -Path $detected.PacketPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($packet.PSObject.Properties.Name -contains "created_at") {
        $createdAt = [datetime]::Parse($packet.created_at).ToUniversalTime()
    }
    if ($packet.PSObject.Properties.Name -contains "codex_home") {
        $codexHome = [string]$packet.codex_home
    }
} catch {
    Write-Host "STATUS: packet_parse_failed ($_)"
    exit 0
}

if ($detected.Runtime -eq "codex") {
    if (-not $codexHome) {
        Write-Host "STATUS: auditor_packet_missing_codex_home"
        exit 0
    }
    if (-not (Test-Path $codexHome)) {
        Write-Host "STATUS: codex_home_missing ($codexHome)"
        exit 0
    }
    $helper = Join-Path $PSScriptRoot "_python\peek_codex_rollout.py"
    if (-not (Test-Path $helper)) {
        [Console]::Error.WriteLine("peek_codex_rollout.py missing at $helper")
        exit 1
    }
    $startedAt = ""
    if ($createdAt) { $startedAt = $createdAt.ToString("o") }
    $pyArgs = @(
        $helper,
        "--codex-home", $codexHome,
        "--started-at", $startedAt,
        "--task-id", $TaskId,
        "--tail", $Tail
    )
    & python @pyArgs
    exit $LASTEXITCODE
}

# claude runtime: discover ~/.claude/projects/*Orchestrator*tasks*<TaskId>*/
$projectsRoot = Join-Path $env:USERPROFILE ".claude\projects"
if (-not (Test-Path $projectsRoot)) {
    Write-Host "STATUS: not_started_yet (no ~/.claude/projects dir)"
    exit 0
}

$candidates = Get-ChildItem -Path $projectsRoot -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*Orchestrator*tasks*$TaskId*" }

if (-not $candidates -or $candidates.Count -eq 0) {
    Write-Host "STATUS: not_started_yet (no session dir yet for TaskId=$TaskId)"
    exit 0
}

$sessionDir = $candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$jsonlFiles = Get-ChildItem -Path $sessionDir.FullName -Filter "*.jsonl" -ErrorAction SilentlyContinue

if (-not $jsonlFiles -or $jsonlFiles.Count -eq 0) {
    Write-Host "STATUS: session_dir_found_but_no_jsonl ($($sessionDir.FullName))"
    exit 0
}

# Partition by mtime vs packet.created_at when applicable. analyst's
# task_packet.json has no created_at; in that case fall back to newest jsonl.
$jsonl = $null
if ($createdAt -and $detected.Name -ne "analyst") {
    $candidatesJsonl = $jsonlFiles | Where-Object { $_.LastWriteTimeUtc -ge $createdAt }
    if ($candidatesJsonl -and $candidatesJsonl.Count -gt 0) {
        $jsonl = $candidatesJsonl | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    } else {
        Write-Host ("STATUS: no_{0}_jsonl_yet (no jsonl newer than packet.created_at={1})" -f $detected.Name, $createdAt.ToString("o"))
        exit 0
    }
} else {
    $jsonl = $jsonlFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

Write-Host "session: $($jsonl.FullName)"
Write-Host "size: $($jsonl.Length) bytes"
Write-Host ""

$lines = Get-Content -Path $jsonl.FullName -Tail $Tail -Encoding UTF8
$idx = 0
foreach ($line in $lines) {
    $idx++
    try {
        $ev = $line | ConvertFrom-Json
    } catch {
        Write-Host "  [$idx] <unparseable line: $($line.Substring(0,[Math]::Min(80,$line.Length)))>"
        continue
    }

    $kind = $null
    if ($ev.PSObject.Properties.Name -contains "type") { $kind = $ev.type }
    if ($ev.PSObject.Properties.Name -contains "message") {
        $msg = $ev.message
        if ($msg.PSObject.Properties.Name -contains "role") {
            $role = $msg.role
            if ($msg.PSObject.Properties.Name -contains "content" -and $msg.content) {
                foreach ($c in $msg.content) {
                    if ($c.type -eq "tool_use") {
                        $args = ""
                        if ($c.PSObject.Properties.Name -contains "input") {
                            $args = ($c.input | ConvertTo-Json -Compress -Depth 5)
                            if ($args.Length -gt 100) { $args = $args.Substring(0,100) + "..." }
                        }
                        Write-Host "  [$idx] tool_use $($c.name) $args"
                    } elseif ($c.type -eq "tool_result") {
                        $status = "ok"
                        if ($c.PSObject.Properties.Name -contains "is_error" -and $c.is_error) { $status = "error" }
                        $clen = 0
                        if ($c.PSObject.Properties.Name -contains "content") {
                            $clen = ($c.content | Out-String).Length
                        }
                        Write-Host "  [$idx] tool_result $status len=$clen"
                    } elseif ($c.type -eq "text") {
                        $txt = $c.text
                        if ($txt -and $txt.Length -gt 200) { $txt = $txt.Substring(0,200) + "..." }
                        Write-Host ("  [{0}] {1}: {2}" -f $idx, $role, $txt)
                    }
                }
                continue
            }
        }
    }
    if (-not $kind) { $kind = "<unknown>" }
    Write-Host "  [$idx] $kind"
}

$ageSec = [int]((Get-Date) - $jsonl.LastWriteTime).TotalSeconds
Write-Host ""
Write-Host "LAST_EVENT_AGO=${ageSec}s"
if ($ageSec -gt 300) {
    Write-Host ("WARNING: {0} may be stuck (no events for >300s)" -f $detected.Name)
}
