#requires -Version 5
<#
.SYNOPSIS
    Spawn an L3 implementer in a new Windows Terminal tab.
.DESCRIPTION
    Resolves an existing tasks/<task_id>/ (created earlier by
    spawn-analyst.ps1, then enriched by spawn-sdd-writer.ps1), runs
    six gating pre-checks, renders implementer templates, writes
    implementer_packet.json + prompt.implementer.md + impl_raw/,
    pre-trusts CWD + orchestrator root + path_local, then launches
    wt.exe nt with _run-implementer.ps1.

    Six gating pre-checks (per Phase 3 SDD section 5.4):
      1. SDD validated   (validate_sdd.py exits 0)             -> exit 5
      2. path_local INVARIANT (Configuration.xml + Catalogs/)  -> exit 1
      3. git_target_dir status clean                           -> exit 6
      4. git_target_dir has 'gitea' or 'origin' remote         -> exit 7
      5. branch orchestrator/<TaskId> not pre-existing in git_target_dir
                                                               -> exit 8
                          (unless -Force)
      6. impl_metadata.json not pre-existing (unless -Force)   -> exit 9

    git_target_dir = $ExtraWritableDir when set in projects.yaml (example-erp / example-trade),
    else $PathLocal. The 1C XML INVARIANT (pre-check 2) ALWAYS operates on
    path_local since that is the codemetadata MCP target. Git ops (commit,
    push, branch lifecycle) operate on git_target_dir since that is the
    real impl repo when path_local is a read-only XML mirror.

    -PrepareOnly: do everything EXCEPT the final wt.exe spawn.
    -Force: allow re-running on a task that already has impl_metadata.json
            and/or pre-existing orchestrator/<TaskId> branch. Removes the
            stale impl_metadata.json + impl_raw/ from the task root. Does
            NOT delete the path_local branch -- implementer uses `git
            checkout -B` to overwrite.
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [switch]$PrepareOnly,
    [switch]$Force
)

$ErrorActionPreference = "Continue"

. (Join-Path $PSScriptRoot "_cursor-lib.ps1")

function Strip-GitCreds {
    param([Parameter(Mandatory=$true)][string]$Url)
    # http://user:pass@host/path -> http://host/path
    return ($Url -replace '^(https?://)[^@/]+@', '$1')
}

$OrchestratorRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OrchestratorRoot = $OrchestratorRoot -replace '\\', '/'

$TaskRoot = Join-Path $OrchestratorRoot "tasks/$TaskId"
$TaskRoot = $TaskRoot -replace '\\', '/'

if (-not (Test-Path $TaskRoot)) {
    [Console]::Error.WriteLine("task_root not found: $TaskRoot")
    [Console]::Error.WriteLine("Run spawn-analyst.ps1 then spawn-sdd-writer.ps1 first.")
    exit 1
}

$taskPacketPath   = Join-Path $TaskRoot "task_packet.json"
$writerPacketPath = Join-Path $TaskRoot "sdd_writer_packet.json"

if (-not (Test-Path $taskPacketPath)) {
    [Console]::Error.WriteLine("task_packet.json not found at $taskPacketPath -- analyst phase missing")
    exit 1
}
if (-not (Test-Path $writerPacketPath)) {
    [Console]::Error.WriteLine("sdd_writer_packet.json not found at $writerPacketPath -- writer phase missing")
    exit 1
}

try {
    $taskPacket   = Get-Content -Path $taskPacketPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $writerPacket = Get-Content -Path $writerPacketPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    [Console]::Error.WriteLine("failed to parse task_packet.json / sdd_writer_packet.json: $_")
    exit 1
}

$ProjectId  = $taskPacket.project_id
$TaskText   = $taskPacket.task_text

if (-not $ProjectId) {
    [Console]::Error.WriteLine("task_packet.json missing required field project_id")
    exit 1
}

# Re-resolve project_path + codemeta_port from current projects.yaml.
# Carry-forward from spawn-sdd-writer.ps1: snapshot in packet may be stale.
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
$PathLocal        = $cfg['path_local']
$CodemetaPort     = $cfg['codemeta_port']
$VmDockerHost     = $cfg['vm_docker_host']
$ExtraWritableDir = $cfg['extra_writable_dir']

if (-not (Test-ProjectRegistryComplete -Cfg $cfg)) {
    [Console]::Error.WriteLine("yaml_get returned incomplete data for $ProjectId : $yamlOut")
    exit 1
}

