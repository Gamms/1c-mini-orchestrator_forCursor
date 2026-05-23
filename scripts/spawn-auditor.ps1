#requires -Version 5
<#
.SYNOPSIS
    Spawn an L3 auditor (codex runtime) in a new Windows Terminal tab.
.DESCRIPTION
    Resolves an existing tasks/<task_id>/ produced by Phases 1-3
    (analyst -> sdd_writer -> implementer), runs six gating pre-checks
    per Phase 4 SDD section 5.4.1, renders auditor templates, writes
    auditor_packet.json + prompt.auditor.md + audit_raw/, pre-trusts
    CWD + orchestrator root + path_local (read-only adds for codex),
    then launches wt.exe nt with _run-auditor.ps1.

    Six gating pre-checks (Phase 4 SDD section 5.4.1):
      1. sdd.md + sdd_metadata.json + impl_metadata.json + analysis_report.json
         present AND validate_sdd.py + validate_impl.py both exit 0  -> exit 5
      2. path_local INVARIANT (Configuration.xml + Catalogs/)        -> exit 1
      3. git_target_dir has branch 'orchestrator/<TaskId>'           -> exit 6
      4. git_target_dir git status clean                             -> exit 7
      5. audit_report.json not pre-existing (unless -Force)          -> exit 8
      6. codex executable resolvable on PATH                         -> exit 2

    git_target_dir = $ExtraWritableDir when set in projects.yaml,
    else $PathLocal. Symmetric with spawn-implementer.ps1 (commit
    1730a7f Phase 6 fix).

    Phase 4 deviates from Phase 3 spawn shape in two ways:
      a) No gitea-remote check: auditor is fully read-only over
         path_local; it never pushes. Implementer already verified +
         pushed the branch.
      b) Per-task codex config delivered via CODEX_HOME redirect, NOT
         a --config flag (Stage 0 finding: codex 0.130.0 has no
         --config <path> option). Rendered config lands at
         <task_root>\.codex_home\config.toml; _run-auditor.ps1 sets
         $env:CODEX_HOME = <task_root>\.codex_home before codex exec.

    -PrepareOnly: do everything EXCEPT the final wt.exe spawn.
    -Force: allow re-running on a task that already has audit_report.json.
            Removes the stale audit_report.json + audit_raw/ from the task
            root before rendering.
    -Model: optional override for codex model selection. Empty string ->
            no -m flag passed (codex uses its default).
#>
param(
    [Parameter(Mandatory=$true)][string]$TaskId,
    [string]$Model = "",
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
    [Console]::Error.WriteLine("Run spawn-analyst.ps1 -> spawn-sdd-writer.ps1 -> spawn-implementer.ps1 first.")
    exit 1
}

$taskPacketPath   = Join-Path $TaskRoot "task_packet.json"
$writerPacketPath = Join-Path $TaskRoot "sdd_writer_packet.json"
$implPacketPath   = Join-Path $TaskRoot "implementer_packet.json"

foreach ($p in @($taskPacketPath, $writerPacketPath, $implPacketPath)) {
    if (-not (Test-Path $p)) {
        [Console]::Error.WriteLine("required packet missing: $p")
        [Console]::Error.WriteLine("upstream phase did not run -- spawn-auditor requires analyst+writer+implementer artifacts.")
        exit 1
    }
}

try {
    $taskPacket   = Get-Content -Path $taskPacketPath   -Raw -Encoding UTF8 | ConvertFrom-Json
    $writerPacket = Get-Content -Path $writerPacketPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $implPacket   = Get-Content -Path $implPacketPath   -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    [Console]::Error.WriteLine("failed to parse one of the upstream packets: $_")
    exit 1
}

$ProjectId = $taskPacket.project_id
$TaskText  = $taskPacket.task_text

if (-not $ProjectId) {
    [Console]::Error.WriteLine("task_packet.json missing required field project_id")
    exit 1
}

# Re-resolve project_path + codemeta_port from current projects.yaml
# (carry-forward from Phase 3: snapshot in packet may be stale).
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
$PathLocal        = $cfg['path_local']
$CodemetaPort     = $cfg['codemeta_port']
$VmDockerHost     = $cfg['vm_docker_host']
$ExtraWritableDir = $cfg['extra_writable_dir']

if (-not $PathLocal -or -not $CodemetaPort -or -not $VmDockerHost) {
    [Console]::Error.WriteLine("yaml_get returned incomplete data for $ProjectId : $yamlOut")
    exit 1
}

$CodemetaUrl = "http://{0}:{1}/mcp" -f $VmDockerHost, $CodemetaPort

