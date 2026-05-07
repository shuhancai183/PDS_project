$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

param(
    [switch]$Reset
)

if (-not $env:DATABASE_URL) {
    $env:DATABASE_URL = Read-Host "Paste Neon DATABASE_URL"
}

$env:SECRET_KEY = "snickr-local-remote-init"

if ($Reset) {
    python -m flask --app app init-db --reset
} else {
    python -m flask --app app init-db
}
