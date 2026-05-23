#requires -Version 5
<#
.SYNOPSIS
    Child wrapper inside the spawned wt tab. Runs claude with task context.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskRoot,
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$OrchestratorRoot
)

$ErrorActionPreference = "Stop"

Set-Location -Path $TaskRoot

$promptPath = Join-Path $TaskRoot "prompt.md"
if (-not (Test-Path $promptPath)) {
    Write-Error "prompt.md not found at $promptPath"
    exit 1
}
$prompt = Get-Content -Path $promptPath -Raw -Encoding UTF8

$mcpConfig = Join-Path $TaskRoot ".mcp.json"

Write-Host "L3 analyst -- task_root: $TaskRoot"
Write-Host "L3 analyst -- project_path: $ProjectPath"
Write-Host "L3 analyst -- orchestrator_root: $OrchestratorRoot"
Write-Host "L3 analyst -- mcp_config: $mcpConfig"
Write-Host ""

& claude `
    --dangerously-skip-permissions `
    --add-dir $ProjectPath `
    --add-dir $OrchestratorRoot `
    --mcp-config $mcpConfig `
    --strict-mcp-config `
    -- $prompt
