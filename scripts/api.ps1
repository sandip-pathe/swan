$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\activate.ps1"
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m uvicorn services.api.app:app --host 127.0.0.1 --port 8000 --no-access-log
exit $LASTEXITCODE
