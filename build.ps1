$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    python -m venv (Join-Path $ProjectRoot ".venv")
}

& $VenvPython -c "import fontTools" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
}

& $VenvPython (Join-Path $ProjectRoot "build_font.py") @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $VenvPython (Join-Path $ProjectRoot "verify_font.py") @args
