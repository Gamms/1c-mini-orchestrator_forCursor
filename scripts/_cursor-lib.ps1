#requires -Version 5
<#
.SYNOPSIS
    Shared helpers for Cursor SDK orchestrator runs.
#>

function Get-OrchestratorPython {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return "py" }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return "python" }
    throw "Python not found (need py or python on PATH)"
}

function Invoke-OrchestratorPy {
    param([Parameter(ValueFromRemainingArguments=$true)][string[]]$ScriptArgs)
    $py = Get-OrchestratorPython
    & $py @ScriptArgs
    return $LASTEXITCODE
}

function Get-CursorRunnerScript {
    return (Join-Path $PSScriptRoot "_python\cursor_runner.py")
}

function Invoke-CursorAgentTab {
    param(
        [Parameter(Mandatory=$true)][string]$Phase,
        [Parameter(Mandatory=$true)][string]$TaskRoot,
        [Parameter(Mandatory=$true)][string]$Title,
        [Parameter(Mandatory=$true)][string]$RunWrapper,
        [hashtable]$RunParams = @{}
    )

    $py = Get-OrchestratorPython
    $runner = Get-CursorRunnerScript

    $wt = Get-Command wt.exe -ErrorAction SilentlyContinue
    if (-not $wt) {
        Write-Warning "wt.exe not found in PATH. Run manually:"
        $argList = @(
            "-NoExit", "-ExecutionPolicy", "Bypass",
            "-File", $RunWrapper
        )
        foreach ($k in $RunParams.Keys) {
            $argList += @("-$k", [string]$RunParams[$k])
        }
        Write-Warning ("powershell.exe {0}" -f ($argList -join " "))
        return $false
    }

    $wtPsArgs = @(
        "-NoExit", "-ExecutionPolicy", "Bypass",
        "-File", $RunWrapper
    )
    foreach ($k in $RunParams.Keys) {
        $wtPsArgs += @("-$k", [string]$RunParams[$k])
    }

    & wt.exe -w 0 nt --title $Title powershell.exe @wtPsArgs
    return $true
}

function Get-OrchestratorRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-CursorApiKeyEnvName {
    param([string]$OrchestratorRoot = "")
    if (-not $OrchestratorRoot) {
        $OrchestratorRoot = Get-OrchestratorRoot
    }
    $cfgPath = Join-Path $OrchestratorRoot "orchestrator.yaml"
    $envName = "CURSOR_API_KEY"
    if (Test-Path $cfgPath) {
        foreach ($line in (Get-Content -Path $cfgPath -Encoding UTF8)) {
            if ($line -match '^\s*api_key_env:\s*(\S+)') {
                $envName = $Matches[1]
                break
            }
        }
    }
    return $envName
}

function Import-CursorApiKeyFromLocalFiles {
    param(
        [Parameter(Mandatory=$true)][string]$OrchestratorRoot,
        [Parameter(Mandatory=$true)][string]$EnvName
    )

    if (Test-Path Env:$EnvName) {
        $val = [string](Get-Item Env:$EnvName).Value
        if ($val.Trim().Length -gt 0) { return $true }
    }

    $candidates = @(
        (Join-Path $OrchestratorRoot ".env"),
        (Join-Path $OrchestratorRoot "config\cursor-api-key.local")
    )

    foreach ($path in $candidates) {
        if (-not (Test-Path $path)) { continue }
        $raw = Get-Content -Path $path -Raw -Encoding UTF8
        if (-not $raw) { continue }
        foreach ($line in ($raw -split "`r?`n")) {
            $line = $line.Trim()
            if (-not $line -or $line.StartsWith("#")) { continue }
            if ($line -match '^\s*CURSOR_API_KEY\s*=\s*(.+)$') {
                $val = $Matches[1].Trim().Trim('"').Trim("'")
                Set-Item -Path Env:$EnvName -Value $val
                return $true
            }
            if ($line -match '^(crsr_|cursor_)') {
                Set-Item -Path Env:$EnvName -Value $line
                return $true
            }
        }
    }
    return $false
}

