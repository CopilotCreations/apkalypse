<#
.SYNOPSIS
    Installs prerequisites for the APK2Spec pipeline.
.DESCRIPTION
    This script installs all required and optional tools via winget, pip, and direct download.
    Run as Administrator for best results.
.NOTES
    Some tools require manual PATH configuration after installation.
#>

param(
    [switch]$SkipWinget,
    [switch]$SkipPip,
    [switch]$SkipApktool,
    [string]$ApktoolPath = "C:\apktool"
)

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " APK2Spec Prerequisites Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[WARNING] Not running as Administrator. Some installations may fail." -ForegroundColor Yellow
}

#region Winget Installations
if (-not $SkipWinget) {
    Write-Host "`n[WINGET] Installing tools via winget..." -ForegroundColor Green
    
    $wingetPackages = @(
        @{ Id = "Microsoft.OpenJDK.17"; Name = "OpenJDK 17" },
        @{ Id = "Google.PlatformTools"; Name = "Android Platform Tools" },
        @{ Id = "Skylot.jadx"; Name = "jadx" },
        @{ Id = "mitmproxy"; Name = "mitmproxy" },
        @{ Id = "Python.Python.3.11"; Name = "Python 3.11" }
    )
    
    foreach ($pkg in $wingetPackages) {
        Write-Host "  Installing $($pkg.Name)..." -ForegroundColor White
        try {
            $result = winget install --id $pkg.Id --accept-source-agreements --accept-package-agreements --silent 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    [OK] $($pkg.Name) installed successfully" -ForegroundColor Green
            } elseif ($result -match "already installed") {
                Write-Host "    [OK] $($pkg.Name) already installed" -ForegroundColor DarkGreen
            } else {
                Write-Host "    [WARN] $($pkg.Name) may have issues (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "    [ERROR] Failed to install $($pkg.Name): $_" -ForegroundColor Red
        }
    }
}
#endregion

#region Pip Installations
if (-not $SkipPip) {
    Write-Host "`n[PIP] Installing Python packages..." -ForegroundColor Green
    
    # Refresh PATH to pick up newly installed Python
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    
    $pipPackages = @(
        "frida-tools",
        "objection"
    )
    
    foreach ($pkg in $pipPackages) {
        Write-Host "  Installing $pkg..." -ForegroundColor White
        try {
            $result = pip install $pkg --quiet 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "    [OK] $pkg installed successfully" -ForegroundColor Green
            } else {
                Write-Host "    [WARN] $pkg may have issues" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "    [ERROR] Failed to install $pkg : $_" -ForegroundColor Red
        }
    }
}
#endregion

#region Apktool Installation (Direct Download)
if (-not $SkipApktool) {
    Write-Host "`n[APKTOOL] Installing apktool via direct download..." -ForegroundColor Green
    
    try {
        # Create apktool directory
        if (-not (Test-Path $ApktoolPath)) {
            New-Item -ItemType Directory -Path $ApktoolPath -Force | Out-Null
            Write-Host "  Created directory: $ApktoolPath" -ForegroundColor White
        }
        
        # Download apktool wrapper script
        $wrapperUrl = "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/windows/apktool.bat"
        $wrapperPath = Join-Path $ApktoolPath "apktool.bat"
        Write-Host "  Downloading apktool.bat..." -ForegroundColor White
        Invoke-WebRequest -Uri $wrapperUrl -OutFile $wrapperPath -UseBasicParsing
        Write-Host "    [OK] Downloaded apktool.bat" -ForegroundColor Green
        
        # Get latest apktool.jar release URL from GitHub API
        Write-Host "  Fetching latest apktool.jar release..." -ForegroundColor White
        $releaseInfo = Invoke-RestMethod -Uri "https://api.github.com/repos/iBotPeaches/Apktool/releases/latest" -UseBasicParsing
        $jarAsset = $releaseInfo.assets | Where-Object { $_.name -match "apktool_.*\.jar$" } | Select-Object -First 1
        
        if ($jarAsset) {
            $jarUrl = $jarAsset.browser_download_url
            $jarPath = Join-Path $ApktoolPath "apktool.jar"
            Write-Host "  Downloading $($jarAsset.name)..." -ForegroundColor White
            Invoke-WebRequest -Uri $jarUrl -OutFile $jarPath -UseBasicParsing
            Write-Host "    [OK] Downloaded apktool.jar (v$($releaseInfo.tag_name))" -ForegroundColor Green
        } else {
            Write-Host "    [ERROR] Could not find apktool.jar in latest release" -ForegroundColor Red
        }
        
        # Add to PATH if not already there
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($currentPath -notlike "*$ApktoolPath*") {
            Write-Host "  Adding $ApktoolPath to user PATH..." -ForegroundColor White
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;$ApktoolPath", "User")
            $env:Path = "$env:Path;$ApktoolPath"
            Write-Host "    [OK] Added to PATH (restart terminal to take effect)" -ForegroundColor Green
        } else {
            Write-Host "    [OK] $ApktoolPath already in PATH" -ForegroundColor DarkGreen
        }
    } catch {
        Write-Host "  [ERROR] Failed to install apktool: $_" -ForegroundColor Red
    }
}
#endregion

#region Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Installation Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host "`n[VERIFICATION] Checking installed tools..." -ForegroundColor Green

# Refresh PATH
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

$tools = @(
    @{ Cmd = "java --version"; Name = "Java" },
    @{ Cmd = "python --version"; Name = "Python" },
    @{ Cmd = "adb --version"; Name = "ADB" },
    @{ Cmd = "jadx --version"; Name = "jadx" },
    @{ Cmd = "mitmproxy --version"; Name = "mitmproxy" },
    @{ Cmd = "frida --version"; Name = "Frida" },
    @{ Cmd = "apktool --version"; Name = "apktool" }
)

foreach ($tool in $tools) {
    try {
        $output = Invoke-Expression $tool.Cmd 2>&1 | Select-Object -First 1
        if ($LASTEXITCODE -eq 0 -or $output) {
            Write-Host "  [OK] $($tool.Name): $output" -ForegroundColor Green
        } else {
            Write-Host "  [--] $($tool.Name): Not found or not in PATH" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  [--] $($tool.Name): Not found or not in PATH" -ForegroundColor Yellow
    }
}

Write-Host "`n[NEXT STEPS]" -ForegroundColor Cyan
Write-Host "  1. Restart your terminal to refresh PATH" -ForegroundColor White
Write-Host "  2. Set ANDROID_SDK_ROOT environment variable" -ForegroundColor White
Write-Host "  3. Set OPENAI_API_KEY or ANTHROPIC_API_KEY" -ForegroundColor White
Write-Host "  4. Run 'pip install -r requirements.txt' in the project directory" -ForegroundColor White
Write-Host "  5. For full Android SDK, download Command Line Tools from:" -ForegroundColor White
Write-Host "     https://developer.android.com/studio#cmdline-tools" -ForegroundColor Gray
Write-Host ""
#endregion
