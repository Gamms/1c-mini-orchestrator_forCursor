#requires -Version 5
<#
.SYNOPSIS
    Child wrapper inside the spawned wt tab for implementer.
.DESCRIPTION
    Sets CWD to TaskRoot (so the claude session dir is encoded from
    TaskRoot and shares the existing analyst+writer dir under
    ~/.claude/projects/), exports ORCH_PATH_LOCAL + ORCH_BRANCH_NAME
    for any prompt-side substitution, then invokes claude with the
    task-scoped .mcp.implementer.json (strict) + --add-dir for the
    project's working tree (writable) and orchestrator root.

    The claude session itself cd's into <path_local> (or
    <extra_writable_dir> if set) for git operations -- this wrapper
    does not, because the session dir name must match TaskRoot for
    peek-task.ps1 discovery.

    -ExtraWritableDir (optional): emits a second --add-dir for an
    alternate writable workspace (e.g. when path_local is a read-only
    XML mirror used only by codemetadata MCP and the real git push
    target lives elsewhere). Sourced from projects.yaml.extra_writable_dir
    via spawn-implementer.ps1.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskRoot,
    [Parameter(Mandatory=$true)][string]$ProjectPath,
    [Parameter(Mandatory=$true)][string]$OrchestratorRoot,
    [Parameter(Mandatory=$true)][string]$PathLocal,
    [Parameter(Mandatory=$true)][string]$GiteaRemoteUrl,
    [string]$ExtraWritableDir = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $TaskRoot)) {
    Write-Error "TaskRoot not found: $TaskRoot"
    exit 1
}

Set-Location -Path $TaskRoot

$promptPath = Join-Path $TaskRoot "prompt.implementer.md"
if (-not (Test-Path $promptPath)) {
    Write-Error "prompt.implementer.md not found at $promptPath"
    exit 1
}
$prompt = Get-Content -Path $promptPath -Raw -Encoding UTF8

$mcpConfig = Join-Path $TaskRoot ".mcp.implementer.json"
if (-not (Test-Path $mcpConfig)) {
    Write-Error ".mcp.implementer.json not found at $mcpConfig"
    exit 1
}

# Derive BranchName from PathLocal + TaskId convention (orchestrator/<task_id>).
# TaskId is the last path segment of TaskRoot.
$TaskId = Split-Path -Leaf $TaskRoot
$BranchName = "orchestrator/" + $TaskId

# Env vars for any prompt-side substitution (SDD section 4.2)
$env:ORCH_PATH_LOCAL  = $PathLocal
$env:ORCH_BRANCH_NAME = $BranchName

Write-Host "L3 implementer -- task_root: $TaskRoot"
Write-Host "L3 implementer -- project_path: $ProjectPath"
Write-Host "L3 implementer -- orchestrator_root: $OrchestratorRoot"
Write-Host "L3 implementer -- path_local: $PathLocal"
Write-Host "L3 implementer -- gitea_remote_url: $GiteaRemoteUrl"
Write-Host "L3 implementer -- branch_name: $BranchName"
Write-Host "L3 implementer -- mcp_config: $mcpConfig"
if ($ExtraWritableDir) {
    Write-Host "L3 implementer -- extra_writable_dir: $ExtraWritableDir"
}
Write-Host ""

if ($ExtraWritableDir) {
    & claude `
        --dangerously-skip-permissions `
        --add-dir $PathLocal `
        --add-dir $OrchestratorRoot `
        --add-dir $ExtraWritableDir `
        --mcp-config $mcpConfig `
        --strict-mcp-config `
        -- $prompt
} else {
    & claude `
        --dangerously-skip-permissions `
        --add-dir $PathLocal `
        --add-dir $OrchestratorRoot `
        --mcp-config $mcpConfig `
        --strict-mcp-config `
        -- $prompt
}
