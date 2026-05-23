#requires -Version 5
<#
.SYNOPSIS
    Spawn an L3 analyst in a new Windows Terminal tab.
.DESCRIPTION
    Resolves projects.yaml -> renders per-task AGENTS.md and .mcp.json ->
    writes task_packet.json + prompt.md -> launches wt.exe nt with
    _run-analyst.ps1 (Cursor SDK) wrapper.

    Emits a single-line JSON to stdout with task metadata.

    -PrepareOnly: do everything EXCEPT the final wt.exe spawn. Used by
    Stage 4 verification to test file generation without opening a tab.
#>
param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [Parameter(Mandatory=$true)][string]$TaskText,
    [string]$TaskId = "",
    [switch]$PrepareOnly
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "_cursor-lib.ps1")

$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OrchestratorRoot = $OrchestratorRoot -replace '\\', '/'

$yamlGet = Join-Path $PSScriptRoot "_python\yaml_get.py"
$yamlOut = & (Get-OrchestratorPython) $yamlGet $ProjectId 2>&1
$yamlExit = $LASTEXITCODE
if ($yamlExit -ne 0) {
    Write-Error "yaml_get.py exit=$yamlExit for project '$ProjectId': $yamlOut"
    exit 1
}

$cfg = @{}
foreach ($line in ($yamlOut -split "`r?`n")) {
    if ($line -match '^([^=]+)=(.*)$') { $cfg[$Matches[1]] = $Matches[2] }
}
$ProjectPath   = $cfg['path_local']
$CodemetaPort  = $cfg['codemeta_port']
$VmDockerHost  = $cfg['vm_docker_host']
$McpServers    = $cfg['mcp_servers']

if (-not (Test-ProjectRegistryComplete -Cfg $cfg)) {
    Write-Error "yaml_get returned incomplete data: $yamlOut"
    exit 1
}

try {
    Test-ProjectPathInvariant -ProjectPath $ProjectPath -Cfg $cfg -ProjectId $ProjectId
} catch {
    Write-Error $_
    exit 1
}

$today = (Get-Date -Format "yyyy-MM-dd")
if (-not $TaskId) {
    $tasksRoot = Join-Path $OrchestratorRoot "tasks"
    if (-not (Test-Path $tasksRoot)) {
        New-Item -ItemType Directory -Path $tasksRoot -Force | Out-Null
    }
    $existing = Get-ChildItem -Path $tasksRoot -Directory -Filter "$today-$ProjectId-*" -ErrorAction SilentlyContinue
    $nextIdx = 1
    foreach ($d in $existing) {
        if ($d.Name -match "$today-$ProjectId-(\d+)") {
            $n = [int]$Matches[1]
            if ($n -ge $nextIdx) { $nextIdx = $n + 1 }
        }
    }
    $TaskId = "$today-$ProjectId-{0:D2}" -f $nextIdx
}

$TaskRoot = Join-Path $OrchestratorRoot "tasks/$TaskId"
$TaskRoot = $TaskRoot -replace '\\', '/'

if (Test-Path $TaskRoot) {
    Write-Error "task_root already exists: $TaskRoot. Pass a different -TaskId or remove the directory."
    exit 1
}

New-Item -ItemType Directory -Path $TaskRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $TaskRoot "analysis_raw") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $TaskRoot "scratch") -Force | Out-Null

$codemetaUrl = Get-ProjectCodemetaUrl -Cfg $cfg

$agentsTpl = Get-Content -Path (Join-Path $OrchestratorRoot "templates/analyst-AGENTS.md.tpl") -Raw -Encoding UTF8

$subst = @{
    "{PROJECT_ID}"        = $ProjectId
    "{PROJECT_PATH}"      = $ProjectPath
    "{TASK_ID}"           = $TaskId
    "{TASK_TEXT}"         = $TaskText
    "{ORCHESTRATOR_ROOT}" = $OrchestratorRoot
    "{TASK_ROOT_ABS}"     = $TaskRoot
    "{CODEMETADATA_URL}"  = $codemetaUrl
}
$agentsRendered = $agentsTpl
foreach ($k in $subst.Keys) {
    $agentsRendered = $agentsRendered.Replace($k, $subst[$k])
}

$agentsRendered | Out-File -FilePath (Join-Path $TaskRoot "AGENTS.md") -Encoding utf8
Write-TaskMcpConfig `
    -OrchestratorRoot $OrchestratorRoot `
    -TaskRoot $TaskRoot `
    -DestFileName ".mcp.json" `
    -Cfg $cfg `
    -TemplateRelativePath "templates/analyst-mcp.json.tpl" `
    -Subst $subst

$wtTitle = "analyst:$TaskId"
$taskPacket = [ordered]@{
    task_id                    = $TaskId
    project_id                 = $ProjectId
    project_path               = $ProjectPath
    task_text                  = $TaskText
    mcp_servers                = ($McpServers -split ',')
    codemetadata_url           = $codemetaUrl
    orchestrator_root          = $OrchestratorRoot
    task_root                  = $TaskRoot
    created_at                 = (Get-Date).ToUniversalTime().ToString("o")
    runtime                    = "cursor"
    wt_window_title            = $wtTitle
}
($taskPacket | ConvertTo-Json -Depth 10) | Out-File -FilePath (Join-Path $TaskRoot "task_packet.json") -Encoding utf8

$promptLines = @(
    "Read ./AGENTS.md in the current directory - it is your contract and lists absolute paths to prompts/skills.",
    "Then follow prompts/analyst.md (linked from that AGENTS.md). One pass, output analysis_report.json + announce REPORT READY."
)
($promptLines -join "`r`n") | Out-File -FilePath (Join-Path $TaskRoot "prompt.md") -Encoding utf8

$result = [ordered]@{
    task_id                   = $TaskId
    task_root                 = $TaskRoot
    project_path              = $ProjectPath
    wt_window_title           = $wtTitle
    runtime                   = "cursor"
    prepare_only              = [bool]$PrepareOnly.IsPresent
}

if ($PrepareOnly) {
    ($result | ConvertTo-Json -Compress)
    exit 0
}

if (-not (Test-CursorApiKey)) { exit 3 }

$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if (-not $wt) {
    Write-Warning "wt.exe not found in PATH. Files prepared at: $TaskRoot"
    Write-Warning "Manual run: powershell.exe -NoExit -ExecutionPolicy Bypass -File ""$PSScriptRoot\_run-analyst.ps1"" -TaskRoot ""$TaskRoot"" -ProjectPath ""$ProjectPath"" -OrchestratorRoot ""$OrchestratorRoot"""
    ($result | ConvertTo-Json -Compress)
    exit 2
}

$runWrapper = Join-Path $PSScriptRoot "_run-analyst.ps1"
& wt.exe -w 0 nt `
    --title $wtTitle `
    powershell.exe -NoExit -ExecutionPolicy Bypass `
        -File $runWrapper `
        -TaskRoot $TaskRoot `
        -ProjectPath $ProjectPath `
        -OrchestratorRoot $OrchestratorRoot

($result | ConvertTo-Json -Compress)
