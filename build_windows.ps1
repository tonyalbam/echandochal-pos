$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.13 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm echandochal_pos.spec

Write-Host ""
Write-Host "Compilación terminada: dist\EchandoChalPOS\EchandoChalPOS.exe"
