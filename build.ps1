$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  throw "Missing .venv. Run .\\run.ps1 first."
}
& $venvPy (Join-Path $root "pack\win_pack.py") stop
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $venvPy -m pip install -q -r (Join-Path $root "requirements.txt")
& $venvPy -m pip install -q pyinstaller
& $venvPy (Join-Path $root "pack\make_icon.py")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $venvPy -m PyInstaller --noconfirm --clean --distpath (Join-Path $root "dist") --workpath (Join-Path $root "build") (Join-Path $root "pack\proba.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $venvPy (Join-Path $root "pack\win_pack.py") copy
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "done"
