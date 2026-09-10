param(
    [string]$Version = "1.0.0-rc1",
    [switch]$RequireInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.13 -m venv .venv
    }
    else {
        python -m venv .venv
    }
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt

$BuildDirectory = Join-Path $ProjectRoot "build"
$DistributionDirectory = Join-Path $ProjectRoot "dist\EchandoChalPOS"
$ReleaseDirectory = Join-Path $ProjectRoot "release"

foreach ($Target in @($BuildDirectory, $DistributionDirectory, $ReleaseDirectory)) {
    if (Test-Path $Target) {
        Remove-Item -Recurse -Force $Target
    }
}

& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm echandochal_pos.spec
& .\.venv\Scripts\python.exe tools\verify_clean_distribution.py $DistributionDirectory

New-Item -ItemType Directory -Force -Path $ReleaseDirectory | Out-Null
$PortableArchive = Join-Path $ReleaseDirectory (
    "EchandoChalPOS-Portable-{0}.zip" -f $Version
)
Compress-Archive -Path $DistributionDirectory -DestinationPath $PortableArchive

$InnoCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
) | Where-Object { $_ -and (Test-Path $_) }

if ($InnoCandidates.Count -gt 0) {
    $InnoCompiler = $InnoCandidates | Select-Object -First 1
    & $InnoCompiler "/DMyAppVersion=$Version" "installer\echandochal_pos.iss"
}
elseif ($RequireInstaller) {
    throw "No se encontró Inno Setup 6; no fue posible crear el instalador."
}
else {
    Write-Warning "No se encontró Inno Setup 6. Se generó únicamente la versión portable."
}

Write-Host ""
Write-Host "Compilación limpia terminada."
Write-Host "Ejecutable: dist\EchandoChalPOS\EchandoChalPOS.exe"
Write-Host "Entregables: release"
