param(
    [string]$ConfigFile = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ConfigFile)) {
    $ConfigFile = Join-Path $Root "config.json"
}
if (-not (Test-Path $ConfigFile)) {
    throw "Не найден config.json: $ConfigFile"
}

$config = Get-Content -Raw $ConfigFile | ConvertFrom-Json
$args = @(
    "--user-data-dir=$($config.browserProfile)",
    "--remote-debugging-address=$($config.browserDebugHost)",
    "--remote-debugging-port=$($config.browserDebugPort)",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-session-crashed-bubble",
    "--disable-background-mode",
    "--disable-backgrounding-occluded-windows"
)

Start-Process -FilePath $config.browserExecutable -ArgumentList $args
Write-Host "Роботизированный Яндекс.Браузер запущен с профилем: $($config.browserProfile)"
Write-Host "CDP: http://$($config.browserDebugHost):$($config.browserDebugPort)"