$CodemetaUrl = Get-ProjectCodemetaUrl -Cfg $cfg

try {
    Test-ProjectPathInvariant -ProjectPath $PathLocal -Cfg $cfg -ProjectId $ProjectId
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}

# extra_writable_dir (optional): second --add-dir for the implementer
# claude session. Validate existence if non-empty. When set, git-side
# pre-checks 3 / 4 / 5 + before_sha operate on extra_writable_dir
# (real impl repo); INVARIANT pre-check 2 still operates on path_local
# (codemetadata XML-dump root).
if ($ExtraWritableDir) {
    if (-not (Test-Path $ExtraWritableDir)) {
        [Console]::Error.WriteLine("extra_writable_dir does not exist on disk: $ExtraWritableDir")
        [Console]::Error.WriteLine("Either fix projects.yaml or create/clone the directory before re-spawning.")
        exit 1
    }
    $GitTargetDir = $ExtraWritableDir
} else {
    $GitTargetDir = $PathLocal
}

# ---- Gating pre-check 1: SDD validated ----
$sddMd   = Join-Path $TaskRoot "sdd.md"
$sddMeta = Join-Path $TaskRoot "sdd_metadata.json"
if (-not (Test-Path $sddMd) -or -not (Test-Path $sddMeta)) {
    [Console]::Error.WriteLine("sdd.md or sdd_metadata.json missing at $TaskRoot -- run spawn-sdd-writer.ps1 first")
    exit 5
}
$validateSddPy = Join-Path $PSScriptRoot "_python\validate_sdd.py"
$validateSddOut = & (Get-OrchestratorPython) $validateSddPy $TaskRoot 2>&1
$validateSddExit = $LASTEXITCODE
if ($validateSddExit -ne 0) {
    [Console]::Error.WriteLine("SDD did not validate (validate_sdd.py exit=$validateSddExit). Run validate-sdd.ps1 first.")
    [Console]::Error.WriteLine($validateSddOut)
    exit 5
}

# ---- Gating pre-check 2: path_local INVARIANT (1C XML-dump root) ----
# handled by Test-ProjectPathInvariant above when skip_path_invariant is false

# ---- Gating pre-check 3: git_target_dir git is clean ----
$porcelain = & git -C $GitTargetDir status --porcelain 2>&1
$porcelainExit = $LASTEXITCODE
if ($porcelainExit -ne 0) {
    [Console]::Error.WriteLine("git -C $GitTargetDir status failed (exit=$porcelainExit): $porcelain")
    exit 6
}
$porcelainStr = ($porcelain | Out-String).Trim()
if ($porcelainStr.Length -gt 0) {
    [Console]::Error.WriteLine("git_target_dir has uncommitted changes; implementer refuses to run on dirty tree:")
    [Console]::Error.WriteLine($porcelainStr)
    [Console]::Error.WriteLine("commit / stash / discard in $GitTargetDir first, then re-spawn.")
    exit 6
}

# ---- Gating pre-check 4: git_target_dir has 'gitea' or 'origin' remote ----
# Convention: path_local-only projects (no extra_writable_dir) have a
# named 'gitea' remote added by the operator. extra_writable_dir projects
# (example-erp / example-trade) clone from Gitea with default 'origin' name. Try 'gitea'
# first, fall back to 'origin'.
$GiteaRemoteName = "gitea"
$GiteaRemoteUrlSanitized = "local-only"
$giteaRemote = & git -C $GitTargetDir remote get-url $GiteaRemoteName 2>&1
$giteaExit = $LASTEXITCODE
if ($giteaExit -ne 0) {
    $GiteaRemoteName = "origin"
    $giteaRemote = & git -C $GitTargetDir remote get-url $GiteaRemoteName 2>&1
    $giteaExit = $LASTEXITCODE
}
if ($giteaExit -ne 0) {
    if ($cfg['allow_missing_git_remote'] -eq 'true') {
        Write-Host "allow_missing_git_remote: no gitea/origin remote; implementer will commit locally only"
        $GiteaRemoteName = "local"
        $GiteaRemoteUrlSanitized = "local-only"
    } else {
        [Console]::Error.WriteLine("git_target_dir has neither 'gitea' nor 'origin' remote: $giteaRemote")
        [Console]::Error.WriteLine("add one with: git -C $GitTargetDir remote add origin <url>")
        [Console]::Error.WriteLine("or set allow_missing_git_remote: true in projects.yaml for local-only repos")
        exit 7
    }
} else {
    $GiteaRemoteUrlRaw       = ($giteaRemote | Out-String).Trim()
    $GiteaRemoteUrlSanitized = Strip-GitCreds $GiteaRemoteUrlRaw
}

