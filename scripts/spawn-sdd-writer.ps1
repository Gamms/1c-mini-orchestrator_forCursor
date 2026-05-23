#requires -Version 5
<#
.SYNOPSIS
    Spawn an L3 sdd_writer in a new Windows Terminal tab.
.DESCRIPTION
    Resolves an existing tasks/<task_id>/ (created earlier by spawn-analyst.ps1),
    re-validates analysis_report.json, renders sdd-writer templates,
    writes sdd_writer_packet.json + prompt.sdd-writer.md, pre-trusts
    CWD + orchestrator root, captures the analyst session.jsonl dir
    (so validate_sdd.py can find it later), then launches wt.exe nt
    with _run-sdd-writer.ps1.

    -PrepareOnly: do everything EXCEPT the final wt.exe spawn.
    -Force: remove existing sdd.md/sdd_metadata.json/sdd_raw/ before writing.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [switch]$PrepareOnly,
    [switch]$Force
)

$ErrorActionPreference = "Continue"

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

$TaskRoot = Join-Path $OrchestratorRoot "tasks/$TaskId"
$TaskRoot = $TaskRoot -replace '\\', '/'

if (-not (Test-Path $TaskRoot)) {
    [Console]::Error.WriteLine("task_root not found: $TaskRoot")
    [Console]::Error.WriteLine("Run spawn-analyst.ps1 first to create the task and produce analysis_report.json.")
    exit 1
}

$packetPath = Join-Path $TaskRoot "task_packet.json"
if (-not (Test-Path $packetPath)) {
    [Console]::Error.WriteLine("task_packet.json not found at $packetPath -- task was not created by spawn-analyst.ps1?")
    exit 1
}

try {
    $analystPacket = Get-Content -Path $packetPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    [Console]::Error.WriteLine("failed to parse task_packet.json: $_")
    exit 1
}

$ProjectId    = $analystPacket.project_id
$TaskText     = $analystPacket.task_text

if (-not $ProjectId) {
    [Console]::Error.WriteLine("task_packet.json missing required field project_id")
    exit 1
}

# Re-resolve project_path + codemeta_port from current projects.yaml.
# task_packet.json may have been written before a projects.yaml change
# (e.g. the D2 path_local fix moved example-erp from example-erp-example-trade-exchange/example-erp to 1c/example-erp-src);
# writer must use current authoritative path, not the analyst's snapshot.
$yamlGet = Join-Path $PSScriptRoot "_python\yaml_get.py"
$yamlOut = & python $yamlGet $ProjectId 2>&1
$yamlExit = $LASTEXITCODE
if ($yamlExit -ne 0) {
    [Console]::Error.WriteLine("yaml_get.py exit=$yamlExit for project '$ProjectId': $yamlOut")
    exit 1
}
$cfg = @{}
foreach ($line in ($yamlOut -split "`r?`n")) {
    if ($line -match '^([^=]+)=(.*)$') { $cfg[$Matches[1]] = $Matches[2] }
}
$ProjectPath  = $cfg['path_local']
$CodemetaPort = $cfg['codemeta_port']
$VmDockerHost = $cfg['vm_docker_host']

if (-not $ProjectPath -or -not $CodemetaPort -or -not $VmDockerHost) {
    [Console]::Error.WriteLine("yaml_get returned incomplete data for $ProjectId : $yamlOut")
    exit 1
}

$CodemetaUrl = "http://{0}:{1}/mcp" -f $VmDockerHost, $CodemetaPort

if (-not (Test-Path $ProjectPath)) {
    [Console]::Error.WriteLine("project path does not exist on disk: $ProjectPath")
    exit 1
}

# Concurrency / re-run guard
$sddMeta = Join-Path $TaskRoot "sdd_metadata.json"
$sddMd   = Join-Path $TaskRoot "sdd.md"
$sddRaw  = Join-Path $TaskRoot "sdd_raw"
if (Test-Path $sddMeta) {
    if ($Force) {
        Remove-Item -Path $sddMeta -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $sddMd   -Force -ErrorAction SilentlyContinue
        if (Test-Path $sddRaw) { Remove-Item -Path $sddRaw -Recurse -Force -ErrorAction SilentlyContinue }
        Write-Host "Removed existing sdd artifacts (-Force)"
    } else {
        [Console]::Error.WriteLine("sdd_metadata.json already exists at $sddMeta. Pass -Force to remove and rerun.")
        exit 6
    }
}

# Pre-condition: analysis_report.json must validate
$validatePy = Join-Path $PSScriptRoot "_python\validate.py"
$validateOut = & python $validatePy $TaskRoot 2>&1
$validateExit = $LASTEXITCODE
if ($validateExit -ne 0) {
    [Console]::Error.WriteLine("analysis_report.json did not validate (exit=$validateExit). Run validate-analysis.ps1 first.")
    [Console]::Error.WriteLine($validateOut)
    exit 5
}

# path_local INVARIANT (mirror spawn-analyst.ps1 lines 98-109)
$cfgXml = Join-Path $ProjectPath "Configuration.xml"
$catalogsDir = Join-Path $ProjectPath "Catalogs"
if (-not (Test-Path $cfgXml) -or -not (Test-Path $catalogsDir)) {
    [Console]::Error.WriteLine("project_path is not a 1C XML-dump root: $ProjectPath")
    [Console]::Error.WriteLine("expected Configuration.xml + Catalogs/ directly under path_local.")
    exit 1
}

