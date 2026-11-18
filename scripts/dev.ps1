$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'activate.ps1')
Push-Location (Join-Path (Split-Path -Parent $PSScriptRoot) 'apps\web')
try { & npm.cmd run dev -- --hostname 127.0.0.1; if ($LASTEXITCODE -ne 0) { throw 'Frontend exited with an error.' } }
finally { Pop-Location }
