param(
    [string]$Version = "0.1.0",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $RepoRoot
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        py -3 -m venv .venv
    }

    & .\.venv\Scripts\python.exe -m pip install -e ".[dev,packaging]"
    & .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\windows\PowerPointVisualArchive.spec

    if (-not (Test-Path "dist\pptviewer.exe") -or -not (Test-Path "dist\PowerPointArchiveAgent.exe")) {
        throw "PyInstaller did not produce the expected executables."
    }

    if (-not $SkipInstaller) {
        $Iscc = Get-Command ISCC.exe -ErrorAction Stop
        & $Iscc.Source "/DAppVersion=$Version" packaging\windows\PowerPointVisualArchive.iss
    }
}
finally {
    Pop-Location
}
