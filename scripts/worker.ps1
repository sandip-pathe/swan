param([ValidateSet('OBSERVATION', 'VALIDATION', 'AUTONOMOUS')][string]$Mode = 'OBSERVATION')
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\activate.ps1"
Set-Location (Split-Path $PSScriptRoot -Parent)
switch ($Mode) {
    'OBSERVATION' { python -m services.market.cli worker --local-owner --observe-only }
    'VALIDATION' { python -m services.market.cli worker --local-owner --validation-only }
    'AUTONOMOUS' { python -m services.market.cli worker --local-owner }
}
exit $LASTEXITCODE
