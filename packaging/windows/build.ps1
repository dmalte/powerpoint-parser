param(
    [string]$Version = "0.1.4",
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    throw "Version must be a numeric X.Y.Z release (for example 0.1.3)."
}
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $RepoRoot
try {
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        py -3 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Python environment creation failed (exit $LASTEXITCODE)." }
    }

    & .\.venv\Scripts\python.exe scripts\preflight_windows_package.py --version $Version
    if ($LASTEXITCODE -ne 0) { throw "Windows package source preflight failed (exit $LASTEXITCODE)." }

    & .\.venv\Scripts\python.exe -m pip install -e ".[dev,packaging]"
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed (exit $LASTEXITCODE)." }

    & .\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\windows\PowerPointVisualArchive.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed (exit $LASTEXITCODE)." }

    if (-not (Test-Path "dist\pptviewer.exe") -or -not (Test-Path "dist\PowerPointArchiveAgent.exe")) {
        throw "PyInstaller did not produce the expected executables."
    }

    if (-not $SkipInstaller) {
        # Inno Setup 6/7 usually installs outside PATH on user machines.
        # Prefer an explicit PATH command, then known installation locations.
        $Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        $IsccPath = if ($Iscc) { $Iscc.Source } else { $null }
        if (-not $IsccPath) {
            $ProgramRoots = @($env:ProgramFiles, ${env:ProgramFiles(x86)},
                              $env:LOCALAPPDATA) | Where-Object { $_ }
            foreach ($Root in $ProgramRoots) {
                foreach ($Major in @(7, 6)) {
                    $Candidate = Join-Path $Root "Inno Setup $Major\ISCC.exe"
                    if (Test-Path $Candidate) { $IsccPath = $Candidate; break }
                }
                if ($IsccPath) { break }
            }
        }
        if (-not $IsccPath) { throw "Inno Setup 6 or 7 compiler (ISCC.exe) not found." }
        & $IsccPath "/DAppVersion=$Version" packaging\windows\PowerPointVisualArchive.iss
        if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed (exit $LASTEXITCODE)." }
        $InstallerPath = "dist\installer\PowerPointVisualArchiveSetup-$Version.exe"
        if (-not (Test-Path $InstallerPath)) {
            throw "Inno Setup did not produce the expected installer: $InstallerPath"
        }
    }

    $ArtifactArgs = @("scripts\preflight_windows_package.py", "--version", $Version, "--artifacts", "dist")
    if ($SkipInstaller) { $ArtifactArgs += "--skip-installer" }
    & .\.venv\Scripts\python.exe @ArtifactArgs
    if ($LASTEXITCODE -ne 0) { throw "Windows package artifact preflight failed (exit $LASTEXITCODE)." }
}
finally {
    Pop-Location
}
