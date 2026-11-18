param(
    [ValidateSet('start', 'status', 'stop', 'worker-stop', 'worker-prepare')][string]$Action = 'start',
    [ValidateSet('OBSERVATION', 'VALIDATION', 'AUTONOMOUS')][string]$WorkerMode = 'OBSERVATION'
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$runDirectory = Join-Path $workspaceRoot '.local\run'
New-Item -ItemType Directory -Force -Path $runDirectory | Out-Null

function Test-LocalPort([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $attempt = $client.ConnectAsync('127.0.0.1', $Port)
        if (-not $attempt.Wait(500)) { return $false }
        return $client.Connected
    } catch { return $false } finally { $client.Dispose() }
}

function Get-OwnedProcess($Service) {
    $recordPath = Join-Path $runDirectory ($Service.Name + '.json')
    if (-not (Test-Path -LiteralPath $recordPath)) { return $null }
    $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    $candidate = Get-Process -Id $record.ProcessId -ErrorAction SilentlyContinue
    if ($null -eq $candidate -or $candidate.StartTime.ToUniversalTime().Ticks.ToString() -ne $record.StartTicks) { return $null }
    $details = Get-CimInstance Win32_Process -Filter ("ProcessId = " + $record.ProcessId)
    if ($null -eq $details -or -not $details.CommandLine.Contains($Service.Script)) { return $null }
    return $candidate
}

function Stop-OwnedTree([int]$ProcessId) {
    $children = @(Get-CimInstance Win32_Process -Filter ("ParentProcessId = " + $ProcessId))
    foreach ($child in $children) { Stop-OwnedTree -ProcessId $child.ProcessId }
    Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue
}

$services = @(
    @{ Name = 'api'; Port = 8000; Script = (Join-Path $PSScriptRoot 'api.ps1'); Url = 'http://127.0.0.1:8000/health' },
    @{ Name = 'web'; Port = 3000; Script = (Join-Path $PSScriptRoot 'dev.ps1'); Url = 'http://localhost:3000' }
)

if ($Action -in @('worker-stop', 'worker-prepare')) {
    $workerMutex = New-Object System.Threading.Mutex($false, 'Local\SWANTradeManagedWorker')
    $workerLocked = $false
    try {
    try { $workerLocked = $workerMutex.WaitOne(5000) } catch [System.Threading.AbandonedMutexException] { $workerLocked = $true }
    if (-not $workerLocked) { throw 'Another managed worker operation is running.' }
    $managedWorker = Get-OwnedProcess @{ Name = 'worker'; Script = (Join-Path $PSScriptRoot 'worker.ps1') }
    if ($null -ne $managedWorker) { Stop-OwnedTree -ProcessId $managedWorker.Id }
    if ($Action -eq 'worker-prepare') {
        $workerScript = Join-Path $PSScriptRoot 'worker.ps1'
        $preparedWorker = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $workerScript + '"'), '-Mode', $WorkerMode
        ) -WorkingDirectory $workspaceRoot -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $runDirectory 'worker.stdout.log') `
          -RedirectStandardError (Join-Path $runDirectory 'worker.stderr.log')
        @{ ProcessId = $preparedWorker.Id; StartTicks = $preparedWorker.StartTime.ToUniversalTime().Ticks.ToString(); Mode = $WorkerMode } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runDirectory 'worker.json') -Encoding UTF8
        Start-Sleep -Milliseconds 1500
        $preparedWorker.Refresh()
        if ($preparedWorker.HasExited) { throw 'Worker preparation failed; inspect the private local logs.' }
        Write-Output 'Worker preparation requested; confirm mode and heartbeat in the app. Entries remain paused.'
        exit 0
    }
    Write-Output 'Managed worker stopped. API and web remain running. Exit monitoring is unavailable until a worker starts.'
    exit 0
    } finally {
        if ($workerLocked) { $workerMutex.ReleaseMutex() }
        $workerMutex.Dispose()
    }
}

if ($Action -eq 'start') {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'database.ps1') start
    if ($LASTEXITCODE -ne 0) { throw 'Local database startup failed.' }
}

foreach ($service in $services) {
    $owned = Get-OwnedProcess $service
    if ($Action -eq 'stop') {
        if ($null -ne $owned) { Stop-OwnedTree -ProcessId $owned.Id }
        Write-Output ($service.Name + ': stopped managed process (if running).')
        continue
    }
    if ($Action -eq 'start' -and -not (Test-LocalPort $service.Port)) {
        if ($null -ne $owned) { throw ($service.Name + ' is already starting; inspect its local log.') }
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $service.Script + '"')
        ) -WorkingDirectory $workspaceRoot -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $runDirectory ($service.Name + '.stdout.log')) `
          -RedirectStandardError (Join-Path $runDirectory ($service.Name + '.stderr.log'))
        $record = @{ ProcessId = $process.Id; StartTicks = $process.StartTime.ToUniversalTime().Ticks.ToString() }
        $record | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runDirectory ($service.Name + '.json')) -Encoding UTF8
        $deadline = (Get-Date).AddSeconds(30)
        while (-not (Test-LocalPort $service.Port)) {
            $process.Refresh()
            if ($process.HasExited -or (Get-Date) -ge $deadline) {
                throw ($service.Name + ' did not start. Inspect .local\run\' + $service.Name + '.stderr.log.')
            }
            Start-Sleep -Milliseconds 250
        }
    }
    $listening = Test-LocalPort $service.Port
    Write-Output ($service.Name + ': ' + $(if ($listening) { 'listening' } else { 'not listening yet' }) + ' - ' + $service.Url)
}
$worker = @{ Name = 'worker'; Script = (Join-Path $PSScriptRoot 'worker.ps1') }
$workerMutex = New-Object System.Threading.Mutex($false, 'Local\SWANTradeManagedWorker')
$workerLocked = $false
try {
try { $workerLocked = $workerMutex.WaitOne(5000) } catch [System.Threading.AbandonedMutexException] { $workerLocked = $true }
if (-not $workerLocked) { throw 'Another managed worker operation is running.' }
$ownedWorker = Get-OwnedProcess $worker
if ($Action -eq 'stop') {
    if ($null -ne $ownedWorker) { Stop-OwnedTree -ProcessId $ownedWorker.Id }
    Write-Output 'worker: stopped managed observation process (if running).'
} else {
    if ($Action -eq 'start' -and $null -eq $ownedWorker) {
        $workerProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $worker.Script + '"')
        ) -WorkingDirectory $workspaceRoot -WindowStyle Hidden -PassThru `
          -RedirectStandardOutput (Join-Path $runDirectory 'worker.stdout.log') `
          -RedirectStandardError (Join-Path $runDirectory 'worker.stderr.log')
        @{ ProcessId = $workerProcess.Id; StartTicks = $workerProcess.StartTime.ToUniversalTime().Ticks.ToString() } |
            ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runDirectory 'worker.json') -Encoding UTF8
        Start-Sleep -Milliseconds 1500
        $ownedWorker = Get-OwnedProcess $worker
    }
    Write-Output ('worker: ' + $(if ($null -ne $ownedWorker) { 'managed process running; confirm mode and heartbeat in the app' } else { 'not running; inspect worker.stderr.log (a signed-in local owner is required)' }))
}
} finally {
    if ($workerLocked) { $workerMutex.ReleaseMutex() }
    $workerMutex.Dispose()
}
if ($Action -eq 'stop') {
    Write-Output 'PostgreSQL remains running. Use database.cmd stop when you want to stop it.'
} else {
    Write-Output 'Logs: .local\run\*.log. New workers default to observation; preparing another mode does not arm entries.'
}
