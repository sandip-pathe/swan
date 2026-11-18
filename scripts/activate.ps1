# Dot-source this script to use workspace-local tools: . .\scripts\activate.ps1
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$nodePathFile = Join-Path $workspaceRoot '.tools\node-path.txt'
$toolPaths = @()
if (Test-Path -LiteralPath $nodePathFile) { $toolPaths += (Get-Content -LiteralPath $nodePathFile -Raw).Trim() }
$toolPaths += @('.tools\uv', '.tools\git\cmd', '.tools\pgsql\bin') | ForEach-Object { Join-Path $workspaceRoot $_ }
$toolPaths += @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313')
)
$toolPaths += Join-Path $workspaceRoot '.venv\Scripts'
foreach ($toolPath in $toolPaths) {
    if ((Test-Path -LiteralPath $toolPath) -and (($env:PATH -split ';') -notcontains $toolPath)) { $env:PATH = $toolPath + ';' + $env:PATH }
}
$env:VIRTUAL_ENV = Join-Path $workspaceRoot '.venv'
$env:NEXT_TELEMETRY_DISABLED = '1'
$env:PSYCOPG_IMPL = 'python'