if (-not (Test-Path $PathLocal)) {
    [Console]::Error.WriteLine("path_local does not exist on disk: $PathLocal")
    exit 1
}

# Symmetric with spawn-implementer.ps1: when projects.yaml sets
# extra_writable_dir, the real impl repo (and the orchestrator/<TaskId>
# branch the auditor audits) lives there, not in path_local. INVARIANT
# check 2 still operates on path_local (XML-dump for codemetadata MCP);
# git-side pre-checks 3 / 4 + branch sha capture operate on git_target_dir.
if ($ExtraWritableDir) {
    if (-not (Test-Path $ExtraWritableDir)) {
        [Console]::Error.WriteLine("extra_writable_dir does not exist on disk: $ExtraWritableDir")
        exit 1
    }
    $GitTargetDir = $ExtraWritableDir
} else {
    $GitTargetDir = $PathLocal
}

# ---- Gating pre-check 1: four upstream artifacts + validators ----
$sddMd       = Join-Path $TaskRoot "sdd.md"
$sddMeta     = Join-Path $TaskRoot "sdd_metadata.json"
$implMeta    = Join-Path $TaskRoot "impl_metadata.json"
$analysisRep = Join-Path $TaskRoot "analysis_report.json"
foreach ($f in @($sddMd, $sddMeta, $implMeta, $analysisRep)) {
    if (-not (Test-Path $f)) {
        [Console]::Error.WriteLine("upstream artifact missing: $f")
        [Console]::Error.WriteLine("auditor requires sdd.md + sdd_metadata.json + impl_metadata.json + analysis_report.json all present.")
        exit 5
    }
}
$validateSddPy = Join-Path $PSScriptRoot "_python\validate_sdd.py"
$sddOut = & python $validateSddPy $TaskRoot 2>&1
$sddExit = $LASTEXITCODE
if ($sddExit -ne 0) {
    [Console]::Error.WriteLine("validate_sdd.py exit=$sddExit (must be 0 before auditor can run):")
    [Console]::Error.WriteLine($sddOut)
    exit 5
}
$validateImplPy = Join-Path $PSScriptRoot "_python\validate_impl.py"
$implOut = & python $validateImplPy $TaskRoot 2>&1
$implExit = $LASTEXITCODE
if ($implExit -ne 0) {
    [Console]::Error.WriteLine("validate_impl.py exit=$implExit (must be 0 before auditor can run):")
    [Console]::Error.WriteLine($implOut)
    exit 5
}

# ---- Gating pre-check 2: path_local INVARIANT (1C XML-dump root) ----
$cfgXml      = Join-Path $PathLocal "Configuration.xml"
$catalogsDir = Join-Path $PathLocal "Catalogs"
if (-not (Test-Path $cfgXml) -or -not (Test-Path $catalogsDir)) {
    [Console]::Error.WriteLine("path_local is not a 1C XML-dump root: $PathLocal")
    [Console]::Error.WriteLine("expected Configuration.xml + Catalogs/ directly under path_local.")
    exit 1
}

# ---- Gating pre-check 3: branch orchestrator/<TaskId> exists in git_target_dir ----
$BranchName = "orchestrator/$TaskId"
& git -C $GitTargetDir rev-parse --verify --quiet ("refs/heads/" + $BranchName) | Out-Null
$branchExit = $LASTEXITCODE
if ($branchExit -ne 0) {
    [Console]::Error.WriteLine("branch '$BranchName' missing in $GitTargetDir -- implementer phase did not complete.")
    exit 6
}

# ---- Gating pre-check 4: git_target_dir git status clean ----
$porcelain = & git -C $GitTargetDir status --porcelain 2>&1
$porcelainExit = $LASTEXITCODE
if ($porcelainExit -ne 0) {
    [Console]::Error.WriteLine("git -C $GitTargetDir status failed (exit=$porcelainExit): $porcelain")
    exit 7
}
$porcelainStr = ($porcelain | Out-String).Trim()
if ($porcelainStr.Length -gt 0) {
    [Console]::Error.WriteLine("git_target_dir dirty after implementer finished; auditor refuses to run on uncommitted state:")
    [Console]::Error.WriteLine($porcelainStr)
    exit 7
}

# Capture before_sha_at_audit_start: tip of orchestrator/<TaskId> branch
$BeforeShaAtAuditStart = (& git -C $GitTargetDir rev-parse ("refs/heads/" + $BranchName) 2>&1 | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $BeforeShaAtAuditStart) {
    [Console]::Error.WriteLine("failed to capture branch sha for $BranchName : $BeforeShaAtAuditStart")
    exit 1
}

