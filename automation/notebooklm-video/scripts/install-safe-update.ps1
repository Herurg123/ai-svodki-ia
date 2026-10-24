[CmdletBinding()]
param(
    [string]$TargetDir = 'C:\TRASH\NotebookLMBot',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Run FROM the extracted update ZIP, not from the NotebookLMBot directory.
# Never modify config/state/tokens/browser profile/downloads/logs/_bak/scheduler.
$releaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $releaseDir 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'manifest.json не найден' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$targetRoot = [IO.Path]::GetFullPath($TargetDir).TrimEnd('\')
if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
    throw "Рабочий каталог отсутствует: $targetRoot"
}
if ($manifest.schema -ne 1 -or $manifest.files.Count -lt 1) {
    throw 'Неверная версия манифеста обновления'
}
foreach ($lock in @('full-worker.lock','scheduled-worker.lock')) {
    if (Test-Path -LiteralPath (Join-Path $targetRoot $lock)) {
        throw "Обнаружен $lock; обновлять работающий или незавершённый комбайн запрещено"
    }
}

$plan = New-Object 'System.Collections.Generic.List[object]'
foreach ($entry in $manifest.files) {
    $name = [string]$entry.file
    if ($name -notmatch '^[A-Za-z0-9_.-]+$' -or $name -eq '_bak') {
        throw "Небезопасный путь в манифесте: $name"
    }
    $source = Join-Path (Join-Path $releaseDir 'payload') $name
    $dest = Join-Path $targetRoot $name
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "В ZIP не найден исходник: $name"
    }
    $sourceSha = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceSha -ne [string]$entry.newSha256) {
        throw "Ошибка SHA-256 ZIP для $name, установка отменена"
    }
    $exists = Test-Path -LiteralPath $dest -PathType Leaf
    $actual = if ($exists) {
        (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
    } else { $null }
    $old = @($entry.allowedOldSha256)
    if (-not $exists -and -not [bool]$entry.allowAbsent) {
        throw "Отсутствует производственный файл $name; blind install запрещён"
    }
    if ($exists -and $actual -ne [string]$entry.newSha256 -and $actual -notin $old) {
        throw "Неизвестная/локально изменённая версия $name (SHA-256: $actual); ничего не заменено"
    }
    $action = if ($actual -eq [string]$entry.newSha256) { 'unchanged' }
              elseif ($exists) { 'replace' }
              else { 'create' }
    $plan.Add([pscustomobject]@{Name=$name;Source=$source;Dest=$dest;
        OldSha=$actual;NewSha=[string]$entry.newSha256;Action=$action;Existed=$exists})
}
Write-Host "Update commit: $($manifest.targetSha)"
foreach ($p in $plan) { Write-Host "$($p.Action): $($p.Name)" }
if (-not $Apply) {
    Write-Host 'DRY-RUN завершён. Никакие файлы не изменены. Для установки повторите с -Apply.'
    exit 0
}
$needs = @($plan | Where-Object { $_.Action -ne 'unchanged' })
if ($needs.Count -eq 0) {
    Write-Host 'Все производственные файлы уже соответствуют целевой версии; ничего не менялось.'
    exit 0
}
$backupParent = Split-Path -Parent $targetRoot
$backupDir = Join-Path $backupParent ('NotebookLMBot-update-backups\' +
    (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $manifest.targetSha.Substring(0,8))
if (Test-Path -LiteralPath $backupDir) { throw "Backup path уже существует: $backupDir" }
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$backups = New-Object 'System.Collections.Generic.List[object]'
# Complete and verify all backups BEFORE replacing the first production file.
foreach ($p in $needs) {
    if ($p.Existed) {
        $backup = Join-Path $backupDir $p.Name
        Copy-Item -LiteralPath $p.Dest -Destination $backup -ErrorAction Stop
        $backedSha = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($backedSha -ne $p.OldSha) { throw "Резервная копия $($p.Name) не прошла SHA-256" }
    }
    $backups.Add([pscustomobject]@{file=$p.Name;existed=$p.Existed;oldSha256=$p.OldSha;
        newSha256=$p.NewSha})
}
$backups | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $backupDir 'backup-manifest.json') -Encoding UTF8
$attempted = New-Object 'System.Collections.Generic.List[object]'
try {
    foreach ($p in $needs) {
        # Source and destination hashes were preflighted; verify live file again
        # to catch any concurrent mutation before touching it.
        if ($p.Existed) {
            $liveSha = (Get-FileHash -LiteralPath $p.Dest -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($liveSha -ne $p.OldSha) { throw "Файл $($p.Name) изменился после preflight" }
        } elseif (Test-Path -LiteralPath $p.Dest) {
            throw "Новый файл $($p.Name) появился после preflight"
        }
        $attempted.Add($p)
        Copy-Item -LiteralPath $p.Source -Destination $p.Dest -Force -ErrorAction Stop
        $installedSha = (Get-FileHash -LiteralPath $p.Dest -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($installedSha -ne $p.NewSha) { throw "Не совпала SHA-256 установленного $($p.Name)" }
    }
} catch {
    $reason = $_.Exception.Message
    foreach ($p in $attempted) {
        try {
            if ($p.Existed) {
                Copy-Item -LiteralPath (Join-Path $backupDir $p.Name) -Destination $p.Dest -Force
            } else {
                Remove-Item -LiteralPath $p.Dest -Force -ErrorAction SilentlyContinue
            }
        } catch { Write-Warning "Rollback $($p.Name) не выполнен: $_" }
    }
    throw "Установка отменена ($reason). Попытка отката выполнена, backup: $backupDir"
}
Write-Host "Установка успешна: $($manifest.targetSha). Резервные копии: $backupDir"
Write-Host 'Проверки: node --check full-worker.js; node --check vk-stage.mjs; node --check dzen-article-link.js'
