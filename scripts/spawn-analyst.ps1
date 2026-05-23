#requires -Version 5
<#
.SYNOPSIS
    Spawn an L3 analyst in a new Windows Terminal tab.
.DESCRIPTION
    Resolves projects.yaml -> renders per-task CLAUDE.md and .mcp.json ->
    writes task_packet.json + prompt.md -> pre-trusts CWD + orchestrator
    root -> launches wt.exe nt with _run-analyst.ps1 wrapper.

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

function Encode-ClaudePath {
    param([Parameter(Mandatory=$true)][string]$Path)
    $enc = $Path -replace ':', '-' -replace '\\', '-' -replace '/', '-'
    return $enc.TrimStart('-')
}

function Write-PreTrust {
    param([Parameter(Mandatory=$true)][string]$AbsPath)
    $encoded = Encode-ClaudePath $AbsPath
    $variants = @($encoded)
    if ($encoded.Length -ge 1) {
        $first = $encoded.Substring(0,1)
        if ([char]::IsLetter($first)) {
            $alt = ($first.ToString().ToUpper() + $encoded.Substring(1))
            if ($alt -ne $encoded) { $variants += $alt }
            $altLow = ($first.ToString().ToLower() + $encoded.Substring(1))
            if ($altLow -ne $encoded -and $variants -notcontains $altLow) {
                $variants += $altLow
            }
        }
    }
    $projectsRoot = Join-Path $env:USERPROFILE ".claude\projects"
    foreach ($v in $variants) {
        $dir = Join-Path $projectsRoot $v
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        $settings = Join-Path $dir "settings.json"
        $obj = [ordered]@{ trusted = $true }
        if (Test-Path $settings) {
            try {
                $existing = Get-Content -Path $settings -Raw -Encoding UTF8 | ConvertFrom-Json
                $existing | Add-Member -NotePropertyName trusted -NotePropertyValue $true -Force
                $obj = $existing
            } catch { }
        }
        ($obj | ConvertTo-Json -Compress) | Out-File -FilePath $settings -Encoding utf8
    }
}

$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OrchestratorRoot = $OrchestratorRoot -replace '\\', '/'

$yamlGet = Join-Path $PSScriptRoot "_python\yaml_get.py"
$yamlOut = & python $yamlGet $ProjectId 2>&1
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

if (-not $ProjectPath -or -not $CodemetaPort -or -not $VmDockerHost) {
    Write-Error "yaml_get returned incomplete data: $yamlOut"
    exit 1
}

if (-not (Test-Path $ProjectPath)) {
    Write-Error "project path does not exist on disk: $ProjectPath"
    exit 1
}

# path_local INVARIANT: must be the 1C XML-dump root that the project's
# codemetadata container indexes. Required so that RelevantFile.path
# values in analysis_report.json are FS-resolvable (Stage 6 D2 finding).
# Fail-fast with clear guidance if the dump is missing or stale.
$cfgXml = Join-Path $ProjectPath "Configuration.xml"
$catalogsDir = Join-Path $ProjectPath "Catalogs"
if (-not (Test-Path $cfgXml) -or -not (Test-Path $catalogsDir)) {
    Write-Error @"
project_path is not a 1C XML-dump root: $ProjectPath
expected to find Configuration.xml + Catalogs/ directly under path_local.

For example-erp/example-trade: clone http://<gitea-host>:3000/admin/${ProjectId}-src.git (auto-synced from /opt/mcp-xml/${ProjectId}/src on <vm-docker-host> every 30 min).
For other projects: verify projects.yaml path_local points at the XML-dump root (often a 'src/' subdir of the project workspace).
"@
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

$codemetaUrl = "http://{0}:{1}/mcp" -f $VmDockerHost, $CodemetaPort

$claudeTpl = Get-Content -Path (Join-Path $OrchestratorRoot "templates/analyst-CLAUDE.md.tpl") -Raw -Encoding UTF8
$mcpTpl    = Get-Content -Path (Join-Path $OrchestratorRoot "templates/analyst-mcp.json.tpl")    -Raw -Encoding UTF8

$subst = @{
    "{PROJECT_ID}"        = $ProjectId
    "{PROJECT_PATH}"      = $ProjectPath
    "{TASK_ID}"           = $TaskId
    "{TASK_TEXT}"         = $TaskText
    "{ORCHESTRATOR_ROOT}" = $OrchestratorRoot
    "{TASK_ROOT_ABS}"     = $TaskRoot
    "{CODEMETADATA_URL}"  = $codemetaUrl
}
$claudeRendered = $claudeTpl
$mcpRendered    = $mcpTpl
foreach ($k in $subst.Keys) {
    $claudeRendered = $claudeRendered.Replace($k, $subst[$k])
    $mcpRendered    = $mcpRendered.Replace($k,    $subst[$k])
}

$claudeRendered | Out-File -FilePath (Join-Path $TaskRoot "CLAUDE.md") -Encoding utf8
$mcpRendered    | Out-File -FilePath (Join-Path $TaskRoot ".mcp.json") -Encoding utf8

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
    expected_session_dir_hint  = (Encode-ClaudePath $TaskRoot)
    wt_window_title            = $wtTitle
}
($taskPacket | ConvertTo-Json -Depth 10) | Out-File -FilePath (Join-Path $TaskRoot "task_packet.json") -Encoding utf8

$promptLines = @(
    "Read ./CLAUDE.md in the current directory - it is your contract and lists absolute paths to prompts/skills.",
    "Then follow prompts/analyst.md (linked from that CLAUDE.md). One pass, output analysis_report.json + announce REPORT READY."
)
($promptLines -join "`r`n") | Out-File -FilePath (Join-Path $TaskRoot "prompt.md") -Encoding utf8

Write-PreTrust -AbsPath $TaskRoot
Write-PreTrust -AbsPath $OrchestratorRoot

$result = [ordered]@{
    task_id                   = $TaskId
    task_root                 = $TaskRoot
    project_path              = $ProjectPath
    wt_window_title           = $wtTitle
    expected_session_dir_hint = $taskPacket.expected_session_dir_hint
    prepare_only              = [bool]$PrepareOnly.IsPresent
}

if ($PrepareOnly) {
    ($result | ConvertTo-Json -Compress)
    exit 0
}

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
