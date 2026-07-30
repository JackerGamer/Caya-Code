$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue

if (-not $PythonCommand) {
    throw "Python is not available on PATH."
}

& $PythonCommand.Source -c "import fontTools"
if ($LASTEXITCODE -ne 0) {
    throw "FontTools is not installed. Run: python -m pip install --upgrade fonttools"
}

& $PythonCommand.Source (Join-Path $ProjectRoot "build_font.py") @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $PythonCommand.Source (Join-Path $ProjectRoot "verify_font.py") @args
exit $LASTEXITCODE
