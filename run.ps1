param(
  [switch]$Atlas
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
if (-not (Test-Path $py)) { $py = "py" }
if (-not (Test-Path (Join-Path $root ".venv\Scripts\python.exe"))) {
  & $py -m venv .venv
}
$venvPy = Join-Path $root ".venv\Scripts\python.exe"
& $venvPy -m pip install -r (Join-Path $root "requirements.txt")
$launch = @("-m", "proba.launch")
if ($Atlas) { $launch += "--atlas" }
& $venvPy @launch
