param([ValidateSet('start', 'stop', 'status')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'activate.ps1')
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$dataDir = Join-Path $workspaceRoot '.local\postgres\data'
$logFile = Join-Path $workspaceRoot '.local\postgres\server.log'
$envFile = Join-Path $workspaceRoot '.env'
$pgCtl = Join-Path $workspaceRoot '.tools\pgsql\bin\pg_ctl.exe'
if (-not (Test-Path -LiteralPath $pgCtl)) { throw 'PostgreSQL binaries are not installed in .tools/pgsql.' }

if ($Action -eq 'stop') {
    & $pgCtl -D $dataDir -m fast -w stop
    if ($LASTEXITCODE -ne 0) { throw 'Database stop failed.' }
    exit
}
if ($Action -eq 'status') { & $pgCtl -D $dataDir status; exit $LASTEXITCODE }

if (-not (Test-Path -LiteralPath (Join-Path $dataDir 'PG_VERSION'))) {
    if (Test-Path -LiteralPath $envFile) { throw 'An existing root .env requires manual reconciliation before initializing a new database.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dataDir) | Out-Null
    $passwordBytes = New-Object byte[] 32
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($passwordBytes) } finally { $rng.Dispose() }
    $password = ([BitConverter]::ToString($passwordBytes)).Replace('-', '').ToLowerInvariant()
    $passwordFile = Join-Path $workspaceRoot '.local\postgres\init-password.tmp'
    try {
        [IO.File]::WriteAllText($passwordFile, $password, [Text.UTF8Encoding]::new($false))
        & (Join-Path $workspaceRoot '.tools\pgsql\bin\initdb.exe') -D $dataDir -U swan --pwfile=$passwordFile --auth=scram-sha-256 --encoding=UTF8 --locale=C
        if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
        [IO.File]::AppendAllText((Join-Path $dataDir 'postgresql.conf'), "`nlisten_addresses = '127.0.0.1'`nport = 54329`ntimezone = 'UTC'`n", [Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText($envFile, "DATABASE_URL=postgresql+psycopg://swan:${password}@127.0.0.1:54329/swan_trade`n", [Text.UTF8Encoding]::new($false))
    } finally {
        if (Test-Path -LiteralPath $passwordFile) { Remove-Item -LiteralPath $passwordFile }
        $password = $null
    }
}

& $pgCtl -D $dataDir status *> $null
if ($LASTEXITCODE -ne 0) {
    $process = Start-Process -FilePath $pgCtl -ArgumentList @('-D', ('"' + $dataDir + '"'), '-l', ('"' + $logFile + '"'), '-w', 'start') -WindowStyle Hidden -PassThru
    $process.WaitForExit()
    $process.Refresh()
    if ($process.ExitCode -ne 0) { throw 'Database startup failed. Inspect the local PostgreSQL server log.' }
}
if (-not (Test-Path -LiteralPath $envFile)) { throw 'Database environment configuration is missing.' }
$databaseLine = Get-Content -LiteralPath $envFile | Where-Object { $_ -like 'DATABASE_URL=*' } | Select-Object -First 1
$connection = [Uri]($databaseLine.Substring('DATABASE_URL='.Length).Replace('postgresql+psycopg://', 'postgresql://'))
$databasePort = $connection.Port
if ($databasePort -lt 1 -or $databasePort -gt 65535) { throw 'DATABASE_URL requires an explicit valid port.' }
$oldPassword = $env:PGPASSWORD
try {
    $env:PGPASSWORD = [Uri]::UnescapeDataString(($connection.UserInfo -split ':', 2)[1])
    $psql = Join-Path $workspaceRoot '.tools\pgsql\bin\psql.exe'
    $exists = & $psql -h 127.0.0.1 -p $databasePort -U swan -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'swan_trade'" -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw 'Database connection failed.' }
    if (($exists -join '').Trim() -ne '1') {
        & (Join-Path $workspaceRoot '.tools\pgsql\bin\createdb.exe') -h 127.0.0.1 -p $databasePort -U swan swan_trade
        if ($LASTEXITCODE -ne 0) { throw 'Database creation failed.' }
    }
    & $psql -h 127.0.0.1 -p $databasePort -U swan -d swan_trade -tAc 'SELECT current_database()' -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) { throw 'Database verification failed.' }
} finally { $env:PGPASSWORD = $oldPassword }
Write-Output "PostgreSQL is ready on 127.0.0.1:$databasePort. Credentials remain in the ignored root .env."