function Ensure-CursorApiKey {
    $root = Get-OrchestratorRoot
    $envName = Get-CursorApiKeyEnvName -OrchestratorRoot $root
    if (Import-CursorApiKeyFromLocalFiles -OrchestratorRoot $root -EnvName $envName) {
        return $true
    }
    return $false
}

function Test-CursorApiKey {
    $envName = Get-CursorApiKeyEnvName
    if (Ensure-CursorApiKey) { return $true }
    [Console]::Error.WriteLine("$envName is not set.")
    [Console]::Error.WriteLine("Set env var OR create config/cursor-api-key.local (see config/cursor-api-key.local.example).")
    [Console]::Error.WriteLine("Note: .cmd wrappers use -NoProfile and do not load your PowerShell profile.")
    return $false
}

function Test-ProjectRegistryComplete {
    param([Parameter(Mandatory=$true)][hashtable]$Cfg)

    if (-not $Cfg['path_local']) { return $false }
    if ($Cfg['mcp_config_file']) { return $true }
    if (-not $Cfg['codemeta_port']) { return $false }
    if (-not $Cfg['vm_docker_host']) { return $false }
    return $true
}

function Test-ProjectPathInvariant {
    param(
        [Parameter(Mandatory=$true)][string]$ProjectPath,
        [Parameter(Mandatory=$true)][hashtable]$Cfg,
        [Parameter(Mandatory=$true)][string]$ProjectId
    )

    if (-not (Test-Path $ProjectPath)) {
        throw "project path does not exist on disk: $ProjectPath"
    }

    if ($Cfg['skip_path_invariant'] -eq 'true') {
        return
    }

    $cfgXml = Join-Path $ProjectPath "Configuration.xml"
    $catalogsDir = Join-Path $ProjectPath "Catalogs"
    if (-not (Test-Path $cfgXml) -or -not (Test-Path $catalogsDir)) {
        throw @"
project_path is not a 1C XML-dump root: $ProjectPath
expected to find Configuration.xml + Catalogs/ directly under path_local.

For project '$ProjectId': set skip_path_invariant: true in projects.yaml if this is an extension/git-root layout (like PFS).
For docker codemetadata projects: verify path_local points at the XML-dump root.
"@
    }
}

function Write-TaskMcpConfig {
    param(
        [Parameter(Mandatory=$true)][string]$OrchestratorRoot,
        [Parameter(Mandatory=$true)][string]$TaskRoot,
        [Parameter(Mandatory=$true)][string]$DestFileName,
        [Parameter(Mandatory=$true)][hashtable]$Cfg,
        [string]$TemplateRelativePath = "",
        [hashtable]$Subst = @{}
    )

    $destPath = Join-Path $TaskRoot $DestFileName
    if ($Cfg['mcp_config_file']) {
        $srcPath = Join-Path $OrchestratorRoot ($Cfg['mcp_config_file'] -replace '/', '\')
        if (-not (Test-Path $srcPath)) {
            throw "mcp_config_file not found: $srcPath"
        }
        Copy-Item -Path $srcPath -Destination $destPath -Force
        return
    }

    if (-not $TemplateRelativePath) {
        throw "Write-TaskMcpConfig: TemplateRelativePath required when mcp_config_file is empty"
    }
    $mcpTpl = Get-Content -Path (Join-Path $OrchestratorRoot $TemplateRelativePath) -Raw -Encoding UTF8
    foreach ($k in $Subst.Keys) {
        $mcpTpl = $mcpTpl.Replace($k, $Subst[$k])
    }
    $mcpTpl | Out-File -FilePath $destPath -Encoding utf8
}

function Get-ProjectCodemetaUrl {
    param([Parameter(Mandatory=$true)][hashtable]$Cfg)

    if ($Cfg['mcp_config_file']) {
        return "file:" + ($Cfg['mcp_config_file'] -replace '\\', '/')
    }
    return ("http://{0}:{1}/mcp" -f $Cfg['vm_docker_host'], $Cfg['codemeta_port'])
}
