# LIEM OS Auto-Bootstrapper and Installer
# This script ensures Rust, uv, and a valid Python environment are installed, then configures the virtual environment.

$ErrorActionPreference = "Stop"
Write-Host "=== LIEM OS BOOTSTRAPPER ===" -ForegroundColor Cyan

# 1. Check/Install Rust
$rustcExists = Get-Command rustc -ErrorAction SilentlyContinue
if (-not $rustcExists) {
    Write-Host "[Bootstrap] Rust (rustc) is not installed. Installing Rustup..." -ForegroundColor Yellow
    # Check if winget is available
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            Write-Host "[Bootstrap] Installing Rust via winget..."
            Start-Process winget -ArgumentList "install --id Rust.Rustup --silent --accept-package-agreements --accept-source-agreements" -Wait -NoNewWindow
            Write-Host "[Bootstrap] Rust installation via winget triggered." -ForegroundColor Green
        } catch {
            Write-Host "[Bootstrap] winget failed. Trying direct download..." -ForegroundColor Yellow
            $needDownload = $true
        }
    } else {
        $needDownload = $true
    }

    if ($needDownload) {
        Write-Host "[Bootstrap] Downloading rustup-init.exe..."
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile("https://win.rustup.rs/x86_64", "$env:TEMP\rustup-init.exe")
        Write-Host "[Bootstrap] Running rustup-init.exe silently..."
        Start-Process -FilePath "$env:TEMP\rustup-init.exe" -ArgumentList "-y --default-toolchain stable" -Wait -NoNewWindow
    }
    
    # Update PATH for the current session
    $cargoBin = "$env:USERPROFILE\.cargo\bin"
    if (Test-Path $cargoBin) {
        $env:PATH += ";$cargoBin"
        Write-Host "[Bootstrap] Added Cargo bin path to current session: $cargoBin"
    }
} else {
    Write-Host "[Bootstrap] Rust is already installed: $(rustc --version)" -ForegroundColor Green
}

# 2. Check/Install uv
$uvExists = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvExists) {
    Write-Host "[Bootstrap] uv is not installed. Installing uv..." -ForegroundColor Yellow
    # Check if we can install via powershell script from astral.sh
    try {
        Write-Host "[Bootstrap] Running Astral's official uv installer..."
        Invoke-Expression (Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1")
    } catch {
        # Fallback to pip if python is already present
        if (Get-Command python -ErrorAction SilentlyContinue) {
            Write-Host "[Bootstrap] Failed to install uv via web script, trying pip..." -ForegroundColor Yellow
            python -m pip install uv
        } else {
            Write-Error "[Bootstrap] Could not install uv. Please install Python or winget first."
            exit 1
        }
    }
    
    # Update PATH for current session
    $uvBin = "$env:USERPROFILE\.local\bin"
    if (Test-Path $uvBin) {
        $env:PATH += ";$uvBin"
    }
    $cargoUvBin = "$env:USERPROFILE\.cargo\bin"
    if (Test-Path "$cargoUvBin\uv.exe") {
        $env:PATH += ";$cargoUvBin"
    }

    $uvExists = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvExists) {
        # Check explicit path
        if (Test-Path "$uvBin\uv.exe") {
            $env:PATH += ";$uvBin"
        } else {
            Write-Error "[Bootstrap] uv installation completed but 'uv' was not found in PATH."
            exit 1
        }
    }
    Write-Host "[Bootstrap] uv successfully installed!" -ForegroundColor Green
} else {
    Write-Host "[Bootstrap] uv is already installed: $(uv --version)" -ForegroundColor Green
}

# 3. Handle Python environment
$pythonVersion = "3.12.10"
$pythonExecutable = "python"
$hasPython = $false

if (Get-Command python -ErrorAction SilentlyContinue) {
    try {
        $versionInfo = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
        Write-Host "[Bootstrap] Default Python version found: $versionInfo" -ForegroundColor Green
        $hasPython = $true
    } catch {
        Write-Host "[Bootstrap] Default Python is broken or errored. Will use uv to install Python $pythonVersion." -ForegroundColor Yellow
    }
}

# Clean existing .venv if present to ensure clean install
if (Test-Path ".venv") {
    Write-Host "[Bootstrap] Removing existing .venv folder..."
    Remove-Item -Recurse -Force ".venv"
}

# 4. Create virtual environment
$venvCreated = $false
Write-Host "[Bootstrap] Creating virtual environment (.venv)..."
if ($hasPython) {
    try {
        uv venv .venv
        Write-Host "[Bootstrap] Virtual environment created using default Python." -ForegroundColor Green
        $venvCreated = $true
    } catch {
        Write-Host "[Bootstrap] Failed to create venv using default Python: $_" -ForegroundColor Yellow
    }
}

if (-not $venvCreated) {
    Write-Host "[Bootstrap] Installing Python $pythonVersion using uv..." -ForegroundColor Yellow
    uv python install $pythonVersion
    uv venv .venv --python $pythonVersion
    Write-Host "[Bootstrap] Virtual environment created using Python $pythonVersion." -ForegroundColor Green
}

# 5. Install package and dependencies in editable mode
Write-Host "[Bootstrap] Installing LIEM OS package and dependencies..."
$env:VIRTUAL_ENV = "$PWD\.venv"
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
uv pip install -e .

# 6. Verify installation
Write-Host "[Bootstrap] Verifying installation..."
& ".\.venv\Scripts\liem-os.exe" --help

# Print matching LIEM OS welcome ASCII art in cyan
Write-Host ""
Write-Host ".----------------------------------------." -ForegroundColor Cyan
Write-Host "|                                        |" -ForegroundColor Cyan
Write-Host "|   _    ___ ___ __  __       ___  ___   |" -ForegroundColor Cyan
Write-Host "|  | |  |_ _| __|  \/  |     / _ \/ __|  |" -ForegroundColor Cyan
Write-Host "|  | |__ | || _|| |\/| |    | (_) \__ \  |" -ForegroundColor Cyan
Write-Host "|  |____|___|___|_|  |_|     \___/|___/  |" -ForegroundColor Cyan
Write-Host "|                                        |" -ForegroundColor Cyan
Write-Host "'----------------------------------------'" -ForegroundColor Cyan

# Print matching colorized completion card box
Write-Host ""
Write-Host ".------------------------------------------------------------." -ForegroundColor Green
Write-Host "|                                                            |" -ForegroundColor Green
Write-Host "|  SUCCESS: LIEM OS bootstrap completed successfully!        |" -ForegroundColor Green
Write-Host "|                                                            |" -ForegroundColor Green
Write-Host "|  To initialize your first project workspace, run:          |" -ForegroundColor Green
Write-Host "|  -> .venv\Scripts\liem-os init <project-name>              |" -ForegroundColor Green
Write-Host "|                                                            |" -ForegroundColor Green
Write-Host "'------------------------------------------------------------'" -ForegroundColor Green
Write-Host ""
