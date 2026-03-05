param(
    [switch]$debug
)

Push-Location -Path (Split-Path $MyInvocation.MyCommand.Path)

$venv = Join-Path $PSScriptRoot '.venv\Scripts\Activate.ps1'
if (Test-Path $venv) {
    . $venv
}

if ($debug) {
    Write-Host 'starting scapegoat api in debug mode'
    $env:APP_ENV = 'development'
    uvicorn main:app --reload --log-level debug
} else {
    Write-Host 'starting scapegoat api in production mode'
    $env:APP_ENV = 'production'
    uvicorn main:app --workers 4 --log-level info
}

Pop-Location
