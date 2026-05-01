$ErrorActionPreference = "Stop"

$listeners = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
if (-not $listeners) {
    Write-Host "No server is listening on port 5000."
    exit 0
}

$listeners | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
    Write-Host "Stopping process $_ on port 5000..."
    Stop-Process -Id $_ -Force
}

Write-Host "Port 5000 is free."
