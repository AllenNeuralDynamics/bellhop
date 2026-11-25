<#
.SYNOPSIS
Installer for bellhop.

.DESCRIPTION
Downloads bellhop.zip from a GitHub release of AllenNeuralDynamics/bellhop
and extracts it to the install directory (default: C:\Program Files\AllenInstitute\bellhop).

Must be run from an elevated (Administrator) PowerShell to write to Program Files.

.PARAMETER Version
Release tag to install (e.g. v0.1.0.dev1). Defaults to the most recent release,
including pre-releases.

.PARAMETER InstallDir
Directory to install into. Defaults to C:\Program Files\AllenInstitute\bellhop.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\install_bellhop.ps1

.EXAMPLE
powershell -ExecutionPolicy Bypass -File scripts\install_bellhop.ps1 -Version v0.1.0.dev1
#>

param (
    [string]$Version,
    [string]$InstallDir = "$env:ProgramFiles\AllenInstitute\bellhop"
)

$ErrorActionPreference = 'Stop'

$Repo = 'AllenNeuralDynamics/bellhop'
$AssetName = 'bellhop.zip'

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
    throw "This installer writes to '$InstallDir' and must be run from an elevated (Administrator) PowerShell."
}

# Resolve the release tag (most recent release, including pre-releases)
if (-not $Version) {
    Write-Host "Resolving latest release of $Repo..."
    $releases = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases?per_page=1"
    if (-not $releases) { throw "No releases found for $Repo." }
    $Version = $releases[0].tag_name
}
Write-Host "Installing bellhop $Version to $InstallDir"

# Download bellhop.zip to a temp directory
$tempDir = Join-Path $env:TEMP "bellhop-install-$([guid]::NewGuid())"
New-Item -ItemType Directory -Path $tempDir | Out-Null
$zipPath = Join-Path $tempDir $AssetName

try {
    $downloadUrl = "https://github.com/$Repo/releases/download/$Version/$AssetName"
    Write-Host "Downloading $downloadUrl..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

    # Replace any existing installation
    if (Test-Path $InstallDir) {
        Write-Host "Removing existing installation at $InstallDir..."
        Remove-Item -Path $InstallDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

    Write-Host "Extracting to $InstallDir..."
    Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force

    $exePath = Join-Path $InstallDir 'bellhop.exe'
    if (-not (Test-Path $exePath)) {
        throw "Installation finished but $exePath was not found. The archive layout may have changed."
    }

    Write-Host ""
    Write-Host "bellhop $Version installed successfully." -ForegroundColor Green
    Write-Host "Run it with: & `"$exePath`""
}
finally {
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}