# Capture before_sha (carrying-forward marker; recorded in implementer_packet)
$BeforeSha = (& git -C $GitTargetDir rev-parse HEAD 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $BeforeSha) {
    [Console]::Error.WriteLine("failed to capture before_sha from git_target_dir: $BeforeSha")
    exit 1
}

$BranchName = "orchestrator/$TaskId"

# ---- Gating pre-check 5: branch not pre-existing in git_target_dir unless -Force ----
& git -C $GitTargetDir rev-parse --verify --quiet ("refs/heads/" + $BranchName) | Out-Null
$branchExists = ($LASTEXITCODE -eq 0)
if ($branchExists -and -not $Force) {
    [Console]::Error.WriteLine("branch '$BranchName' already exists in $GitTargetDir; pass -Force to overwrite")
    exit 8
}

# ---- Gating pre-check 6: impl_metadata not pre-existing unless -Force ----
$implMetaPath = Join-Path $TaskRoot "impl_metadata.json"
$implRawDir   = Join-Path $TaskRoot "impl_raw"
if (Test-Path $implMetaPath) {
    if ($Force) {
        Remove-Item -Path $implMetaPath -Force -ErrorAction SilentlyContinue
        if (Test-Path $implRawDir) {
            Remove-Item -Path $implRawDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Host "Removed existing impl artifacts (-Force)"
    } else {
        [Console]::Error.WriteLine("impl_metadata.json already exists at $implMetaPath. Pass -Force to remove and rerun.")
        exit 9
    }
}

# Ensure impl_raw/ exists
if (-not (Test-Path $implRawDir)) {
    New-Item -ItemType Directory -Path $implRawDir -Force | Out-Null
}

# Render templates
$agentsTplPath = Join-Path $OrchestratorRoot "templates/implementer-AGENTS.md.tpl"
if (-not (Test-Path $agentsTplPath)) {
    [Console]::Error.WriteLine("implementer templates missing at $agentsTplPath")
    exit 1
}
$agentsTpl = Get-Content -Path $agentsTplPath -Raw -Encoding UTF8

$subst = @{
    "{PROJECT_ID}"          = $ProjectId
    "{PROJECT_PATH}"        = $PathLocal
    "{GIT_TARGET_DIR}"      = $GitTargetDir
    "{TASK_ID}"             = $TaskId
    "{TASK_TEXT}"           = $TaskText
    "{ORCHESTRATOR_ROOT}"   = $OrchestratorRoot
    "{TASK_ROOT_ABS}"       = $TaskRoot
    "{CODEMETADATA_URL}"    = $CodemetaUrl
    "{SDD_REF}"             = "sdd.md"
    "{SDD_METADATA_REF}"    = "sdd_metadata.json"
    "{GITEA_REMOTE_URL}"    = $GiteaRemoteUrlSanitized
    "{GITEA_REMOTE_NAME}"   = $GiteaRemoteName
    "{BRANCH_NAME}"         = $BranchName
}
$agentsRendered = $agentsTpl
foreach ($k in $subst.Keys) {
    $agentsRendered = $agentsRendered.Replace($k, $subst[$k])
}

$agentsRendered | Out-File -FilePath (Join-Path $TaskRoot "AGENTS.implementer.md")   -Encoding utf8
Write-TaskMcpConfig `
    -OrchestratorRoot $OrchestratorRoot `
    -TaskRoot $TaskRoot `
    -DestFileName ".mcp.implementer.json" `
    -Cfg $cfg `
    -TemplateRelativePath "templates/implementer-mcp.json.tpl" `
    -Subst $subst

# Capture orchestrator-side porcelain baseline. validate_impl Gate B
# compares current porcelain against this baseline so harness side-effects
# (e.g. session-start hooks that modify Orchestrator/.gitignore) outside
# tasks/<task_id>/ are absorbed rather than reported as implementer bleed.
$orchPorcelainRaw = & git -C $OrchestratorRoot status --porcelain 2>&1
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("git -C $OrchestratorRoot status --porcelain failed (exit=$LASTEXITCODE): $orchPorcelainRaw")
    exit 1
}
$orchPorcelainLines = @()
foreach ($pline in (($orchPorcelainRaw | Out-String) -split "`r?`n")) {
    if ($pline.Trim().Length -gt 0) { $orchPorcelainLines += $pline.TrimEnd() }
}

