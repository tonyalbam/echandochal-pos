param(
    [string]$Version = "",
    [switch]$RequireInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

# Una sola versión para la interfaz y el instalador: app/version.py.
$VersionSource = Get-Content "app\version.py" -Raw -Encoding UTF8
$VersionMatch = [regex]::Match(
    $VersionSource,
    '(?m)^APP_VERSION\s*=\s*"([^"]+)"'
)
if (-not $VersionMatch.Success) { throw "No se encontró APP_VERSION." }
$SourceVersion = $VersionMatch.Groups[1].Value
if ([string]::IsNullOrWhiteSpace($Version)) { $Version = $SourceVersion }
if ($Version -ne $SourceVersion) {
    throw "La versión del instalador ($Version) debe coincidir con la aplicación ($SourceVersion)."
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.13 -m venv .venv
    }
    else {
        python -m venv .venv
    }
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "No se pudo actualizar pip." }
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "No se pudieron instalar las dependencias." }

$BuildDirectory = Join-Path $ProjectRoot "build"
$DistributionDirectory = Join-Path $ProjectRoot "dist\EchandoChalPOS"
$ReleaseDirectory = Join-Path $ProjectRoot "release"

foreach ($Target in @($BuildDirectory, $DistributionDirectory, $ReleaseDirectory)) {
    if (Test-Path $Target) {
        Remove-Item -Recurse -Force $Target
    }
}

& .\.venv\Scripts\python.exe tools\create_app_icon.py
if ($LASTEXITCODE -ne 0) { throw "No fue posible generar el ícono de Echando Chal." }

& .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm echandochal_pos.spec
if ($LASTEXITCODE -ne 0) { throw "Falló PyInstaller." }
& .\.venv\Scripts\python.exe tools\verify_clean_distribution.py $DistributionDirectory
if ($LASTEXITCODE -ne 0) { throw "La distribución contiene datos operativos o está incompleta." }

New-Item -ItemType Directory -Force -Path $ReleaseDirectory | Out-Null
$PortableArchive = Join-Path $ReleaseDirectory (
    "EchandoChalPOS-Portable-{0}.zip" -f $Version
)
Compress-Archive -Path $DistributionDirectory -DestinationPath $PortableArchive

$InnoCandidates = @(
    "D:\Inno Setup 7\ISCC.exe",
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
) | Where-Object { $_ -and (Test-Path $_) }

if ($InnoCandidates.Count -gt 0) {
    $InnoCompiler = $InnoCandidates | Select-Object -First 1
    & $InnoCompiler "/DMyAppVersion=$Version" "installer\echandochal_pos.iss"
    if ($LASTEXITCODE -ne 0) { throw "Falló la compilación del instalador." }
    $Installer = Join-Path $ReleaseDirectory ("EchandoChalPOS-Setup-{0}.exe" -f $Version)
    if (-not (Test-Path $Installer)) { throw "No se encontró el instalador generado." }
}
elseif ($RequireInstaller) {
    throw "No se encontró Inno Setup 6 o 7; no fue posible crear el instalador."
}
else {
    Write-Warning "No se encontró Inno Setup 6 o 7. Se generó únicamente la versión portable."
}

Write-Host ""
Write-Host "Compilación limpia terminada."
Write-Host "Ejecutable: dist\EchandoChalPOS\EchandoChalPOS.exe"
Write-Host "Entregables: release"
