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

. (Join-Path $PSScriptRoot "_cursor-lib.ps1")

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
$yamlOut = & (Get-OrchestratorPython) $yamlGet $ProjectId 2>&1
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

if (-not (Test-ProjectRegistryComplete -Cfg $cfg)) {
    [Console]::Error.WriteLine("yaml_get returned incomplete data for $ProjectId : $yamlOut")
    exit 1
}

$CodemetaUrl = Get-ProjectCodemetaUrl -Cfg $cfg

try {
    Test-ProjectPathInvariant -ProjectPath $ProjectPath -Cfg $cfg -ProjectId $ProjectId
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
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
$validateOut = & (Get-OrchestratorPython) $validatePy $TaskRoot 2>&1
$validateExit = $LASTEXITCODE
if ($validateExit -ne 0) {
    [Console]::Error.WriteLine("analysis_report.json did not validate (exit=$validateExit). Run validate-analysis.ps1 first.")
    [Console]::Error.WriteLine($validateOut)
    exit 5
}

# Ensure sdd_raw exists
if (-not (Test-Path $sddRaw)) {
    New-Item -ItemType Directory -Path $sddRaw -Force | Out-Null
}

# Render templates
$agentsTpl = Get-Content -Path (Join-Path $OrchestratorRoot "templates/sdd-writer-AGENTS.md.tpl") -Raw -Encoding UTF8

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
$agentsRendered = $agentsTpl
foreach ($k in $subst.Keys) {
    $agentsRendered = $agentsRendered.Replace($k, $subst[$k])
}

$agentsRendered | Out-File -FilePath (Join-Path $TaskRoot "AGENTS.sdd-writer.md") -Encoding utf8
Write-TaskMcpConfig `
    -OrchestratorRoot $OrchestratorRoot `
    -TaskRoot $TaskRoot `
    -DestFileName ".mcp.sdd-writer.json" `
    -Cfg $cfg `
    -TemplateRelativePath "templates/sdd-writer-mcp.json.tpl" `
    -Subst $subst

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
    runtime                    = "cursor"
    wt_window_title            = $wtTitle
}
($writerPacket | ConvertTo-Json -Depth 10) | Out-File -FilePath (Join-Path $TaskRoot "sdd_writer_packet.json") -Encoding utf8

$promptLines = @(
    "Read ./AGENTS.sdd-writer.md in the current directory - it is your contract and lists absolute paths to prompts/skills/schemas.",
    "Then follow prompts/sdd-writer.md (linked from that AGENTS.sdd-writer.md). One pass, output sdd.md + sdd_metadata.json + announce SDD READY."
)
($promptLines -join "`r`n") | Out-File -FilePath (Join-Path $TaskRoot "prompt.sdd-writer.md") -Encoding utf8

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
