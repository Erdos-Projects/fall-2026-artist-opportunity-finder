# Local environment setup for Windows (Part A: data collection, cleaning, labeling).
#
# Run from a PowerShell terminal in the project folder:
#     .\scripts\setup.ps1
#
# If PowerShell refuses to run scripts, allow them for this terminal only, then retry:
#     Set-ExecutionPolicy -Scope Process Bypass
#
# Safe to run again at any time. It reuses the existing .venv and only installs
# what is missing.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$venvPython = Join-Path $venv "Scripts\python.exe"
$requirements = Join-Path $root "requirements.txt"
$pythonVersion = "3.12"

$uv = Get-Command uv -ErrorAction SilentlyContinue

# 1. Create the virtual environment
if (Test-Path $venvPython) {
    Write-Host "Virtual environment already exists at .venv"
} elseif ($uv) {
    Write-Host "Creating virtual environment with uv (Python $pythonVersion)..."
    uv venv --python $pythonVersion $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
} else {
    # The Microsoft Store placeholder also answers to "python", so skip it.
    $python = Get-Command python -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike "*\WindowsApps\*" }
    if (-not $python) {
        throw "No Python found. Install uv (https://docs.astral.sh/uv/) or Python $pythonVersion, then run this script again."
    }
    Write-Host "Creating virtual environment with $($python.Source)..."
    & $python.Source -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment." }
}

# 2. Install packages
Write-Host "Installing packages from requirements.txt..."
if ($uv) {
    uv pip install --python $venvPython -r $requirements
} else {
    & $venvPython -m pip install -r $requirements
}
if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }

# 3. Create the data folders (their contents are ignored by git)
foreach ($name in "raw", "clean", "labeled") {
    $dir = Join-Path $root "data\$name"
    New-Item -ItemType Directory -Force $dir | Out-Null
    $keep = Join-Path $dir ".gitkeep"
    if (-not (Test-Path $keep)) { New-Item -ItemType File $keep | Out-Null }
}

# 4. Activate the environment in the current terminal
& (Join-Path $venv "Scripts\Activate.ps1")

Write-Host ""
Write-Host "Setup complete. The environment is active in this terminal."
Write-Host "Next time, activate it with:  .venv\Scripts\Activate.ps1"
Write-Host "Leave it with:                deactivate"
