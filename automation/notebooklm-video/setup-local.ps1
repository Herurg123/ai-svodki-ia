param(
    [string]$TargetDir = "C:\NotebookLMBot",
    [string]$BrowserProfile = "",
    [string]$AllowedIp = "",
    [switch]$ConfigureFtp
)

$ErrorActionPreference = "Stop"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($BrowserProfile)) {
    $BrowserProfile = Join-Path $env:USERPROFILE "NotebookLMBot-yandex-profile"
}
if ([string]::IsNullOrWhiteSpace($AllowedIp)) {
    $AllowedIp = Read-Host "Разрешённый внешний IP для проверки внутри Яндекс.Браузера"
}
if ([string]::IsNullOrWhiteSpace($AllowedIp)) {
    throw "AllowedIp не может быть пустым."
}

New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

$files = @(
    "worker.js",
    "full-worker.js",
    "scheduled-worker.js",
    "browser-session.js",
    "dzen-error-log.js",
    "dzen-duplicate-guard.js",
    "dzen-browser-runner.js",
    "dzen-publish.js",
    "dzen-publish-live.js",
    "dzen-publish-direct.js",
    "dzen-collections.js",
    "dzen-collections-debug.js",
    "package.json",
    "package-lock.json",
    "run-worker.cmd",
    "run-worker-hidden.vbs",
    "run-dzen-publish.cmd",
    "run-dzen-dry-run.cmd",
    "run-dzen-collections-debug.cmd",
    "run-dzen-collections-apply.cmd",
    "open-robot-browser.cmd",
    "open-robot-browser.ps1",
    "install-ftp-support.cmd",
    "configure-ftp-access.ps1",
    "README.md",
    "DEPLOYMENT.md",
    "DZEN_NATIVE_UPLOAD.md",
    "DZEN_VIDEO_EXPERIMENTS.md",
    "DZEN_COLLECTIONS_DEBUG_README.txt",
    "НАСТРОЙКИ.txt",
    "config.example.json",
    "ftp-access.example.json"
)
foreach ($name in $files) {
    Copy-Item (Join-Path $SourceDir $name) (Join-Path $TargetDir $name) -Force
}

$template = Get-Content -Raw (Join-Path $SourceDir "config.example.json") | ConvertFrom-Json
$template.browserProfile = $BrowserProfile
$template.workDir = $TargetDir
$template.downloadDir = Join-Path $TargetDir "downloads"
$template.screenshotsDir = Join-Path $TargetDir "screenshots"
$template.tracesDir = Join-Path $TargetDir "traces"
$template.tempDir = Join-Path $TargetDir "temp"
$template.regularLog = Join-Path $TargetDir "worker.log"
$template.errorLog = Join-Path $TargetDir "!!! ERROR !!!.log"
$template.logRotation.archiveDir = Join-Path $TargetDir "logs"
$template.stateFile = Join-Path $TargetDir "state.json"
$template.descriptionFile = Join-Path $template.downloadDir "_ИИ-Сводка.txt"
$template.successRegistryFile = Join-Path $template.downloadDir "_СКАЧАННЫЕ_ВИДЕО.json"
$template.ftpUpload.accessFile = Join-Path $TargetDir "ftp-access.json"
$template.allowedIp = $AllowedIp.Trim()

$configPath = Join-Path $TargetDir "config.json"
if (Test-Path $configPath) {
    $backup = "$configPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $configPath $backup -Force
    Write-Host "Резервная копия config.json: $backup"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    $configPath,
    ($template | ConvertTo-Json -Depth 20),
    $utf8NoBom
)

Push-Location $TargetDir
try {
    npm ci --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci завершился ошибкой." }
    node --check worker.js
    if ($LASTEXITCODE -ne 0) { throw "node --check worker.js завершился ошибкой." }
    node --check full-worker.js
    if ($LASTEXITCODE -ne 0) { throw "node --check full-worker.js завершился ошибкой." }
    node --check scheduled-worker.js
    if ($LASTEXITCODE -ne 0) { throw "node --check scheduled-worker.js завершился ошибкой." }
    node --check dzen-publish-direct.js
    if ($LASTEXITCODE -ne 0) { throw "node --check dzen-publish-direct.js завершился ошибкой." }
    node --check dzen-collections.js
    if ($LASTEXITCODE -ne 0) { throw "node --check dzen-collections.js завершился ошибкой." }
}
finally {
    Pop-Location
}

$accessPath = Join-Path $TargetDir "ftp-access.json"
if ($ConfigureFtp) {
    & (Join-Path $TargetDir "configure-ftp-access.ps1") -AccessFile $accessPath
}
else {
    Write-Host "FTP-доступ не создавался. При необходимости запустите configure-ftp-access.ps1 отдельно."
}

Write-Host "Локальная установка подготовлена: $TargetDir"
Write-Host "run-worker.cmd запускает полный scheduled flow: NotebookLM -> FTP -> Dzen -> подборки."
Write-Host "Защищённый профиль Яндекс.Браузера не создаётся и не копируется этим скриптом."
Write-Host "Настройку Планировщика Windows выполните по DEPLOYMENT.md."
