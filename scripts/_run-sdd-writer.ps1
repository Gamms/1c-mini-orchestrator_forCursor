#requires -Version 5
<#
.SYNOPSIS
    Child wrapper inside the spawned wt tab for sdd_writer.
.DESCRIPTION
    Sets CWD to TaskRoot, reads prompt.sdd-writer.md, invokes claude
    with task-scoped .mcp.sdd-writer.json (strict) + add-dir for the
    project (read-only) and orchestrator root.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskRoot,
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$OrchestratorRoot
)

$ErrorActionPreference = "Stop"

Set-Location -Path $TaskRoot

$promptPath = Join-Path $TaskRoot "prompt.sdd-writer.md"
if (-not (Test-Path $promptPath)) {
    Write-Error "prompt.sdd-writer.md not found at $promptPath"
    exit 1
}
$prompt = Get-Content -Path $promptPath -Raw -Encoding UTF8

$mcpConfig = Join-Path $TaskRoot ".mcp.sdd-writer.json"

Write-Host "L3 sdd-writer -- task_root: $TaskRoot"
Write-Host "L3 sdd-writer -- project_path: $ProjectPath"
Write-Host "L3 sdd-writer -- orchestrator_root: $OrchestratorRoot"
Write-Host "L3 sdd-writer -- mcp_config: $mcpConfig"
Write-Host ""

& claude `
    --dangerously-skip-permissions `
    --add-dir $ProjectPath `
    --add-dir $OrchestratorRoot `
    --mcp-config $mcpConfig `
    --strict-mcp-config `
    -- $prompt