# ---- Gating pre-check 5: audit_report not pre-existing unless -Force ----
$auditReportPath = Join-Path $TaskRoot "audit_report.json"
$auditRawDir     = Join-Path $TaskRoot "audit_raw"
$codexHomeDir    = Join-Path $TaskRoot ".codex_home"

if (Test-Path $auditReportPath) {
    if ($Force) {
        Remove-Item -Path $auditReportPath -Force -ErrorAction SilentlyContinue
        if (Test-Path $auditRawDir) {
            Remove-Item -Path $auditRawDir -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Host "Removed existing audit artifacts (-Force)"
    } else {
        [Console]::Error.WriteLine("audit_report.json already exists at $auditReportPath. Pass -Force to remove and rerun.")
        exit 8
    }
}

# Ensure audit_raw/ + .codex_home/ exist
if (-not (Test-Path $auditRawDir))  { New-Item -ItemType Directory -Path $auditRawDir  -Force | Out-Null }
if (-not (Test-Path $codexHomeDir)) { New-Item -ItemType Directory -Path $codexHomeDir -Force | Out-Null }

# ---- Gating pre-check 6: codex executable resolvable on PATH ----
$codexCmd = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codexCmd) {
    [Console]::Error.WriteLine("codex executable not found on PATH; install codex CLI 0.130.0+ before re-running.")
    exit 2
}

# Render templates
$claudeTplPath = Join-Path $OrchestratorRoot "templates/auditor-CLAUDE.md.tpl"
$tomlTplPath   = Join-Path $OrchestratorRoot "templates/auditor-codex.toml.tpl"
if (-not (Test-Path $claudeTplPath) -or -not (Test-Path $tomlTplPath)) {
    [Console]::Error.WriteLine("auditor templates missing at $claudeTplPath / $tomlTplPath")
    exit 1
}
$claudeTpl = Get-Content -Path $claudeTplPath -Raw -Encoding UTF8
$tomlTpl   = Get-Content -Path $tomlTplPath   -Raw -Encoding UTF8

$TaskRootWin = $TaskRoot -replace '/', '\'
$subst = @{
    "{PROJECT_ID}"                = $ProjectId
    "{PROJECT_PATH}"              = $PathLocal
    "{GIT_TARGET_DIR}"            = $GitTargetDir
    "{TASK_ID}"                   = $TaskId
    "{TASK_TEXT}"                 = $TaskText
    "{ORCHESTRATOR_ROOT}"         = $OrchestratorRoot
    "{TASK_ROOT_ABS}"             = $TaskRootWin
    "{CODEMETADATA_URL}"          = $CodemetaUrl
    "{SDD_REF}"                   = "sdd.md"
    "{SDD_METADATA_REF}"          = "sdd_metadata.json"
    "{IMPL_METADATA_REF}"         = "impl_metadata.json"
    "{ANALYSIS_REF}"              = "analysis_report.json"
    "{BRANCH_AUDITED}"            = $BranchName
    "{BRANCH_SHA_AT_AUDIT_START}" = $BeforeShaAtAuditStart
}
$claudeRendered = $claudeTpl
$tomlRendered   = $tomlTpl
foreach ($k in $subst.Keys) {
    $claudeRendered = $claudeRendered.Replace($k, $subst[$k])
    $tomlRendered   = $tomlRendered.Replace($k,   $subst[$k])
}

$claudeRendered | Out-File -FilePath (Join-Path $TaskRoot "CLAUDE.auditor.md") -Encoding utf8
$tomlRendered   | Out-File -FilePath (Join-Path $codexHomeDir "config.toml")   -Encoding utf8

# Stage 4 follow-up: when CODEX_HOME is redirected per-task, codex still
# expects auth.json + installation_id in that same dir. The user's
# default codex config lives at $env:USERPROFILE\.codex\ -- copy the
# auth artifacts forward so the per-task home is a self-contained
# codex environment. Without this, codex 0.130.0 fails with HTTP 401
# "Missing bearer or basic authentication in header" at session start.
$defaultCodexHome = Join-Path $env:USERPROFILE ".codex"
foreach ($authFile in @("auth.json", "installation_id")) {
    $src = Join-Path $defaultCodexHome $authFile
    $dst = Join-Path $codexHomeDir $authFile
    if ((Test-Path $src) -and -not (Test-Path $dst)) {
        Copy-Item -Path $src -Destination $dst -Force
    }
}

