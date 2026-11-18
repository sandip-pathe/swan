$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\activate.ps1"
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m services.market.cli @args
exit $LASTEXITCODE
