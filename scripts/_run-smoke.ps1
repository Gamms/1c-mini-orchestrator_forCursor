param([string]$Note = "smoke")
$ErrorActionPreference = "Continue"
Write-Host "smoke from powershell: $Note"
$ver = (& claude --version) | Out-String
Write-Host $ver
$markerDir = Join-Path $PSScriptRoot "..\tasks"
if (-not (Test-Path $markerDir)) { New-Item -ItemType Directory -Path $markerDir -Force | Out-Null }
$marker = Join-Path $markerDir ".smoke-marker.txt"
$payload = "smoke OK | note=$Note | claude=$($ver.Trim()) | host=$env:COMPUTERNAME | ts=$(Get-Date -Format o)"
$payload | Out-File -Encoding utf8 -FilePath $marker
Write-Host "marker written: $marker"
Write-Host "smoke done. Press Enter to close."
$null = Read-Host
