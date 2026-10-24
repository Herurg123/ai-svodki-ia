[CmdletBinding()]
param(
    [string]$TargetDir = 'C:\TRASH\NotebookLMBot',
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ZIP must be extracted outside the production folder. Never touch operator
# configs, tokens, state, downloads, logs, browser data, _bak or scheduler.
$releaseDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$manifestPath = Join-Path $releaseDir 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Отсутствует manifest.json' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$targetRoot = [IO.Path]::GetFullPath($TargetDir).TrimEnd('\')
if (-not (Test-Path -LiteralPath $targetRoot -PathType Container)) {
    throw "Рабочая папка не найдена: $targetRoot"
}
if ($manifest.schema -ne 1 -or $manifest.files.Count -ne 8 -or
    [string]$manifest.targetSha -notmatch '^[0-9a-f]{40}$') {
    throw 'Неизвестная схема или содержимое manifest.json'
}
$allowedNames = @(
    'dzen-article-link.js', 'dzen-article-video.js', 'dzen-publish-direct.js',
    'full-worker.js', 'vk-stage.mjs', 'vk-text.mjs', 'setup-local.ps1', 'package.json'
)
$names = @($manifest.files | ForEach-Object { [string]$_.file })
if (@($names | Sort-Object -Unique).Count -ne 8) {
    throw 'Повторяющиеся файлы в манифесте'
}
foreach ($lock in @('full-worker.lock','scheduled-worker.lock')) {
    if (Test-Path -LiteralPath (Join-Path $targetRoot $lock)) {
        throw "Активная либо неопределённая блокировка $lock; установка запрещена"
    }
}

$plan = New-Object 'System.Collections.Generic.List[object]'
foreach ($entry in $manifest.files) {
    $name = [string]$entry.file
    if (($name -notin $allowedNames) -or ($name -notmatch '^[A-Za-z0-9_.-]+$')) {
        throw "Путь $name не разрешён"
    }
    $source = Join-Path (Join-Path $releaseDir 'payload') $name
    $destination = Join-Path $targetRoot $name
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "В ZIP не найден $name"
    }
    if ([string]$entry.newSha256 -notmatch '^[a-f0-9]{64}$') {
        throw "Некорректная SHA-256 для $name"
    }
    if ([bool]$entry.allowAbsent -and $name -ne 'dzen-article-link.js') {
        throw "Нельзя установить отсутствующий $name без предыдущей версии"
    }
    $sourceSha = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($sourceSha -ne [string]$entry.newSha256) {
        throw "Контрольная сумма ZIP для $name не совпадает"
    }
    $exists = Test-Path -LiteralPath $destination -PathType Leaf
    $oldSha = if ($exists) {
        (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    } else { $null }
    if (-not $exists -and -not [bool]$entry.allowAbsent) {
        throw "Нет ожидаемого производственного файла $name"
    }
    $allowedOld = @($entry.allowedOldSha256)
    if ($exists -and $oldSha -ne [string]$entry.newSha256 -and $oldSha -notin $allowedOld) {
        throw "Незнакомая SHA-256 у $name ($oldSha). Ничего не заменено"
    }
    $action = if ($oldSha -eq [string]$entry.newSha256) { 'unchanged' }
              elseif ($exists) { 'replace' }
              else { 'create' }
    $plan.Add([pscustomobject]@{
        Name=$name; Source=$source; Dest=$destination; Existed=$exists
        OldSha=$oldSha; NewSha=[string]$entry.newSha256; Action=$action
    })
}
Write-Host "Версия обновления (merge Git SHA): $($manifest.targetSha)"
foreach ($item in $plan) { Write-Host "$($item.Action): $($item.Name)" }
if (-not $Apply) {
    Write-Host 'DRY-RUN завершён: ничего не изменено. Повторите с -Apply для установки.'
    exit 0
}
$needs = @($plan | Where-Object { $_.Action -ne 'unchanged' })
if ($needs.Count -eq 0) {
    Write-Host 'Уже установлены те же исходники; изменений нет.'
    exit 0
}
$backupParent = Split-Path -Parent $targetRoot
$backupDir = Join-Path $backupParent (
    'NotebookLMBot-update-backups\' +
    (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $manifest.targetSha.Substring(0,8)
)
if (Test-Path -LiteralPath $backupDir) {
    throw "Резервная папка уже существует: $backupDir"
}
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$backups = New-Object 'System.Collections.Generic.List[object]'
# ALL backup copies must exist and pass verification before first replacement.
foreach ($item in $needs) {
    if ($item.Existed) {
        $backup = Join-Path $backupDir $item.Name
        Copy-Item -LiteralPath $item.Dest -Destination $backup -ErrorAction Stop
        $copiedSha = (Get-FileHash -LiteralPath $backup -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($copiedSha -ne $item.OldSha) {
            throw "Не удалось сохранить подтверждённую копию $($item.Name)"
        }
    }
    $backups.Add([pscustomobject]@{
        file=$item.Name; existed=$item.Existed
        oldSha256=$item.OldSha; newSha256=$item.NewSha
    })
}
$backups | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (
    Join-Path $backupDir 'backup-manifest.json'
) -Encoding UTF8
$attempted = New-Object 'System.Collections.Generic.List[object]'
try {
    foreach ($item in $needs) {
        foreach ($lock in @('full-worker.lock','scheduled-worker.lock')) {
            if (Test-Path -LiteralPath (Join-Path $targetRoot $lock)) {
                throw "Перед заменой появился $lock; требуется остановка"
            }
        }
        if ($item.Existed) {
            $liveSha = (Get-FileHash -LiteralPath $item.Dest -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($liveSha -ne $item.OldSha) {
                throw "Файл $($item.Name) изменился после проверки"
            }
        } elseif (Test-Path -LiteralPath $item.Dest) {
            throw "Файл $($item.Name) появился после проверки"
        }
        $attempted.Add($item)
        Copy-Item -LiteralPath $item.Source -Destination $item.Dest -Force -ErrorAction Stop
        $sha = (Get-FileHash -LiteralPath $item.Dest -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($sha -ne $item.NewSha) { throw "Не совпала SHA-256 $($item.Name) после установки" }
    }
} catch {
    $reason = $_.Exception.Message
    foreach ($item in $attempted) {
        try {
            if ($item.Existed) {
                Copy-Item -LiteralPath (Join-Path $backupDir $item.Name) -Destination $item.Dest -Force
            } else {
                Remove-Item -LiteralPath $item.Dest -Force -ErrorAction SilentlyContinue
            }
        } catch {
            Write-Warning "Откат $($item.Name) не выполнен; проверьте backupDir: $_"
        }
    }
    throw "Установка прервана: $reason. Выполнен откат; копии: $backupDir"
}
Write-Host "Установка выполнена и SHA-256 проверены; копии: $backupDir"
Write-Host 'Безопасная проверка: node --check full-worker.js; node --check dzen-article-link.js; node --check vk-stage.mjs'