# Capture orchestrator-side porcelain baseline (Gate B parity with Phase 3)
$orchPorcelainRaw = & git -C $OrchestratorRoot status --porcelain 2>&1
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("git -C $OrchestratorRoot status --porcelain failed (exit=$LASTEXITCODE): $orchPorcelainRaw")
    exit 1
}
$orchPorcelainLines = @()
foreach ($pline in (($orchPorcelainRaw | Out-String) -split "`r?`n")) {
    if ($pline.Trim().Length -gt 0) { $orchPorcelainLines += $pline.TrimEnd() }
}

$wtTitle = "auditor:$TaskId"
$audPacket = [ordered]@{
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
    branch_audited             = $BranchName
    before_sha_at_audit_start  = $BeforeShaAtAuditStart
    codex_home                 = ($codexHomeDir -replace '/', '\')
    model                      = $Model
    force                      = [bool]$Force.IsPresent
    created_at                 = (Get-Date).ToUniversalTime().ToString("o")
    wt_window_title            = $wtTitle
    orch_porcelain_baseline    = @($orchPorcelainLines)
}
($audPacket | ConvertTo-Json -Depth 10) | Out-File -FilePath (Join-Path $TaskRoot "auditor_packet.json") -Encoding utf8

$promptLines = @(
    "Read ./CLAUDE.auditor.md in the current directory - it is your contract and lists absolute paths to prompts/schemas/inputs.",
    "Then follow prompts/auditor.md (linked from that CLAUDE.auditor.md). Read-only audit; produce audit_report.json + announce AUDIT READY."
)
($promptLines -join "`r`n") | Out-File -FilePath (Join-Path $TaskRoot "prompt.auditor.md") -Encoding utf8

# Pre-trust task root + orchestrator + path_local (path_local read-only for codex).
# Pre-trust extra_writable_dir too when set (codex needs read access to audit it).
Write-PreTrust -AbsPath $TaskRoot
Write-PreTrust -AbsPath $OrchestratorRoot
Write-PreTrust -AbsPath $PathLocal
if ($ExtraWritableDir) {
    Write-PreTrust -AbsPath $ExtraWritableDir
}

$result = [ordered]@{
    task_id                    = $TaskId
    task_root                  = $TaskRoot
    project_path               = $PathLocal
    path_local                 = $PathLocal
    extra_writable_dir         = $ExtraWritableDir
    git_target_dir             = $GitTargetDir
    branch_audited             = $BranchName
    before_sha_at_audit_start  = $BeforeShaAtAuditStart
    codex_home                 = ($codexHomeDir -replace '/', '\')
    model                      = $Model
    wt_window_title            = $wtTitle
    prepare_only               = [bool]$PrepareOnly.IsPresent
    force                      = [bool]$Force.IsPresent
}

if ($PrepareOnly) {
    ($result | ConvertTo-Json -Compress)
    exit 0
}

$wt = Get-Command wt.exe -ErrorAction SilentlyContinue
if (-not $wt) {
    Write-Warning "wt.exe not found in PATH. Files prepared at: $TaskRoot"
    $runWrapper = Join-Path $PSScriptRoot "_run-auditor.ps1"
    $modelSuffix = if ($Model) { " -Model `"$Model`"" } else { "" }
    Write-Warning "Manual run: powershell.exe -NoExit -ExecutionPolicy Bypass -File ""$runWrapper"" -TaskRoot ""$TaskRoot"" -ProjectPath ""$PathLocal"" -OrchestratorRoot ""$OrchestratorRoot"" -PathLocal ""$PathLocal""$modelSuffix"
    ($result | ConvertTo-Json -Compress)
    exit 2
}

$runWrapper = Join-Path $PSScriptRoot "_run-auditor.ps1"
# Build the powershell arg list dynamically so -Model is only present
# when non-empty (PowerShell rejects "-Model ''" as MissingArgument).
$wtPsArgs = @(
    "-NoExit", "-ExecutionPolicy", "Bypass",
    "-File", $runWrapper,
    "-TaskRoot", $TaskRoot,
    "-ProjectPath", $PathLocal,
    "-OrchestratorRoot", $OrchestratorRoot,
    "-PathLocal", $PathLocal
)
if ($ExtraWritableDir) {
    $wtPsArgs += @("-ExtraWritableDir", $ExtraWritableDir)
}
if ($Model) {
    $wtPsArgs += @("-Model", $Model)
}
& wt.exe -w 0 nt --title $wtTitle powershell.exe @wtPsArgs

($result | ConvertTo-Json -Compress)