# Resolve analyst session.jsonl dir BEFORE spawning the writer.
# At this moment, only the analyst session exists for this task_id;
# after wt spawn a new dir appears for the writer.
$projectsRoot = Join-Path $env:USERPROFILE ".claude\projects"
$analystSessionDir = ""
if (Test-Path $projectsRoot) {
    $candidates = Get-ChildItem -Path $projectsRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "*Orchestrator*tasks*$TaskId*" }
    if ($candidates) {
        $analystSessionDir = ($candidates | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
    }
}

# Ensure sdd_raw exists
if (-not (Test-Path $sddRaw)) {
    New-Item -ItemType Directory -Path $sddRaw -Force | Out-Null
}

# Render templates
$claudeTpl = Get-Content -Path (Join-Path $OrchestratorRoot "templates/sdd-writer-CLAUDE.md.tpl") -Raw -Encoding UTF8
$mcpTpl    = Get-Content -Path (Join-Path $OrchestratorRoot "templates/sdd-writer-mcp.json.tpl")    -Raw -Encoding UTF8

$subst = @{
    "{PROJECT_ID}"          = $ProjectId
    "{PROJECT_PATH}"        = $ProjectPath
    "{TASK_ID}"             = $TaskId
    "{TASK_TEXT}"           = $TaskText
    "{ORCHESTRATOR_ROOT}"   = $OrchestratorRoot
    "{TASK_ROOT_ABS}"       = $TaskRoot
    "{CODEMETADATA_URL}"    = $CodemetaUrl
    "{ANALYSIS_REPORT_REL}" = "analysis_report.json"
}
$claudeRendered = $claudeTpl
$mcpRendered    = $mcpTpl
foreach ($k in $subst.Keys) {
    $claudeRendered = $claudeRendered.Replace($k, $subst[$k])
    $mcpRendered    = $mcpRendered.Replace($k,    $subst[$k])
}

$claudeRendered | Out-File -FilePath (Join-Path $TaskRoot "CLAUDE.sdd-writer.md") -Encoding utf8
$mcpRendered    | Out-File -FilePath (Join-Path $TaskRoot ".mcp.sdd-writer.json") -Encoding utf8

$wtTitle = "sdd-writer:$TaskId"
$writerPacket = [ordered]@{
    task_id                    = $TaskId
    project_id                 = $ProjectId
    project_path               = $ProjectPath
    task_text                  = $TaskText
    codemetadata_url           = $CodemetaUrl
    orchestrator_root          = $OrchestratorRoot
    task_root                  = $TaskRoot
    created_at                 = (Get-Date).ToUniversalTime().ToString("o")
    analyst_session_dir        = $analystSessionDir
    expected_session_dir_hint  = (Encode-ClaudePath $TaskRoot)
    wt_window_title            = $wtTitle
}
($writerPacket | ConvertTo-Json -Depth 10) | Out-File -FilePath (Join-Path $TaskRoot "sdd_writer_packet.json") -Encoding utf8

$promptLines = @(
    "Read ./CLAUDE.sdd-writer.md in the current directory - it is your contract and lists absolute paths to prompts/skills/schemas.",
    "Then follow prompts/sdd-writer.md (linked from that CLAUDE.sdd-writer.md). One pass, output sdd.md + sdd_metadata.json + announce SDD READY."
)
($promptLines -join "`r`n") | Out-File -FilePath (Join-Path $TaskRoot "prompt.sdd-writer.md") -Encoding utf8

Write-PreTrust -AbsPath $TaskRoot
Write-PreTrust -AbsPath $OrchestratorRoot

$result = [ordered]@{
    task_id                   = $TaskId
    task_root                 = $TaskRoot
    project_path              = $ProjectPath
    wt_window_title           = $wtTitle
    expected_session_dir_hint = $writerPacket.expected_session_dir_hint
    analyst_session_dir       = $analystSessionDir
    prepare_only              = [bool]$PrepareOnly.IsPresent
}

if ($PrepareOnly) {
    ($result | ConvertTo-Json -Compress)
    exit 0
}

$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if (-not $wt) {
    Write-Warning "wt.exe not found in PATH. Files prepared at: $TaskRoot"
    $runWrapper = Join-Path $PSScriptRoot "_run-sdd-writer.ps1"
    Write-Warning "Manual run: powershell.exe -NoExit -ExecutionPolicy Bypass -File ""$runWrapper"" -TaskRoot ""$TaskRoot"" -ProjectPath ""$ProjectPath"" -OrchestratorRoot ""$OrchestratorRoot"""
    ($result | ConvertTo-Json -Compress)
    exit 2
}

$runWrapper = Join-Path $PSScriptRoot "_run-sdd-writer.ps1"
& wt.exe -w 0 nt `
    --title $wtTitle `
    powershell.exe -NoExit -ExecutionPolicy Bypass `
        -File $runWrapper `
        -TaskRoot $TaskRoot `
        -ProjectPath $ProjectPath `
        -OrchestratorRoot $OrchestratorRoot

($result | ConvertTo-Json -Compress)
