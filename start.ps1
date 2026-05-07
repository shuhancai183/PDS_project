$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$env:DATABASE_URL = "postgresql://postgres:csh1q2w3e4r@localhost:5432/snickr"
$env:SECRET_KEY = "snickr-local-demo-secret"
$env:FLASK_DEBUG = "1"

python -m flask --app app run --debug
