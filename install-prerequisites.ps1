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
    [switch]$SkipJadx,
    [switch]$SkipAndroidSdk,
    [string]$ApktoolPath = "C:\apktool",
    [string]$JadxPath = "C:\jadx",
    [string]$AndroidSdkPath = "$env:LOCALAPPDATA\Android\Sdk"
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
        @{ Id = "mitmproxy.mitmproxy"; Name = "mitmproxy" },
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

#region Android SDK Installation
if (-not $SkipAndroidSdk) {
    Write-Host "`n[ANDROID SDK] Setting up Android SDK..." -ForegroundColor Green
    
    try {
        # Create Android SDK directory
        if (-not (Test-Path $AndroidSdkPath)) {
            New-Item -ItemType Directory -Path $AndroidSdkPath -Force | Out-Null
            Write-Host "  Created directory: $AndroidSdkPath" -ForegroundColor White
        }
        
        # Download Android Command Line Tools if not present
        $cmdlineToolsPath = Join-Path $AndroidSdkPath "cmdline-tools\latest"
        $sdkmanagerPath = Join-Path $cmdlineToolsPath "bin\sdkmanager.bat"
        
        if (-not (Test-Path $sdkmanagerPath)) {
            Write-Host "  Downloading Android Command Line Tools..." -ForegroundColor White
            $cmdlineToolsUrl = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
            $cmdlineToolsZip = Join-Path $env:TEMP "commandlinetools.zip"
            $cmdlineToolsExtract = Join-Path $env:TEMP "cmdline-tools-extract"
            
            Invoke-WebRequest -Uri $cmdlineToolsUrl -OutFile $cmdlineToolsZip -UseBasicParsing
            
            # Extract to temp folder first
            if (Test-Path $cmdlineToolsExtract) {
                Remove-Item $cmdlineToolsExtract -Recurse -Force
            }
            Expand-Archive -Path $cmdlineToolsZip -DestinationPath $cmdlineToolsExtract -Force
            
            # Move to correct location (cmdline-tools/latest)
            $cmdlineToolsParent = Join-Path $AndroidSdkPath "cmdline-tools"
            if (-not (Test-Path $cmdlineToolsParent)) {
                New-Item -ItemType Directory -Path $cmdlineToolsParent -Force | Out-Null
            }
            
            $extractedFolder = Join-Path $cmdlineToolsExtract "cmdline-tools"
            if (Test-Path $extractedFolder) {
                if (Test-Path $cmdlineToolsPath) {
                    Remove-Item $cmdlineToolsPath -Recurse -Force
                }
                Move-Item -Path $extractedFolder -Destination $cmdlineToolsPath -Force
            }
            
            # Cleanup
            Remove-Item $cmdlineToolsZip -Force -ErrorAction SilentlyContinue
            Remove-Item $cmdlineToolsExtract -Recurse -Force -ErrorAction SilentlyContinue
            
            Write-Host "    [OK] Android Command Line Tools installed" -ForegroundColor Green
        } else {
            Write-Host "    [OK] Android Command Line Tools already installed" -ForegroundColor DarkGreen
        }
        
        # Set ANDROID_SDK_ROOT environment variable
        $currentSdkRoot = [Environment]::GetEnvironmentVariable("ANDROID_SDK_ROOT", "User")
        if (-not $currentSdkRoot) {
            Write-Host "  Setting ANDROID_SDK_ROOT environment variable..." -ForegroundColor White
            [Environment]::SetEnvironmentVariable("ANDROID_SDK_ROOT", $AndroidSdkPath, "User")
            $env:ANDROID_SDK_ROOT = $AndroidSdkPath
            Write-Host "    [OK] ANDROID_SDK_ROOT set to $AndroidSdkPath" -ForegroundColor Green
        } else {
            Write-Host "    [OK] ANDROID_SDK_ROOT already set to $currentSdkRoot" -ForegroundColor DarkGreen
            $AndroidSdkPath = $currentSdkRoot
        }
        
        # Add platform-tools and cmdline-tools to PATH
        $platformToolsPath = Join-Path $AndroidSdkPath "platform-tools"
        $cmdlineToolsBinPath = Join-Path $cmdlineToolsPath "bin"
        
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        $pathsToAdd = @()
        
        if ($currentPath -notlike "*$platformToolsPath*") {
            $pathsToAdd += $platformToolsPath
        }
        if ($currentPath -notlike "*$cmdlineToolsBinPath*") {
            $pathsToAdd += $cmdlineToolsBinPath
        }
        
        if ($pathsToAdd.Count -gt 0) {
            $newPath = $currentPath + ";" + ($pathsToAdd -join ";")
            [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
            $env:Path = "$env:Path;" + ($pathsToAdd -join ";")
            Write-Host "    [OK] Added Android SDK paths to PATH" -ForegroundColor Green
        } else {
            Write-Host "    [OK] Android SDK paths already in PATH" -ForegroundColor DarkGreen
        }
        
        # Accept licenses and install platform-tools if sdkmanager exists
        if (Test-Path $sdkmanagerPath) {
            # Check if platform-tools is already installed
            $adbPath = Join-Path $platformToolsPath "adb.exe"
            if (-not (Test-Path $adbPath)) {
                Write-Host "  Installing platform-tools via sdkmanager..." -ForegroundColor White
                
                # Accept licenses
                $licenseAccept = "y`ny`ny`ny`ny`ny`ny`n"
                $licenseAccept | & $sdkmanagerPath --licenses 2>&1 | Out-Null
                
                # Install platform-tools
                & $sdkmanagerPath "platform-tools" 2>&1 | Out-Null
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "    [OK] platform-tools installed" -ForegroundColor Green
                } else {
                    Write-Host "    [WARN] platform-tools installation may have issues" -ForegroundColor Yellow
                }
            } else {
                Write-Host "    [OK] platform-tools already installed" -ForegroundColor DarkGreen
            }
        }
        
    } catch {
        Write-Host "  [ERROR] Failed to setup Android SDK: $_" -ForegroundColor Red
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

#region jadx Installation (Direct Download)
if (-not $SkipJadx) {
    Write-Host "`n[JADX] Installing jadx via direct download..." -ForegroundColor Green
    
    try {
        # Create jadx directory
        if (-not (Test-Path $JadxPath)) {
            New-Item -ItemType Directory -Path $JadxPath -Force | Out-Null
            Write-Host "  Created directory: $JadxPath" -ForegroundColor White
        }
        
        # Download and extract jadx (skip if cached)
        $jadxBinPath = Join-Path $JadxPath "bin"
        $jadxExePath = Join-Path $jadxBinPath "jadx.bat"
        if (Test-Path $jadxExePath) {
            Write-Host "    [OK] jadx already cached" -ForegroundColor DarkGreen
        } else {
            Write-Host "  Fetching latest jadx release..." -ForegroundColor White
            $releaseInfo = Invoke-RestMethod -Uri "https://api.github.com/repos/skylot/jadx/releases/latest" -UseBasicParsing
            $zipAsset = $releaseInfo.assets | Where-Object { $_.name -match "^jadx-[\d\.]+\.zip$" } | Select-Object -First 1
            
            if ($zipAsset) {
                $zipUrl = $zipAsset.browser_download_url
                $zipPath = Join-Path $env:TEMP "jadx.zip"
                Write-Host "  Downloading $($zipAsset.name)..." -ForegroundColor White
                Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath -UseBasicParsing
                Write-Host "  Extracting jadx..." -ForegroundColor White
                Expand-Archive -Path $zipPath -DestinationPath $JadxPath -Force
                Remove-Item $zipPath -Force
                Write-Host "    [OK] Installed jadx (v$($releaseInfo.tag_name))" -ForegroundColor Green
            } else {
                Write-Host "    [ERROR] Could not find jadx zip in latest release" -ForegroundColor Red
            }
        }
        
        # Add bin folder to PATH if not already there
        if (Test-Path $jadxBinPath) {
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
            if ($currentPath -notlike "*$jadxBinPath*") {
                Write-Host "  Adding $jadxBinPath to user PATH..." -ForegroundColor White
                [Environment]::SetEnvironmentVariable("Path", "$currentPath;$jadxBinPath", "User")
                $env:Path = "$env:Path;$jadxBinPath"
                Write-Host "    [OK] Added to PATH (restart terminal to take effect)" -ForegroundColor Green
            } else {
                Write-Host "    [OK] $jadxBinPath already in PATH" -ForegroundColor DarkGreen
            }
        }
    } catch {
        Write-Host "  [ERROR] Failed to install jadx: $_" -ForegroundColor Red
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
        
        # Download apktool wrapper script (skip if cached)
        $wrapperUrl = "https://raw.githubusercontent.com/iBotPeaches/Apktool/master/scripts/windows/apktool.bat"
        $wrapperPath = Join-Path $ApktoolPath "apktool.bat"
        if (Test-Path $wrapperPath) {
            Write-Host "    [OK] apktool.bat already cached" -ForegroundColor DarkGreen
        } else {
            Write-Host "  Downloading apktool.bat..." -ForegroundColor White
            Invoke-WebRequest -Uri $wrapperUrl -OutFile $wrapperPath -UseBasicParsing
            Write-Host "    [OK] Downloaded apktool.bat" -ForegroundColor Green
        }
        
        # Get latest apktool.jar release URL from GitHub API (skip if cached)
        $jarPath = Join-Path $ApktoolPath "apktool.jar"
        if (Test-Path $jarPath) {
            Write-Host "    [OK] apktool.jar already cached" -ForegroundColor DarkGreen
        } else {
            Write-Host "  Fetching latest apktool.jar release..." -ForegroundColor White
            $releaseInfo = Invoke-RestMethod -Uri "https://api.github.com/repos/iBotPeaches/Apktool/releases/latest" -UseBasicParsing
            $jarAsset = $releaseInfo.assets | Where-Object { $_.name -match "apktool_.*\.jar$" } | Select-Object -First 1
            
            if ($jarAsset) {
                $jarUrl = $jarAsset.browser_download_url
                Write-Host "  Downloading $($jarAsset.name)..." -ForegroundColor White
                Invoke-WebRequest -Uri $jarUrl -OutFile $jarPath -UseBasicParsing
                Write-Host "    [OK] Downloaded apktool.jar (v$($releaseInfo.tag_name))" -ForegroundColor Green
            } else {
                Write-Host "    [ERROR] Could not find apktool.jar in latest release" -ForegroundColor Red
            }
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

# Check environment variables
$envChecks = @(
    @{ Name = "ANDROID_SDK_ROOT"; Required = $true },
    @{ Name = "OPENAI_API_KEY"; Required = $false },
    @{ Name = "ANTHROPIC_API_KEY"; Required = $false },
    @{ Name = "AZURE_OPENAI_API_KEY"; Required = $false }
)

$hasApiKey = $false
$missingEnvVars = @()

foreach ($env in $envChecks) {
    $value = [Environment]::GetEnvironmentVariable($env.Name, "User")
    if (-not $value) {
        $value = [Environment]::GetEnvironmentVariable($env.Name, "Machine")
    }
    
    if ($value) {
        Write-Host "  [OK] $($env.Name) is set" -ForegroundColor Green
        if ($env.Name -match "API_KEY") { $hasApiKey = $true }
    } else {
        if ($env.Required) {
            Write-Host "  [--] $($env.Name) is not set (required)" -ForegroundColor Yellow
            $missingEnvVars += $env.Name
        } else {
            Write-Host "  [--] $($env.Name) is not set (optional)" -ForegroundColor DarkGray
        }
    }
}

if (-not $hasApiKey) {
    Write-Host "`n  [WARN] No API key found. Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or AZURE_OPENAI_API_KEY" -ForegroundColor Yellow
}

# Check for .env file in project directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $scriptDir ".env"
$envExample = Join-Path $scriptDir ".env.example"

if (Test-Path $envFile) {
    Write-Host "`n  [OK] .env file found in project directory" -ForegroundColor Green
} elseif (Test-Path $envExample) {
    Write-Host "`n  [TIP] Copy .env.example to .env and configure your environment:" -ForegroundColor Cyan
    Write-Host "        Copy-Item '$envExample' '$envFile'" -ForegroundColor Gray
}

Write-Host "`n[REMAINING STEPS]" -ForegroundColor Cyan
Write-Host "  1. Restart your terminal to refresh PATH" -ForegroundColor White
if ($missingEnvVars.Count -gt 0) {
    Write-Host "  2. Set missing environment variables: $($missingEnvVars -join ', ')" -ForegroundColor White
    Write-Host "     Or configure them in a .env file" -ForegroundColor Gray
}
Write-Host "  3. Run 'pip install -r requirements.txt' in the project directory" -ForegroundColor White
Write-Host "  4. For full Android SDK, download Command Line Tools from:" -ForegroundColor White
Write-Host "     https://developer.android.com/studio#cmdline-tools" -ForegroundColor Gray
Write-Host ""
#endregion