$wtTitle = "implementer:$TaskId"
$implPacket = [ordered]@{
    task_id                    = $TaskId
    project_id                 = $ProjectId
    project_path               = $PathLocal
    path_local                 = $PathLocal
    extra_writable_dir         = $ExtraWritableDir
    git_target_dir             = $GitTargetDir
    task_text                  = $TaskText
    codemetadata_url           = $CodemetaUrl
    orchestrator_root          = $OrchestratorRoot
    task_root                  = $TaskRoot
    gitea_remote_url           = $GiteaRemoteUrlSanitized
    gitea_remote_name          = $GiteaRemoteName
    branch_name                = $BranchName
    before_sha                 = $BeforeSha
    force                      = [bool]$Force.IsPresent
    created_at                 = (Get-Date).ToUniversalTime().ToString("o")
    runtime                    = "cursor"
    wt_window_title            = $wtTitle
    orch_porcelain_baseline    = @($orchPorcelainLines)
}
($implPacket | ConvertTo-Json -Depth 10) | Out-File -FilePath (Join-Path $TaskRoot "implementer_packet.json") -Encoding utf8

$promptLines = @(
    "Read ./AGENTS.implementer.md in the current directory - it is your contract and lists absolute paths to prompts/skills/schemas.",
    "Then follow prompts/implementer.md (linked from that AGENTS.implementer.md). One pass per SDD stage, push branch, output impl_metadata.json + announce IMPLEMENT READY / NEEDS_REVISION / BLOCKED."
)
($promptLines -join "`r`n") | Out-File -FilePath (Join-Path $TaskRoot "prompt.implementer.md") -Encoding utf8

$result = [ordered]@{
    task_id                   = $TaskId
    task_root                 = $TaskRoot
    project_path              = $PathLocal
    path_local                = $PathLocal
    extra_writable_dir        = $ExtraWritableDir
    git_target_dir            = $GitTargetDir
    branch_name               = $BranchName
    gitea_remote_url          = $GiteaRemoteUrlSanitized
    gitea_remote_name         = $GiteaRemoteName
    before_sha                = $BeforeSha
    wt_window_title           = $wtTitle
    runtime                   = "cursor"
    prepare_only              = [bool]$PrepareOnly.IsPresent
    force                     = [bool]$Force.IsPresent
}

if ($PrepareOnly) {
    ($result | ConvertTo-Json -Compress)
    exit 0
}

if (-not (Test-CursorApiKey)) { exit 3 }

$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if (-not $wt) {
    Write-Warning "wt.exe not found in PATH. Files prepared at: $TaskRoot"
    $runWrapper = Join-Path $PSScriptRoot "_run-implementer.ps1"
    $manualExtra = ""
    if ($ExtraWritableDir) { $manualExtra = " -ExtraWritableDir ""$ExtraWritableDir""" }
    Write-Warning "Manual run: powershell.exe -NoExit -ExecutionPolicy Bypass -File ""$runWrapper"" -TaskRoot ""$TaskRoot"" -ProjectPath ""$PathLocal"" -OrchestratorRoot ""$OrchestratorRoot"" -PathLocal ""$PathLocal"" -GiteaRemoteUrl ""$GiteaRemoteUrlSanitized""$manualExtra"
    ($result | ConvertTo-Json -Compress)
    exit 2
}

$runWrapper = Join-Path $PSScriptRoot "_run-implementer.ps1"
if ($ExtraWritableDir) {
    & wt.exe -w 0 nt `
        --title $wtTitle `
        powershell.exe -NoExit -ExecutionPolicy Bypass `
            -File $runWrapper `
            -TaskRoot $TaskRoot `
            -ProjectPath $PathLocal `
            -OrchestratorRoot $OrchestratorRoot `
            -PathLocal $PathLocal `
            -GiteaRemoteUrl $GiteaRemoteUrlSanitized `
            -ExtraWritableDir $ExtraWritableDir
} else {
    & wt.exe -w 0 nt `
        --title $wtTitle `
        powershell.exe -NoExit -ExecutionPolicy Bypass `
            -File $runWrapper `
            -TaskRoot $TaskRoot `
            -ProjectPath $PathLocal `
            -OrchestratorRoot $OrchestratorRoot `
            -PathLocal $PathLocal `
            -GiteaRemoteUrl $GiteaRemoteUrlSanitized
}

($result | ConvertTo-Json -Compress)
